from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xime.core.bootstrap.application import Application


@runtime_checkable
class Adapter(Protocol):
    """Protocol that every Xime adapter must satisfy.

    Adapters are registered via app.use(adapter) and started concurrently
    by app.run() after the DI container is fully built.

    Lifecycle:
        1. app.run() calls app.start()     — DI container built, singletons created
        2. app.run() calls adapter.start(app) for every registered adapter
           (all adapters start concurrently via asyncio.gather)
        3. On shutdown: adapter.stop() called in reverse registration order (LIFO)
        4. app.run() calls app.stop()      — PreDestroy hooks, DI dispose
    """

    async def start(self, app: "Application") -> None:
        """Start the adapter. Called after the DI container is fully built.

        Should block until the adapter is stopped (e.g. uvicorn.Server.serve(),
        grpc.Server.wait_for_termination()). app.run() gathers all adapters
        concurrently, so returning early means that adapter is done.
        """
        ...

    async def stop(self) -> None:
        """Signal the adapter to shut down gracefully.

        Called by app.run() in the finally block after asyncio.gather is
        cancelled. Should be idempotent — safe to call even if start() was
        never completed.
        """
        ...
