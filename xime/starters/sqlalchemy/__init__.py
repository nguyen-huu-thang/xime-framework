# The `X as X` form is PEP 484's explicit re-export marker — see the note in
# xime/starters/jwt/__init__.py for why __all__ cannot serve that role here.
#
# The guard translates a missing dependency into a message that names the extra.
# It raises ImportError rather than the RuntimeError used by mqtt/modbus/opcua:
# those raise at ADAPTER START-UP, where ImportError would be misleading, while
# this fires at IMPORT time, where ImportError is the correct type and keeps
# `except ImportError` in caller code working.
# Guard dịch lỗi thiếu thư viện thành thông điệp có tên extra. Ném ImportError
# chứ không phải RuntimeError như mqtt/modbus/opcua: chúng ném lúc KHỞI ĐỘNG
# ADAPTER, còn chỗ này nổ lúc IMPORT - ImportError mới đúng kiểu, và giữ nguyên
# được các chỗ đang bắt `except ImportError`.
try:
    from xime.starters.sqlalchemy.base import Base as Base
    from xime.starters.sqlalchemy.base import TimestampMixin as TimestampMixin
    from xime.starters.sqlalchemy.engine import AsyncEngineProvider as AsyncEngineProvider
    from xime.starters.sqlalchemy.readonly import (
        SqlAlchemyReadOnlyContext as SqlAlchemyReadOnlyContext,
    )
    from xime.starters.sqlalchemy.readonly import (
        SqlAlchemyReadOnlyManager as SqlAlchemyReadOnlyManager,
    )
    from xime.starters.sqlalchemy.repository import CrudRepository as CrudRepository
    from xime.starters.sqlalchemy.repository import EntityNotFoundError as EntityNotFoundError
    from xime.starters.sqlalchemy.session import AsyncSessionFactory as AsyncSessionFactory
    from xime.starters.sqlalchemy.transaction import (
        SqlAlchemyTransactionContext as SqlAlchemyTransactionContext,
    )
    from xime.starters.sqlalchemy.transaction import (
        SqlAlchemyTransactionManager as SqlAlchemyTransactionManager,
    )
except ImportError as exc:  # pragma: no cover - needs an install without the extra
    # Only a missing SQLAlchemy is translated. An ImportError from anywhere else
    # is a real bug and must not be disguised as a missing dependency.
    if (exc.name or "").split(".")[0] != "sqlalchemy":
        raise
    raise ImportError(
        "The SQLAlchemy starter requires SQLAlchemy. "
        "Run: pip install 'xime[sqlalchemy]'"
    ) from exc

# __all__ controls which classes the DI scanner registers when the user calls
# dependency.scan("xime.starters.sqlalchemy"). Only DI-managed singletons appear here.
#
# Base, TimestampMixin, CrudRepository, EntityNotFoundError,
# SqlAlchemyTransactionContext, SqlAlchemyReadOnlyContext are intentionally excluded:
#   - Base / TimestampMixin  : model base classes, not injectable services
#   - CrudRepository         : abstract generic base (inspect.isabstract → True),
#     never instantiated directly; only its concrete subclasses (in the app's own
#     scanned packages) become DI singletons
#   - EntityNotFoundError    : runtime exception type, not a service
#   - SqlAlchemyTransactionContext / SqlAlchemyReadOnlyContext : per-block objects
#     created by __call__(), not singletons — their session dep is never in the
#     DI container
#
# All classes are still importable directly:
#   from xime.starters.sqlalchemy import Base, CrudRepository
__all__ = [
    "AsyncEngineProvider",
    "AsyncSessionFactory",
    "SqlAlchemyReadOnlyManager",
    "SqlAlchemyTransactionManager",
]
