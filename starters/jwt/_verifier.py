from __future__ import annotations

from typing import Any, Protocol

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from core.exception.framework import AuthenticationException

from ._key_context import KeyContext


class JwtTokenVerifier(Protocol):
    """Contract for verifying and decoding JWT tokens.

    Implement this Protocol to use a custom verification strategy,
    e.g., fetching public keys from a JWKS endpoint, or validating
    against an external authorization server.

    Default ready-made implementation: PyJwtTokenVerifier.

    Bind in config/dependency.py if using a custom implementation:
        dependency.bind({JwtTokenVerifier: MyJwksVerifier})
    """

    def verify(self, token: str, key_context: KeyContext) -> dict[str, Any]:
        """Verify and decode a JWT token.

        Args:
            token: Raw JWT string (without "Bearer " prefix).
            key_context: Key material and algorithm for verification.
                         For asymmetric algorithms, only public_key_pem is needed.

        Returns:
            Decoded claims dict.

        Raises:
            AuthenticationException: if the token is expired, has an invalid
                                     signature, or is structurally malformed.
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
    when the developer calls dependency.scan("starters.jwt").

    Also used internally by JwtAuthMiddleware for HTTP Bearer token verification.
    """

    def verify(self, token: str, key_context: KeyContext) -> dict[str, Any]:
        verify_key = self._resolve_verify_key(key_context)
        try:
            return jwt.decode(
                token,
                verify_key,
                algorithms=[key_context.algorithm],
            )
        except ExpiredSignatureError:
            raise AuthenticationException("Token has expired")
        except InvalidTokenError as exc:
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
