from __future__ import annotations

import asyncio
import logging
import time
import uuid

from fastapi import WebSocket, WebSocketDisconnect

from xime.core.context import request_context
from xime.core.security import clear_security

from ._auth import WS_UNAUTHORIZED, split_subprotocols

_log = logging.getLogger("xime.web.ws")


class WebSocketHandler:
    """Base class cho WebSocket handler trong Xime.

    Override các method cần thiết - framework quản lý toàn bộ vòng đời kết nối.

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

    # Close the connection once the token that opened it expires. Default ON:
    # without it, revoking a token cannot end a WebSocket session, and a chat
    # socket opened this morning still speaks for an account disabled at noon -
    # the same shape of bug as "locking an account does not cut its sessions".
    # Đóng kết nối khi token mở nó hết hạn. Mặc định BẬT: thiếu nó thì thu hồi
    # token KHÔNG cắt được phiên WebSocket, và một socket mở từ sáng vẫn nói thay
    # cho tài khoản bị khoá lúc trưa - cùng khuôn lỗi "khoá tài khoản không cắt
    # phiên". Tắt bằng cách đặt False trên lớp con.
    close_on_token_expiry: bool = True

    async def on_connect(self, ws: WebSocket) -> None:
        """Khi client kết nối. Mặc định: accept, vọng lại subprotocol đã thoả thuận.

        Xác thực KHÔNG nằm ở đây - nó chạy trước, ở lớp đăng ký route, nên
        override method này không bỏ qua được nó.
        Authentication does NOT live here: it runs earlier, in the route
        registrar, so overriding this method cannot skip it.

        Override để kiểm query params hoặc từ chối kết nối vì lý do nghiệp vụ.
        Nếu raise exception tại đây, on_disconnect sẽ KHÔNG được gọi vì kết nối
        chưa được thiết lập thành công.
        """
        await ws.accept(subprotocol=self.negotiated_subprotocol(ws))

    @staticmethod
    def negotiated_subprotocol(ws: WebSocket) -> str | None:
        """Subprotocol phải vọng lại khi accept, bỏ qua entry chở token.

        A server that accepts must echo one of the offered subprotocols, and the
        `xime.bearer.<token>` entry is not a protocol - echoing it would send the
        token straight back to whoever asked.
        Server accept thì phải vọng lại một trong các subprotocol được đề nghị, mà
        entry `xime.bearer.<token>` không phải một giao thức - vọng lại nó là gửi
        token về đúng nơi vừa hỏi.
        """
        _token, echo = split_subprotocols(list(ws.scope.get("subprotocols") or []))
        return echo

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
        """Main loop - framework gọi hàm này để chạy vòng đời kết nối.

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
        watchdog = self._start_expiry_watchdog(ws)
        try:
            await self.on_connect(ws)
            connected = True
            while True:
                message = await ws.receive()
                # Starlette's low-level receive() does NOT raise on disconnect -
                # it returns a {"type": "websocket.disconnect", "code": ...} dict
                # and only the typed helpers (receive_text/bytes) raise
                # WebSocketDisconnect. Handle the disconnect message explicitly so
                # the real close code is reported instead of leaking a RuntimeError.
                # receive() của Starlette KHÔNG raise khi disconnect - nó trả dict
                # {"type": "websocket.disconnect", "code": ...}; chỉ receive_text/
                # bytes mới raise. Xử lý message disconnect tường minh để báo đúng
                # close code thay vì để lọt RuntimeError.
                if message["type"] == "websocket.disconnect":
                    await self.on_disconnect(ws, message.get("code", 1000))
                    return
                # Starlette luôn trả về cả hai key "text" và "bytes",
                # nhưng chỉ một trong hai khác None tại một thời điểm.
                if message.get("text") is not None:
                    await self.on_message(ws, message["text"])
                elif message.get("bytes") is not None:
                    await self.on_bytes(ws, message["bytes"])
        except WebSocketDisconnect as exc:
            # Defensive: a handler that calls receive_text/json itself surfaces
            # disconnect as this exception. Only meaningful after on_connect.
            # Phòng thủ: handler tự gọi receive_text/json sẽ ném exception này.
            if connected:
                await self.on_disconnect(ws, exc.code)
        except Exception:
            if connected:
                await self.on_disconnect(ws, 1011)
            raise
        finally:
            if watchdog is not None:
                watchdog.cancel()
            request_context.clear()
            clear_security()

    # ------------------------------------------------------------------
    # Token lifetime
    # ------------------------------------------------------------------

    def _start_expiry_watchdog(self, ws: WebSocket) -> asyncio.Task | None:
        """Schedule a close for the moment the token expires, or None.

        A separate task rather than a timeout around receive(): wrapping
        receive() in wait_for would cancel it mid-await, and a message already in
        flight can be lost that way. Closing from the side lets the normal loop
        observe an ordinary disconnect.
        Dùng task riêng thay vì đặt timeout quanh receive(): bọc receive() bằng
        wait_for sẽ huỷ nó giữa chừng và một message đang trên đường có thể mất.
        Đóng từ bên cạnh thì vòng lặp thường thấy một disconnect bình thường.
        """
        if not self.close_on_token_expiry:
            return None

        from xime.starters.jwt._middleware import JWT_CLAIMS

        claims = request_context.get(JWT_CLAIMS)
        if not isinstance(claims, dict):
            return None
        exp = claims.get("exp")
        if not isinstance(exp, (int, float)):
            # No `exp` means the token never expires - a real possibility that
            # JwtMiddlewareConfig.require exists to forbid. Nothing to watch.
            # Không có `exp` nghĩa là token không bao giờ hết hạn - chuyện có
            # thật mà `require` sinh ra để cấm. Không có gì để canh.
            return None

        return asyncio.ensure_future(self._close_when_expired(ws, float(exp)))

    async def _close_when_expired(self, ws: WebSocket, exp: float) -> None:
        await asyncio.sleep(max(0.0, exp - time.time()))
        _log.info(
            "WebSocket %s: token expired, closing the connection",
            request_context.get("connection_id"),
        )
        try:
            # Same close code as a refused handshake, on purpose: in both cases
            # the client does exactly one thing - get a fresh token and
            # reconnect. Splitting a value that changes nothing for the caller
            # only leaks more of our internals.
            # Cùng mã đóng với bắt tay bị từ chối, có chủ đích: cả hai ca thì
            # client làm đúng MỘT việc - lấy token mới rồi nối lại. Tách một giá
            # trị không đổi hành động của bên gọi chỉ lộ thêm nội bộ của mình.
            await ws.close(code=WS_UNAUTHORIZED)
        except Exception:
            # The peer may already be gone; that is not an error worth raising
            # from a background task nobody awaits.
            # Đầu kia có thể đã đi rồi; đó không phải lỗi đáng ném ra từ một task
            # nền không ai await.
            _log.debug("WebSocket close after token expiry failed", exc_info=True)
