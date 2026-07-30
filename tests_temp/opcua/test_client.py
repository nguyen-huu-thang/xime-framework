"""OpcuaClient and OpcuaAdapter against a real asyncua server (0.7)."""
import asyncio

import pytest

from xime.adapters.opcua._adapter import OpcuaAdapter, _has_changed
from xime.adapters.opcua._client import (
    OpcuaClient,
    register_resolved_config,
)
from xime.adapters.opcua._config import OpcuaConfig, opcua_registry
from xime.adapters.opcua._decorators import on_node_change
from xime.adapters.opcua._errors import OpcuaConnectionError, OpcuaNodeError
from xime.adapters.opcua._model import Node, node_model
from xime.core.exception.framework import StartupException

pytestmark = pytest.mark.asyncio


@node_model
class Tank:
    level: float = Node("ns=2;s=Tank.Level")
    setpoint: float = Node("ns=2;s=Tank.Setpoint")
    alarm: bool = Node("ns=2;s=Tank.Alarm", writable=False)


class RuntimeStub:
    def __init__(self, endpoint, **extra):
        self._data = {"opcua": {"endpoint": endpoint, **extra}}

    def get(self, key, default=None):
        return self._data.get(key, default)


class AppStub:
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
    """Runs an OpcuaAdapter for the duration of an `async with` block."""

    def __init__(self, server, *instances, controllers=None, **runtime_extra):
        self._app = AppStub(RuntimeStub(server.endpoint, **runtime_extra), *instances)
        self._adapter = OpcuaAdapter(
            controllers=controllers if controllers is not None
            else [type(obj) for obj in instances],
        )
        self._task = None

    async def __aenter__(self):
        self._task = asyncio.create_task(self._adapter.start(self._app))
        await asyncio.sleep(0.4)  # connect + subscribe
        return self._adapter

    async def __aexit__(self, *_):
        await self._adapter.stop()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass


class TestReading:
    async def test_read_a_single_node_by_id(self, opcua_server):
        await opcua_server.set("ns=2;s=Tank.Level", 22.5)

        async with RunningAdapter(opcua_server, controllers=[]):
            assert await OpcuaClient().read("ns=2;s=Tank.Level") == 22.5

    async def test_read_a_declared_node(self, opcua_server):
        await opcua_server.set("ns=2;s=Tank.Setpoint", 30.0)

        async with RunningAdapter(opcua_server, controllers=[]):
            assert await OpcuaClient().read_node(Tank.setpoint) == 30.0

    async def test_read_model_fills_every_node(self, opcua_server):
        await opcua_server.set("ns=2;s=Tank.Level", 11.0)
        await opcua_server.set("ns=2;s=Tank.Setpoint", 12.0)
        await opcua_server.set("ns=2;s=Tank.Alarm", True)

        async with RunningAdapter(opcua_server, controllers=[]):
            tank = await OpcuaClient().read_model(Tank)

        assert (tank.level, tank.setpoint, tank.alarm) == (11.0, 12.0, True)

    async def test_unknown_node_is_reported_as_a_node_error(self, opcua_server):
        # A wrong NodeId is a modelling mistake, not a network problem, and the
        # error type says so.
        async with RunningAdapter(opcua_server, controllers=[]):
            with pytest.raises(OpcuaNodeError):
                await OpcuaClient().read("ns=2;s=Nope.Missing")


class TestWriting:
    async def test_write_a_declared_node(self, opcua_server):
        async with RunningAdapter(opcua_server, controllers=[]):
            await OpcuaClient().write(Tank.setpoint, 41.0)

        assert await opcua_server.get("ns=2;s=Tank.Setpoint") == 41.0

    async def test_write_by_node_id_string(self, opcua_server):
        async with RunningAdapter(opcua_server, controllers=[]):
            await OpcuaClient().write("ns=2;s=Tank.Level", 7.5)

        assert await opcua_server.get("ns=2;s=Tank.Level") == 7.5

    async def test_a_node_declared_read_only_is_refused_before_the_wire(
        self, opcua_server
    ):
        async with RunningAdapter(opcua_server, controllers=[]):
            with pytest.raises(OpcuaNodeError, match="writable=False"):
                await OpcuaClient().write(Tank.alarm, True)

    async def test_write_model_updates_only_what_is_set(self, opcua_server):
        await opcua_server.set("ns=2;s=Tank.Level", 1.0)

        async with RunningAdapter(opcua_server, controllers=[]):
            await OpcuaClient().write_model(Tank(setpoint=99.0))

        assert await opcua_server.get("ns=2;s=Tank.Setpoint") == 99.0
        assert await opcua_server.get("ns=2;s=Tank.Level") == 1.0

    async def test_write_model_skips_read_only_nodes(self, opcua_server):
        # Naming a read-only node should not blow up a whole-model write.
        async with RunningAdapter(opcua_server, controllers=[]):
            await OpcuaClient().write_model(Tank(alarm=True, setpoint=5.0))

        assert await opcua_server.get("ns=2;s=Tank.Setpoint") == 5.0


