"""
Web adapter — HTTP + WebSocket qua FastAPI (ASGI).

Public API:
    from xime.adapters.web import WebAdapter, WebSocketHandler
    from xime.adapters.web import get, post, put, patch, delete, configure_controllers
    from xime.adapters.web import configure_middleware, configure_exception_handlers
    from xime.adapters.web import configure_cors, Inject, FromConfig
    from xime.adapters.web import ServerTlsConfig          # HTTPS cho server phụ
    from xime.adapters.web.openapi import configure_openapi, OpenApiConfig, JwtBearer, ApiKey
"""

from xime.core.config.runtime import ServerTlsConfig

from ._adapter import WebAdapter
from ._config import configure_exception_handlers, configure_middleware
from ._cors import configure_cors
from ._markers import FromConfig, Inject
from .routing import configure_controllers, delete, get, patch, post, put
from .ws import WebSocketHandler

__all__ = [
    "WebAdapter",
    "ServerTlsConfig",
    "WebSocketHandler",
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "configure_controllers",
    "configure_middleware",
    "configure_exception_handlers",
    "configure_cors",
    "Inject",
    "FromConfig",
]
