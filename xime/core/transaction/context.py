from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TransactionContext(Protocol):
    """
    Async context manager wrapping a single unit of work.

    Entering begins a transaction; exiting commits on success or rolls back
    on any exception. Implementations live in starters (e.g. starters/sqlalchemy/).

    Usage - obtained by calling TransactionManager:
        async with self.transaction():
            await self.repository.save_user()
            await self.repository.save_profile()
    """

    async def __aenter__(self) -> TransactionContext: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None: ...
