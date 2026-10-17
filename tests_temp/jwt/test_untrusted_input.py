"""Untrusted JWT headers must fail authentication, including decoder recursion."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Sequence

import jwt
import pytest
import uvicorn
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, RemoteProtocolError

from xime.core.exception.framework import AuthenticationException
from xime.starters.jwt import JwtAuthenticator, JwtMiddlewareConfig, KeyContext
from xime.starters.jwt._middleware import JwtAuthMiddleware
from xime.starters.jwt._verifier import PyJwtTokenVerifier

_SECRET = "jwt-untrusted-input-test-key-at-least-32-bytes"
_KEY = KeyContext(algorithm="HS256", secret=_SECRET)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@pytest.fixture(scope="module")
def nested_token() -> str:
    # CPython 3.14's JSON decoder has a different depth limit from Python's
    # recursion limit. This size reproduced the issue on 3.14.8; older supported
    # interpreters reject it at a lower depth. No valid signature is needed.
    header = b'{"alg":"HS256","x":' + b"[" * 70_000 + b"0" + b"]" * 70_000 + b"}"
    return _b64(header) + "." + _b64(b'{"sub":"test"}') + ".AAAA"


class _Provider:
    def keys(self, kid: str | None) -> Sequence[KeyContext]:
        return (_KEY,)


def _app(provider: bool = False) -> FastAPI:
    app = FastAPI()
    config = JwtMiddlewareConfig(key_context=None if provider else _KEY)
    app.add_middleware(
        JwtAuthMiddleware,
        config=config,
        key_provider=_Provider() if provider else None,
    )

    @app.get("/protected")
    async def protected() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_verifier_rejects_a_real_deeply_nested_header(nested_token: str) -> None:
    with pytest.raises(AuthenticationException):
        PyJwtTokenVerifier().verify(nested_token, _KEY)


@pytest.mark.parametrize("provider", [False, True])
def test_authenticator_rejects_nested_header_in_both_key_modes(
    nested_token: str, provider: bool
) -> None:
    config = JwtMiddlewareConfig(key_context=None if provider else _KEY)
    authenticator = JwtAuthenticator(
        config, key_provider=_Provider() if provider else None
    )
    with pytest.raises(AuthenticationException):
        authenticator.verify(nested_token)


def test_decoder_recursion_is_normalized_even_if_the_dependency_leaks_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = RecursionError("JSON nesting limit reached")

    def decode(*args, **kwargs):
        raise error

    monkeypatch.setattr(jwt, "decode", decode)
    with pytest.raises(AuthenticationException, match="Invalid token") as caught:
        PyJwtTokenVerifier().verify("untrusted-token", _KEY)
    assert caught.value.__cause__ is error
    assert "untrusted-token" not in caught.value.message
    assert _SECRET not in caught.value.message


@pytest.mark.parametrize("error_type", [RuntimeError, ValueError, TypeError])
def test_unrelated_decoder_failures_remain_visible(
    monkeypatch: pytest.MonkeyPatch, error_type: type[Exception]
) -> None:
    error = error_type("unexpected decoder failure")

    def decode(*args, **kwargs):
        raise error

    monkeypatch.setattr(jwt, "decode", decode)
    with pytest.raises(error_type) as caught:
        PyJwtTokenVerifier().verify("untrusted-token", _KEY)
    assert caught.value is error


def test_each_verification_has_its_own_claim_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: list[dict] = []

    def decode(*args, **kwargs):
        options = kwargs["options"]
        received.append(options)
        assert options.get("verify_signature") is not False
        assert "verify_exp" not in options
        assert kwargs["algorithms"] == ["HS256"]
        # Model the upstream options-mutation advisory: a previous call must
        # not be able to turn off checks in the next call.
        options["verify_exp"] = False
        options["require"].append("changed-by-decoder")
        return {"sub": "test"}

    monkeypatch.setattr(jwt, "decode", decode)
    required = ["exp"]
    verifier = PyJwtTokenVerifier()
    verifier.verify("first", _KEY, audience="service-a", require=required)
    verifier.verify("second", _KEY, audience="service-b", require=required)
    assert received[0] is not received[1]
    assert required == ["exp"]


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", [False, True])
async def test_http_rejects_nested_header_without_becoming_a_500(
    nested_token: str, provider: bool
) -> None:
    transport = ASGITransport(app=_app(provider), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/protected", headers={"Authorization": "Bearer " + nested_token}
        )
        assert response.status_code == 401
        valid = jwt.encode({"sub": "test"}, _SECRET, algorithm="HS256")
        response = await client.get(
            "/protected", headers={"Authorization": "Bearer " + valid}
        )
        assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("http_protocol", ["httptools", "h11"])
async def test_real_http_listener_survives_an_untrusted_nested_header(
    nested_token: str, http_protocol: str
) -> None:
    pytest.importorskip(http_protocol)
    config = uvicorn.Config(
        _app(), host="127.0.0.1", port=0, lifespan="off", http=http_protocol,
        access_log=False, log_level="critical",
    )
    config.load()
    server = uvicorn.Server(config)
    server.lifespan = config.lifespan_class(config)
    await server.startup()
    port = server.servers[0].sockets[0].getsockname()[1]
    serving = asyncio.create_task(server.main_loop())
    valid = jwt.encode({"sub": "test"}, _SECRET, algorithm="HS256")
    try:
        async with AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=5) as client:
            response = await client.get(
                "/protected", headers={"Authorization": "Bearer " + valid}
            )
            assert response.status_code == 200
            try:
                rejected = await client.get(
                    "/protected", headers={"Authorization": "Bearer " + nested_token}
                )
            except RemoteProtocolError:
                # Some HTTP parsers reject an oversized header by closing the
                # connection. The valid request below proves the listener lives.
                pass
            else:
                assert rejected.status_code in {400, 401, 431}
            response = await client.get(
                "/protected", headers={"Authorization": "Bearer " + valid}
            )
            assert response.status_code == 200
    finally:
        server.should_exit = True
        await asyncio.wait_for(serving, timeout=5)
        await server.shutdown()
