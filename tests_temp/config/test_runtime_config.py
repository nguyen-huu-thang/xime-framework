"""
Test RuntimeConfig và ServerConfig:
  - giá trị mặc định
  - from_dict() với dữ liệu đầy đủ / một phần / extra keys
  - get() với dot-notation: key hợp lệ, thiếu, nested, default
  - ServerConfig validate kiểu dữ liệu
"""
import pytest

from core.config import RuntimeConfig, ServerConfig


# ---------------------------------------------------------------------------
# Giá trị mặc định
# ---------------------------------------------------------------------------

def test_default_env():
    cfg = RuntimeConfig()
    assert cfg.env == "development"


def test_default_server_host():
    cfg = RuntimeConfig()
    assert cfg.server.host == "0.0.0.0"


def test_default_server_port():
    cfg = RuntimeConfig()
    assert cfg.server.port == 8080


# ---------------------------------------------------------------------------
# from_dict()
# ---------------------------------------------------------------------------

def test_from_dict_empty_uses_defaults():
    cfg = RuntimeConfig.from_dict({})
    assert cfg.env == "development"
    assert cfg.server.port == 8080


def test_from_dict_overrides_env():
    cfg = RuntimeConfig.from_dict({"env": "production"})
    assert cfg.env == "production"


def test_from_dict_overrides_server():
    cfg = RuntimeConfig.from_dict({"server": {"host": "127.0.0.1", "port": 9000}})
    assert cfg.server.host == "127.0.0.1"
    assert cfg.server.port == 9000


def test_from_dict_partial_server_uses_defaults_for_missing():
    cfg = RuntimeConfig.from_dict({"server": {"port": 9999}})
    assert cfg.server.host == "0.0.0.0"   # mặc định
    assert cfg.server.port == 9999


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
# get() — dot-notation access
# ---------------------------------------------------------------------------

def test_get_top_level_key():
    cfg = RuntimeConfig.from_dict({"env": "production"})
    assert cfg.get("env") == "production"


def test_get_nested_framework_key():
    cfg = RuntimeConfig.from_dict({"server": {"port": 9090}})
    assert cfg.get("server.port") == 9090
    assert cfg.get("server.host") == "0.0.0.0"


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
# ServerConfig validation
# ---------------------------------------------------------------------------

def test_server_config_rejects_invalid_port():
    with pytest.raises(Exception):
        ServerConfig(host="0.0.0.0", port="not-a-number")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Cache — model_dump() chỉ gọi một lần (Issue #10)
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
        f"get() gọi model_dump() thêm {call_count} lần — phải dùng _dump cache"
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
