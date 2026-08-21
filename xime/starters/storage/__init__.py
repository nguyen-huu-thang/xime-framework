from xime.starters.storage._exceptions import ObjectNotFound as ObjectNotFound
from xime.starters.storage._exceptions import StorageError as StorageError
from xime.starters.storage._exceptions import UnsupportedOperation as UnsupportedOperation
from xime.starters.storage._service import StorageService as StorageService
from xime.starters.storage._service import StorageStat as StorageStat

# The `X as X` form is PEP 484's explicit re-export marker - see the note in
# xime/starters/jwt/__init__.py for why __all__ cannot serve that role here.
#
# __all__ controls which classes the DI scanner registers when a service calls
# dependency.scan("xime.starters.storage"). It is intentionally empty:
#
#   StorageService : a Protocol - the scanner skips all Protocols, and an
#                    interface has no implementation to instantiate. Bind a
#                    concrete backend (LocalFileStorage / S3FileStorage)
#                    explicitly in config/dependency.py.
#
# The names below are still importable directly for bindings and type hints:
#   from xime.starters.storage import StorageService, StorageStat, StorageError
__all__: list[str] = []
