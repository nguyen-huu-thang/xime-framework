"""
F1 - đăng ký route WebSocket ở tầng WebAdapter (0.7.2).

Trước bản này `WebSocketHandler` là một lớp nền KHÔNG CÓ đường gắn vào ứng dụng:
không có `@ws`, không có `add_api_websocket_route` ở đâu trong `xime/`, và chính
docstring của nó viết "routing API sẽ được thiết kế sau". PoC của kiểm toán chạy
được là vì nó tự dựng `WebSocketRoute` bằng Starlette, không đi qua đường nào của
Xime.
"""
import pytest
from fastapi import FastAPI

from xime.adapters.web import WebSocketHandler, ws
from xime.adapters.web._adapter import WebAdapter
from xime.starters.jwt import JwtMiddlewareConfig, KeyContext

_LOGGER = "xime.web.ws"


class _FakeScanner:
    """Stands in for ControllerScanner: the walk itself is tested elsewhere."""

    def __init__(self, *handlers: type) -> None:
        self._handlers = list(handlers)

    def find_websocket_handlers(self, *_packages: str) -> list[type]:
        return list(self._handlers)


class _FakeApp:
    def __init__(self, *instances) -> None:
        self._by_type = {type(i): i for i in instances}

    def get(self, cls):
        return self._by_type[cls]


@ws("/ws/one")
class OneHandler(WebSocketHandler):
    pass


@ws("/ws/two")
class TwoHandler(WebSocketHandler):
    pass


@ws("/ws/other-server")
class OtherServerHandler(WebSocketHandler):
    server_id = "admin"


def _register(handlers, instances, *, server_id="default"):
    app = FastAPI()
    WebAdapter._register_websocket_handlers(
        app, _FakeApp(*instances), server_id, _FakeScanner(*handlers), ["pkg"]
    )
    return app


def _ws_paths(app: FastAPI) -> set[str]:
    from starlette.routing import WebSocketRoute

    return {r.path for r in app.routes if isinstance(r, WebSocketRoute)}


@pytest.fixture(autouse=True)
def _clean_jwt_registry():
    from xime.starters.jwt._config import jwt_registry

    saved = jwt_registry.get()
    yield
    jwt_registry._config = saved  # type: ignore[attr-defined]


class TestRegistration:
    def test_every_marked_class_becomes_a_route(self):
        app = _register([OneHandler, TwoHandler], [OneHandler(), TwoHandler()])
        assert _ws_paths(app) == {"/ws/one", "/ws/two"}

    def test_handlers_of_another_server_are_skipped(self):
        """Same rule controllers already follow - one adapter, one server_id."""
        app = _register(
            [OneHandler, OtherServerHandler], [OneHandler(), OtherServerHandler()]
        )
        assert _ws_paths(app) == {"/ws/one"}

    def test_a_handler_missing_from_the_container_says_which_and_why(self):
        with pytest.raises(RuntimeError, match="dependency.scan"):
            _register([OneHandler], [])

    def test_no_handlers_means_nothing_happens(self):
        app = _register([], [])
        assert _ws_paths(app) == set()


class TestOpenSocketWarning:
    """An app may legitimately have no JWT - but its sockets are then open.

    F1 survived because that fact was silent. The warning is what ends the
    silence; it does not change behaviour.
    F1 sống lâu vì chuyện đó im lặng. Cảnh báo chấm dứt sự im lặng chứ không đổi
    hành vi.

    Paired tests: it must fire when there is something to warn about and stay
    quiet otherwise - a warning that always fires teaches people to skip logs.
    """

    def test_websocket_routes_without_configure_jwt_are_reported(self, caplog):
        from xime.starters.jwt._config import jwt_registry

        jwt_registry._config = None  # type: ignore[attr-defined]
        with caplog.at_level("WARNING", logger=_LOGGER):
            _register([OneHandler, TwoHandler], [OneHandler(), TwoHandler()])

        assert "configure_jwt() was never called" in caplog.text
        assert "OneHandler" in caplog.text and "TwoHandler" in caplog.text

    def test_nothing_is_said_when_jwt_is_configured(self, caplog):
        from xime.starters.jwt._config import jwt_registry

        jwt_registry._config = JwtMiddlewareConfig(  # type: ignore[attr-defined]
            key_context=KeyContext(algorithm="HS256", secret="x" * 32)
        )
        with caplog.at_level("WARNING", logger=_LOGGER):
            _register([OneHandler], [OneHandler()])

        assert caplog.text == ""

    def test_nothing_is_said_when_there_are_no_websocket_routes(self, caplog):
        """The other half again: an app with no sockets has nothing open."""
        from xime.starters.jwt._config import jwt_registry

        jwt_registry._config = None  # type: ignore[attr-defined]
        with caplog.at_level("WARNING", logger=_LOGGER):
            _register([], [])

        assert caplog.text == ""


class TestScannerFindsMarkedClasses:
    def test_the_predicate_picks_ws_classes_not_controllers(self):
        """find_websocket_handlers and find_controllers share one walk.

        Chúng dùng chung một phép duyệt, chỉ khác vị từ - viết scanner thứ hai là
        để hai đoạn code cùng quyết định "một gói là gì", rồi chúng lệch nhau.
        """
        from xime.adapters.web.routing._scanner import ControllerScanner
        from xime.adapters.web.ws._decorators import get_ws_info

        scanner = ControllerScanner()
        found = scanner.find_websocket_handlers("tests_temp.ws")
        assert OneHandler in found
        assert all(get_ws_info(cls) is not None for cls in found)

    def test_a_ws_class_is_not_mistaken_for_a_controller(self):
        from xime.adapters.web.routing._scanner import ControllerScanner

        controllers = ControllerScanner().find_controllers("tests_temp.ws")
        assert OneHandler not in controllers
