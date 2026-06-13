"""
Test EventBus (fire-and-forget — handler chạy nền bằng asyncio Task):

  - subscribe + publish + drain: handler được gọi với đúng event
  - publish KHÔNG block: trả về ngay cả khi handler chậm
  - nhiều handler cùng event type: tất cả được gọi (concurrent, không cam kết thứ tự)
  - đăng ký cùng một handler hai lần: được gọi hai lần
  - event type khác nhau: độc lập nhau; khớp exact type, không theo kế thừa
  - publish event không có handler: không lỗi
  - handler lỗi: KHÔNG propagate về publisher — chỉ log; handler khác vẫn chạy
  - drain(): chờ toàn bộ handler đang bay xong; không có task thì no-op
"""
import asyncio
import logging
from typing import Any

import pytest

from xime.core.event import EventBus


# ---------------------------------------------------------------------------
# Sample events
# ---------------------------------------------------------------------------

class UserCreatedEvent:
    def __init__(self, user_id: str):
        self.user_id = user_id


class OrderPlacedEvent:
    def __init__(self, order_id: int):
        self.order_id = order_id


# ---------------------------------------------------------------------------
# Helper: handler ghi lại các lần được gọi
# ---------------------------------------------------------------------------

class RecordingHandler:
    def __init__(self, name: str = "handler"):
        self.name = name
        self.received: list[Any] = []

    async def handle(self, event: Any) -> None:
        self.received.append(event)


class FailingHandler:
    def __init__(self, error: Exception):
        self.error = error
        self.called = False

    async def handle(self, event: Any) -> None:
        self.called = True
        raise self.error


class SlowHandler:
    def __init__(self):
        self.done = False

    async def handle(self, event: Any) -> None:
        await asyncio.sleep(0.05)
        self.done = True


# ---------------------------------------------------------------------------
# subscribe + publish cơ bản
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handler_receives_published_event():
    bus = EventBus()
    handler = RecordingHandler()
    event = UserCreatedEvent("u1")

    bus.subscribe(UserCreatedEvent, handler)
    await bus.publish(event)
    await bus.drain()

    assert handler.received == [event]


@pytest.mark.asyncio
async def test_handler_receives_correct_event_data():
    bus = EventBus()
    handler = RecordingHandler()

    bus.subscribe(UserCreatedEvent, handler)
    await bus.publish(UserCreatedEvent("user-42"))
    await bus.drain()

    assert handler.received[0].user_id == "user-42"


@pytest.mark.asyncio
async def test_publish_does_not_block_on_slow_handler():
    """Fire-and-forget: publish trả về trước khi handler chậm chạy xong."""
    bus = EventBus()
    slow = SlowHandler()
    bus.subscribe(UserCreatedEvent, slow)

    await bus.publish(UserCreatedEvent("u1"))
    assert slow.done is False      # publish không chờ handler

    await bus.drain()
    assert slow.done is True       # drain mới là điểm chờ


# ---------------------------------------------------------------------------
# Nhiều handler cùng event type
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_handlers_all_called():
    bus = EventBus()
    h1 = RecordingHandler("h1")
    h2 = RecordingHandler("h2")
    h3 = RecordingHandler("h3")

    bus.subscribe(UserCreatedEvent, h1)
    bus.subscribe(UserCreatedEvent, h2)
    bus.subscribe(UserCreatedEvent, h3)

    event = UserCreatedEvent("u1")
    await bus.publish(event)
    await bus.drain()

    # Handler chạy concurrent — cam kết "tất cả được gọi", không cam kết thứ tự.
    assert h1.received == [event]
    assert h2.received == [event]
    assert h3.received == [event]


@pytest.mark.asyncio
async def test_same_handler_subscribed_twice_called_twice():
    bus = EventBus()
    handler = RecordingHandler()

    bus.subscribe(UserCreatedEvent, handler)
    bus.subscribe(UserCreatedEvent, handler)

    await bus.publish(UserCreatedEvent("u1"))
    await bus.drain()

    assert len(handler.received) == 2


# ---------------------------------------------------------------------------
# Event types khác nhau
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_different_event_types_are_independent():
    bus = EventBus()
    user_handler = RecordingHandler()
    order_handler = RecordingHandler()

    bus.subscribe(UserCreatedEvent, user_handler)
    bus.subscribe(OrderPlacedEvent, order_handler)

    await bus.publish(UserCreatedEvent("u1"))
    await bus.drain()

    assert len(user_handler.received) == 1
    assert len(order_handler.received) == 0   # không nhận UserCreatedEvent


