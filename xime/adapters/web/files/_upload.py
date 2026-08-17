from __future__ import annotations

import mimetypes

from fastapi import UploadFile

from xime.starters.storage import StorageService

from ._errors import PayloadTooLarge

# Size of each chunk read from the UploadFile and forwarded to storage. 1 MiB
# keeps memory bounded while limiting the number of awaits for large files.
# Kích thước mỗi chunk đọc từ UploadFile - 1 MiB, giữ RAM ổn định.
_CHUNK_SIZE = 1024 * 1024

# Default cap. Unlimited by default meant one request could fill the disk (or
# the S3 invoice); an explicit `max_bytes=None` still opts out.
# Trần mặc định. Không giới hạn nghĩa là một request đủ làm đầy đĩa.
DEFAULT_MAX_BYTES = 32 * 1024 * 1024

# Neutral type stored when the file name says nothing. Not text/*, not
# anything a browser renders.
# Kiểu trung tính khi tên file không nói gì - không phải thứ trình duyệt render.
_NEUTRAL_TYPE = "application/octet-stream"


def _sniff_from_name(filename: str | None) -> str:
    """Guess a content type from the file NAME, never from the client's header."""
    if not filename:
        return _NEUTRAL_TYPE
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or _NEUTRAL_TYPE


async def save_upload(
    storage: StorageService,
    key: str,
    upload_file: UploadFile,
    *,
    max_bytes: int | None = DEFAULT_MAX_BYTES,
    content_type: str | None = None,
) -> int:
    """Stream a FastAPI UploadFile into storage chunk by chunk.

    Reads the upload in fixed-size chunks and forwards them to
    storage.put_stream() so the file is never fully buffered in memory. Enforces
    a size cap (32 MiB unless overridden): once the running total exceeds
    `max_bytes` the upload is rejected with PayloadTooLarge (HTTP 413) before the
    whole body is read. Pass `max_bytes=None` for no limit.
    Đọc UploadFile theo chunk -> put_stream, không nạp hết vào RAM; vượt
    max_bytes -> PayloadTooLarge (413) trước khi đọc hết body.

    The stored content type is derived from the FILE NAME, not from the
    multipart part's Content-Type header: that header is attacker-controlled, and
    an S3 backend hands it straight back on download, which is how an
    "avatar.png" declared as text/html turns into stored XSS. Pass
    `content_type=` explicitly when the caller genuinely knows better.
    Content type lưu lại suy từ TÊN FILE, không lấy header Content-Type của phần
    multipart: header đó do kẻ gọi điều khiển, và backend S3 trả lại y nguyên lúc
    tải về - đó chính là đường biến "avatar.png" khai text/html thành XSS lưu trữ.

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

    resolved_type = content_type or _sniff_from_name(upload_file.filename)
    await storage.put_stream(key, _chunks(), content_type=resolved_type)
    return written
