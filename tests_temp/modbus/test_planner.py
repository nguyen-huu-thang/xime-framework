"""Read planning: area separation, gap grouping, protocol limits (0.7).

The planner is the piece that decides between "one big block" and "several
tight commands". A wrong plan does not just waste bytes - reading an address
the device does not implement fails the entire command with ILLEGAL DATA
ADDRESS, so these assertions guard correctness, not performance.
"""
import pytest

from xime.adapters.modbus._model import (
    Area,
    Coil,
    Discrete,
    Holding,
    Input,
    device,
    require_device_info,
)
from xime.adapters.modbus._planner import (
    MAX_BITS_PER_READ,
    MAX_REGISTERS_PER_READ,
    ReadCommand,
    describe_plan,
    plan_reads,
)


def spans(commands, area=None):
    """(address, count) of each command, optionally filtered to one area."""
    return [
        (c.address, c.count) for c in commands if area is None or c.area is area
    ]


class TestAreaSeparation:
    def test_areas_never_share_a_command(self):
        # Coil 0 and holding 0 are different storage read by different function
        # codes, so they can never be merged even at identical addresses.
        @device(unit=1)
        class Mixed:
            flag: bool = Coil(0)
            value: int = Holding(0)
            sensor: int = Input(0)
            alarm: bool = Discrete(0)

        commands = plan_reads(require_device_info(Mixed))
        assert len(commands) == 4
        assert {c.area for c in commands} == set(Area)

    def test_areas_come_back_in_a_stable_order(self):
        @device(unit=1)
        class Mixed:
            value: int = Holding(0)
            flag: bool = Coil(0)
            sensor: int = Input(0)

        areas = [c.area for c in plan_reads(require_device_info(Mixed))]
        assert areas == [Area.COIL, Area.INPUT, Area.HOLDING]


class TestGrouping:
    def test_adjacent_fields_merge_into_one_command(self):
        @device(unit=1)
        class Adjacent:
            a: float = Holding(0, type="float32")
            b: float = Holding(2, type="float32")

        assert spans(plan_reads(require_device_info(Adjacent))) == [(0, 4)]

    def test_small_gap_is_absorbed(self):
        @device(unit=1)
        class SmallGap:
            a: int = Holding(0)
            b: int = Holding(5)

        # One command covering 0..5 - the four unused registers cost less than
        # a second round trip.
        assert spans(plan_reads(require_device_info(SmallGap), max_gap=8)) == [(0, 6)]

    def test_large_gap_is_split(self):
        @device(unit=1)
        class LargeGap:
            a: int = Holding(0)
            b: int = Holding(500)

        # This is the case that makes one-big-block dangerous: registers 1..499
        # very likely do not exist on the device.
        assert spans(plan_reads(require_device_info(LargeGap), max_gap=8)) == [
            (0, 1), (500, 1),
        ]

    def test_max_gap_zero_reads_exactly_the_declared_addresses(self):
        @device(unit=1)
        class SmallGap:
            a: int = Holding(0)
            b: int = Holding(5)

        assert spans(plan_reads(require_device_info(SmallGap), max_gap=0)) == [
            (0, 1), (5, 1),
        ]

    def test_gap_is_measured_from_the_end_of_the_previous_field(self):
        # 'a' occupies 0-1, so 'b' at 4 leaves a gap of 2, not 4.
        @device(unit=1)
        class Wide:
            a: float = Holding(0, type="float32")
            b: int = Holding(4)

        assert spans(plan_reads(require_device_info(Wide), max_gap=2)) == [(0, 5)]
        assert spans(plan_reads(require_device_info(Wide), max_gap=1)) == [
            (0, 2), (4, 1),
        ]

    def test_declaration_order_does_not_matter(self):
        @device(unit=1)
        class Shuffled:
            c: int = Holding(20)
            a: int = Holding(0)
            b: int = Holding(1)

        assert spans(plan_reads(require_device_info(Shuffled), max_gap=0)) == [
            (0, 2), (20, 1),
        ]

    def test_negative_max_gap_is_refused(self):
        @device(unit=1)
        class One:
            a: int = Holding(0)

        with pytest.raises(ValueError, match="max_gap must be >= 0"):
            plan_reads(require_device_info(One), max_gap=-1)


