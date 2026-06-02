"""
xime.starters.sqlalchemy — Async SQLAlchemy integration.

Usage:
    from xime.starters.sqlalchemy import Base, TimestampMixin
    from xime.starters.sqlalchemy import SqlAlchemyTransactionManager
    from xime.starters.sqlalchemy import AsyncEngineProvider, AsyncSessionFactory

Typical setup in config/dependency.py:
    dependency.scan("starters.sqlalchemy", ...)
    dependency.bind({TransactionManager: SqlAlchemyTransactionManager})
"""

from starters.sqlalchemy import (
    AsyncEngineProvider,
    AsyncSessionFactory,
    Base,
    SqlAlchemyTransactionContext,
    SqlAlchemyTransactionManager,
    TimestampMixin,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "AsyncEngineProvider",
    "AsyncSessionFactory",
    "SqlAlchemyTransactionManager",
    "SqlAlchemyTransactionContext",
]
