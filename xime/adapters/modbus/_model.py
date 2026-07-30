"""Declarative device model — the heart of the Modbus adapter.

Modbus itself carries no type information: every read returns a list of raw
16-bit words (or bits). Turning 40001-40002 into `voltage = 220.5` means
knowing which two registers to read, how to join the words, in which order,
and by what factor to scale. Getting any of that wrong yields plausible-looking
garbage rather than an error, which is why it is the single biggest source of
bugs when talking to PLCs.
Modbus không mang thông tin kiểu: mỗi lần đọc chỉ trả về mảng word 16-bit thô.
Ghép sai thứ tự word ra số rác chứ không báo lỗi - đây là nguồn bug lớn nhất.

A device model class declares that knowledge once and the framework uses it for
every direction: client read, client write, polling, and serving as a slave.
This mirrors what `core/contract/` does for socket and gRPC.

    @device(unit=1)
    class Inverter:
        voltage:    float = Holding(modicon=40001, type="float32", scale=0.1)
        current:    float = Holding(2, type="float32")
        run_state:  bool  = Coil(0)
        fault_code: int   = Input(9, type="uint16")

This module is pure Python — it does NOT import pymodbus, so a device model can
be imported (and unit-tested) without the `xime[modbus]` extra installed.
Module này KHÔNG import pymodbus nên model import/test được mà không cần extra.
"""

from __future__ import annotations

import enum
from typing import Any, Literal

# Attribute holding the DeviceInfo built by @device — internal to the framework.
# Mirrors MQTT_ATTR (mqtt) / ROUTE_ATTR (web).
DEVICE_ATTR = "_xime_modbus_device"

ByteOrder = Literal["big", "little"]
WordOrder = Literal["big", "little"]


class Area(enum.Enum):
    """The four Modbus address spaces.

    These are genuinely SEPARATE spaces served by different function codes, not
    four ranges of one space: holding register 0 and coil 0 are unrelated
    storage. A read command can therefore never span two areas.
    Bốn không gian địa chỉ TÁCH BIỆT, function code khác nhau - một lệnh đọc
    không bao giờ trải qua hai vùng.

    `modicon_base` is the first address in the classic Modicon numbering used by
    device datasheets (coil 1, discrete 10001, input 30001, holding 40001).
    """

    COIL = ("coil", True, True, 1)
    DISCRETE = ("discrete", True, False, 10001)
    INPUT = ("input", False, False, 30001)
    HOLDING = ("holding", False, True, 40001)

    def __init__(
        self, label: str, is_bit: bool, writable: bool, modicon_base: int
    ) -> None:
        self.label = label
        self.is_bit = is_bit
        self.writable = writable
        self.modicon_base = modicon_base

    @property
    def modicon_span(self) -> tuple[int, int]:
        """Inclusive Modicon range of this area, e.g. (40001, 49999)."""
        return (self.modicon_base, self.modicon_base + 9998)


class DataType(enum.Enum):
    """Value types a register field can decode to.

    `words` is how many 16-bit registers the type occupies; STRING is variable
    and takes its length from the field's `count`. BOOL is bit-area only.
    `words` = số register 16-bit mà kiểu chiếm chỗ.
    """

    BOOL = ("bool", 0)
    INT16 = ("int16", 1)
    UINT16 = ("uint16", 1)
    INT32 = ("int32", 2)
    UINT32 = ("uint32", 2)
    INT64 = ("int64", 4)
    UINT64 = ("uint64", 4)
    FLOAT32 = ("float32", 2)
    FLOAT64 = ("float64", 4)
    STRING = ("string", 0)

    def __init__(self, label: str, words: int) -> None:
        self.label = label
        self.words = words

    @classmethod
    def parse(cls, value: str | DataType) -> DataType:
        """Resolve the user-facing string (e.g. "float32") to a member.

        Unknown names fail immediately at class-definition time rather than on
        the first read, so a typo never reaches a live device.
        Tên lạ nổ ngay lúc định nghĩa class, không đợi tới lần đọc đầu tiên.
        """
        if isinstance(value, cls):
            return value
        for member in cls:
            if member.label == value:
                return member
        valid = ", ".join(m.label for m in cls)
        raise ValueError(
            f"Unknown Modbus data type {value!r}. Valid types: {valid}."
        )


