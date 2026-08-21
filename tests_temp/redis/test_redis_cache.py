"""
Test the redis starter (0.4) using mocks only - no live Redis server required.

  RedisCacheService (implements cache.CacheService):
    - satisfies the CacheService Protocol
    - get / set(ttl) / delete / exists delegate to the right client commands
    - exists() normalises Redis' integer count to bool

  RedisClientProvider:
    - missing redis.url → ValueError (fail-fast), before any redis import
    - builds the client via redis.asyncio.from_url with url + max_connections
    - pre_destroy() closes the client (aclose)

The `redis` package is not installed in the test env, so the success-path tests
inject a fake `redis.asyncio` module via sys.modules to drive the lazy import.
"""
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

from xime.core.config.runtime import RuntimeConfig
from xime.starters.cache import CacheService
from xime.starters.redis import RedisCacheService, RedisClientProvider


# ---------------------------------------------------------------------------
# Fakes / fixtures
# ---------------------------------------------------------------------------

class _FakeProvider:
    """Stand-in for RedisClientProvider exposing a mock async client."""

    def __init__(self) -> None:
        self.client = AsyncMock()


@pytest.fixture
def fake_redis_module(monkeypatch):
    """Inject a fake `redis` + `redis.asyncio` so the lazy import resolves.

    from_url is a MagicMock returning a client mock; tests can assert on the
    call and on the returned client.
    """
    client = MagicMock()
    client.aclose = AsyncMock()

    asyncio_mod = types.ModuleType("redis.asyncio")
    asyncio_mod.from_url = MagicMock(return_value=client)

    redis_mod = types.ModuleType("redis")
    redis_mod.asyncio = asyncio_mod

    monkeypatch.setitem(sys.modules, "redis", redis_mod)
    monkeypatch.setitem(sys.modules, "redis.asyncio", asyncio_mod)
    return asyncio_mod, client


# ---------------------------------------------------------------------------
# RedisCacheService - Protocol conformance
# ---------------------------------------------------------------------------

class TestRedisCacheServiceProtocol:
    def test_satisfies_cache_service_protocol(self):
        assert isinstance(RedisCacheService(_FakeProvider()), CacheService)


# ---------------------------------------------------------------------------
# RedisCacheService - command delegation
# ---------------------------------------------------------------------------

class TestRedisCacheServiceCommands:
    @pytest.mark.asyncio
    async def test_get_delegates_to_client_get(self):
        provider = _FakeProvider()
        provider.client.get.return_value = b"value"
        cache = RedisCacheService(provider)

        result = await cache.get("k")

        assert result == b"value"
        provider.client.get.assert_awaited_once_with("k")

    @pytest.mark.asyncio
    async def test_set_without_ttl_passes_ex_none(self):
        provider = _FakeProvider()
        cache = RedisCacheService(provider)

        await cache.set("k", b"v")

        provider.client.set.assert_awaited_once_with("k", b"v", ex=None)

    @pytest.mark.asyncio
    async def test_set_with_ttl_passes_ex_seconds(self):
        provider = _FakeProvider()
        cache = RedisCacheService(provider)

        await cache.set("k", b"v", ttl=30)

        provider.client.set.assert_awaited_once_with("k", b"v", ex=30)

    @pytest.mark.asyncio
    async def test_delete_delegates_to_client_delete(self):
        provider = _FakeProvider()
        cache = RedisCacheService(provider)

        await cache.delete("k")

        provider.client.delete.assert_awaited_once_with("k")

    @pytest.mark.asyncio
    async def test_exists_true_when_count_positive(self):
        provider = _FakeProvider()
        provider.client.exists.return_value = 1
        cache = RedisCacheService(provider)

        assert await cache.exists("k") is True
        provider.client.exists.assert_awaited_once_with("k")

    @pytest.mark.asyncio
    async def test_exists_false_when_count_zero(self):
        provider = _FakeProvider()
        provider.client.exists.return_value = 0
        cache = RedisCacheService(provider)

        assert await cache.exists("k") is False


# ---------------------------------------------------------------------------
# RedisClientProvider - fail-fast & lifecycle
# ---------------------------------------------------------------------------

class TestRedisClientProvider:
    def test_missing_url_raises_value_error(self):
        config = RuntimeConfig.from_dict({})
        with pytest.raises(ValueError, match="redis.url"):
            RedisClientProvider(config)

    def test_builds_client_with_url_and_max_connections(self, fake_redis_module):
        asyncio_mod, client = fake_redis_module
        config = RuntimeConfig.from_dict(
            {"redis": {"url": "redis://localhost:6379/0", "max_connections": 7}}
        )

        provider = RedisClientProvider(config)

        # `decode_responses=False` phải nằm trong lời gọi, không phải dựa vào
        # mặc định của redis-py: `CacheService.get()` hứa `bytes | None`, và bật
        # giải mã thì nó trả `str` - cùng chữ ký, hai kiểu, không lỗi nào phát
        # ra. Ghim ở đây để một lần "dọn cho gọn" không âm thầm mở lại.
        asyncio_mod.from_url.assert_called_once_with(
            "redis://localhost:6379/0", max_connections=7, decode_responses=False
        )
        assert provider.client is client

    def test_max_connections_defaults_to_10(self, fake_redis_module):
        asyncio_mod, _client = fake_redis_module
        config = RuntimeConfig.from_dict({"redis": {"url": "redis://localhost:6379/0"}})

        RedisClientProvider(config)

        asyncio_mod.from_url.assert_called_once_with(
            "redis://localhost:6379/0", max_connections=10, decode_responses=False
        )

    @pytest.mark.asyncio
    async def test_pre_destroy_closes_client(self, fake_redis_module):
        _asyncio_mod, client = fake_redis_module
        config = RuntimeConfig.from_dict({"redis": {"url": "redis://localhost:6379/0"}})

        provider = RedisClientProvider(config)
        await provider.pre_destroy()

        client.aclose.assert_awaited_once()
