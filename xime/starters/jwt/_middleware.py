from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from xime.core.context import request_context
from xime.core.exception.framework import AuthenticationException
from xime.core.security.enums import CredentialType
from xime.core.security.session import authenticate

from ._config import JwtMiddlewareConfig
from ._key_context import KeyContext
from ._provider import JwtKeyProvider
from ._pyjwt import pyjwt
from ._verifier import JwtTokenVerifier, PyJwtTokenVerifier

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
        self._provider = key_provider
        # Both collaborators arrive already built - the adapter resolves them
        # from the DI container, so binding JwtTokenVerifier actually reaches
        # this middleware instead of only reaching code that calls it directly.
        # Cả hai cộng tác viên được truyền vào đã dựng sẵn - adapter lấy chúng từ
        # DI container, nên bind JwtTokenVerifier thật sự tới được middleware này.
        self._verifier = verifier if verifier is not None else PyJwtTokenVerifier()
        # Normalize configured paths: strip trailing slashes so "/auth/login"
        # and "/auth/login/" are treated as the same entry.
        self._public = frozenset(self._normalize(p) for p in config.public_paths)

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

        if self._normalize(request.url.path) in self._public:
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
        """Verify against every key that answers to the token's `kid`.

        More than one candidate is normal while an issuer rotates: the old key
        and the new one are both valid, and only trying them tells which signed
        this token.
        Nhiều hơn một khoá ứng viên là bình thường trong lúc issuer xoay khoá.
        """
        first_error: AuthenticationException | None = None
        for key in self._candidate_keys(token):
            try:
                return self._verifier.verify(
                    token,
                    key,
                    audience=self._config.audience,
                    issuer=self._config.issuer,
                    algorithms=self._config.algorithms,
                    leeway=self._config.leeway,
                    require=self._config.require,
                )
            except AuthenticationException as exc:
                # Report the FIRST failure, not the last: keys() returns
                # candidates in the order they should be tried, so the first is
                # the one the provider considers most likely to be right, and its
                # reason is the most useful thing to tell the caller.
                # Báo lỗi ĐẦU TIÊN chứ không phải cuối: keys() trả khoá theo thứ
                # tự nên thử, nên cái đầu là cái provider cho là khả dĩ nhất.
                if first_error is None:
                    first_error = exc

        raise first_error or AuthenticationException("Unknown signing key")

    def _candidate_keys(self, token: str) -> Sequence[KeyContext]:
        if self._provider is None:
            # Startup validation guarantees a static key exists when there is no
            # provider, so this is not an optional dereference in practice.
            # Kiểm lúc khởi động đã bảo đảm có khoá tĩnh khi không có provider.
            static = self._config.key_context
            return (static,) if static is not None else ()

        kid = self._read_kid(token)
        try:
            candidates = self._provider.keys(kid)
        except Exception:
            # keys() is contractually forbidden from raising. If it does anyway,
            # fail closed rather than turning an attacker-supplied `kid` into a
            # 500 - but log it loudly, because it is a bug in the provider and
            # silence would let it live forever behind a plain 401.
            # keys() bị hợp đồng cấm ném lỗi. Nếu vẫn ném thì đóng cửa lại thay vì
            # biến một `kid` do kẻ tấn công đặt thành lỗi 500 - nhưng phải log to,
            # vì đó là bug của provider và im lặng sẽ giấu nó sau một mã 401.
            _log.exception("JwtKeyProvider.keys() raised; rejecting the request")
            raise AuthenticationException("Unknown signing key") from None

        if not candidates:
            raise AuthenticationException("Unknown signing key")
        return candidates

    @staticmethod
    def _read_kid(token: str) -> str | None:
        """Read the `kid` header without a key, and refuse anything but a string.

        The header is JSON chosen by whoever sent the token, so `kid` can arrive
        as a number, a list or an object. Every PyJWT in the supported range
        (checked at the 2.8 floor) already refuses those, so the isinstance check
        below is not load-bearing against PyJWT - it is here because
        JwtKeyProvider.keys() is annotated `str | None`, and a promise made to
        application developers should be kept by the code that makes it rather
        than by a third-party library that happens to agree today. Without it, a
        provider doing a plain dict lookup would meet an unhashable key.
        Header là JSON do bên gửi token chọn, nên `kid` có thể tới dưới dạng số,
        mảng hay object. Mọi bản PyJWT trong dải hỗ trợ (đã kiểm ở sàn 2.8) đều
        đã từ chối sẵn, nên phép kiểm isinstance dưới đây không phải lớp chắn
        trước PyJWT - nó ở đây vì JwtKeyProvider.keys() khai kiểu `str | None`, và
        một lời hứa với người viết ứng dụng nên do chính chỗ hứa giữ, chứ không
        nhờ một thư viện bên thứ ba tình cờ đang đồng ý.
        """
        try:
            header = pyjwt().get_unverified_header(token)
        except Exception:
            raise AuthenticationException("Invalid token: malformed header") from None

        kid = header.get("kid")
        if kid is None:
            return None
        if not isinstance(kid, str):
            raise AuthenticationException("Invalid token: malformed header")
        return kid

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
