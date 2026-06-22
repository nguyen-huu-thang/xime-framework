from xime.starters.storage._exceptions import (
    ObjectNotFound,
    StorageError,
    UnsupportedOperation,
)
from xime.starters.storage._service import StorageService, StorageStat

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
