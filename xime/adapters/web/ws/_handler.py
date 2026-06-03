from __future__ import annotations

import uuid

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from xime.core.context import request_context
from xime.core.security import clear_security


class WebSocketHandler:
    """Base class cho WebSocket handler trong Xime.

    Override các method cần thiết — framework quản lý toàn bộ vòng đời kết nối.

    BaseHTTPMiddleware không chạy cho WebSocket connection, nên handle()
    tự setup và teardown request_context / security context.

    Ví dụ:

        class ChatHandler(WebSocketHandler):
            def __init__(self, room_service: RoomService) -> None:
                self.room_service = room_service

            async def on_connect(self, ws: WebSocket) -> None:
                await ws.accept()
                await self.room_service.join(ws.query_params["room"])

            async def on_message(self, ws: WebSocket, data: str) -> None:
                await self.room_service.broadcast(data)

            async def on_disconnect(self, ws: WebSocket, code: int) -> None:
                await self.room_service.leave()

    Đăng ký trong config/routing.py (routing API sẽ được thiết kế sau):

        router.websocket("/chat", ChatHandler)
    """

    async def on_connect(self, ws: WebSocket) -> None:
        """Khi client kết nối. Mặc định: accept ngay.

        Override để kiểm tra auth, query params, hoặc từ chối kết nối.
        Nếu raise exception tại đây, on_disconnect sẽ KHÔNG được gọi vì
        kết nối chưa được thiết lập thành công.
        """
        await ws.accept()

    async def on_message(self, ws: WebSocket, data: str) -> None:
        """Khi nhận text message từ client."""

    async def on_bytes(self, ws: WebSocket, data: bytes) -> None:
        """Khi nhận binary message từ client."""

    async def on_disconnect(self, ws: WebSocket, code: int) -> None:
        """Khi kết nối kết thúc sau khi on_connect thành công.

        Được gọi trong mọi trường hợp kết nối kết thúc:
          - Client chủ động ngắt  → code từ WebSocketDisconnect
          - Lỗi phía server       → code 1011 (Internal Error, RFC 6455)
        """

    async def handle(self, ws: WebSocket) -> None:
        """Main loop — framework gọi hàm này để chạy vòng đời kết nối.

        Override chỉ khi cần toàn quyền kiểm soát message loop.
        Trong trường hợp thông thường, override on_connect / on_message /
        on_bytes / on_disconnect.

        Thứ tự đảm bảo:
          - on_connect raise → on_disconnect KHÔNG gọi, exception propagate
          - Kết nối thành công, sau đó kết thúc vì bất kỳ lý do gì
            → on_disconnect luôn được gọi trước khi cleanup context
        """
        request_context.set("connection_id", str(uuid.uuid4()))
        connected = False
        try:
            await self.on_connect(ws)
            connected = True
            while True:
                message = await ws.receive()
                # Starlette luôn trả về cả hai key "text" và "bytes",
                # nhưng chỉ một trong hai khác None tại một thời điểm.
                if message.get("text") is not None:
                    await self.on_message(ws, message["text"])
                elif message.get("bytes") is not None:
                    await self.on_bytes(ws, message["bytes"])
        except WebSocketDisconnect as exc:
            await self.on_disconnect(ws, exc.code)
        except Exception:
            if connected:
                await self.on_disconnect(ws, 1011)
            raise
        finally:
            request_context.clear()
            clear_security()
