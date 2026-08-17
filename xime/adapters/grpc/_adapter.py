from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import grpc.aio

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


class GrpcAdapter:
    """gRPC adapter — wraps grpc.aio.Server into the Xime adapter lifecycle.

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
    - server_id khác "default": port bắt buộc phải truyền vào constructor.
    - Không được có hai GrpcAdapter cùng server_id — Application.use() sẽ báo lỗi.

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
            ca_file:   certs/ca.crt   # optional — needed for mTLS
            mutual:    true            # true = require client certificate
          servers:
            internal:
              tls:
                enabled: true
                mutual: true

    Cert động (rotate không restart): đăng ký provider qua configure_grpc_tls()
    trong config/grpc.py — khi đó cert_file/key_file/ca_file không cần nữa,
    cert được đọc từ provider ở mỗi TLS handshake mới.

    Interceptor order (outermost first):
        1. RequestContextInterceptor  — always present, sets request_id + cleans up
        2. ErrorMappingInterceptor    — always present, maps exceptions → StatusCode
        3. user-declared interceptors — registered via configure_grpc_interceptors()
    """

    def __init__(
        self,
        server_id: str = "default",
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        if server_id != "default" and port is None:
            raise ValueError(
                f"GrpcAdapter(server_id='{server_id}'): "
                "port is required for non-default servers."
            )
        self._server_id = server_id
        self._host_override = host
        self._port_override = port
        self._server: grpc.aio.Server | None = None
        self._app: Application | None = None

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

        # Default server reads full config from application.yml (port, TLS, etc.).
        # Non-default servers: port from constructor, TLS from grpc.servers.<id>.
        # Server default đọc config từ application.yml; server khác: port từ
        # constructor, TLS từ block grpc.servers.<id>.
        if self._server_id == "default":
            config = GrpcServerConfig.from_runtime(runtime)
        else:
            config = GrpcServerConfig.for_server(runtime, self._server_id)
            config = config.model_copy(update={"port": self._port_override})

        bind_host = self._host_override or "[::]"
        interceptors = self._build_interceptors()

        self._server = grpc.aio.server(
            interceptors=interceptors,
            options=config.keepalive.server_options(),
        )

        # Validate packages are importable before trying to fetch instances.
        scanner = GrpcServiceScanner()
        scanner.validate_packages(*grpc_service_registry.get_packages())

        # Register only servicers whose server_id matches this adapter.
        builder = GrpcServiceBuilder(app, self._server_id)
        builder.register_all(self._server, grpc_service_registry.get_bindings())

        # Register code-first controllers (@command/@stream) for this server, if any.
        # Đăng ký controller code-first cho server này (nếu có).
        self._register_codefirst(app)

        # Bind port — any server may enable TLS/mTLS; dynamic provider wins
        # over static files when registered via configure_grpc_tls().
        # Mọi server đều có thể bật TLS/mTLS; provider động (configure_grpc_tls)
        # được ưu tiên hơn đọc file tĩnh.
        credentials = self._build_credentials(app, config)
        if credentials is not None:
            self._server.add_secure_port(f"{bind_host}:{config.port}", credentials)
        else:
            self._server.add_insecure_port(f"{bind_host}:{config.port}")
        self._warn_insecure_mode(config, secure=credentials is not None)

        await self._server.start()
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

        provider_class = grpc_tls_registry.get_provider(self._server_id)
        if provider_class is None:
            return build_server_credentials(config.tls)

        try:
            provider = app.get(provider_class)
        except KeyError:
            raise RuntimeError(
                f"GrpcAdapter('{self._server_id}'): certificate provider "
                f"'{provider_class.__name__}' (configure_grpc_tls) is not in "
                "the DI container. Add its package to dependency.scan() or "
                "dependency.register() in config/dependency.py."
            ) from None

        from .tls._credentials import build_dynamic_server_credentials

        try:
            return build_dynamic_server_credentials(provider, mutual=config.tls.mutual)
        except Exception as exc:
            raise RuntimeError(
                f"GrpcAdapter('{self._server_id}'): certificate provider "
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
                self._server_id, config.port,
            )
        elif not config.tls.mutual:
            _log.warning(
                "gRPC server '%s' on port %d has TLS but not mTLS "
                "(grpc.tls.mutual is false): traffic is encrypted, yet the "
                "server does not verify WHO is calling - any client that trusts "
                "the CA can invoke every RPC.",
                self._server_id, config.port,
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
        if not any(getattr(c, "server_id", "default") == self._server_id for c in controllers):
            return

        output_dir = codefirst_registry.output_dir()
        lock = LockFile.load(codefirst_registry.lock_file())
        model = ContractBuilder(self._server_id, lock).build(controllers)
        if not model.services:
            return

        messages = load_message_classes(output_dir, self._server_id)
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
