from xime.starters.s3._client import S3ClientProvider
from xime.starters.s3._storage import S3FileStorage

# __all__ controls which classes the DI scanner registers when a service calls
# dependency.scan("xime.starters.s3"). Both are framework-managed singletons:
#
#   S3ClientProvider : owns the async S3 client + connection pool. RuntimeConfig
#                      injected automatically; post_construct opens the client,
#                      pre_destroy closes it.
#   S3FileStorage    : implements storage.StorageService, takes the provider.
#                      Bind it as the StorageService backend:
#                          dependency.bind({ StorageService: S3FileStorage })
#
# Both are importable directly for that binding:
#   from xime.starters.s3 import S3FileStorage, S3ClientProvider
__all__ = [
    "S3ClientProvider",
    "S3FileStorage",
]
