"""Device model declaration, address forms and startup validation (0.7)."""
import pytest

from xime.adapters.modbus._model import (
    Area,
    Coil,
    DataType,
    Discrete,
    Holding,
    Input,
    ModbusField,
    device,
    get_device_info,
    require_device_info,
)


@device(unit=3)
class Inverter:
    voltage: float = Holding(modicon=40001, type="float32", scale=0.1)
    current: float = Holding(2, type="float32")
    run_state: bool = Coil(0)
    fault_code: int = Input(9, type="uint16")


class TestAddressForms:
    def test_protocol_address_is_used_as_is(self):
        assert Inverter.current.address == 2

    def test_modicon_is_converted_to_protocol_address(self):
        # 40001 is the FIRST holding register, i.e. protocol address 0.
        assert Inverter.voltage.address == 0
        assert Holding(modicon=40003).address == 2
        assert Input(modicon=30010).address == 9
        assert Coil(modicon=1).address == 0
        assert Discrete(modicon=10001).address == 0

    def test_both_forms_at_once_is_refused(self):
        # Accepting both would leave which one wins to chance.
        with pytest.raises(ValueError, match="not both"):
            Holding(2, modicon=40003)

    def test_no_address_at_all_is_refused(self):
        with pytest.raises(ValueError, match="needs an address"):
            Holding()

    def test_modicon_must_match_the_area(self):
        # 40001 is holding numbering; asking for it on a coil is a mistake.
        with pytest.raises(ValueError, match="outside the coil range"):
            Coil(modicon=40001)
        with pytest.raises(ValueError, match="outside the input range"):
            Input(modicon=40001)

    def test_address_bounds(self):
        with pytest.raises(ValueError, match=">= 0"):
            Holding(-1)
        # Beyond the 16-bit space the hint points at the likely cause.
        with pytest.raises(ValueError, match="16-bit"):
            Holding(70000)


class TestFieldValidation:
    def test_unknown_type_fails_at_declaration(self):
        with pytest.raises(ValueError, match="Unknown Modbus data type"):
            Holding(0, type="float24")

    def test_bit_areas_reject_numeric_types(self):
        with pytest.raises(ValueError, match="single bits"):
            ModbusField(0, area=Area.COIL, type="uint16")

    def test_register_areas_reject_bool(self):
        with pytest.raises(ValueError, match="only valid for Coil/Discrete"):
            Holding(0, type="bool")

    def test_string_requires_count(self):
        # Modbus sends no length prefix, so the model must say where text ends.
        with pytest.raises(ValueError, match="need count"):
            Holding(0, type="string")
        assert Holding(0, type="string", count=4).word_count == 4

    def test_scale_zero_is_refused(self):
        with pytest.raises(ValueError, match="scale=0"):
            Holding(0, scale=0)

    def test_bad_order_value(self):
        with pytest.raises(ValueError, match="word_order"):
            Holding(0, word_order="middle")


class TestWordCount:
    def test_width_per_type(self):
        assert Holding(0, type="uint16").word_count == 1
        assert Holding(0, type="int32").word_count == 2
        assert Holding(0, type="float32").word_count == 2
        assert Holding(0, type="float64").word_count == 4
        assert Coil(0).word_count == 1
        assert Coil(0, count=8).word_count == 8

    def test_end_address_is_exclusive(self):
        field = Holding(10, type="int32")
        assert field.end_address == 12


class TestDescriptorProtocol:
    def test_class_access_returns_the_field(self):
        # This is what lets @on_change(Inverter.fault_code) work without a
        # magic string.
        assert isinstance(Inverter.voltage, ModbusField)
        assert Inverter.voltage.name == "voltage"

    def test_instance_access_returns_the_value(self):
        inverter = Inverter(voltage=220.5)
        assert inverter.voltage == 220.5
        assert inverter.current is None

    def test_instances_do_not_share_values(self):
        a, b = Inverter(voltage=1.0), Inverter(voltage=2.0)
        assert (a.voltage, b.voltage) == (1.0, 2.0)

    def test_generated_init_rejects_unknown_fields(self):
        with pytest.raises(TypeError, match="unexpected field"):
            Inverter(voltag=220.5)

    def test_generated_repr_lists_fields(self):
        assert "voltage=220.5" in repr(Inverter(voltage=220.5))


