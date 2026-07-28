from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from xime.core.exception.framework import XimeException
from xime.starters.sqlalchemy.base import Base
from xime.starters.sqlalchemy.session import AsyncSessionFactory

# Bound to Base so the repository only works with mapped ORM models.
# Giới hạn theo Base để repository chỉ làm việc với ORM model đã mapping.
T = TypeVar("T", bound=Base)


class EntityNotFoundError(XimeException):
    """
    Raised by CrudRepository.find_or_fail when no row matches the given id.

    A runtime data error specific to the SQLAlchemy starter — not a startup or
    DI error, so it lives here rather than in core/exception.
    Lỗi dữ liệu lúc chạy của riêng starter SQLAlchemy, không phải lỗi startup/DI.
    """

    def __init__(self, model_name: str, id_: Any) -> None:
        self.model_name = model_name
        self.id = id_
        super().__init__(f"{model_name} with id {id_!r} not found")


class CrudRepository(Generic[T], ABC):
    """
    Generic base repository providing the common CRUD operations every app
    repository needs, so they no longer hand-write the same boilerplate.
    Lớp repository nền cung cấp sẵn CRUD chung, app không phải tự viết lại.

    A concrete repository only declares the model and any custom queries:

        from xime.starters.sqlalchemy import CrudRepository

        class CategoryRepository(CrudRepository[Category]):
            model = Category

            async def find_by_slug(self, slug: str) -> Category | None:
                result = await self.session.execute(
                    select(Category).where(Category.slug == slug)
                )
                return result.scalar_one_or_none()

    Why `model` is an abstract property:
      Declaring it abstract makes CrudRepository itself abstract
      (inspect.isabstract → True), so the DI PackageScanner skips the base
      class. A subclass that sets `model = SomeEntity` (a plain class attribute)
      overrides the abstract name, becomes concrete, and IS registered — with no
      extra boilerplate beyond the `model` line it already needs.
      Khai báo `model` abstract khiến chính CrudRepository là abstract -> scanner
      bỏ qua lớp nền; subclass set `model = Entity` thành class concrete và được
      đăng ký, không tốn thêm boilerplate.

    All methods read the active session from AsyncSessionFactory.current(), so
    they must be called inside 'async with self.transaction():' (writes) or
    'async with self.read_only():' (reads).
    Mọi method đọc session đang hoạt động -> phải gọi trong 'transaction()' (ghi)
    hoặc 'read_only()' (đọc).
    """

    @property
    @abstractmethod
    def model(self) -> type[T]:
        """The ORM model class this repository manages. Set as a class attribute
        in the subclass: `model = Category`."""
        ...

    def __init__(self, sessions: AsyncSessionFactory) -> None:
        self._sessions = sessions

    @property
    def session(self) -> AsyncSession:
        """The active session for the current transaction or read-only block.

        Raises RuntimeError if accessed outside both.
        """
        return self._sessions.current()

    async def find(self, id_: Any) -> T | None:
        """Return the entity with the given primary key, or None if absent."""
        return await self.session.get(self.model, id_)

    async def find_or_fail(self, id_: Any) -> T:
        """Like find(), but raise EntityNotFoundError when no row matches."""
        entity = await self.find(id_)
        if entity is None:
            raise EntityNotFoundError(self.model.__name__, id_)
        return entity

    async def find_all(self) -> list[T]:
        """Return every row of the model."""
        result = await self.session.execute(select(self.model))
        return list(result.scalars().all())

    async def exists(self, id_: Any) -> bool:
        """Return True if a row with the given primary key exists."""
        return await self.find(id_) is not None

    async def count(self) -> int:
        """Return the total number of rows for the model."""
        result = await self.session.execute(
            select(func.count()).select_from(self.model)
        )
        return int(result.scalar_one())

    async def save(self, entity: T) -> T:
        """Add (or update) the entity and flush so it gets its generated keys."""
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def save_all(self, entities: Iterable[T]) -> list[T]:
        """Add several entities in one flush. Returns them as a list."""
        items = list(entities)
        self.session.add_all(items)
        await self.session.flush()
        return items

    async def delete(self, entity: T) -> None:
        """Delete the entity and flush the change."""
        await self.session.delete(entity)
        await self.session.flush()
