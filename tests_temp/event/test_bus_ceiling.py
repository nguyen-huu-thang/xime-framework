"""
F15 - trần số handler task đang bay của EventBus, và các cách nói "đừng bỏ cái này".

  - quá trần thì event bị bỏ, dưới trần thì không bỏ gì (test đi thành CẶP)
  - bỏ NGUYÊN CON: hoặc chạy hết handler của event, hoặc không handler nào
  - log có hãm nhịp: lũ event không được biến cảnh báo thành lũ log thứ hai
  - never_drop miễn trần theo KIỂU CHÍNH XÁC (không khớp kế thừa)
  - max_pending=None giữ đúng hành vi trước 0.7.2
  - loại được miễn mà vượt trần thì phải NÓI RA: rủi ro được dời chứ không mất
"""
import asyncio
import logging
from typing import Any

import pytest

from xime.core.event import EventBus, EventBusConfig
from xime.core.event.bus import _WARN_EVERY

_LOGGER = "xime.core.event.bus"


class UserCreatedEvent:
    def __init__(self, user_id: str = "u"):
        self.user_id = user_id


class AuditEvent:
    pass


class BlockingHandler:
    """Never finishes on its own, so pending tasks pile up predictably."""

    def __init__(self) -> None:
        self.started = 0

    async def handle(self, event: Any) -> None:
        self.started += 1
        await asyncio.Event().wait()


class RecordingHandler:
    def __init__(self) -> None:
        self.received: list[Any] = []

    async def handle(self, event: Any) -> None:
        self.received.append(event)


async def _cancel_all(bus: EventBus) -> None:
    for task in list(bus._pending):
        task.cancel()
    await bus.drain()


class TestPendingCeiling:
    """Tests come in PAIRS: one that the ceiling bites, one that it does NOT.

    A ceiling tested only on the biting half is indistinguishable from an
    implementation that drops everything.
    Chỉ kiểm vế "phải bỏ" thì bản hiện thực "bỏ tất" cũng qua.
    """

    @pytest.mark.asyncio
    async def test_events_past_the_ceiling_are_dropped(self):
        bus = EventBus(EventBusConfig(max_pending=3))
        handler = BlockingHandler()
        bus.subscribe(UserCreatedEvent, handler)

        for i in range(10):
            await bus.publish(UserCreatedEvent(str(i)))
        await asyncio.sleep(0)

        assert len(bus._pending) == 3
        assert handler.started == 3
        assert bus.dropped == 7
        assert bus.dropped_by_type() == {UserCreatedEvent: 7}
        await _cancel_all(bus)

    @pytest.mark.asyncio
    async def test_events_under_the_ceiling_all_run(self):
        """Other half of the pair - nothing is dropped while there is room."""
        bus = EventBus(EventBusConfig(max_pending=100))
        handler = RecordingHandler()
        bus.subscribe(UserCreatedEvent, handler)

        for i in range(10):
            await bus.publish(UserCreatedEvent(str(i)))
        await bus.drain()

        assert len(handler.received) == 10
        assert bus.dropped == 0

    @pytest.mark.asyncio
    async def test_an_event_is_dropped_whole_never_half(self):
        """All handlers or none - half an event is a state nobody designed for.

        Trần 3, event có 2 handler: sau lần publish đầu còn chỗ cho 1, không đủ
        cho event thứ hai, và KHÔNG được chạy một trong hai handler của nó.
        """
        bus = EventBus(EventBusConfig(max_pending=3))
        first, second = BlockingHandler(), BlockingHandler()
        bus.subscribe(UserCreatedEvent, first)
        bus.subscribe(UserCreatedEvent, second)

        await bus.publish(UserCreatedEvent("a"))
        await bus.publish(UserCreatedEvent("b"))
        await asyncio.sleep(0)

        assert len(bus._pending) == 2
        assert first.started == 1
        assert second.started == 1
        assert bus.dropped == 1
        await _cancel_all(bus)

    @pytest.mark.asyncio
    async def test_a_drop_says_what_it_dropped_and_how_to_fix_it(self, caplog):
        bus = EventBus(EventBusConfig(max_pending=1))
        bus.subscribe(UserCreatedEvent, BlockingHandler())
        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            await bus.publish(UserCreatedEvent("a"))
            await bus.publish(UserCreatedEvent("b"))

        assert "dropped UserCreatedEvent" in caplog.text
        assert "max_pending" in caplog.text
        assert "never_drop" in caplog.text
        await _cancel_all(bus)

    @pytest.mark.asyncio
    async def test_drop_logging_is_throttled(self, caplog):
        """A flood must not turn one warning into a second flood."""
        bus = EventBus(EventBusConfig(max_pending=1))
        bus.subscribe(UserCreatedEvent, BlockingHandler())
        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            for i in range(_WARN_EVERY + 5):
                await bus.publish(UserCreatedEvent(str(i)))

        lines = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(lines) == 2  # lần bỏ đầu tiên + đúng một mốc _WARN_EVERY
        assert bus.dropped == _WARN_EVERY + 4
        await _cancel_all(bus)


