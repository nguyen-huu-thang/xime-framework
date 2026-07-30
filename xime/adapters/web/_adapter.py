from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from ssl import CERT_NONE, CERT_OPTIONAL, CERT_REQUIRED
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI

from xime.core.config.runtime import ServerTlsConfig
from xime.core.exception.framework import StartupException

from ._markers import resolve_options
from ._registry import registry
from .middleware import RequestContextMiddleware
from .openapi._builder import build_custom_openapi

if TYPE_CHECKING:
    import uvicorn

    from xime.core.bootstrap.application import Application

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
    # does not mean "use the default" — it overwrites it and breaks the
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


class WebAdapter:
    """HTTP adapter — wraps FastAPI + uvicorn into the Xime adapter lifecycle.

    Register via app.use() and start via app.run():

        app = Application()
        app.use(WebAdapter())
        app.run()

    Hỗ trợ nhiều server trên các port khác nhau:

        app.use(WebAdapter())                              # server_id="default"
        app.use(WebAdapter("admin", "0.0.0.0", 8081))     # server_id="admin"

    Quy tắc:
    - server_id="default" (mặc định): host/port đọc từ application.yml khi không truyền.
    - server_id khác "default": host và port bắt buộc phải truyền vào constructor.
    - Không được có hai WebAdapter cùng server_id — Application.use() sẽ báo lỗi.

    HTTPS bật bằng khối server.ssl trong application.yml (để trống = HTTP thuần
    như cũ):

        server:
          port: 8107
          ssl:
            certfile: "/etc/letsencrypt/live/gym.xime.vn/fullchain.pem"
            keyfile: "/etc/letsencrypt/live/gym.xime.vn/privkey.pem"

    Mọi WebAdapter kế thừa server.ssl, kể cả server phụ — để server phụ không âm
    thầm chạy HTTP khi server chính đã HTTPS. Muốn khác thì truyền tường minh:

        app.use(WebAdapter("admin", "0.0.0.0", 8081, ssl=ServerTlsConfig(...)))
        app.use(WebAdapter("internal", "127.0.0.1", 8082, ssl=ServerTlsConfig()))  # tắt TLS

    Cert phải là cert CA công cộng (certbot...) vì trình duyệt KHÔNG tin CA nội
    bộ của Trust; cert Trust dành cho mTLS giữa service với nhau.

    Controller thuộc server nào khai báo qua class variable server_id:

        class AdminController:
            prefix = "/admin"
            server_id = "admin"   # chỉ đăng ký vào WebAdapter("admin", ...)

        class PublicController:
            prefix = "/api/v1"
            # không khai báo → mặc định "default"

    Startup order (driven by Application._run_async):
        1. Application.start()       — DI container fully built
        2. WebAdapter.start(app)     — builds FastAPI, registers controllers,
                                       runs uvicorn (blocks until stopped)

    Shutdown order:
        3. WebAdapter.stop()         — sets uvicorn.should_exit = True
        4. Application.stop()        — PreDestroy hooks, DI dispose

    For HTTP-level integration tests, use build_app() to obtain the FastAPI
    instance without running uvicorn:

        fastapi_app = WebAdapter().build_app(xime_app)
        async with AsyncClient(app=fastapi_app, base_url="http://test") as client:
            ...
    """

    def __init__(
        self,
        server_id: str = "default",
        host: str | None = None,
        port: int | None = None,
        ssl: ServerTlsConfig | None = None,
    ) -> None:
        if server_id != "default" and (host is None or port is None):
            raise ValueError(
                f"WebAdapter(server_id='{server_id}'): "
                "host and port are required for non-default servers."
            )
        self._server_id = server_id
        self._host_override = host
        self._port_override = port
        self._ssl_override = ssl
        self._server: uvicorn.Server | None = None

    # ------------------------------------------------------------------
    # Adapter protocol
    # ------------------------------------------------------------------

    async def start(self, app: Application) -> None:
        """Build the FastAPI app, resolve host/port, and run uvicorn.

        Blocks until the server is stopped (via stop() or SIGINT).
        Called by Application._run_async() after DI is fully built.
        """
        try:
            import uvicorn
        except ImportError:
            raise RuntimeError(
                "WebAdapter requires uvicorn. "
                "Run: pip install 'uvicorn[standard]' or pip install 'xime[web]'"
            ) from None

        from xime.core.config.runtime import RuntimeConfig
        runtime: RuntimeConfig = app.get(RuntimeConfig)  # type: ignore[assignment]

        if self._server_id == "default":
            # Explicit None checks so a valid host="" or port=0 (ask the OS for a
            # free port) is honoured instead of falling back to the YAML value.
            # Kiểm tra None tường minh để host=""/port=0 hợp lệ không bị rơi về YAML.
            host = self._host_override if self._host_override is not None else runtime.server.host
            port = self._port_override if self._port_override is not None else runtime.server.port
        else:
            host = self._host_override  # type: ignore[assignment]  # validated in __init__
            port = self._port_override  # type: ignore[assignment]

        # TLS is inherited from server.ssl unless the adapter was given its own.
        # Inheriting (rather than defaulting to plain HTTP) is deliberate: a
        # secondary server quietly serving HTTP while the main one serves HTTPS
        # is a security hole nobody would notice. Pass ssl=ServerTlsConfig() to
        # opt a secondary server out explicitly.
        # TLS kế thừa từ server.ssl trừ khi adapter được truyền riêng. Kế thừa
        # (thay vì mặc định HTTP thuần) là có chủ đích: server phụ âm thầm chạy
        # HTTP trong khi server chính đã HTTPS là lỗ hổng không ai để ý. Muốn
        # server phụ không dùng TLS thì truyền ssl=ServerTlsConfig() tường minh.
        tls = self._ssl_override if self._ssl_override is not None else runtime.server.ssl

        fastapi_app = self.build_app(app)
        config = uvicorn.Config(
            fastapi_app,
            host=host,
            port=port,
            **_tls_kwargs(tls, self._server_id),
        )
        self._server = uvicorn.Server(config)
        await self._server.serve()

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
        openapi_config = registry.get_openapi(self._server_id)
        has_custom_swagger_title = (
            openapi_config is not None and openapi_config.swagger_ui_title is not None
        )

        @asynccontextmanager
        async def lifespan(fastapi_app: FastAPI) -> AsyncGenerator[None, None]:
            # DI container already built by Application.start() — only register routes.
            self._register_controllers(fastapi_app, xime_app, self._server_id)
            yield

        fastapi_app = FastAPI(
            lifespan=lifespan,
            # Disable default Swagger UI when custom title is set — we add our own route below.
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
        self._add_jwt_middleware(fastapi_app)
        for middleware, options in reversed(registry.get_middlewares(self._server_id)):
            # Phân giải marker Inject/FromConfig (DI service, runtime config) ngay
            # tại đây — DI container đã dựng xong nên option động lấy được giá trị
            # thật mà không cần app subclass WebAdapter.
            resolved = resolve_options(options, xime_app)
            fastapi_app.add_middleware(middleware, **resolved)
        fastapi_app.add_middleware(RequestContextMiddleware)

        # Global exception handlers registered via configure_exception_handlers().
        # Exception handler toàn cục đăng ký qua configure_exception_handlers().
        for exc_type, handler in registry.get_exception_handlers(self._server_id).items():
            fastapi_app.add_exception_handler(exc_type, handler)

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
    def _add_jwt_middleware(app: FastAPI) -> None:
        # Reading the registry runs on EVERY web start-up, including apps that
        # never touch JWT — so this import must not require the [jwt] extra.
        # Đọc registry chạy ở MỌI lần khởi động web, kể cả app không dùng JWT -
        # nên import này không được đòi extra [jwt].
        from xime.starters.jwt._config import jwt_registry

        jwt_config = jwt_registry.get()
        if jwt_config is None:
            return

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
        app.add_middleware(JwtAuthMiddleware, config=jwt_config)

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
