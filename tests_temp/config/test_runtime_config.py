"""
Test RuntimeConfig và WebServerConfig:
  - giá trị mặc định
  - from_dict() với dữ liệu đầy đủ / một phần / extra keys
  - get() với dot-notation: key hợp lệ, thiếu, nested, default
  - get_bool() ép kiểu chặt: chuỗi "false" KHÔNG được thành True (0.6.3)
  - WebServerConfig validate kiểu dữ liệu
"""
import pytest

from xime.adapters.web import WebServerConfig
from xime.core.config import RuntimeConfig

# ⚠ `ServerConfig` ĐÃ RỜI core ở 0.8 và thành `WebServerConfig` của web
# adapter - core không được biết về khái niệm *"HTTP adapter"*. Khoá YAML
# `server:` thì **giữ nguyên từng chữ**, nên các test dưới vẫn đọc đúng khối
# đó, chỉ qua một cửa khác.


def _server(cfg: RuntimeConfig) -> WebServerConfig:
    return WebServerConfig.from_runtime(cfg)
from xime.core.exception import StartupException


# ---------------------------------------------------------------------------
# Giá trị mặc định
# ---------------------------------------------------------------------------

def test_default_env():
    cfg = RuntimeConfig()
    assert cfg.env == "development"


def test_default_server_host():
    cfg = RuntimeConfig()
    assert _server(cfg).host == "0.0.0.0"


def test_default_server_port():
    cfg = RuntimeConfig()
    assert _server(cfg).port == 8080


# ---------------------------------------------------------------------------
# from_dict()
# ---------------------------------------------------------------------------

def test_from_dict_empty_uses_defaults():
    cfg = RuntimeConfig.from_dict({})
    assert cfg.env == "development"
    assert _server(cfg).port == 8080


def test_from_dict_overrides_env():
    cfg = RuntimeConfig.from_dict({"env": "production"})
    assert cfg.env == "production"


def test_from_dict_overrides_server():
    cfg = RuntimeConfig.from_dict({"server": {"host": "127.0.0.1", "port": 9000}})
    assert _server(cfg).host == "127.0.0.1"
    assert _server(cfg).port == 9000


def test_from_dict_partial_server_uses_defaults_for_missing():
    cfg = RuntimeConfig.from_dict({"server": {"port": 9999}})
    assert _server(cfg).host == "0.0.0.0"   # mặc định
    assert _server(cfg).port == 9999


def test_from_dict_stores_extra_application_keys():
    cfg = RuntimeConfig.from_dict({
        "env": "staging",
        "database": {"url": "postgresql://localhost/db", "pool_size": 5},
    })
    assert cfg.env == "staging"
    # Extra key phải tồn tại và truy xuất được
    assert cfg.get("database.url") == "postgresql://localhost/db"
    assert cfg.get("database.pool_size") == 5


# ---------------------------------------------------------------------------
# get() - dot-notation access
# ---------------------------------------------------------------------------

def test_get_top_level_key():
    cfg = RuntimeConfig.from_dict({"env": "production"})
    assert cfg.get("env") == "production"


def test_get_nested_framework_key():
    cfg = RuntimeConfig.from_dict({"server": {"port": 9090}})
    assert cfg.get("server.port") == 9090


def test_get_no_longer_materialises_web_defaults():
    """⚠ **Đổi hành vi ở 0.8**, và nó là hệ quả trực tiếp của việc gỡ
    `ServerConfig` khỏi core.

    Trước đây `server:` là một model có kiểu **trên `RuntimeConfig`**, nên mặc
    định của nó lọt cả vào `get()`: `get("server.host")` trả `"0.0.0.0"` dù YAML
    không khai. Nay `server:` chỉ là một khoá thường, và `get()` trả đúng thứ có
    trong file.

    App nào cần mặc định thì đọc qua `WebServerConfig.from_runtime(runtime)` -
    chỗ mặc định thật sự sống. Khoá YAML **không đổi một chữ**.
    """
    cfg = RuntimeConfig.from_dict({"server": {"port": 9090}})
    assert cfg.get("server.host") is None
    assert WebServerConfig.from_runtime(cfg).host == "0.0.0.0"


def test_get_nested_extra_key():
    cfg = RuntimeConfig.from_dict({"redis": {"host": "redis-server", "port": 6379}})
    assert cfg.get("redis.host") == "redis-server"
    assert cfg.get("redis.port") == 6379


def test_get_missing_key_returns_none():
    cfg = RuntimeConfig()
    assert cfg.get("nonexistent") is None


def test_get_missing_key_returns_custom_default():
    cfg = RuntimeConfig()
    assert cfg.get("nonexistent", "fallback") == "fallback"


def test_get_partial_path_missing_returns_default():
    cfg = RuntimeConfig.from_dict({"database": {"host": "localhost"}})
    assert cfg.get("database.port", 5432) == 5432


def test_get_path_too_deep_returns_default():
    cfg = RuntimeConfig.from_dict({"server": {"port": 8080}})
    # port là int, không thể đi sâu hơn
    assert cfg.get("server.port.something", "nope") == "nope"


# ---------------------------------------------------------------------------
# get_bool() - ép kiểu boolean chặt (0.6.3)
# ---------------------------------------------------------------------------

def _flag(value) -> RuntimeConfig:
    return RuntimeConfig.from_dict({"xime": {"di": {"dynamic-binding": value}}})


FLAG = "xime.di.dynamic-binding"


