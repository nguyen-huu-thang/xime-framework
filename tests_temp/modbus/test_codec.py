"""Register <-> value conversion: word/byte order, scale, strings, bits (0.7).

These tests need no network and no server - pymodbus' converters are
classmethods, so the codec is exercised directly on register lists.
"""
import pytest

from xime.adapters.modbus._codec import (
    ModbusCodecError,
    decode_device,
    decode_field,
    encode_field,
    swap_bytes,
)
from xime.adapters.modbus._model import (
    Area,
    Coil,
    Discrete,
    Holding,
    Input,
    device,
    require_device_info,
)


@device(unit=1)
class Big:
    value: float = Holding(0, type="float32")
    scaled: float = Holding(2, type="uint16", scale=0.1)
    signed: int = Holding(3, type="int16")
    wide: int = Holding(4, type="int32")
    label: str = Holding(6, type="string", count=3)
    flag: bool = Coil(0)
    flags: list = Coil(10, count=3)
    sensor: int = Input(0, type="uint16")
    alarm: bool = Discrete(0)


BIG = require_device_info(Big)


@device(unit=1, word_order="little")
class WordSwapped:
    value: float = Holding(0, type="float32")


@device(unit=1, byte_order="little")
class ByteSwapped:
    value: int = Holding(0, type="uint16")


class TestNumericRoundTrip:
    def test_float32(self):
        registers = encode_field(Big.value, BIG, 220.5)
        assert len(registers) == 2
        assert decode_field(Big.value, BIG, registers) == 220.5

    def test_int32_negative(self):
        registers = encode_field(Big.wide, BIG, -70000)
        assert decode_field(Big.wide, BIG, registers) == -70000

    def test_int16_negative_uses_two_complement(self):
        assert encode_field(Big.signed, BIG, -5) == [65531]
        assert decode_field(Big.signed, BIG, [65531]) == -5

    def test_uint16_upper_bound(self):
        field = Holding(0, type="uint16")
        assert decode_field(field, BIG, [65535]) == 65535


class TestWordOrder:
    def test_little_word_order_swaps_the_register_pair(self):
        big = encode_field(Big.value, BIG, 220.5)
        little = encode_field(WordSwapped.value, require_device_info(WordSwapped), 220.5)
        assert little == list(reversed(big))

    def test_round_trip_holds_within_one_order(self):
        info = require_device_info(WordSwapped)
        registers = encode_field(WordSwapped.value, info, 220.5)
        assert decode_field(WordSwapped.value, info, registers) == 220.5

    def test_wrong_word_order_yields_garbage_not_an_error(self):
        # This is precisely why the device model exists: reading a word-swapped
        # device with the default order returns a plausible-looking number, not
        # a failure. Nothing in the protocol can catch it.
        registers = encode_field(Big.value, BIG, 220.5)
        decoded = decode_field(
            WordSwapped.value, require_device_info(WordSwapped), registers
        )
        assert decoded != pytest.approx(220.5)


class TestByteOrder:
    def test_swap_bytes_helper(self):
        assert swap_bytes([0x1234, 0xABCD]) == [0x3412, 0xCDAB]
        assert swap_bytes(swap_bytes([0x1234])) == [0x1234]

    def test_little_byte_order_round_trip(self):
        info = require_device_info(ByteSwapped)
        registers = encode_field(ByteSwapped.value, info, 0x1234)
        # On the wire the bytes are reversed compared to the spec default...
        assert registers == [0x3412]
        # ...but decoding with the same setting gives the value back.
        assert decode_field(ByteSwapped.value, info, registers) == 0x1234


class TestScale:
    def test_decode_applies_scale(self):
        assert decode_field(Big.scaled, BIG, [2205]) == pytest.approx(220.5)

    def test_encode_inverts_scale(self):
        assert encode_field(Big.scaled, BIG, 220.5) == [2205]

    def test_integer_fields_round_rather_than_truncate(self):
        # Truncation would turn a 220.5 round-trip into 220.4.
        field = Holding(0, type="uint16", scale=0.1)
        assert encode_field(field, BIG, 220.5) == [2205]
        assert encode_field(field, BIG, 12.34) == [123]

    def test_offset_is_applied_after_scale(self):
        field = Holding(0, type="int16", scale=0.5, offset=-40)
        assert decode_field(field, BIG, [100]) == pytest.approx(10.0)
        assert encode_field(field, BIG, 10.0) == [100]

    def test_no_scale_leaves_the_value_untouched(self):
        assert decode_field(Big.signed, BIG, [7]) == 7
        assert isinstance(decode_field(Big.signed, BIG, [7]), int)


