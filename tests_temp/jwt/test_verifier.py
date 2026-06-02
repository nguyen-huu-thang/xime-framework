"""
Test PyJwtTokenVerifier:
  - verify() trả về claims dict từ token hợp lệ
  - verify() trả về đầy đủ claims (cả standard lẫn custom)
  - verify() raise AuthenticationException khi token hết hạn (message có "expired")
  - verify() raise AuthenticationException khi sai secret/chữ ký (message có "Invalid token")
  - verify() raise AuthenticationException khi token bị cắt hoặc sai format
  - verify() raise AuthenticationException khi chuỗi rỗng
  - verify() raise ValueError khi KeyContext thiếu secret cho HS256
  - verify() raise ValueError khi KeyContext thiếu public_key_pem cho RS256
  - round-trip: sign bằng PyJwtTokenSigner → verify → claims đúng
  - round-trip RS256: sign → verify asymmetric
"""
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

from core.exception.framework import AuthenticationException
from starters.jwt._key_context import KeyContext
from starters.jwt._verifier import PyJwtTokenVerifier

UTC = timezone.utc
TEST_SECRET = "verifier-test-secret-long-enough-for-hs256-min-32bytes"


def make_token(
    sub: str = "user_1",
    secret: str = TEST_SECRET,
    expire_minutes: int = 30,
    extra: dict | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict = {"sub": sub, "iat": now, "exp": now + timedelta(minutes=expire_minutes)}
    if extra:
        payload.update(extra)
    return pyjwt.encode(payload, secret, algorithm="HS256")


def make_expired_token(secret: str = TEST_SECRET) -> str:
    past = datetime.now(UTC) - timedelta(hours=1)
    payload = {
        "sub": "user_1",
        "iat": past - timedelta(minutes=30),
        "exp": past,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# HS256 — happy path
# ---------------------------------------------------------------------------

class TestPyJwtTokenVerifierHs256ValidToken:
    def setup_method(self):
        self.verifier = PyJwtTokenVerifier()
        self.ctx = KeyContext(algorithm="HS256", secret=TEST_SECRET)

    def test_verify_returns_dict(self):
        token = make_token()
        result = self.verifier.verify(token, self.ctx)
        assert isinstance(result, dict)

    def test_verify_returns_correct_sub(self):
        token = make_token(sub="user_abc")
        claims = self.verifier.verify(token, self.ctx)
        assert claims["sub"] == "user_abc"

    def test_verify_returns_standard_claims(self):
        token = make_token()
        claims = self.verifier.verify(token, self.ctx)
        assert "sub" in claims
        assert "iat" in claims
        assert "exp" in claims

    def test_verify_returns_custom_claims(self):
        token = make_token(extra={"tenant": "org_99", "roles": ["admin", "user"]})
        claims = self.verifier.verify(token, self.ctx)
        assert claims["tenant"] == "org_99"
        assert claims["roles"] == ["admin", "user"]


# ---------------------------------------------------------------------------
# HS256 — error cases
# ---------------------------------------------------------------------------

class TestPyJwtTokenVerifierHs256Errors:
    def setup_method(self):
        self.verifier = PyJwtTokenVerifier()
        self.ctx = KeyContext(algorithm="HS256", secret=TEST_SECRET)

    def test_expired_token_raises_authentication_exception(self):
        token = make_expired_token()
        with pytest.raises(AuthenticationException):
            self.verifier.verify(token, self.ctx)

    def test_expired_token_message_contains_expired(self):
        token = make_expired_token()
        with pytest.raises(AuthenticationException) as exc_info:
            self.verifier.verify(token, self.ctx)
        assert "expired" in exc_info.value.message.lower()

    def test_wrong_secret_raises_authentication_exception(self):
        token = make_token(secret="correct-secret-long-enough-for-hs256-min-32bytes")
        wrong_ctx = KeyContext(algorithm="HS256", secret="wrong-secret-long-enough-for-hs256-32bytes")
        with pytest.raises(AuthenticationException) as exc_info:
            self.verifier.verify(token, wrong_ctx)
        assert "Invalid token" in exc_info.value.message

    def test_malformed_token_raises_authentication_exception(self):
        with pytest.raises(AuthenticationException):
            self.verifier.verify("not.a.valid.token", self.ctx)

    def test_empty_string_raises_authentication_exception(self):
        with pytest.raises(AuthenticationException):
            self.verifier.verify("", self.ctx)

    def test_garbage_string_raises_authentication_exception(self):
        with pytest.raises(AuthenticationException):
            self.verifier.verify("completely-invalid-string", self.ctx)

    def test_missing_secret_raises_value_error(self):
        ctx = KeyContext(algorithm="HS256")  # secret=None
        with pytest.raises(ValueError, match="secret"):
            self.verifier.verify(make_token(), ctx)

    def test_empty_secret_raises_value_error(self):
        ctx = KeyContext(algorithm="HS256", secret="")
        with pytest.raises(ValueError, match="secret"):
            self.verifier.verify(make_token(), ctx)

    def test_algorithm_mismatch_raises_authentication_exception(self):
        """Token ký bằng secret khác algorithm — vẫn là invalid token."""
        token_with_different_algo = pyjwt.encode(
            {"sub": "u", "exp": datetime.now(UTC) + timedelta(minutes=5)},
            TEST_SECRET,
            algorithm="HS384",  # ký bằng HS384
        )
        # verify với ctx HS256 → không hợp lệ
        with pytest.raises(AuthenticationException):
            self.verifier.verify(token_with_different_algo, self.ctx)


# ---------------------------------------------------------------------------
# Round-trip HS256: signer → verifier
# ---------------------------------------------------------------------------

class TestPyJwtTokenVerifierRoundTrip:
    def test_sign_then_verify_preserves_sub(self):
        from starters.jwt._signer import PyJwtTokenSigner

        ctx = KeyContext(algorithm="HS256", secret="round-trip-secret-long-enough-for-hs256-32bytes")
        now = datetime.now(UTC)
        payload = {
            "sub": "round_trip_user",
            "iat": now,
            "exp": now + timedelta(minutes=15),
        }

        token = PyJwtTokenSigner().sign(payload, ctx)
        claims = PyJwtTokenVerifier().verify(token, ctx)
        assert claims["sub"] == "round_trip_user"

    def test_sign_then_verify_preserves_custom_claims(self):
        from starters.jwt._signer import PyJwtTokenSigner

        ctx = KeyContext(algorithm="HS256", secret="round-trip-secret-long-enough-for-hs256-32bytes")
        now = datetime.now(UTC)
        payload = {
            "sub": "u1",
            "iat": now,
            "exp": now + timedelta(minutes=15),
            "dept": "engineering",
            "level": 3,
        }

        token = PyJwtTokenSigner().sign(payload, ctx)
        claims = PyJwtTokenVerifier().verify(token, ctx)
        assert claims["dept"] == "engineering"
        assert claims["level"] == 3


# ---------------------------------------------------------------------------
# RS256 — bỏ qua nếu cryptography chưa cài
# ---------------------------------------------------------------------------

class TestPyJwtTokenVerifierRs256:
    def test_verify_rs256_token_returns_correct_claims(self, rs256_contexts):
        from starters.jwt._signer import PyJwtTokenSigner

        signing_ctx, verifying_ctx = rs256_contexts
        now = datetime.now(UTC)
        payload = {"sub": "rsa_user", "iat": now, "exp": now + timedelta(minutes=5)}

        token = PyJwtTokenSigner().sign(payload, signing_ctx)
        claims = PyJwtTokenVerifier().verify(token, verifying_ctx)
        assert claims["sub"] == "rsa_user"

    def test_verify_rs256_with_hs256_token_raises_authentication_exception(self, rs256_contexts):
        """Token ký bằng HS256 không thể verify bằng RS256 public key."""
        _, verifying_ctx = rs256_contexts
        hs256_token = make_token()
        with pytest.raises(AuthenticationException):
            PyJwtTokenVerifier().verify(hs256_token, verifying_ctx)

    def test_missing_public_key_pem_raises_value_error(self):
        ctx = KeyContext(algorithm="RS256")  # public_key_pem=None
        with pytest.raises(ValueError, match="public_key_pem"):
            PyJwtTokenVerifier().verify("any.token.here", ctx)

    def test_empty_public_key_pem_raises_value_error(self):
        ctx = KeyContext(algorithm="RS256", public_key_pem="")
        with pytest.raises(ValueError, match="public_key_pem"):
            PyJwtTokenVerifier().verify("any.token.here", ctx)
