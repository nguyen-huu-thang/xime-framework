from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CacheService(Protocol):
    """
    Backend-neutral contract for a key/value cache.

    Define this once; bind a concrete backend in config/dependency.py, e.g.

        dependency.bind({ CacheService: RedisCacheService })

    and inject CacheService wherever caching is needed:

        class TokenService:
            def __init__(self, cache: CacheService) -> None:
                self._cache = cache

    Values are raw bytes by design. The framework does not impose a
    serialization policy - callers encode/decode (JSON, pickle, msgpack, plain
    UTF-8) however their domain requires. This keeps the contract small and the
    backend dumb.
    Giá trị là bytes thô có chủ đích. Framework không áp đặt serialize - caller
    tự encode/decode. Giữ contract gọn và backend "ngu".

    TTL is expressed in whole seconds; None means the entry never expires.
    TTL tính bằng giây nguyên; None nghĩa là không hết hạn.
    """

    async def get(self, key: str) -> bytes | None:
        """Return the stored value, or None if the key is absent/expired."""
        ...

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        """Store value under key. If ttl is given, the entry expires after
        that many seconds; otherwise it persists until deleted."""
        ...

    async def delete(self, key: str) -> None:
        """Remove the key. A no-op if the key does not exist."""
        ...

    async def exists(self, key: str) -> bool:
        """Return True if the key is present (and not expired)."""
        ...
