from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import grpc.aio

from xime.core.bootstrap._slot import AdapterSlot
from xime.core.bootstrap.adapter import SCALING_REPLICATED, Adapter
from xime.core.exception.framework import StartupException

from ._config import GrpcServerConfig
from .interceptors._config import grpc_interceptor_registry
from .interceptors._context import RequestContextInterceptor
from .interceptors._error import ErrorMappingInterceptor
from .routing._builder import GrpcServiceBuilder
from .routing._config import grpc_service_registry
from .routing._scanner import GrpcServiceScanner
from .tls._credentials import build_server_credentials

if TYPE_CHECKING:
    from xime.core.bootstrap.application import Application

_log = logging.getLogger(__name__)


def _shared_grpc_settings(runtime: Any) -> dict[str, Any]:
    """Phần **chung cho mọi server gRPC** trong khối `grpc:`.

    Ranh giới: thứ **khác nhau giữa các điểm phục vụ** (`port`, `tls`) thì nằm ở
    ô cấu hình; thứ **chung cho cả loại** ở lại đây.

    ⚠ `grpc.servers.<id>` đã **biến mất** ở 0.8. Nó là cái tên thứ ba cho cùng
    một khái niệm, và nó giữ một khoá `port` **chết**: adapter đọc khối đó xong
    ghi đè vô điều kiện bằng đối số constructor, nên người vận hành sửa
    `grpc.servers.<id>.port` trong YAML thì cổng **không đổi**, không một dòng
    cảnh báo.
    """
    raw = runtime.get("grpc")
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if k in ("max_workers", "keepalive")}


