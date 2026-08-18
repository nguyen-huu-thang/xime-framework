"""The substitution seams have to actually REACH the middleware.

JwtTokenVerifier has been a documented extension point since 0.2 - its docstring
names JWKS endpoints and external authorization servers - while the middleware
constructed PyJwtTokenVerifier itself and took no verifier argument at all. So
the seam applied to code that called the verifier directly, and to nothing on the
request path. Nothing failed; the substitution simply had no effect, and no test
existed that would have noticed.

JwtTokenVerifier là điểm mở rộng có tài liệu từ 0.2, trong khi middleware tự dựng
PyJwtTokenVerifier và không nhận tham số verifier nào. Không có gì hỏng; phép thay
thế chỉ đơn giản là không có tác dụng, và không test nào bắt được.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from xime.adapters.web import WebAdapter
from xime.starters.jwt import (
    JwtMiddlewareConfig,
    KeyContext,
    PyJwtTokenVerifier,
    configure_jwt,
)
from xime.starters.jwt._config import jwt_registry

SECRET = "s" * 32


class _StubContainer:
    """Stands in for Application.get(), recording what the adapter asked for."""

    def __init__(self, instances: dict[type, object]) -> None:
        self._instances = instances
        self.asked: list[type] = []

    def get(self, cls: type) -> object:
        self.asked.append(cls)
        return self._instances[cls]


class _MyVerifier:
    def verify(self, token, key_context, **kw):
        return {"sub": "from-my-verifier"}


class _MyProvider:
    def keys(self, kid):
        return ()


@pytest.fixture(autouse=True)
def _clean_registry():
    jwt_registry.reset()
    yield
    jwt_registry.reset()


def _built_kwargs(container) -> dict:
    app = FastAPI()
    WebAdapter._add_jwt_middleware(app, container)
    return app.user_middleware[0].kwargs


class TestVerifierSubstitution:
    def test_a_named_verifier_is_resolved_and_handed_to_the_middleware(self):
        instance = _MyVerifier()
        container = _StubContainer({_MyVerifier: instance})
        configure_jwt(
            JwtMiddlewareConfig(key_context=KeyContext(algorithm="HS256", secret=SECRET)),
            verifier=_MyVerifier,
        )

        kwargs = _built_kwargs(container)

        assert kwargs["verifier"] is instance
        assert container.asked == [_MyVerifier]

    def test_naming_no_verifier_leaves_the_default_in_place(self):
        """Paired with the test above - substitution must stay opt-in."""
        configure_jwt(
            JwtMiddlewareConfig(key_context=KeyContext(algorithm="HS256", secret=SECRET))
        )

        kwargs = _built_kwargs(_StubContainer({}))

        assert kwargs["verifier"] is None  # middleware falls back to PyJwtTokenVerifier

    @pytest.mark.asyncio
    async def test_the_default_is_still_PyJwtTokenVerifier(self):
        from xime.starters.jwt._middleware import JwtAuthMiddleware

        middleware = JwtAuthMiddleware(None, config=JwtMiddlewareConfig())
        # Verification moved into JwtAuthenticator in 0.7.2 so the WebSocket path
        # shares it; the default it falls back to must not have changed.
        # Phần verify dời sang JwtAuthenticator ở 0.7.2 để WebSocket dùng chung;
        # mặc định nó rơi về thì không được đổi.
        assert isinstance(middleware._auth._verifier, PyJwtTokenVerifier)


class TestKeyProviderWiring:
    def test_the_provider_class_is_resolved_from_the_container(self):
        instance = _MyProvider()
        container = _StubContainer({_MyProvider: instance})
        configure_jwt(JwtMiddlewareConfig(), key_provider=_MyProvider)

        kwargs = _built_kwargs(container)

        assert kwargs["key_provider"] is instance
        assert container.asked == [_MyProvider]

    def test_a_static_key_config_never_touches_the_container(self):
        """Paired: apps that do not use a provider must not need DI for JWT."""
        container = _StubContainer({})
        configure_jwt(
            JwtMiddlewareConfig(key_context=KeyContext(algorithm="HS256", secret=SECRET))
        )

        kwargs = _built_kwargs(container)

        assert kwargs["key_provider"] is None
        assert container.asked == []
