from __future__ import annotations

from typing import Any, TypeVar

from xime.core.bootstrap.orchestrator import StartupOrchestrator

_T = TypeVar("_T")
from xime.core.config.binding import BindingConfig
from xime.core.config.loader import YamlConfigLoader, detect_env
from xime.core.config.runtime import RuntimeConfig
from xime.core.container import XimeContainer
from xime.core.lifecycle.manager import LifecycleManager


class _TestStartupOrchestrator(StartupOrchestrator):
    """
    StartupOrchestrator variant that pre-registers override instances before
    the DI container is built.

    Each override is registered via XimeContainer.register_instance() so that
    the DI graph wiring uses the test double instead of scanning for or
    instantiating a production implementation.
    """

    def __init__(
        self,
        binding: BindingConfig,
        runtime: RuntimeConfig,
        overrides: dict[type, object],
    ) -> None:
        super().__init__(binding, runtime)
        self._overrides = overrides

    async def start(self) -> None:
        if self._container is not None:
            raise RuntimeError(
                "TestApplication is already running. "
                "Call stop() before starting again."
            )

        container = XimeContainer().register_instance(RuntimeConfig, self._runtime)
        for cls, instance in self._overrides.items():
            container.register_instance(cls, instance)

        self._container = (
            container
            .scan(*self._binding.packages)
            .bind(self._binding.bindings)
            .build()
        )

        instances = self._container.get_all_in_order()
        instances.extend(self._build_framework_components(self._container.get))

        self._lifecycle = LifecycleManager(instances)
        await self._lifecycle.start()


class TestApplication:
    """
    Application variant for integration tests.

    Starts the full DI container with the same scan packages and bindings as
    production, but allows specific dependencies to be replaced with pre-built
    test doubles (fakes, mocks, stubs) via the ``overrides`` parameter.

    Override instances bypass DI scanning and binding resolution — the
    framework registers them directly and wires them into any service that
    declares a matching type hint.

    Example::

        fake_repo = FakeUserRepository()

        async with TestApplication(
            binding=my_binding,
            overrides={
                UserRepository: fake_repo,
                TransactionManager: FakeTransactionManager(),
            },
        ) as app:
            service = app.get(UserService)
            assert service.repository is fake_repo
            await service.create_user("Alice")

    Parameters
    ----------
    binding:
        Production BindingConfig (same scan packages and protocol→impl bindings).
        Defaults to an empty BindingConfig when omitted.
    overrides:
        Mapping of ``type → pre-built instance``.  Each entry replaces the DI
        container's resolution for that type with the supplied object.
    resources_dir:
        Directory to search for ``application.yml``.  If loading fails or the
        directory does not exist, an empty RuntimeConfig is used.
    runtime_config:
        Supply a RuntimeConfig directly to skip YAML loading entirely.
        Useful when tests don't need any configuration values.
    """

    def __init__(
        self,
        *,
        binding: BindingConfig | None = None,
        overrides: dict[type, object] | None = None,
        resources_dir: str = "resources",
        runtime_config: RuntimeConfig | None = None,
    ) -> None:
        self._binding = binding or BindingConfig()
        self._overrides = overrides or {}
        self._resources_dir = resources_dir
        self._runtime_config = runtime_config
        self._orchestrator: _TestStartupOrchestrator | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start with overrides applied. Raises RuntimeError if already running."""
        if self._orchestrator is not None:
            raise RuntimeError(
                "TestApplication is already running. "
                "Call stop() before starting again."
            )
        runtime = self._resolve_runtime()
        self._orchestrator = _TestStartupOrchestrator(
            self._binding, runtime, self._overrides
        )
        await self._orchestrator.start()

    async def stop(self) -> None:
        """Shut down. No-op if never started; resets state so start() can be called again."""
        if self._orchestrator is not None:
            await self._orchestrator.stop()
            self._orchestrator = None

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "TestApplication":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    def get(self, cls: type[_T]) -> _T:
        """
        Return a singleton from the DI container (or an override instance).
        Raises RuntimeError if called before start().
        """
        if self._orchestrator is None:
            raise RuntimeError(
                "TestApplication has not started. "
                "Use as async context manager or call start() first."
            )
        return self._orchestrator.get(cls)  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_runtime(self) -> RuntimeConfig:
        if self._runtime_config is not None:
            return self._runtime_config
        try:
            loader = YamlConfigLoader(self._resources_dir)
            return RuntimeConfig.from_dict(loader.load(env=detect_env()))
        except Exception:
            return RuntimeConfig.from_dict({})
