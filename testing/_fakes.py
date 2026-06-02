from __future__ import annotations

from typing import Any


class _FakeTransactionContext:
    """No-op async context manager returned by FakeTransactionManager."""

    async def __aenter__(self) -> "_FakeTransactionContext":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        pass  # no commit, no rollback — nothing to do


class FakeTransactionManager:
    """
    No-op TransactionManager for unit and integration tests.

    Replaces any TransactionManager implementation without requiring a real
    database connection. The ``async with self.transaction()`` boundary in
    business code still works exactly as written — entering and exiting raise
    no errors, but no actual database work occurs.

    Usage with TestApplication::

        async with TestApplication(
            binding=my_binding,
            overrides={TransactionManager: FakeTransactionManager()},
        ) as app:
            service = app.get(UserService)
            await service.create_user("Alice")  # no DB needed

    To track how many transactions were opened, subclass and count calls::

        class CountingTransactionManager(FakeTransactionManager):
            def __init__(self) -> None:
                self.call_count = 0

            def __call__(self) -> _FakeTransactionContext:
                self.call_count += 1
                return super().__call__()
    """

    def __call__(self) -> _FakeTransactionContext:
        return _FakeTransactionContext()