class TestSubscriptions:
    async def test_handler_fires_when_the_value_changes(self, opcua_server):
        seen = []

        class Monitor:
            @on_node_change(Tank.level)
            async def changed(self, value):
                seen.append(value)

        await opcua_server.set("ns=2;s=Tank.Level", 1.0)

        async with RunningAdapter(opcua_server, Monitor()):
            await opcua_server.set("ns=2;s=Tank.Level", 2.0)
            await asyncio.sleep(0.5)

        assert 2.0 in seen

    async def test_the_initial_value_is_only_a_baseline_by_default(self, opcua_server):
        # OPC UA pushes the current value the moment you subscribe; reporting it
        # would fire every handler at every startup.
        seen = []

        class Monitor:
            @on_node_change(Tank.level)
            async def changed(self, value):
                seen.append(value)

        await opcua_server.set("ns=2;s=Tank.Level", 5.0)

        async with RunningAdapter(opcua_server, Monitor()):
            await asyncio.sleep(0.4)

        assert seen == []

    async def test_initial_true_delivers_the_current_value(self, opcua_server):
        seen = []

        class Monitor:
            @on_node_change(Tank.level, initial=True)
            async def changed(self, value):
                seen.append(value)

        await opcua_server.set("ns=2;s=Tank.Level", 5.0)

        async with RunningAdapter(opcua_server, Monitor()):
            await asyncio.sleep(0.4)

        assert seen == [5.0]

    async def test_deadband_suppresses_small_movements(self, opcua_server):
        seen = []

        class Monitor:
            @on_node_change(Tank.level, deadband=1.0)
            async def changed(self, value):
                seen.append(value)

        await opcua_server.set("ns=2;s=Tank.Level", 20.0)

        async with RunningAdapter(opcua_server, Monitor()):
            await asyncio.sleep(0.3)
            await opcua_server.set("ns=2;s=Tank.Level", 20.4)
            await asyncio.sleep(0.3)
            await opcua_server.set("ns=2;s=Tank.Level", 25.0)
            await asyncio.sleep(0.4)

        assert seen == [25.0]

    async def test_a_failing_handler_does_not_stop_the_subscription(self, opcua_server):
        calls = []

        class Monitor:
            @on_node_change(Tank.level)
            async def changed(self, value):
                calls.append(value)
                raise RuntimeError("downstream is down")

        await opcua_server.set("ns=2;s=Tank.Level", 1.0)

        async with RunningAdapter(opcua_server, Monitor()):
            await opcua_server.set("ns=2;s=Tank.Level", 2.0)
            await asyncio.sleep(0.4)
            await opcua_server.set("ns=2;s=Tank.Level", 3.0)
            await asyncio.sleep(0.4)

        assert len(calls) >= 2, "the subscription stopped after the first failure"


class TestAdapterValidation:
    async def test_sync_handler_is_refused(self, opcua_server):
        class Monitor:
            @on_node_change(Tank.level)
            def not_async(self, value): ...

        adapter = OpcuaAdapter(controllers=[Monitor])
        app = AppStub(RuntimeStub(opcua_server.endpoint), Monitor())

        with pytest.raises(StartupException, match="async def"):
            await adapter.start(app)

    async def test_on_node_change_needs_a_model_node(self, opcua_server):
        class Monitor:
            @on_node_change("ns=2;s=Tank.Level")  # a raw string, not a node
            async def changed(self, value): ...

        adapter = OpcuaAdapter(controllers=[Monitor])
        app = AppStub(RuntimeStub(opcua_server.endpoint), Monitor())

        with pytest.raises(StartupException, match="needs a model node"):
            await adapter.start(app)

    async def test_missing_endpoint_fails_at_startup(self):
        class EmptyRuntime:
            def get(self, key, default=None):
                return {}

        adapter = OpcuaAdapter(controllers=[])
        with pytest.raises(StartupException, match="Missing OPC UA endpoint"):
            await adapter.start(AppStub(EmptyRuntime()))


class TestUnservedServer:
    async def test_reading_an_unserved_server_fails_fast(self):
        with pytest.raises(OpcuaConnectionError, match="No OpcuaAdapter serves"):
            await OpcuaClient().read("ns=2;s=X", server="nowhere")

    async def test_served_but_not_connected_times_out(self):
        opcua_registry.connection("slow").mark_served()
        register_resolved_config(
            OpcuaConfig(name="slow", endpoint="opc.tcp://10.0.0.1:4840", timeout=0.05)
        )

        with pytest.raises(OpcuaConnectionError, match="Timed out"):
            await OpcuaClient().read("ns=2;s=X", server="slow")


class TestHasChanged:
    async def test_matches_the_modbus_rule(self):
        # Both adapters must behave alike so users learn the rule once.
        assert _has_changed(1, 2, None)
        assert not _has_changed(2, 2, None)
        assert not _has_changed(20.0, 20.5, 0.5)
        assert _has_changed(20.0, 20.6, 0.5)
        assert _has_changed(False, True, 0.5)
