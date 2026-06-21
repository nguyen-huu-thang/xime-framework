from xime.starters.redis._cache import RedisCacheService
from xime.starters.redis._client import RedisClientProvider

# __all__ controls which classes the DI scanner registers when a service calls
# dependency.scan("xime.starters.redis"). Both are framework-managed singletons:
#
#   RedisClientProvider : owns the async client + connection pool, RuntimeConfig
#                         injected automatically, pre_destroy closes the pool.
#   RedisCacheService   : implements cache.CacheService, takes the provider.
#
# Both are importable directly for bindings:
#   from xime.starters.redis import RedisCacheService, RedisClientProvider
__all__ = [
    "RedisClientProvider",
    "RedisCacheService",
]
