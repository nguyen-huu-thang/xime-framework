from __future__ import annotations

import uuid

from xime.core.context import request_context
from xime.core.security import clear_security


class RequestContextMiddleware:
    """Pure-ASGI middleware: set up and teardown request-scoped context per HTTP request.

    Pure-ASGI middleware (KHÔNG dùng starlette BaseHTTPMiddleware) thiết lập và
    dọn dẹp context theo từng request HTTP.

    Why not BaseHTTPMiddleware: it runs the downstream app in a separate
    anyio task, so ContextVar set/clear here would NOT share the handler's
    context - security/identity could leak to a later request (dental-clinic
    #001). A pure ASGI middleware calls downstream in the SAME context, so set
    and clear are consistent and nothing bleeds.
    Vì sao không dùng BaseHTTPMiddleware: nó chạy app downstream trong task anyio
    riêng nên set/clear ContextVar ở đây không cùng context với handler -> identity
    có thể rò sang request sau (dental-clinic #001). Pure ASGI gọi downstream
    NGAY trong cùng context nên set/clear nhất quán, không rò.

    Startup:
      - assign a request_id (UUID) into request_context.

    Teardown (always runs, even when the handler raises):
      - request_context.clear()
      - clear_security() (identity, credentials, permissions...)
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        # Only manage context for HTTP requests; websocket/lifespan pass through
        # untouched (WebSocketHandler cleans up its own context).
        # Chỉ quản lý context cho request HTTP; websocket/lifespan đi thẳng qua
        # (WebSocketHandler tự dọn context của nó).
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_context.set("request_id", str(uuid.uuid4()))
        try:
            await self.app(scope, receive, send)
        finally:
            request_context.clear()
            clear_security()