class TestDeviceDecorator:
    def test_device_info_is_attached(self):
        info = require_device_info(Inverter)
        assert info.unit == 3
        assert set(info.fields) == {"voltage", "current", "run_state", "fault_code"}
        assert info.byte_order == "big" and info.word_order == "big"

    def test_get_device_info_works_on_instances(self):
        assert get_device_info(Inverter()) is get_device_info(Inverter)

    def test_plain_class_has_no_device_info(self):
        class NotADevice:
            pass

        assert get_device_info(NotADevice) is None
        with pytest.raises(TypeError, match="not a Modbus device model"):
            require_device_info(NotADevice)

    def test_fields_in_area_are_sorted_by_address(self):
        @device(unit=1)
        class Scattered:
            c: int = Holding(30)
            a: int = Holding(10)
            b: int = Holding(20)

        addresses = [f.address for f in require_device_info(Scattered).fields_in(Area.HOLDING)]
        assert addresses == [10, 20, 30]

    def test_empty_model_is_refused(self):
        with pytest.raises(ValueError, match="declares no fields"):

            @device(unit=1)
            class Empty:
                pass

    def test_unit_bounds(self):
        with pytest.raises(ValueError, match="between 0 and 255"):

            @device(unit=999)
            class TooHigh:
                a: int = Holding(0)

    def test_overlapping_fields_are_refused(self):
        # A 32-bit value at 0 occupies 0 and 1, so a field at 1 is a slip that
        # would otherwise make both attributes decode from the same registers.
        with pytest.raises(ValueError, match="Overlapping Modbus fields"):

            @device(unit=1)
            class Overlap:
                wide: float = Holding(0, type="float32")
                clash: int = Holding(1)

    def test_same_address_in_different_areas_is_fine(self):
        # Coil 0 and holding 0 are unrelated storage.
        @device(unit=1)
        class Mixed:
            flag: bool = Coil(0)
            value: int = Holding(0)

        assert len(require_device_info(Mixed).fields) == 2

    def test_inherited_fields_are_collected(self):
        @device(unit=1)
        class Base:
            common: int = Holding(0)

        @device(unit=2)
        class Derived(Base):
            extra: int = Holding(1)

        assert set(require_device_info(Derived).fields) == {"common", "extra"}


class TestOrderResolution:
    def test_field_overrides_device_default(self):
        @device(unit=1, word_order="little", byte_order="little")
        class Device:
            inherited: float = Holding(0, type="float32")
            overridden: float = Holding(2, type="float32", word_order="big")

        info = require_device_info(Device)
        assert info.resolved_word_order(Device.inherited) == "little"
        assert info.resolved_byte_order(Device.inherited) == "little"
        assert info.resolved_word_order(Device.overridden) == "big"
        # byte_order was not overridden on that field -> still the device default
        assert info.resolved_byte_order(Device.overridden) == "little"


class TestDataType:
    def test_parse_accepts_labels_and_members(self):
        assert DataType.parse("float32") is DataType.FLOAT32
        assert DataType.parse(DataType.INT16) is DataType.INT16

    def test_parse_error_lists_valid_types(self):
        with pytest.raises(ValueError, match="float32"):
            DataType.parse("nope")


class TestArea:
    def test_areas_are_separate_spaces_with_their_own_traits(self):
        assert Area.COIL.is_bit and Area.COIL.writable
        assert Area.DISCRETE.is_bit and not Area.DISCRETE.writable
        assert not Area.INPUT.is_bit and not Area.INPUT.writable
        assert not Area.HOLDING.is_bit and Area.HOLDING.writable

    def test_modicon_spans(self):
        assert Area.COIL.modicon_span == (1, 9999)
        assert Area.DISCRETE.modicon_span == (10001, 19999)
        assert Area.INPUT.modicon_span == (30001, 39999)
        assert Area.HOLDING.modicon_span == (40001, 49999)


class TestCountIsRejectedWhereItDoesNothing:
    """`count` used to be accepted and silently discarded on numeric fields.

    A numeric register type already knows its own width, so Holding(0,
    type='uint16', count=5) read ONE register while the author expected five -
    with no error at declaration time and no error at read time either.
    """

    def test_numeric_holding_with_count_is_refused(self):
        with pytest.raises(ValueError, match="count is only meaningful"):
            Holding(0, type="uint16", count=5)

    def test_numeric_input_with_count_is_refused(self):
        with pytest.raises(ValueError, match="count is only meaningful"):
            Input(0, type="float32", count=2)

    def test_string_still_needs_count(self):
        field = Holding(0, type="string", count=8)
        assert field.word_count == 8

    def test_bit_fields_still_take_count(self):
        assert Coil(0, count=4).word_count == 4
        assert Discrete(0, count=3).word_count == 3

    def test_the_six_digit_modicon_error_points_somewhere(self):
        # A datasheet using extended numbering must not leave the reader stuck.
        with pytest.raises(ValueError, match="0-based protocol address"):
            Holding(modicon=400001)
