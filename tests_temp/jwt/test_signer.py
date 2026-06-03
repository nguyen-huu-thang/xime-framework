"""
Test PyJwtTokenSigner:
  - sign() trả về chuỗi JWT hợp lệ (3 phần cách nhau bởi dấu chấm)
  - payload claims xuất hiện đúng trong token sau decode
  - key_id được ghi vào header "kid" khi có
  - không có "kid" trong header khi key_id là None
  - custom claim được bảo toàn
  - payload khác nhau → token khác nhau
  - ValueError khi thiếu secret cho HS256
  - ValueError khi thiếu private_key_pem cho RS256
  - round-trip RS256: sign → decode bằng PyJWT trực tiếp
"""
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

from xime.starters.jwt._key_context import KeyContext
from xime.starters.jwt._signer import PyJwtTokenSigner

UTC = timezone.utc


def make_payload(sub: str = "user_1") -> dict:
    now = datetime.now(UTC)
    return {
        "sub": sub,
        "iat": now,
        "exp": now + timedelta(minutes=30),
    }


# ---------------------------------------------------------------------------
# HS256
# ---------------------------------------------------------------------------

class TestPyJwtTokenSignerHs256:
    def setup_method(self):
        self.signer = PyJwtTokenSigner()
        self.ctx = KeyContext(algorithm="HS256", secret="test-secret-key-long-enough-for-hs256-min-32bytes")

    def test_sign_returns_string(self):
        token = self.signer.sign(make_payload(), self.ctx)
        assert isinstance(token, str)

    def test_sign_produces_three_part_jwt(self):
        token = self.signer.sign(make_payload(), self.ctx)
        assert len(token.split(".")) == 3

    def test_signed_token_contains_correct_sub(self):
        token = self.signer.sign(make_payload("user_abc"), self.ctx)
        claims = pyjwt.decode(token, "test-secret-key-long-enough-for-hs256-min-32bytes", algorithms=["HS256"])
        assert claims["sub"] == "user_abc"

    def test_signed_token_contains_exp_claim(self):
        token = self.signer.sign(make_payload(), self.ctx)
        claims = pyjwt.decode(token, "test-secret-key-long-enough-for-hs256-min-32bytes", algorithms=["HS256"])
        assert "exp" in claims

    def test_signed_token_contains_iat_claim(self):
        token = self.signer.sign(make_payload(), self.ctx)
        claims = pyjwt.decode(token, "test-secret-key-long-enough-for-hs256-min-32bytes", algorithms=["HS256"])
        assert "iat" in claims

    def test_custom_claim_is_preserved(self):
        payload = make_payload()
        payload["tenant"] = "org_42"
        token = self.signer.sign(payload, self.ctx)
        claims = pyjwt.decode(token, "test-secret-key-long-enough-for-hs256-min-32bytes", algorithms=["HS256"])
        assert claims["tenant"] == "org_42"

    def test_different_payloads_produce_different_tokens(self):
        token_a = self.signer.sign(make_payload("user_A"), self.ctx)
        token_b = self.signer.sign(make_payload("user_B"), self.ctx)
        assert token_a != token_b

    def test_sign_with_key_id_adds_kid_to_header(self):
        ctx = KeyContext(algorithm="HS256", secret="test-secret-key-long-enough-for-hs256-min-32bytes", key_id="kid-2025")
        token = self.signer.sign(make_payload(), ctx)
        header = pyjwt.get_unverified_header(token)
        assert header["kid"] == "kid-2025"

    def test_sign_without_key_id_has_no_kid_in_header(self):
        token = self.signer.sign(make_payload(), self.ctx)
        header = pyjwt.get_unverified_header(token)
        assert "kid" not in header

    def test_sign_raises_value_error_when_secret_is_none(self):
        ctx = KeyContext(algorithm="HS256")  # secret=None
        with pytest.raises(ValueError, match="secret"):
            self.signer.sign(make_payload(), ctx)

    def test_sign_raises_value_error_when_secret_is_empty_string(self):
        ctx = KeyContext(algorithm="HS256", secret="")
        with pytest.raises(ValueError, match="secret"):
            self.signer.sign(make_payload(), ctx)


# ---------------------------------------------------------------------------
# Asymmetric (RS256) — bỏ qua nếu cryptography chưa cài
# ---------------------------------------------------------------------------

class TestPyJwtTokenSignerAsymmetric:
    def test_sign_raises_value_error_when_private_key_pem_is_none(self):
        signer = PyJwtTokenSigner()
        ctx = KeyContext(algorithm="RS256")  # private_key_pem=None
        with pytest.raises(ValueError, match="private_key_pem"):
            signer.sign(make_payload(), ctx)

    def test_sign_raises_value_error_when_private_key_pem_is_empty(self):
        signer = PyJwtTokenSigner()
        ctx = KeyContext(algorithm="RS256", private_key_pem="")
        with pytest.raises(ValueError, match="private_key_pem"):
            signer.sign(make_payload(), ctx)

    def test_sign_rs256_produces_valid_jwt(self, rs256_contexts):
        signing_ctx, verifying_ctx = rs256_contexts
        signer = PyJwtTokenSigner()

        token = signer.sign(make_payload("rsa_user"), signing_ctx)
        parts = token.split(".")
        assert len(parts) == 3

    def test_sign_rs256_can_be_decoded_with_public_key(self, rs256_contexts):
        signing_ctx, verifying_ctx = rs256_contexts
        signer = PyJwtTokenSigner()

        token = signer.sign(make_payload("rsa_user"), signing_ctx)
        claims = pyjwt.decode(token, verifying_ctx.public_key_pem, algorithms=["RS256"])
        assert claims["sub"] == "rsa_user"

    def test_sign_rs256_header_has_correct_algorithm(self, rs256_contexts):
        signing_ctx, _ = rs256_contexts
        signer = PyJwtTokenSigner()

        token = signer.sign(make_payload(), signing_ctx)
        header = pyjwt.get_unverified_header(token)
        assert header["alg"] == "RS256"