class TestProtocolLimits:
    def test_register_command_is_split_at_125(self):
        @device(unit=1)
        class Long:
            a: int = Holding(0)
            b: int = Holding(124)
            c: int = Holding(125)

        # 0..125 would be 126 registers, one over the ceiling.
        plan = spans(plan_reads(require_device_info(Long), max_gap=200))
        assert plan == [(0, 125), (125, 1)]
        assert all(c.count <= MAX_REGISTERS_PER_READ for c in plan_reads(require_device_info(Long)))

    def test_bit_command_is_split_at_2000(self):
        @device(unit=1)
        class ManyBits:
            a: bool = Coil(0)
            b: bool = Coil(1999)
            c: bool = Coil(2000)

        plan = spans(plan_reads(require_device_info(ManyBits), max_gap=4000))
        assert plan == [(0, MAX_BITS_PER_READ), (2000, 1)]

    def test_field_larger_than_the_limit_is_a_modelling_error(self):
        # A field must arrive in one command to be decoded, so this cannot be
        # solved by splitting - say so with the field name instead of letting
        # the device answer with a bare exception code.
        @device(unit=1)
        class Huge:
            text: str = Holding(0, type="string", count=200)

        with pytest.raises(ValueError, match="too large for one read"):
            plan_reads(require_device_info(Huge))


class TestFieldSubset:
    def test_planning_a_single_field(self):
        # What @on_change(Inverter.fault_code) needs: read just that field.
        @device(unit=1)
        class Device:
            a: int = Holding(0)
            b: int = Holding(50)

        info = require_device_info(Device)
        assert spans(plan_reads(info, [Device.b])) == [(50, 1)]

    def test_empty_selection_plans_nothing(self):
        @device(unit=1)
        class Device:
            a: int = Holding(0)

        assert plan_reads(require_device_info(Device), []) == []


class TestReadCommand:
    def test_covers_only_its_own_area_and_span(self):
        @device(unit=1)
        class Device:
            a: float = Holding(10, type="float32")
            flag: bool = Coil(10)

        command = ReadCommand(Area.HOLDING, 10, 2)
        assert command.covers(Device.a)
        assert not command.covers(Device.flag)      # right span, wrong area
        assert not ReadCommand(Area.HOLDING, 10, 1).covers(Device.a)  # truncated

    def test_end_address_is_exclusive(self):
        assert ReadCommand(Area.HOLDING, 10, 2).end_address == 12

    def test_repr_shows_the_inclusive_range(self):
        assert "10..11" in repr(ReadCommand(Area.HOLDING, 10, 2))


class TestDescribePlan:
    def test_one_line_per_command(self):
        @device(unit=1)
        class Device:
            a: int = Holding(0)
            flag: bool = Coil(0)

        text = describe_plan(plan_reads(require_device_info(Device)))
        assert len(text.splitlines()) == 2
        assert "coil" in text and "holding" in text

    def test_empty_plan(self):
        assert describe_plan([]) == "(no read commands)"


class TestPlanCoversEveryField:
    def test_every_field_is_covered_by_exactly_one_command(self):
        # The property the codec relies on: decode_device must find a payload
        # for each field.
        @device(unit=1)
        class Realistic:
            voltage: float = Holding(modicon=40001, type="float32", scale=0.1)
            current: float = Holding(2, type="float32")
            serial: str = Holding(20, type="string", count=8)
            run_state: bool = Coil(0)
            fault_code: int = Input(9)

        info = require_device_info(Realistic)
        commands = plan_reads(info)
        for field in info.fields.values():
            covering = [c for c in commands if c.covers(field)]
            assert len(covering) == 1, f"{field.name} covered by {covering}"
