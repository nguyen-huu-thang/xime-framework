from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .openapi._config import OpenApiConfig


class _WebRegistry:
    def __init__(self) -> None:
        self._openapi: dict[str, "OpenApiConfig"] = {}
        # (middleware_class, options) in declaration order, per server_id.
        # (class middleware, options) theo thứ tự khai báo, theo từng server_id.
        self._middlewares: dict[str, list[tuple[type, dict[str, Any]]]] = {}
        self._exception_handlers: dict[str, dict[type[Exception], Callable]] = {}

    def set_openapi(self, config: "OpenApiConfig", server_id: str = "default") -> None:
        self._openapi[server_id] = config

    def get_openapi(self, server_id: str = "default") -> "OpenApiConfig | None":
        return self._openapi.get(server_id)

    def add_middleware(
        self,
        middleware: type,
        options: dict[str, Any],
        server_id: str = "default",
    ) -> None:
        self._middlewares.setdefault(server_id, []).append((middleware, options))

    def get_middlewares(self, server_id: str = "default") -> list[tuple[type, dict[str, Any]]]:
        return list(self._middlewares.get(server_id, []))

    def add_exception_handlers(
        self,
        handlers: dict[type[Exception], Callable],
        server_id: str = "default",
    ) -> None:
        self._exception_handlers.setdefault(server_id, {}).update(handlers)

    def get_exception_handlers(
        self, server_id: str = "default"
    ) -> dict[type[Exception], Callable]:
        return dict(self._exception_handlers.get(server_id, {}))

    def reset(self) -> None:
        """Clear all registrations - test cleanup only.

        Xóa toàn bộ đăng ký - chỉ dùng dọn dẹp trong test.
        """
        self._openapi.clear()
        self._middlewares.clear()
        self._exception_handlers.clear()


registry = _WebRegistry()
