from __future__ import annotations

from contextvars import Token
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from xime.starters.sqlalchemy.session import AsyncSessionFactory, _current_session


class SqlAlchemyReadOnlyContext:
    """
    Async context manager for a read-only unit of work.

    On enter : reuses the session already in flight if there is one; otherwise
               opens a fresh session and publishes it in the ContextVar so
               repositories can find it.
    On exit  : detaches every entity, discards the session without committing,
               and restores the ContextVar. A no-op when the session was
               borrowed from an enclosing block.

    Created by SqlAlchemyReadOnlyManager.__call__() - not used directly.

    Two details worth knowing:

    No explicit begin(). SQLAlchemy autobegins on the first statement, so a
    block that ends up reading nothing never checks out a connection at all.
    Không gọi begin() tường minh: SQLAlchemy tự mở transaction ở câu lệnh đầu,
    nên khối không đọc gì thì không hề lấy connection ra khỏi pool.

    expunge_all() before rollback. rollback() expires every object the session
    still owns, so touching one of their attributes after the block raises
    DetachedInstanceError instead of returning the value that was already read.
    Detaching first leaves the loaded values intact, so entities stay usable
    after the block - matching how they behave after a committed transaction.
    Gọi expunge_all() trước rollback: rollback làm hết object trong session bị
    expire, nên chạm vào attribute của chúng sau khi ra khỏi block sẽ ném
    DetachedInstanceError thay vì trả về giá trị vốn đã đọc được. Gỡ ra trước thì
    giá trị đã nạp còn nguyên, entity vẫn dùng được sau khi ra khỏi block -
    giống như sau một transaction đã commit.
    """

    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._factory = session_factory
        self._session: AsyncSession | None = None
        self._token: Token[AsyncSession | None] | None = None

    async def __aenter__(self) -> "SqlAlchemyReadOnlyContext":
        # Nested inside a transaction or another read-only block: borrow that
        # session and leave its lifecycle to whoever opened it.
        # Lồng trong transaction hoặc khối chỉ-đọc khác: mượn session đó, vòng
        # đời để người mở lo.
        if _current_session.get() is not None:
            return self

        session = self._factory.create()
        self._session = session
        self._token = _current_session.set(session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        session = self._session
        if session is None:
            return  # borrowed session - nothing of ours to clean up

        try:
            session.expunge_all()
            await session.rollback()
        finally:
            await session.close()
            if self._token is not None:
                _current_session.reset(self._token)
            self._session = None
            self._token = None


class SqlAlchemyReadOnlyManager:
    """
    Implementation of ReadOnlyManager for SQLAlchemy AsyncSession.

    Bind in config/dependency.py next to the transaction manager:
        from xime.core.transaction import ReadOnlyManager, TransactionManager
        from xime.starters.sqlalchemy import (
            SqlAlchemyReadOnlyManager,
            SqlAlchemyTransactionManager,
        )

        dependency.bind({
            TransactionManager: SqlAlchemyTransactionManager,
            ReadOnlyManager: SqlAlchemyReadOnlyManager,
        })

    Usage in business layer (via ReadOnlyManager Protocol):
        class ProductService:
            def __init__(
                self,
                read_only: ReadOnlyManager,
                products: ProductRepository,
            ) -> None:
                self.read_only = read_only
                self.products = products

            async def list_products(self) -> list[Product]:
                async with self.read_only():
                    return await self.products.find_all()

    Both managers share one AsyncSessionFactory today, so reads and writes hit
    the same engine. Pointing reads at a replica means binding ReadOnlyManager
    to a different implementation - no business code changes.
    Hiện hai manager dùng chung một AsyncSessionFactory nên đọc và ghi cùng
    engine. Muốn đọc từ replica thì bind ReadOnlyManager sang implementation
    khác, code nghiệp vụ không phải sửa.
    """

    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._factory = session_factory

    def __call__(self) -> SqlAlchemyReadOnlyContext:
        return SqlAlchemyReadOnlyContext(self._factory)
