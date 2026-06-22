from __future__ import annotations

from pathlib import PurePosixPath

from ._exceptions import StorageError


def validate_object_key(key: str) -> str:
    """Validate a storage key so every backend treats keys identically.

    Rejects empty, absolute, and traversal (`..`) keys. Local and S3 backends
    both apply this, so switching backend never changes which keys are accepted
    (the local backend additionally resolves symlinks against its root).
    Chuẩn hóa key chung cho mọi backend: từ chối rỗng/tuyệt đối/`..`. Local và S3
    đều áp dụng nên đổi backend không đổi tập key hợp lệ.

    Returns the key unchanged when valid; raises StorageError otherwise.
    """
    if not key:
        raise StorageError("storage key must not be empty")
    pure = PurePosixPath(key)
    if pure.is_absolute():
        raise StorageError(f"storage key must be relative, got {key!r}")
    if any(part == ".." for part in pure.parts):
        raise StorageError(f"storage key must not contain '..': {key!r}")
    return key
