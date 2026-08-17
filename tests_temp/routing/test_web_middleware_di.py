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
        with pytest.raises(RuntimeError, match="is not registered"):
            resolve_options({"auth_svc": Inject(AuthService)}, app)

    def test_from_config_no_default_is_none(self):
        """FromConfig không truyền default + thiếu key -> None (không có chế độ bắt buộc)."""
        app = FakeApp(config=RuntimeConfig.from_dict({}))
        resolved = resolve_options({"realm": FromConfig("auth.realm")}, app)
        assert resolved["realm"] is None

    def test_runtime_config_fetched_once_for_many_from_config(self):
        """RuntimeConfig chỉ lấy một lần dù nhiều FromConfig (tránh get() lặp)."""
        from unittest.mock import MagicMock

        config = RuntimeConfig.from_dict({"a": {"b": 1, "c": 2}})
        app = MagicMock()
        app.get.return_value = config
        resolve_options({"x": FromConfig("a.b"), "y": FromConfig("a.c")}, app)
        assert app.get.call_count == 1

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

    def test_separated_by_server_id(self):
        configure_cors(allow_origins=["http://admin"], server_id="admin")
        assert registry.get_middlewares("default") == []
        assert len(registry.get_middlewares("admin")) == 1

    def test_missing_yaml_uses_starlette_defaults(self):
        """configure_cors() + không có khối cors.* -> mặc định an toàn Starlette."""
        from starlette.middleware.cors import CORSMiddleware
        from xime.adapters.web import WebAdapter

        app = FakeApp(config=RuntimeConfig.from_dict({}))
        configure_cors()
        fastapi_app = WebAdapter().build_app(app)
        kwargs = next(
            m for m in fastapi_app.user_middleware if m.cls is CORSMiddleware
        ).kwargs
        assert kwargs["allow_origins"] == ()
        assert kwargs["allow_methods"] == ("GET",)
        assert kwargs["allow_credentials"] is False
        assert kwargs["max_age"] == 600

    def test_explicit_beats_yaml(self):
        from starlette.middleware.cors import CORSMiddleware
        from xime.adapters.web import WebAdapter

        config = RuntimeConfig.from_dict({"cors": {"allow_origins": ["http://yaml"]}})
        app = FakeApp(config=config)
        configure_cors(allow_origins=["http://explicit"])
        fastapi_app = WebAdapter().build_app(app)
        kwargs = next(
            m for m in fastapi_app.user_middleware if m.cls is CORSMiddleware
        ).kwargs
        assert kwargs["allow_origins"] == ["http://explicit"]

    def test_string_allow_origins_from_yaml_fails_startup(self):
        """F4: quên ngoặc vuông trong YAML -> Starlette duyệt TỪNG KÝ TỰ.

        Không nổ, không khớp gì cả - kiểu hỏng im lặng tệ nhất, nên chặn ngay
        lúc khởi động.
        """
        from xime.adapters.web import WebAdapter
        from xime.core.exception.framework import StartupException

        app = FakeApp(
            config=RuntimeConfig.from_dict(
                {"cors": {"allow_origins": "https://app.example.com"}}
            )
        )
        configure_cors()
        with pytest.raises(StartupException, match="must be a LIST"):
            WebAdapter().build_app(app)

    def test_wildcard_with_credentials_fails_startup(self):
        """F4: Starlette PHẢN CHIẾU origin của người gọi, trình duyệt KHÔNG chặn."""
        from xime.adapters.web import WebAdapter
        from xime.core.exception.framework import StartupException

        app = FakeApp(config=RuntimeConfig.from_dict({}))
        configure_cors(allow_origins=["*"], allow_credentials=True)
        with pytest.raises(StartupException, match="wide open"):
            WebAdapter().build_app(app)

    def test_wildcard_without_credentials_is_allowed(self):
        # Public API không cookie: '*' là hợp lệ, đừng chặn nhầm.
        from starlette.middleware.cors import CORSMiddleware
        from xime.adapters.web import WebAdapter

        app = FakeApp(config=RuntimeConfig.from_dict({}))
        configure_cors(allow_origins=["*"])
        fastapi_app = WebAdapter().build_app(app)
        assert any(m.cls is CORSMiddleware for m in fastapi_app.user_middleware)

    def test_cors_sits_outside_jwt_in_stack(self):
        """CORS phải outermost hơn JwtAuth: preflight OPTIONS chạy trước xác thực
        (đúng kịch bản I1 - thứ tự middleware)."""
        from starlette.middleware.cors import CORSMiddleware
        from xime.adapters.web import WebAdapter
        from xime.starters.jwt import (
            JwtMiddlewareConfig,
            KeyContext,
            configure_jwt,
        )
        from xime.starters.jwt._config import jwt_registry
        from xime.starters.jwt._middleware import JwtAuthMiddleware

        try:
            configure_jwt(
                JwtMiddlewareConfig(
                    key_context=KeyContext(algorithm="HS256", secret="x" * 32)
                )
            )
            configure_cors(allow_origins=["http://x"])
            fastapi_app = WebAdapter().build_app(
                FakeApp(config=RuntimeConfig.from_dict({}))
            )
            classes = [m.cls for m in fastapi_app.user_middleware]
            # Starlette: add sau = đứng đầu list = outermost. CORS add sau JwtAuth.
            assert classes.index(CORSMiddleware) < classes.index(JwtAuthMiddleware)
        finally:
            jwt_registry.reset()


# --- F11: configure_jwt không ép audience ----------------------------------

class TestJwtAudienceWarning:
    """Nền tảng dùng chung một nơi ký token: bỏ `aud` nghĩa là token cấp cho
    service KHÁC vẫn qua được ở đây (cùng chữ ký, cùng issuer)."""

    _LOGGER = "xime.adapters.web._adapter"

    def _configure(self, **extra):
        from xime.starters.jwt import JwtMiddlewareConfig, KeyContext, configure_jwt

        configure_jwt(
            JwtMiddlewareConfig(
                key_context=KeyContext(algorithm="HS256", secret="x" * 32), **extra
            )
        )

    def test_missing_audience_warns(self, caplog):
        from fastapi import FastAPI

        from xime.adapters.web import WebAdapter
        from xime.starters.jwt._config import jwt_registry

        try:
            self._configure()
            with caplog.at_level("WARNING", logger=self._LOGGER):
                WebAdapter._add_jwt_middleware(FastAPI())
            assert "audience" in caplog.text
        finally:
            jwt_registry.reset()

    def test_audience_set_says_nothing(self, caplog):
        from fastapi import FastAPI

        from xime.adapters.web import WebAdapter
        from xime.starters.jwt._config import jwt_registry

        try:
            self._configure(audience="data-service")
            with caplog.at_level("WARNING", logger=self._LOGGER):
                WebAdapter._add_jwt_middleware(FastAPI())
            assert caplog.text == ""
        finally:
            jwt_registry.reset()
