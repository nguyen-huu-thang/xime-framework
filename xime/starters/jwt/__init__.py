"""
xime.starters.jwt — JWT authentication starter.

Usage:
    from xime.starters.jwt import configure_jwt, JwtMiddlewareConfig, KeyContext
    from xime.starters.jwt import JwtTokenSigner, JwtTokenVerifier
    from xime.starters.jwt import PyJwtTokenSigner, PyJwtTokenVerifier

Example:
    configure_jwt(JwtMiddlewareConfig(
        key_context=KeyContext(algorithm="RS256", public_key_pem=os.environ["JWT_PUBLIC_KEY"]),
        identity_claim="sub",
        public_paths=["/auth/login", "/health"],
    ))
"""

from starters.jwt import (
    JwtMiddlewareConfig,
    JwtTokenSigner,
    JwtTokenVerifier,
    KeyContext,
    PyJwtTokenSigner,
    PyJwtTokenVerifier,
    configure_jwt,
)

__all__ = [
    "configure_jwt",
    "JwtMiddlewareConfig",
    "KeyContext",
    "JwtTokenSigner",
    "JwtTokenVerifier",
    "PyJwtTokenSigner",
    "PyJwtTokenVerifier",
]
