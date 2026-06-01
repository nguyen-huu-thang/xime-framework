"""
Test từng security field riêng lẻ:
  identity / credentials / credential_type / permissions
  — set, get, clear, reset, giá trị mặc định, kiểu dữ liệu tùy ý
"""
from enum import Enum

import pytest

from core.security import CredentialType, credential_type, credentials, identity, permissions


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------

class TestIdentityField:
    def test_default_none(self):
        assert identity.get() is None

    def test_set_string(self):
        identity.set("user_123")
        assert identity.get() == "user_123"

    def test_set_integer_id(self):
        identity.set(42)
        assert identity.get() == 42

    def test_set_dict(self):
        payload = {"sub": "user_1", "email": "a@b.com"}
        identity.set(payload)
        assert identity.get() == payload

    def test_overwrite(self):
        identity.set("old")
        identity.set("new")
        assert identity.get() == "new"

    def test_clear(self):
        identity.set("user_x")
        identity.clear()
        assert identity.get() is None

    def test_reset_restores_previous(self):
        identity.set("outer")
        token = identity.set("inner")
        assert identity.get() == "inner"

        identity.reset(token)
        assert identity.get() == "outer"

    def test_reset_to_none(self):
        token = identity.set("user_1")
        identity.reset(token)
        assert identity.get() is None


# ---------------------------------------------------------------------------
# credentials
# ---------------------------------------------------------------------------

class TestCredentialsField:
    def test_default_none(self):
        assert credentials.get() is None

    def test_set_password_string(self):
        credentials.set("plain-password")
        assert credentials.get() == "plain-password"

    def test_set_token(self):
        credentials.set("Bearer eyJhbGciOiJIUzI1NiJ9...")
        assert credentials.get().startswith("Bearer")

    def test_set_dict_payload(self):
        payload = {"token": "abc", "issued_at": 1700000000}
        credentials.set(payload)
        assert credentials.get()["token"] == "abc"

    def test_clear(self):
        credentials.set("secret")
        credentials.clear()
        assert credentials.get() is None


# ---------------------------------------------------------------------------
# credential_type
# ---------------------------------------------------------------------------

class TestCredentialTypeField:
    def test_default_none(self):
        assert credential_type.get() is None

    def test_framework_enum_password(self):
        credential_type.set(CredentialType.PASSWORD)
        assert credential_type.get() is CredentialType.PASSWORD

    def test_framework_enum_token(self):
        credential_type.set(CredentialType.TOKEN)
        assert credential_type.get() is CredentialType.TOKEN

    def test_framework_enum_api_key(self):
        credential_type.set(CredentialType.API_KEY)
        assert credential_type.get() is CredentialType.API_KEY

    def test_framework_enum_oauth2(self):
        credential_type.set(CredentialType.OAUTH2)
        assert credential_type.get() is CredentialType.OAUTH2

    def test_framework_enum_certificate(self):
        credential_type.set(CredentialType.CERTIFICATE)
        assert credential_type.get() is CredentialType.CERTIFICATE

    def test_custom_developer_enum(self):
        class AuthMethod(Enum):
            BIOMETRIC = "biometric"
            SMS_OTP   = "sms_otp"
            MAGIC_LINK = "magic_link"

        credential_type.set(AuthMethod.BIOMETRIC)
        assert credential_type.get() is AuthMethod.BIOMETRIC

    def test_overwrite_with_different_enum(self):
        credential_type.set(CredentialType.PASSWORD)

        class AuthMethod(Enum):
            SMS_OTP = "sms_otp"

        credential_type.set(AuthMethod.SMS_OTP)
        assert credential_type.get() is AuthMethod.SMS_OTP

    def test_clear(self):
        credential_type.set(CredentialType.TOKEN)
        credential_type.clear()
        assert credential_type.get() is None


# ---------------------------------------------------------------------------
# permissions
# ---------------------------------------------------------------------------

class TestPermissionsField:
    def setup_method(self):
        class Permission(Enum):
            READ   = "read"
            WRITE  = "write"
            DELETE = "delete"
            ADMIN  = "admin"

        self.Permission = Permission

    def test_default_none(self):
        assert permissions.get() is None

    def test_set_single_permission(self):
        permissions.set({self.Permission.READ})
        assert self.Permission.READ in permissions.get()

    def test_set_multiple_permissions(self):
        permissions.set({self.Permission.READ, self.Permission.WRITE})
        perms = permissions.get()
        assert self.Permission.READ in perms
        assert self.Permission.WRITE in perms
        assert self.Permission.DELETE not in perms

    def test_set_all_permissions(self):
        all_perms = set(self.Permission)
        permissions.set(all_perms)
        assert permissions.get() == all_perms

    def test_custom_permission_enum(self):
        class AppPermission(Enum):
            VIEW_DASHBOARD = "view_dashboard"
            APPROVE_ORDER  = "approve_order"
            EXPORT_REPORT  = "export_report"

        permissions.set({AppPermission.APPROVE_ORDER, AppPermission.EXPORT_REPORT})
        perms = permissions.get()
        assert AppPermission.APPROVE_ORDER in perms
        assert AppPermission.VIEW_DASHBOARD not in perms

    def test_overwrite_permissions(self):
        permissions.set({self.Permission.READ})
        permissions.set({self.Permission.ADMIN})
        assert self.Permission.ADMIN in permissions.get()
        assert self.Permission.READ not in permissions.get()

    def test_clear(self):
        permissions.set({self.Permission.READ})
        permissions.clear()
        assert permissions.get() is None


# ---------------------------------------------------------------------------
# Các field độc lập nhau
# ---------------------------------------------------------------------------

class TestFieldsAreIndependent:
    def test_set_identity_does_not_affect_others(self):
        identity.set("user_1")
        assert credentials.get() is None
        assert credential_type.get() is None
        assert permissions.get() is None

    def test_clear_one_field_leaves_others(self):
        identity.set("user_1")
        credentials.set("secret")

        identity.clear()

        assert identity.get() is None
        assert credentials.get() == "secret"

    def test_all_fields_set_simultaneously(self):
        class Perm(Enum):
            READ = "read"

        identity.set("user_1")
        credentials.set("token")
        credential_type.set(CredentialType.TOKEN)
        permissions.set({Perm.READ})

        assert identity.get() == "user_1"
        assert credentials.get() == "token"
        assert credential_type.get() is CredentialType.TOKEN
        assert Perm.READ in permissions.get()
