from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import replace
from ssl import CERT_NONE, CERT_OPTIONAL, CERT_REQUIRED
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI

from xime.core.bootstrap._slot import AdapterSlot
from xime.core.bootstrap.adapter import SCALING_REPLICATED, Adapter
from xime.core.config.runtime import RuntimeConfig
from xime.core.exception.framework import StartupException

from ._cors import validate_cors_options
from ._health import add_health_routes, public_health_paths
from ._markers import resolve_options
from ._registry import registry
from ._server_config import ServerTlsConfig, WebServerConfig
from .middleware import RequestContextMiddleware
from .openapi._builder import build_custom_openapi

if TYPE_CHECKING:
    import uvicorn

    from xime.core.bootstrap.application import Application

_log = logging.getLogger(__name__)

# Spelled-out cert_reqs values mapped to the stdlib constants uvicorn expects.
# Imported by name so the module-level `ssl` symbol stays free for the
# WebAdapter(ssl=...) parameter, which mirrors the `server.ssl` config key.
# Giá trị cert_reqs dạng chữ ánh xạ sang hằng stdlib mà uvicorn cần. Import theo
# tên để tên `ssl` ở mức module còn trống cho tham số WebAdapter(ssl=...), vốn
# đặt theo đúng key cấu hình `server.ssl`.
_CERT_REQS = {
    "none": CERT_NONE,
    "optional": CERT_OPTIONAL,
    "required": CERT_REQUIRED,
}


def _tls_kwargs(tls: ServerTlsConfig, server_id: str) -> dict[str, Any]:
    """Validate TLS settings and return the ssl_* kwargs for uvicorn.Config.

    Returns an empty dict when TLS is not configured, so the plain-HTTP path is
    byte-for-byte what it was before.
    Trả dict rỗng khi không cấu hình TLS, nên đường HTTP thuần y hệt như trước.

    Everything is validated here rather than left to uvicorn because uvicorn's
    failures for a half-configured certificate are undebuggable: a missing
    keyfile surfaces as `SSLError: [SSL] PEM lib`, and a missing certfile as a
    bare `AssertionError` with no message at all. A server that silently serves
    plain HTTP while the operator believes it is HTTPS would be worse still, so
    a bad configuration must stop startup with a message that names the key.
    Validate ở đây chứ không phó mặc uvicorn vì lỗi của nó khi cert khai nửa vời
    là không thể debug: thiếu keyfile ra `SSLError: [SSL] PEM lib`, thiếu certfile
    ra `AssertionError` rỗng message. Tệ hơn nữa là server âm thầm chạy HTTP
    trong khi operator tưởng đang HTTPS, nên cấu hình sai phải chặn startup kèm
    thông báo nêu đúng key.
    """
    if not tls.enabled:
        return {}

    where = f"server.ssl (WebAdapter server_id={server_id!r})"

    # Both halves are required: a certificate without its private key cannot
    # terminate TLS, and vice versa.
    # Phải có cả hai: cert không có private key thì không kết thúc TLS được, và
    # ngược lại.
    missing = [
        name
        for name, value in (("certfile", tls.certfile), ("keyfile", tls.keyfile))
        if not value
    ]
    if missing:
        raise StartupException(
            f"\nIncomplete TLS Configuration\n"
            f"  Config  : {where}\n"
            f"  Missing : {', '.join(missing)}\n"
            f"  Detail  : certfile and keyfile must both be set to serve HTTPS."
        )

    for name, path in (
        ("certfile", tls.certfile),
        ("keyfile", tls.keyfile),
        ("ca_certs", tls.ca_certs),
    ):
        if not path:
            continue
        if not os.path.isfile(path):
            raise StartupException(
                f"\nTLS File Not Found\n"
                f"  Config: {where}.{name}\n"
                f"  Path  : {path}\n"
                f"  Detail: the file does not exist or is not a regular file."
            )
        # Existing but unreadable is the common real-world failure: certbot
        # writes privkey.pem as root-only, so an app running as another user
        # trips over permissions rather than a missing path. Open it now to say
        # so clearly instead of letting uvicorn raise PermissionError mid-serve.
        # Tồn tại mà không đọc được mới là lỗi hay gặp thật: certbot ghi
        # privkey.pem chỉ cho root, app chạy bằng user khác là vấp quyền chứ
        # không phải thiếu file. Mở thử ngay để báo rõ, thay vì để uvicorn ném
        # PermissionError giữa lúc serve.
        try:
            with open(path, "rb"):
                pass
        except OSError as exc:
            raise StartupException(
                f"\nTLS File Not Readable\n"
                f"  Config: {where}.{name}\n"
                f"  Path  : {path}\n"
                f"  Detail: {exc.strerror or exc}"
            ) from exc

    kwargs: dict[str, Any] = {
        "ssl_certfile": tls.certfile,
        "ssl_keyfile": tls.keyfile,
    }
    # Only forward what was actually configured. uvicorn defaults ssl_cert_reqs
    # to ssl.CERT_NONE and ssl_ciphers to a non-empty string, so passing None
    # does not mean "use the default" - it overwrites it and breaks the
    # handshake (verified: ssl_cert_reqs=None raises "None is not a valid
    # VerifyMode" while building the context).
    # Chỉ chuyển tiếp thứ thực sự được cấu hình. uvicorn đặt mặc định
    # ssl_cert_reqs = ssl.CERT_NONE và ssl_ciphers là chuỗi khác rỗng, nên truyền
    # None KHÔNG có nghĩa "dùng mặc định" mà ghi đè mất và hỏng handshake (đã
    # kiểm chứng: ssl_cert_reqs=None ném "None is not a valid VerifyMode").
    if tls.keyfile_password:
        kwargs["ssl_keyfile_password"] = tls.keyfile_password
    if tls.ca_certs:
        kwargs["ssl_ca_certs"] = tls.ca_certs
    if tls.cert_reqs is not None:
        kwargs["ssl_cert_reqs"] = _CERT_REQS[tls.cert_reqs]
    if tls.ciphers:
        kwargs["ssl_ciphers"] = tls.ciphers
    return kwargs


