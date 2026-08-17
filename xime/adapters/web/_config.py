from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ._registry import registry


def configure_middleware(
    middleware: type,
    server_id: str = "default",
    **options: Any,
) -> None:
    """Register a custom ASGI/Starlette middleware for the web adapter.

    Call once per middleware in your config layer (e.g. config/web.py),
    following the configure_* discovery pattern. Options are forwarded to
    FastAPI's add_middleware().
    Gọi một lần cho mỗi middleware trong config layer (vd config/web.py),
    theo pattern configure_*. Options được chuyển nguyên vẹn cho add_middleware().

    Ordering: user middleware sit between RequestContextMiddleware (outermost)
    and JwtAuthMiddleware (innermost). Among user middleware, the one declared
    first runs first.
    Thứ tự: middleware của user nằm giữa RequestContextMiddleware (ngoài cùng)
    và JwtAuthMiddleware (trong cùng). Trong nhóm user, khai báo trước chạy trước.

    Example:
        from xime.adapters.web import configure_middleware
        from fastapi.middleware.cors import CORSMiddleware

        configure_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])
    """
    registry.add_middleware(middleware, options, server_id)


def configure_exception_handlers(
    handlers: dict[type[Exception], Callable],
    server_id: str = "default",
) -> None:
    """Register global FastAPI exception handlers.

    Maps exception types to handler callables with FastAPI's signature
    (request, exc) -> Response. Applied to the FastAPI app in build_app(),
    so they work both under uvicorn and in HTTP integration tests.
    Map exception type sang handler theo chữ ký FastAPI (request, exc) -> Response.
    Được áp vào app trong build_app() nên chạy cả với uvicorn lẫn test tích hợp.

    Example:
        from xime.adapters.web import configure_exception_handlers

        configure_exception_handlers({
            AppException: app_exception_handler,
            NotFoundError: not_found_handler,
        })
    """
    registry.add_exception_handlers(handlers, server_id)
