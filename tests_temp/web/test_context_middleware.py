"""Regression test cho H1 (dental-clinic #001): RequestContextMiddleware +
JwtAuthMiddleware là pure-ASGI nên context (request_id, security/identity) được
set/clear cùng context với handler -> không rò sang request sau.

Trước khi vá, hai middleware kế thừa BaseHTTPMiddleware (chạy downstream ở task
anyio riêng) nên việc clear không cùng context với nơi set -> identity có thể rò
giữa các request trên cùng worker.
"""
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from xime.adapters.web.middleware import RequestContextMiddleware
from xime.core.context import request_context
from xime.core.security.context import identity as _identity
from xime.core.security.session import authenticate
from xime.starters.jwt._config import JwtMiddlewareConfig
from xime.starters.jwt._key_context import KeyContext
from xime.starters.jwt._middleware import JwtAuthMiddleware

SECRET = "regression-secret-long-enough-for-hs256-32bytes"


# ---------------------------------------------------------------------------
# Unit: RequestContextMiddleware là pure-ASGI, set/clear cùng context với app
# ---------------------------------------------------------------------------

def _http_scope(path: str = "/") -> dict:
    return {
        "type": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "headers": [],
        "query_string": b"",
    }


async def _receive() -> dict:
    return {"type": "http.request", "body": b"", "more_body": False}


def _drain_send():
    async def send(_message: dict) -> None:
        return None
    return send


@pytest.mark.asyncio
async def test_request_id_visible_inside_app():
    seen: dict = {}

    async def app(scope, receive, send):
        seen["request_id"] = request_context.get("request_id")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    await RequestContextMiddleware(app)(_http_scope(), _receive, _drain_send())
    assert seen["request_id"]  # một request_id được set và nhìn thấy trong app


@pytest.mark.asyncio
async def test_security_cleared_in_caller_context_after_request():
    """App set identity (như JwtAuthMiddleware làm); middleware phải clear NGAY
    trong context của caller - điều chỉ pure-ASGI mới đảm bảo."""

    async def app(scope, receive, send):
        authenticate(identity="leaked-user")
        assert _identity.get() == "leaked-user"
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    await RequestContextMiddleware(app)(_http_scope(), _receive, _drain_send())
    # Sau request: identity + request_id đã bị dọn trong chính context này.
    assert _identity.get() is None
    assert request_context.get("request_id") is None


@pytest.mark.asyncio
async def test_teardown_runs_even_when_handler_raises():
    async def app(scope, receive, send):
        authenticate(identity="boom-user")
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await RequestContextMiddleware(app)(_http_scope(), _receive, _drain_send())
    assert _identity.get() is None
    assert request_context.get("request_id") is None


@pytest.mark.asyncio
async def test_non_http_scope_passes_through_without_context():
    called: dict = {}

    async def app(scope, receive, send):
        called["type"] = scope["type"]

    await RequestContextMiddleware(app)({"type": "websocket"}, _receive, _drain_send())
    assert called["type"] == "websocket"
    assert request_context.get("request_id") is None  # không set cho non-http


# ---------------------------------------------------------------------------
# Integration: stack RequestContext (ngoài) + JwtAuth (trong) như WebAdapter,
# kiểm tra identity KHÔNG rò sang request sau (đúng kịch bản dental-clinic #001)
# ---------------------------------------------------------------------------

def _token(sub: str) -> str:
    now = datetime.now(UTC)
    return pyjwt.encode(
        {"sub": sub, "iat": now, "exp": now + timedelta(minutes=30)},
        SECRET,
        algorithm="HS256",
    )


def _stacked_app() -> Starlette:
    async def handler(request: Request) -> JSONResponse:
        return JSONResponse({
            "identity": _identity.get(),
            "request_id": request_context.get("request_id"),
        })

    app = Starlette(routes=[
        Route("/protected", handler),
        Route("/public", handler),
    ])
    # Thứ tự giống WebAdapter.build_app: JwtAuth thêm trước (trong cùng),
    # RequestContext thêm sau (ngoài cùng -> chạy đầu, dọn cuối).
    app.add_middleware(
        JwtAuthMiddleware,
        config=JwtMiddlewareConfig(
            key_context=KeyContext(algorithm="HS256", secret=SECRET),
            public_paths=["/public"],
        ),
    )
    app.add_middleware(RequestContextMiddleware)
    return app


@pytest.mark.asyncio
async def test_identity_does_not_bleed_to_next_request():
    app = _stacked_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Request 1: có token -> identity = user_A.
        r1 = await client.get("/protected", headers={"Authorization": f"Bearer {_token('user_A')}"})
        # Request 2: public, KHÔNG token -> identity phải là None (không rò user_A).
        r2 = await client.get("/public")

    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["identity"] == "user_A"
    assert r2.json()["identity"] is None  # không rò identity của request trước

    # request_id được set cho mỗi request và khác nhau giữa các request.
    assert r1.json()["request_id"]
    assert r2.json()["request_id"]
    assert r1.json()["request_id"] != r2.json()["request_id"]


@pytest.mark.asyncio
async def test_missing_token_on_protected_still_401_under_stack():
    app = _stacked_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/protected")  # không token
    assert resp.status_code == 401
