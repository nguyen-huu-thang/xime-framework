from __future__ import annotations

import asyncio
import importlib
from typing import Any

from core.bootstrap.orchestrator import StartupOrchestrator
from core.config.binding import BindingConfig
from core.config.loader import YamlConfigLoader, detect_env
from core.config.runtime import RuntimeConfig


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

        # Blocking (CLI / scripts)
        Application().run()
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

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Load config and run the full startup pipeline."""
        binding = self._resolve_binding()
        runtime = self._load_runtime()
        self._orchestrator = StartupOrchestrator(binding, runtime)
        await self._orchestrator.start()

    async def stop(self) -> None:
        """Shut down the application. No-op if start() was never called."""
        if self._orchestrator is not None:
            await self._orchestrator.stop()

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
        """Start the application and block until interrupted (Ctrl+C)."""
        asyncio.run(self._run_async())

    async def _run_async(self) -> None:
        await self.start()
        try:
            await asyncio.sleep(float("inf"))
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
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
        Falls back to an empty BindingConfig when the module is not found.
        """
        try:
            module = importlib.import_module(self._config_module)
            cfg = getattr(module, "dependency", None)
            if isinstance(cfg, BindingConfig):
                return cfg
        except ImportError:
            pass
        return BindingConfig()

    def _load_runtime(self) -> RuntimeConfig:
        loader = YamlConfigLoader(self._resources_dir)
        return RuntimeConfig.from_dict(loader.load(env=detect_env()))
