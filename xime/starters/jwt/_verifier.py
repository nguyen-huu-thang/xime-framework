from __future__ import annotations

from typing import Any, Protocol

from xime.core.exception.framework import AuthenticationException, TokenExpiredException

from ._key_context import KeyContext
from ._pyjwt import pyjwt


class JwtTokenVerifier(Protocol):
    """Contract for verifying and decoding JWT tokens.

    Implement this Protocol to use a custom verification strategy,
    e.g., fetching public keys from a JWKS endpoint, or validating
    against an external authorization server.

    Default ready-made implementation: PyJwtTokenVerifier.

    Bind in config/dependency.py if using a custom implementation:
        dependency.bind({JwtTokenVerifier: MyJwksVerifier})
    """

    def verify(
        self,
        token: str,
        key_context: KeyContext,
        *,
        audience: str | list[str] | None = None,
        issuer: str | None = None,
        algorithms: list[str] | None = None,
        leeway: float = 0,
        require: list[str] | None = None,
    ) -> dict[str, Any]:
        """Verify and decode a JWT token.

        Args:
            token: Raw JWT string (without "Bearer " prefix).
            key_context: Key material and algorithm for verification.
                         For asymmetric algorithms, only public_key_pem is needed.
            audience: Expected `aud` claim. When set it is enforced; when None the
                      audience is not enforced (tokens with an `aud` claim are
                      still accepted).
            issuer: Expected `iss` claim. Enforced when set; not checked when None.
            algorithms: Allow-list of accepted `alg` values. A key whose algorithm
                      is outside it is refused before any signature is checked.
                      None accepts whatever the key declares.
            leeway: Seconds of tolerance for exp / nbf / iat.
            require: Claims that must be present. Note that exp is only verified
                      when it EXISTS, so a token with no exp never expires unless
                      "exp" appears here.

        Returns:
            Decoded claims dict.

        Raises:
            AuthenticationException: if the token is expired, has an invalid
                                     signature, a mismatched audience/issuer, a
                                     disallowed algorithm, a missing required
                                     claim, or is structurally malformed.
            ValueError: if key_context is missing required key material.

        Note for implementers: these knobs are enumerated as parameters, which
        means every future one changes this Protocol. That is tolerable while the
        list is short and no third-party implementation is known to exist; the
        moment a fourth knob is needed, group them into an options object instead.
        Ghi chú cho người hiện thực: các knob đang được liệt kê thành từng tham
        số, nên mỗi knob thêm về sau đều đổi Protocol này. Chấp nhận được khi
        danh sách còn ngắn; tới knob thứ tư thì gom vào một object options.
        """
        ...


class PyJwtTokenVerifier:
    """JWT token verifier using PyJWT.

    Supports all algorithms PyJWT provides:
        Symmetric - HS256, HS384, HS512
        RSA - RS256, RS384, RS512, PS256, PS384, PS512
        EC - ES256, ES256K, ES384, ES512
        OKP - EdDSA

    No constructor dependencies - DI registers this as a singleton automatically
    when the developer calls dependency.scan("xime.starters.jwt").

    Also used internally by JwtAuthMiddleware for HTTP Bearer token verification.
    """

    def verify(
        self,
        token: str,
        key_context: KeyContext,
        *,
        audience: str | list[str] | None = None,
        issuer: str | None = None,
        algorithms: list[str] | None = None,
        leeway: float = 0,
        require: list[str] | None = None,
    ) -> dict[str, Any]:
        # The allow-list caps which keys may be used at all; the algorithm the
        # token is actually checked against stays pinned to this key's own, so a
        # token cannot pick a weaker one from the list.
        # Danh sách trắng giới hạn khoá nào được dùng; thuật toán thật sự đem ra
        # kiểm vẫn ghim theo chính khoá này, nên token không thể tự chọn một
        # thuật toán yếu hơn trong danh sách.
        if algorithms is not None and key_context.algorithm not in algorithms:
            raise AuthenticationException(
                f"Algorithm '{key_context.algorithm}' is not in the allow-list"
            )

        verify_key = self._resolve_verify_key(key_context)
        # When no audience is configured, disable aud verification explicitly:
        # otherwise PyJWT REJECTS any token that carries an `aud` claim (it raises
        # InvalidAudienceError when a token has aud but decode() got no audience).
        # Không cấu hình audience -> tắt verify_aud, nếu không PyJWT TỪ CHỐI mọi
        # token có claim aud (raise InvalidAudienceError).
        options: dict[str, Any] = {"verify_aud": audience is not None}
        if require:
            options["require"] = list(require)
        jwt = pyjwt()
        try:
            return jwt.decode(
                token,
                verify_key,
                algorithms=[key_context.algorithm],
                audience=audience,
                issuer=issuer,
                leeway=leeway,
                options=options,
            )
        # `from exc` on purpose, and it is load-bearing rather than tidy: PEP 3134
        # makes __cause__ an explicit promise, while the __context__ Python sets
        # by itself inside an `except` block is a side effect nobody owes anyone.
        # This same package already writes `raise ... from None` in two places, so
        # a later pass tidying for consistency could silently erase the implicit
        # chain - and a caller reading it would then see every failure collapse
        # into one, with no test of ours turning red.
        # `from exc` là cố ý, và nó chịu lực chứ không phải cho gọn: PEP 3134 biến
        # __cause__ thành một lời hứa tường minh, còn __context__ mà Python tự gắn
        # trong khối `except` chỉ là tác dụng phụ không ai nợ ai. Chính package
        # này đã viết `raise ... from None` ở hai chỗ, nên một lượt dọn cho đồng
        # bộ có thể lặng lẽ xoá chuỗi ngầm đó.
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredException("Token has expired") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationException(f"Invalid token: {exc}") from exc

    def _resolve_verify_key(self, key_context: KeyContext) -> str | bytes:
        if key_context.algorithm.upper().startswith("HS"):
            if not key_context.secret:
                raise ValueError(
                    f"KeyContext.secret is required for algorithm '{key_context.algorithm}'"
                )
            return key_context.secret

        if not key_context.public_key_pem:
            raise ValueError(
                f"KeyContext.public_key_pem is required for algorithm '{key_context.algorithm}'"
            )
        return key_context.public_key_pem
