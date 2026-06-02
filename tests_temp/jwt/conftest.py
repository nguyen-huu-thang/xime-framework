from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

from core.security import clear_security
from starters.jwt._key_context import KeyContext

UTC = timezone.utc
TEST_SECRET = "xime-unit-test-secret-do-not-use-in-production"


@pytest.fixture(autouse=True)
def clean_security_context():
    """Đảm bảo security context sạch trước và sau mỗi test."""
    clear_security()
    yield
    clear_security()


# ---------------------------------------------------------------------------
# HS256 fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hs256_context() -> KeyContext:
    return KeyContext(algorithm="HS256", secret=TEST_SECRET)


@pytest.fixture
def hs256_valid_token() -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": "user_123",
        "iat": now,
        "exp": now + timedelta(minutes=30),
    }
    return pyjwt.encode(payload, TEST_SECRET, algorithm="HS256")


@pytest.fixture
def hs256_expired_token() -> str:
    past = datetime.now(UTC) - timedelta(hours=1)
    payload = {
        "sub": "user_123",
        "iat": past - timedelta(minutes=30),
        "exp": past,
    }
    return pyjwt.encode(payload, TEST_SECRET, algorithm="HS256")


# ---------------------------------------------------------------------------
# RSA fixtures — bỏ qua nếu package 'cryptography' chưa cài
# ---------------------------------------------------------------------------

@pytest.fixture
def rsa_key_pair() -> tuple[str, str]:
    """Sinh cặp RSA 2048-bit, trả về (private_pem, public_pem)."""
    pytest.importorskip("cryptography", reason="pip install pyjwt[crypto] để chạy RSA tests")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    return private_pem, public_pem


@pytest.fixture
def rs256_contexts(rsa_key_pair) -> tuple[KeyContext, KeyContext]:
    """Trả về (signing_context, verifying_context) cho RS256."""
    private_pem, public_pem = rsa_key_pair
    signing = KeyContext(algorithm="RS256", private_key_pem=private_pem)
    verifying = KeyContext(algorithm="RS256", public_key_pem=public_pem)
    return signing, verifying
