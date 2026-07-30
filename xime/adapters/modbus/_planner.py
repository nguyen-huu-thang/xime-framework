"""Turning a device model into the actual read commands to send.

Modbus has exactly one way to read: "give me N consecutive addresses starting
at X". A device model whose fields sit at scattered addresses therefore has to
be translated into a set of commands, and how that translation is done has
correctness consequences, not just efficiency ones.

Two rules drive the planner:

1. **Never span areas.** Coil, discrete input, input register and holding
   register are four separate address spaces read by four different function
   codes. Holding 0 and coil 0 are unrelated storage, so a command can only
   ever cover one area.

2. **Group nearby fields, split distant ones.** Reading one big block from the
   lowest to the highest address is simpler, but if any address in between does
   not exist on the device, the slave answers ILLEGAL DATA ADDRESS and the
   WHOLE read fails - even though every field the model declares is valid. That
   failure is hard to diagnose because the model and the config both look
   correct. So fields are only merged into one command while the gap between
   them stays within `max_gap`.
   Đọc một block lớn đơn giản hơn, nhưng chỉ cần một địa chỉ ở giữa không tồn
   tại là slave trả ILLEGAL DATA ADDRESS và hỏng CẢ lần đọc.

`max_gap` is the knob between the two failure modes: 0 reads exactly the
declared addresses and nothing else (safest, most commands), larger values trade
a few wasted registers for fewer round trips. The default of 8 assumes devices
rarely leave small holes inside an otherwise valid block.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._model import Area, DeviceInfo, ModbusField

# Protocol ceilings on a single read command (Modbus application protocol spec).
# A request for more than this is rejected by the device, so the planner splits.
# Trần của một lệnh đọc theo spec - vượt là thiết bị từ chối, planner phải chia.
MAX_REGISTERS_PER_READ = 125
MAX_BITS_PER_READ = 2000

DEFAULT_MAX_GAP = 8


@dataclass(frozen=True)
class ReadCommand:
    """One request to put on the wire: `count` addresses starting at `address`."""

    area: Area
    address: int
    count: int

    @property
    def end_address(self) -> int:
        """First address after this command (exclusive)."""
        return self.address + self.count

    def covers(self, field: ModbusField) -> bool:
        return (
            field.area is self.area
            and self.address <= field.address
            and field.end_address <= self.end_address
        )

    def __repr__(self) -> str:
        return (
            f"ReadCommand({self.area.label}, {self.address}.."
            f"{self.end_address - 1}, count={self.count})"
        )


def plan_reads(
    info: DeviceInfo,
    fields: list[ModbusField] | None = None,
    *,
    max_gap: int = DEFAULT_MAX_GAP,
) -> list[ReadCommand]:
    """Plan the read commands needed to fill `fields` (default: all of them).

    Commands come back grouped by area in a stable order (coil, discrete, input,
    holding) and sorted by address within each area, so a plan is reproducible
    and easy to assert on in tests.
    """
    if max_gap < 0:
        raise ValueError(f"max_gap must be >= 0 (got {max_gap})")

    selected = list(info.fields.values()) if fields is None else list(fields)
    commands: list[ReadCommand] = []
    for area in Area:
        in_area = sorted(
            (f for f in selected if f.area is area), key=lambda f: f.address
        )
        if in_area:
            commands.extend(_plan_area(area, in_area, max_gap))
    return commands


def _plan_area(
    area: Area, fields: list[ModbusField], max_gap: int
) -> list[ReadCommand]:
    limit = MAX_BITS_PER_READ if area.is_bit else MAX_REGISTERS_PER_READ
    commands: list[ReadCommand] = []

    start = fields[0].address
    end = fields[0].address + _span(area, fields[0], limit)

    for field in fields[1:]:
        field_end = field.address + _span(area, field, limit)
        gap = field.address - end
        merged_size = field_end - start
        # A negative gap means overlap, which @device already rejects; treat it
        # as adjacent so a hand-built field list still produces a valid plan.
        if gap <= max_gap and merged_size <= limit:
            end = max(end, field_end)
        else:
            commands.append(ReadCommand(area, start, end - start))
            start, end = field.address, field_end

    commands.append(ReadCommand(area, start, end - start))
    return commands


def _span(area: Area, field: ModbusField, limit: int) -> int:
    """Size of one field, refusing fields that cannot fit in any command.

    A field larger than the protocol limit cannot be split - its bytes have to
    arrive together to decode - so this is a modelling error, caught with a
    message that names the field instead of a device-side exception code.
    Field lớn hơn trần của giao thức thì không chia được, đây là lỗi mô hình.
    """
    size = field.word_count
    if size > limit:
        unit = "bits" if area.is_bit else "registers"
        raise ValueError(
            f"\nModbus field too large for one read\n"
            f"  Field : {field.name} ({area.label} address {field.address})\n"
            f"  Size  : {size} {unit}\n"
            f"  Limit : {limit} {unit} per command\n"
            f"  Why   : a field must be read in one command to be decoded, and\n"
            f"          the protocol caps a single command at {limit} {unit}.\n"
            f"  Fix   : split it into several smaller fields."
        )
    return size


def describe_plan(commands: list[ReadCommand]) -> str:
    """One line per command - for startup logging and debugging."""
    if not commands:
        return "(no read commands)"
    return "\n".join(
        f"  {c.area.label:<8} {c.address}..{c.end_address - 1} ({c.count})"
        for c in commands
    )
