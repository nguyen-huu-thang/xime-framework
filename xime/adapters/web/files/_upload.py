from __future__ import annotations

from fastapi import UploadFile

from xime.starters.storage import StorageService

from ._errors import PayloadTooLarge

# Size of each chunk read from the UploadFile and forwarded to storage. 1 MiB
# keeps memory bounded while limiting the number of awaits for large files.
# Kích thước mỗi chunk đọc từ UploadFile - 1 MiB, giữ RAM ổn định.
_CHUNK_SIZE = 1024 * 1024


async def save_upload(
    storage: StorageService,
    key: str,
    upload_file: UploadFile,
    *,
    max_bytes: int | None = None,
    content_type: str | None = None,
) -> int:
    """Stream a FastAPI UploadFile into storage chunk by chunk.

    Reads the upload in fixed-size chunks and forwards them to
    storage.put_stream() so the file is never fully buffered in memory. Enforces
    an optional size cap: once the running total exceeds `max_bytes` the upload
    is rejected with PayloadTooLarge (HTTP 413) before the whole body is read.
    Đọc UploadFile theo chunk -> put_stream, không nạp hết vào RAM; vượt
    max_bytes -> PayloadTooLarge (413) trước khi đọc hết body.

    Returns the number of bytes written.
    """
    written = 0

    async def _chunks():
        nonlocal written
        while True:
            chunk = await upload_file.read(_CHUNK_SIZE)
            if not chunk:
                break
            written += len(chunk)
            if max_bytes is not None and written > max_bytes:
                raise PayloadTooLarge(max_bytes)
            yield chunk

    resolved_type = content_type or upload_file.content_type
    await storage.put_stream(key, _chunks(), content_type=resolved_type)
    return written