def test_get_bool_missing_key_returns_default():
    cfg = RuntimeConfig()
    assert cfg.get_bool(FLAG) is False
    assert cfg.get_bool(FLAG, default=True) is True


def test_get_bool_null_value_returns_default():
    """YAML `dynamic-binding:` không giá trị -> None -> dùng default."""
    assert _flag(None).get_bool(FLAG) is False
    assert _flag(None).get_bool(FLAG, default=True) is True


def test_get_bool_native_booleans():
    assert _flag(True).get_bool(FLAG) is True
    assert _flag(False).get_bool(FLAG) is False


@pytest.mark.parametrize("value", ["false", "False", "FALSE", "no", "off", "0", 0])
def test_get_bool_falsy_spellings_stay_false(value):
    """Chính là footgun cũ: bool("false") == True nên cờ bị bật nhầm."""
    assert _flag(value).get_bool(FLAG) is False


@pytest.mark.parametrize("value", ["true", "True", "yes", "on", "1", 1])
def test_get_bool_truthy_spellings_become_true(value):
    assert _flag(value).get_bool(FLAG) is True


@pytest.mark.parametrize("value", ["maybe", "", "2", [], {"a": 1}])
def test_get_bool_rejects_non_boolean_loudly(value):
    """Cờ cấu hình sai phải nổ lúc startup, không âm thầm chọn một nhánh."""
    with pytest.raises(StartupException) as exc:
        _flag(value).get_bool(FLAG)
    assert FLAG in str(exc.value)


def test_get_bool_does_not_affect_get():
    """get() vẫn trả giá trị thô, không đổi hành vi cũ."""
    assert _flag("false").get(FLAG) == "false"


# ---------------------------------------------------------------------------
# WebServerConfig validation
# ---------------------------------------------------------------------------

def test_server_config_rejects_invalid_port():
    with pytest.raises(Exception):
        WebServerConfig(host="0.0.0.0", port="not-a-number")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Cache - model_dump() chỉ gọi một lần (Issue #10)
# ---------------------------------------------------------------------------

def test_get_does_not_call_model_dump_after_creation():
    """
    get() phải đọc từ _dump cache, không gọi thêm model_dump().
    model_dump() chỉ được gọi một lần khi model_post_init chạy.
    """
    from unittest.mock import patch

    cfg = RuntimeConfig.from_dict({
        "env": "production",
        "server": {"port": 9090},
        "database": {"url": "postgresql://localhost/db"},
    })

    # Patch INSTANCE method sau khi model đã được tạo (cache đã build xong)
    call_count = 0
    original = cfg.model_dump

    def counting_dump(**kw):
        nonlocal call_count
        call_count += 1
        return original(**kw)

    with patch.object(cfg, "model_dump", counting_dump):
        _ = cfg.get("env")
        _ = cfg.get("server.port")
        _ = cfg.get("database.url")
        _ = cfg.get("missing.key", "fallback")

    assert call_count == 0, (
        f"get() gọi model_dump() thêm {call_count} lần - phải dùng _dump cache"
    )


def test_dump_cache_populated_on_creation():
    """_dump được build ngay khi model tạo, không phải lazy."""
    cfg = RuntimeConfig.from_dict({"env": "staging", "server": {"port": 7777}})
    assert isinstance(cfg._dump, dict)
    assert cfg._dump["env"] == "staging"
    assert cfg._dump["server"]["port"] == 7777


def test_get_consistent_with_model_dump():
    """Kết quả get() phải nhất quán với model_dump() để đảm bảo cache không stale."""
    data = {
        "env": "production",
        "server": {"host": "10.0.0.1", "port": 443},
        "redis": {"host": "redis-host", "ttl": 300},
    }
    cfg = RuntimeConfig.from_dict(data)
    full_dump = cfg.model_dump()

    assert cfg.get("env") == full_dump["env"]
    assert cfg.get("server.port") == full_dump["server"]["port"]
    assert cfg.get("redis.ttl") == full_dump["redis"]["ttl"]


# ---------------------------------------------------------------------------
# F5 - repr() không được in secret
# ---------------------------------------------------------------------------

class TestRedactedRepr:
    """Một dòng `logger.debug("config=%s", config)` từng đủ để đẩy jwt.secret và
    mật khẩu DB ra file log dạng rõ."""

    def _config(self):
        return RuntimeConfig.from_dict(
            {
                "env": "production",
                "jwt": {"secret": "KHOA-KY-BI-MAT", "issuer": "trust"},
                "database": {"password": "MAT-KHAU-DB", "host": "db"},
                "auth": {"keys": {"signing_key": "AAA", "kid": "k1"}},
                "api_tokens": ["t1", "t2"],
            }
        )

    def test_repr_masks_sensitive_values(self):
        text = repr(self._config())
        for secret in ("KHOA-KY-BI-MAT", "MAT-KHAU-DB", "AAA", "t1"):
            assert secret not in text

    def test_repr_keeps_non_sensitive_values_readable(self):
        text = repr(self._config())
        assert "production" in text
        assert "trust" in text
        assert "'host': 'db'" in text
        assert "'kid': 'k1'" in text   # cấu trúc lồng vẫn đọc được

    def test_str_is_masked_too(self):
        # f-string dùng __str__; nếu chỉ vá __repr__ thì vẫn rò.
        assert "KHOA-KY-BI-MAT" not in f"{self._config()}"

    def test_get_still_returns_the_real_value(self):
        assert self._config().get("jwt.secret") == "KHOA-KY-BI-MAT"