@pytest.mark.asyncio
async def test_subclass_event_does_not_dispatch_to_parent_handler():
    """Bus khớp exact type, không dùng isinstance — không dispatch theo kế thừa."""
    class SpecialUserCreatedEvent(UserCreatedEvent):
        pass

    bus = EventBus()
    handler = RecordingHandler()
    bus.subscribe(UserCreatedEvent, handler)

    await bus.publish(SpecialUserCreatedEvent("u1"))
    await bus.drain()

    # SpecialUserCreatedEvent khác type với UserCreatedEvent
    assert len(handler.received) == 0


# ---------------------------------------------------------------------------
# Không có handler
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_publish_with_no_handlers_is_noop():
    bus = EventBus()
    await bus.publish(UserCreatedEvent("u1"))   # không raise


@pytest.mark.asyncio
async def test_publish_unregistered_event_type_is_noop():
    bus = EventBus()
    handler = RecordingHandler()
    bus.subscribe(UserCreatedEvent, handler)

    await bus.publish(OrderPlacedEvent(99))   # không có handler → không raise
    await bus.drain()

    assert len(handler.received) == 0


# ---------------------------------------------------------------------------
# Xử lý lỗi trong handler — lỗi KHÔNG propagate, chỉ log
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handler_error_does_not_propagate_to_publisher(caplog):
    bus = EventBus()
    bus.subscribe(UserCreatedEvent, FailingHandler(ValueError("bad event")))

    with caplog.at_level(logging.ERROR, logger="xime.core.event.bus"):
        await bus.publish(UserCreatedEvent("u1"))   # không raise
        await bus.drain()                            # cũng không raise

    # Lỗi được log kèm tên handler và tên event
    assert any(
        "FailingHandler" in record.message and "UserCreatedEvent" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_all_handler_errors_are_logged(caplog):
    bus = EventBus()
    bus.subscribe(UserCreatedEvent, FailingHandler(ValueError("err A")))
    bus.subscribe(UserCreatedEvent, FailingHandler(RuntimeError("err B")))

    with caplog.at_level(logging.ERROR, logger="xime.core.event.bus"):
        await bus.publish(UserCreatedEvent("u1"))
        await bus.drain()

    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 2


@pytest.mark.asyncio
async def test_all_handlers_called_even_when_one_fails(caplog):
    bus = EventBus()
    good = RecordingHandler()
    failing = FailingHandler(RuntimeError("boom"))
    also_good = RecordingHandler()

    bus.subscribe(UserCreatedEvent, good)
    bus.subscribe(UserCreatedEvent, failing)
    bus.subscribe(UserCreatedEvent, also_good)

    with caplog.at_level(logging.ERROR, logger="xime.core.event.bus"):
        await bus.publish(UserCreatedEvent("u1"))
        await bus.drain()

    # Handler lỗi không ảnh hưởng các handler còn lại
    assert len(good.received) == 1
    assert failing.called is True
    assert len(also_good.received) == 1


@pytest.mark.asyncio
async def test_no_error_logged_when_all_handlers_succeed(caplog):
    bus = EventBus()
    bus.subscribe(UserCreatedEvent, RecordingHandler())
    bus.subscribe(UserCreatedEvent, RecordingHandler())

    with caplog.at_level(logging.ERROR, logger="xime.core.event.bus"):
        await bus.publish(UserCreatedEvent("u1"))
        await bus.drain()

    assert not [r for r in caplog.records if r.levelno == logging.ERROR]


# ---------------------------------------------------------------------------
# drain()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_drain_without_pending_tasks_is_noop():
    bus = EventBus()
    await bus.drain()   # không raise


@pytest.mark.asyncio
async def test_drain_waits_for_all_in_flight_handlers():
    bus = EventBus()
    slow_a = SlowHandler()
    slow_b = SlowHandler()
    bus.subscribe(UserCreatedEvent, slow_a)
    bus.subscribe(OrderPlacedEvent, slow_b)

    await bus.publish(UserCreatedEvent("u1"))
    await bus.publish(OrderPlacedEvent(7))
    await bus.drain()

    assert slow_a.done is True
    assert slow_b.done is True
