from xime.starters.sqlalchemy.base import Base, TimestampMixin
from xime.starters.sqlalchemy.engine import AsyncEngineProvider
from xime.starters.sqlalchemy.repository import CrudRepository, EntityNotFoundError
from xime.starters.sqlalchemy.session import AsyncSessionFactory
from xime.starters.sqlalchemy.transaction import SqlAlchemyTransactionContext, SqlAlchemyTransactionManager

# __all__ controls which classes the DI scanner registers when the user calls
# dependency.scan("xime.starters.sqlalchemy"). Only DI-managed singletons appear here.
#
# Base, TimestampMixin, CrudRepository, EntityNotFoundError,
# SqlAlchemyTransactionContext are intentionally excluded:
#   - Base / TimestampMixin  : model base classes, not injectable services
#   - CrudRepository         : abstract generic base (inspect.isabstract → True),
#     never instantiated directly; only its concrete subclasses (in the app's own
#     scanned packages) become DI singletons
#   - EntityNotFoundError    : runtime exception type, not a service
#   - SqlAlchemyTransactionContext : per-transaction object created by __call__(),
#     not a singleton — its AsyncSession dep is never in the DI container
#
# All classes are still importable directly:
#   from xime.starters.sqlalchemy import Base, CrudRepository
__all__ = [
    "AsyncEngineProvider",
    "AsyncSessionFactory",
    "SqlAlchemyTransactionManager",
]
