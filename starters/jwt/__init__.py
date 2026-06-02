from ._config import JwtMiddlewareConfig, configure_jwt
from ._key_context import KeyContext
from ._signer import JwtTokenSigner, PyJwtTokenSigner
from ._verifier import JwtTokenVerifier, PyJwtTokenVerifier

# __all__ controls which classes DI scanner registers from dependency.scan("starters.jwt").
# Only stateless singleton services appear here — config/data objects are excluded.
#
# PyJwtTokenSigner  : no constructor deps, injectable as JwtTokenSigner implementation
# PyJwtTokenVerifier: no constructor deps, injectable as JwtTokenVerifier implementation
#
# KeyContext, JwtMiddlewareConfig, configure_jwt: config objects — not DI-managed,
# but still importable directly:
#   from starters.jwt import KeyContext, JwtMiddlewareConfig, configure_jwt
__all__ = [
    "PyJwtTokenSigner",
    "PyJwtTokenVerifier",
]
