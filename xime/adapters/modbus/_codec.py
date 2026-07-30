"""Register <-> typed value conversion.

Everything that makes a raw Modbus reading meaningful lives here: joining words
into wide types, honouring the device's word/byte order, and applying the
linear scale the datasheet specifies.

The heavy lifting (struct packing per data type) is delegated to pymodbus'
`convert_from_registers` / `convert_to_registers`, which are classmethods and
need no live client — so this whole module is unit-testable without a network
or even a server. On top of that the codec adds two things pymodbus does not
offer: byte-order swapping inside each register, and scale/offset.
Phần đóng gói theo kiểu để pymodbus lo; codec thêm hai thứ pymodbus không có:
hoán byte trong từng register, và scale/offset.

pymodbus is imported lazily so `_model` and this module can be imported without
the `xime[modbus]` extra; only actually converting needs it.
"""

from __future__ import annotations

from typing import Any

from ._errors import ModbusCodecError
from ._model import Area, DataType, DeviceInfo, ModbusField

# Xime data type -> pymodbus DATATYPE member name. BOOL never reaches pymodbus
# (bit areas come back as booleans already), so it has no entry.
_PYMODBUS_TYPE_NAMES: dict[DataType, str] = {
    DataType.INT16: "INT16",
    DataType.UINT16: "UINT16",
    DataType.INT32: "INT32",
    DataType.UINT32: "UINT32",
    DataType.INT64: "INT64",
    DataType.UINT64: "UINT64",
    DataType.FLOAT32: "FLOAT32",
    DataType.FLOAT64: "FLOAT64",
    DataType.STRING: "STRING",
}

_INTEGER_TYPES = frozenset({
    DataType.INT16, DataType.UINT16, DataType.INT32,
    DataType.UINT32, DataType.INT64, DataType.UINT64,
})


def _pymodbus_datatype(data_type: DataType):
    """Resolve the pymodbus DATATYPE member for a Xime data type (lazy import)."""
    try:
        from pymodbus.client.mixin import ModbusClientMixin
    except ImportError:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            "The Modbus adapter requires pymodbus. Run: pip install 'xime[modbus]'"
        ) from None

    name = _PYMODBUS_TYPE_NAMES.get(data_type)
    if name is None:
        raise ModbusCodecError(
            f"{data_type.label} values are not stored in registers"
        )
    return ModbusClientMixin.DATATYPE[name]


def _convert_from_registers(registers: list[int], data_type: DataType, word_order: str):
    from pymodbus.client.mixin import ModbusClientMixin

    return ModbusClientMixin.convert_from_registers(
        registers, _pymodbus_datatype(data_type), word_order=word_order
    )


def _convert_to_registers(value: Any, data_type: DataType, word_order: str) -> list[int]:
    from pymodbus.client.mixin import ModbusClientMixin

    return ModbusClientMixin.convert_to_registers(
        value, _pymodbus_datatype(data_type), word_order=word_order
    )


def swap_bytes(registers: list[int]) -> list[int]:
    """Swap the two bytes inside each 16-bit register.

    The Modbus specification transmits each register big-endian, and pymodbus
    assumes exactly that. A minority of devices ignore the spec and send the
    low byte first ("byte swap" / mid-endian), so the framework offers
    byte_order="little" and implements it here rather than pretending the
    problem does not exist.
    Spec quy định mỗi register truyền big-endian và pymodbus theo đúng vậy; một
    số thiết bị đảo byte nên framework tự hoán ở đây.
    """
    return [((r & 0xFF) << 8) | ((r >> 8) & 0xFF) for r in registers]


# ---------------------------------------------------------------------------
# Decode: wire -> Python
# ---------------------------------------------------------------------------

def decode_field(field: ModbusField, info: DeviceInfo, raw: Any) -> Any:
    """Decode one field's raw payload into its Python value.

    `raw` is whatever the read command returned for exactly this field's span:
    a list of booleans for coil/discrete areas, a list of 16-bit ints otherwise.
    """
    if field.area.is_bit:
        return _decode_bits(field, raw)

    registers = _as_registers(field, raw)
    if info.resolved_byte_order(field) == "little":
        registers = swap_bytes(registers)

    value = _convert_from_registers(
        registers, field.type, info.resolved_word_order(field)
    )
    if field.type is DataType.STRING:
        return value
    return _apply_scale(field, value)


def _decode_bits(field: ModbusField, raw: Any) -> Any:
    bits = list(raw) if isinstance(raw, (list, tuple)) else [raw]
    expected = field.word_count
    if len(bits) < expected:
        raise ModbusCodecError(
            f"field '{field.name}' needs {expected} bit(s) but the read "
            f"returned {len(bits)}"
        )
    bits = [bool(b) for b in bits[:expected]]
    return bits if field.count and field.count > 1 else bits[0]


