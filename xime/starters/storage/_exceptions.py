from __future__ import annotations


class StorageError(Exception):
    """Base class for every error raised by a StorageService backend.

    Backends raise subclasses of this; callers can catch StorageError to handle
    any storage failure uniformly, or catch a specific subclass.
    Lớp gốc cho mọi lỗi của backend StorageService. Caller bắt StorageError để
    xử lý chung, hoặc bắt subclass cụ thể.
    """


class ObjectNotFound(StorageError):
    """Raised when a key does not exist for an operation that requires it.

    `get`/`open_stream`/`stat` return None for an absent key instead of raising;
    this is reserved for operations where absence is an actual error (the backend
    decides). Kept distinct so callers can map it to a 404 if they wish.
    Dùng khi key không tồn tại cho thao tác bắt buộc phải có. get/open_stream/stat
    trả None khi thiếu key thay vì raise.
    """

    def __init__(self, key: str) -> None:
        super().__init__(f"object not found: {key!r}")
        self.key = key


class UnsupportedOperation(StorageError):
    """Raised when a backend cannot perform a requested operation.

    Example: the local filesystem backend has no notion of a presigned URL, so
    `LocalFileStorage.url()` raises this rather than returning a fake value.
    Dùng khi backend không hỗ trợ thao tác (vd local không có presigned URL).
    """
