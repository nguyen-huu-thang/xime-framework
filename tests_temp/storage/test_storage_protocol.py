"""
Test the StorageService Protocol contract (0.5 - storage starter):

  - StorageService is runtime-checkable: a fake exposing every method satisfies
    isinstance(fake, StorageService).
  - A class missing a method does NOT satisfy the Protocol (fail-fast signal for
    binding validation, same as CacheService).
  - StorageStat is a frozen dataclass with optional fields defaulting to None.
"""
from collections.abc import AsyncIterator

from xime.starters.storage import StorageService, StorageStat


class _FakeStorage:
    """Minimal in-memory StorageService used to pin the interface shape."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def put(self, key, data, *, content_type=None):
        self._store[key] = data

    async def get(self, key):
        return self._store.get(key)

    async def put_stream(self, key, chunks, *, content_type=None):
        buf = bytearray()
        async for c in chunks:
            buf.extend(c)
        self._store[key] = bytes(buf)

    async def _iter(self, key):
        yield self._store[key]

    def open_stream(self, key, *, offset=0, length=None) -> AsyncIterator[bytes]:
        return self._iter(key)

    async def delete(self, key):
        self._store.pop(key, None)

    async def exists(self, key):
        return key in self._store

    async def stat(self, key):
        if key not in self._store:
            return None
        return StorageStat(size=len(self._store[key]))

    async def url(self, key, *, expires=None):
        return f"mem://{key}"


class _IncompleteStorage:
    async def get(self, key):
        return None


class TestStorageServiceProtocol:
    def test_complete_impl_satisfies_protocol(self):
        assert isinstance(_FakeStorage(), StorageService)

    def test_incomplete_impl_does_not_satisfy_protocol(self):
        assert not isinstance(_IncompleteStorage(), StorageService)


class TestStorageStat:
    def test_defaults_are_none(self):
        st = StorageStat()
        assert st.size is None
        assert st.content_type is None
        assert st.etag is None

    def test_is_frozen(self):
        st = StorageStat(size=10)
        try:
            st.size = 20  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("StorageStat must be frozen (immutable)")
