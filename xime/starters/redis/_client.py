from __future__ import annotations

from typing import TYPE_CHECKING

from xime.core.config.runtime import RuntimeConfig

if TYPE_CHECKING:
    from redis.asyncio import Redis


class RedisClientProvider:
    """
    Owns the lifecycle of the async Redis client (and its connection pool).

    Reads settings from RuntimeConfig (application.yml):

        redis:
          url: redis://localhost:6379/0
          max_connections: 10   # optional, default 10

    PreDestroy closes the connection pool cleanly on shutdown, matching the
    "Close Database / Redis / gRPC Channels" step of the shutdown sequence.

    Register in config/dependency.py:
        dependency.scan("xime.starters.redis")
    RuntimeConfig is injected automatically by the framework.

    The `redis` package is imported lazily (after config validation) so the
    starter module stays importable even when redis is not installed - only
    services that actually scan this package need `pip install xime[redis]`.
    Import `redis` lười (sau khi validate config) để module vẫn import được khi
    chưa cài redis - chỉ service nào scan package này mới cần cài.
    """

    def __init__(self, config: RuntimeConfig) -> None:
        url: str = config.get("redis.url") or ""
        if not url:
            raise ValueError(
                "redis.url is not configured. "
                "Add 'redis.url' to resources/application.yml."
            )

        max_connections: int = config.get("redis.max_connections", 10)

        # Lazy import: fail-fast with a clear message if the extra is missing.
        # Import lười: báo lỗi rõ nếu chưa cài extra.
        try:
            from redis.asyncio import from_url
        except ImportError as exc:
            raise ImportError(
                "The redis starter requires the 'redis' package. "
                "Install it with: pip install xime[redis]"
            ) from exc

        # `decode_responses=False` khai TƯỜNG MINH, không dựa vào mặc định của
        # redis-py: `CacheService.get()` hứa trả `bytes | None`, và bật giải mã
        # thì nó trả `str` - cùng một chữ ký, hai kiểu dữ liệu, không lỗi nào
        # phát ra. Đúng luật 03 ở tầng kiểu trả về.
        self._client: Redis = from_url(
            url, max_connections=max_connections, decode_responses=False
        )

    @property
    def client(self) -> Redis:
        """The underlying async Redis client."""
        return self._client

    async def pre_destroy(self) -> None:
        """Close the client and its connection pool before shutdown."""
        await self._client.aclose()
