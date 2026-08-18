"""
F1 - WebSocket đi qua xác thực JWT (0.7.2).

Trước bản này: `JwtAuthMiddleware` bỏ qua mọi scope không phải "http", và
`on_connect` mặc định là `await ws.accept()` - nên một route WebSocket nhận mọi
kết nối trong khi docstring của middleware hứa mọi đường ngoài `public_paths`
đều cần token.

Điểm quan trọng nhất của thiết kế, và là thứ nhóm test đầu canh: **xác thực chạy
ở lớp ĐĂNG KÝ ROUTE, trước khi vào handler** - không nằm trong `on_connect` như
đề xuất ban đầu. Đặt trong `on_connect` thì nó là một mặc định mà lớp con xoá đi
chỉ bằng cách override, tức là chốt chặn biến mất đúng lúc người ta viết code mà
tài liệu bảo họ viết.
"""
import time

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from xime.adapters.web import BEARER_SUBPROTOCOL_PREFIX, WebSocketHandler, ws
from xime.adapters.web.ws._auth import WS_UNAUTHORIZED, split_subprotocols
from xime.adapters.web.ws._registrar import WebSocketRegistrar
from xime.core.context import request_context
from xime.core.security import identity
from xime.starters.jwt import JwtMiddlewareConfig, KeyContext
from xime.starters.jwt._authenticator import JwtAuthenticator

SECRET = "s3cret-for-tests-only"


class _FakeSocket:
    """Chỉ cần đủ cho _start_expiry_watchdog - nó không chạm socket thật."""

    scope: dict = {}

    async def close(self, code: int = 1000) -> None:
        return None



def _token(sub: str = "user-42", *, ttl: float = 60, **extra) -> str:
    import jwt as pyjwt

    payload = {"sub": sub, "exp": time.time() + ttl, **extra}
    return pyjwt.encode(payload, SECRET, algorithm="HS256")


def _bearer(token: str) -> list[str]:
    return [BEARER_SUBPROTOCOL_PREFIX + token, "xime"]


def _config(**kwargs) -> JwtMiddlewareConfig:
    return JwtMiddlewareConfig(
        key_context=KeyContext(algorithm="HS256", secret=SECRET), **kwargs
    )


def _client(handler_cls, config: JwtMiddlewareConfig | None = _config()) -> TestClient:
    """Build a FastAPI app with one @ws route registered the way the adapter does."""
    app = FastAPI()
    authenticator = JwtAuthenticator(config) if config is not None else None
    registrar = WebSocketRegistrar(authenticator, config)
    registrar.register(app, handler_cls, handler_cls())
    return TestClient(app)


# ---------------------------------------------------------------------------
# Handlers dùng trong test
# ---------------------------------------------------------------------------

@ws("/ws/secret")
class SecretHandler(WebSocketHandler):
    async def on_connect(self, socket) -> None:
        await super().on_connect(socket)
        await socket.send_text(f"BI-MAT cho {identity.get()}")


@ws("/ws/open")
class OpenHandler(WebSocketHandler):
    async def on_connect(self, socket) -> None:
        await super().on_connect(socket)
        await socket.send_text("ai cung xem duoc")


@ws("/ws/careless")
class CarelessHandler(WebSocketHandler):
    """Overrides on_connect completely and never calls super().

    This is the handler the original proposal would have failed on: if the
    default `on_connect` were the thing doing the rejecting, this class would
    quietly accept everyone.
    Đây là handler mà đề xuất ban đầu sẽ thua: nếu `on_connect` mặc định là chỗ
    từ chối, lớp này sẽ âm thầm nhận tất.
    """

    async def on_connect(self, socket) -> None:
        await socket.accept()
        await socket.send_text("toi tu accept")


# ---------------------------------------------------------------------------


class TestSubprotocolSplit:
    def test_token_and_echo_are_separated(self):
        token, echo = split_subprotocols(["xime.bearer.abc", "xime"])
        assert token == "abc"
        assert echo == "xime"

    def test_no_bearer_entry(self):
        assert split_subprotocols(["xime"]) == (None, "xime")

    def test_nothing_offered(self):
        assert split_subprotocols([]) == (None, None)

    def test_empty_token_is_not_a_token(self):
        """`xime.bearer.` with nothing after it must not read as an empty token."""
        assert split_subprotocols(["xime.bearer."]) == (None, None)

    def test_only_the_first_bearer_entry_is_read(self):
        """Two of them is a malformed request, not a choice for the server to make.

        Hai cái là request hỏng, không phải phép chọn của server.
        """
        token, _ = split_subprotocols(["xime.bearer.first", "xime.bearer.second"])
        assert token == "first"


