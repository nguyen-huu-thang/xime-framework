from __future__ import annotations

from typing import Any, Callable

from xime.core.config.binding import BindingConfig
from xime.core.config.runtime import RuntimeConfig
from xime.core.container import XimeContainer
from xime.core.event.bus import EventBus
from xime.core.lifecycle.manager import LifecycleManager


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

        event_bus = EventBus()
        container = (
            XimeContainer()
            .register_instance(RuntimeConfig, self._runtime)
            .register_instance(EventBus, event_bus)
            .scan(*self._binding.packages)
            .bind(self._binding.bindings)
            .register(*self._binding.explicit_classes)
        )
        for config_cls in self._binding.config_classes:
            container.configure(config_cls)
        if self._binding.order_rules:
            container.order(*self._binding.order_rules)
        self._container = container.build()

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

        Each starter has its own _try_build_* method below.  To integrate a new
        starter: add a private static method _try_build_<name> and call it here.
        """
        builders = [
            StartupOrchestrator._try_build_scheduler,
        ]
        return [c for b in builders if (c := b(resolver)) is not None]

    @staticmethod
    def _try_build_scheduler(resolver: Callable[[type], Any]) -> object | None:
        """Return a SchedulerRunner if the scheduler starter is configured, else None."""
        try:
            from xime.starters.scheduler._config import scheduler_registry
        except ImportError:
            return None  # starter not installed — skip silently

        config = scheduler_registry.get()
        if config is None:
            return None

        try:
            from xime.starters.scheduler._runner import SchedulerRunner
        except ImportError:
            raise RuntimeError(
                "Scheduler is configured via configure_scheduler() but "
                "'apscheduler' is not installed. "
                "Run: pip install 'apscheduler>=4.0'"
            )
        return SchedulerRunner(config, resolver)
