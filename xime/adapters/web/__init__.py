"""
xime.adapters.web — HTTP + WebSocket adapter.

Usage:
    from xime.adapters.web import WebAdapter
    from xime.adapters.web import WebSocketHandler
    from xime.adapters.web import get, post, put, patch, delete
    from xime.adapters.web import configure_controllers
"""

from adapters.web import (
    WebAdapter,
    WebSocketHandler,
    configure_controllers,
    delete,
    get,
    patch,
    post,
    put,
)

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
