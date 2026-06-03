from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from xime.core.context import request_context
from xime.core.security import clear_security


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Set up và teardown request-scoped context cho mỗi HTTP request.

    Startup:
      - Gán request_id UUID vào request_context

    Teardown (luôn chạy, kể cả khi handler throw exception):
      - Xóa toàn bộ request_context
      - Xóa toàn bộ security context (identity, credentials, permissions...)
        để tránh data bleeding giữa các request trên cùng worker
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_context.set("request_id", str(uuid.uuid4()))
        try:
            return await call_next(request)
        finally:
            request_context.clear()
            clear_security()