class TestHandshakeAuthentication:
    """PoC 1 của kiểm toán, chạy ngược lại: đường này phải đóng.

    Tests come in PAIRS - refused without a token, accepted with one. Only the
    first half would also pass an implementation that refuses everything.
    """

    def test_no_token_is_refused(self):
        from starlette.websockets import WebSocketDisconnect

        client = _client(SecretHandler)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/secret") as socket:
                socket.receive_text()

    def test_a_valid_token_gets_in(self):
        client = _client(SecretHandler)
        with client.websocket_connect(
            "/ws/secret", subprotocols=_bearer(_token())
        ) as socket:
            assert socket.receive_text() == "BI-MAT cho user-42"

    def test_expired_token_is_refused(self):
        from starlette.websockets import WebSocketDisconnect

        client = _client(SecretHandler)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/ws/secret", subprotocols=_bearer(_token(ttl=-10))
            ) as socket:
                socket.receive_text()

    def test_token_signed_by_another_key_is_refused(self):
        import jwt as pyjwt
        from starlette.websockets import WebSocketDisconnect

        forged = pyjwt.encode(
            {"sub": "attacker", "exp": time.time() + 60}, "wrong-key", algorithm="HS256"
        )
        client = _client(SecretHandler)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/ws/secret", subprotocols=_bearer(forged)
            ) as socket:
                socket.receive_text()

    def test_token_without_the_identity_claim_is_refused(self):
        import jwt as pyjwt
        from starlette.websockets import WebSocketDisconnect

        no_sub = pyjwt.encode(
            {"exp": time.time() + 60}, SECRET, algorithm="HS256"
        )
        client = _client(SecretHandler)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/ws/secret", subprotocols=_bearer(no_sub)
            ) as socket:
                socket.receive_text()


class TestAuthCannotBeOverriddenAway:
    """⭐ The reason authentication sits in the registrar and not in on_connect.

    ⭐ Lý do xác thực nằm ở lớp đăng ký chứ không nằm trong on_connect.
    """

    def test_a_handler_that_accepts_by_itself_still_cannot_be_reached(self):
        from starlette.websockets import WebSocketDisconnect

        client = _client(CarelessHandler)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/careless") as socket:
                socket.receive_text()

    def test_the_same_handler_works_with_a_token(self):
        """Paired: the guard must block the missing token, not the handler."""
        client = _client(CarelessHandler)
        with client.websocket_connect(
            "/ws/careless", subprotocols=_bearer(_token())
        ) as socket:
            assert socket.receive_text() == "toi tu accept"


class TestPublicPaths:
    """One list of open paths for the whole app, not one per transport.

    Một danh sách đường mở cho cả ứng dụng, không phải mỗi transport một cái.
    """

    def test_a_path_in_public_paths_needs_no_token(self):
        client = _client(OpenHandler, _config(public_paths=["/ws/open"]))
        with client.websocket_connect("/ws/open") as socket:
            assert socket.receive_text() == "ai cung xem duoc"

    def test_a_path_not_listed_still_needs_one(self):
        """Paired - public_paths must open only what it names."""
        from starlette.websockets import WebSocketDisconnect

        client = _client(SecretHandler, _config(public_paths=["/ws/open"]))
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/secret") as socket:
                socket.receive_text()


class TestNoJwtConfigured:
    def test_an_app_without_configure_jwt_keeps_its_socket_open(self):
        """Consistent with HTTP: no configure_jwt() means no authentication.

        The adapter logs a WARNING naming every such route - see
        test_ws_registration.py. Behaviour unchanged; the silence is what ended.
        Nhất quán với HTTP. Adapter ghi một WARNING nêu tên từng route như vậy;
        hành vi không đổi, thứ chấm dứt là sự im lặng.
        """
        client = _client(OpenHandler, None)
        with client.websocket_connect("/ws/open") as socket:
            assert socket.receive_text() == "ai cung xem duoc"


