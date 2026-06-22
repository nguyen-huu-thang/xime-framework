"""
Test LocalFileStorage (0.5 - localfs starter), the filesystem StorageService:

  Construction:
    - missing storage.local.root → ValueError (fail-fast)
    - root directory is created if absent
  Round-trip:
    - put/get, exists, delete (idempotent), stat (size + etag)
    - put_stream + open_stream full, and Range via offset/length
    - open_stream on a missing key raises ObjectNotFound on first iteration
    - put_stream is atomic: no leftover .part file after success
  Safety:
    - path traversal (.., absolute, empty) is rejected with StorageError
    - url() raises UnsupportedOperation (no presigned URL for local)
  Protocol:
    - LocalFileStorage satisfies the StorageService Protocol
"""
import os

import pytest

from xime.core.config.runtime import RuntimeConfig
from xime.starters.localfs import LocalFileStorage
from xime.starters.storage import (
    ObjectNotFound,
    StorageError,
    StorageService,
    UnsupportedOperation,
)


def _storage(root) -> LocalFileStorage:
    return LocalFileStorage(RuntimeConfig.from_dict({"storage": {"local": {"root": str(root)}}}))


async def _agen(*parts):
    for p in parts:
        yield p


class TestConstruction:
    def test_missing_root_raises(self):
        with pytest.raises(ValueError, match="storage.local.root"):
            LocalFileStorage(RuntimeConfig.from_dict({}))

    def test_creates_root_dir(self, tmp_path):
        root = tmp_path / "objects"
        assert not root.exists()
        _storage(root)
        assert root.is_dir()

    def test_satisfies_protocol(self, tmp_path):
        assert isinstance(_storage(tmp_path), StorageService)


class TestRoundTrip:
    @pytest.mark.asyncio
    async def test_put_get(self, tmp_path):
        st = _storage(tmp_path)
        await st.put("a/b.txt", b"hello")
        assert await st.get("a/b.txt") == b"hello"

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, tmp_path):
        st = _storage(tmp_path)
        assert await st.get("nope") is None

    @pytest.mark.asyncio
    async def test_exists(self, tmp_path):
        st = _storage(tmp_path)
        assert await st.exists("k") is False
        await st.put("k", b"v")
        assert await st.exists("k") is True

    @pytest.mark.asyncio
    async def test_delete_is_idempotent(self, tmp_path):
        st = _storage(tmp_path)
        await st.put("k", b"v")
        await st.delete("k")
        await st.delete("k")  # must not raise
        assert await st.exists("k") is False

    @pytest.mark.asyncio
    async def test_stat(self, tmp_path):
        st = _storage(tmp_path)
        await st.put("k", b"12345")
        stat = await st.stat("k")
        assert stat is not None and stat.size == 5 and stat.etag
        assert await st.stat("missing") is None

    @pytest.mark.asyncio
    async def test_stat_on_directory_returns_none(self, tmp_path):
        st = _storage(tmp_path)
        await st.put("dir/inner.txt", b"x")  # creates 'dir' directory
        assert await st.stat("dir") is None

    @pytest.mark.asyncio
    async def test_put_stream_then_full_read(self, tmp_path):
        st = _storage(tmp_path)
        await st.put_stream("big.bin", _agen(b"AAAA", b"BBBB", b"CCCC"))
        chunks = [c async for c in st.open_stream("big.bin")]
        assert b"".join(chunks) == b"AAAABBBBCCCC"

    @pytest.mark.asyncio
    async def test_open_stream_range(self, tmp_path):
        st = _storage(tmp_path)
        await st.put("k", b"0123456789")
        out = b"".join([c async for c in st.open_stream("k", offset=4, length=3)])
        assert out == b"456"

    @pytest.mark.asyncio
    async def test_open_stream_missing_raises(self, tmp_path):
        st = _storage(tmp_path)
        with pytest.raises(ObjectNotFound):
            [c async for c in st.open_stream("nope")]

    @pytest.mark.asyncio
    async def test_put_stream_leaves_no_part_file(self, tmp_path):
        st = _storage(tmp_path)
        await st.put_stream("clean.bin", _agen(b"data"))
        leftovers = [p for p in os.listdir(tmp_path) if p.endswith(".part")]
        assert leftovers == []


class TestSafety:
    @pytest.mark.asyncio
    async def test_traversal_rejected(self, tmp_path):
        st = _storage(tmp_path)
        for bad in ["../escape", "x/../../y", ""]:
            with pytest.raises(StorageError):
                st._resolve(bad)

    @pytest.mark.asyncio
    async def test_absolute_key_rejected(self, tmp_path):
        st = _storage(tmp_path)
        with pytest.raises(StorageError):
            st._resolve("/etc/passwd")

    @pytest.mark.asyncio
    async def test_url_unsupported(self, tmp_path):
        st = _storage(tmp_path)
        with pytest.raises(UnsupportedOperation):
            await st.url("k")
