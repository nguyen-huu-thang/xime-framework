"""Shared fixtures: a real pymodbus server running in-process.

Reading a device is the kind of thing that only proves out against a real
protocol implementation — a mock would happily agree with whatever the codec
believes. So these tests start an actual Modbus TCP server in the same event
loop and talk to it over a real socket on localhost.
Mock sẽ đồng ý với bất cứ điều gì codec tin, nên test dựng server Modbus thật
trong cùng event loop và nói chuyện qua socket thật.

The server is built with SimData/SimDevice, not the older ModbusServerContext:
that API is deprecated for pymodbus v4, and on 3.14 its compatibility shim
already shifts addresses by one. SimDevice also models the four areas as
genuinely separate blocks, which is exactly the shape Xime's device model
assumes.
Dùng SimData/SimDevice chứ không phải ModbusServerContext: API cũ đã deprecated
và trên 3.14 lớp tương thích của nó còn lệch địa chỉ một đơn vị.
"""
from __future__ import annotations

import socket

import pytest_asyncio

from xime.adapters.modbus._client import clear_resolved_configs
from xime.adapters.modbus._config import modbus_registry

# pymodbus function codes, as used by SimCore.async_getValues/async_setValues.
FC_COIL = 1
FC_DISCRETE = 2
FC_HOLDING = 3
FC_INPUT = 4

TEST_UNIT = 1


def free_port() -> int:
    """Ask the OS for a port nobody is using, to keep tests parallel-safe."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class ServerHandle:
    """Access to the simulated device's storage, for arranging and asserting."""

    def __init__(self, host: str, port: int, server) -> None:
        self.host = host
        self.port = port
        self._server = server

    async def set(self, func_code: int, address: int, values: list) -> None:
        await self._server.async_setValues(TEST_UNIT, func_code, address, values)

    async def get(self, func_code: int, address: int, count: int) -> list:
        return await self._server.async_getValues(
            TEST_UNIT, func_code, address, count
        )


@pytest_asyncio.fixture
async def modbus_server():
    """Start a Modbus TCP server holding one unit; yield a ServerHandle.

    Addresses outside the declared blocks are invalid on purpose - the server
    answers ILLEGAL DATA ADDRESS, which is what makes the read-planning tests
    meaningful.
    Địa chỉ ngoài khối khai báo là không hợp lệ - server trả ILLEGAL DATA
    ADDRESS, nhờ vậy test lập kế hoạch đọc mới có ý nghĩa.
    """
    from pymodbus.server import ModbusTcpServer
    from pymodbus.simulator import DataType, SimData, SimDevice

    device = SimDevice(
        TEST_UNIT,
        simdata=(
            [SimData(0, values=[False] * 200, datatype=DataType.BITS)],
            [SimData(0, values=[False] * 200, datatype=DataType.BITS)],
            [SimData(0, values=[0] * 600, datatype=DataType.REGISTERS)],
            [SimData(0, values=[0] * 200, datatype=DataType.REGISTERS)],
        ),
    )

    port = free_port()
    server = ModbusTcpServer(device, address=("127.0.0.1", port))
    # background=True returns as soon as the listener is accepting. Without it,
    # serve_forever() awaits `self.serving`, which only resolves at SHUTDOWN —
    # awaiting it here hangs the test run forever.
    # Thiếu background=True thì serve_forever() chờ tới lúc server DỪNG -> treo.
    await server.serve_forever(background=True)

    try:
        yield ServerHandle("127.0.0.1", port, server)
    finally:
        await server.shutdown()


@pytest_asyncio.fixture(autouse=True)
def clean_registry():
    """Every test starts with an empty registry and no cached configs."""
    modbus_registry.reset()
    clear_resolved_configs()
    yield
    modbus_registry.reset()
    clear_resolved_configs()


@pytest_asyncio.fixture
async def connected(modbus_server):
    """A ModbusConnection with a live pymodbus client attached.

    Attaching by hand (rather than running ModbusAdapter) is deliberate: it
    proves the connection holder is genuinely independent of the adapter, which
    is what lets ModbusClient be a plain DI singleton.
    Gắn thủ công để chứng minh connection độc lập với adapter.
    """
    from pymodbus.client import AsyncModbusTcpClient

    connection = modbus_registry.connection("default")
    connection.mark_served()

    client = AsyncModbusTcpClient(modbus_server.host, port=modbus_server.port, timeout=2)
    await client.connect()
    connection.attach(client)
    try:
        yield connection, modbus_server
    finally:
        connection.detach()
        client.close()
