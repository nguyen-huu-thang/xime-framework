"""Xime serving OPC UA to a real asyncua client (0.7)."""
import asyncio

import pytest

from xime.adapters.opcua._decorators import on_node_write, serve_nodes
from xime.adapters.opcua._model import Node, node_model
from xime.adapters.opcua._server import OpcuaServerAdapter
from xime.core.exception.framework import StartupException

from .conftest import free_port

pytestmark = pytest.mark.asyncio


@node_model(namespace="http://xime.test/served")
class Boiler:
    temperature: float = Node("ns=2;s=Boiler.Temperature", writable=False, default=0.0)
    setpoint: float = Node("ns=2;s=Boiler.Setpoint", default=0.0)


class RuntimeStub:
    def __init__(self, endpoint, **server_extra):
        self._data = {"opcua": {"server": {"endpoint": endpoint, **server_extra}}}

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


class RunningServer:
    """Runs an OpcuaServerAdapter and yields a connected client."""

    def __init__(self, *instances, refresh=0.1, **server_extra):
        self.endpoint = f"opc.tcp://127.0.0.1:{free_port()}/xime"
        self._app = AppStub(RuntimeStub(self.endpoint, **server_extra), *instances)
        self.adapter = OpcuaServerAdapter(
            controllers=[type(obj) for obj in instances], refresh=refresh
        )
        self._task = None
        self.client = None

    async def __aenter__(self):
        from asyncua import Client

        await self.adapter.start(self._app)
        self._task = asyncio.create_task(self.adapter.serve())
        await asyncio.sleep(0.5)  # listener up + first refresh
        self.client = Client(self.endpoint, timeout=4)
        await self.client.connect()
        return self

    async def __aexit__(self, *_):
        if self.client is not None:
            try:
                await self.client.disconnect()
            except Exception:
                pass
        await self.adapter.stop()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

    async def read(self, node_id: str):
        return await self.client.get_node(node_id).read_value()

    async def write(self, node_id: str, value) -> None:
        await self.client.get_node(node_id).write_value(value)


class TestServingNodes:
    async def test_client_reads_what_the_provider_returns(self):
        class Emulator:
            @serve_nodes(Boiler)
            async def provide(self) -> Boiler:
                return Boiler(temperature=88.5, setpoint=90.0)

        async with RunningServer(Emulator()) as running:
            assert await running.read("ns=2;s=Boiler.Temperature") == 88.5
            assert await running.read("ns=2;s=Boiler.Setpoint") == 90.0

    async def test_values_follow_the_provider_over_time(self):
        state = {"t": 10.0}

        class Emulator:
            @serve_nodes(Boiler)
            async def provide(self) -> Boiler:
                return Boiler(temperature=state["t"])

        async with RunningServer(Emulator()) as running:
            assert await running.read("ns=2;s=Boiler.Temperature") == 10.0
            state["t"] = 42.0
            await asyncio.sleep(0.3)
            assert await running.read("ns=2;s=Boiler.Temperature") == 42.0

    async def test_a_failing_provider_does_not_stop_the_server(self):
        calls = []

        class Emulator:
            @serve_nodes(Boiler)
            async def provide(self) -> Boiler:
                calls.append(1)
                raise RuntimeError("sensor unavailable")

        async with RunningServer(Emulator()) as running:
            await asyncio.sleep(0.3)
            # The server still answers, with the declared default.
            assert await running.read("ns=2;s=Boiler.Temperature") == 0.0
        assert len(calls) >= 2, "the refresh loop stopped after the first failure"

    async def test_the_model_namespace_is_registered(self):
        class Emulator:
            @serve_nodes(Boiler)
            async def provide(self) -> Boiler:
                return Boiler(temperature=1.0)

        async with RunningServer(Emulator()) as running:
            namespaces = await running.client.get_namespace_array()
            assert "http://xime.test/served" in namespaces


class TestAcceptingWrites:
    async def test_client_write_reaches_the_handler(self):
        received = []

        class Emulator:
            @serve_nodes(Boiler)
            async def provide(self) -> Boiler:
                return Boiler(setpoint=0.0)

            @on_node_write(Boiler.setpoint)
            async def setpoint_written(self, value: float) -> None:
                received.append(value)

        async with RunningServer(Emulator(), refresh=5.0) as running:
            await running.write("ns=2;s=Boiler.Setpoint", 77.0)
            await asyncio.sleep(0.3)

        assert 77.0 in received

    async def test_a_failing_write_handler_does_not_break_the_response(self):
        class Emulator:
            @serve_nodes(Boiler)
            async def provide(self) -> Boiler:
                return Boiler(setpoint=0.0)

            @on_node_write(Boiler.setpoint)
            async def setpoint_written(self, value: float) -> None:
                raise RuntimeError("downstream is down")

        async with RunningServer(Emulator(), refresh=5.0) as running:
            # The write itself must still succeed from the client's point of view.
            await running.write("ns=2;s=Boiler.Setpoint", 5.0)
            assert await running.read("ns=2;s=Boiler.Setpoint") == 5.0


