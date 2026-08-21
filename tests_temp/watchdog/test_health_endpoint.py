"""`configure_health()` - endpoint sẵn, **mặc định TẮT**.

Test đi thành cặp ở đúng chỗ đó: không khai thì **không có route nào**, khai thì
có. Chỉ kiểm vế sau thì một hiện thực luôn thêm route cũng qua được - mà đó là
phương án A, phương án chủ dự án đã bác vì bất ngờ.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from xime.adapters.web import configure_health
from xime.adapters.web._health import add_health_routes, public_health_paths
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