class ModbusField:
    """One field of a device model: where it lives and how to decode it.

    Implemented as a data descriptor so the SAME attribute serves two purposes:

        Inverter.voltage        -> the ModbusField (for @on_change / write)
        inverter_obj.voltage    -> the decoded value

    That is what lets `await modbus.write(Inverter.run_state, False)` and
    `@on_change(Inverter.fault_code)` refer to a field without a magic string.
    Là data descriptor nên truy cập qua CLASS trả về field, qua INSTANCE trả về
    giá trị - nhờ đó tham chiếu field không cần chuỗi ma thuật.

    Note for type checkers: the annotation on a model attribute describes the
    *value* type (`voltage: float`), so `Inverter.voltage` appears to be a float
    while it is really a ModbusField. This is the same trade-off SQLAlchemy's
    declarative columns make; it costs a `# type: ignore` at the few call sites
    that pass a field object.

    Prefer the concrete constructors (Holding/Input/Coil/Discrete) over
    instantiating this class directly.
    """

    __slots__ = (
        "area", "address", "type", "word_order", "byte_order",
        "scale", "offset", "count", "name", "_attr", "_owner_info",
    )

    def __init__(
        self,
        address: int | None = None,
        *,
        area: Area,
        modicon: int | None = None,
        type: str | DataType = "uint16",  # noqa: A002 - reads naturally in models
        word_order: WordOrder | None = None,
        byte_order: ByteOrder | None = None,
        scale: float | None = None,
        offset: float | None = None,
        count: int | None = None,
    ) -> None:
        self.area = area
        self.address = _resolve_address(address, modicon, area)
        self.type = DataType.parse(type)
        self.word_order = _check_order(word_order, "word_order")
        self.byte_order = _check_order(byte_order, "byte_order")
        self.scale = scale
        self.offset = offset
        self.count = count
        self.name = ""            # filled by __set_name__
        self._attr = ""
        # The device model this field belongs to, attached by @device. Lets
        # `modbus.write(Inverter.run_state, False)` find the unit id and the
        # word/byte order without the caller naming the model again.
        # @device gắn vào để write(field, ...) tự biết unit và endian.
        self._owner_info: DeviceInfo | None = None

        self._validate()

    # ------------------------------------------------------------------
    # Descriptor protocol
    # ------------------------------------------------------------------

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
        self._attr = f"__xime_modbus_{name}"

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self  # accessed on the class -> the field itself
        return getattr(obj, self._attr, None)

    def __set__(self, obj: Any, value: Any) -> None:
        setattr(obj, self._attr, value)

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def word_count(self) -> int:
        """How many registers (or bits, for bit areas) this field occupies."""
        if self.area.is_bit:
            return self.count or 1
        if self.type is DataType.STRING:
            # count is the register count for strings — validated in _validate.
            return self.count or 1
        return self.type.words

    @property
    def end_address(self) -> int:
        """First address AFTER this field (exclusive), for range planning."""
        return self.address + self.word_count

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(name={self.name!r}, area={self.area.label}, "
            f"address={self.address}, type={self.type.label})"
        )

    # ------------------------------------------------------------------
    # Validation — every check fails at class-definition time
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        if self.area.is_bit:
            if self.type is not DataType.BOOL:
                raise ValueError(
                    f"{self.area.label} fields hold single bits, so type must be "
                    f"'bool' (got {self.type.label!r}). Use Holding/Input for "
                    f"numeric register types."
                )
        elif self.type is DataType.BOOL:
            raise ValueError(
                "type 'bool' is only valid for Coil/Discrete fields. A register "
                "holding a flag is usually type='uint16'."
            )

        if self.type is DataType.STRING and not self.count:
            raise ValueError(
                "string fields need count=<number of registers> — Modbus gives "
                "no length prefix, so the framework cannot know where the text "
                "ends. Two ASCII characters fit in one register."
            )
        if self.count is not None and self.count < 1:
            raise ValueError(f"count must be >= 1 (got {self.count})")
        if (
            self.count is not None
            and not self.area.is_bit
            and self.type is not DataType.STRING
        ):
            # A numeric register type already knows its own width (int32 is two
            # registers, always), so count has nothing left to say and was
            # silently discarded. Someone writing Holding(0, type='uint16',
            # count=5) expects five values and gets one, with no error anywhere.
            # Kiểu số đã tự biết chiếm mấy thanh ghi nên count vô nghĩa và trước
            # đây bị bỏ qua im lặng - người viết mong 5 giá trị mà chỉ nhận 1.
            raise ValueError(
                f"count is only meaningful for bit fields (Coil/Discrete) and "
                f"string fields; {self.type.label!r} always occupies "
                f"{self.type.words} register(s). Declare one field per value, "
                f"or use type='string' with count=<registers>."
            )
        if self.scale is not None and self.scale == 0:
            raise ValueError(
                "scale=0 would make every reading 0 and make writing impossible "
                "(division by zero). Leave scale unset if the value needs no "
                "conversion."
            )


