"""
Test clear_security():
  - xóa tất cả field sau khi đã gán
  - gọi trên context rỗng không raise
  - sau khi clear, authenticate() vẫn hoạt động bình thường
"""
from enum import Enum

import pytest

from core.security import (
    CredentialType,
    authenticate,
    clear_security,
    credential_type,
    credentials,
    identity,
    permissions,
)


class Permission(Enum):
    READ  = "read"
    ADMIN = "admin"


class TestClearSecurity:
    def test_clears_all_fields(self):
        authenticate(
            identity="user_1",
            credentials="secret",
            credential_type=CredentialType.TOKEN,
            permissions={Permission.ADMIN},
        )

        clear_security()

        assert identity.get() is None
        assert credentials.get() is None
        assert credential_type.get() is None
        assert permissions.get() is None

    def test_clear_on_empty_context_is_noop(self):
        clear_security()  # không raise dù context đang rỗng

    def test_clear_twice_is_noop(self):
        authenticate(identity="user_1")
        clear_security()
        clear_security()  # không raise

    def test_after_clear_can_authenticate_again(self):
        authenticate(identity="user_1", credential_type=CredentialType.TOKEN)
        clear_security()

        authenticate(identity="user_2", credential_type=CredentialType.API_KEY)

        assert identity.get() == "user_2"
        assert credential_type.get() is CredentialType.API_KEY

    @pytest.mark.asyncio
    async def test_clear_only_affects_current_task(self):
        """clear_security() xóa context của task hiện tại — không ảnh hưởng task khác."""
        import asyncio

        results: dict = {}

        async def task_persistent():
            authenticate(identity="persistent_user")
            await asyncio.sleep(0)
            results["after"] = identity.get()

        async def task_clearer():
            authenticate(identity="temp_user")
            clear_security()
            results["cleared"] = identity.get()

        await asyncio.gather(task_persistent(), task_clearer())

        assert results["after"] == "persistent_user"
        assert results["cleared"] is None


class TestIndividualFieldClear:
    def test_clear_identity_leaves_others(self):
        authenticate(
            identity="user_1",
            credentials="secret",
        )
        identity.clear()

        assert identity.get() is None
        assert credentials.get() == "secret"

    def test_clear_credentials_leaves_others(self):
        authenticate(
            identity="user_1",
            credentials="secret",
            credential_type=CredentialType.PASSWORD,
        )
        credentials.clear()

        assert credentials.get() is None
        assert identity.get() == "user_1"
        assert credential_type.get() is CredentialType.PASSWORD
