from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

from xime.starters.storage import StorageService

# Fallback media type when neither the caller nor stat() knows the content type.
# Media type dự phòng khi không xác định được.
_DEFAULT_MEDIA_TYPE = "application/octet-stream"


@dataclass(frozen=True, slots=True)
class _Range:
    """A resolved byte range: start (inclusive) and length in bytes."""

    offset: int
    length: int


def _parse_range(header: str, total: int) -> _Range | None:
    """Parse a single HTTP Range header against a known total size.

    Supports the three common single-range forms. Returns None when the header
    is absent of a real byte range, multi-range, or syntactically malformed
    (per RFC 7233 a malformed Range is IGNORED -> caller serves the full 200).
    Raises ValueError only for a syntactically-valid but UNSATISFIABLE range so
    the caller can emit 416.
    Hỗ trợ ba dạng range đơn. Trả None khi header sai cú pháp/đa range (RFC 7233:
    bỏ qua -> phục vụ full 200). Chỉ raise ValueError khi range hợp lệ cú pháp
    nhưng KHÔNG thoả mãn (caller trả 416).
    """
    header = header.strip()
    if not header.startswith("bytes=") or "," in header:
        return None  # not a byte range, or multi-range — serve full
    spec = header[len("bytes="):].strip()
    start_s, sep, end_s = spec.partition("-")
    if sep == "":
        return None  # no '-' separator — malformed, ignore

    if start_s == "":
        # suffix form: bytes=-N  -> last N bytes
        if end_s == "":
            return None
        try:
            suffix = int(end_s)
        except ValueError:
            return None  # non-numeric — malformed, ignore (serve full 200)
        if suffix <= 0:
            raise ValueError("unsatisfiable")
        length = min(suffix, total)
        return _Range(offset=total - length, length=length)

    try:
        start = int(start_s)
    except ValueError:
        return None  # non-numeric — malformed, ignore
    if start >= total:
        raise ValueError("unsatisfiable")
    if end_s == "":
        # bytes=start-  -> start to end of object
        return _Range(offset=start, length=total - start)
    try:
        end = int(end_s)
    except ValueError:
        return None  # non-numeric end — malformed, ignore
    if end < start:
        return None
    end = min(end, total - 1)  # clamp to the last byte
    return _Range(offset=start, length=end - start + 1)


async def stream_object(
    storage: StorageService,
    key: str,
    *,
    request: Request | None = None,
    filename: str | None = None,
    content_type: str | None = None,
    download: bool = False,
) -> StreamingResponse:
    """Stream a stored object as an HTTP response, honouring Range requests.

    Looks up object metadata via storage.stat(); a missing object yields a 404.
    When `request` carries a satisfiable Range header and the size is known, the
    response is 206 Partial Content with Content-Range; otherwise it is a full
    200 stream. Bytes are read lazily from storage.open_stream() so large objects
    never load fully into memory.
    Stream object qua HTTP, tôn trọng Range; thiếu object -> 404; có Range hợp lệ
    -> 206, ngược lại 200 full. Đọc lười từ open_stream, không nạp hết vào RAM.

    Args:
        download: when True, set Content-Disposition: attachment (force download)
                  instead of inline.
    """
    stat = await storage.stat(key)
    if stat is None:
        raise HTTPException(status_code=404, detail=f"object not found: {key!r}")

    media_type = content_type or stat.content_type or _DEFAULT_MEDIA_TYPE
    total = stat.size

    headers: dict[str, str] = {"Accept-Ranges": "bytes"}
    if filename is not None:
        disposition = "attachment" if download else "inline"
        headers["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    if stat.etag:
        headers["ETag"] = f'"{stat.etag}"'

    range_header = request.headers.get("range") if request is not None else None
    rng: _Range | None = None
    if range_header and total is not None:
        try:
            rng = _parse_range(range_header, total)
        except ValueError:
            # Unsatisfiable range — RFC 7233 requires 416 + Content-Range */total.
            # Range không thoả mãn -> 416 kèm Content-Range */total.
            raise HTTPException(
                status_code=416,
                detail="requested range not satisfiable",
                headers={"Content-Range": f"bytes */{total}"},
            ) from None

    if rng is not None:
        headers["Content-Range"] = (
            f"bytes {rng.offset}-{rng.offset + rng.length - 1}/{total}"
        )
        headers["Content-Length"] = str(rng.length)
        body = storage.open_stream(key, offset=rng.offset, length=rng.length)
        status_code = 206
    else:
        if total is not None:
            headers["Content-Length"] = str(total)
        body = storage.open_stream(key)
        status_code = 200

    return StreamingResponse(
        body, status_code=status_code, media_type=media_type, headers=headers
    )
