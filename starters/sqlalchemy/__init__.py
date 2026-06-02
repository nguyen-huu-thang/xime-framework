from starters.sqlalchemy.base import Base, TimestampMixin
from starters.sqlalchemy.engine import AsyncEngineProvider
from starters.sqlalchemy.session import AsyncSessionFactory
from starters.sqlalchemy.transaction import SqlAlchemyTransactionContext, SqlAlchemyTransactionManager

# __all__ controls which classes the DI scanner registers when the user calls
# dependency.scan("starters.sqlalchemy"). Only DI-managed singletons appear here.
#
# Base, TimestampMixin, SqlAlchemyTransactionContext are intentionally excluded:
#   - Base / TimestampMixin  : model base classes, not injectable services
#   - SqlAlchemyTransactionContext : per-transaction object created by __call__(),
#     not a singleton — its AsyncSession dep is never in the DI container
#
# All classes are still importable directly:
#   from starters.sqlalchemy import Base, SqlAlchemyTransactionContext
__all__ = [
    "AsyncEngineProvider",
    "AsyncSessionFactory",
    "SqlAlchemyTransactionManager",
]
