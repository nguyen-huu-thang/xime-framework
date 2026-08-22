from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from xime.core.context import request_context
from xime.core.exception.framework import AuthenticationException
from xime.core.security.enums import CredentialType
from xime.core.security.session import authenticate

from ._authenticator import JwtAuthenticator
from ._config import JwtMiddlewareConfig, path_is_public, split_public_paths
from ._provider import JwtKeyProvider
from ._verifier import JwtTokenVerifier

_BEARER_PREFIX = "Bearer "
_log = logging.getLogger(__name__)

# request_context key holding the full verified JWT claims, so application code
# can authorize on aud/scope/roles/... without re-decoding the token. Cleared by
# RequestContextMiddleware at the end of the request.
# Key chứa toàn bộ claim đã verify để app authorize tiếp (aud/scope/roles) mà
# không phải decode lại; RequestContextMiddleware dọn cuối request.
JWT_CLAIMS = "jwt_claims"


class JwtAuthMiddleware:
    """Pure-ASGI middleware that validates JWT Bearer tokens on protected requests.

    Pure-ASGI middleware (KHÔNG dùng BaseHTTPMiddleware) xác thực JWT Bearer token.

    Why pure ASGI: authenticate() must set identity in the SAME context as the
    handler, and RequestContextMiddleware (outermost) must be able to clear that
    context after the request. BaseHTTPMiddleware runs downstream in a separate
    task, breaking both - identity could leak between requests. This was a real
    bug reported against 0.4, not a theoretical concern.
    Vì sao pure ASGI: authenticate() phải set identity vào đúng context của handler,
    và RequestContextMiddleware (ngoài cùng) phải dọn được context đó sau request.
    BaseHTTPMiddleware chạy downstream ở task riêng nên phá cả hai -> identity có
    thể rò giữa các request. Đây là lỗi thật đã bị báo ở bản 0.4, không phải lo xa.

    Added automatically by WebAdapter.build_app() when the developer calls
    configure_jwt(). Runs inside RequestContextMiddleware (request_id already set).

    Per-request flow:
        1. Path in public_paths?         -> skip, forward request as-is
        2. Missing Authorization header? -> 401 "Missing authorization token"
        3. Not "Bearer <token>" format?  -> 401 "Missing authorization token"
        4. Pick candidate keys:
             static key configured       -> that one key
             key_provider configured     -> read `kid` from the token header
                                            (no key needed) and ask the provider
             header unreadable / kid not a string -> 401 "Invalid token: malformed header"
             provider knows no such kid  -> 401 "Unknown signing key"
        5. Token expired or invalid?     -> 401 with reason from AuthenticationException
        6. identity_claim absent?        -> 401 "Token missing required claim '...'"
        7. All checks pass               -> authenticate(identity=..., credential_type=TOKEN)
                                            -> forward request to next layer

    Each rejection carries its own reason, because the operator action differs:
    an unknown `kid` points at key distribution, an invalid signature points at
    the token itself, and a malformed header points at a client that is not
    speaking JWT at all.
    Mỗi lý do từ chối là một thông điệp riêng, vì việc operator phải làm khác
    nhau: `kid` lạ là chuyện phân phối khoá, chữ ký sai là chuyện bản thân token,
    header hỏng là chuyện client không nói JWT.
    """

    def __init__(
        self,
        app,
        *,
        config: JwtMiddlewareConfig,
        key_provider: JwtKeyProvider | None = None,
        verifier: JwtTokenVerifier | None = None,
    ) -> None:
        self.app = app
        self._config = config
        # Both collaborators arrive already built - the adapter resolves them
        # from the DI container, so binding JwtTokenVerifier actually reaches
        # this middleware instead of only reaching code that calls it directly.
        # Cả hai cộng tác viên được truyền vào đã dựng sẵn - adapter lấy chúng từ
        # DI container, nên bind JwtTokenVerifier thật sự tới được middleware này.
        #
        # Verification itself lives in JwtAuthenticator (0.7.2) so the WebSocket
        # path uses the SAME definition of a valid token rather than a second one.
        # Phần verify nằm ở JwtAuthenticator để đường WebSocket dùng CHUNG định
        # nghĩa "token hợp lệ" chứ không mọc thêm bản thứ hai.
        self._auth = JwtAuthenticator(
            config, key_provider=key_provider, verifier=verifier
        )
        # Normalize configured paths: strip trailing slashes so "/auth/login"
        # and "/auth/login/" are treated as the same entry. An entry ending in
        # "/*" becomes a branch prefix instead - see split_public_paths().
        self._public, self._public_prefixes = split_public_paths(config.public_paths)

    async def __call__(self, scope, receive, send) -> None:
        # Token auth only applies to HTTP; websocket/lifespan pass through.
        # Auth token chỉ áp cho HTTP; websocket/lifespan đi thẳng qua.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Request reads path/headers from scope only - it does not consume the
        # request body, so the same receive is forwarded intact to the handler.
        # Request chỉ đọc path/headers từ scope, KHÔNG tiêu thụ body - receive được
        # chuyển nguyên vẹn xuống handler.
        request = Request(scope, receive=receive)

        if path_is_public(request.url.path, self._public, self._public_prefixes):
            await self.app(scope, receive, send)
            return

        token = self._extract_bearer_token(request)
        if token is None:
            await self._reject("Missing authorization token", scope, receive, send)
            return

        try:
            claims = self._verify(token)
        except AuthenticationException as exc:
            await self._reject(exc.message, scope, receive, send)
            return

        identity = claims.get(self._config.identity_claim)
        if identity is None:
            await self._reject(
                f"Token missing required claim '{self._config.identity_claim}'",
                scope, receive, send,
            )
            return

        # Expose the full claims so handlers can authorize on aud/scope/roles
        # without re-decoding; identity is also surfaced via SecurityContext.
        # Phơi toàn bộ claim để handler authorize tiếp; identity vẫn vào SecurityContext.
        request_context.set(JWT_CLAIMS, claims)
        authenticate(
            identity=identity,
            credential_type=CredentialType.TOKEN,
        )

        await self.app(scope, receive, send)

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def _verify(self, token: str) -> dict[str, Any]:
        """Delegate to JwtAuthenticator - one definition of a valid token."""
        return self._auth.verify(token)

    @staticmethod
    def _read_kid(token: str) -> str | None:
        """Delegate to JwtAuthenticator. Kept as a name the tests already know."""
        return JwtAuthenticator.read_kid(token)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _reject(detail: str, scope, receive, send) -> None:
        # JSONResponse is itself an ASGI app - call it directly to emit the 401.
        # JSONResponse cũng là một ASGI app - gọi trực tiếp để trả 401.
        await JSONResponse({"detail": detail}, status_code=401)(scope, receive, send)

    @staticmethod
    def _normalize(path: str) -> str:
        """Strip trailing slash, but keep bare '/' intact."""
        return path.rstrip("/") or "/"

    def _extract_bearer_token(self, request: Request) -> str | None:
        auth_header = request.headers.get("Authorization", "")
        # The scheme is case-insensitive per RFC 7235; some clients and gateways
        # send "bearer". Matching only the capitalised spelling turned a valid
        # request into a 401 whose message ("Missing authorization token") says
        # the header is absent when it is right there.
        # Theo RFC 7235 tên scheme không phân biệt hoa thường; một số client gửi
        # "bearer". Chỉ khớp đúng chữ hoa thì request hợp lệ bị 401 với thông báo
        # "thiếu token" trong khi header nằm ngay đó.
        if auth_header[: len(_BEARER_PREFIX)].lower() != _BEARER_PREFIX.lower():
            return None
        token = auth_header[len(_BEARER_PREFIX):].strip()
        return token if token else None
