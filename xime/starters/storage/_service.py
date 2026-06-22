from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class StorageStat:
    """Metadata about a stored object, returned by StorageService.stat().

    Fields that a backend cannot determine are left as None — callers must treat
    them as optional. `size` is in bytes; `etag` is whatever the backend uses to
    identify a version (S3 ETag, file mtime+size hash, ...), opaque to callers.
    Metadata của object. Backend không xác định được trường nào thì để None.
    """

    size: int | None = None
    content_type: str | None = None
    etag: str | None = None


@runtime_checkable
class StorageService(Protocol):
    """
    Backend-neutral contract for an object/blob store.

    Define this once; bind a concrete backend in config/dependency.py, e.g.

        dependency.bind({ StorageService: LocalFileStorage })   # or S3FileStorage

    and inject StorageService wherever file storage is needed:

        class AvatarService:
            def __init__(self, storage: StorageService) -> None:
                self._storage = storage

    The framework only provides the mechanism: objects are raw bytes (or raw
    byte streams). It imposes no policy on naming, authorization, content type
    sniffing or encoding — that is the application's job. This keeps the contract
    small and every backend interchangeable.
    Framework chỉ cấp cơ chế: object là bytes thô (hoặc stream bytes thô). Không
    áp đặt chính sách đặt tên/authorization/định dạng - đó là việc của app.

    Two access shapes, by design (chốt 2026-06-22):
      - put/get        : whole-object bytes, convenient for small objects.
      - put_stream /   : async byte streams, for large objects that must not be
        open_stream      buffered fully in memory.

    `key` is a backend-relative identifier (e.g. "avatars/u123.png"). EVERY
    backend rejects empty, absolute, and traversal (`..`) keys identically (see
    storage._keys.validate_object_key), so switching backend never changes which
    keys are accepted; the local backend additionally guards against symlinks
    escaping its root.
    `key` là định danh tương đối; MỌI backend đều từ chối key rỗng/tuyệt đối/`..`
    như nhau -> đổi backend không đổi tập key hợp lệ.
    """

    async def put(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> None:
        """Store `data` under `key`, overwriting any existing object.

        `content_type` is metadata the backend may persist (S3) or ignore
        (filesystem). For large payloads prefer put_stream to avoid buffering.
        """
        ...

    async def get(self, key: str) -> bytes | None:
        """Return the whole object as bytes, or None if the key is absent.

        Loads the entire object into memory — use open_stream for large objects.
        """
        ...

    async def put_stream(
        self,
        key: str,
        chunks: AsyncIterator[bytes],
        *,
        content_type: str | None = None,
    ) -> None:
        """Store an object by consuming an async stream of byte chunks.

        The backend writes incrementally without buffering the whole object in
        memory. Implementations should write atomically where possible so a
        failure mid-stream does not leave a partial object visible under `key`.
        Ghi theo stream, không buffer toàn bộ; nên ghi nguyên tử (atomic).
        """
        ...

    def open_stream(
        self, key: str, *, offset: int = 0, length: int | None = None
    ) -> AsyncIterator[bytes]:
        """Return an async iterator yielding the object's bytes in chunks.

        `offset`/`length` select a byte range (used by HTTP Range downloads):
        start at `offset`, yield at most `length` bytes (None = to the end).
        Returns an empty iterator semantics are backend-defined for an absent
        key; backends should raise ObjectNotFound on first iteration instead of
        silently yielding nothing.
        Trả iterator các chunk bytes; offset/length chọn dải byte cho HTTP Range.

        Note: this is NOT `async def` — it returns an async iterator directly so
        callers write `async for chunk in storage.open_stream(key): ...`.
        """
        ...

    async def delete(self, key: str) -> None:
        """Remove the object under `key`. A no-op if the key does not exist."""
        ...

    async def exists(self, key: str) -> bool:
        """Return True if an object is stored under `key`."""
        ...

    async def stat(self, key: str) -> StorageStat | None:
        """Return metadata for `key`, or None if the key is absent."""
        ...

    async def url(self, key: str, *, expires: int | None = None) -> str:
        """Return a directly-accessible URL for `key` (e.g. an S3 presigned URL).

        `expires` is the validity window in seconds (None = backend default).
        Backends without a URL concept (e.g. local filesystem) raise
        UnsupportedOperation rather than returning a fake value.
        Backend không có khái niệm URL (vd local) raise UnsupportedOperation.
        """
        ...
