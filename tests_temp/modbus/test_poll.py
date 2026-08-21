"""Poll groups, @on_change semantics and the running adapter (0.7).

The builder tests are pure (a fake Application hands back instances), while the
adapter tests drive a real server so the whole chain - connect, plan, read,
decode, dispatch - is exercised end to end.
"""
import asyncio

import pytest

from xime.adapters.modbus._adapter import ModbusAdapter, _has_changed
from xime.adapters.modbus._config import modbus_registry
from xime.adapters.modbus._decorators import on_change, poll
from xime.adapters.modbus._model import Coil, Holding, Input, device
from xime.adapters.modbus.routing._builder import (
    DEFAULT_POLL_INTERVAL,
    ModbusRouteBuilder,
)
from xime.core.exception.framework import StartupException

from .conftest import FC_COIL, FC_HOLDING, FC_INPUT


@device(unit=1)
class Tank:
    level: float = Holding(0, type="float32")
    setpoint: int = Holding(2, type="uint16")
    valve: bool = Coil(0)
    fault: int = Input(0, type="uint16")


class FakeApp:
    """Stands in for Application: returns one instance per controller class."""

    def __init__(self, *instances):
        self._by_type = {type(obj): obj for obj in instances}

    def get(self, cls):
        if cls not in self._by_type:
            raise KeyError(cls)
        return self._by_type[cls]


def build(*instances):
    controllers = [type(obj) for obj in instances]
    return ModbusRouteBuilder(FakeApp(*instances)).build(controllers)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class TestGrouping:
    def test_two_handlers_same_model_and_interval_share_one_loop(self):
        # Otherwise the device would be read twice per second for no reason.
        class Monitor:
            @poll(Tank, interval=1.0)
            async def a(self, tank): ...

            @poll(Tank, interval=1.0)
            async def b(self, tank): ...

        groups = build(Monitor())
        assert len(groups) == 1
        assert len(groups[0].polls) == 2

    def test_different_intervals_get_their_own_loops(self):
        class Monitor:
            @poll(Tank, interval=1.0)
            async def fast(self, tank): ...

            @poll(Tank, interval=60.0)
            async def slow(self, tank): ...

        groups = build(Monitor())
        assert sorted(g.interval for g in groups) == [1.0, 60.0]

    def test_handlers_in_different_controllers_still_share_a_loop(self):
        class A:
            @poll(Tank, interval=2.0)
            async def a(self, tank): ...

        class B:
            @poll(Tank, interval=2.0)
            async def b(self, tank): ...

        assert len(build(A(), B())) == 1

    def test_one_adapter_one_kind_means_ONE_loop(self):
        """0.8 bỏ trục `device` khỏi `@poll`: hai handler cùng model, cùng
        nhịp thì dùng **một** vòng, không tách ra được nữa.

        Trước 0.8 `device="other"` tách chúng thành hai vòng - lúc đó một
        adapter nối tới **một thiết bị**. Nay một adapter phục vụ một **loại**
        và giữ N thực thể, nên việc chọn máy nào không còn nằm ở decorator.
        """
        class Monitor:
            @poll(Tank, interval=1.0)
            async def here(self, tank): ...

            @poll(Tank, interval=1.0)
            async def there(self, tank): ...

        groups = build(Monitor())
        assert len(groups) == 1
        assert len(groups[0].polls) == 2


class TestChangeWatchAttachment:
    def test_watch_joins_the_fastest_existing_loop(self):
        # A change can only be noticed as fast as the model is read, so the
        # watch belongs on the quickest loop rather than forcing a new one.
        class Monitor:
            @poll(Tank, interval=5.0)
            async def slow(self, tank): ...

            @poll(Tank, interval=0.5)
            async def fast(self, tank): ...

            @on_change(Tank.fault)
            async def on_fault(self, value): ...

        groups = build(Monitor())
        watched = [g for g in groups if g.watches]
        assert len(watched) == 1
        assert watched[0].interval == 0.5

    def test_watch_without_any_poll_creates_its_own_loop(self):
        class Monitor:
            @on_change(Tank.fault)
            async def on_fault(self, value): ...

        groups = build(Monitor())
        assert len(groups) == 1
        assert groups[0].interval == DEFAULT_POLL_INTERVAL
        assert groups[0].model is Tank

    def test_deadband_is_carried_through(self):
        class Monitor:
            @on_change(Tank.level, deadband=0.5)
            async def on_level(self, value): ...

        assert build(Monitor())[0].watches[0].deadband == 0.5