class TestNegotiatedSubprotocol:
    def test_the_server_echoes_the_non_token_subprotocol(self):
        """Echoing the bearer entry would send the token back to whoever asked.

        Vọng lại entry bearer là gửi token về đúng nơi vừa hỏi.
        """
        client = _client(SecretHandler)
        with client.websocket_connect(
            "/ws/secret", subprotocols=_bearer(_token())
        ) as socket:
            assert socket.accepted_subprotocol == "xime"
            socket.receive_text()

    def test_nothing_to_echo_when_only_the_token_was_offered(self):
        client = _client(SecretHandler)
        with client.websocket_connect(
            "/ws/secret", subprotocols=[BEARER_SUBPROTOCOL_PREFIX + _token()]
        ) as socket:
            assert socket.accepted_subprotocol is None
            socket.receive_text()


class TestTokenExpiryDuringTheConnection:
    """A WebSocket outlives a request, so a token verified once is not enough.

    Không kiểm chỗ này thì thu hồi token KHÔNG cắt được phiên WebSocket - đúng
    khuôn lỗi "khoá tài khoản không cắt phiên".

    ⚠ Hai chi tiết của chính bộ test này, học được khi nó fail lần đầu:

    1. TTL phải TRÊN một giây. PyJWT ép `exp` về số nguyên, nên `exp = now + 0.1`
       bị cắt xuống dưới `now` và token chết ngay lúc bắt tay.
    2. Test phải khẳng định bắt tay ĐÃ THÀNH CÔNG trước, rồi mới đợi bị ngắt.
       Bản đầu chỉ đòi "bị ngắt" nên nó **xanh cả khi bắt tay bị từ chối** - đo
       đúng triệu chứng của một nguyên nhân khác hẳn.
    """

    def test_the_connection_is_closed_when_the_token_expires(self):
        from starlette.websockets import WebSocketDisconnect

        @ws("/ws/short")
        class ShortLived(WebSocketHandler):
            async def on_connect(self, socket) -> None:
                await super().on_connect(socket)
                await socket.send_text("xin chao")

        client = _client(ShortLived)
        with pytest.raises(WebSocketDisconnect) as caught:
            with client.websocket_connect(
                "/ws/short", subprotocols=_bearer(_token(ttl=1.5))
            ) as socket:
                # Chứng minh bắt tay ĐÃ qua - nếu không có dòng này thì test còn
                # xanh cả khi kết nối bị từ chối ngay từ đầu.
                assert socket.receive_text() == "xin chao"
                socket.receive_text()  # chờ tới lúc token hết hạn

        assert caught.value.code == WS_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_a_handler_can_opt_out(self):
        """Paired - the watchdog must be a default, not a law.

        Kiểm thẳng vào chỗ quyết định thay vì đợi đồng hồ thật: chờ thật thì phải
        chọn một khoảng thời gian, mà mọi khoảng thời gian trong test đều là một
        lời hứa về tốc độ máy chạy test.
        """
        from xime.starters.jwt._middleware import JWT_CLAIMS

        class Watching(WebSocketHandler):
            pass

        class NotWatching(WebSocketHandler):
            close_on_token_expiry = False

        request_context.set(JWT_CLAIMS, {"sub": "u", "exp": time.time() + 60})
        try:
            watching = Watching()._start_expiry_watchdog(_FakeSocket())
            assert watching is not None
            watching.cancel()

            assert NotWatching()._start_expiry_watchdog(_FakeSocket()) is None
        finally:
            request_context.clear()

    @pytest.mark.asyncio
    async def test_a_token_without_exp_has_nothing_to_watch(self):
        """No `exp` means the token never expires - a real case, not a mistake.

        `JwtMiddlewareConfig.require` exists to forbid it; the watchdog just has
        no deadline to work from.
        """
        from xime.starters.jwt._middleware import JWT_CLAIMS

        request_context.set(JWT_CLAIMS, {"sub": "u"})
        try:
            assert WebSocketHandler()._start_expiry_watchdog(_FakeSocket()) is None
        finally:
            request_context.clear()


class TestWsDecorator:
    def test_it_refuses_a_class_that_is_not_a_websocket_handler(self):
        with pytest.raises(TypeError, match="WebSocketHandler subclass"):

            @ws("/nope")
            class NotAHandler:
                pass

    def test_a_subclass_without_its_own_marker_is_not_a_route(self):
        """@ws marks a class, not a family - inheriting the mark is not declaring one.

        @ws đánh dấu một lớp, không đánh dấu cả họ - thừa hưởng dấu không phải là
        tự khai báo.
        """
        from xime.adapters.web.ws._decorators import get_ws_info

        class Inherited(SecretHandler):
            pass

        assert get_ws_info(SecretHandler) is not None
        assert get_ws_info(Inherited) is None
