from __future__ import annotations

from contextvars import ContextVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from xime.starters.sqlalchemy.engine import AsyncEngineProvider

# Module-level ContextVar: holds the active session for the current async task.
# Set by SqlAlchemyTransactionContext.__aenter__, cleared in __aexit__.
# Repositories call AsyncSessionFactory.current() to read from here.
_current_session: ContextVar[AsyncSession | None] = ContextVar(
    "xime_sqlalchemy_session", default=None
)


class AsyncSessionFactory:
    """
    Creates AsyncSession instances and exposes the active session for the
    current async task via a ContextVar.

    Inject into repositories to access the session inside a transaction:

        class UserRepository:
            def __init__(self, sessions: AsyncSessionFactory) -> None:
                self._sessions = sessions

            async def save(self, user: UserEntity) -> None:
                session = self._sessions.current()
                session.add(user)

    The session is available only inside 'async with self.transaction():'.
    Calling current() outside a transaction raises RuntimeError.
    """

    def __init__(self, engine_provider: AsyncEngineProvider) -> None:
        self._factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine_provider.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    def create(self) -> AsyncSession:
        """Create a new AsyncSession (called by SqlAlchemyTransactionManager)."""
        return self._factory()

    @staticmethod
    def current() -> AsyncSession:
        """
        Return the active session for the current async task.
        Raises RuntimeError if called outside a transaction context.
        """
        session = _current_session.get()
        if session is None:
            raise RuntimeError(
                "No active database session. "
                "Call repository methods inside 'async with self.transaction():'."
            )
        return session