def _as_registers(field: ModbusField, raw: Any) -> list[int]:
    registers = list(raw) if isinstance(raw, (list, tuple)) else [raw]
    expected = field.word_count
    if len(registers) < expected:
        raise ModbusCodecError(
            f"field '{field.name}' needs {expected} register(s) but the read "
            f"returned {len(registers)}"
        )
    return registers[:expected]


def _apply_scale(field: ModbusField, value: Any) -> Any:
    """Turn the raw number into engineering units: value * scale + offset."""
    if field.scale is None and field.offset is None:
        return value
    result = float(value)
    if field.scale is not None:
        result *= field.scale
    if field.offset is not None:
        result += field.offset
    return result


# ---------------------------------------------------------------------------
# Encode: Python -> wire
# ---------------------------------------------------------------------------

def encode_field(
    field: ModbusField,
    info: DeviceInfo,
    value: Any,
    *,
    allow_read_only: bool = False,
) -> list[Any]:
    """Encode a Python value into the payload for one field.

    Returns a list of booleans for bit areas, otherwise a list of registers.
    Writing to a read-only area is refused here rather than at the device: the
    device would answer with an exception code that says nothing about which
    field was at fault.
    Ghi vào vùng chỉ đọc bị chặn ngay ở đây - để thiết bị báo lỗi thì thông
    điệp không cho biết field nào sai.

    `allow_read_only` lifts that check for SLAVE mode, where the roles are
    reversed: input registers and discrete inputs are precisely what a slave
    publishes. Client code should never pass it.
    `allow_read_only` dành cho vai slave - lúc đó vùng chỉ đọc chính là thứ
    phải công bố. Code client không bao giờ dùng cờ này.
    """
    if not field.area.writable and not allow_read_only:
        raise ModbusCodecError(
            f"field '{field.name}' is in the {field.area.label} area, which is "
            f"read-only on the Modbus protocol. Only coil and holding register "
            f"fields can be written."
        )

    if field.area.is_bit:
        return _encode_bits(field, value)

    raw = _unapply_scale(field, value)
    registers = _convert_to_registers(
        raw, field.type, info.resolved_word_order(field)
    )
    if info.resolved_byte_order(field) == "little":
        registers = swap_bytes(registers)

    expected = field.word_count
    if len(registers) > expected:
        raise ModbusCodecError(
            f"value for field '{field.name}' needs {len(registers)} register(s) "
            f"but the field reserves {expected}"
        )
    # Strings shorter than the reserved span are null-padded so the remainder of
    # the field is overwritten instead of keeping stale characters.
    # Chuỗi ngắn hơn vùng dành sẵn được đệm 0 để không sót ký tự cũ.
    return registers + [0] * (expected - len(registers))


def _encode_bits(field: ModbusField, value: Any) -> list[bool]:
    expected = field.word_count
    bits = [bool(b) for b in value] if isinstance(value, (list, tuple)) else [bool(value)]
    if len(bits) != expected:
        raise ModbusCodecError(
            f"field '{field.name}' covers {expected} bit(s) but got "
            f"{len(bits)} value(s)"
        )
    return bits


def _unapply_scale(field: ModbusField, value: Any) -> Any:
    """Invert _apply_scale: raw = (value - offset) / scale.

    Integer fields are rounded rather than truncated — truncation would make a
    round-trip of 220.5 through scale=0.1 come back as 220.4.
    Field số nguyên được LÀM TRÒN, không cắt cụt.
    """
    if field.type is DataType.STRING:
        if not isinstance(value, str):
            raise ModbusCodecError(
                f"field '{field.name}' is a string field but got "
                f"{type(value).__name__}"
            )
        return value

    if field.scale is None and field.offset is None:
        raw: Any = value
    else:
        raw = float(value)
        if field.offset is not None:
            raw -= field.offset
        if field.scale is not None:
            raw /= field.scale

    if field.type in _INTEGER_TYPES:
        return int(round(raw))
    return float(raw)


# ---------------------------------------------------------------------------
# Whole-model decode
# ---------------------------------------------------------------------------

def decode_device(
    info: DeviceInfo, payloads: dict[Area, dict[int, Any]]
) -> Any:
    """Build a device model instance from the payloads of every read command.

    `payloads` maps an area to {start_address: values_read_from_that_address},
    which is exactly the shape ReadPlan execution produces.
    """
    instance = object.__new__(info.cls)
    for name, field in info.fields.items():
        chunk = _slice_for(field, payloads.get(field.area, {}))
        setattr(instance, name, decode_field(field, info, chunk))
    return instance


def _slice_for(field: ModbusField, area_payloads: dict[int, Any]) -> Any:
    """Cut this field's span out of whichever command's payload covers it."""
    for start, values in area_payloads.items():
        end = start + len(values)
        if start <= field.address and field.end_address <= end:
            begin = field.address - start
            return values[begin:begin + field.word_count]
    raise ModbusCodecError(
        f"no read command covered field '{field.name}' at "
        f"{field.area.label} address {field.address}"
    )
