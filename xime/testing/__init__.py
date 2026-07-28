from ._app import TestApplication
from ._fakes import FakeReadOnlyManager, FakeTransactionManager

# Empty __all__ prevents DI scanner from registering testing utilities
# as application singletons if this package is accidentally scanned.
__all__: list[str] = []