def _resolve_address(
    address: int | None, modicon: int | None, area: Area
) -> int:
    """Turn either address form into the 0-based protocol address.

    Two explicit entry points, never a guess:

        Holding(2)              -> protocol address 2
        Holding(modicon=40003)  -> datasheet numbering, also protocol address 2

    Datasheets almost always use Modicon numbering (40001+) while the wire
    protocol uses 0-based offsets. Silently accepting both in one parameter
    would make `Holding(40001)` read a completely different register on a device
    that really does have 40002 registers — a wrong value with no error. So the
    two forms are separate keywords and mixing them fails.
    Datasheet ghi 40001+, trên dây là offset 0-based. Nhận nhập nhèm cả hai
    trong một tham số sẽ đọc nhầm thanh ghi mà không báo lỗi -> tách hai đường.
    """
    if address is None and modicon is None:
        raise ValueError(
            "a field needs an address: either the 0-based protocol address "
            "(e.g. Holding(2)) or the datasheet number "
            "(e.g. Holding(modicon=40003))."
        )
    if address is not None and modicon is not None:
        raise ValueError(
            f"give either address or modicon, not both "
            f"(got address={address}, modicon={modicon})."
        )

    if modicon is not None:
        low, high = area.modicon_span
        if not low <= modicon <= high:
            raise ValueError(
                f"modicon={modicon} is outside the {area.label} range "
                f"{low}-{high}. Modicon numbering encodes the area in the "
                f"leading digit, so it must agree with the field type you "
                f"chose. Extended six-digit numbering (e.g. {low * 10 + 1} for "
                f"the first {area.label}) is not accepted here — pass the "
                f"0-based protocol address instead, e.g. "
                f"{area.label.capitalize()}(0)."
            )
        return modicon - area.modicon_base

    assert address is not None
    if address < 0:
        raise ValueError(f"address must be >= 0 (got {address})")
    if address > 0xFFFF:
        raise ValueError(
            f"address {address} exceeds the 16-bit Modbus address space "
            f"(max 65535). If this came from a datasheet, pass it as "
            f"modicon={address} instead."
        )
    return address


def _check_order(value: Any, label: str) -> Any:
    if value is not None and value not in ("big", "little"):
        raise ValueError(f"{label} must be 'big' or 'little' (got {value!r})")
    return value


# ---------------------------------------------------------------------------
# Field constructors — one per Modbus area
# ---------------------------------------------------------------------------

def Holding(  # noqa: N802 - reads as a type in model declarations
    address: int | None = None,
    *,
    modicon: int | None = None,
    type: str | DataType = "uint16",  # noqa: A002
    word_order: WordOrder | None = None,
    byte_order: ByteOrder | None = None,
    scale: float | None = None,
    offset: float | None = None,
    count: int | None = None,
) -> Any:
    """A read/write 16-bit register (function code 3 to read, 6/16 to write)."""
    return ModbusField(
        address, area=Area.HOLDING, modicon=modicon, type=type,
        word_order=word_order, byte_order=byte_order,
        scale=scale, offset=offset, count=count,
    )


