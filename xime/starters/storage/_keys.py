from __future__ import annotations

from pathlib import PurePosixPath

from ._exceptions import StorageError


def validate_object_key(key: str) -> str:
    """Validate a storage key so every backend treats keys identically.

    Rejects empty, absolute, traversal (`..`), backslash and NUL keys. Local and
    S3 backends both apply this, so switching backend never changes which keys
    are accepted (the local backend additionally resolves symlinks against its
    root).
    Chuẩn hóa key chung cho mọi backend: từ chối rỗng/tuyệt đối/`..`/gạch
    ngược/NUL. Local và S3 đều áp dụng nên đổi backend không đổi tập key
    hợp lệ.

    Returns the key unchanged when valid; raises StorageError otherwise.
    """
    if not key:
        raise StorageError("storage key must not be empty")
    pure = PurePosixPath(key)
    if pure.is_absolute():
        raise StorageError(f"storage key must be relative, got {key!r}")
    if any(part == ".." for part in pure.parts):
        raise StorageError(f"storage key must not contain '..': {key!r}")
    # `PurePosixPath` treats `\` as an ordinary character, so a Windows-style
    # key slips through every check above. It then means three different things:
    # traversal on a Windows local root, a literal filename on a POSIX root, and
    # a literal key on S3. Reject it so the promise above stays true.
    # `PurePosixPath` coi `\` là ký tự thường nên key kiểu Windows lọt hết các
    # phép kiểm trên, rồi mang BA nghĩa khác nhau tùy backend và hệ điều hành.
    if "\\" in key:
        raise StorageError(f"storage key must not contain a backslash: {key!r}")
    # NUL survives `Path.exists()` (returns False) but blows up inside `open()`
    # with a bare ValueError, so callers see a wrong answer or the wrong
    # exception type instead of StorageError.
    # NUL đi lọt `Path.exists()` (trả False) rồi nổ trong `open()` bằng
    # `ValueError` trần - bên gọi nhận câu trả lời sai hoặc sai kiểu ngoại lệ.
    if "\x00" in key:
        raise StorageError(f"storage key must not contain a NUL byte: {key!r}")
    return key
