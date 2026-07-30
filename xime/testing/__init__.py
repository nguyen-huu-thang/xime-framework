from ._app import TestApplication as TestApplication
from ._fakes import FakeReadOnlyManager as FakeReadOnlyManager
from ._fakes import FakeTransactionManager as FakeTransactionManager

# The `X as X` form is PEP 484's explicit re-export marker — see the note in
# xime/starters/jwt/__init__.py for why __all__ cannot serve that role here.
#
# Empty __all__ prevents DI scanner from registering testing utilities
# as application singletons if this package is accidentally scanned.
__all__: list[str] = []
