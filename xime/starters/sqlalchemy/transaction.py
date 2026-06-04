from __future__ import annotations

from contextvars import Token
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from xime.starters.sqlalchemy.session import AsyncSessionFactory, _current_session


class SqlAlchemyTransactionContext:
    """
    Async context manager for a single database transaction.

    On enter : sets the active session in the ContextVar, begins a transaction.
    On exit  : commits on success, rolls back on any exception, closes the session,
               and restores the ContextVar to its previous state.

    Created by SqlAlchemyTransactionManager.__call__() — not used directly.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._token: Token[AsyncSession | None] | None = None

    async def __aenter__(self) -> "SqlAlchemyTransactionContext":
        self._token = _current_session.set(self._session)
        try:
            await self._session.begin()
        except BaseException:
            # begin() raised before the transaction opened — __aexit__ will NOT
            # be called, so we must restore the ContextVar manually here.
            _current_session.reset(self._token)
            self._token = None
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        try:
            if exc_type is None:
                await self._session.commit()
            else:
                await self._session.rollback()
        finally:
            await self._session.close()
            if self._token is not None:
                _current_session.reset(self._token)


class SqlAlchemyTransactionManager:
    """
    Implementation of TransactionManager for SQLAlchemy AsyncSession.

    Bind in config/dependency.py:
        from xime.core.transaction import TransactionManager
        from xime.starters.sqlalchemy import SqlAlchemyTransactionManager

        dependency.bind({TransactionManager: SqlAlchemyTransactionManager})

    Usage in business layer (via TransactionManager Protocol):
        class UserService:
            def __init__(
                self,
                transaction: TransactionManager,
                repository: UserRepository,
            ) -> None:
                self.transaction = transaction
                self.repository = repository

            async def create_user(self, name: str) -> None:
                async with self.transaction():
                    await self.repository.save(UserEntity(name=name))
    """

    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._factory = session_factory

    def __call__(self) -> SqlAlchemyTransactionContext:
        return SqlAlchemyTransactionContext(self._factory.create())
