from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from core.bootstrap.application import Application

from ._registry import registry
from .middleware import RequestContextMiddleware
from .openapi._builder import build_custom_openapi


class WebAdapter:
    """Tạo FastAPI ASGI app và tích hợp lifecycle của Xime Application.

    Dùng trong main.py của ứng dụng:

        from xime.adapters.web import WebAdapter
        from core.bootstrap.application import Application

        app = WebAdapter(Application()).build()
        # Chạy với: uvicorn main:app

    Thứ tự khởi động (uvicorn start):
        FastAPI lifespan → Application.start()
            → DI container build → PostConstruct hooks

    Thứ tự tắt (uvicorn shutdown):
        FastAPI lifespan exit → Application.stop()
            → PreDestroy hooks (reverse order)
    """

    def __init__(self, application: Application) -> None:
        self._application = application

    def build(self) -> FastAPI:
        """Tạo và trả về FastAPI ASGI app đã được cấu hình đầy đủ.

        Đọc OpenApiConfig từ registry nếu developer đã gọi configure_openapi().
        """
        openapi_config = registry.get_openapi()

        @asynccontextmanager
        async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
            await self._application.start()
            yield
            await self._application.stop()

        fastapi_app = FastAPI(
            lifespan=lifespan,
            docs_url=openapi_config.docs_url if openapi_config else "/docs",
            redoc_url=openapi_config.redoc_url if openapi_config else "/redoc",
            openapi_url=openapi_config.openapi_url if openapi_config else "/openapi.json",
        )

        fastapi_app.add_middleware(RequestContextMiddleware)

        if openapi_config is not None:
            fastapi_app.openapi = build_custom_openapi(fastapi_app, openapi_config)

        return fastapi_app
