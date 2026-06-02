"""
Web adapter — HTTP + WebSocket qua FastAPI (ASGI).

Public API:
    from xime.adapters.web import WebAdapter, WebSocketHandler
    from xime.adapters.web.openapi import configure_openapi, OpenApiConfig, JwtBearer, ApiKey
"""

from ._adapter import WebAdapter
from .ws import WebSocketHandler

__all__ = ["WebAdapter", "WebSocketHandler"]
