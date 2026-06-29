"""
Test marker Inject/FromConfig cho option middleware + configure_cors().

Khoảng trống trước đây (shop/dental phải subclass WebAdapter): middleware cần
service từ DI container hoặc giá trị từ runtime config thì không khai báo được
qua configure_middleware (chỉ nhận option tĩnh). Marker Inject/FromConfig lấp
khoảng trống đó — phân giải lúc build_app.
"""
import pytest

from xime.adapters.web import (
    FromConfig,
    Inject,
    configure_cors,
    configure_middleware,
)
from xime.adapters.web._markers import resolve_options
from xime.adapters.web._registry import registry
from xime.core.config.runtime import RuntimeConfig


@pytest.fixture(autouse=True)
def reset_web_registry():
    yield
    registry.reset()


# --- Fakes -----------------------------------------------------------------

class AuthService:
    pass


class FakeApp:
    """Giả lập Application.get(): tra theo type, có sẵn RuntimeConfig."""

    def __init__(self, *, config: RuntimeConfig | None = None, **bindings):
        self._by_type = {type(v): v for v in bindings.values()}
        if config is not None:
            self._by_type[RuntimeConfig] = config

    def get(self, cls):
        try:
            return self._by_type[cls]
        except KeyError:
            raise KeyError(cls) from None


# --- resolve_options -------------------------------------------------------

class TestResolveOptions:
    def test_inject_resolved_from_container(self):
        auth = AuthService()
        app = FakeApp(auth=auth)
        resolved = resolve_options({"auth_svc": Inject(AuthService)}, app)
        assert resolved["auth_svc"] is auth

    def test_inject_missing_type_raises_clear_error(self):
        app = FakeApp()
        with pytest.raises(RuntimeError, match="chưa được đăng ký"):
            resolve_options({"auth_svc": Inject(AuthService)}, app)

    def test_from_config_reads_runtime_value(self):
        config = RuntimeConfig.from_dict({"cors": {"allow_origins": ["https://x"]}})
        app = FakeApp(config=config)
        resolved = resolve_options(
            {"allow_origins": FromConfig("cors.allow_origins", [])}, app
        )
        assert resolved["allow_origins"] == ["https://x"]

    def test_from_config_falls_back_to_default(self):
        config = RuntimeConfig.from_dict({})
        app = FakeApp(config=config)
        resolved = resolve_options(
            {"allow_origins": FromConfig("cors.allow_origins", ["d"])}, app
        )
        assert resolved["allow_origins"] == ["d"]

    def test_plain_values_pass_through_untouched(self):
        app = FakeApp()
        resolved = resolve_options({"x": 1, "y": "z"}, app)
        assert resolved == {"x": 1, "y": "z"}


# --- build_app phân giải marker thật --------------------------------------

class CapturingMiddleware:
    def __init__(self, app, **kwargs):
        self.app = app


class TestBuildAppResolvesMarkers:
    def test_inject_and_fromconfig_resolved_into_middleware(self):
        # Starlette khởi tạo middleware lười (lúc chạy) nên ta kiểm tra kwargs đã
        # phân giải trên user_middleware, không dựa vào việc khởi tạo.
        auth = AuthService()
        config = RuntimeConfig.from_dict({"feature": {"flag": True}})
        app = FakeApp(auth=auth, config=config)

        configure_middleware(
            CapturingMiddleware,
            auth_svc=Inject(AuthService),
            flag=FromConfig("feature.flag", False),
            static="keep",
        )

        from xime.adapters.web import WebAdapter
        fastapi_app = WebAdapter().build_app(app)

        entry = next(
            m for m in fastapi_app.user_middleware if m.cls is CapturingMiddleware
        )
        assert entry.kwargs["auth_svc"] is auth
        assert entry.kwargs["flag"] is True
        assert entry.kwargs["static"] == "keep"


# --- configure_cors --------------------------------------------------------

class TestConfigureCors:
    def _cors_options(self):
        mws = registry.get_middlewares()
        assert len(mws) == 1
        return mws[0][1]

    def test_explicit_values_used_directly(self):
        configure_cors(allow_origins=["http://localhost:3000"], allow_credentials=True)
        opts = self._cors_options()
        assert opts["allow_origins"] == ["http://localhost:3000"]
        assert opts["allow_credentials"] is True

    def test_unset_values_become_fromconfig_markers(self):
        configure_cors()
        opts = self._cors_options()
        assert isinstance(opts["allow_origins"], FromConfig)
        assert opts["allow_origins"].key == "cors.allow_origins"

    def test_resolves_from_yaml_at_build(self):
        config = RuntimeConfig.from_dict(
            {"cors": {"allow_origins": ["https://app"], "allow_credentials": True}}
        )
        app = FakeApp(config=config)
        configure_cors()

        from starlette.middleware.cors import CORSMiddleware
        from xime.adapters.web import WebAdapter

        fastapi_app = WebAdapter().build_app(app)
        entry = next(m for m in fastapi_app.user_middleware if m.cls is CORSMiddleware)
        assert entry.kwargs["allow_origins"] == ["https://app"]
        assert entry.kwargs["allow_credentials"] is True