class TestServerValidation:
    async def test_nothing_to_serve_is_refused(self):
        adapter = OpcuaServerAdapter(controllers=[])
        endpoint = f"opc.tcp://127.0.0.1:{free_port()}/xime"
        with pytest.raises(StartupException, match="nothing to serve"):
            await adapter.start(AppStub(RuntimeStub(endpoint)))

    async def test_two_providers_for_one_model_are_refused(self):
        class Emulator:
            @serve_nodes(Boiler)
            async def one(self) -> Boiler: ...

            @serve_nodes(Boiler)
            async def two(self) -> Boiler: ...

        adapter = OpcuaServerAdapter(controllers=[Emulator])
        endpoint = f"opc.tcp://127.0.0.1:{free_port()}/xime"
        with pytest.raises(StartupException, match="Duplicate @serve_nodes"):
            await adapter.start(AppStub(RuntimeStub(endpoint), Emulator()))

    async def test_serve_nodes_needs_a_node_model(self):
        class NotAModel:
            pass

        class Emulator:
            @serve_nodes(NotAModel)
            async def provide(self): ...

        adapter = OpcuaServerAdapter(controllers=[Emulator])
        endpoint = f"opc.tcp://127.0.0.1:{free_port()}/xime"
        with pytest.raises(StartupException, match="not a node model"):
            await adapter.start(AppStub(RuntimeStub(endpoint), Emulator()))

    async def test_on_node_write_needs_a_model_node(self):
        class Emulator:
            @serve_nodes(Boiler)
            async def provide(self) -> Boiler: ...

            @on_node_write("ns=2;s=Boiler.Setpoint")  # a raw string
            async def written(self, value): ...

        adapter = OpcuaServerAdapter(controllers=[Emulator])
        endpoint = f"opc.tcp://127.0.0.1:{free_port()}/xime"
        with pytest.raises(StartupException, match="Invalid @on_node_write"):
            await adapter.start(AppStub(RuntimeStub(endpoint), Emulator()))

    async def test_an_unknown_security_mode_fails_at_startup(self):
        # Typos in a security setting must never be shrugged off - the whole
        # point of the setting is that it is enforced.
        class Emulator:
            @serve_nodes(Boiler)
            async def provide(self) -> Boiler: ...

        adapter = OpcuaServerAdapter(controllers=[Emulator])
        endpoint = f"opc.tcp://127.0.0.1:{free_port()}/xime"
        app = AppStub(RuntimeStub(endpoint, security="Encrypt"), Emulator())

        with pytest.raises(StartupException, match="Invalid OPC UA security mode"):
            await adapter.start(app)


@node_model(namespace="http://xime.test/typed")
class Mixed:
    """No default= anywhere - the annotation alone must fix each node's type."""

    running: bool = Node("ns=2;s=Mixed.Running")
    label: str = Node("ns=2;s=Mixed.Label")
    count: int = Node("ns=2;s=Mixed.Count")
    level: float = Node("ns=2;s=Mixed.Level")


class TestNodeDataTypes:
    """An OPC UA variable takes its data type from the value it is created with.

    Before this was handled, every node without an explicit `default=` was
    created as a Double, so publishing a bool, a string or an int failed with
    BadTypeMismatch - inside a caught-and-logged handler, which meant the node
    simply kept its initial 0.0 forever with nothing visible to the caller.
    Every existing server test declared `default=0.0` on float nodes, which is
    why 1427 tests missed it.
    """

    async def test_non_float_nodes_publish_without_an_explicit_default(self):
        class Emulator:
            @serve_nodes(Mixed)
            async def provide(self) -> Mixed:
                return Mixed(running=True, label="ok", count=7, level=1.5)

        async with RunningServer(Emulator()) as running:
            assert await running.read("ns=2;s=Mixed.Running") is True
            assert await running.read("ns=2;s=Mixed.Label") == "ok"
            assert await running.read("ns=2;s=Mixed.Count") == 7
            assert await running.read("ns=2;s=Mixed.Level") == 1.5

    async def test_an_untypeable_node_fails_at_startup(self):
        # Neither an annotation nor a default: guessing would recreate exactly
        # the silent failure above, so start-up must stop and name the node.
        @node_model(namespace="http://xime.test/untyped")
        class Untyped:
            mystery = Node("ns=2;s=Untyped.Mystery")

        class Emulator:
            @serve_nodes(Untyped)
            async def provide(self) -> Untyped: ...

        adapter = OpcuaServerAdapter(controllers=[Emulator])
        endpoint = f"opc.tcp://127.0.0.1:{free_port()}/xime"
        with pytest.raises(StartupException, match="Cannot determine the OPC UA type"):
            await adapter.start(AppStub(RuntimeStub(endpoint), Emulator()))

    async def test_one_rejected_node_does_not_block_the_others(self):
        # `count` is an int node; handing it a string is refused by the server.
        # The nodes declared after it must still be published - with one try
        # around the whole loop, the first rejection froze every later node.
        class Emulator:
            @serve_nodes(Mixed)
            async def provide(self) -> Mixed:
                return Mixed(running=True, label="ok", count="not-an-int", level=1.5)

        async with RunningServer(Emulator()) as running:
            assert await running.read("ns=2;s=Mixed.Count") == 0, "bad write applied?"
            assert await running.read("ns=2;s=Mixed.Level") == 1.5
            assert await running.read("ns=2;s=Mixed.Running") is True


class TestApplicationUri:
    """Sign / SignAndEncrypt require the application URI to match the cert.

    A server validates the URI in a client's session request against the URI in
    the client's certificate and answers BadCertificateUriInvalid when they
    differ. asyncua defaults to its own placeholder and never reads the value
    out of the certificate, so without this setting no real certificate could
    be used - the two secure modes were effectively unusable.
    """

    async def test_server_advertises_the_configured_uri(self):
        class Emulator:
            @serve_nodes(Boiler)
            async def provide(self) -> Boiler:
                return Boiler(temperature=1.0)

        uri = "urn:xime.test:opcua:server"
        async with RunningServer(Emulator(), application_uri=uri) as running:
            assert running.adapter._server.get_application_uri() == uri

    async def test_left_unset_the_server_keeps_the_library_default(self):
        class Emulator:
            @serve_nodes(Boiler)
            async def provide(self) -> Boiler:
                return Boiler(temperature=1.0)

        async with RunningServer(Emulator()) as running:
            assert running.adapter._server.get_application_uri()
