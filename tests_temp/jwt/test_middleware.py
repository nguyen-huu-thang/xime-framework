"""
Test JwtAuthMiddleware (HTTP flow):
  - request đến public path → 200, không cần Authorization
  - public path không set identity trong SecurityContext
  - thiếu Authorization header → 401
  - Authorization không có "Bearer " prefix → 401
  - "Bearer " nhưng token rỗng → 401
  - token hợp lệ → 200, identity được set trong SecurityContext
  - credential_type = TOKEN sau khi auth thành công
  - token hết hạn → 401, message chứa "expired"
  - chữ ký sai (secret khác) → 401, message chứa "Invalid token"
  - token bị cắt/sai format → 401
  - token thiếu identity_claim → 401, message chứa tên claim
  - identity_claim tùy chỉnh được map đúng vào SecurityContext
"""
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from xime.core.security.context import credential_type as _credential_type
from xime.core.security.context import identity as _identity
from xime.core.security.enums import CredentialType
from xime.starters.jwt._config import JwtMiddlewareConfig
from xime.starters.jwt._key_context import KeyContext
from xime.starters.jwt._middleware import JwtAuthMiddleware

UTC = timezone.utc
MW_SECRET = "middleware-test-secret-long-enough-for-hs256-32bytes"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_token(
    sub: str = "user_123",
    secret: str = MW_SECRET,
    expire_minutes: int = 30,
    extra_claims: dict | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict = {
        "sub": sub,
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    if extra_claims:
        payload.update(extra_claims)
    return pyjwt.encode(payload, secret, algorithm="HS256")


def make_expired_token(secret: str = MW_SECRET) -> str:
    past = datetime.now(UTC) - timedelta(hours=1)
    return pyjwt.encode(
        {"sub": "user_123", "iat": past - timedelta(minutes=30), "exp": past},
        secret,
        algorithm="HS256",
    )


def build_app(
    *,
    secret: str = MW_SECRET,
    identity_claim: str = "sub",
    public_paths: list[str] | None = None,
) -> Starlette:
    """Starlette app tối giản với JwtAuthMiddleware và một handler trả về security context."""

    async def ctx_handler(request: Request) -> JSONResponse:
        cred_type = _credential_type.get()
        return JSONResponse({
            "identity": _identity.get(),
            "credential_type": cred_type.value if cred_type else None,
        })

    config = JwtMiddlewareConfig(
        key_context=KeyContext(algorithm="HS256", secret=secret),
        identity_claim=identity_claim,
        public_paths=public_paths or [],
    )
    app = Starlette(routes=[
        Route("/protected", ctx_handler),
        Route("/public", ctx_handler),
    ])
    app.add_middleware(JwtAuthMiddleware, config=config)
    return app


# ---------------------------------------------------------------------------
# Fixture — app mặc định cho hầu hết test
# ---------------------------------------------------------------------------

@pytest.fixture
def default_app():
    return build_app(public_paths=["/public"])


@pytest.fixture
def transport(default_app):
    return ASGITransport(app=default_app)


# ---------------------------------------------------------------------------
# Public path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_public_path_returns_200_without_auth(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/public")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_public_path_does_not_set_identity(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/public")
    assert response.json()["identity"] is None


@pytest.mark.asyncio
async def test_public_path_does_not_set_credential_type(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/public")
    assert response.json()["credential_type"] is None


# ---------------------------------------------------------------------------
# Missing / malformed Authorization header
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_authorization_header_returns_401(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/protected")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_non_bearer_scheme_returns_401(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_bearer_without_token_value_returns_401(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": "Bearer "})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Valid token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_token_returns_200(transport):
    token = make_token()
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_valid_token_sets_identity_in_security_context(transport):
    token = make_token(sub="user_abc")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.json()["identity"] == "user_abc"


@pytest.mark.asyncio
async def test_valid_token_sets_credential_type_to_token(transport):
    token = make_token()
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.json()["credential_type"] == CredentialType.TOKEN.value


@pytest.mark.asyncio
async def test_consecutive_requests_have_independent_identities(transport):
    """Hai request liên tiếp không chia sẻ security context."""
    token_a = make_token(sub="user_A")
    token_b = make_token(sub="user_B")

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_a = await client.get("/protected", headers={"Authorization": f"Bearer {token_a}"})
        resp_b = await client.get("/protected", headers={"Authorization": f"Bearer {token_b}"})

    assert resp_a.json()["identity"] == "user_A"
    assert resp_b.json()["identity"] == "user_B"


# ---------------------------------------------------------------------------
# Token lỗi
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expired_token_returns_401(transport):
    token = make_expired_token()
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_response_mentions_expired(transport):
    token = make_expired_token()
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert "expired" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_wrong_secret_returns_401(transport):
    token = make_token(secret="correct-secret-long-enough-for-hs256-32bytes")  # app dùng MW_SECRET
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_wrong_secret_response_mentions_invalid_token(transport):
    token = make_token(secret="correct-secret-long-enough-for-hs256-32bytes")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert "Invalid token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_malformed_token_returns_401(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/protected", headers={"Authorization": "Bearer not.a.valid.jwt.at.all"}
        )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Thiếu identity claim
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_token_missing_identity_claim_returns_401():
    """Token không chứa claim mà identity_claim chỉ định → 401."""
    app = build_app(identity_claim="user_id")  # mong đợi "user_id", nhưng token chỉ có "sub"
    token = make_token()  # payload: {"sub": ..., "iat": ..., "exp": ...}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_claim_response_contains_claim_name():
    app = build_app(identity_claim="user_id")
    token = make_token()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert "user_id" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Custom identity_claim
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_custom_identity_claim_maps_correctly():
    """Middleware đọc đúng claim khi identity_claim được tùy chỉnh."""
    app = build_app(identity_claim="uid")
    token = make_token(extra_claims={"uid": "custom_uid_999"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["identity"] == "custom_uid_999"


# ---------------------------------------------------------------------------
# Audience / Issuer + claims exposure (M5)
# ---------------------------------------------------------------------------

def _build_app_aud(*, audience=None, issuer=None) -> Starlette:
    from xime.core.context import request_context
    from xime.starters.jwt._middleware import JWT_CLAIMS

    async def handler(request: Request) -> JSONResponse:
        return JSONResponse({
            "identity": _identity.get(),
            "claims": request_context.get(JWT_CLAIMS),
        })

    config = JwtMiddlewareConfig(
        key_context=KeyContext(algorithm="HS256", secret=MW_SECRET),
        audience=audience,
        issuer=issuer,
    )
    app = Starlette(routes=[Route("/protected", handler)])
    app.add_middleware(JwtAuthMiddleware, config=config)
    return app


@pytest.mark.asyncio
async def test_token_with_aud_accepted_when_audience_not_configured():
    """Functional fix: token mang aud không bị 401 khi app không cấu hình audience."""
    app = _build_app_aud()
    token = make_token(extra_claims={"aud": "data-service"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_matching_audience_accepted():
    app = _build_app_aud(audience="data-service")
    token = make_token(extra_claims={"aud": "data-service"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_wrong_audience_rejected_401():
    app = _build_app_aud(audience="data-service")
    token = make_token(extra_claims={"aud": "other-service"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_wrong_issuer_rejected_401():
    app = _build_app_aud(issuer="trust")
    token = make_token(extra_claims={"iss": "evil"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_claims_exposed_in_request_context():
    app = _build_app_aud()
    token = make_token(sub="u7", extra_claims={"scope": "read write", "roles": ["a"]})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    body = r.json()
    assert body["identity"] == "u7"
    assert body["claims"]["scope"] == "read write"
    assert body["claims"]["roles"] == ["a"]
