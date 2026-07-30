"""ModbusClient against a real pymodbus TCP server (0.7).

Everything here goes over a real socket to a real protocol implementation, so a
passing test means the codec, the planner and the wire format actually agree.
"""
import pytest

from xime.adapters.modbus._client import (
    ModbusClient,
    register_resolved_config,
)
from xime.adapters.modbus._codec import encode_field
from xime.adapters.modbus._config import ModbusConfig, modbus_registry
from xime.adapters.modbus._errors import (
    ModbusCodecError,
    ModbusConnectionError,
    ModbusDeviceError,
)
from xime.adapters.modbus._model import (
    Coil,
    Discrete,
    Holding,
    Input,
    device,
    require_device_info,
)

from .conftest import FC_COIL, FC_DISCRETE, FC_HOLDING, FC_INPUT

pytestmark = pytest.mark.asyncio


@device(unit=1)
class Inverter:
    voltage: float = Holding(modicon=40001, type="float32", scale=0.1)
    current: float = Holding(2, type="float32")
    setpoint: int = Holding(4, type="uint16")
    run_state: bool = Coil(0)
    fault_code: int = Input(9, type="uint16")
    alarm: bool = Discrete(3)


INFO = require_device_info(Inverter)


class TestReadWholeModel:
    async def test_reads_every_field_across_all_four_areas(self, connected):
        _, server = connected
        # voltage: 2205 as float32 -> * 0.1 scale -> 220.5
        await server.set(FC_HOLDING, 0, encode_field(Inverter.voltage, INFO, 220.5))
        await server.set(FC_HOLDING, 2, encode_field(Inverter.current, INFO, 12.5))
        await server.set(FC_HOLDING, 4, [400])
        await server.set(FC_COIL, 0, [True])
        await server.set(FC_INPUT, 9, [7])
        await server.set(FC_DISCRETE, 3, [True])

        result = await ModbusClient().read(Inverter)

        assert result.voltage == pytest.approx(220.5)
        assert result.current == pytest.approx(12.5)
        assert result.setpoint == 400
        assert result.run_state is True
        assert result.fault_code == 7
        assert result.alarm is True

    async def test_negative_float_survives_the_wire(self, connected):
        _, server = connected
        await server.set(FC_HOLDING, 2, encode_field(Inverter.current, INFO, -3.75))

        result = await ModbusClient().read(Inverter)
        assert result.current == pytest.approx(-3.75)

    async def test_unset_registers_read_as_zero(self, connected):
        result = await ModbusClient().read(Inverter)
        assert result.setpoint == 0
        assert result.run_state is False


class TestReadSingleField:
    async def test_reads_only_that_field(self, connected):
        _, server = connected
        await server.set(FC_HOLDING, 4, [1234])

        assert await ModbusClient().read_field(Inverter.setpoint) == 1234

    async def test_bit_field(self, connected):
        _, server = connected
        await server.set(FC_COIL, 0, [True])

        assert await ModbusClient().read_field(Inverter.run_state) is True


class TestWrite:
    async def test_write_register_field(self, connected):
        _, server = connected
        client = ModbusClient()

        await client.write(Inverter.setpoint, 777)

        assert await server.get(FC_HOLDING, 4, 1) == [777]
        assert await client.read_field(Inverter.setpoint) == 777

    async def test_write_applies_the_scale(self, connected):
        client = ModbusClient()

        await client.write(Inverter.voltage, 220.5)

        assert await client.read_field(Inverter.voltage) == pytest.approx(220.5)

    async def test_write_coil(self, connected):
        _, server = connected
        client = ModbusClient()

        await client.write(Inverter.run_state, True)
        assert await server.get(FC_COIL, 0, 1) == [True]

        await client.write(Inverter.run_state, False)
        assert await server.get(FC_COIL, 0, 1) == [False]

    async def test_write_device_updates_only_the_fields_that_hold_values(
        self, connected
    ):
        _, server = connected
        await server.set(FC_HOLDING, 4, [111])

        await ModbusClient().write_device(Inverter(run_state=True))

        assert await server.get(FC_COIL, 0, 1) == [True]
        # setpoint was None on the instance -> left untouched
        assert await server.get(FC_HOLDING, 4, 1) == [111]

    async def test_write_device_skips_read_only_areas(self, connected):
        _, server = connected
        # fault_code is an input register: unwritable, but naming it should not
        # blow up a whole-device write.
        await ModbusClient().write_device(Inverter(fault_code=9, setpoint=5))

        assert await server.get(FC_HOLDING, 4, 1) == [5]

    async def test_writing_a_read_only_field_directly_is_refused(self, connected):
        with pytest.raises(ModbusCodecError, match="read-only"):
            await ModbusClient().write(Inverter.fault_code, 1)


