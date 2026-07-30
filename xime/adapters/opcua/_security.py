"""Mapping Xime's `security:` setting onto asyncua's policies.

OPC UA offers three levels, and the project decided to support all of them:

    None             — no signing, no encryption. Fine on an isolated
                       machine network, never over anything routable.
    Sign             — messages are signed: tampering is detected, but the
                       payload travels in clear text.
    SignAndEncrypt   — signed and encrypted.

Both Sign and SignAndEncrypt need a client certificate and private key, so a
half-configured setup fails at startup rather than silently falling back to an
unprotected connection — a fallback would be the worst possible outcome for a
setting whose entire purpose is protection.
Cấu hình nửa vời sẽ NỔ lúc startup chứ không âm thầm tụt xuống kết nối không
bảo vệ - tụt xuống là kết cục tệ nhất cho một tuỳ chọn sinh ra để bảo vệ.
"""

from __future__ import annotations

from typing import Any

from xime.core.exception.framework import StartupException

# Xime setting -> asyncua policy suffix. The concrete algorithm (Basic256Sha256)
# is the modern default; older ones exist but are deprecated by the OPC
# Foundation and not worth offering as a choice.
SECURITY_MODES = ("None", "Sign", "SignAndEncrypt")

_POLICY_NAMES = {
    "Sign": "Basic256Sha256_Sign",
    "SignAndEncrypt": "Basic256Sha256_SignAndEncrypt",
}


def normalize_mode(value: str | None) -> str:
    """Accept the mode case-insensitively and reject anything unknown."""
    if value is None:
        return "None"
    for mode in SECURITY_MODES:
        if str(value).strip().lower() == mode.lower():
            return mode
    raise StartupException(
        f"\nInvalid OPC UA security mode\n"
        f"  Value: {value!r}\n"
        f"  Fix  : use one of {', '.join(SECURITY_MODES)}."
    )


def build_security_string(
    mode: str, certificate: str | None, private_key: str | None
) -> str | None:
    """Build the string asyncua's Client.set_security_string() expects.

    Returns None for mode "None" — the caller then simply skips the call.
    Format: "<Policy>,<Mode>,<cert path>,<key path>".
    """
    mode = normalize_mode(mode)
    if mode == "None":
        return None

    missing = [
        label for label, value in (
            ("opcua.certificate", certificate), ("opcua.private_key", private_key)
        ) if not value
    ]
    if missing:
        raise StartupException(
            f"\nOPC UA security needs a certificate\n"
            f"  Mode   : {mode}\n"
            f"  Missing: {', '.join(missing)}\n"
            f"  Why    : signing and encryption are certificate-based; without\n"
            f"           one the connection could only fall back to no\n"
            f"           protection at all, which is never what 'Sign' meant.\n"
            f"  Fix    : set them in resources/application.yml, or use\n"
            f"           security: None on an isolated network."
        )

    policy = _POLICY_NAMES[mode]
    return f"{policy},{mode},{certificate},{private_key}"


def server_policies(mode: str) -> list[Any]:
    """The asyncua SecurityPolicyType list a server should accept.

    A server configured for Sign also accepts SignAndEncrypt: refusing a
    STRONGER protection than asked for would be perverse.
    Server đặt ở mức Sign vẫn nhận SignAndEncrypt - từ chối mức bảo vệ MẠNH hơn
    thì vô lý.
    """
    from asyncua import ua

    mode = normalize_mode(mode)
    if mode == "None":
        return [ua.SecurityPolicyType.NoSecurity]
    if mode == "Sign":
        return [
            ua.SecurityPolicyType.Basic256Sha256_Sign,
            ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt,
        ]
    return [ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt]
