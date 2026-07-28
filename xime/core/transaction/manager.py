from __future__ import annotations

from typing import Protocol

from xime.core.transaction.context import TransactionContext


class TransactionManager(Protocol):
    """
    Factory that creates a TransactionContext for each unit of work.

    Implement this Protocol in a starter and register it via DI binding:
        dependency.bind({TransactionManager: SqlAlchemyTransactionManager})

    Business services receive TransactionManager through constructor injection:

        class UserService:
            def __init__(
                self,
                transaction: TransactionManager,
                repository: UserRepository,
            ) -> None:
                self.transaction = transaction
                self.repository = repository

            async def create_user(self) -> None:
                async with self.transaction():
                    await self.repository.save_user()
                    await self.repository.save_profile()

    Success flow : BEGIN → operations → COMMIT
    Error flow   : BEGIN → operation raises → ROLLBACK

    For use cases that only read, inject ReadOnlyManager instead - a separate
    sibling of this Protocol, not a method on it. See core/transaction/readonly.py.
    Usecase chỉ đọc thì inject ReadOnlyManager - anh em cùng cấp của Protocol này,
    không phải method của nó.

    Planned extensions (does not break current usage):
        async with self.transaction(isolation="SERIALIZABLE"): ...
    """

    def __call__(self) -> TransactionContext: ...