class TestBuilderValidation:
    def test_sync_handler_is_refused(self):
        class Monitor:
            @poll(Tank, interval=1.0)
            def not_async(self, tank): ...

        with pytest.raises(StartupException, match="async def"):
            build(Monitor())

    def test_non_device_model_is_refused(self):
        class NotADevice:
            pass

        class Monitor:
            @poll(NotADevice, interval=1.0)
            async def handler(self, thing): ...

        with pytest.raises(StartupException, match="not a device model"):
            build(Monitor())

    def test_wrong_parameter_count_is_refused(self):
        class Monitor:
            @poll(Tank, interval=1.0)
            async def handler(self, tank, extra): ...

        with pytest.raises(StartupException, match="optional parameter named"):
            build(Monitor())

    def test_mismatched_annotation_is_refused(self):
        # Annotated with the wrong model -> the handler would receive an object
        # it does not expect. Cheaper to catch at startup.
        @device(unit=2)
        class Other:
            x: int = Holding(0)

        class Monitor:
            @poll(Tank, interval=1.0)
            async def handler(self, value: Other): ...

        with pytest.raises(StartupException, match="annotated"):
            build(Monitor())

    def test_correct_annotation_is_accepted(self):
        class Monitor:
            @poll(Tank, interval=1.0)
            async def handler(self, tank: Tank): ...

        assert len(build(Monitor())) == 1

    def test_zero_interval_is_refused(self):
        class Monitor:
            @poll(Tank, interval=0)
            async def handler(self, tank): ...

        with pytest.raises(StartupException, match="interval must be > 0"):
            build(Monitor())

    def test_on_change_needs_a_field(self):
        class Monitor:
            @on_change(Tank)  # the model, not a field
            async def handler(self, value): ...

        with pytest.raises(StartupException, match="device model field"):
            build(Monitor())

    def test_controller_missing_from_di_is_reported(self):
        class Monitor:
            @poll(Tank, interval=1.0)
            async def handler(self, tank): ...

        builder = ModbusRouteBuilder(FakeApp())  # nothing registered
        with pytest.raises(StartupException, match="not in the DI container"):
            builder.build([Monitor])


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------

class TestHasChanged:
    def test_plain_inequality_without_deadband(self):
        assert _has_changed(1, 2, None)
        assert not _has_changed(2, 2, None)
        assert _has_changed(False, True, None)

    def test_deadband_ignores_small_movement(self):
        assert not _has_changed(20.0, 20.3, 0.5)
        assert _has_changed(20.0, 20.6, 0.5)

    def test_deadband_is_exclusive_at_the_boundary(self):
        # "moved by MORE than the deadband" - exactly the deadband is noise.
        assert not _has_changed(20.0, 20.5, 0.5)

    def test_deadband_does_not_apply_to_booleans(self):
        # A bool is not an analogue reading; True is a real change.
        assert _has_changed(False, True, 0.5)

    def test_deadband_falls_back_to_inequality_for_non_numbers(self):
        assert _has_changed("a", "b", 0.5)


# ---------------------------------------------------------------------------
# Running adapter
# ---------------------------------------------------------------------------

class RuntimeStub:
    """Minimal stand-in for RuntimeConfig holding one device entry."""

    def __init__(self, host, port, **extra):
        self._data = {
            "modbus": {
                "devices": {"default": {"host": host, "port": port, "unit": 1}},
                **extra,
            }
        }

    def get(self, key, default=None):
        return self._data.get(key, default)


class AppStub:
    """Stands in for Application: serves RuntimeConfig plus controller singletons."""

    def __init__(self, runtime, *instances):
        self._runtime = runtime
        self._by_type = {type(obj): obj for obj in instances}

    def get(self, cls):
        from xime.core.config.runtime import RuntimeConfig

        if cls is RuntimeConfig:
            return self._runtime
        if cls not in self._by_type:
            raise KeyError(cls)
        return self._by_type[cls]


class RunningAdapter:
    """Runs a ModbusAdapter for the duration of a `with` block."""

    def __init__(self, server, *instances, controllers=None, **runtime_extra):
        self._app = AppStub(
            RuntimeStub(server.host, server.port, **runtime_extra), *instances
        )
        self._adapter = ModbusAdapter(
            "default",
            controllers=controllers or [type(obj) for obj in instances],
        )
        self._task = None

    async def __aenter__(self):
        await self._adapter.start(self._app)
        self._task = asyncio.create_task(self._adapter.serve())
        # Give the adapter a moment to connect and run its first cycle.
        await asyncio.sleep(0.15)
        return self._adapter

    async def __aexit__(self, *_):
        await self._adapter.stop()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass


