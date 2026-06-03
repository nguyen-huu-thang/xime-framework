from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, MappedColumn, mapped_column


class Base(DeclarativeBase):
    """
    Base class for all ORM models.

    Inherit from this to register a model with SQLAlchemy's metadata:

        from xime.starters.sqlalchemy import Base

        class UserEntity(Base):
            __tablename__ = "users"
            id: MappedColumn[int] = mapped_column(primary_key=True)
            name: MappedColumn[str] = mapped_column(nullable=False)
    """


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at columns.

    Use alongside Base:

        class UserEntity(TimestampMixin, Base):
            __tablename__ = "users"
            ...
    """

    created_at: MappedColumn[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: MappedColumn[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
