from __future__ import annotations

from fastapi import HTTPException


class PayloadTooLarge(HTTPException):
    """Raised when an upload exceeds the configured byte limit (HTTP 413).

    Subclasses FastAPI's HTTPException so the framework's existing exception
    handling turns it into a 413 response without extra wiring.
    Kế thừa HTTPException để framework tự trả 413 mà không cần nối thêm.
    """

    def __init__(self, max_bytes: int) -> None:
        super().__init__(
            status_code=413,
            detail=f"upload exceeds the maximum allowed size of {max_bytes} bytes",
        )
        self.max_bytes = max_bytes
