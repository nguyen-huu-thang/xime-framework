from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from core.config.runtime import RuntimeConfig


class AsyncEngineProvider:
    """
    Manages the lifecycle of the SQLAlchemy AsyncEngine.

    Reads database settings from RuntimeConfig (application.yml):

        database:
          url: postgresql+asyncpg://user:pass@localhost/dbname
          pool_size: 5        # optional, default 5
          max_overflow: 10    # optional, default 10
          echo: false         # optional, default false

    PreDestroy disposes the connection pool cleanly on shutdown.

    Register in config/dependency.py:
        dependency.scan("starters.sqlalchemy", ...)
    RuntimeConfig is injected automatically by the framework.
    """

    def __init__(self, config: RuntimeConfig) -> None:
        url: str = config.get("database.url") or ""
        if not url:
            raise ValueError(
                "database.url is not configured. "
                "Add 'database.url' to resources/application.yml."
            )

        pool_size: int = config.get("database.pool_size", 5)
        max_overflow: int = config.get("database.max_overflow", 10)
        echo: bool = config.get("database.echo", False)

        self._engine: AsyncEngine = create_async_engine(
            url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            echo=echo,
        )

    @property
    def engine(self) -> AsyncEngine:
        """The underlying AsyncEngine instance."""
        return self._engine

    async def pre_destroy(self) -> None:
        """Dispose the connection pool before shutdown."""
        await self._engine.dispose()
