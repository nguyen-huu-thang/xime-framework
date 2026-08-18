from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, WebSocket

from xime.core.context import request_context
from xime.core.exception.framework import AuthenticationException
from xime.core.security.enums import CredentialType
from xime.core.security.session import authenticate

from ._auth import WS_UNAUTHORIZED, split_subprotocols
from ._decorators import get_ws_info

_log = logging.getLogger("xime.web.ws")


class WebSocketRegistrar:
    """Registers @ws classes as FastAPI websocket routes, with auth in front.

    ⭐ Authentication runs HERE, before the handler is entered - not inside
    WebSocketHandler.on_connect as originally proposed. Putting it in on_connect
    would make it a default a subclass silently removes by overriding the method,
    and "the protection disappears when you write the code you were told to
    write" is not a protection.
    ⭐ Xác thực chạy Ở ĐÂY, trước khi vào handler - không nằm trong
    `on_connect` như đề xuất ban đầu. Đặt trong on_connect thì nó là một mặc định
    mà lớp con xoá đi chỉ bằng cách override, và "chốt chặn biến mất đúng lúc bạn
    viết code mà người ta bảo bạn viết" thì không phải chốt chặn.
    """

    def __init__(self, authenticator: Any, config: Any) -> None:
        # Both None when configure_jwt() was never called: an app with no JWT at
        # all keeps its WebSocket routes open, exactly as its HTTP routes are.
        # Cả hai là None khi chưa gọi configure_jwt(): app không dùng JWT thì
        # route WebSocket vẫn mở, y như route HTTP của nó.
        self._auth = authenticator
        self._config = config
        self._public = (
            frozenset(self._normalize(p) for p in config.public_paths)
            if config is not None
            else frozenset()
        )

    # ------------------------------------------------------------------

    def register(self, app: FastAPI, cls: type, instance: Any) -> str:
        """Add one @ws class to the FastAPI app. Returns the registered path."""
        info = get_ws_info(cls)
        if info is None:  # pragma: no cover - the scanner only yields marked classes
            raise RuntimeError(f"{cls.__name__} is not marked with @ws")

        requires_auth = self._auth is not None and not self._is_public(info.path)

        async def endpoint(websocket: WebSocket) -> None:
            if requires_auth and not await self._authenticate(websocket, info.path):
                return
            await instance.handle(websocket)

        app.add_api_websocket_route(info.path, endpoint, name=info.name or cls.__name__)
        return info.path

    # ------------------------------------------------------------------

    async def _authenticate(self, websocket: WebSocket, path: str) -> bool:
        """Verify the handshake. Returns False after closing a refused socket.

        Every refusal uses the same close code and says nothing about which step
        failed. A handshake has no response body to carry a reason, and the
        client's action is identical in all three cases - get a valid token and
        try again - so splitting them would only tell an attacker which half of
        the guess was right.
        Mọi lần từ chối dùng chung một mã đóng và không nói bước nào hỏng. Bắt tay
        không có body để chở lý do, và hành động của client giống hệt nhau ở cả
        ba ca - lấy token hợp lệ rồi thử lại - nên tách ra chỉ mách cho kẻ tấn
        công biết nửa nào của phỏng đoán là đúng.
        """
        offered = list(websocket.scope.get("subprotocols") or [])
        token, _echo = split_subprotocols(offered)

        if token is None:
            return await self._refuse(websocket, path, "no bearer subprotocol offered")

        try:
            claims = self._auth.verify(token)
        except AuthenticationException as exc:
            return await self._refuse(websocket, path, exc.message)

        identity = claims.get(self._config.identity_claim)
        if identity is None:
            return await self._refuse(
                websocket, path,
                f"token missing claim '{self._config.identity_claim}'",
            )

        # Set before handle() so the handler's own finally-block clears it, and
        # so the expiry watchdog can read `exp` without a second decode.
        # Đặt trước handle() để khối finally của chính handler dọn nó, và để đồng
        # hồ canh hết hạn đọc được `exp` mà không phải decode lần hai.
        from xime.starters.jwt._middleware import JWT_CLAIMS

        request_context.set(JWT_CLAIMS, claims)
        authenticate(identity=identity, credential_type=CredentialType.TOKEN)
        return True

    @staticmethod
    async def _refuse(websocket: WebSocket, path: str, reason: str) -> bool:
        # The reason goes to the log, not to the peer: the operator needs to tell
        # a key-distribution problem from an expired token, and the caller does not.
        # Lý do đi vào log chứ không đi tới đầu kia: người vận hành cần phân biệt
        # lỗi phân phối khoá với token hết hạn, còn bên gọi thì không.
        _log.info("WebSocket %s refused: %s", path, reason)
        await websocket.close(code=WS_UNAUTHORIZED)
        return False

    def _is_public(self, path: str) -> bool:
        return self._normalize(path) in self._public

    @staticmethod
    def _normalize(path: str) -> str:
        return path.rstrip("/") or "/"
