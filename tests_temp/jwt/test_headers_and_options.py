"""Header control on the signing side, and the verification knobs PyJWT exposes
but JwtMiddlewareConfig used to hide.

Điều khiển header phía ký, và các knob verify mà PyJWT có nhưng
JwtMiddlewareConfig từng giấu đi.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest

from xime.core.exception.framework import AuthenticationException
from xime.starters.jwt import KeyContext, PyJwtTokenSigner, PyJwtTokenVerifier

SECRET = "s" * 32


def _header(token: str) -> dict:
    raw = token.split(".")[0]
    raw += "=" * (-len(raw) % 4)
    return json.loads(base64.urlsafe_b64decode(raw))


def _ctx(**kw) -> KeyContext:
    return KeyContext(algorithm=kw.pop("algorithm", "HS256"), secret=SECRET, **kw)


# ----------------------------------------------------------------------
# kid
# ----------------------------------------------------------------------


class TestKeyIdStamping:
    def test_a_key_id_is_stamped_as_kid(self):
        token = PyJwtTokenSigner().sign({"sub": "u"}, _ctx(key_id="k1"))
        assert _header(token)["kid"] == "k1"

    def test_no_key_id_stamps_no_kid(self):
        token = PyJwtTokenSigner().sign({"sub": "u"}, _ctx())
        assert "kid" not in _header(token)

    def test_an_EMPTY_key_id_stamps_no_kid_either(self):
        """`is not None` used to let "" through and write kid:"" into real tokens.

        That is worse than carrying no kid: a keyset verifier looks up "", finds
        nothing and rejects, while the token still looks like it named its key -
        so whoever debugs it starts in the wrong place.
        `is not None` từng cho "" lọt qua và ghi kid:"" vào token thật. Tệ hơn cả
        không có kid: bên verify tra "" không thấy gì rồi từ chối, trong khi token
        vẫn trông như đã gọi tên khoá.
        """
        token = PyJwtTokenSigner().sign({"sub": "u"}, _ctx(key_id=""))
        assert "kid" not in _header(token)


# ----------------------------------------------------------------------
# Extra headers
# ----------------------------------------------------------------------


class TestExtraHeaders:
    def test_a_standard_typ_can_finally_be_set(self):
        """RFC 9068 access tokens declare typ=at+jwt. There was no way to do it."""
        token = PyJwtTokenSigner().sign(
            {"sub": "u"}, _ctx(key_id="k1"), headers={"typ": "at+jwt"}
        )
        head = _header(token)
        assert head["typ"] == "at+jwt"
        assert head["kid"] == "k1", "the key id must survive alongside custom headers"

    def test_custom_headers_pass_through(self):
        token = PyJwtTokenSigner().sign({"sub": "u"}, _ctx(), headers={"x-tenant": "acme"})
        assert _header(token)["x-tenant"] == "acme"

    @pytest.mark.parametrize("name", ["alg", "b64", "kid"])
    def test_reserved_names_are_refused(self, name):
        with pytest.raises(ValueError, match=name):
            PyJwtTokenSigner().sign({"sub": "u"}, _ctx(), headers={name: "whatever"})

    def test_alg_in_particular_would_have_overridden_the_key_context(self):
        """Why `alg` is reserved rather than merged.

        PyJWT prefers a header value over its own `algorithm` argument, so an
        `alg` here signs with something other than KeyContext.algorithm declares -
        silently. Pinned as a fact about PyJWT, not as our behaviour.
        PyJWT ưu tiên giá trị header hơn tham số `algorithm` của chính nó.
        """
        import jwt as pyjwt_lib

        token = pyjwt_lib.encode(
            {"sub": "u"}, SECRET, algorithm="HS256", headers={"alg": "HS512"}
        )
        assert _header(token)["alg"] == "HS512"


# ----------------------------------------------------------------------
# Verification knobs
# ----------------------------------------------------------------------


class TestRequire:
    def test_a_token_with_no_exp_is_accepted_by_default(self):
        """PyJWT verifies exp only when the claim EXISTS - so it never expires."""
        token = PyJwtTokenSigner().sign({"sub": "u"}, _ctx())
        assert PyJwtTokenVerifier().verify(token, _ctx())["sub"] == "u"

    def test_require_exp_refuses_the_same_token(self):
        token = PyJwtTokenSigner().sign({"sub": "u"}, _ctx())
        with pytest.raises(AuthenticationException):
            PyJwtTokenVerifier().verify(token, _ctx(), require=["exp"])


class TestLeeway:
    def _future_token(self, seconds: int) -> str:
        issued = datetime.now(UTC) + timedelta(seconds=seconds)
        return PyJwtTokenSigner().sign(
            {"sub": "u", "iat": issued, "nbf": issued, "exp": issued + timedelta(minutes=5)},
            _ctx(),
        )

    def test_a_clock_ahead_by_seconds_rejects_a_valid_token(self):
        """The intermittent 401 nobody can reproduce, made reproducible."""
        with pytest.raises(AuthenticationException):
            PyJwtTokenVerifier().verify(self._future_token(20), _ctx())

    def test_leeway_absorbs_it(self):
        claims = PyJwtTokenVerifier().verify(self._future_token(20), _ctx(), leeway=60)
        assert claims["sub"] == "u"


class TestAlgorithmAllowList:
    def test_a_key_outside_the_allow_list_is_refused(self):
        token = PyJwtTokenSigner().sign({"sub": "u"}, _ctx())
        with pytest.raises(AuthenticationException, match="allow-list"):
            PyJwtTokenVerifier().verify(token, _ctx(), algorithms=["RS256"])

    def test_a_key_inside_it_verifies(self):
        token = PyJwtTokenSigner().sign({"sub": "u"}, _ctx())
        assert PyJwtTokenVerifier().verify(token, _ctx(), algorithms=["HS256", "RS256"])

    def test_no_allow_list_accepts_whatever_the_key_declares(self):
        """Paired with the two above: the cap must stay opt-in.

        Defaulting it to something would break every existing caller, and there
        is no list the framework could pick that is right for everyone.
        """
        token = PyJwtTokenSigner().sign({"sub": "u"}, _ctx())
        assert PyJwtTokenVerifier().verify(token, _ctx())

    def test_the_allow_list_never_widens_what_a_token_may_choose(self):
        """The cap restricts keys; it must not let a token pick from the list.

        Verification stays pinned to the candidate key's own algorithm, so a
        token declaring HS256 cannot be checked against an RS256 key just because
        both names appear in the allow-list.
        Trần này hạn chế KHOÁ; nó không được cho TOKEN tự chọn trong danh sách.
        """
        rs_key = KeyContext(algorithm="RS256", public_key_pem="not-a-real-key")
        hs_token = PyJwtTokenSigner().sign({"sub": "u"}, _ctx())
        with pytest.raises((AuthenticationException, ValueError)):
            PyJwtTokenVerifier().verify(hs_token, rs_key, algorithms=["HS256", "RS256"])
