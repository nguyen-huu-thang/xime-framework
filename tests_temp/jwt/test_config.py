"""
Test JwtMiddlewareConfig và configure_jwt() / jwt_registry:
  - JwtMiddlewareConfig: giá trị mặc định của identity_claim và public_paths
  - JwtMiddlewareConfig: lưu đúng key_context
  - JwtMiddlewareConfig: tùy chỉnh identity_claim và public_paths
  - jwt_registry.get() trả về None trước khi configure_jwt()
  - configure_jwt() lưu config vào registry
  - configure_jwt() gọi lần 2 ghi đè config cũ
  - configure_jwt() không clone config — trả về cùng object
"""
import pytest

from starters.jwt._config import JwtMiddlewareConfig, configure_jwt, jwt_registry
from starters.jwt._key_context import KeyContext


@pytest.fixture(autouse=True)
def reset_jwt_registry():
    """Khôi phục registry về trạng thái ban đầu sau mỗi test."""
    original = jwt_registry.get()
    yield
    jwt_registry._config = original


def _make_ctx() -> KeyContext:
    return KeyContext(algorithm="HS256", secret="test-secret")


# ---------------------------------------------------------------------------
# JwtMiddlewareConfig — defaults và giá trị tùy chỉnh
# ---------------------------------------------------------------------------

class TestJwtMiddlewareConfigDefaults:
    def test_identity_claim_defaults_to_sub(self):
        config = JwtMiddlewareConfig(key_context=_make_ctx())
        assert config.identity_claim == "sub"

    def test_public_paths_defaults_to_empty_list(self):
        config = JwtMiddlewareConfig(key_context=_make_ctx())
        assert config.public_paths == []

    def test_key_context_is_stored(self):
        ctx = _make_ctx()
        config = JwtMiddlewareConfig(key_context=ctx)
        assert config.key_context is ctx


class TestJwtMiddlewareConfigCustom:
    def test_custom_identity_claim(self):
        config = JwtMiddlewareConfig(key_context=_make_ctx(), identity_claim="user_id")
        assert config.identity_claim == "user_id"

    def test_custom_public_paths(self):
        paths = ["/login", "/health", "/metrics"]
        config = JwtMiddlewareConfig(key_context=_make_ctx(), public_paths=paths)
        assert config.public_paths == paths

    def test_public_paths_are_independent_per_instance(self):
        """Hai config với public_paths mặc định không dùng chung list."""
        config_a = JwtMiddlewareConfig(key_context=_make_ctx())
        config_b = JwtMiddlewareConfig(key_context=_make_ctx())
        config_a.public_paths.append("/new")
        assert "/new" not in config_b.public_paths


# ---------------------------------------------------------------------------
# jwt_registry + configure_jwt()
# ---------------------------------------------------------------------------

class TestJwtRegistry:
    def test_registry_returns_none_before_configure(self):
        jwt_registry._config = None
        assert jwt_registry.get() is None

    def test_configure_jwt_stores_config_in_registry(self):
        config = JwtMiddlewareConfig(key_context=_make_ctx())
        configure_jwt(config)
        assert jwt_registry.get() is not None

    def test_configure_jwt_stores_exact_config_object(self):
        config = JwtMiddlewareConfig(key_context=_make_ctx())
        configure_jwt(config)
        assert jwt_registry.get() is config

    def test_configure_jwt_twice_overwrites_previous(self):
        config_a = JwtMiddlewareConfig(key_context=_make_ctx(), identity_claim="sub")
        config_b = JwtMiddlewareConfig(key_context=_make_ctx(), identity_claim="uid")
        configure_jwt(config_a)
        configure_jwt(config_b)
        assert jwt_registry.get().identity_claim == "uid"

    def test_configure_jwt_config_preserves_public_paths(self):
        paths = ["/auth/login", "/health"]
        config = JwtMiddlewareConfig(key_context=_make_ctx(), public_paths=paths)
        configure_jwt(config)
        assert jwt_registry.get().public_paths == paths
