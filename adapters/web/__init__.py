"""
Web adapter — HTTP + WebSocket qua FastAPI (ASGI).

Public API:
    from adapters.web import WebAdapter, WebSocketHandler
    from adapters.web import get, post, put, patch, delete, configure_controllers
    from adapters.web.openapi import configure_openapi, OpenApiConfig, JwtBearer, ApiKey
"""

from ._adapter import WebAdapter
from .routing import configure_controllers, delete, get, patch, post, put
from .ws import WebSocketHandler

__all__ = [
    "WebAdapter",
    "WebSocketHandler",
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "configure_controllers",
]
