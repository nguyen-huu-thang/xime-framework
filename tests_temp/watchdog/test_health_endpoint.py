"""`configure_health()` - endpoint sẵn, **mặc định TẮT**.

Test đi thành cặp ở đúng chỗ đó: không khai thì **không có route nào**, khai thì
có. Chỉ kiểm vế sau thì một hiện thực luôn thêm route cũng qua được - mà đó là
phương án A, phương án chủ dự án đã bác vì bất ngờ.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# `public_health_paths` cố ý lấy qua ĐƯỜNG CÔNG KHAI, đúng dòng tài liệu bảo
# người dùng viết. Lấy từ `._health` thì bộ test vẫn xanh kể cả ngày cái tên rơi
# khỏi `__all__` - tức nó canh hàm, không canh thứ người dùng chạm tới.
from xime.adapters.web import configure_health, public_health_paths
from xime.adapters.web._health import add_health_routes
from xime.adapters.web._registry import registry
from xime.core.bootstrap._health import (
    ISOLATED,
    SERVING,
    STANDBY,
    AdapterHealth,
    HealthReport,
)


@pytest.fixture(autouse=True)
def reset_registry():
    yield
    registry.reset()


class FakeApp:
    """Đứng thay `Application` - chỉ cần một method `health()`."""

    def __init__(self, *states: str, primary: bool = True) -> None:
        self._report = HealthReport(
            primary=primary,
            adapters=tuple(
                AdapterHealth(adapter_id=f"a{i}", kind="web", state=s)
                for i, s in enumerate(states)
            ),
        )

    def health(self) -> HealthReport:
        return self._report


def _client(app_state: FakeApp) -> TestClient:
    fastapi_app = FastAPI()
    add_health_routes(fastapi_app, app_state)  # type: ignore[arg-type]
    return TestClient(fastapi_app)


class TestItIsOffUntilAsked:
    def test_no_configure_call_means_no_routes(self) -> None:
        fastapi_app = FastAPI()
        add_health_routes(fastapi_app, FakeApp(SERVING))  # type: ignore[arg-type]
        paths = {r.path for r in fastapi_app.routes}  # type: ignore[attr-defined]
        assert "/healthz" not in paths
        assert "/readyz" not in paths

    def test_configuring_it_adds_both(self) -> None:
        configure_health()
        fastapi_app = FastAPI()
        add_health_routes(fastapi_app, FakeApp(SERVING))  # type: ignore[arg-type]
        paths = {r.path for r in fastapi_app.routes}  # type: ignore[attr-defined]
        assert {"/healthz", "/readyz"} <= paths

    def test_one_of_the_two_can_be_turned_off(self) -> None:
        configure_health(readyz=None)
        fastapi_app = FastAPI()
        add_health_routes(fastapi_app, FakeApp(SERVING))  # type: ignore[arg-type]
        paths = {r.path for r in fastapi_app.routes}  # type: ignore[attr-defined]
        assert "/healthz" in paths
        assert "/readyz" not in paths

    def test_the_paths_can_be_moved(self) -> None:
        """Một đường dẫn cố định có thể va với route nghiệp vụ - đó là nửa lý do
        phương án A bị bác."""
        configure_health(healthz="/_alive", readyz="/_ready")
        fastapi_app = FastAPI()
        add_health_routes(fastapi_app, FakeApp(SERVING))  # type: ignore[arg-type]
        paths = {r.path for r in fastapi_app.routes}  # type: ignore[attr-defined]
        assert {"/_alive", "/_ready"} <= paths


class TestTheStatusCodes:
    def test_both_green_when_everything_serves(self) -> None:
        configure_health()
        client = _client(FakeApp(SERVING, SERVING))
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200

    def test_one_broken_pulls_readyz_but_not_healthz(self) -> None:
        """⭐ Ca hai đường dẫn phải trả lời khác nhau - lý do không gộp chúng."""
        configure_health()
        client = _client(FakeApp(SERVING, ISOLATED))
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 503

    def test_everything_broken_reddens_both(self) -> None:
        configure_health()
        client = _client(FakeApp(ISOLATED))
        assert client.get("/healthz").status_code == 503
        assert client.get("/readyz").status_code == 503

    def test_a_standby_singleton_keeps_readyz_green(self) -> None:
        configure_health()
        client = _client(FakeApp(SERVING, STANDBY, primary=False))
        assert client.get("/readyz").status_code == 200
        assert client.get("/readyz").json()["primary"] is False


class TestTheyAreAlwaysPublic:
    """⛔ Cố ý không xác thực: chúng phải trả lời được **khi mọi thứ khác đã
    hỏng**, kể cả khi không lấy nổi khoá verify. Một `/healthz` đòi token là một
    `/healthz` im lặng đúng lúc cần nhất."""

    def test_nothing_configured_lists_nothing(self) -> None:
        assert public_health_paths() == ()

    def test_configured_paths_are_listed_for_the_jwt_middleware(self) -> None:
        configure_health(healthz="/_alive", readyz="/_ready")
        assert set(public_health_paths()) == {"/_alive", "/_ready"}

    def test_a_disabled_one_is_not_listed(self) -> None:
        # Không tắt route mà vẫn khai nó là công khai thì ta đang mở một đường
        # dẫn không tồn tại - vô hại hôm nay, và là một cái bẫy ngày ai đó dùng
        # lại đúng đường dẫn ấy cho việc khác.
        configure_health(readyz=None)
        assert set(public_health_paths()) == {"/healthz"}


class TestNoLayInDuocQuaDuongCongKhai:
    """⭐ Không phải chuyện phong cách: 8 repo đã gọi hàm này từ `._health` vì
    nó thiếu ở `__all__` - lời import riêng tư DUY NHẤT nằm trong code sản
    phẩm của cả 28 repo. Một hàm tự khai mình để cho app dùng thì phải có
    đường công khai, nếu không app buộc phải bám vào ruột của framework."""

    def test_ten_nam_trong_all(self) -> None:
        import xime.adapters.web as web

        assert "public_health_paths" in web.__all__

    def test_khong_can_cham_toi_module_rieng_tu(self) -> None:
        # `from xime.adapters.web import public_health_paths` phải chạy được -
        # chính là dòng ở đầu file này.
        assert public_health_paths.__module__ == "xime.adapters.web._health"


class TestMiddlewareTuVietChoDuongSucKhoeDiQua:
    """Đường dùng mà docstring của hàm hướng dẫn, chạy thật.

    ⚠ Đây KHÔNG phải middleware xác thực, và đó là chủ đích: lý do phản đối
    việc export là *"nó chỉ có ích cho người tự viết middleware JWT"*. Một hàng
    rào IP đủ để bác lập luận đó - nó không biến mất khi app chuyển sang
    `configure_jwt`.
    """

    @staticmethod
    def _client_voi_hang_rao(cong_khai: tuple[str, ...]):
        class HangRaoIp:
            def __init__(self, app, public_paths: tuple[str, ...]) -> None:
                self.app = app
                self.public_paths = public_paths

            async def __call__(self, scope, receive, send):
                if scope["type"] == "http" and scope["path"] not in self.public_paths:
                    from starlette.responses import JSONResponse

                    await JSONResponse({"detail": "cam"}, status_code=403)(
                        scope, receive, send
                    )
                    return
                await self.app(scope, receive, send)

        app = FastAPI()
        add_health_routes(app, FakeApp(SERVING))

        @app.get("/nghiep-vu")
        def _nghiep_vu() -> dict[str, bool]:
            return {"ok": True}

        app.add_middleware(HangRaoIp, public_paths=cong_khai)
        return TestClient(app)

    def test_duong_suc_khoe_di_qua_duoc_hang_rao(self) -> None:
        configure_health()
        client = self._client_voi_hang_rao(public_health_paths())
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200

    def test_ma_duong_nghiep_vu_thi_khong(self) -> None:
        # Vế thứ hai của cặp. Thiếu nó thì một hàng rào cho qua TẤT CẢ cũng
        # xanh, và test trên không chứng minh được gì.
        configure_health()
        client = self._client_voi_hang_rao(public_health_paths())
        assert client.get("/nghiep-vu").status_code == 403

    def test_quen_configure_health_thi_hang_rao_chan_luon_healthz(self) -> None:
        # ⚠ Cái bẫy thứ tự, khoá lại thành hành vi biết trước thay vì một điều
        # bất ngờ: đọc trước khi khai thì danh sách rỗng, và `/healthz` bị
        # chính hàng rào của mình chặn - im lặng, vì 403 trông rất gọn gàng.
        cong_khai = public_health_paths()
        configure_health()
        client = self._client_voi_hang_rao(cong_khai)
        assert cong_khai == ()
        assert client.get("/healthz").status_code == 403

