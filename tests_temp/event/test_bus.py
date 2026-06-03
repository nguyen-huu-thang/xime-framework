"""
Test EventBus:
  - subscribe + publish: handler được gọi với đúng event
  - nhiều handler cùng event type: tất cả được gọi theo thứ tự đăng ký
  - event type khác nhau: độc lập nhau
  - publish event không có handler: không lỗi
  - publish thu thập tất cả lỗi của handler vào ExceptionGroup
  - handler lỗi không ngăn các handler còn lại chạy
  - publish với handler không lỗi: không raise
  - đăng ký cùng một handler hai lần: được gọi hai lần
"""
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

    assert handler.received == [event]


@pytest.mark.asyncio
async def test_handler_receives_correct_event_data():
    bus = EventBus()
    handler = RecordingHandler()

    bus.subscribe(UserCreatedEvent, handler)
    await bus.publish(UserCreatedEvent("user-42"))

    assert handler.received[0].user_id == "user-42"


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

    assert h1.received == [event]
    assert h2.received == [event]
    assert h3.received == [event]


@pytest.mark.asyncio
async def test_handlers_called_in_subscription_order():
    bus = EventBus()
    call_order: list[str] = []

    class OrderedHandler:
        def __init__(self, label: str):
            self.label = label

        async def handle(self, event: Any) -> None:
            call_order.append(self.label)

    bus.subscribe(UserCreatedEvent, OrderedHandler("first"))
    bus.subscribe(UserCreatedEvent, OrderedHandler("second"))
    bus.subscribe(UserCreatedEvent, OrderedHandler("third"))

    await bus.publish(UserCreatedEvent("u1"))

    assert call_order == ["first", "second", "third"]


@pytest.mark.asyncio
async def test_same_handler_subscribed_twice_called_twice():
    bus = EventBus()
    handler = RecordingHandler()

    bus.subscribe(UserCreatedEvent, handler)
    bus.subscribe(UserCreatedEvent, handler)

    await bus.publish(UserCreatedEvent("u1"))

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

    assert len(handler.received) == 0


# ---------------------------------------------------------------------------
# Xử lý lỗi trong handler
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_publish_raises_exception_group_when_handler_fails():
    bus = EventBus()
    bus.subscribe(UserCreatedEvent, FailingHandler(ValueError("bad event")))

    with pytest.raises(ExceptionGroup) as exc_info:
        await bus.publish(UserCreatedEvent("u1"))

    assert len(exc_info.value.exceptions) == 1
    assert isinstance(exc_info.value.exceptions[0], ValueError)


@pytest.mark.asyncio
async def test_publish_collects_all_handler_errors():
    bus = EventBus()
    bus.subscribe(UserCreatedEvent, FailingHandler(ValueError("err A")))
    bus.subscribe(UserCreatedEvent, FailingHandler(RuntimeError("err B")))

    with pytest.raises(ExceptionGroup) as exc_info:
        await bus.publish(UserCreatedEvent("u1"))

    errors = exc_info.value.exceptions
    assert len(errors) == 2
    assert any(isinstance(e, ValueError) for e in errors)
    assert any(isinstance(e, RuntimeError) for e in errors)


@pytest.mark.asyncio
async def test_all_handlers_called_even_when_one_fails():
    bus = EventBus()
    good = RecordingHandler()
    failing = FailingHandler(RuntimeError("boom"))
    also_good = RecordingHandler()

    bus.subscribe(UserCreatedEvent, good)
    bus.subscribe(UserCreatedEvent, failing)
    bus.subscribe(UserCreatedEvent, also_good)

    with pytest.raises(ExceptionGroup):
        await bus.publish(UserCreatedEvent("u1"))

    # Cả good và also_good đều được gọi dù failing raise
    assert len(good.received) == 1
    assert failing.called is True
    assert len(also_good.received) == 1


@pytest.mark.asyncio
async def test_exception_group_message_contains_event_type_name():
    bus = EventBus()
    bus.subscribe(UserCreatedEvent, FailingHandler(Exception("x")))

    with pytest.raises(ExceptionGroup) as exc_info:
        await bus.publish(UserCreatedEvent("u1"))

    assert "UserCreatedEvent" in str(exc_info.value)


@pytest.mark.asyncio
async def test_no_exception_when_all_handlers_succeed():
    bus = EventBus()
    bus.subscribe(UserCreatedEvent, RecordingHandler())
    bus.subscribe(UserCreatedEvent, RecordingHandler())

    await bus.publish(UserCreatedEvent("u1"))   # không raise
