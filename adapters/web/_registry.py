from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .openapi._config import OpenApiConfig


class _WebRegistry:
    def __init__(self) -> None:
        self._openapi: OpenApiConfig | None = None

    def set_openapi(self, config: OpenApiConfig) -> None:
        self._openapi = config

    def get_openapi(self) -> OpenApiConfig | None:
        return self._openapi


registry = _WebRegistry()