def Input(  # noqa: N802
    address: int | None = None,
    *,
    modicon: int | None = None,
    type: str | DataType = "uint16",  # noqa: A002
    word_order: WordOrder | None = None,
    byte_order: ByteOrder | None = None,
    scale: float | None = None,
    offset: float | None = None,
    count: int | None = None,
) -> Any:
    """A read-only 16-bit register (function code 4)."""
    return ModbusField(
        address, area=Area.INPUT, modicon=modicon, type=type,
        word_order=word_order, byte_order=byte_order,
        scale=scale, offset=offset, count=count,
    )


def Coil(  # noqa: N802
    address: int | None = None,
    *,
    modicon: int | None = None,
    count: int | None = None,
) -> Any:
    """A read/write single bit (function code 1 to read, 5/15 to write)."""
    return ModbusField(
        address, area=Area.COIL, modicon=modicon, type=DataType.BOOL, count=count
    )


def Discrete(  # noqa: N802
    address: int | None = None,
    *,
    modicon: int | None = None,
    count: int | None = None,
) -> Any:
    """A read-only single bit (function code 2)."""
    return ModbusField(
        address, area=Area.DISCRETE, modicon=modicon, type=DataType.BOOL, count=count
    )


# ---------------------------------------------------------------------------
# @device
# ---------------------------------------------------------------------------

class DeviceInfo:
    """Everything the adapter needs to know about one device model class."""

    __slots__ = ("cls", "unit", "fields", "byte_order", "word_order")

    def __init__(
        self,
        cls: type,
        unit: int,
        fields: dict[str, ModbusField],
        byte_order: ByteOrder,
        word_order: WordOrder,
    ) -> None:
        self.cls = cls
        self.unit = unit
        self.fields = fields
        self.byte_order = byte_order
        self.word_order = word_order

    def fields_in(self, area: Area) -> list[ModbusField]:
        """Fields of one area, sorted by address (planning order)."""
        return sorted(
            (f for f in self.fields.values() if f.area is area),
            key=lambda f: f.address,
        )

    def resolved_word_order(self, field: ModbusField) -> WordOrder:
        return field.word_order or self.word_order

    def resolved_byte_order(self, field: ModbusField) -> ByteOrder:
        return field.byte_order or self.byte_order

    def __repr__(self) -> str:
        return (
            f"DeviceInfo(cls={self.cls.__name__}, unit={self.unit}, "
            f"fields={list(self.fields)})"
        )


def device(
    *,
    unit: int = 1,
    byte_order: ByteOrder = "big",
    word_order: WordOrder = "big",
):
    """Mark a class as a Modbus device model.

        @device(unit=1, word_order="little")
        class Inverter:
            voltage: float = Holding(modicon=40001, type="float32", scale=0.1)

    `unit` is the Modbus unit/slave id: on a plain TCP device it is usually 1,
    on an RTU-over-TCP gateway it selects which device on the serial chain.
    `byte_order`/`word_order` are the device-wide defaults; a field may override
    either. Most devices are big-endian in both, but word-swapped 32-bit values
    are common enough that the default is worth checking against the datasheet.
    unit = slave id; byte_order/word_order là mặc định toàn thiết bị, field
    override được.

    A generated `__init__` accepts the fields as keyword arguments (defaulting
    to None) unless the class defines its own.
    """

    def decorator(cls: type) -> type:
        if not isinstance(unit, int) or isinstance(unit, bool):
            raise ValueError(f"unit must be an int (got {unit!r})")
        if not 0 <= unit <= 255:
            raise ValueError(
                f"unit must be between 0 and 255 (got {unit}). Modbus carries "
                f"the unit id in a single byte."
            )
        _check_order(byte_order, "byte_order")
        _check_order(word_order, "word_order")

        fields = _collect_fields(cls)
        if not fields:
            raise ValueError(
                f"@device class '{cls.__name__}' declares no fields. Add at "
                f"least one, e.g. `level: float = Holding(0, type='float32')`."
            )
        _check_no_overlap(cls, fields)

        info = DeviceInfo(cls, unit, fields, byte_order, word_order)
        for field in fields.values():
            # A field inherited by several models is one shared object, so the
            # first model to claim it wins and the binding stays deterministic
            # regardless of import order later. Pass unit= to read/write when
            # addressing a different unit with the same layout (e.g. three
            # identical inverters at unit 1, 2, 3).
            # Field kế thừa là object dùng chung -> model NHẬN ĐẦU TIÊN thắng,
            # muốn unit khác thì truyền unit= lúc gọi read/write.
            if field._owner_info is None:
                field._owner_info = info
        setattr(cls, DEVICE_ATTR, info)
        if "__init__" not in cls.__dict__:
            cls.__init__ = _make_init(fields)  # type: ignore[method-assign]
        if "__repr__" not in cls.__dict__:
            cls.__repr__ = _make_repr(fields)  # type: ignore[method-assign]
        return cls

    return decorator