class WebAdapter(Adapter, scaling=SCALING_REPLICATED):
    """HTTP adapter - wraps FastAPI + uvicorn into the Xime adapter lifecycle.

    Register via app.use() and start via app.run():

        app = Application()
        app.use(WebAdapter())
        app.run()

    Hỗ trợ nhiều server trên các port khác nhau:

        app.use(WebAdapter())                              # server_id="default"
        app.use(WebAdapter("admin", "0.0.0.0", 8081))     # server_id="admin"

    Quy tắc:
    - server_id="default" (mặc định): host/port đọc từ application.yml khi không truyền.
    - server_id khác "default": host và port bắt buộc, kiểm ở start() chứ không ở
      constructor - xem ghi chú trong __init__.
    - Không được có hai WebAdapter cùng server_id - Application.use() sẽ báo lỗi.

    Dưới share_load() thì mọi thứ khác: host/port/shared đến từ khối
    processes.<tiến trình>.web.<server_id>, và truyền chúng trong code là **lỗi
    khởi động**. Xem docs/{vn,en}/multi-process.md.

    HTTPS bật bằng khối server.ssl trong application.yml (để trống = HTTP thuần
    như cũ):

        server:
          port: 8107
          ssl:
            certfile: "/etc/letsencrypt/live/example.com/fullchain.pem"
            keyfile: "/etc/letsencrypt/live/example.com/privkey.pem"

    Mọi WebAdapter kế thừa server.ssl, kể cả server phụ - để server phụ không âm
    thầm chạy HTTP khi server chính đã HTTPS. Muốn khác thì truyền tường minh:

        app.use(WebAdapter("admin", "0.0.0.0", 8081, ssl=ServerTlsConfig(...)))
        app.use(WebAdapter("internal", "127.0.0.1", 8082, ssl=ServerTlsConfig()))  # tắt TLS

    Cert phải là cert CA công cộng (certbot...) vì trình duyệt KHÔNG tin CA nội
    bộ; cert do CA nội bộ cấp thì dành cho mTLS giữa service với nhau.

    Controller thuộc server nào khai báo qua class variable server_id:

        class AdminController:
            prefix = "/admin"
            server_id = "admin"   # chỉ đăng ký vào WebAdapter("admin", ...)

        class PublicController:
            prefix = "/api/v1"
            # không khai báo → mặc định "default"

    Startup order (driven by Application._run_async):
        1. Application.start() - DI container fully built
        2. WebAdapter.start(app) - builds FastAPI, registers controllers,
                                       runs uvicorn (blocks until stopped)

    Shutdown order:
        3. WebAdapter.stop() - sets uvicorn.should_exit = True
        4. Application.stop() - PreDestroy hooks, DI dispose

    For HTTP-level integration tests, use build_app() to obtain the FastAPI
    instance without running uvicorn:

        fastapi_app = WebAdapter().build_app(xime_app)
        async with AsyncClient(app=fastapi_app, base_url="http://test") as client:
            ...
    """

    # Khoá tầng hai trong khối `processes:` (`processes.<p>.web.<id>`).
    adapter_kind = "web"

    # Cổng dùng chung: cha `bind()` + `listen()` rồi truyền socket xuống con.
    # uvicorn nhận `serve(sockets=[...])` nên chạy được trên cả hai hệ điều hành
    # (Windows chuyển socket qua `WSADuplicateSocket`, `multiprocessing` lo).
    share_port_by = "inherit"

    def __init__(self, server_id: str = "default") -> None:
        """⛔ **Không còn nhận `host` / `port` / `ssl`.**

        Ba thứ đó nay đến từ cấu hình - `process.web.<id>` cho một tiến trình,
        `processes.<p>.web.<id>` cho nhiều. Lý do khác nhau cho từng cái:

        | | |
        |---|---|
        | `host` / `port` | **Mô tả sự thật** - ở nhánh chia tải thì cha `bind()` rồi truyền socket xuống, nên con **không có cách nào tự chọn cổng**. Một đối số ở đây là lời hứa framework không giữ được |
        | `ssl` | **Ngoại lệ hết lý do tồn tại** - nó sinh ra để phục vụ server phụ cần cert khác, mà server phụ nay có ô cấu hình riêng |
        """
        self.adapter_id = server_id
        self._server: uvicorn.Server | None = None
        self._slot: AdapterSlot | None = None
        self._sockets: list[Any] | None = None

    # ------------------------------------------------------------------
    # Adapter protocol
    # ------------------------------------------------------------------

    def assign_slot(self, slot: AdapterSlot) -> None:
        """Nhận ô `process.web.<id>` hoặc `processes.<p>.web.<id>`."""
        self._slot = slot

    @staticmethod
    def resolve_tls(slot: AdapterSlot, runtime: RuntimeConfig) -> ServerTlsConfig:
        """TLS của một điểm phục vụ: ô trước, `server.ssl` sau.

        ⭐ **Kế thừa `server.ssl` khi ô không khai** là một tính chất bảo mật,
        không phải tiện lợi: một server phụ **âm thầm chạy HTTP** trong khi server
        chính đã HTTPS là lỗ hổng không ai để ý, vì nó vẫn trả lời 200.

        Muốn một điểm phục vụ **không** dùng TLS thì khai rỗng, tường minh:

        ```yaml
        process:
          web:
            public:   { port: 8086 }                       # kế thừa server.ssl
            internal: { port: 8082, ssl: {} }              # cố ý HTTP thuần
        ```

        Đây là chỗ `ssl=ServerTlsConfig()` cũ chuyển tới - cùng ý nghĩa, nhưng
        nay nằm trong cấu hình chứ không trong code.
        """
        raw = slot.spec.options.get("ssl")
        if raw is None:
            return WebServerConfig.from_runtime(runtime).ssl
        return ServerTlsConfig.model_validate(raw)

    # ------------------------------------------------------------------

    async def start(self, app: Application) -> None:
        """Dựng FastAPI và **bind cổng** theo ô cấu hình - rồi TRẢ VỀ.

        ⭐ Từ 0.8 ô **luôn có** ở cả ba nhánh của `run()`, nên ở đây không còn
        nhánh nào để adapter tự đi tìm khoá của riêng nó.
        """
        try:
            import uvicorn
        except ImportError:
            raise RuntimeError(
                "WebAdapter requires uvicorn. "
                "Run: pip install 'uvicorn[standard]' or pip install 'xime[web]'"
            ) from None

        slot = self._slot
        if slot is None:
            raise StartupException(
                "\nWeb Adapter Started Without A Configuration Cell\n"
                f"  Adapter: WebAdapter({self.adapter_id!r})\n"
                "  Detail : the framework pushes one in every branch of run(); "
                "seeing none means start() was called outside run()."
            )

        host = slot.spec.host if slot.spec.host is not None else "0.0.0.0"
        port = slot.spec.port
        if port is None and slot.sock is None:
            raise StartupException(
                "\nWeb Endpoint Without A Port\n"
                f"  Config: {slot.where}\n"
                "  Detail: a web endpoint must declare a port."
            )

        tls = self.resolve_tls(slot, app.get(RuntimeConfig))  # type: ignore[arg-type]
        fastapi_app = self.build_app(app)
        config = uvicorn.Config(
            fastapi_app,
            host=host,
            port=port if port is not None else 0,
            **_tls_kwargs(tls, self.adapter_id),
        )
        _log.info(
            "web %s: process %s serving on %s:%s%s",
            self.adapter_id, slot.process_id, host, port,
            " (shared socket from supervisor)" if slot.sock is not None else "",
        )
        await self._bind(uvicorn, config, [slot.sock] if slot.sock else None)

    async def _bind(
        self, uvicorn: Any, config: Any, sockets: list[Any] | None = None
    ) -> None:
        """Nửa đầu của `uvicorn.Server._serve()` - tới lúc cổng đã mở.

        ⚠ Ba dòng dưới là **những dòng đầu của `_serve()`**, chép ra chứ không
        gọi vào, vì `serve()` gộp cả hai giai đoạn. Chúng phải đi cùng nhau:
        `config.load()` dựng ASGI app, `lifespan_class` phải có trước
        `startup()`, và `startup()` là chỗ cổng thật sự mở.
        """
        if not config.loaded:
            config.load()
        self._server = uvicorn.Server(config)
        self._server.lifespan = config.lifespan_class(config)
        self._sockets = sockets
        await self._server.startup(sockets=sockets)

    async def serve(self) -> None:
        """Nửa sau: phục vụ tới khi `stop()` được gọi, rồi tắt êm.

        `capture_signals()` giữ nguyên hành vi của `Server.serve()`: uvicorn bắt
        `SIGINT`/`SIGTERM` để tắt êm. Bỏ nó là mất tắt êm dưới `systemd`, và cái
        mất đó **không có triệu chứng** cho tới lần deploy đầu tiên.
        """
        if self._server is None:
            return
        with self._server.capture_signals():
            if not self._server.should_exit:
                await self._server.main_loop()
        if self._server.started:
            await self._server.shutdown(sockets=self._sockets)

    async def stop(self) -> None:
        """Signal uvicorn to shut down gracefully. No-op if start() was not called."""
        if self._server is not None:
            self._server.should_exit = True

    # ------------------------------------------------------------------
    # FastAPI app builder (also used for testing)
    # ------------------------------------------------------------------

    def build_app(self, xime_app: Application) -> FastAPI:
        """Build and return the configured FastAPI ASGI app.

        Unlike start(), this does NOT run uvicorn. Use it in integration
        tests to get a testable FastAPI instance:

            fastapi_app = WebAdapter().build_app(app)
            async with AsyncClient(app=fastapi_app, base_url="http://test") as client:
                ...

        The Application must be started (app.start() called) before
        build_app() is invoked so that the DI container is available.
        """
        openapi_config = registry.get_openapi(self.adapter_id)
        has_custom_swagger_title = (
            openapi_config is not None and openapi_config.swagger_ui_title is not None
        )

        @asynccontextmanager
        async def lifespan(fastapi_app: FastAPI) -> AsyncGenerator[None, None]:
            # DI container already built by Application.start() - only register routes.
            self._register_controllers(fastapi_app, xime_app, self.adapter_id)
            yield

        fastapi_app = FastAPI(
            lifespan=lifespan,
            # Disable default Swagger UI when custom title is set - we add our own route below.
            docs_url=None if has_custom_swagger_title else (openapi_config.docs_url if openapi_config else "/docs"),
            redoc_url=openapi_config.redoc_url if openapi_config else "/redoc",
            openapi_url=openapi_config.openapi_url if openapi_config else "/openapi.json",
        )

        # Middleware stack is addded in LIFO order (last added = outermost = runs first).
        # JwtAuthMiddleware added first → innermost → runs after RequestContextMiddleware.
        # RequestContextMiddleware added last → outermost → runs first, cleans up last.
        # User middleware (configure_middleware) sit in between: outside JwtAuth so
        # e.g. CORS preflight is handled before auth; declared-first runs first.
        # Middleware của user (configure_middleware) nằm giữa: ngoài JwtAuth để
        # CORS preflight chạy trước auth; khai báo trước chạy trước.
        self._add_jwt_middleware(fastapi_app, xime_app, self.adapter_id)
        for middleware, options in reversed(registry.get_middlewares(self.adapter_id)):
            # Phân giải marker Inject/FromConfig (DI service, runtime config) ngay
            # tại đây - DI container đã dựng xong nên option động lấy được giá trị
            # thật mà không cần app subclass WebAdapter.
            resolved = resolve_options(options, xime_app)
            # CORS options come from YAML more often than from code, and two
            # shapes there are silently permissive rather than broken - check
            # them once the real values are known.
            # Option CORS phần lớn đến từ YAML, và hai dạng sai ở đó là "mở
            # toang trong im lặng" chứ không phải hỏng - kiểm khi đã có giá trị thật.
            validate_cors_options(middleware, resolved)
            fastapi_app.add_middleware(middleware, **resolved)
        fastapi_app.add_middleware(RequestContextMiddleware)

        # Global exception handlers registered via configure_exception_handlers().
        # Exception handler toàn cục đăng ký qua configure_exception_handlers().
        for exc_type, handler in registry.get_exception_handlers(self.adapter_id).items():
            fastapi_app.add_exception_handler(exc_type, handler)

        # Route sức khoẻ gắn TRƯỚC OpenAPI, và `include_in_schema=False` nên
        # chúng không hiện trong tài liệu API: chúng phục vụ hạ tầng, không phải
        # người dùng API.
        add_health_routes(fastapi_app, xime_app, self.adapter_id)

        if openapi_config is not None:
            fastapi_app.openapi = build_custom_openapi(fastapi_app, openapi_config)

        if has_custom_swagger_title:
            self._add_custom_swagger_ui(fastapi_app, openapi_config)

        return fastapi_app

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _add_custom_swagger_ui(app: FastAPI, config) -> None:
        from fastapi.openapi.docs import get_swagger_ui_html

        docs_url = config.docs_url or "/docs"
        openapi_url = config.openapi_url or "/openapi.json"
        title = config.swagger_ui_title

        @app.get(docs_url, include_in_schema=False)
        async def _swagger_ui_html():
            return get_swagger_ui_html(openapi_url=openapi_url, title=title)

    @staticmethod
    def _add_jwt_middleware(
        app: FastAPI, xime_app: Application, server_id: str = "default"
    ) -> None:
        # Reading the registry runs on EVERY web start-up, including apps that
        # never touch JWT - so this import must not require the [jwt] extra.
        # Đọc registry chạy ở MỌI lần khởi động web, kể cả app không dùng JWT -
        # nên import này không được đòi extra [jwt].
        from xime.starters.jwt._config import jwt_registry

        jwt_config = jwt_registry.get()
        if jwt_config is None:
            return

        # Exactly one key source. Refusing "neither" is the whole point: without
        # this check an application whose keys were not available at start-up
        # boots with NO authentication middleware and reports itself healthy
        # while every endpoint is open - the failure looks like success.
        # Đúng MỘT nguồn khoá. Từ chối "không có cái nào" chính là mục đích của
        # phép kiểm này: thiếu nó thì app không lấy được khoá lúc khởi động sẽ lên
        # mà KHÔNG có middleware xác thực nào và tự báo là khoẻ, trong khi mọi
        # endpoint đều mở - hỏng mà trông y như chạy tốt.
        key_provider_cls = jwt_registry.get_key_provider()
        if jwt_config.key_context is None and key_provider_cls is None:
            raise StartupException(
                "configure_jwt() was called without a key source: set "
                "JwtMiddlewareConfig.key_context for a single static key, or pass "
                "key_provider= for keys addressed by `kid`."
            )
        if jwt_config.key_context is not None and key_provider_cls is not None:
            raise StartupException(
                "configure_jwt() got both key_context and key_provider. Pick one: "
                "two sources for the same fact are two sources that can disagree."
            )

        # configure_jwt() was called, so PyJWT is genuinely required. Probe it
        # here, at start-up: PyJWT is now imported lazily inside the verifier, so
        # without this the app would boot fine and only fail on the first request
        # that carries a token.
        # Đã gọi configure_jwt() nghĩa là thật sự cần PyJWT. Dò ngay lúc khởi
        # động: verifier giờ nạp PyJWT lười nên thiếu nó app vẫn lên, chỉ chết ở
        # request đầu tiên mang token.
        from xime.starters.jwt._middleware import JwtAuthMiddleware
        from xime.starters.jwt._pyjwt import pyjwt

        pyjwt()
        if jwt_config.audience is None:
            # On a platform where one authority signs tokens for many services,
            # skipping `aud` means a token minted for ANOTHER service verifies
            # here: same signature, same issuer, different intended recipient.
            # Trên nền tảng mà một nơi ký token cho nhiều service, bỏ `aud`
            # nghĩa là token cấp cho service KHÁC vẫn qua được ở đây.
            _log.warning(
                "configure_jwt() does not set `audience`: the `aud` claim is "
                "not enforced, so a token issued for a different service is "
                "accepted here. Set audience=<this service> unless tokens are "
                "signed by a key nobody else uses."
            )
        # Both collaborators are resolved here, not inside the middleware: the
        # container is already built at this point (the same reason Inject(...)
        # markers are resolved a few lines below). The middleware used to
        # construct PyJwtTokenVerifier itself, which meant the substitution seam
        # its own docstring advertised quietly applied to nothing.
        # Cả hai được phân giải ở đây chứ không trong middleware: container đã
        # dựng xong tại điểm này. Trước đây middleware tự dựng PyJwtTokenVerifier,
        # tức cái khe thay thế mà docstring của chính nó quảng cáo âm thầm không
        # áp cho cái gì cả.
        verifier_cls = jwt_registry.get_verifier()
        # Đường dẫn sức khoẻ luôn công khai, và đó là quyết định chứ không phải
        # sót: chúng phải trả lời được **khi mọi thứ khác đã hỏng**, kể cả khi
        # không lấy nổi khoá verify. Một `/healthz` đòi token là một `/healthz`
        # im lặng đúng lúc cần nhất. Bù lại thân phản hồi không mang gì nhạy cảm.
        health_paths = public_health_paths(server_id)
        if health_paths:
            missing = [p for p in health_paths if p not in jwt_config.public_paths]
            if missing:
                jwt_config = replace(
                    jwt_config,
                    public_paths=[*jwt_config.public_paths, *missing],
                )
        app.add_middleware(
            JwtAuthMiddleware,
            config=jwt_config,
            key_provider=xime_app.get(key_provider_cls) if key_provider_cls else None,
            verifier=xime_app.get(verifier_cls) if verifier_cls else None,
        )

    @staticmethod
    def _register_controllers(
        app: FastAPI,
        xime_app: Application,
        server_id: str = "default",
    ) -> None:
        """Discover controller classes and register their routes into the FastAPI app.

        Only controllers whose server_id class variable matches the given server_id
        are registered. Controllers without server_id default to "default".

        Runs after application.start() so that the DI container is fully built
        and controller instances are available via xime_app.get(cls).
        """
        from .routing._builder import RouteBuilder
        from .routing._config import controller_registry
        from .routing._scanner import ControllerScanner

        packages = controller_registry.get_packages()
        if not packages:
            return

        scanner = ControllerScanner()
        builder = RouteBuilder()

        for cls in scanner.find_controllers(*packages):
            if getattr(cls, "server_id", "default") != server_id:
                continue
            try:
                instance = xime_app.get(cls)
            except KeyError:
                raise RuntimeError(
                    f"Controller '{cls.__name__}' is not registered in the DI container. "
                    f"Add its package to dependency.scan() in config/dependency.py."
                ) from None
            router = builder.build(cls, instance)
            app.include_router(router)

        WebAdapter._register_websocket_handlers(
            app, xime_app, server_id, scanner, packages
        )

    @staticmethod
    def _register_websocket_handlers(
        app: FastAPI,
        xime_app: Application,
        server_id: str,
        scanner: Any,
        packages: list[str],
    ) -> None:
        """Register every @ws class, with JWT verification in front of each.

        Kept next to controller registration because a WebSocket route is a route:
        same packages, same DI container, same server_id filter.
        Đặt cạnh phần đăng ký controller vì route WebSocket cũng là một route:
        cùng gói, cùng DI container, cùng phép lọc server_id.
        """
        from xime.starters.jwt._config import jwt_registry

        from .ws._registrar import WebSocketRegistrar

        handlers = [
            cls
            for cls in scanner.find_websocket_handlers(*packages)
            if getattr(cls, "server_id", "default") == server_id
        ]
        if not handlers:
            return

        jwt_config = jwt_registry.get()
        authenticator = None
        if jwt_config is not None:
            from xime.starters.jwt._authenticator import JwtAuthenticator

            provider_cls = jwt_registry.get_key_provider()
            verifier_cls = jwt_registry.get_verifier()
            authenticator = JwtAuthenticator(
                jwt_config,
                key_provider=xime_app.get(provider_cls) if provider_cls else None,
                verifier=xime_app.get(verifier_cls) if verifier_cls else None,
            )
        else:
            # An app can legitimately have no JWT at all - but a WebSocket route
            # in that app is open, and the silence around that fact is the whole
            # reason F1 survived: the middleware's own docstring promises every
            # path outside public_paths needs a token, and a @ws route quietly
            # broke that promise with nothing logged.
            # App không dùng JWT là chuyện hợp lệ - nhưng route WebSocket của nó
            # thì mở, và chính sự im lặng quanh chuyện đó là lý do F1 sống lâu.
            _log.warning(
                "%d WebSocket route(s) registered but configure_jwt() was never "
                "called, so every one of them accepts unauthenticated "
                "connections: %s",
                len(handlers),
                ", ".join(sorted(getattr(c, "__name__", str(c)) for c in handlers)),
            )

        registrar = WebSocketRegistrar(authenticator, jwt_config)
        for cls in handlers:
            try:
                instance = xime_app.get(cls)
            except KeyError:
                raise RuntimeError(
                    f"WebSocket handler '{cls.__name__}' is not registered in the DI "
                    f"container. Add its package to dependency.scan() in "
                    f"config/dependency.py."
                ) from None
            path = registrar.register(app, cls, instance)
            _log.debug("WebSocket route registered: %s -> %s", path, cls.__name__)
