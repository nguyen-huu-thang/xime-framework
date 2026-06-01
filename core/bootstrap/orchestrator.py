from __future__ import annotations

from core.config.binding import BindingConfig
from core.config.runtime import RuntimeConfig
from core.container import XimeContainer
from core.lifecycle.manager import LifecycleManager


class StartupOrchestrator:
    """
    Runs the full Xime startup pipeline and owns the running application state.

    Startup sequence:
      1. Build DI container (scan packages → resolve → validate → register)
      2. Force-instantiate all singletons in topological order
      3. Create LifecycleManager with ordered instances
      4. Call lifecycle.start() — invokes PostConstruct on each eligible singleton

    Shutdown sequence:
      1. Call lifecycle.stop() — invokes PreDestroy in reverse order

    get(cls) is available after start() and delegates to the DI container.
    """

    def __init__(self, binding: BindingConfig, runtime: RuntimeConfig) -> None:
        self._binding = binding
        self._runtime = runtime
        self._container: XimeContainer | None = None
        self._lifecycle: LifecycleManager | None = None

    @property
    def runtime(self) -> RuntimeConfig:
        """Typed runtime config loaded from YAML (available before start())."""
        return self._runtime

    async def start(self) -> None:
        """
        Execute the full startup pipeline.
        Raises StartupException (or subclass) on DI validation errors.
        Raises on the first PostConstruct failure (fail-fast).
        """
        self._container = (
            XimeContainer()
            .scan(*self._binding.packages)
            .bind(self._binding.bindings)
            .build()
        )

        instances = self._container.get_all_in_order()
        self._lifecycle = LifecycleManager(instances)
        await self._lifecycle.start()

    async def stop(self) -> None:
        """
        Execute shutdown. No-op if start() was never called.
        Raises ExceptionGroup if any PreDestroy hook fails.
        """
        if self._lifecycle is not None:
            await self._lifecycle.stop()

    def get(self, cls: type) -> object:
        """
        Return the singleton instance for the given class.
        Raises RuntimeError if called before start().
        """
        if self._container is None:
            raise RuntimeError(
                "StartupOrchestrator has not started. Call start() first."
            )
        return self._container.get(cls)
