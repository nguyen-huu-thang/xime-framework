from __future__ import annotations

from dataclasses import dataclass, field

from ._key_context import KeyContext


@dataclass
class JwtMiddlewareConfig:
    """Configuration for JwtAuthMiddleware.

    key_context : Key used to VERIFY incoming tokens.
                  For asymmetric algorithms, provide only public_key_pem.
                  For HMAC, provide secret.
    identity_claim : JWT claim mapped to SecurityContext.identity (default: "sub").
    public_paths   : Request paths that bypass JWT authentication entirely.
    audience : Expected `aud` claim. When set, the token's audience MUST match
               (PyJWT raises otherwise). When None, the audience is NOT enforced
               and tokens carrying an `aud` claim are still accepted (a multi-
               service platform that shares one signing key SHOULD set this to
               its own service id to reject tokens minted for another service).
               Khi set: bắt buộc khớp aud; khi None: KHÔNG ép aud (vẫn nhận token
               có aud). Platform dùng chung key NÊN set để chặn token của service khác.
    issuer   : Expected `iss` claim. When set, the token's issuer MUST match.
               When None, the issuer is not checked.
               Khi set: bắt buộc khớp iss; None: không kiểm.

    Example usage in config/jwt.py:

        import os
        from xime.starters.jwt import configure_jwt, JwtMiddlewareConfig, KeyContext

        configure_jwt(JwtMiddlewareConfig(
            key_context=KeyContext(
                algorithm="RS256",
                public_key_pem=os.environ["JWT_PUBLIC_KEY"],
            ),
            identity_claim="sub",
            audience="data-service",
            issuer="https://identity.internal",
            public_paths=["/auth/login", "/auth/refresh", "/health"],
        ))
    """

    key_context: KeyContext
    identity_claim: str = "sub"
    public_paths: list[str] = field(default_factory=list)
    audience: str | list[str] | None = None
    issuer: str | None = None


class _JwtRegistry:
    def __init__(self) -> None:
        self._config: JwtMiddlewareConfig | None = None

    def set(self, config: JwtMiddlewareConfig) -> None:
        self._config = config

    def get(self) -> JwtMiddlewareConfig | None:
        return self._config

    def reset(self) -> None:
        """Clear the registration - test cleanup only."""
        self._config = None


# Module-level singleton — read by WebAdapter.build() to add JwtAuthMiddleware.
jwt_registry = _JwtRegistry()


def configure_jwt(config: JwtMiddlewareConfig) -> None:
    """Register JWT middleware configuration.

    Call this once in your config layer (e.g. config/jwt.py).
    WebAdapter.build() reads this registry and adds JwtAuthMiddleware automatically.

    This follows the same explicit-call pattern as configure_openapi():
    the developer opts in by calling this function — no auto-scan magic.
    """
    jwt_registry.set(config)
