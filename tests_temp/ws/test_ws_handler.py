"""
Test WebSocketHandler.handle():
  - on_disconnect được gọi khi client ngắt kết nối bình thường (WebSocketDisconnect)
  - on_disconnect được gọi khi message loop raise exception khác (code 1011)
  - on_disconnect KHÔNG được gọi khi on_connect raise (kết nối chưa được thiết lập)
  - exception từ message loop được re-raise sau khi on_disconnect chạy
  - context (request_context, security) luôn được dọn dẹp trong mọi trường hợp
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.websockets import WebSocketDisconnect

from xime.adapters.web.ws._handler import WebSocketHandler
from xime.core.context import request_context
from xime.core.security.context import identity


def _make_ws() -> MagicMock:
    """Tạo WebSocket mock với accept() sẵn sàng."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.url.path = "/ws/test"
    return ws


# ---------------------------------------------------------------------------
# Case 1: Client ngắt kết nối bình thường
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_on_disconnect_called_on_websocket_disconnect():
    log: list[str] = []

    class TestHandler(WebSocketHandler):
        async def on_disconnect(self, ws, code: int) -> None:
            log.append(f"disconnected:{code}")

    ws = _make_ws()
    ws.receive = AsyncMock(side_effect=WebSocketDisconnect(code=1000))

    await TestHandler().handle(ws)

    assert log == ["disconnected:1000"]


# ---------------------------------------------------------------------------
# Case 2: Server-side exception trong message loop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_on_disconnect_called_with_1011_on_server_error():
    """Khi message loop raise exception không phải WebSocketDisconnect,
    on_disconnect được gọi với code 1011 (Internal Error)."""
    log: list[str] = []

    class TestHandler(WebSocketHandler):
        async def on_disconnect(self, ws, code: int) -> None:
            log.append(f"disconnected:{code}")

    ws = _make_ws()
    ws.receive = AsyncMock(side_effect=RuntimeError("unexpected"))

    with pytest.raises(RuntimeError, match="unexpected"):
        await TestHandler().handle(ws)

    assert log == ["disconnected:1011"]


@pytest.mark.asyncio
async def test_server_error_is_reraised_after_on_disconnect():
    """Exception từ message loop phải được re-raise sau khi on_disconnect chạy xong."""

    class TestHandler(WebSocketHandler):
        pass

    ws = _make_ws()
    ws.receive = AsyncMock(side_effect=ValueError("boom"))

    with pytest.raises(ValueError, match="boom"):
        await TestHandler().handle(ws)


# ---------------------------------------------------------------------------
# Case 3: on_connect raise — on_disconnect KHÔNG được gọi
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_on_disconnect_not_called_when_on_connect_raises():
    """Nếu on_connect raise, kết nối chưa được thiết lập → on_disconnect không được gọi."""
    log: list[str] = []

    class TestHandler(WebSocketHandler):
        async def on_connect(self, ws) -> None:
            raise PermissionError("rejected")

        async def on_disconnect(self, ws, code: int) -> None:
            log.append("disconnected")

    ws = _make_ws()

    with pytest.raises(PermissionError):
        await TestHandler().handle(ws)

    assert log == []


# ---------------------------------------------------------------------------
# Context cleanup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_context_cleared_after_normal_disconnect():
    """request_context và security phải được dọn sạch sau khi kết nối kết thúc."""

    class TestHandler(WebSocketHandler):
        pass

    ws = _make_ws()
    ws.receive = AsyncMock(side_effect=WebSocketDisconnect(code=1000))

    identity.set("user_123")
    await TestHandler().handle(ws)

    assert request_context.get("connection_id") is None
    assert identity.get() is None


@pytest.mark.asyncio
async def test_context_cleared_after_server_error():
    """Context phải được dọn sạch kể cả khi server raise exception."""

    class TestHandler(WebSocketHandler):
        pass

    ws = _make_ws()
    ws.receive = AsyncMock(side_effect=RuntimeError("crash"))

    identity.set("user_456")

    with pytest.raises(RuntimeError):
        await TestHandler().handle(ws)

    assert request_context.get("connection_id") is None
    assert identity.get() is None


@pytest.mark.asyncio
async def test_context_cleared_when_on_connect_raises():
    """Context phải được dọn sạch kể cả khi on_connect raise."""

    class TestHandler(WebSocketHandler):
        async def on_connect(self, ws) -> None:
            request_context.set("connection_id", "temp")
            raise RuntimeError("auth failed")

    ws = _make_ws()

    with pytest.raises(RuntimeError):
        await TestHandler().handle(ws)

    assert request_context.get("connection_id") is None
