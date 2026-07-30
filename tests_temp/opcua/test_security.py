"""Security mode mapping and its fail-fast rules (0.7)."""
import pytest

from xime.adapters.opcua._security import (
    build_security_string,
    normalize_mode,
    server_policies,
)
from xime.core.exception.framework import StartupException


class TestNormalizeMode:
    def test_accepts_the_three_documented_modes(self):
        assert normalize_mode("None") == "None"
        assert normalize_mode("Sign") == "Sign"
        assert normalize_mode("SignAndEncrypt") == "SignAndEncrypt"

    def test_is_case_insensitive(self):
        assert normalize_mode("signandencrypt") == "SignAndEncrypt"
        assert normalize_mode("  sign  ") == "Sign"

    def test_missing_means_none(self):
        assert normalize_mode(None) == "None"

    def test_unknown_mode_is_refused(self):
        with pytest.raises(StartupException, match="Invalid OPC UA security mode"):
            normalize_mode("Encrypt")


class TestSecurityString:
    def test_none_needs_no_certificate(self):
        assert build_security_string("None", None, None) is None

    def test_sign_builds_the_asyncua_string(self):
        result = build_security_string("Sign", "/c.der", "/k.pem")
        assert result == "Basic256Sha256_Sign,Sign,/c.der,/k.pem"

    def test_sign_and_encrypt_builds_the_asyncua_string(self):
        result = build_security_string("SignAndEncrypt", "/c.der", "/k.pem")
        assert result == "Basic256Sha256_SignAndEncrypt,SignAndEncrypt,/c.der,/k.pem"

    def test_missing_certificate_fails_instead_of_downgrading(self):
        # Silently falling back to an unprotected connection would defeat the
        # only purpose of asking for Sign in the first place.
        with pytest.raises(StartupException, match="needs a certificate"):
            build_security_string("SignAndEncrypt", None, None)

    def test_the_error_names_what_is_missing(self):
        with pytest.raises(StartupException, match="opcua.private_key"):
            build_security_string("Sign", "/c.der", None)


class TestServerPolicies:
    def test_none(self):
        from asyncua import ua

        assert server_policies("None") == [ua.SecurityPolicyType.NoSecurity]

    def test_sign_also_accepts_the_stronger_mode(self):
        # Refusing a client that brings MORE protection than required would be
        # perverse.
        from asyncua import ua

        policies = server_policies("Sign")
        assert ua.SecurityPolicyType.Basic256Sha256_Sign in policies
        assert ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt in policies

    def test_sign_and_encrypt_is_exclusive(self):
        from asyncua import ua

        assert server_policies("SignAndEncrypt") == [
            ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt
        ]
