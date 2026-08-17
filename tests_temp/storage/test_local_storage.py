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


# ---------------------------------------------------------------------------
# F13 - tên file tạm, quyền, và put() nguyên tử
# ---------------------------------------------------------------------------

class TestLocalStorageHardening:
    @pytest.mark.asyncio
    async def test_concurrent_writes_to_same_key_do_not_share_a_temp_file(self, tmp_path):
        """PID dùng chung cho cả tiến trình: hai upload cùng key từng ghi chung
        MỘT file tạm rồi công bố kết quả lai. Đây là lỗi toàn vẹn dữ liệu."""
        import asyncio

        storage = _storage(tmp_path)

        async def slow_chunks(marker: bytes):
            for _ in range(4):
                await asyncio.sleep(0)
                yield marker * 1000

        await asyncio.gather(
            storage.put_stream("same.bin", slow_chunks(b"A")),
            storage.put_stream("same.bin", slow_chunks(b"B")),
        )

        data = await storage.get("same.bin")
        # Kết quả phải là của MỘT trong hai lần ghi, không phải hỗn hợp.
        assert data in (b"A" * 4000, b"B" * 4000)

    # -- Công bố file: retry va chạm tạm thời, NHƯNG không nuốt lỗi vĩnh viễn --
    # Phải test CẶP: chỉ có test đầu thì cách sửa sai "nuốt mọi PermissionError"
    # cũng qua được, mà thế là hỏng ngược chiều.
    #
    # Bối cảnh: trên Windows, MoveFileEx báo ERROR_ACCESS_DENIED khi file ĐÍCH
    # đang được ai đó mở - kể cả khoảng rất ngắn mà một lần publish đồng thời
    # cùng key đang giữ nó. Đo được ~10% lần chạy đỏ trước bản vá.
    # Monkeypatch chứ không dựa vào hành vi thật của OS, để test xác định trên
    # mọi nền tảng (POSIX rename(2) không bao giờ tái hiện được ca này).

    @pytest.mark.asyncio
    async def test_publish_retries_a_transient_permission_error(self, tmp_path, monkeypatch):
        storage = _storage(tmp_path)
        real_replace = os.replace
        calls = {"n": 0}

        def flaky(src, dst):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise PermissionError(5, "Access is denied")
            return real_replace(src, dst)

        monkeypatch.setattr(os, "replace", flaky)
        await storage.put("k.bin", b"payload")

        assert await storage.get("k.bin") == b"payload"
        assert calls["n"] == 3  # hai lần hỏng rồi thành công

    @pytest.mark.asyncio
    async def test_publish_gives_up_and_raises_on_permanent_error(self, tmp_path, monkeypatch):
        """Nguyên nhân vĩnh viễn (đích read-only, hoặc có người giữ file mở lâu)
        phải LỘ RA, không được biến mất sau vài lần thử."""
        storage = _storage(tmp_path)
        calls = {"n": 0}

        def always_denied(src, dst):
            calls["n"] += 1
            raise PermissionError(5, "Access is denied")

        monkeypatch.setattr(os, "replace", always_denied)
        with pytest.raises(PermissionError):
            await storage.put("k.bin", b"payload")

        assert calls["n"] <= 6  # có giới hạn, không thử mãi

    @pytest.mark.asyncio
    async def test_put_is_atomic_like_put_stream(self, tmp_path):
        storage = _storage(tmp_path)
        await storage.put("doc.bin", b"payload")
        assert await storage.get("doc.bin") == b"payload"
        leftovers = [p for p in os.listdir(tmp_path) if p.endswith(".part")]
        assert leftovers == []

    @pytest.mark.asyncio
    @pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits only")
    async def test_written_file_is_owner_only_by_default(self, tmp_path):
        import stat

        storage = _storage(tmp_path)
        await storage.put("secret.bin", b"x")
        mode = stat.S_IMODE((tmp_path / "secret.bin").stat().st_mode)
        assert mode == 0o600

    @pytest.mark.asyncio
    @pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits only")
    async def test_file_mode_configurable_as_octal_string(self, tmp_path):
        import stat

        storage = LocalFileStorage(
            RuntimeConfig.from_dict(
                {"storage": {"local": {"root": str(tmp_path), "file_mode": "0640"}}}
            )
        )
        await storage.put("shared.bin", b"x")
        mode = stat.S_IMODE((tmp_path / "shared.bin").stat().st_mode)
        assert mode == 0o640

    def test_unquoted_yaml_mode_is_read_as_decimal_int(self, tmp_path):
        # Không phải hành vi mong muốn nhưng phải xác định: số nguyên giữ nguyên,
        # chuỗi mới đọc theo bát phân. Ghi lại để người sau không đoán.
        from xime.starters.localfs._storage import _parse_mode

        assert _parse_mode("0600", 0) == 0o600
        assert _parse_mode(0o600, 0) == 0o600
        assert _parse_mode(None, 0o600) == 0o600
