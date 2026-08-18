from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

# Attribute name used to mark a WebSocket handler class - internal to the framework.
# Tên thuộc tính đánh dấu một lớp handler WebSocket - nội bộ framework.
WS_ATTR = "_xime_ws_route_info"


@dataclass
class WebSocketRouteInfo:
    """Metadata attached to a WebSocketHandler subclass by @ws.

    Deliberately mirrors RouteInfo: the decorator only MARKS, and the adapter
    registers later, once the DI container exists.
    Cố ý giống RouteInfo: decorator chỉ ĐÁNH DẤU, adapter đăng ký sau, khi DI đã
    dựng xong.
    """

    path: str
    name: str | None = None


def ws(path: str, *, name: str | None = None) -> Callable[[type], type]:
    """Mark a WebSocketHandler subclass as the handler for a WebSocket path.

    The class is instantiated by the DI container like any controller, so its
    package must also appear in dependency.scan().
    Lớp này được DI container dựng như mọi controller, nên gói của nó cũng phải
    có trong dependency.scan().

        from xime.adapters.web import WebSocketHandler, ws

        @ws("/chat")
        class ChatHandler(WebSocketHandler):
            def __init__(self, rooms: RoomService) -> None:
                self.rooms = rooms

            async def on_message(self, socket, data: str) -> None:
                await self.rooms.broadcast(data)

    ⚠ Authentication is ON by default. When configure_jwt() has been called,
    every @ws path demands a valid token unless the path is listed in
    JwtMiddlewareConfig.public_paths - the same list HTTP uses, because "this
    path is open" should mean one thing in an application, not two.
    ⚠ Xác thực BẬT theo mặc định. Đã gọi configure_jwt() thì mọi đường @ws đòi
    token hợp lệ, trừ khi đường đó nằm trong `public_paths` - cùng danh sách với
    HTTP, vì "đường này mở" nên mang một nghĩa trong một ứng dụng, không phải hai.

    Args:
        path: URL path of the WebSocket endpoint, e.g. "/chat".
        name: Optional route name, used for url_for-style lookups.
    """

    def decorator(cls: type) -> type:
        # Checked here rather than at registration time: the failure is a typo in
        # the developer's own file, and reporting it at import time points at
        # that file instead of at a startup routine three layers away.
        # Kiểm ở đây chứ không lúc đăng ký: lỗi là ở chính file của lập trình
        # viên, báo lúc import thì trỏ đúng vào file đó thay vì vào một thủ tục
        # khởi động cách ba tầng.
        from ._handler import WebSocketHandler

        if not (isinstance(cls, type) and issubclass(cls, WebSocketHandler)):
            raise TypeError(
                f"@ws('{path}') expects a WebSocketHandler subclass, got "
                f"{getattr(cls, '__name__', cls)!r}. The connection lifecycle "
                "(accept, receive loop, disconnect, context cleanup) lives in "
                "WebSocketHandler; a plain class has none of it."
            )
        setattr(cls, WS_ATTR, WebSocketRouteInfo(path=path, name=name))
        return cls

    return decorator


def get_ws_info(cls: type) -> WebSocketRouteInfo | None:
    """Return the WebSocketRouteInfo attached to a class, or None.

    Reads the class's OWN attribute: a subclass that does not carry its own @ws
    is not a route, even though it inherits the marker through the MRO.
    Đọc thuộc tính của CHÍNH lớp đó: lớp con không tự mang @ws thì không phải một
    route, dù nó thừa hưởng dấu đánh qua MRO.
    """
    return cls.__dict__.get(WS_ATTR)
