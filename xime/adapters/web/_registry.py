from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .openapi._config import OpenApiConfig


class _WebRegistry:
    def __init__(self) -> None:
        self._openapi: dict[str, "OpenApiConfig"] = {}

    def set_openapi(self, config: "OpenApiConfig", server_id: str = "default") -> None:
        self._openapi[server_id] = config

    def get_openapi(self, server_id: str = "default") -> "OpenApiConfig | None":
        return self._openapi.get(server_id)


registry = _WebRegistry()
