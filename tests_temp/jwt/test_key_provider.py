"""Keys addressed by `kid`: the provider seam, and the start-up contract.

Tests come in PAIRS wherever a value was split into two meanings, because a test
for one branch alone cannot tell "the split works" from "everything now takes the
other branch".

Test đi thành CẶP ở mọi chỗ vừa tách một giá trị làm hai nghĩa, vì test cho một
nhánh không phân biệt được "đã tách đúng" với "mọi thứ nay rơi hết sang nhánh kia".
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import jwt as pyjwt_lib
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from xime.adapters.web import WebAdapter
from xime.core.exception.framework import StartupException
from xime.starters.jwt import (
    JwtKeyProvider,
    JwtMiddlewareConfig,
    KeyContext,
    PyJwtTokenSigner,
    configure_jwt,
)
from xime.starters.jwt._config import jwt_registry
from xime.starters.jwt._middleware import JwtAuthMiddleware

SECRET_A = "a" * 32
SECRET_B = "b" * 32


def _key(kid: str | None, secret: str) -> KeyContext:
    return KeyContext(algorithm="HS256", secret=secret, key_id=kid)


def _token(secret: str, kid: str | None, **claims) -> str:
    payload = {"sub": "u1", "exp": datetime.now(UTC) + timedelta(minutes=5), **claims}
    return PyJwtTokenSigner().sign(payload, _key(kid, secret))


class _Provider:
    """Minimal in-memory provider - the shape an application is expected to write."""

    def __init__(self, keys: dict[str, KeyContext] | None = None) -> None:
        self._keys = keys or {}
        self.calls: list[str | None] = []

    def keys(self, kid: str | None) -> Sequence[KeyContext]:
        self.calls.append(kid)
        if kid is None:
            return ()
        found = self._keys.get(kid)
        return (found,) if found else ()


@pytest.fixture(autouse=True)
def _clean_registry():
    jwt_registry.reset()
    yield
    jwt_registry.reset()


async def _call(middleware_kwargs: dict, token: str | None, path: str = "/x"):
    app = FastAPI()

    @app.get("/x")
    async def _handler():
        return {"ok": True}

    app.add_middleware(JwtAuthMiddleware, **middleware_kwargs)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        return await client.get(path, headers=headers)


# ----------------------------------------------------------------------
# Routing a token to its key
# ----------------------------------------------------------------------


class TestKidRouting:
    @pytest.mark.asyncio
    async def test_token_verifies_with_the_key_its_kid_names(self):
        provider = _Provider({"k1": _key("k1", SECRET_A)})
        res = await _call(
            {"config": JwtMiddlewareConfig(), "key_provider": provider},
            _token(SECRET_A, "k1"),
        )
        assert res.status_code == 200
        assert provider.calls == ["k1"]

    @pytest.mark.asyncio
    async def test_overlapping_rotation_accepts_both_old_and_new(self):
        """The whole point of a keyset: two keys valid at once, neither restart."""
        provider = _Provider({"old": _key("old", SECRET_A), "new": _key("new", SECRET_B)})
        cfg = {"config": JwtMiddlewareConfig(), "key_provider": provider}

        assert (await _call(cfg, _token(SECRET_A, "old"))).status_code == 200
        assert (await _call(cfg, _token(SECRET_B, "new"))).status_code == 200

    @pytest.mark.asyncio
    async def test_unknown_kid_is_rejected_and_says_so(self):
        provider = _Provider({"k1": _key("k1", SECRET_A)})
        res = await _call(
            {"config": JwtMiddlewareConfig(), "key_provider": provider},
            _token(SECRET_A, "gone"),
        )
        assert res.status_code == 401
        assert res.json()["detail"] == "Unknown signing key"

    @pytest.mark.asyncio
    async def test_known_kid_with_a_bad_signature_says_something_ELSE(self):
        """Paired with the test above: two rejections, two operator actions.

        An unknown kid points at key distribution; a bad signature points at the
        token. Collapsing them into one message throws away the only clue.
        `kid` lạ là chuyện phân phối khoá, chữ ký sai là chuyện bản thân token.
        """
        provider = _Provider({"k1": _key("k1", SECRET_A)})
        res = await _call(
            {"config": JwtMiddlewareConfig(), "key_provider": provider},
            _token(SECRET_B, "k1"),  # signed with the wrong secret
        )
        assert res.status_code == 401
        assert res.json()["detail"] != "Unknown signing key"
        assert "Invalid token" in res.json()["detail"]


# ----------------------------------------------------------------------
# Hostile headers - reached before any credential is checked
# ----------------------------------------------------------------------


class TestMalformedHeader:
    @pytest.mark.asyncio
    async def test_a_non_string_kid_never_reaches_the_middleware(self):
        """Layer one: PyJWT itself refuses it, at every version we support.

        Measured against the declared 2.8 floor as well as the installed 2.13, so
        the crafted token cannot even be built, let alone parsed. Pinned here so
        that the day this stops being true, something goes red - the guard below
        is the only thing standing behind it.
        Đo cả ở sàn 2.8 lẫn bản 2.13 đang cài. Ghim lại để ngày điều này hết đúng
        thì có cái báo đỏ.
        """
        with pytest.raises(pyjwt_lib.InvalidTokenError, match="must be a string"):
            pyjwt_lib.encode(
                {"sub": "u1"}, SECRET_A, algorithm="HS256", headers={"kid": {"a": 1}}
            )

    def test_read_kid_refuses_a_non_string_even_if_one_gets_through(self, monkeypatch):
        """Layer two: our own promise.

        JwtKeyProvider.keys() is annotated `str | None`. Since PyJWT blocks this
        on its own, the branch is unreachable through a real request - which is
        exactly why it needs a direct test rather than none: an untested guard
        that nothing can reach is indistinguishable from a broken one.
        keys() khai kiểu `str | None`. PyJWT đã chặn sẵn nên nhánh này không tới
        được qua request thật - và chính vì thế nó cần một test trực tiếp: một
        chốt chặn không ai chạm tới và không ai kiểm thì không phân biệt được với
        một chốt chặn hỏng.
        """
        from xime.core.exception.framework import AuthenticationException
        from xime.starters.jwt import _middleware

        class _FakeJwt:
            @staticmethod
            def get_unverified_header(_token):
                return {"alg": "HS256", "kid": {"a": 1}}

        monkeypatch.setattr(_middleware, "pyjwt", lambda: _FakeJwt)
        with pytest.raises(AuthenticationException, match="malformed header"):
            JwtAuthMiddleware._read_kid("anything")

    @pytest.mark.asyncio
    async def test_garbage_token_does_not_become_a_500(self):
        provider = _Provider({"k1": _key("k1", SECRET_A)})
        res = await _call(
            {"config": JwtMiddlewareConfig(), "key_provider": provider}, "not-a-jwt"
        )
        assert res.status_code == 401
        assert res.json()["detail"] == "Invalid token: malformed header"

    @pytest.mark.asyncio
    async def test_token_without_kid_reaches_the_provider_as_None(self):
        """RFC 7515 makes `kid` OPTIONAL, so None is a value, not a malformation.

        What it MEANS is the provider's policy - the framework must not decide
        for it, and in particular must not fall back to trying every key.
        """
        provider = _Provider({"k1": _key("k1", SECRET_A)})
        res = await _call(
            {"config": JwtMiddlewareConfig(), "key_provider": provider},
            _token(SECRET_A, None),
        )
        assert provider.calls == [None]
        assert res.status_code == 401  # this provider answers () for None

    @pytest.mark.asyncio
    async def test_a_provider_that_raises_fails_closed(self):
        class Broken:
            def keys(self, kid):
                raise RuntimeError("boom")

        res = await _call(
            {"config": JwtMiddlewareConfig(), "key_provider": Broken()},
            _token(SECRET_A, "k1"),
        )
        assert res.status_code == 401


# ----------------------------------------------------------------------
# Start-up: three outcomes, not two
# ----------------------------------------------------------------------


class TestStartupKeySourceValidation:
    def test_no_key_source_at_all_refuses_to_start(self):
        """The A1 hole, closed.

        Before this check, an application whose keys were unavailable at start-up
        simply never called configure_jwt() and booted with NO authentication at
        all, reporting itself healthy while every endpoint was open.
        """
        configure_jwt(JwtMiddlewareConfig(audience="svc"))
        with pytest.raises(StartupException, match="without a key source"):
            WebAdapter._add_jwt_middleware(FastAPI(), None)

    def test_both_key_sources_refuses_to_start(self):
        configure_jwt(
            JwtMiddlewareConfig(key_context=_key("k1", SECRET_A)),
            key_provider=_Provider,
        )
        with pytest.raises(StartupException, match="both"):
            WebAdapter._add_jwt_middleware(FastAPI(), None)

    def test_a_static_key_alone_still_starts(self):
        """Paired with the two above: the guard must not reject the legal cases."""
        configure_jwt(JwtMiddlewareConfig(key_context=_key("k1", SECRET_A)))
        WebAdapter._add_jwt_middleware(FastAPI(), None)  # no raise

    def test_never_calling_configure_jwt_still_starts(self):
        """Opting out of JWT entirely is not the same as opting in badly."""
        WebAdapter._add_jwt_middleware(FastAPI(), None)  # no raise


# ----------------------------------------------------------------------
# The static path is untouched
# ----------------------------------------------------------------------


class TestStaticKeyUnchanged:
    @pytest.mark.asyncio
    async def test_single_key_config_behaves_exactly_as_before(self):
        res = await _call(
            {"config": JwtMiddlewareConfig(key_context=_key(None, SECRET_A))},
            _token(SECRET_A, None),
        )
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_static_key_never_reads_the_kid_header(self):
        """A token carrying an unrelated kid must still verify on the static path.

        Otherwise adding kid support would silently narrow the old behaviour.
        """
        res = await _call(
            {"config": JwtMiddlewareConfig(key_context=_key(None, SECRET_A))},
            _token(SECRET_A, "some-other-kid"),
        )
        assert res.status_code == 200
