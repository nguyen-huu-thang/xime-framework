"""Slave mode: Xime serving models to a real pymodbus master (0.7).

The master here is pymodbus' own AsyncModbusTcpClient, so anything that passes
would also work for a PLC or a SCADA package on the other end of the cable.
"""
import asyncio

import pytest

from xime.adapters.modbus._decorators import on_write, serve
from xime.adapters.modbus._model import Coil, Discrete, Holding, Input, device
from xime.adapters.modbus._server import ModbusServerAdapter
from xime.core.exception.framework import StartupException

from .conftest import free_port

pytestmark = pytest.mark.asyncio


@device(unit=1)
class Plant:
    level: float = Holding(0, type="float32", scale=0.1)
    setpoint: int = Holding(2, type="uint16")
    pump: bool = Coil(0)
    temperature: int = Input(0, type="int16")
    alarm: bool = Discrete(0)


@device(unit=7)
class SecondUnit:
    counter: int = Holding(0, type="uint16")


class RuntimeStub:
    def __init__(self, port):
        self._data = {"modbus": {"server": {"host": "127.0.0.1", "port": port}}}

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
    """Runs a ModbusServerAdapter and yields a connected master client."""

    def __init__(self, *instances, refresh=0.05):
        self.port = free_port()
        self._app = AppStub(RuntimeStub(self.port), *instances)
        self.adapter = ModbusServerAdapter(
            controllers=[type(obj) for obj in instances], refresh=refresh
        )
        self._task = None
        self.master = None

    async def __aenter__(self):
        from pymodbus.client import AsyncModbusTcpClient

        await self.adapter.start(self._app)
        self._task = asyncio.create_task(self.adapter.serve())
        await asyncio.sleep(0.15)  # listener up + first refresh done
        self.master = AsyncModbusTcpClient("127.0.0.1", port=self.port, timeout=2)
        await self.master.connect()
        return self

    async def __aexit__(self, *_):
        if self.master is not None:
            self.master.close()
        await self.adapter.stop()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass


class TestServingValues:
    async def test_master_reads_what_the_provider_returns(self):
        class Emulator:
            @serve(Plant)
            async def provide(self) -> Plant:
                return Plant(
                    level=22.5, setpoint=300, pump=True,
                    temperature=-40, alarm=True,
                )

        async with RunningServer(Emulator()) as running:
            master = running.master

            holding = await master.read_holding_registers(2, count=1, device_id=1)
            assert holding.registers == [300]

            coils = await master.read_coils(0, count=1, device_id=1)
            assert coils.bits[0] is True

            inputs = await master.read_input_registers(0, count=1, device_id=1)
            # -40 as int16 two's complement
            assert inputs.registers == [65496]

            discrete = await master.read_discrete_inputs(0, count=1, device_id=1)
            assert discrete.bits[0] is True

    async def test_scaled_float_is_encoded_the_way_the_model_declares(self):
        class Emulator:
            @serve(Plant)
            async def provide(self) -> Plant:
                return Plant(level=22.5)

        async with RunningServer(Emulator()) as running:
            response = await running.master.read_holding_registers(
                0, count=2, device_id=1
            )
            # A Xime client decoding the same registers must get 22.5 back.
            from xime.adapters.modbus._codec import decode_field
            from xime.adapters.modbus._model import require_device_info

            info = require_device_info(Plant)
            assert decode_field(Plant.level, info, response.registers) == pytest.approx(22.5)

    async def test_values_follow_the_provider_over_time(self):
        state = {"value": 1}

        class Emulator:
            @serve(Plant)
            async def provide(self) -> Plant:
                return Plant(setpoint=state["value"])

        async with RunningServer(Emulator()) as running:
            first = await running.master.read_holding_registers(2, count=1, device_id=1)
            assert first.registers == [1]

            state["value"] = 42
            await asyncio.sleep(0.15)

            second = await running.master.read_holding_registers(2, count=1, device_id=1)
            assert second.registers == [42]

    async def test_reading_beyond_the_declared_span_is_refused(self):
        class Emulator:
            @serve(Plant)
            async def provide(self) -> Plant:
                return Plant(setpoint=1)

        async with RunningServer(Emulator()) as running:
            # Plant declares holding 0-2; 50 was never modelled.
            response = await running.master.read_holding_registers(
                50, count=1, device_id=1
            )
            assert response.isError()

    async def test_a_failing_provider_does_not_stop_the_server(self):
        calls = []

        class Emulator:
            @serve(Plant)
            async def provide(self) -> Plant:
                calls.append(1)
                raise RuntimeError("sensor unavailable")

        async with RunningServer(Emulator()) as running:
            await asyncio.sleep(0.15)
            response = await running.master.read_holding_registers(2, count=1, device_id=1)
            assert not response.isError()
        assert len(calls) >= 2, "the refresh loop stopped after the first failure"


