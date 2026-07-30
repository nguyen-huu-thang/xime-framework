from __future__ import annotations

from typing import Any, Protocol

from ._key_context import KeyContext
from ._pyjwt import pyjwt


class JwtTokenSigner(Protocol):
    """Contract for signing JWT tokens.

    Implement this Protocol to use a custom signing library, HSM, or cloud KMS.
    Default ready-made implementation: PyJwtTokenSigner.

    Bind in config/dependency.py if using a custom implementation:
        dependency.bind({JwtTokenSigner: MyCustomSigner})

    Or use PyJwtTokenSigner directly (no binding needed — it implements the protocol):
        dependency.scan("xime.starters.jwt")
    """

    def sign(self, payload: dict[str, Any], key_context: KeyContext) -> str:
        """Sign a payload and return the serialized JWT string.

        Developer is fully responsible for building the payload — standard claims
        (sub, iss, aud, iat, exp, jti, ...) and any custom claims.

        Args:
            payload: Claims dict.
            key_context: Key material and algorithm.

        Returns:
            Compact serialized JWT (header.payload.signature).

        Raises:
            ValueError: if key_context is missing required key material for the algorithm.
        """
        ...


class PyJwtTokenSigner:
    """JWT token signer using PyJWT.

    Supports all algorithms PyJWT provides:
        Symmetric  — HS256, HS384, HS512
        RSA        — RS256, RS384, RS512, PS256, PS384, PS512
        EC         — ES256, ES256K, ES384, ES512
        OKP        — EdDSA

    No constructor dependencies — DI registers this as a singleton automatically
    when the developer calls dependency.scan("xime.starters.jwt").

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

    def sign(self, payload: dict[str, Any], key_context: KeyContext) -> str:
        signing_key = self._resolve_signing_key(key_context)
        headers: dict[str, str] = {}
        if key_context.key_id is not None:
            headers["kid"] = key_context.key_id

        return pyjwt().encode(
            payload,
            signing_key,
            algorithm=key_context.algorithm,
            headers=headers if headers else None,
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
