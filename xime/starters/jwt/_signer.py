from __future__ import annotations

from typing import Any, Protocol

from ._key_context import KeyContext
from ._pyjwt import pyjwt

# Header names the caller may not set. See PyJwtTokenSigner for why each one.
# Tên header người gọi không được đặt. Lý do từng cái ở PyJwtTokenSigner.
_RESERVED_HEADERS = frozenset({"alg", "b64", "kid"})


class JwtTokenSigner(Protocol):
    """Contract for signing JWT tokens.

    Implement this Protocol to use a custom signing library, HSM, or cloud KMS.
    Default ready-made implementation: PyJwtTokenSigner.

    Bind in config/dependency.py if using a custom implementation:
        dependency.bind({JwtTokenSigner: MyCustomSigner})

    Or use PyJwtTokenSigner directly (no binding needed - it implements the protocol):
        dependency.scan("xime.starters.jwt")
    """

    def sign(
        self,
        payload: dict[str, Any],
        key_context: KeyContext,
        *,
        headers: dict[str, Any] | None = None,
    ) -> str:
        """Sign a payload and return the serialized JWT string.

        Developer is fully responsible for building the payload - standard claims
        (sub, iss, aud, iat, exp, jti, ...) and any custom claims.

        Args:
            payload: Claims dict.
            key_context: Key material and algorithm.
            headers: Extra JOSE header parameters, e.g. {"typ": "at+jwt"} for an
                OAuth 2.0 access token (RFC 9068), or "cty" / "x5t#S256".
                Three names are refused rather than merged - see the note on
                PyJwtTokenSigner.
                Header JOSE thêm vào. Ba tên bị từ chối chứ không gộp - xem ghi
                chú ở PyJwtTokenSigner.

        Returns:
            Compact serialized JWT (header.payload.signature).

        Raises:
            ValueError: if key_context is missing required key material for the
                algorithm, or if headers carries a reserved name.
        """
        ...


class PyJwtTokenSigner:
    """JWT token signer using PyJWT.

    Supports all algorithms PyJWT provides:
        Symmetric - HS256, HS384, HS512
        RSA - RS256, RS384, RS512, PS256, PS384, PS512
        EC - ES256, ES256K, ES384, ES512
        OKP - EdDSA

    No constructor dependencies - DI registers this as a singleton automatically
    when the developer calls dependency.scan("xime.starters.jwt").

    Three header names are refused instead of merged, each for its own reason:

        alg  PyJWT prefers a header value over its `algorithm` argument, so an
             `alg` here would silently contradict KeyContext.algorithm: the token
             gets signed with something other than what the caller declared, and
             nothing reports it.
             PyJWT ưu tiên giá trị trong header hơn tham số `algorithm`, nên `alg`
             ở đây sẽ âm thầm mâu thuẫn với KeyContext.algorithm.
        b64  Setting it to False switches PyJWT into detached-payload mode
             (RFC 7797), which produces a token this library cannot verify.
             Đặt False là chuyển PyJWT sang chế độ detached payload, sinh ra token
             chính thư viện này không verify được.
        kid  It must name the key that actually signed, and KeyContext.key_id is
             the one place that knows which key that is. Two sources for one fact
             is two sources that can disagree.
             Nó phải gọi tên đúng khoá đã ký, mà chỉ KeyContext.key_id biết đó là
             khoá nào. Một sự thật hai chỗ khai là hai chỗ có thể mâu thuẫn.

    Signing without a key id is legal - RFC 7515 makes `kid` OPTIONAL - but it is
    a decision, not a detail: a token that names no key cannot be routed to one,
    so no verifier can hold two keys at once for it, so the issuer can never
    rotate without a flag day. Set KeyContext.key_id unless you are certain the
    key will never change.
    Ký mà không có key id là hợp lệ - RFC 7515 nói `kid` TUỲ CHỌN - nhưng đó là
    một quyết định chứ không phải chi tiết: token không gọi tên khoá nào thì
    không định tuyến được tới khoá, nên không bên verify nào giữ hai khoá cùng
    lúc cho nó được, nên issuer không bao giờ xoay khoá mà không phải cắt dịch vụ.

    Usage in application service:
        class TokenService:
            def __init__(self, signer: JwtTokenSigner) -> None:
                self._signer = signer
                self._key = KeyContext(
                    algorithm="RS256",
                    private_key_pem=config.get("jwt.private_key"),
                    key_id="key-2025",
                )

            def create_access_token(self, subject: str) -> str:
                payload = {
                    "sub": subject,
                    "iss": "my-service",
                    "iat": datetime.now(UTC),
                    "exp": datetime.now(UTC) + timedelta(minutes=30),
                }
                return self._signer.sign(payload, self._key)
    """

    def sign(
        self,
        payload: dict[str, Any],
        key_context: KeyContext,
        *,
        headers: dict[str, Any] | None = None,
    ) -> str:
        merged = dict(headers or {})
        if reserved := _RESERVED_HEADERS & merged.keys():
            raise ValueError(
                f"headers must not set {sorted(reserved)} - "
                f"set them on KeyContext instead. See PyJwtTokenSigner."
            )

        signing_key = self._resolve_signing_key(key_context)
        # Empty string is not a key id. `is not None` let "" through and stamped
        # kid:"" into real tokens, which is worse than carrying no kid at all: a
        # keyset verifier looks up "" , finds nothing and rejects, while the token
        # still looks like it declared its key.
        # Chuỗi rỗng không phải key id. `is not None` cho "" lọt qua và đóng dấu
        # kid:"" vào token thật - tệ hơn cả không có kid: bên verify tra "" không
        # thấy gì rồi từ chối, trong khi token vẫn trông như đã khai khoá.
        if key_context.key_id:
            merged["kid"] = key_context.key_id

        return pyjwt().encode(
            payload,
            signing_key,
            algorithm=key_context.algorithm,
            headers=merged or None,
        )

    def _resolve_signing_key(self, key_context: KeyContext) -> str | bytes:
        if key_context.algorithm.upper().startswith("HS"):
            if not key_context.secret:
                raise ValueError(
                    f"KeyContext.secret is required for algorithm '{key_context.algorithm}'"
                )
            return key_context.secret

        if not key_context.private_key_pem:
            raise ValueError(
                f"KeyContext.private_key_pem is required for algorithm '{key_context.algorithm}'"
            )
        return key_context.private_key_pem
