"""
Test configure_middleware() / configure_exception_handlers() (Issue #2 từ shop):

  Registry:
    - add_middleware giữ đúng thứ tự khai báo + options
    - add_exception_handlers merge nhiều lần gọi
    - tách biệt theo server_id
    - reset() xóa sạch

  build_app:
    - exception handler được add vào FastAPI app
    - middleware của user được add vào FastAPI app
"""
from unittest.mock import MagicMock

import pytest

from xime.adapters.web._config import configure_exception_handlers, configure_middleware
from xime.adapters.web._registry import _WebRegistry, registry


@pytest.fixture(autouse=True)
def reset_web_registry():
    """Khôi phục web registry sau mỗi test."""
    yield
    registry.reset()


class FakeMiddleware:
    def __init__(self, app, **options):
        self.app = app


class AppError(Exception):
    pass


async def app_error_handler(request, exc):  # chữ ký FastAPI (request, exc)
    return None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestWebRegistryMiddleware:
    def test_keeps_declaration_order_and_options(self):
        reg = _WebRegistry()
        reg.add_middleware(FakeMiddleware, {"a": 1})
        reg.add_middleware(FakeMiddleware, {"b": 2})
        result = reg.get_middlewares()
        assert result == [(FakeMiddleware, {"a": 1}), (FakeMiddleware, {"b": 2})]

    def test_separated_by_server_id(self):
        reg = _WebRegistry()
        reg.add_middleware(FakeMiddleware, {}, server_id="admin")
        assert reg.get_middlewares("default") == []
        assert reg.get_middlewares("admin") == [(FakeMiddleware, {})]

    def test_configure_middleware_writes_global_registry(self):
        configure_middleware(FakeMiddleware, some_option="x")
        assert registry.get_middlewares() == [(FakeMiddleware, {"some_option": "x"})]


class TestWebRegistryExceptionHandlers:
    def test_multiple_calls_merge(self):
        reg = _WebRegistry()
        reg.add_exception_handlers({AppError: app_error_handler})
        reg.add_exception_handlers({ValueError: app_error_handler})
        handlers = reg.get_exception_handlers()
        assert handlers == {AppError: app_error_handler, ValueError: app_error_handler}

    def test_later_registration_wins_for_same_type(self):
        async def other_handler(request, exc):
            return None

        reg = _WebRegistry()
        reg.add_exception_handlers({AppError: app_error_handler})
        reg.add_exception_handlers({AppError: other_handler})
        assert reg.get_exception_handlers()[AppError] is other_handler

    def test_configure_exception_handlers_writes_global_registry(self):
        configure_exception_handlers({AppError: app_error_handler})
        assert registry.get_exception_handlers() == {AppError: app_error_handler}

    def test_reset_clears_everything(self):
        reg = _WebRegistry()
        reg.add_middleware(FakeMiddleware, {})
        reg.add_exception_handlers({AppError: app_error_handler})
        reg.reset()
        assert reg.get_middlewares() == []
        assert reg.get_exception_handlers() == {}


# ---------------------------------------------------------------------------
# build_app - handlers/middleware thực sự được gắn vào FastAPI app
# ---------------------------------------------------------------------------

class TestBuildAppApplies:
    def _build(self):
        from xime.adapters.web import WebAdapter
        return WebAdapter().build_app(MagicMock())

    def test_exception_handler_attached_to_fastapi_app(self):
        configure_exception_handlers({AppError: app_error_handler})
        fastapi_app = self._build()
        assert fastapi_app.exception_handlers.get(AppError) is app_error_handler

    def test_user_middleware_attached_to_fastapi_app(self):
        configure_middleware(FakeMiddleware, marker="m1")
        fastapi_app = self._build()
        entries = [m for m in fastapi_app.user_middleware if m.cls is FakeMiddleware]
        assert len(entries) == 1
        assert entries[0].kwargs == {"marker": "m1"}

    def test_request_context_remains_outermost(self):
        """RequestContextMiddleware phải nằm ngoài cùng (phần tử cuối user_middleware
        là middleware add sau cùng = outermost trong Starlette)."""
        from xime.adapters.web.middleware import RequestContextMiddleware

        configure_middleware(FakeMiddleware)
        fastapi_app = self._build()
        # Starlette giữ user_middleware theo thứ tự add ngược (add sau → đứng đầu)
        assert fastapi_app.user_middleware[0].cls is RequestContextMiddleware

    def test_user_middleware_declared_first_runs_first(self):
        """Khai báo trước → outermost hơn trong nhóm user middleware."""
        class MiddlewareA(FakeMiddleware): ...
        class MiddlewareB(FakeMiddleware): ...

        configure_middleware(MiddlewareA)
        configure_middleware(MiddlewareB)
        fastapi_app = self._build()
        classes = [m.cls for m in fastapi_app.user_middleware]
        # outermost trước: RequestContext, rồi A (khai báo trước), rồi B
        index_a = classes.index(MiddlewareA)
        index_b = classes.index(MiddlewareB)
        assert index_a < index_b