class GrpcAdapter(Adapter, scaling=SCALING_REPLICATED):
    """gRPC adapter - wraps grpc.aio.Server into the Xime adapter lifecycle.

    Register via app.use() and start via app.run():

        app = Application()
        app.use(WebAdapter())
        app.use(GrpcAdapter())
        app.run()

    Hỗ trợ nhiều server gRPC trên các port khác nhau:

        app.use(GrpcAdapter())                                  # server_id="default"
        app.use(GrpcAdapter("internal", "0.0.0.0", 50052))     # server_id="internal"

    Quy tắc:
    - server_id="default" (mặc định): port đọc từ application.yml (grpc.port).
    - server_id khác "default": port bắt buộc, kiểm ở start() chứ không ở
      constructor - xem ghi chú trong __init__.
    - Không được có hai GrpcAdapter cùng server_id - Application.use() sẽ báo lỗi.

    Dưới share_load() thì port và cờ shared đến từ khối
    processes.<tiến trình>.grpc.<server_id>, và truyền chúng trong code là **lỗi
    khởi động**. ⚠ Windows không có SO_REUSEPORT nên gRPC không dùng chung cổng
    được ở đó - khai cổng riêng cho từng tiến trình. Xem
    docs/{vn,en}/multi-process.md.

    Servicer thuộc server nào khai báo qua class variable server_id:

        class InternalUserServicer:
            server_id = "internal"   # chỉ đăng ký vào GrpcAdapter("internal", ...)

        class ExternalUserServicer:
            # không khai báo → mặc định "default"

    TLS / mTLS áp dụng được cho mọi server. Server default cấu hình qua
    grpc.tls; server khác qua grpc.servers.<server_id>.tls:
        grpc:
          port: 50051
          tls:
            enabled: true
            cert_file: certs/server.crt   # chế độ tĩnh (không có provider)
            key_file:  certs/server.key
            ca_file:   certs/ca.crt   # optional - needed for mTLS
            mutual:    true            # true = require client certificate
          servers:
            internal:
              tls:
                enabled: true
                mutual: true

    Cert động (rotate không restart): đăng ký provider qua configure_grpc_tls()
    trong config/grpc.py - khi đó cert_file/key_file/ca_file không cần nữa,
    cert được đọc từ provider ở mỗi TLS handshake mới.

    Interceptor order (outermost first):
        1. RequestContextInterceptor - always present, sets request_id + cleans up
        2. ErrorMappingInterceptor - always present, maps exceptions → StatusCode
        3. user-declared interceptors - registered via configure_grpc_interceptors()
    """

    # Khoá tầng hai trong khối `processes:` (`processes.<p>.grpc.<id>`).
    adapter_kind = "grpc"

    # Cổng dùng chung: mỗi tiến trình tự bind, kernel chia tải qua
    # `SO_REUSEPORT`. `grpc.aio` chỉ nhận địa chỉ dạng chuỗi
    # (`add_insecure_port("host:port")`), **không có API nhận socket từ ngoài**,
    # nên đường "cha giữ socket" của web không dùng được ở đây.
    # ⚠ Windows không có `SO_REUSEPORT` - `_reject_unsupported_sharing()` nổ
    # ngay lúc khởi động thay vì để tiến trình thứ hai chết bằng
    # `WinError 10048` giữa chừng.
    share_port_by = "reuseport"

    def __init__(self, server_id: str = "default") -> None:
        """⛔ **Không còn nhận `host` / `port`** - xem `WebAdapter.__init__`.

        Ở gRPC còn một lý do nữa: cờ `shared` quyết định `SO_REUSEPORT` bật hay
        tắt, mà một đối số trong code không mang được thông tin đó.
        """
        self.adapter_id = server_id
        self._server: grpc.aio.Server | None = None
        self._app: Application | None = None
        self._slot: AdapterSlot | None = None

    def assign_slot(self, slot: AdapterSlot) -> None:
        """Nhận ô `process.grpc.<id>` hoặc `processes.<p>.grpc.<id>`."""
        self._slot = slot

    # ------------------------------------------------------------------
    # Adapter protocol
    # ------------------------------------------------------------------

    async def start(self, app: Application) -> None:
        """Build and start the gRPC server.

        Called by Application._run_async() after the DI container is fully built,
        so GrpcServiceBuilder can fetch handler instances from the container.
        Blocks until the server is stopped (via stop() or SIGINT).
        """
        from xime.core.config.runtime import RuntimeConfig
        runtime: RuntimeConfig = app.get(RuntimeConfig)  # type: ignore[assignment]

        self._app = app

        # Cổng và TLS đến từ ô cấu hình; phần chung của khối `grpc:` (max_workers,
        # keepalive) đến từ `_shared_grpc_settings`.
        slot = self._slot
        if slot is None:
            raise StartupException(
                "\ngRPC Adapter Started Without A Configuration Cell\n"
                f"  Adapter: GrpcAdapter({self.adapter_id!r})\n"
                "  Detail : the framework pushes one in every branch of run()."
            )
        if slot.spec.port is None:
            raise StartupException(
                "\ngRPC Endpoint Without A Port\n"
                f"  Config: {slot.where}\n"
                "  Detail: a gRPC endpoint must declare a port."
            )
        config = GrpcServerConfig.model_validate(
            {
                "port": slot.spec.port,
                **_shared_grpc_settings(runtime),
                **(
                    {"tls": slot.spec.options["tls"]}
                    if "tls" in slot.spec.options
                    else {}
                ),
            }
        )
        bind_host = slot.spec.host or "[::]"

        interceptors = self._build_interceptors()

        self._server = grpc.aio.server(
            interceptors=interceptors,
            options=[*config.keepalive.server_options(), *self._reuseport_option()],
        )

        # Validate packages are importable before trying to fetch instances.
        scanner = GrpcServiceScanner()
        scanner.validate_packages(*grpc_service_registry.get_packages())

        # Register only servicers whose server_id matches this adapter.
        builder = GrpcServiceBuilder(app, self.adapter_id)
        builder.register_all(self._server, grpc_service_registry.get_bindings())

        # Register code-first controllers (@command/@stream) for this server, if any.
        # Đăng ký controller code-first cho server này (nếu có).
        self._register_codefirst(app)

        # Bind port - any server may enable TLS/mTLS; dynamic provider wins
        # over static files when registered via configure_grpc_tls().
        # Mọi server đều có thể bật TLS/mTLS; provider động (configure_grpc_tls)
        # được ưu tiên hơn đọc file tĩnh.
        credentials = self._build_credentials(app, config)
        if credentials is not None:
            self._server.add_secure_port(f"{bind_host}:{config.port}", credentials)
        else:
            self._server.add_insecure_port(f"{bind_host}:{config.port}")
        self._warn_insecure_mode(config, secure=credentials is not None)

        # ⭐ Hai dòng này VỐN ĐÃ tách sẵn ở tầng dưới - `grpc.aio` cho
        # `start()` non-blocking rồi `wait_for_termination()` chặn. Trước 0.8
        # framework gộp chúng lại sau một `start()` duy nhất; nay chỉ việc để
        # chúng ở đúng hai chỗ.
        await self._server.start()

    async def serve(self) -> None:
        """Chặn tới khi server dừng. Cổng đã mở từ `start()`."""
        if self._server is not None:
            await self._server.wait_for_termination()

    async def stop(self) -> None:
        """Gracefully stop the gRPC server.

        Waits up to 5 seconds for in-flight RPCs to complete before forcing
        a shutdown. No-op if start() was never called.
        """
        if self._server is not None:
            await self._server.stop(grace=5)
            self._server = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reuseport_option(self) -> list[tuple[str, int]]:
        """Bật/tắt `SO_REUSEPORT` **tường minh** ở nhánh `share_load()`.

        ⚠ Đây là bản vá cho chỗ *"bind thành công"* mang hai nghĩa. gRPC C-core
        bật `SO_REUSEPORT` **mặc định** trên Linux, nên hai tiến trình khai nhầm
        cùng một cổng sẽ bind thành công cả hai và kernel chia đôi request -
        Windows báo lỗi ngay, Linux chạy êm và một nửa request đi vào tiến trình
        không ai định gửi tới. Khai `shared: false` (mặc định) thì tắt hẳn, và
        cổng trùng lại nổ như đáng ra phải thế.

        Ngoài nhánh `share_load()` thì không đụng vào - hành vi của 31 app hiện
        tại giữ nguyên từng bit.
        """
        if self._slot is None:
            return []
        return [("grpc.so_reuseport", 1 if self._slot.spec.shared else 0)]

    def _build_credentials(
        self, app: Application, config: GrpcServerConfig
    ) -> grpc.ServerCredentials | None:
        """Resolve TLS credentials for this server, or None for insecure.

        Resolution order:
        1. tls.enabled is false                  → None (insecure).
        2. provider via configure_grpc_tls()     → dynamic credentials:
           every new handshake re-reads the provider, so certificate rotation
           needs no restart and never touches established sessions.
        3. no provider                           → static file-based credentials.

        Thứ tự: TLS tắt → insecure; có provider → dynamic (rotate không cần
        restart, không cắt phiên đang mở); không có provider → đọc file tĩnh.

        Fails fast with a clear message when the provider is missing from the
        DI container or cannot supply the initial certificate.
        """
        if not config.tls.enabled:
            return None

        from .tls._config import grpc_tls_registry

        provider_class = grpc_tls_registry.get_provider(self.adapter_id)
        if provider_class is None:
            return build_server_credentials(config.tls)

        try:
            provider = app.get(provider_class)
        except KeyError:
            raise RuntimeError(
                f"GrpcAdapter('{self.adapter_id}'): certificate provider "
                f"'{provider_class.__name__}' (configure_grpc_tls) is not in "
                "the DI container. Add its package to dependency.scan() or "
                "dependency.register() in config/dependency.py."
            ) from None

        from .tls._credentials import build_dynamic_server_credentials

        try:
            return build_dynamic_server_credentials(provider, mutual=config.tls.mutual)
        except Exception as exc:
            raise RuntimeError(
                f"GrpcAdapter('{self.adapter_id}'): certificate provider "
                f"'{provider_class.__name__}' failed to supply the initial "
                f"certificate: {exc}\n"
                "Ensure the certificate is loaded before adapters start "
                "(e.g. by a PostConstruct bootstrap such as a Trust startup "
                "orchestrator)."
            ) from exc

    def _warn_insecure_mode(self, config: GrpcServerConfig, secure: bool) -> None:
        """Say out loud, once at startup, that this server is not protected.

        The framework's defaults are permissive (TLS off) on purpose - a dev
        machine must work with an empty application.yml. The danger is that the
        permissive mode is also SILENT, so a production service that lost its
        TLS block looks exactly like a healthy one in the log.
        Mặc định của framework là dễ dãi (TLS tắt) có chủ đích - máy dev phải
        chạy được với application.yml rỗng. Cái nguy là chế độ dễ dãi đó còn IM
        LẶNG, nên service thật mất khối TLS trông y hệt service khoẻ mạnh.
        """
        if not secure:
            _log.warning(
                "gRPC server '%s' on port %d is serving PLAINTEXT: traffic is "
                "unencrypted and any client may call it. Set grpc.tls.enabled "
                "(+ mutual: true for mTLS) in application.yml.",
                self.adapter_id, config.port,
            )
        elif not config.tls.mutual:
            _log.warning(
                "gRPC server '%s' on port %d has TLS but not mTLS "
                "(grpc.tls.mutual is false): traffic is encrypted, yet the "
                "server does not verify WHO is calling - any client that trusts "
                "the CA can invoke every RPC.",
                self.adapter_id, config.port,
            )

    def _register_codefirst(self, app: Application) -> None:
        """Build + register code-first controllers for this server, if configured.

        No-op when configure_grpc_codefirst() was never called. Imports the
        code-first modules lazily so projects that don't use it (and may not have
        protobuf/grpc-tools artifacts) are unaffected.
        Không làm gì nếu chưa configure_grpc_codefirst(). Import lười phần code-first.
        """
        from xime.adapters.grpc.codefirst._config import codefirst_registry

        packages = codefirst_registry.get_packages()
        if not packages:
            return

        from xime.adapters.grpc.codefirst._builder import ContractBuilder
        from xime.adapters.grpc.codefirst._lock import LockFile
        from xime.adapters.grpc.codefirst._pb2_loader import load_message_classes
        from xime.adapters.grpc.codefirst._service_builder import CodeFirstGrpcBuilder
        from xime.core.contract import ControllerScanner

        controllers = ControllerScanner().find_controllers(*packages)
        # Only build/serve when at least one controller targets this server.
        # Chỉ build/serve khi có ít nhất một controller thuộc server này.
        if not any(getattr(c, "server_id", "default") == self.adapter_id for c in controllers):
            return

        output_dir = codefirst_registry.output_dir()
        lock = LockFile.load(codefirst_registry.lock_file())
        model = ContractBuilder(self.adapter_id, lock).build(controllers)
        if not model.services:
            return

        messages = load_message_classes(output_dir, self.adapter_id)
        CodeFirstGrpcBuilder(app, model, messages).register_all(self._server)

    def _build_interceptors(self) -> list[grpc.aio.ServerInterceptor]:
        """Compose the full interceptor stack.

        Built-in interceptors always lead so that context setup and error
        handling wrap every user-declared interceptor and every handler.
        """
        mappings = grpc_interceptor_registry.get_error_mappings()
        built_in: list[grpc.aio.ServerInterceptor] = [
            RequestContextInterceptor(),
            ErrorMappingInterceptor(mappings),
        ]
        return built_in + grpc_interceptor_registry.get_interceptors()
