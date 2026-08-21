"""Hai đoạn NỐI mà test đơn vị đi vòng qua.

⚠ Cả hai lỗ hổng dưới đây lộ ra bằng **đối chứng**, không bằng đọc code: bộ test
kiểm `public_health_paths()` trả đúng danh sách, và kiểm `_tell` gửi đúng tin -
nhưng không cái nào đi qua chỗ hai thứ đó **được dùng**. Gỡ hẳn phần dùng ra thì
mọi test cũ vẫn xanh.

Đây là lần thứ năm cùng một khuôn trong 0.8: lỗi nằm ở chỗ nối, và test đi đường
tắt không thấy.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from xime.adapters.web import WebAdapter, configure_health
from xime.adapters.web._registry import registry
from xime.core.bootstrap._cluster import ClusterMember
from xime.starters.jwt import JwtMiddlewareConfig, configure_jwt
from xime.starters.jwt._config import jwt_registry


@pytest.fixture(autouse=True)
def reset():
    yield
    registry.reset()
    jwt_registry.reset()


def _middleware_config(app: FastAPI) -> JwtMiddlewareConfig:
    """Đào ra `config=` mà web adapter đã đẩy vào JwtAuthMiddleware."""
    from xime.starters.jwt._middleware import JwtAuthMiddleware

    for entry in app.user_middleware:
        if entry.cls is JwtAuthMiddleware:
            return entry.kwargs["config"]
    raise AssertionError("không có JwtAuthMiddleware nào được gắn")


class TestHealthPathsReachTheJwtMiddleware:
    """⛔ Hai đường dẫn sức khoẻ **không xác thực**, cố ý: chúng phải trả lời được
    khi mọi thứ khác đã hỏng, kể cả khi không lấy nổi khoá verify."""

    def test_they_are_added_to_public_paths(self) -> None:
        configure_jwt(JwtMiddlewareConfig(key_context="k", public_paths=["/login"]))
        configure_health()
        app = FastAPI()
        WebAdapter._add_jwt_middleware(app, None)  # type: ignore[arg-type]
        public = _middleware_config(app).public_paths
        assert "/healthz" in public
        assert "/readyz" in public

    def test_custom_paths_too(self) -> None:
        configure_jwt(JwtMiddlewareConfig(key_context="k"))
        configure_health(healthz="/_alive", readyz=None)
        app = FastAPI()
        WebAdapter._add_jwt_middleware(app, None)  # type: ignore[arg-type]
        assert "/_alive" in _middleware_config(app).public_paths

    def test_what_the_application_declared_is_not_lost(self) -> None:
        # Vế thứ hai của cặp: thêm vào chứ không thay thế. Ghi đè thì mọi endpoint
        # công khai của app đột nhiên đòi token, và nó hỏng ở đăng nhập.
        configure_jwt(JwtMiddlewareConfig(key_context="k", public_paths=["/login"]))
        configure_health()
        app = FastAPI()
        WebAdapter._add_jwt_middleware(app, None)  # type: ignore[arg-type]
        assert "/login" in _middleware_config(app).public_paths

    def test_nothing_is_added_when_health_is_off(self) -> None:
        configure_jwt(JwtMiddlewareConfig(key_context="k", public_paths=["/login"]))
        app = FastAPI()
        WebAdapter._add_jwt_middleware(app, None)  # type: ignore[arg-type]
        assert _middleware_config(app).public_paths == ["/login"]


class ExplodingLink:
    """Bus hỏng đúng lúc con muốn báo tin."""

    def __init__(self) -> None:
        self.tried = 0

    def announce_sync(self, *_args: object, **_kwargs: object) -> None:
        self.tried += 1
        raise RuntimeError("bộ nhớ chung đã bị gỡ")


class TestReportingNeverThrows:
    """⚠ Đường báo tin không được phép làm hỏng thứ nó đang đi báo.

    Nặng nhất là `report_promote_failed`: cả lời gọi tồn tại **vì có chuyện vừa
    hỏng**, nên một lỗi ở đó biến *"tôi không nhận được vai"* thành *"tôi chết
    luôn"* - đúng cái sập mà mục 4.4 của thiết kế dựng lên để tránh.
    """

    def _member(self) -> tuple[ClusterMember, ExplodingLink]:
        member = ClusterMember(None, share_load=True)
        link = ExplodingLink()
        member._link = link  # type: ignore[assignment]
        member._slots = 2  # coi như đang ở trong một cụm
        return member, link

    @pytest.mark.parametrize(
        "call",
        [
            lambda m: m.report_ready(),
            lambda m: m.report_run_once_done(),
            lambda m: m.report_promoted(),
            lambda m: m.report_promote_failed("cert hỏng"),
            lambda m: m.report_adapter_isolated("WebAdapter('default')"),
        ],
    )
    def test_a_broken_bus_does_not_take_the_caller_down(self, call) -> None:
        member, link = self._member()
        call(member)  # không ném
        assert link.tried == 1, "phép đo không chạm tới đường báo tin"

    def test_a_single_process_reports_nothing_at_all(self) -> None:
        # Vế thứ hai: một tiến trình đơn không có ai để báo, và nó KHÔNG được
        # cố gửi - gửi vào một bus một-ô là ghi một dòng không ai đọc, mỗi lần
        # khởi động.
        member, link = self._member()
        member._slots = 1
        member.report_ready()
        assert link.tried == 0
