"""
Test authenticate():
  - gán đầy đủ / một phần / không truyền field nào
  - không ghi đè field đã có khi không truyền
  - hoạt động với enum tùy chỉnh của developer
"""
from enum import Enum

from xime.core.security import (
    CredentialType,
    authenticate,
    credential_type,
    credentials,
    identity,
    permissions,
)


class Permission(Enum):
    READ   = "read"
    WRITE  = "write"
    DELETE = "delete"
    ADMIN  = "admin"


class TestAuthenticateFullSet:
    def test_sets_identity(self):
        authenticate(identity="user_99")
        assert identity.get() == "user_99"

    def test_sets_credentials(self):
        authenticate(credentials="Bearer token-abc")
        assert credentials.get() == "Bearer token-abc"

    def test_sets_credential_type(self):
        authenticate(credential_type=CredentialType.TOKEN)
        assert credential_type.get() is CredentialType.TOKEN

    def test_sets_permissions(self):
        authenticate(permissions={Permission.READ, Permission.WRITE})
        perms = permissions.get()
        assert Permission.READ in perms
        assert Permission.WRITE in perms

    def test_sets_all_at_once(self):
        authenticate(
            identity="user_1",
            credentials="secret",
            credential_type=CredentialType.PASSWORD,
            permissions={Permission.ADMIN},
        )
        assert identity.get() == "user_1"
        assert credentials.get() == "secret"
        assert credential_type.get() is CredentialType.PASSWORD
        assert Permission.ADMIN in permissions.get()


class TestAuthenticatePartialSet:
    def test_omitted_fields_stay_none_when_fresh(self):
        authenticate(identity="user_1")
        assert credentials.get() is None
        assert credential_type.get() is None
        assert permissions.get() is None

    def test_omitted_fields_do_not_overwrite_existing(self):
        """Gọi authenticate() lần 2 chỉ với một field → các field khác giữ nguyên."""
        authenticate(
            identity="user_1",
            permissions={Permission.READ},
        )
        # Lần 2 chỉ cập nhật credential_type
        authenticate(credential_type=CredentialType.TOKEN)

        assert identity.get() == "user_1"            # giữ nguyên
        assert Permission.READ in permissions.get()  # giữ nguyên
        assert credential_type.get() is CredentialType.TOKEN  # mới

    def test_call_twice_overwrites_field(self):
        authenticate(identity="user_old")
        authenticate(identity="user_new")
        assert identity.get() == "user_new"

    def test_no_arguments_is_noop(self):
        """authenticate() không có tham số không thay đổi gì."""
        identity.set("existing")
        authenticate()
        assert identity.get() == "existing"


class TestAuthenticateWithCustomEnums:
    def test_custom_credential_type(self):
        class AuthMethod(Enum):
            MAGIC_LINK = "magic_link"

        authenticate(identity="user_x", credential_type=AuthMethod.MAGIC_LINK)
        assert credential_type.get() is AuthMethod.MAGIC_LINK

    def test_custom_permission_enum(self):
        class AppPermission(Enum):
            VIEW_REPORT    = "view_report"
            APPROVE_BUDGET = "approve_budget"

        authenticate(
            identity="manager_1",
            permissions={AppPermission.VIEW_REPORT, AppPermission.APPROVE_BUDGET},
        )
        perms = permissions.get()
        assert AppPermission.APPROVE_BUDGET in perms

    def test_identity_as_integer(self):
        authenticate(identity=42)
        assert identity.get() == 42

    def test_identity_as_dict(self):
        payload = {"sub": "uuid-abc", "tenant": "org_1"}
        authenticate(identity=payload)
        assert identity.get()["tenant"] == "org_1"