class TestDeviceErrors:
    async def test_illegal_data_address_is_reported_with_its_meaning(self, connected):
        # The server declares 600 holding registers; reading past the end is
        # exactly what a naive one-big-block planner would cause.
        @device(unit=1)
        class OutOfRange:
            value: int = Holding(5000)

        with pytest.raises(ModbusDeviceError) as excinfo:
            await ModbusClient().read(OutOfRange)

        assert excinfo.value.code == 2
        assert "ILLEGAL DATA ADDRESS" in str(excinfo.value)

    async def test_unit_override_reaches_a_different_unit(self, connected):
        @device(unit=9)
        class WrongUnit:
            value: int = Holding(0)

        _, server = connected
        await server.set(FC_HOLDING, 0, [42])

        # The model says unit 9; the caller overrides to the unit that exists.
        assert await ModbusClient().read_field(WrongUnit.value, unit=1) == 42


class TestUnservedDevice:
    async def test_reading_an_unserved_device_fails_fast(self):
        # Nothing called mark_served() for "nowhere": without this check the
        # read would wait forever for a connection that is not coming.
        with pytest.raises(ModbusConnectionError, match="No ModbusAdapter serves"):
            await ModbusClient().read_field(Inverter.setpoint, device="nowhere")

    async def test_served_but_not_yet_connected_times_out(self):
        modbus_registry.connection("slow").mark_served()
        register_resolved_config(
            ModbusConfig(name="slow", host="10.0.0.1", timeout=0.05)
        )

        with pytest.raises(ModbusConnectionError, match="Timed out"):
            await ModbusClient().read_field(Inverter.setpoint, device="slow")


class TestPlanningAffectsTheWire:
    async def test_scattered_fields_are_read_as_separate_commands(self, connected):
        # 0 and 550 are 550 apart: one big block would ask for 551 registers,
        # over the 125-register protocol limit, and fail outright.
        @device(unit=1)
        class Scattered:
            near: int = Holding(0)
            far: int = Holding(550)

        _, server = connected
        await server.set(FC_HOLDING, 0, [11])
        await server.set(FC_HOLDING, 550, [22])

        result = await ModbusClient().read(Scattered)
        assert (result.near, result.far) == (11, 22)

    async def test_a_read_spanning_beyond_the_device_fails(self, connected):
        # Proves the previous test is not a coincidence: had the planner merged
        # 0 and 550 into one command, this is the error it would have produced.
        connection, _ = connected
        from xime.adapters.modbus._model import Area

        with pytest.raises(ModbusDeviceError):
            await connection.read(Area.HOLDING, 590, 20, unit=1)

    async def test_max_gap_zero_still_reads_everything(self, connected):
        @device(unit=1)
        class Gapped:
            a: int = Holding(0)
            b: int = Holding(5)

        _, server = connected
        await server.set(FC_HOLDING, 0, [1])
        await server.set(FC_HOLDING, 5, [2])
        register_resolved_config(
            ModbusConfig(name="default", host="127.0.0.1", max_gap=0)
        )

        result = await ModbusClient().read(Gapped)
        assert (result.a, result.b) == (1, 2)
