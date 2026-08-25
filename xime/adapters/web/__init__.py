"""
Web adapter - HTTP + WebSocket qua FastAPI (ASGI).

Public API:
    from xime.adapters.web import WebAdapter, WebSocketHandler
    from xime.adapters.web import get, post, put, patch, delete, configure_controllers
    from xime.adapters.web import configure_middleware, configure_exception_handlers
    from xime.adapters.web import configure_cors, configure_health, Inject, FromConfig
    from xime.adapters.web import public_health_paths   # cho middleware TỰ VIẾT
    from xime.adapters.web import ServerTlsConfig          # HTTPS cho server phụ
    from xime.adapters.web.openapi import configure_openapi, OpenApiConfig, JwtBearer, ApiKey
"""

from ._adapter import WebAdapter
from ._config import configure_exception_handlers, configure_middleware
from ._cors import configure_cors
from ._health import configure_health, public_health_paths
from ._markers import FromConfig, Inject
from ._server_config import ServerTlsConfig, WebServerConfig
from .routing import configure_controllers, delete, get, patch, post, put
from .ws import BEARER_SUBPROTOCOL_PREFIX, WS_UNAUTHORIZED, WebSocketHandler, ws

__all__ = [
    "WebAdapter",
    "ServerTlsConfig",
    "WebServerConfig",
    "BEARER_SUBPROTOCOL_PREFIX",
    "WS_UNAUTHORIZED",
    "WebSocketHandler",
    "ws",
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "configure_controllers",
    "configure_middleware",
    "configure_exception_handlers",
    "configure_cors",
    "configure_health",
    "public_health_paths",
    "Inject",
    "FromConfig",
]
