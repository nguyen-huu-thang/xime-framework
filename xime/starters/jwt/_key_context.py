from __future__ import annotations

from dataclasses import dataclass


@dataclass
class KeyContext:
    """Key material and algorithm for JWT signing/verification.

    Developer sets algorithm explicitly - no auto-resolution from key type.

    HMAC (symmetric):
        KeyContext(algorithm="HS256", secret="your-secret")
        KeyContext(algorithm="HS384", secret="your-secret")
        KeyContext(algorithm="HS512", secret="your-secret")

    RSA:
        KeyContext(algorithm="RS256", private_key_pem="...", public_key_pem="...")
        KeyContext(algorithm="PS256", private_key_pem="...", public_key_pem="...")

    EC:
        KeyContext(algorithm="ES256", private_key_pem="...", public_key_pem="...")
        KeyContext(algorithm="ES384", private_key_pem="...", public_key_pem="...")
        KeyContext(algorithm="ES512", private_key_pem="...", public_key_pem="...")

    EdDSA:
        KeyContext(algorithm="EdDSA", private_key_pem="...", public_key_pem="...")

    For verification-only contexts (middleware), omit private_key_pem.
    For signing-only contexts, omit public_key_pem.
    """

    algorithm: str
    key_id: str | None = None

    # HMAC algorithms (HS256 / HS384 / HS512)
    secret: str | None = None

    # Asymmetric algorithms (RS*, PS*, ES*, EdDSA)
    private_key_pem: str | None = None
    public_key_pem: str | None = None
