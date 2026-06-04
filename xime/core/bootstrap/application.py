from __future__ import annotations

import asyncio
import importlib
import pkgutil
import sys
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
      2. config_module= explicit path → import that module, read its `dependency`
      3. Auto-discovery (config_module=None, the default):
           a. {main_package}.config.dependency  (detected from __main__.__spec__)
           b. config.dependency                 (fallback for root-level main.py)
      4. Fallback: empty BindingConfig (no packages scanned)

    Auto-discovery example:
        Running "python -m app.main"  → tries app.config.dependency first.
        Running "python main.py"      → tries config.dependency.

    Runtime config is always loaded from resources/{application.yml} merged
    with resources/application-{env}.yml (env from XIME_ENV or APP_ENV).

    Typical usage:
        # Blocking with adapters — config auto-detected from package
        app = Application()
        app.use(WebAdapter()).use(GrpcAdapter()).run()

        # Explicit config module
        app = Application(config_module="app.config.dependency")

        # As async context manager
        async with Application() as app:
            ...
    """

    def __init__(
        self,
        *,
        binding: BindingConfig | None = None,
        resources_dir: str = "resources",
        config_module: str | None = None,
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
        # Include start() inside try so that the finally cleanup block always
        # runs even when a PostConstruct hook raises during startup.
        try:
            await self.start()
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
        Try each candidate config module in order and return the first
        `dependency` (BindingConfig) found.

        After finding the dependency module, imports all sibling modules in the
        same config package so their configure_*() side effects take effect
        (e.g. configure_controllers(), configure_openapi(), configure_grpc()).

        Falls back to empty BindingConfig only when none of the candidates
        exist. Re-raises if a candidate module exists but fails to import
        (e.g. a broken dependency inside it), so the error is not hidden.
        """
        for module_path in self._config_module_candidates():
            result = self._try_load_config(module_path)
            if result is not None:
                self._import_config_siblings(module_path)
                return result
        return BindingConfig()

    def _config_module_candidates(self) -> list[str]:
        """
        Return the ordered list of module paths to probe for BindingConfig.

        When config_module is explicit → only that path is tried.
        When config_module is None    → auto-detect from __main__ package,
                                        then fall back to "config.dependency".
        """
        if self._config_module is not None:
            return [self._config_module]

        candidates: list[str] = []

        # Detect the package of the running entry-point.
        # "python -m app.main"  → __spec__.parent = "app"  → try app.config.dependency
        # "python main.py"      → __spec__ is None or parent = "" → skip to fallback
        main = sys.modules.get("__main__")
        if main is not None:
            spec = getattr(main, "__spec__", None)
            if spec is not None and spec.parent:
                candidates.append(f"{spec.parent}.config.dependency")

        candidates.append("config.dependency")
        return candidates

    def _try_load_config(self, module_path: str) -> BindingConfig | None:
        """
        Import module_path and return its `dependency` attribute if it is a
        BindingConfig instance.  Returns None when the module does not exist.
        Re-raises ModuleNotFoundError when the error originates from inside the
        module (a missing transitive dependency), not from the module itself.
        """
        try:
            module = importlib.import_module(module_path)
            cfg = getattr(module, "dependency", None)
            return cfg if isinstance(cfg, BindingConfig) else None
        except ModuleNotFoundError as exc:
            # Only suppress when the config module (or a true dotted-path parent)
            # is absent. Re-raise if something *inside* an existing module fails
            # to import, so the developer sees the real error.
            # Use split-based comparison instead of startswith() to avoid
            # "myapp" matching "myapp_service" across a package boundary.
            missing = exc.name or ""
            config_parts = module_path.split(".")
            missing_parts = missing.split(".")
            if config_parts[: len(missing_parts)] != missing_parts:
                raise
            return None

    @staticmethod
    def _import_config_siblings(dependency_module_path: str) -> None:
        """
        Import every module in the same config package except `dependency` itself.

        e.g. finding "app.config.dependency" → imports "app.config.web",
        "app.config.grpc", etc. so their configure_*() calls register into the
        framework registries before adapters start.

        Errors inside sibling modules propagate normally — a broken config file
        should not be silently ignored.
        """
        parts = dependency_module_path.rsplit(".", 1)
        if len(parts) < 2:
            return
        config_package = parts[0]  # "app.config.dependency" → "app.config"

        try:
            pkg = importlib.import_module(config_package)
        except ImportError:
            return

        pkg_path = getattr(pkg, "__path__", None)
        if pkg_path is None:
            return

        for _, name, _ in pkgutil.iter_modules(pkg_path):
            if name == "dependency":
                continue  # already imported by _try_load_config
            importlib.import_module(f"{config_package}.{name}")

    def _load_runtime(self) -> RuntimeConfig:
        loader = YamlConfigLoader(self._resources_dir)
        return RuntimeConfig.from_dict(loader.load(env=detect_env()))