class TestNeverDrop:
    """Two ways to say "do not drop this", both required.

    Losing an audit or money event is worse than the memory it costs, and that
    judgement belongs to whoever designs the app, not to the framework.
    Mất một event kiểm toán hay event tiền còn tệ hơn tốn bộ nhớ, và đó là phán
    đoán của người thiết kế app chứ không phải của framework.
    """

    @pytest.mark.asyncio
    async def test_exempt_type_survives_a_full_bus(self):
        bus = EventBus(
            EventBusConfig(max_pending=2, never_drop=frozenset({AuditEvent}))
        )
        normal, audit = BlockingHandler(), BlockingHandler()
        bus.subscribe(UserCreatedEvent, normal)
        bus.subscribe(AuditEvent, audit)

        for i in range(10):
            await bus.publish(UserCreatedEvent(str(i)))
        for _ in range(5):
            await bus.publish(AuditEvent())
        await asyncio.sleep(0)

        assert normal.started == 2  # loại thường bị trần chặn
        assert audit.started == 5  # loại được miễn đi hết
        assert bus.dropped_by_type() == {UserCreatedEvent: 8}
        await _cancel_all(bus)

    @pytest.mark.asyncio
    async def test_a_type_not_exempted_is_still_dropped(self):
        """Other half - never_drop must exempt only what it names."""
        bus = EventBus(
            EventBusConfig(max_pending=1, never_drop=frozenset({AuditEvent}))
        )
        bus.subscribe(UserCreatedEvent, BlockingHandler())

        for i in range(5):
            await bus.publish(UserCreatedEvent(str(i)))
        await asyncio.sleep(0)

        assert bus.dropped == 4
        await _cancel_all(bus)

    @pytest.mark.asyncio
    async def test_exemption_matches_exact_type_not_inheritance(self):
        """Same rule as handler lookup - exact type, no inheritance matching.

        Cùng luật với việc tra handler. Ngày nào đổi thì đổi cả hai chỗ, đừng để
        hai nơi hiểu "cùng loại event" theo hai kiểu khác nhau.
        """

        class SubAudit(AuditEvent):
            pass

        bus = EventBus(
            EventBusConfig(max_pending=1, never_drop=frozenset({AuditEvent}))
        )
        bus.subscribe(SubAudit, BlockingHandler())

        for _ in range(5):
            await bus.publish(SubAudit())
        await asyncio.sleep(0)

        assert bus.dropped == 4  # lớp con KHÔNG thừa hưởng quyền miễn
        await _cancel_all(bus)

    @pytest.mark.asyncio
    async def test_no_ceiling_at_all_keeps_the_old_behaviour(self):
        """max_pending=None is the pre-0.7.2 bus, an explicit choice."""
        bus = EventBus(EventBusConfig(max_pending=None))
        handler = BlockingHandler()
        bus.subscribe(UserCreatedEvent, handler)

        for i in range(500):
            await bus.publish(UserCreatedEvent(str(i)))
        await asyncio.sleep(0)

        assert len(bus._pending) == 500
        assert bus.dropped == 0
        await _cancel_all(bus)

    @pytest.mark.asyncio
    async def test_exempt_type_past_the_ceiling_says_so(self, caplog):
        """The risk is MOVED, not removed - so it has to be visible."""
        bus = EventBus(
            EventBusConfig(max_pending=1, never_drop=frozenset({AuditEvent}))
        )
        bus.subscribe(AuditEvent, BlockingHandler())
        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            for _ in range(3):
                await bus.publish(AuditEvent())

        assert "never_drop" in caplog.text
        assert "keep growing" in caplog.text
        await _cancel_all(bus)

    @pytest.mark.asyncio
    async def test_exempt_warning_stays_quiet_below_the_ceiling(self, caplog):
        """Paired with the test above.

        Regression guard for a real bug in the first draft: the throttle counter
        was shared with the drop counter, so `0 % _WARN_EVERY == 0` made it warn
        on EVERY publish while nothing had been dropped - the very flood the
        throttle exists to stop.
        Canh một lỗi thật của bản nháp đầu: bộ đếm hãm nhịp dùng chung với bộ đếm
        bỏ, nên `0 % _WARN_EVERY == 0` khiến nó kêu ở MỌI lần publish trong khi
        chưa bỏ cái nào - đúng cái lũ log mà phép hãm nhịp sinh ra để chặn.
        """
        bus = EventBus(
            EventBusConfig(max_pending=100, never_drop=frozenset({AuditEvent}))
        )
        bus.subscribe(AuditEvent, BlockingHandler())
        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            for _ in range(10):
                await bus.publish(AuditEvent())

        assert caplog.text == ""
        await _cancel_all(bus)


class TestConfigureEventBus:
    """configure_event_bus() is FRAMEWORK config - Python, not application.yml.

    How many in-flight handlers an app can carry, and which events must never be
    lost, are design properties of the app - not environment settings an
    operator tunes. Same reasoning as routing and DI bindings.
    """

    def setup_method(self):
        from xime.core.event import event_bus_registry

        event_bus_registry.reset()

    teardown_method = setup_method

    def test_default_has_a_ceiling(self):
        from xime.core.event import event_bus_registry

        assert event_bus_registry.get_config().max_pending == 10_000

    def test_developer_sets_the_number_and_the_exemptions(self):
        from xime.core.event import configure_event_bus, event_bus_registry

        configure_event_bus(max_pending=50_000, never_drop=(AuditEvent,))
        cfg = event_bus_registry.get_config()
        assert cfg.max_pending == 50_000
        assert cfg.never_drop == frozenset({AuditEvent})

    def test_no_ceiling_is_expressible(self):
        from xime.core.event import configure_event_bus, event_bus_registry

        configure_event_bus(max_pending=None)
        assert event_bus_registry.get_config().max_pending is None

    def test_nonsense_ceiling_fails_fast(self):
        from xime.core.event import configure_event_bus

        with pytest.raises(ValueError, match="must be >= 1 or None"):
            configure_event_bus(max_pending=0)

    def test_never_drop_must_hold_classes(self):
        """A string here would silently exempt nothing - it can never match."""
        from xime.core.event import configure_event_bus

        with pytest.raises(ValueError, match="event CLASSES"):
            configure_event_bus(never_drop=("AuditEvent",))  # type: ignore[arg-type]
