from __future__ import annotations

import asyncio
import os
import stat as stat_module
from collections.abc import AsyncIterator
from pathlib import Path, PurePosixPath

from xime.core.config.runtime import RuntimeConfig
from xime.starters.storage import (
    ObjectNotFound,
    StorageError,
    StorageStat,
    UnsupportedOperation,
)
from xime.starters.storage._keys import validate_object_key

# Chunk size for streaming reads/writes. 64 KiB balances syscall count against
# memory per in-flight chunk; matches a common default for file streaming.
# Kích thước chunk khi stream đọc/ghi - 64 KiB.
_CHUNK_SIZE = 64 * 1024


class LocalFileStorage:
    """StorageService backend that stores objects as files under a root directory.

    Reads its root from RuntimeConfig (application.yml):

        storage:
          local:
            root: /var/lib/xime/objects

    Keys are backend-relative POSIX-style paths ("avatars/u123.png"). Every key
    is resolved against the root and rejected if it would escape it (path
    traversal), so a malicious key like "../../etc/passwd" never touches a file
    outside `root`.
    Key là path tương đối kiểu POSIX, luôn được ghép trong root và từ chối nếu
    thoát ra ngoài (chống path traversal).

    Filesystem IO is blocking, so every syscall runs in a worker thread via
    asyncio.to_thread to avoid stalling the event loop. No extra dependency
    (aiofiles) is required.
    IO file là blocking nên mọi syscall chạy trong thread qua asyncio.to_thread.

    Register and bind in config/dependency.py:
        dependency.scan("xime.starters.localfs")
        dependency.bind({ StorageService: LocalFileStorage })
    RuntimeConfig is injected automatically by the framework.

    The local backend has no notion of a content type or a presigned URL: stat()
    reports size only, and url() raises UnsupportedOperation.
    """

    def __init__(self, config: RuntimeConfig) -> None:
        root: str = config.get("storage.local.root") or ""
        if not root:
            raise ValueError(
                "storage.local.root is not configured. "
                "Add 'storage.local.root' to resources/application.yml."
            )
        # Resolve once at startup so every key is checked against a canonical
        # root (symlinks/.. already collapsed).
        # Phân giải root một lần lúc startup để mọi key kiểm tra trên root chuẩn.
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Key resolution (path-traversal guard)
    # ------------------------------------------------------------------

    def _resolve(self, key: str) -> Path:
        """Map a backend-relative key to an absolute path inside the root.

        Rejects absolute keys and any key that, once normalised, would escape
        the root directory.
        Từ chối key tuyệt đối hoặc key thoát khỏi root sau khi chuẩn hóa.
        """
        # Shared key contract (empty / absolute / '..') - identical across backends.
        # Hợp đồng key dùng chung (rỗng/tuyệt đối/'..') - giống nhau mọi backend.
        validate_object_key(key)
        pure = PurePosixPath(key)

        candidate = (self._root / Path(*pure.parts)).resolve()
        # Final defence: the resolved path must stay within root even if a
        # symlink in the tree points elsewhere.
        # Phòng tuyến cuối: path sau resolve phải vẫn nằm trong root.
        if candidate != self._root and self._root not in candidate.parents:
            raise StorageError(f"storage key escapes the storage root: {key!r}")
        return candidate

    # ------------------------------------------------------------------
    # Whole-object access
    # ------------------------------------------------------------------

    async def put(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> None:
        path = self._resolve(key)
        await asyncio.to_thread(self._write_bytes, path, data)

    async def get(self, key: str) -> bytes | None:
        path = self._resolve(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError:
            return None
        except IsADirectoryError:
            return None

    # ------------------------------------------------------------------
    # Streaming access
    # ------------------------------------------------------------------

    async def put_stream(
        self,
        key: str,
        chunks: AsyncIterator[bytes],
        *,
        content_type: str | None = None,
    ) -> None:
        """Write a stream atomically: stage to a .part file, then os.replace.

        os.replace is atomic on the same filesystem, so a reader never sees a
        partially-written object under `key`. A failure mid-stream leaves only
        the temp file, which is cleaned up.
        Ghi nguyên tử: ghi ra file tạm .part rồi os.replace.
        """
        path = self._resolve(key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.part")

        def _open() -> object:
            return open(tmp, "wb")

        handle = await asyncio.to_thread(_open)
        try:
            async for chunk in chunks:
                await asyncio.to_thread(handle.write, chunk)  # type: ignore[attr-defined]
            await asyncio.to_thread(handle.flush)  # type: ignore[attr-defined]
            await asyncio.to_thread(os.fsync, handle.fileno())  # type: ignore[attr-defined]
        except BaseException:
            await asyncio.to_thread(handle.close)  # type: ignore[attr-defined]
            await asyncio.to_thread(self._unlink_quiet, tmp)
            raise
        else:
            await asyncio.to_thread(handle.close)  # type: ignore[attr-defined]
            await asyncio.to_thread(os.replace, tmp, path)

    def open_stream(
        self, key: str, *, offset: int = 0, length: int | None = None
    ) -> AsyncIterator[bytes]:
        # Resolve eagerly so an invalid key fails immediately, not on first
        # iteration. The generator below performs the actual (blocking) IO.
        # Phân giải key ngay để key sai báo lỗi sớm, không đợi vòng lặp đầu.
        if offset < 0:
            raise StorageError("offset must be >= 0")
        if length is not None and length < 0:
            raise StorageError("length must be >= 0")
        path = self._resolve(key)
        return self._iter_file(path, offset, length)

    async def _iter_file(
        self, path: Path, offset: int, length: int | None
    ) -> AsyncIterator[bytes]:
        def _open() -> object:
            return open(path, "rb")

        try:
            handle = await asyncio.to_thread(_open)
        except FileNotFoundError:
            raise ObjectNotFound(str(path)) from None
        except IsADirectoryError:
            raise ObjectNotFound(str(path)) from None

        try:
            if offset:
                await asyncio.to_thread(handle.seek, offset)  # type: ignore[attr-defined]
            remaining = length
            while True:
                to_read = _CHUNK_SIZE if remaining is None else min(_CHUNK_SIZE, remaining)
                if to_read <= 0:
                    break
                chunk = await asyncio.to_thread(handle.read, to_read)  # type: ignore[attr-defined]
                if not chunk:
                    break
                if remaining is not None:
                    remaining -= len(chunk)
                yield chunk
        finally:
            await asyncio.to_thread(handle.close)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Metadata / lifecycle of an object
    # ------------------------------------------------------------------

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        await asyncio.to_thread(self._unlink_quiet, path)

    async def exists(self, key: str) -> bool:
        path = self._resolve(key)
        return await asyncio.to_thread(path.is_file)

    async def stat(self, key: str) -> StorageStat | None:
        path = self._resolve(key)
        try:
            st = await asyncio.to_thread(path.stat)
        except FileNotFoundError:
            return None
        if not stat_module.S_ISREG(st.st_mode):
            return None
        # etag: cheap, stable-per-version identifier from size + mtime_ns.
        # etag: định danh theo phiên bản, rẻ, từ size + mtime_ns.
        etag = f"{st.st_size:x}-{st.st_mtime_ns:x}"
        return StorageStat(size=st.st_size, content_type=None, etag=etag)

    async def url(self, key: str, *, expires: int | None = None) -> str:
        raise UnsupportedOperation(
            "LocalFileStorage has no presigned URL; serve files via the web "
            "adapter's stream_object() helper instead."
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _write_bytes(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    @staticmethod
    def _unlink_quiet(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except IsADirectoryError:
            pass
