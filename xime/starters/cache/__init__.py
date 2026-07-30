from xime.starters.cache._service import CacheService as CacheService

# The `X as X` form is PEP 484's explicit re-export marker — see the note in
# xime/starters/jwt/__init__.py for why __all__ cannot serve that role here.
#
# __all__ controls which classes the DI scanner registers when a service calls
# dependency.scan("xime.starters.cache"). It is intentionally empty:
#
#   CacheService : a Protocol - the scanner skips all Protocols, and an interface
#                  has no implementation to instantiate. Bind a concrete backend
#                  (e.g. RedisCacheService) explicitly in config/dependency.py.
#
# CacheService is still importable directly for use in bindings and type hints:
#   from xime.starters.cache import CacheService
__all__: list[str] = []
