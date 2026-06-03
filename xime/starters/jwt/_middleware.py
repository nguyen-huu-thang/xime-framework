from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from xime.core.exception.framework import AuthenticationException
from xime.core.security.enums import CredentialType
from xime.core.security.session import authenticate

from ._config import JwtMiddlewareConfig
from ._verifier import PyJwtTokenVerifier

_BEARER_PREFIX = "Bearer "


class JwtAuthMiddleware(BaseHTTPMiddleware):
    """HTTP middleware that validates JWT Bearer tokens on every protected request.

    Added automatically by WebAdapter.build() when the developer calls configure_jwt().
    Runs after RequestContextMiddleware in the processing chain (inner layer) —
    request_id is already set when token validation begins.

    Per-request flow:
        1. Path in public_paths?        → skip, forward request as-is
        2. Missing Authorization header? → 401 "Missing authorization token"
        3. Not "Bearer <token>" format?  → 401 "Missing authorization token"
        4. Token expired or invalid?     → 401 with reason from AuthenticationException
        5. identity_claim absent?        → 401 "Token missing required claim '...'"
        6. All checks pass              → authenticate(identity=..., credential_type=TOKEN)
                                          → forward request to next layer
    """

    def __init__(self, app, *, config: JwtMiddlewareConfig) -> None:
        super().__init__(app)
        self._config = config
        self._verifier = PyJwtTokenVerifier()
        self._public = frozenset(config.public_paths)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self._public:
            return await call_next(request)

        token = self._extract_bearer_token(request)
        if token is None:
            return JSONResponse(
                {"detail": "Missing authorization token"},
                status_code=401,
            )

        try:
            claims = self._verifier.verify(token, self._config.key_context)
        except AuthenticationException as exc:
            return JSONResponse({"detail": exc.message}, status_code=401)

        identity = claims.get(self._config.identity_claim)
        if identity is None:
            return JSONResponse(
                {"detail": f"Token missing required claim '{self._config.identity_claim}'"},
                status_code=401,
            )

        authenticate(
            identity=identity,
            credential_type=CredentialType.TOKEN,
        )

        return await call_next(request)

    def _extract_bearer_token(self, request: Request) -> str | None:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith(_BEARER_PREFIX):
            return None
        token = auth_header[len(_BEARER_PREFIX):]
        return token if token else None
