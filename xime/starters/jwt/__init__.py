from ._config import JwtMiddlewareConfig as JwtMiddlewareConfig
from ._config import configure_jwt as configure_jwt
from ._key_context import KeyContext as KeyContext
from ._middleware import JWT_CLAIMS as JWT_CLAIMS
from ._provider import JwtKeyProvider as JwtKeyProvider
from ._signer import JwtTokenSigner as JwtTokenSigner
from ._signer import PyJwtTokenSigner as PyJwtTokenSigner
from ._verifier import JwtTokenVerifier as JwtTokenVerifier
from ._verifier import PyJwtTokenVerifier as PyJwtTokenVerifier

# The `X as X` form is PEP 484's explicit re-export marker. It is needed because
# __all__ here is NOT the list of public names — it is the list the DI scanner
# registers (see rules/coding.md). Without the marker, a user running
# `mypy --strict` gets "does not explicitly export attribute" on the very
# imports this framework's own documentation tells them to write.
# Dạng `X as X` là dấu re-export tường minh của PEP 484. Cần nó vì __all__ ở đây
# KHÔNG phải danh sách tên công khai, mà là danh sách DI scanner đăng ký. Thiếu
# nó thì người dùng bật `mypy --strict` sẽ bị báo lỗi ngay ở những dòng import
# mà chính tài liệu của framework hướng dẫn viết.
#
# __all__ controls which classes DI scanner registers from dependency.scan("xime.starters.jwt").
# Only stateless singleton services appear here — config/data objects are excluded.
#
# PyJwtTokenSigner  : no constructor deps, injectable as JwtTokenSigner implementation
# PyJwtTokenVerifier: no constructor deps, injectable as JwtTokenVerifier implementation
#
# KeyContext, JwtMiddlewareConfig, configure_jwt: config objects — not DI-managed,
# but still importable directly:
#   from xime.starters.jwt import KeyContext, JwtMiddlewareConfig, configure_jwt
#
# JWT_CLAIMS: the request_context key holding the verified claims. Exported
# in 0.7.2 because application code genuinely needs it - the WebSocket docs
# tell readers to look claims up, and pointing them at a module whose name
# starts with an underscore is telling them to reach into our internals.
# JWT_CLAIMS: key trong request_context chứa claim đã verify. Export ở 0.7.2
# vì code ứng dụng thật sự cần - chỉ người ta vào một module có tên bắt đầu
# bằng dấu gạch dưới là bảo họ thò tay vào ruột của mình.
__all__ = [
    "PyJwtTokenSigner",
    "PyJwtTokenVerifier",
]
