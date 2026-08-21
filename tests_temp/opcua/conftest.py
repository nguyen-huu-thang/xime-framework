"""Shared fixtures: a real asyncua server running in-process.

Same reasoning as the Modbus tests - a mock would agree with whatever the
adapter believes, so these talk to a genuine OPC UA server over a socket.
"""
from __future__ import annotations

import socket

import pytest_asyncio

from xime.adapters.opcua._client import clear_resolved_configs
from xime.adapters.opcua._config import opcua_registry

NAMESPACE = "http://xime.test/tanks"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class ServerHandle:
    """The running server plus helpers to arrange and assert on its values."""

    def __init__(self, endpoint: str, variables: dict) -> None:
        self.endpoint = endpoint
        self._variables = variables

    async def set(self, node_id: str, value) -> None:
        await self._variables[node_id].write_value(value)

    async def get(self, node_id: str):
        return await self._variables[node_id].read_value()


@pytest_asyncio.fixture(autouse=True)
def clean_registry():
    opcua_registry.reset()
    clear_resolved_configs()
    yield
    opcua_registry.reset()
    clear_resolved_configs()


@pytest_asyncio.fixture
async def opcua_server():
    """An OPC UA server exposing Tank.Level / Tank.Setpoint / Tank.Alarm."""
    from asyncua import Server, ua

    port = free_port()
    endpoint = f"opc.tcp://127.0.0.1:{port}/xime-test"

    server = Server()
    await server.init()
    server.set_endpoint(endpoint)
    server.set_server_name("Xime test server")
    await server.register_namespace(NAMESPACE)

    folder = await server.nodes.objects.add_folder(
        ua.NodeId("TankFolder", 0, ua.NodeIdType.String), "Tank"
    )
    variables = {}
    for node_id, initial in (
        ("ns=2;s=Tank.Level", 0.0),
        ("ns=2;s=Tank.Setpoint", 0.0),
        ("ns=2;s=Tank.Alarm", False),
    ):
        variable = await folder.add_variable(
            ua.NodeId.from_string(node_id), node_id.split(".")[-1], initial
        )
        await variable.set_writable()
        variables[node_id] = variable

    await server.start()
    try:
        yield ServerHandle(endpoint, variables)
    finally:
        await server.stop()
