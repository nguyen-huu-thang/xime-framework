from __future__ import annotations

from typing import Any, Protocol

from xime.core.exception.framework import AuthenticationException

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

        Returns:
            Decoded claims dict.

        Raises:
            AuthenticationException: if the token is expired, has an invalid
                                     signature, a mismatched audience/issuer, or
                                     is structurally malformed.
            ValueError: if key_context is missing required key material.
        """
        ...


class PyJwtTokenVerifier:
    """JWT token verifier using PyJWT.

    Supports all algorithms PyJWT provides:
        Symmetric  — HS256, HS384, HS512
        RSA        — RS256, RS384, RS512, PS256, PS384, PS512
        EC         — ES256, ES256K, ES384, ES512
        OKP        — EdDSA

    No constructor dependencies — DI registers this as a singleton automatically
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
    ) -> dict[str, Any]:
        verify_key = self._resolve_verify_key(key_context)
        # When no audience is configured, disable aud verification explicitly:
        # otherwise PyJWT REJECTS any token that carries an `aud` claim (it raises
        # InvalidAudienceError when a token has aud but decode() got no audience).
        # Không cấu hình audience -> tắt verify_aud, nếu không PyJWT TỪ CHỐI mọi
        # token có claim aud (raise InvalidAudienceError).
        options = {"verify_aud": audience is not None}
        jwt = pyjwt()
        try:
            return jwt.decode(
                token,
                verify_key,
                algorithms=[key_context.algorithm],
                audience=audience,
                issuer=issuer,
                options=options,
            )
        except jwt.ExpiredSignatureError:
            raise AuthenticationException("Token has expired")
        except jwt.InvalidTokenError as exc:
            raise AuthenticationException(f"Invalid token: {exc}")

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
