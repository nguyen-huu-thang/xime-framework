from __future__ import annotations

from xime.starters.redis._client import RedisClientProvider


class RedisCacheService:
    """
    Redis-backed implementation of CacheService (xime.starters.cache).

    Bind it in config/dependency.py:
        from xime.starters.cache import CacheService
        from xime.starters.redis import RedisCacheService

        dependency.scan("xime.starters.redis")
        dependency.bind({ CacheService: RedisCacheService })

    Does not inherit the CacheService Protocol (structural typing) - the
    framework validates conformance at startup when the binding is resolved.
    Không kế thừa Protocol CacheService (structural typing) - framework validate
    lúc startup khi resolve binding.

    Values are stored and returned as raw bytes; serialization is the caller's
    responsibility, per the CacheService contract.
    Giá trị là bytes thô; serialize do caller lo, theo contract CacheService.
    """

    def __init__(self, provider: RedisClientProvider) -> None:
        # Use the provider (not a raw client) so the connection-pool lifecycle
        # stays owned by RedisClientProvider (pre_destroy closes it).
        # Dùng provider (không phải client thô) để vòng đời pool nằm gọn ở provider.
        self._provider = provider

    async def get(self, key: str) -> bytes | None:
        return await self._provider.client.get(key)

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        # redis-py maps ex=<seconds> to the SET ... EX option; None → no expiry.
        # ex=<giây> tương ứng SET ... EX; None → không hết hạn.
        await self._provider.client.set(key, value, ex=ttl)

    async def delete(self, key: str) -> None:
        await self._provider.client.delete(key)

    async def exists(self, key: str) -> bool:
        # redis EXISTS returns the count of matching keys; normalise to bool.
        # EXISTS trả số key khớp; chuẩn hoá về bool.
        return bool(await self._provider.client.exists(key))
