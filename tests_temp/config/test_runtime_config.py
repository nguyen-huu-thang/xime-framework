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
