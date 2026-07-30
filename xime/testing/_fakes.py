from __future__ import annotations

from typing import Any


class _FakeTransactionContext:
    """No-op async context manager returned by FakeTransactionManager."""

    async def __aenter__(self) -> _FakeTransactionContext:
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


class _FakeReadOnlyContext:
    """No-op async context manager returned by FakeReadOnlyManager."""

    async def __aenter__(self) -> _FakeReadOnlyContext:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        pass  # nothing was opened — nothing to discard


class FakeReadOnlyManager:
    """
    No-op ReadOnlyManager for unit and integration tests.

    The read-only counterpart of FakeTransactionManager. Replaces any
    ReadOnlyManager implementation without a real database, so the
    ``async with self.read_only()`` boundary in business code still works
    exactly as written.
    Bản chỉ-đọc tương ứng của FakeTransactionManager: thay implementation thật mà
    không cần database, khối ``async with self.read_only()`` trong code nghiệp vụ
    vẫn chạy y như đã viết.

    Usage with TestApplication::

        async with TestApplication(
            binding=my_binding,
            overrides={ReadOnlyManager: FakeReadOnlyManager()},
        ) as app:
            service = app.get(ProductService)
            await service.list_products()  # no DB needed
    """

    def __call__(self) -> _FakeReadOnlyContext:
        return _FakeReadOnlyContext()