def get_device_info(target: Any) -> DeviceInfo | None:
    """Return the DeviceInfo of a device model class (or instance), or None."""
    cls = target if isinstance(target, type) else type(target)
    return getattr(cls, DEVICE_ATTR, None)


def require_device_info(target: Any) -> DeviceInfo:
    """Like get_device_info but fails with an actionable message."""
    info = get_device_info(target)
    if info is None:
        name = getattr(target, "__name__", type(target).__name__)
        raise TypeError(
            f"'{name}' is not a Modbus device model. Decorate the class with "
            f"@device(unit=...) from xime.adapters.modbus."
        )
    return info


def _collect_fields(cls: type) -> dict[str, ModbusField]:
    """Collect fields across the MRO, base classes first so overrides win."""
    fields: dict[str, ModbusField] = {}
    for klass in reversed(cls.__mro__):
        for name, value in vars(klass).items():
            if isinstance(value, ModbusField):
                if not value.name:  # defined outside a class body
                    value.__set_name__(klass, name)
                fields[name] = value
    return fields


def _check_no_overlap(cls: type, fields: dict[str, ModbusField]) -> None:
    """Reject two fields covering the same address in the same area.

    Overlap is nearly always a copy-paste slip (a field left at the address of
    the one above it). Left alone it decodes both names from the same registers
    and the mistake surfaces as two attributes that mysteriously always agree.
    Trùng địa chỉ gần như luôn là lỗi copy-paste; để im thì hai field luôn ra
    cùng giá trị, rất khó lần ra.
    """
    by_area: dict[Area, list[ModbusField]] = {}
    for field in fields.values():
        by_area.setdefault(field.area, []).append(field)

    for area, group in by_area.items():
        group.sort(key=lambda f: f.address)
        for previous, current in zip(group, group[1:]):
            if current.address < previous.end_address:
                raise ValueError(
                    f"\nOverlapping Modbus fields in '{cls.__name__}'\n"
                    f"  Area   : {area.label}\n"
                    f"  Field  : {previous.name} covers "
                    f"{previous.address}-{previous.end_address - 1}\n"
                    f"  Field  : {current.name} starts at {current.address}\n"
                    f"  Fix    : give them distinct addresses, or remove one."
                )


def _make_init(fields: dict[str, ModbusField]):
    names = tuple(fields)

    def __init__(self: Any, **values: Any) -> None:
        unknown = set(values) - set(names)
        if unknown:
            raise TypeError(
                f"{type(self).__name__} got unexpected field(s) "
                f"{sorted(unknown)}; known fields: {list(names)}"
            )
        for name in names:
            setattr(self, name, values.get(name))

    return __init__


def _make_repr(fields: dict[str, ModbusField]):
    names = tuple(fields)

    def __repr__(self: Any) -> str:
        body = ", ".join(f"{n}={getattr(self, n)!r}" for n in names)
        return f"{type(self).__name__}({body})"

    return __repr__
