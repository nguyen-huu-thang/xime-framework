from __future__ import annotations

import asyncio
import importlib
from typing import TYPE_CHECKING, Any

from xime.core.bootstrap.orchestrator import StartupOrchestrator
from xime.core.config.binding import BindingConfig
from xime.core.config.loader import YamlConfigLoader, detect_env
from xime.core.config.runtime import RuntimeConfig

if TYPE_CHECKING:
    from xime.core.bootstrap.adapter import Adapter


class Application:
    """
    Entry point for a Xime application.

    Loads configuration, runs the startup pipeline, and manages the
    application lifecycle. Designed to be used as an async context manager
    or driven manually via start() / stop().

    Config loading (in order of precedence):
      1. binding= passed directly → used as-is, auto-discovery skipped
      2. Auto-discovery: import config_module, read its `dependency` attribute
      3. Fallback: empty BindingConfig (no packages scanned)

    Runtime config is always loaded from resources/{application.yml} merged
    with resources/application-{env}.yml (env from XIME_ENV or APP_ENV).

    Typical usage:
        # As async context manager (recommended)
        async with Application() as app:
            ...

        # Manual lifecycle
        app = Application()
        await app.start()
        try:
            ...
        finally:
            await app.stop()

        # Blocking with adapters (REST only, or REST + gRPC simultaneously)
        app = Application()
        app.use(WebAdapter())
        app.use(GrpcAdapter())
        app.run()
    """

    def __init__(
        self,
        *,
        binding: BindingConfig | None = None,
        resources_dir: str = "resources",
        config_module: str = "config.dependency",
    ) -> None:
        self._binding = binding
        self._resources_dir = resources_dir
        self._config_module = config_module
        self._orchestrator: StartupOrchestrator | None = None
        self._adapters: list["Adapter"] = []

    # ------------------------------------------------------------------
    # Adapter registration
    # ------------------------------------------------------------------

    def use(self, adapter: "Adapter") -> "Application":
        """Register an adapter to run when app.run() is called.

        Adapters start concurrently after the DI container is built.
        Supports chaining: app.use(WebAdapter()).use(GrpcAdapter()).run()
        """
        self._adapters.append(adapter)
        return self

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """
        Load config and run the full startup pipeline.
        Raises RuntimeError if called while already running — call stop() first.
        """
        if self._orchestrator is not None:
            raise RuntimeError(
                "Application is already running. "
                "Call stop() before starting again."
            )

        binding = self._resolve_binding()
        runtime = self._load_runtime()
        self._orchestrator = StartupOrchestrator(binding, runtime)
        await self._orchestrator.start()

    async def stop(self) -> None:
        """
        Shut down the application. No-op if start() was never called.
        Resets internal state so start() can be called again.
        """
        if self._orchestrator is not None:
            await self._orchestrator.stop()
            self._orchestrator = None

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "Application":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    # ------------------------------------------------------------------
    # Blocking entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the application and all registered adapters, block until interrupted."""
        asyncio.run(self._run_async())

    async def _run_async(self) -> None:
        await self.start()
        try:
            if self._adapters:
                # TaskGroup guarantees all adapter tasks are cancelled when any
                # one of them fails — no orphaned background tasks.
                try:
                    async with asyncio.TaskGroup() as tg:
                        for adapter in self._adapters:
                            tg.create_task(adapter.start(self))
                except* (KeyboardInterrupt, asyncio.CancelledError):
                    pass  # tasks raised CancelledError internally — handled below
            else:
                await asyncio.sleep(float("inf"))
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass  # normal shutdown via Ctrl+C or external cancellation
        finally:
            # Shut down adapters in reverse registration order (LIFO)
            for adapter in reversed(self._adapters):
                try:
                    await adapter.stop()
                except (asyncio.CancelledError, Exception):
                    pass
            await self.stop()

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    def get(self, cls: type) -> object:
        """
        Return a singleton from the DI container.
        Raises RuntimeError if called before start().
        """
        if self._orchestrator is None:
            raise RuntimeError(
                "Application has not started. "
                "Use as async context manager or call start() first."
            )
        return self._orchestrator.get(cls)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_binding(self) -> BindingConfig:
        if self._binding is not None:
            return self._binding
        return self._discover_binding()

    def _discover_binding(self) -> BindingConfig:
        """
        Try to import config_module and return its `dependency` attribute.
        Falls back to an empty BindingConfig only when the config module itself
        does not exist. Re-raises if the module exists but has an import error
        inside it (e.g. a missing dependency), so the error is not silently hidden.
        """
        try:
            module = importlib.import_module(self._config_module)
            cfg = getattr(module, "dependency", None)
            if isinstance(cfg, BindingConfig):
                return cfg
        except ModuleNotFoundError as exc:
            # Only suppress when the config module (or a parent package in its
            # dotted path) is absent. Re-raise if something *inside* an existing
            # module fails to import, so the developer sees the real error.
            if exc.name is None or not self._config_module.startswith(exc.name):
                raise
        return BindingConfig()

    def _load_runtime(self) -> RuntimeConfig:
        loader = YamlConfigLoader(self._resources_dir)
        return RuntimeConfig.from_dict(loader.load(env=detect_env()))