class TestString:
    def test_round_trip(self):
        registers = encode_field(Big.label, BIG, "ABCDE")
        assert len(registers) == 3
        assert decode_field(Big.label, BIG, registers) == "ABCDE"

    def test_short_string_is_null_padded_to_the_declared_span(self):
        # Without padding, the tail of a previous longer value would survive.
        registers = encode_field(Big.label, BIG, "AB")
        assert len(registers) == 3
        assert registers[1:] == [0, 0]

    def test_too_long_string_is_refused(self):
        with pytest.raises(ModbusCodecError, match="reserves"):
            encode_field(Big.label, BIG, "ABCDEFGHIJ")

    def test_non_string_value_is_refused(self):
        with pytest.raises(ModbusCodecError, match="string field"):
            encode_field(Big.label, BIG, 42)


class TestBits:
    def test_single_coil(self):
        assert decode_field(Big.flag, BIG, [True]) is True
        assert decode_field(Big.flag, BIG, [False]) is False
        assert encode_field(Big.flag, BIG, True) == [True]

    def test_multi_bit_field_returns_a_list(self):
        assert decode_field(Big.flags, BIG, [True, False, True]) == [True, False, True]
        assert encode_field(Big.flags, BIG, [True, False, True]) == [True, False, True]

    def test_multi_bit_field_checks_the_value_count(self):
        with pytest.raises(ModbusCodecError, match="covers 3 bit"):
            encode_field(Big.flags, BIG, [True, False])

    def test_extra_bits_from_the_read_are_ignored(self):
        # Reads are planned per block, so a field often sits inside a longer
        # payload; only its own span is decoded.
        assert decode_field(Big.flag, BIG, [True, False, False]) is True


class TestReadOnlyAreas:
    def test_input_registers_cannot_be_written(self):
        with pytest.raises(ModbusCodecError, match="read-only"):
            encode_field(Big.sensor, BIG, 5)

    def test_discrete_inputs_cannot_be_written(self):
        with pytest.raises(ModbusCodecError, match="read-only"):
            encode_field(Big.alarm, BIG, True)


class TestShortPayloads:
    def test_missing_registers_are_reported_with_the_field_name(self):
        with pytest.raises(ModbusCodecError, match="'value' needs 2 register"):
            decode_field(Big.value, BIG, [17244])

    def test_missing_bits_are_reported(self):
        with pytest.raises(ModbusCodecError, match="'flags' needs 3 bit"):
            decode_field(Big.flags, BIG, [True])


class TestDecodeDevice:
    def test_builds_an_instance_from_block_payloads(self):
        holding = encode_field(Big.value, BIG, 220.5) + [2205, 65531]
        payloads = {
            Area.HOLDING: {0: holding},
            Area.COIL: {0: [True], 10: [True, False, True]},
            Area.INPUT: {0: [77]},
            Area.DISCRETE: {0: [False]},
        }
        # 'wide' and 'label' are not covered on purpose -> decode only what was read.
        info = require_device_info(Partial)
        result = decode_device(info, payloads)
        assert result.value == 220.5
        assert result.scaled == pytest.approx(220.5)
        assert result.flag is True
        assert result.flags == [True, False, True]
        assert result.sensor == 77
        assert result.alarm is False

    def test_uncovered_field_is_reported_clearly(self):
        with pytest.raises(ModbusCodecError, match="no read command covered"):
            decode_device(BIG, {Area.HOLDING: {0: [0, 0]}})


@device(unit=1)
class Partial:
    value: float = Holding(0, type="float32")
    scaled: float = Holding(2, type="uint16", scale=0.1)
    signed: int = Holding(3, type="int16")
    flag: bool = Coil(0)
    flags: list = Coil(10, count=3)
    sensor: int = Input(0, type="uint16")
    alarm: bool = Discrete(0)
