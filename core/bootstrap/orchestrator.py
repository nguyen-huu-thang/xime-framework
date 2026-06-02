from __future__ import annotations

from typing import Any, Callable

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
      3. Collect framework-managed lifecycle components (e.g. SchedulerRunner)
      4. Create LifecycleManager with all instances (user singletons + framework components)
      5. Call lifecycle.start() — invokes PostConstruct on each eligible instance

    Shutdown sequence:
      1. Call lifecycle.stop() — invokes PreDestroy in reverse order
         (framework components shut down before user singletons)

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
        Raises RuntimeError if called while already running — call stop() first.
        Raises StartupException (or subclass) on DI validation errors.
        Raises on the first PostConstruct failure (fail-fast).
        """
        if self._container is not None:
            raise RuntimeError(
                "StartupOrchestrator is already running. "
                "Call stop() before starting again."
            )

        self._container = (
            XimeContainer()
            .register_instance(RuntimeConfig, self._runtime)
            .scan(*self._binding.packages)
            .bind(self._binding.bindings)
            .build()
        )

        # User singletons in topological order, followed by framework-managed
        # components that need the DI container (e.g. SchedulerRunner).
        # Appending last ensures framework components start after all user
        # singletons and stop before them (LifecycleManager reverses on stop).
        instances = self._container.get_all_in_order()
        instances.extend(self._build_framework_components(self._container.get))

        self._lifecycle = LifecycleManager(instances)
        await self._lifecycle.start()

    async def stop(self) -> None:
        """
        Execute shutdown. No-op if start() was never called.
        Raises ExceptionGroup if any PreDestroy hook fails.
        Resets internal state so start() can be called again.
        """
        if self._lifecycle is not None:
            await self._lifecycle.stop()
        self._lifecycle = None
        self._container = None

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

    # ------------------------------------------------------------------
    # Framework-managed lifecycle components
    # ------------------------------------------------------------------

    @staticmethod
    def _build_framework_components(resolver: Callable[[type], Any]) -> list[object]:
        """
        Collect lifecycle-aware components provided by starters that cannot be
        registered as ordinary DI singletons because they need the container's
        resolver to function (e.g. SchedulerRunner resolves job classes from DI).

        Each starter is checked via lazy import so that missing optional packages
        do not cause startup errors when the starter is not configured.

        New starters that need lifecycle integration should add a block here.
        """
        components: list[object] = []

        # ── Scheduler starter ──────────────────────────────────────────────
        try:
            from starters.scheduler._config import scheduler_registry
            config = scheduler_registry.get()
            if config is not None:
                try:
                    from starters.scheduler._runner import SchedulerRunner
                except ImportError:
                    raise RuntimeError(
                        "Scheduler is configured via configure_scheduler() but "
                        "'apscheduler' is not installed. "
                        "Run: pip install 'apscheduler>=4.0'"
                    )
                components.append(SchedulerRunner(config, resolver))
        except ImportError:
            pass  # starters/scheduler not present — skip silently

        return components