@pytest.mark.asyncio
class TestAdapterPolling:
    async def test_poll_handler_receives_a_decoded_model(self, modbus_server):
        received = []

        class Monitor:
            @poll(Tank, interval=0.05)
            async def sample(self, tank: Tank):
                received.append(tank)

        await modbus_server.set(FC_HOLDING, 2, [123])
        await modbus_server.set(FC_COIL, 0, [True])
        await modbus_server.set(FC_INPUT, 0, [4])

        async with RunningAdapter(modbus_server, Monitor()):
            await asyncio.sleep(0.15)

        assert received, "poll handler never ran"
        assert received[0].setpoint == 123
        assert received[0].valve is True
        assert received[0].fault == 4

    async def test_the_loop_keeps_running_across_cycles(self, modbus_server):
        count = []

        class Monitor:
            @poll(Tank, interval=0.05)
            async def sample(self, tank: Tank):
                count.append(1)

        async with RunningAdapter(modbus_server, Monitor()):
            await asyncio.sleep(0.3)

        assert len(count) >= 3, f"expected several cycles, got {len(count)}"

    async def test_a_failing_handler_does_not_stop_the_loop(self, modbus_server):
        calls = []

        class Monitor:
            @poll(Tank, interval=0.05)
            async def explodes(self, tank: Tank):
                calls.append(1)
                raise RuntimeError("boom")

        async with RunningAdapter(modbus_server, Monitor()):
            await asyncio.sleep(0.25)

        assert len(calls) >= 3, "the loop stopped after the first failure"

    async def test_client_reads_work_while_the_adapter_holds_the_connection(
        self, modbus_server
    ):
        # An application with no @poll handlers still gets a live connection -
        # this is the on-demand-only case.
        from xime.adapters.modbus._client import ModbusClient

        await modbus_server.set(FC_HOLDING, 2, [55])

        async with RunningAdapter(modbus_server, controllers=[]):
            assert await ModbusClient().read_field(Tank.setpoint) == 55


@pytest.mark.asyncio
class TestAdapterChangeDetection:
    async def test_first_reading_is_only_a_baseline(self, modbus_server):
        seen = []

        class Monitor:
            @poll(Tank, interval=0.05)
            async def sample(self, tank: Tank): ...

            @on_change(Tank.setpoint)
            async def changed(self, value):
                seen.append(value)

        await modbus_server.set(FC_HOLDING, 2, [10])

        async with RunningAdapter(modbus_server, Monitor()):
            await asyncio.sleep(0.2)

        assert seen == [], "a steady value must not look like a change"

    async def test_change_is_reported_once_the_value_moves(self, modbus_server):
        seen = []

        class Monitor:
            @poll(Tank, interval=0.05)
            async def sample(self, tank: Tank): ...

            @on_change(Tank.setpoint)
            async def changed(self, value):
                seen.append(value)

        await modbus_server.set(FC_HOLDING, 2, [10])

        async with RunningAdapter(modbus_server, Monitor()):
            await asyncio.sleep(0.15)
            await modbus_server.set(FC_HOLDING, 2, [99])
            await asyncio.sleep(0.2)

        # 10 was the baseline; only the move to 99 is news, and only once.
        assert seen == [99]

    async def test_deadband_suppresses_small_movements(self, modbus_server):
        seen = []

        class Monitor:
            @poll(Tank, interval=0.05)
            async def sample(self, tank: Tank): ...

            @on_change(Tank.level, deadband=1.0)
            async def changed(self, value):
                seen.append(value)

        from xime.adapters.modbus._codec import encode_field
        from xime.adapters.modbus._model import require_device_info

        info = require_device_info(Tank)
        await modbus_server.set(FC_HOLDING, 0, encode_field(Tank.level, info, 20.0))

        async with RunningAdapter(modbus_server, Monitor()):
            await asyncio.sleep(0.15)
            await modbus_server.set(FC_HOLDING, 0, encode_field(Tank.level, info, 20.4))
            await asyncio.sleep(0.15)
            await modbus_server.set(FC_HOLDING, 0, encode_field(Tank.level, info, 25.0))
            await asyncio.sleep(0.2)

        assert seen == [pytest.approx(25.0)]


@pytest.mark.asyncio
class TestAdapterLifecycle:
    async def test_adapter_claims_the_device_name_at_construction(self):
        # Before start(), so a ModbusClient injected into a service that runs
        # early does not fail fast for the wrong reason.
        adapter = ModbusAdapter("claimed")
        assert modbus_registry.connection("claimed").is_served is True
        assert adapter is not None

    async def test_unknown_device_fails_at_startup(self, modbus_server):
        class Monitor:
            @poll(Tank, interval=1.0)
            async def sample(self, tank: Tank): ...

        app = AppStub(RuntimeStub(modbus_server.host, modbus_server.port), Monitor())
        adapter = ModbusAdapter("not_in_yaml", controllers=[Monitor])

        with pytest.raises(StartupException, match="Unknown Modbus device"):
            await adapter.start(app)

    async def test_stop_detaches_the_connection(self, modbus_server):
        async with RunningAdapter(modbus_server, controllers=[]) as adapter:
            assert modbus_registry.connection("default").is_connected is True
            await adapter.stop()
            assert modbus_registry.connection("default").is_connected is False
