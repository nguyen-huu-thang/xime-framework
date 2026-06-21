"""
Test the CacheService Protocol contract (0.4 - cache starter):

  - CacheService is runtime-checkable: a fake with the four async methods
    satisfies isinstance(fake, CacheService).
  - A class missing a method does NOT satisfy the Protocol (fail-fast signal
    for binding validation).
  - Round-trip semantics of a reference in-memory implementation:
    get/set/delete/exists, TTL=None persists, missing key → None/False.
"""
import pytest

from xime.starters.cache import CacheService


class _FakeCache:
    """Minimal in-memory CacheService used to pin the interface shape.

    TTL is accepted but not enforced (no clock) — the cache starter only defines
    the contract; real expiry is the backend's job (tested in the redis suite).
    """

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self._store.get(key)

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._store


class _IncompleteCache:
    async def get(self, key: str) -> bytes | None:
        return None


class TestCacheServiceProtocol:
    def test_complete_impl_satisfies_protocol(self):
        assert isinstance(_FakeCache(), CacheService)

    def test_incomplete_impl_does_not_satisfy_protocol(self):
        assert not isinstance(_IncompleteCache(), CacheService)


class TestFakeCacheRoundTrip:
    @pytest.mark.asyncio
    async def test_set_then_get_returns_value(self):
        cache = _FakeCache()
        await cache.set("k", b"v")
        assert await cache.get("k") == b"v"

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self):
        cache = _FakeCache()
        assert await cache.get("absent") is None

    @pytest.mark.asyncio
    async def test_exists_reflects_presence(self):
        cache = _FakeCache()
        assert await cache.exists("k") is False
        await cache.set("k", b"v")
        assert await cache.exists("k") is True

    @pytest.mark.asyncio
    async def test_delete_removes_key(self):
        cache = _FakeCache()
        await cache.set("k", b"v")
        await cache.delete("k")
        assert await cache.get("k") is None
        assert await cache.exists("k") is False

    @pytest.mark.asyncio
    async def test_delete_missing_is_noop(self):
        cache = _FakeCache()
        await cache.delete("absent")  # must not raise

    @pytest.mark.asyncio
    async def test_set_with_ttl_none_persists(self):
        cache = _FakeCache()
        await cache.set("k", b"v", ttl=None)
        assert await cache.get("k") == b"v"