class TestAcceptingWrites:
    async def test_coil_write_reaches_the_handler(self):
        received = []

        class Emulator:
            @serve(Plant)
            async def provide(self) -> Plant:
                return Plant(pump=False)

            @on_write(Plant.pump)
            async def on_pump(self, value: bool) -> None:
                received.append(value)

        async with RunningServer(Emulator()) as running:
            await running.master.write_coil(0, True, device_id=1)
            await asyncio.sleep(0.1)

        assert received == [True]

    async def test_register_write_is_decoded_through_the_model(self):
        received = []

        class Emulator:
            @serve(Plant)
            async def provide(self) -> Plant:
                return Plant(setpoint=0)

            @on_write(Plant.setpoint)
            async def on_setpoint(self, value: int) -> None:
                received.append(value)

        async with RunningServer(Emulator()) as running:
            await running.master.write_register(2, 654, device_id=1)
            await asyncio.sleep(0.1)

        assert received == [654]

    async def test_a_write_elsewhere_does_not_fire_the_handler(self):
        received = []

        class Emulator:
            @serve(Plant)
            async def provide(self) -> Plant:
                return Plant(setpoint=0)

            @on_write(Plant.setpoint)
            async def on_setpoint(self, value: int) -> None:
                received.append(value)

        async with RunningServer(Emulator()) as running:
            await running.master.write_register(0, 5, device_id=1)  # level, not setpoint
            await asyncio.sleep(0.1)

        assert received == []

    async def test_a_failing_write_handler_does_not_break_the_reply(self):
        class Emulator:
            @serve(Plant)
            async def provide(self) -> Plant:
                return Plant(setpoint=0)

            @on_write(Plant.setpoint)
            async def on_setpoint(self, value: int) -> None:
                raise RuntimeError("downstream is down")

        async with RunningServer(Emulator()) as running:
            response = await running.master.write_register(2, 1, device_id=1)
            assert not response.isError()


class TestMultipleUnits:
    async def test_each_unit_gets_its_own_storage(self):
        # The whole point of keying datastores by unit id: one process behaves
        # like several devices behind one port.
        class Emulator:
            @serve(Plant)
            async def plant(self) -> Plant:
                return Plant(setpoint=11)

            @serve(SecondUnit)
            async def second(self) -> SecondUnit:
                return SecondUnit(counter=22)

        async with RunningServer(Emulator()) as running:
            unit_1 = await running.master.read_holding_registers(2, count=1, device_id=1)
            unit_7 = await running.master.read_holding_registers(0, count=1, device_id=7)

            assert unit_1.registers == [11]
            assert unit_7.registers == [22]

    async def test_an_unknown_unit_is_not_answered(self):
        class Emulator:
            @serve(Plant)
            async def plant(self) -> Plant:
                return Plant(setpoint=11)

        async with RunningServer(Emulator()) as running:
            response = await running.master.read_holding_registers(
                2, count=1, device_id=99
            )
            assert response.isError()


class TestServerValidation:
    async def test_nothing_to_serve_is_refused(self):
        adapter = ModbusServerAdapter(controllers=[])
        with pytest.raises(StartupException, match="nothing to serve"):
            await adapter.start(AppStub(RuntimeStub(free_port())))

    async def test_two_providers_for_one_model_are_refused(self):
        class Emulator:
            @serve(Plant)
            async def one(self) -> Plant: ...

            @serve(Plant)
            async def two(self) -> Plant: ...

        adapter = ModbusServerAdapter(controllers=[Emulator])
        with pytest.raises(StartupException, match="Duplicate @serve"):
            await adapter.start(AppStub(RuntimeStub(free_port()), Emulator()))

    async def test_on_write_to_a_read_only_area_is_refused(self):
        class Emulator:
            @serve(Plant)
            async def provide(self) -> Plant: ...

            @on_write(Plant.temperature)  # input register: masters cannot write it
            async def impossible(self, value): ...

        adapter = ModbusServerAdapter(controllers=[Emulator])
        with pytest.raises(StartupException, match="Unwritable @on_write"):
            await adapter.start(AppStub(RuntimeStub(free_port()), Emulator()))

    async def test_serve_needs_a_device_model(self):
        class NotADevice:
            pass

        class Emulator:
            @serve(NotADevice)
            async def provide(self): ...

        adapter = ModbusServerAdapter(controllers=[Emulator])
        with pytest.raises(StartupException, match="not a device model"):
            await adapter.start(AppStub(RuntimeStub(free_port()), Emulator()))
