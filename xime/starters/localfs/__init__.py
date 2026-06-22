from xime.starters.localfs._storage import LocalFileStorage

# __all__ controls which classes the DI scanner registers when a service calls
# dependency.scan("xime.starters.localfs"):
#
#   LocalFileStorage : implements storage.StorageService, RuntimeConfig injected
#                      automatically. Bind it as the StorageService backend:
#                          dependency.bind({ StorageService: LocalFileStorage })
#
# Importable directly for that binding:
#   from xime.starters.localfs import LocalFileStorage
__all__ = ["LocalFileStorage"]
