"""
Test TestApplication:

  Lifecycle:
    - Starts without error with empty binding
    - stop() without start() is no-op
    - get() before start() raises RuntimeError
    - start() twice raises RuntimeError
    - Async context manager starts and stops cleanly
    - Can restart after stop

  runtime_config parameter:
    - Bypasses YAML loading and uses the provided RuntimeConfig
    - RuntimeConfig singleton is accessible via get()

  overrides — Protocol dependency injection:
    - Override instance is returned by get(Protocol type)
    - Override instance is injected into scanned service that depends on the Protocol
    - Service uses the override instance for business calls
    - Override instance is a singleton (same object on each get())
    - Multiple overrides are all applied independently

  Fail-fast (inherited DI validation still applies):
    - Missing Protocol dep without override raises at start time
"""
import pytest

from xime.core.config.binding import BindingConfig
from xime.core.config.runtime import RuntimeConfig
from xime.testing import TestApplication

from tsvc.service import SampleService, StoragePort


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class _FakeStorage:
    """In-memory StoragePort implementation for tests."""

    def __init__(self) -> None:
        self._data: list[str] = []

    def store(self, value: str) -> None:
        self._data.append(value)

    def retrieve(self) -> list[str]:
        return list(self._data)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_binding() -> BindingConfig:
    """BindingConfig that scans the sample service package."""
    b = BindingConfig()
    b.scan("tsvc.service")
    return b


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

class TestTestApplicationLifecycle:
    @pytest.mark.asyncio
    async def test_starts_with_empty_binding(self):
        async with TestApplication():
            pass  # no error

    @pytest.mark.asyncio
    async def test_stop_without_start_is_noop(self):
        app = TestApplication()
        await app.stop()  # no error, no exception

    @pytest.mark.asyncio
    async def test_get_before_start_raises_runtime_error(self):
        app = TestApplication()
        with pytest.raises(RuntimeError, match="not started"):
            app.get(SampleService)

    @pytest.mark.asyncio
    async def test_start_twice_raises_runtime_error(self):
        app = TestApplication(
            binding=_sample_binding(),
            overrides={StoragePort: _FakeStorage()},
        )
        await app.start()
        try:
            with pytest.raises(RuntimeError, match="already running"):
                await app.start()
        finally:
            await app.stop()

    @pytest.mark.asyncio
    async def test_context_manager_starts_and_stops_cleanly(self):
        async with TestApplication(
            binding=_sample_binding(),
            overrides={StoragePort: _FakeStorage()},
        ) as app:
            assert app.get(SampleService) is not None

    @pytest.mark.asyncio
    async def test_can_restart_after_stop(self):
        """start → stop → start again does not raise."""
        app = TestApplication(
            binding=_sample_binding(),
            overrides={StoragePort: _FakeStorage()},
        )
        await app.start()
        await app.stop()
        await app.start()
        await app.stop()  # no error


# ---------------------------------------------------------------------------
# runtime_config parameter
# ---------------------------------------------------------------------------

class TestTestApplicationRuntimeConfig:
    @pytest.mark.asyncio
    async def test_runtime_config_bypasses_yaml_loading(self):
        custom = RuntimeConfig.from_dict({"env": "test", "server": {"port": 9999}})
        async with TestApplication(runtime_config=custom) as app:
            runtime = app.get(RuntimeConfig)
            assert runtime.env == "test"
            assert runtime.server.port == 9999

    @pytest.mark.asyncio
    async def test_empty_runtime_config_is_valid(self):
        async with TestApplication(runtime_config=RuntimeConfig.from_dict({})):
            pass  # no error


# ---------------------------------------------------------------------------
# Override — Protocol dependency injection
# ---------------------------------------------------------------------------

class TestTestApplicationOverrides:
    @pytest.mark.asyncio
    async def test_override_instance_is_returned_by_get(self):
        """get(Protocol) returns the exact override instance."""
        fake = _FakeStorage()
        async with TestApplication(overrides={StoragePort: fake}) as app:
            retrieved = app.get(StoragePort)
            assert retrieved is fake

    @pytest.mark.asyncio
    async def test_override_instance_is_injected_into_service(self):
        """Service that declares Protocol dep receives the override instance."""
        fake = _FakeStorage()
        async with TestApplication(
            binding=_sample_binding(),
            overrides={StoragePort: fake},
        ) as app:
            service = app.get(SampleService)
            assert service.storage is fake

    @pytest.mark.asyncio
    async def test_service_uses_override_for_business_calls(self):
        """Calls on service are dispatched to the fake, not a real implementation."""
        fake = _FakeStorage()
        async with TestApplication(
            binding=_sample_binding(),
            overrides={StoragePort: fake},
        ) as app:
            service = app.get(SampleService)
            service.save("hello")
            service.save("world")
            assert fake.retrieve() == ["hello", "world"]

    @pytest.mark.asyncio
    async def test_override_is_singleton_same_instance_on_repeated_get(self):
        fake = _FakeStorage()
        async with TestApplication(overrides={StoragePort: fake}) as app:
            a = app.get(StoragePort)
            b = app.get(StoragePort)
            assert a is b is fake

    @pytest.mark.asyncio
    async def test_scanned_service_is_also_singleton(self):
        async with TestApplication(
            binding=_sample_binding(),
            overrides={StoragePort: _FakeStorage()},
        ) as app:
            s1 = app.get(SampleService)
            s2 = app.get(SampleService)
            assert s1 is s2

    @pytest.mark.asyncio
    async def test_multiple_overrides_are_all_applied(self):
        """Each override key-value pair is independently registered."""
        class _AnotherPort:
            pass

        fake_storage = _FakeStorage()
        fake_other = _AnotherPort()

        async with TestApplication(
            overrides={
                StoragePort: fake_storage,
                _AnotherPort: fake_other,
            }
        ) as app:
            assert app.get(StoragePort) is fake_storage
            assert app.get(_AnotherPort) is fake_other

    @pytest.mark.asyncio
    async def test_no_overrides_defaults_to_empty_dict(self):
        """TestApplication with no overrides= keyword works."""
        async with TestApplication():
            pass  # no error


# ---------------------------------------------------------------------------
# Fail-fast — DI validation still applies when overrides are incomplete
# ---------------------------------------------------------------------------

class TestTestApplicationFailFast:
    @pytest.mark.asyncio
    async def test_missing_protocol_dep_without_override_raises_at_start(self):
        """
        If a scanned service depends on a Protocol and no override (and no binding)
        is provided, startup must fail immediately — not at get() time.
        """
        binding = _sample_binding()  # scans SampleService which needs StoragePort
        # NO override for StoragePort provided → DI cannot resolve it
        with pytest.raises(Exception):  # StartupException or subclass
            async with TestApplication(binding=binding):
                pass
