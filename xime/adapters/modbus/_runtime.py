"""The shared, live connection to one named device.

Bridges the adapter (which owns the connection lifecycle) and ModbusClient (a DI
singleton injected into business code): the adapter calls attach() once
connected and detach() on loss, while reads wait until a client is attached.
One instance per device name, owned by the registry, exactly like
MqttConnection.

This is also the only place that speaks to pymodbus response objects, so the
rest of the adapter deals in plain lists and Xime exceptions.
Đây là nơi DUY NHẤT chạm vào object response của pymodbus - phần còn lại của
adapter chỉ làm việc với list thuần và exception của Xime.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ._errors import ModbusConnectionError, ModbusDeviceError
from ._model import Area

# Which pymodbus client method serves each area. The four areas are read by
# four different function codes - this table is that mapping, nothing more.
_READ_METHODS: dict[Area, str] = {
    Area.COIL: "read_coils",
    Area.DISCRETE: "read_discrete_inputs",
    Area.HOLDING: "read_holding_registers",
    Area.INPUT: "read_input_registers",
}


class ModbusConnection:
    """Holder for the live pymodbus client of one device name."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._client: Any = None
        self._connected = asyncio.Event()
        # True once a ModbusAdapter has claimed this name (in its __init__).
        # Without an adapter, a read would wait forever for a connection that
        # is never coming -> fail fast instead.
        # Không adapter nào nhận tên này thì read sẽ chờ vô hạn -> fail fast.
        self._served = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    @property
    def is_served(self) -> bool:
        return self._served

    def mark_served(self) -> None:
        """Called by ModbusAdapter (at construction) to claim this device name."""
        self._served = True

    def attach(self, client: Any) -> None:
        self._client = client
        self._connected.set()

    def detach(self) -> None:
        self._client = None
        self._connected.clear()

    # ------------------------------------------------------------------
    # Requests
    # ------------------------------------------------------------------

    async def read(
        self,
        area: Area,
        address: int,
        count: int,
        *,
        unit: int,
        timeout: float | None = None,
    ) -> list[Any]:
        """Execute one read command and return exactly `count` raw values.

        Bit areas come back from pymodbus padded to a multiple of 8, so the
        list is trimmed here - a caller asking for 3 coils gets 3 booleans.
        Vùng bit được pymodbus đệm cho tròn 8 -> cắt lại đúng số lượng.
        """
        client = await self._require_client(timeout)
        method = getattr(client, _READ_METHODS[area])
        try:
            response = await method(address, count=count, device_id=unit)
        except Exception as exc:  # transport-level failure
            raise ModbusConnectionError(
                f"Modbus read failed on device '{self._name}' "
                f"({area.label} {address}, count={count}): {exc}"
            ) from exc

        self._raise_for_error(response, f"reading {area.label} {address}+{count}")
        values = response.bits if area.is_bit else response.registers
        return list(values)[:count]

    async def write_registers(
        self, address: int, values: list[int], *, unit: int, timeout: float | None = None
    ) -> None:
        """Write holding registers (function code 16, or 6 for a single one)."""
        client = await self._require_client(timeout)
        try:
            if len(values) == 1:
                response = await client.write_register(address, values[0], device_id=unit)
            else:
                response = await client.write_registers(address, values, device_id=unit)
        except Exception as exc:
            raise ModbusConnectionError(
                f"Modbus write failed on device '{self._name}' "
                f"(holding {address}): {exc}"
            ) from exc
        self._raise_for_error(response, f"writing holding {address}")

    async def write_coils(
        self, address: int, values: list[bool], *, unit: int, timeout: float | None = None
    ) -> None:
        """Write coils (function code 15, or 5 for a single one)."""
        client = await self._require_client(timeout)
        try:
            if len(values) == 1:
                response = await client.write_coil(address, values[0], device_id=unit)
            else:
                response = await client.write_coils(address, values, device_id=unit)
        except Exception as exc:
            raise ModbusConnectionError(
                f"Modbus write failed on device '{self._name}' "
                f"(coil {address}): {exc}"
            ) from exc
        self._raise_for_error(response, f"writing coil {address}")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _require_client(self, timeout: float | None) -> Any:
        """Wait for a live client, or explain why one will never arrive."""
        if not self._connected.is_set():
            if not self._served:
                raise ModbusConnectionError(
                    f"No ModbusAdapter serves device '{self._name}', so this "
                    f"request would block forever. Register the adapter, e.g. "
                    f"app.use(ModbusAdapter('{self._name}')), or use the name of "
                    f"a device you did register."
                )
            if timeout is None:
                await self._connected.wait()
            else:
                try:
                    await asyncio.wait_for(self._connected.wait(), timeout)
                except TimeoutError:
                    raise ModbusConnectionError(
                        f"Timed out after {timeout}s waiting for device "
                        f"'{self._name}' to connect."
                    ) from None
        client = self._client
        if client is None:  # detached between the wait and here
            raise ModbusConnectionError(
                f"Modbus connection '{self._name}' is not available"
            )
        return client

    @staticmethod
    def _raise_for_error(response: Any, what: str) -> None:
        """Turn a Modbus exception response into a ModbusDeviceError.

        pymodbus reports device refusals through the response object rather
        than by raising, so a missing check here would silently decode garbage
        from an error frame.
        pymodbus báo lỗi qua object response chứ không ném - thiếu kiểm tra ở
        đây thì sẽ decode nhầm từ frame lỗi.
        """
        if response is None:
            raise ModbusConnectionError(f"No response while {what}")
        if hasattr(response, "isError") and response.isError():
            code = getattr(response, "exception_code", None)
            raise ModbusDeviceError(code, what)
