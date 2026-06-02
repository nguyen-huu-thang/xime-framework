"""
Test KeyContext:
  - tất cả field có giá trị mặc định đúng
  - cấu hình HMAC: secret + algorithm
  - cấu hình asymmetric: private + public key
  - cấu hình verify-only (chỉ public_key_pem)
  - cấu hình sign-only (chỉ private_key_pem)
  - key_id được lưu đúng
"""
from starters.jwt._key_context import KeyContext


class TestKeyContextDefaults:
    def test_key_id_defaults_to_none(self):
        ctx = KeyContext(algorithm="HS256")
        assert ctx.key_id is None

    def test_secret_defaults_to_none(self):
        ctx = KeyContext(algorithm="HS256")
        assert ctx.secret is None

    def test_private_key_pem_defaults_to_none(self):
        ctx = KeyContext(algorithm="RS256")
        assert ctx.private_key_pem is None

    def test_public_key_pem_defaults_to_none(self):
        ctx = KeyContext(algorithm="RS256")
        assert ctx.public_key_pem is None


class TestKeyContextHmac:
    def test_hs256_stores_algorithm(self):
        ctx = KeyContext(algorithm="HS256", secret="my-secret")
        assert ctx.algorithm == "HS256"

    def test_hs384_stores_algorithm(self):
        ctx = KeyContext(algorithm="HS384", secret="my-secret")
        assert ctx.algorithm == "HS384"

    def test_hs512_stores_algorithm(self):
        ctx = KeyContext(algorithm="HS512", secret="my-secret")
        assert ctx.algorithm == "HS512"

    def test_secret_is_stored(self):
        ctx = KeyContext(algorithm="HS256", secret="super-secret")
        assert ctx.secret == "super-secret"

    def test_key_id_is_stored(self):
        ctx = KeyContext(algorithm="HS256", secret="s", key_id="kid-2025")
        assert ctx.key_id == "kid-2025"


class TestKeyContextAsymmetric:
    def test_rs256_with_both_keys(self):
        ctx = KeyContext(
            algorithm="RS256",
            private_key_pem="-----BEGIN RSA PRIVATE KEY-----",
            public_key_pem="-----BEGIN PUBLIC KEY-----",
        )
        assert ctx.algorithm == "RS256"
        assert ctx.private_key_pem is not None
        assert ctx.public_key_pem is not None

    def test_es256_algorithm(self):
        ctx = KeyContext(algorithm="ES256", private_key_pem="-----BEGIN EC PRIVATE KEY-----")
        assert ctx.algorithm == "ES256"

    def test_verify_only_context_has_no_private_key(self):
        """Middleware chỉ cần public key để verify — không cần private key."""
        ctx = KeyContext(
            algorithm="RS256",
            public_key_pem="-----BEGIN PUBLIC KEY-----",
        )
        assert ctx.private_key_pem is None
        assert ctx.public_key_pem is not None

    def test_sign_only_context_has_no_public_key(self):
        """Token service chỉ cần private key để ký — không cần public key."""
        ctx = KeyContext(
            algorithm="ES256",
            private_key_pem="-----BEGIN EC PRIVATE KEY-----",
        )
        assert ctx.private_key_pem is not None
        assert ctx.public_key_pem is None

    def test_key_id_on_asymmetric_context(self):
        ctx = KeyContext(
            algorithm="RS256",
            private_key_pem="key",
            key_id="rsa-key-2025",
        )
        assert ctx.key_id == "rsa-key-2025"
