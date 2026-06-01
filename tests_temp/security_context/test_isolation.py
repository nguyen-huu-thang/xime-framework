"""
Test isolation giữa các async task:
  - mỗi task có ContextVar riêng
  - task con kế thừa context từ task cha tại thời điểm tạo
  - task anh em không ảnh hưởng nhau
"""
import asyncio
from enum import Enum

import pytest

from core.security import authenticate, clear_security, credential_type, identity, permissions
from core.security import CredentialType


class Permission(Enum):
    READ  = "read"
    ADMIN = "admin"


class TestSiblingTaskIsolation:
    @pytest.mark.asyncio
    async def test_sibling_tasks_do_not_share_context(self):
        results: dict = {}

        async def task_a():
            authenticate(identity="user_A")
            await asyncio.sleep(0)
            results["a"] = identity.get()

        async def task_b():
            await asyncio.sleep(0)
            results["b"] = identity.get()   # không authenticate → None

        await asyncio.gather(task_a(), task_b())

        assert results["a"] == "user_A"
        assert results["b"] is None

    @pytest.mark.asyncio
    async def test_each_task_has_independent_context(self):
        results: dict = {}

        async def make_task(user_id: str, key: str):
            authenticate(identity=user_id)
            await asyncio.sleep(0)
            results[key] = identity.get()

        await asyncio.gather(
            make_task("user_1", "t1"),
            make_task("user_2", "t2"),
            make_task("user_3", "t3"),
        )

        assert results["t1"] == "user_1"
        assert results["t2"] == "user_2"
        assert results["t3"] == "user_3"

    @pytest.mark.asyncio
    async def test_clear_in_one_task_does_not_affect_another(self):
        results: dict = {}

        async def task_a():
            authenticate(identity="user_A")
            await asyncio.sleep(0)
            results["a_before"] = identity.get()

        async def task_b():
            authenticate(identity="user_B")
            clear_security()                    # clear trong task_b
            await asyncio.sleep(0)
            results["b_after"] = identity.get()

        await asyncio.gather(task_a(), task_b())

        assert results["a_before"] == "user_A"  # task_a không bị ảnh hưởng
        assert results["b_after"] is None        # task_b đã clear

    @pytest.mark.asyncio
    async def test_permissions_isolated_per_task(self):
        results: dict = {}

        async def admin_task():
            authenticate(permissions={Permission.ADMIN})
            await asyncio.sleep(0)
            results["admin"] = permissions.get()

        async def reader_task():
            authenticate(permissions={Permission.READ})
            await asyncio.sleep(0)
            results["reader"] = permissions.get()

        await asyncio.gather(admin_task(), reader_task())

        assert Permission.ADMIN in results["admin"]
        assert Permission.ADMIN not in results["reader"]
        assert Permission.READ in results["reader"]


class TestChildTaskInheritance:
    @pytest.mark.asyncio
    async def test_child_task_inherits_parent_context_at_creation(self):
        """
        Task con được tạo SAU KHI parent authenticate() → con thừa hưởng context đó.
        Đây là hành vi mặc định của Python ContextVar.
        """
        authenticate(identity="parent_user")

        result: dict = {}

        async def child():
            result["identity"] = identity.get()

        await asyncio.create_task(child())

        assert result["identity"] == "parent_user"

    @pytest.mark.asyncio
    async def test_child_modification_does_not_affect_parent(self):
        """
        Task con thay đổi context không ảnh hưởng lại task cha.
        """
        authenticate(identity="parent_user")

        async def child():
            authenticate(identity="child_user")   # ghi đè trong task con

        await asyncio.create_task(child())

        # Task cha vẫn giữ context gốc
        assert identity.get() == "parent_user"
