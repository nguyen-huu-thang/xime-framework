from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncGenerator

from fastapi import FastAPI

from ._registry import registry
from .middleware import RequestContextMiddleware
from .openapi._builder import build_custom_openapi

if TYPE_CHECKING:
    import uvicorn
    from xime.core.bootstrap.application import Application


class WebAdapter:
    """HTTP adapter — wraps FastAPI + uvicorn into the Xime adapter lifecycle.

    Register via app.use() and start via app.run():

        app = Application()
        app.use(WebAdapter())
        app.run()

    Constructor accepts optional host/port overrides. When omitted, values
    are read from runtime config (server.host / server.port in application.yml).

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
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        self._host_override = host
        self._port_override = port
        self._server: uvicorn.Server | None = None

    # ------------------------------------------------------------------
    # Adapter protocol
    # ------------------------------------------------------------------

    async def start(self, app: "Application") -> None:
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

        host = self._host_override or runtime.server.host
        port = self._port_override or runtime.server.port

        fastapi_app = self.build_app(app)
        config = uvicorn.Config(fastapi_app, host=host, port=port)
        self._server = uvicorn.Server(config)
        await self._server.serve()

    async def stop(self) -> None:
        """Signal uvicorn to shut down gracefully. No-op if start() was not called."""
        if self._server is not None:
            self._server.should_exit = True

    # ------------------------------------------------------------------
    # FastAPI app builder (also used for testing)
    # ------------------------------------------------------------------

    def build_app(self, xime_app: "Application") -> FastAPI:
        """Build and return the configured FastAPI ASGI app.

        Unlike start(), this does NOT run uvicorn. Use it in integration
        tests to get a testable FastAPI instance:

            fastapi_app = WebAdapter().build_app(app)
            async with AsyncClient(app=fastapi_app, base_url="http://test") as client:
                ...

        The Application must be started (app.start() called) before
        build_app() is invoked so that the DI container is available.
        """
        openapi_config = registry.get_openapi()
        has_custom_swagger_title = (
            openapi_config is not None and openapi_config.swagger_ui_title is not None
        )

        @asynccontextmanager
        async def lifespan(fastapi_app: FastAPI) -> AsyncGenerator[None, None]:
            # DI container already built by Application.start() — only register routes.
            self._register_controllers(fastapi_app, xime_app)
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
        self._add_jwt_middleware(fastapi_app)
        fastapi_app.add_middleware(RequestContextMiddleware)

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
        from xime.starters.jwt._config import jwt_registry
        jwt_config = jwt_registry.get()
        if jwt_config is None:
            return
        try:
            from xime.starters.jwt._middleware import JwtAuthMiddleware
        except ImportError:
            raise RuntimeError(
                "JWT middleware is configured via configure_jwt() but PyJWT is not installed. "
                "Run: pip install pyjwt"
            )
        app.add_middleware(JwtAuthMiddleware, config=jwt_config)

    @staticmethod
    def _register_controllers(app: FastAPI, xime_app: "Application") -> None:
        """Discover controller classes and register their routes into the FastAPI app.

        Runs after application.start() so that the DI container is fully built
        and controller instances are available via xime_app.get(cls).
        """
        from .routing._config import controller_registry
        from .routing._scanner import ControllerScanner
        from .routing._builder import RouteBuilder

        packages = controller_registry.get_packages()
        if not packages:
            return

        scanner = ControllerScanner()
        builder = RouteBuilder()

        for cls in scanner.find_controllers(*packages):
            try:
                instance = xime_app.get(cls)
            except KeyError:
                raise RuntimeError(
                    f"Controller '{cls.__name__}' is not registered in the DI container. "
                    f"Add its package to dependency.scan() in config/dependency.py."
                ) from None
            router = builder.build(cls, instance)
            app.include_router(router)
