from __future__ import annotations

import asyncio
import enum
import logging
from collections import defaultdict

from xime.core.event._config import EventBusConfig
from xime.core.event.handler import EventHandler

_logger = logging.getLogger(__name__)


class PublishOutcome(enum.Enum):
    """Chuyện gì đã xảy ra với một lần `publish()`. Ba kết cục, không phải hai.

    Trả nợ luật 03 đã khai từ 0.7.2: trước bản này cả ba tình huống dưới đây
    đều trả `None`, nên bên gọi **không có cách nào** biết event của mình có
    được xếp lịch hay đã bị bỏ vì đầy trần. Nợ được hoãn tới 0.8 vì đóng nó là
    đổi chữ ký công khai - mà **0.8 là bản alpha cuối**: `0.8.x` không đổi API
    và 0.9 trở đi coi như đã chốt. Đây là chuyến cuối. Phát hiện T12 của kiểm
    toán 0.8.

    ⚠ **Đừng dùng giá trị này như boolean.** Cả ba đều "truthy" - so sánh
    tường minh với đúng thành viên bạn quan tâm. Ba tình huống này khiến người
    gọi làm ba việc khác nhau, và đó là toàn bộ lý do chúng là ba giá trị:

    | | |
    |---|---|
    | `SCHEDULED` | handler đã xếp lịch chạy nền. Không phải làm gì |
    | `NO_HANDLERS` | **không ai đăng ký** loại event này. Lúc chạy thì vô hại, nhưng nếu bạn tin là có người nghe thì đây là một lỗi nối dây, và nó chỉ nhìn thấy được ở đây |
    | `DROPPED` | vượt `max_pending`, event bị bỏ **nguyên con**. Đây là tín hiệu ngược dòng: hệ thống đang mất việc |

    Tương thích: 31 ứng dụng hiện có bỏ qua giá trị trả về vẫn chạy y nguyên -
    `await bus.publish(e)` không đọc kết quả thì không có gì đổi.
    """

    SCHEDULED = "scheduled"
    NO_HANDLERS = "no_handlers"
    DROPPED = "dropped"

# One WARNING on the first drop, then one every _WARN_EVERY drops. A flood must
# not be able to turn a warning into a second flood, but the running total has
# to stay visible - a log line that appears once and never again reads like a
# one-off incident rather than an ongoing loss.
# Cảnh báo ở lần bỏ ĐẦU, rồi cứ _WARN_EVERY lần bỏ một dòng. Lũ event không được
# biến cảnh báo thành lũ thứ hai, nhưng tổng số phải vẫn nhìn thấy được - một
# dòng log xuất hiện đúng một lần đọc như sự cố lẻ, không như mất mát đang diễn ra.
_WARN_EVERY = 1_000


class EventBus:
    """
    In-process async event bus - fire and forget.

    Events are plain Python objects - no base class required. Any class
    instance can be published. The bus dispatches to all handlers subscribed
    for that exact type (no inheritance matching).

    Registration is explicit: call subscribe() for each (event_type, handler)
    pair, typically from PostConstruct hooks or application config.

    publish() behaviour:
        Each handler is scheduled as an independent asyncio Task. The caller
        is NOT blocked - publish() returns as soon as all tasks are scheduled.
        Handlers run concurrently in the background.

    Ceiling (0.7.2, F15):
        In-flight handler tasks are capped by EventBusConfig.max_pending
        (default 10 000). Over the cap an event is dropped WHOLE and counted;
        see publish(). Declare configure_event_bus(never_drop=(...)) for event
        types that must never be dropped, or max_pending=None for no cap at all.
        Trần số task đang chạy theo EventBusConfig.max_pending (mặc định 10 000);
        quá trần thì event bị bỏ NGUYÊN CON và được đếm.

    Error handling:
        Handler exceptions are logged and do not propagate back to the
        publisher. A failed handler does not affect other handlers.

    Testing / graceful shutdown:
        Call await event_bus.drain() to wait for all in-flight handlers to
        finish before asserting results or stopping the application.

    Typical usage:
        # Registration - e.g. in PostConstruct
        event_bus.subscribe(UserCreatedEvent, self.welcome_email_handler)
        event_bus.subscribe(UserCreatedEvent, self.audit_handler)

        # Publishing - caller returns immediately, handlers run in background
        await event_bus.publish(UserCreatedEvent(user_id=user.id))
    """

    def __init__(self, config: EventBusConfig | None = None) -> None:
        self._handlers: dict[type, list[EventHandler]] = defaultdict(list)
        self._pending: set[asyncio.Task] = set()
        self._config = config or EventBusConfig()
        self._dropped = 0
        self._dropped_by_type: dict[type, int] = defaultdict(int)
        # Its OWN counter, not self._dropped: an exempt type may sail past the
        # ceiling while nothing has ever been dropped, and 0 % N == 0 would then
        # warn on every single publish - the flood the throttle exists to stop.
        # Bộ đếm RIÊNG, không dùng self._dropped: loại được miễn có thể vượt trần
        # trong khi chưa bỏ cái nào, mà 0 % N == 0 thì kêu ở MỌI lần publish -
        # đúng cái lũ log mà phép hãm nhịp sinh ra để chặn.
        self._exempt_over_cap = 0

    @property
    def dropped(self) -> int:
        """How many events have been dropped for hitting the ceiling.

        A log line says an event was just dropped; this says how many. Only the
        second one is usable for choosing a ceiling.
        Log nói vừa bỏ một cái; số này nói đã bỏ bao nhiêu. Chỉ cái thứ hai mới
        dùng được để chọn trần.
        """
        return self._dropped

    def dropped_by_type(self) -> dict[type, int]:
        """Per-event-type drop counts - which event is actually losing."""
        return dict(self._dropped_by_type)

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        """
        Register handler for the given event type.

        Multiple handlers may be registered for the same type; they are
        scheduled concurrently when the event is published. The same handler
        instance may be registered more than once and will be called that
        many times.
        """
        self._handlers[event_type].append(handler)

    async def publish(self, event: object) -> PublishOutcome:
        """
        Schedule all handlers for the event type as background tasks.

        Returns immediately after scheduling - does not wait for handlers
        to complete. No-op when no handlers are registered for the event type.

        Over EventBusConfig.max_pending the event is dropped WHOLE - all of its
        handlers or none. Half an event is worse than no event: one side effect
        happening while its sibling does not is a state nobody designed for,
        and it is invisible from the outside.
        Quá `max_pending` thì event bị bỏ NGUYÊN CON - hoặc chạy hết handler,
        hoặc không handler nào. Nửa event tệ hơn không event: một tác dụng phụ
        xảy ra còn cái đi kèm thì không là trạng thái không ai thiết kế cho, mà
        lại không nhìn thấy được từ bên ngoài.

        Returns a `PublishOutcome`: `SCHEDULED`, `NO_HANDLERS` or `DROPPED`.
        Ignoring the return value is fine and keeps the old behaviour.
        Trả về `PublishOutcome`. Bỏ qua giá trị trả về thì hành vi y như cũ.

        ⭐ Nợ luật 03 khai ở 0.7.2 (*bên gọi không phân biệt được event bị bỏ
        với event đã xếp lịch, cả hai trả `None`*) **được trả ở đây**. Xem
        `PublishOutcome` để biết vì sao là ba giá trị chứ không phải hai, và vì
        sao phải trả ở bản này chứ không phải bản sau.
        """
        # Use .get() rather than indexing the defaultdict so publishing an event
        # type that has no subscribers does not create a permanent empty entry.
        # Dùng .get() thay vì index defaultdict để publish event không có handler
        # không tạo entry rỗng vĩnh viễn.
        event_type = type(event)
        handlers = self._handlers.get(event_type)
        if not handlers:
            return PublishOutcome.NO_HANDLERS

        if not self._has_room(event_type, len(handlers)):
            self._record_drop(event_type, len(handlers))
            return PublishOutcome.DROPPED

        for handler in handlers:
            task = asyncio.create_task(self._dispatch(handler, event))
            self._pending.add(task)
            task.add_done_callback(self._pending.discard)
        return PublishOutcome.SCHEDULED

    def _has_room(self, event_type: type, needed: int) -> bool:
        """Whether this event may be scheduled: no cap, exempt type, or room left."""
        cap = self._config.max_pending
        if cap is None:
            return True
        if event_type in self._config.never_drop:
            # Exempt on purpose: losing this event is worse than the memory it
            # costs. The risk is moved, not removed - so say so, throttled.
            # Miễn có chủ đích: mất event này tệ hơn tốn bộ nhớ. Rủi ro được DỜI
            # chứ không mất, nên phải nói ra, có hãm nhịp.
            if len(self._pending) + needed > cap:
                self._warn_exempt_over_cap(event_type, cap)
            return True
        return len(self._pending) + needed <= cap

    def _record_drop(self, event_type: type, handlers: int) -> None:
        self._dropped += 1
        self._dropped_by_type[event_type] += 1
        if self._dropped == 1 or self._dropped % _WARN_EVERY == 0:
            _logger.warning(
                "EventBus dropped %s: %d handler task(s) in flight, ceiling is %s. "
                "%d event(s) dropped so far. Raise it with "
                "configure_event_bus(max_pending=...), or exempt this type with "
                "never_drop=(%s,) if losing it is worse than the memory it costs.",
                event_type.__name__, len(self._pending), self._config.max_pending,
                self._dropped, event_type.__name__,
            )

    def _warn_exempt_over_cap(self, event_type: type, cap: int) -> None:
        self._exempt_over_cap += 1
        if self._exempt_over_cap == 1 or self._exempt_over_cap % _WARN_EVERY == 0:
            _logger.warning(
                "EventBus is past its ceiling of %d (%d handler task(s) in flight) "
                "but %s is in never_drop, so it is still being scheduled. Memory "
                "will keep growing while this lasts.",
                cap, len(self._pending), event_type.__name__,
            )

    async def drain(self) -> None:
        """
        Wait for all in-flight handler tasks to complete.

        Use in tests to assert side effects, or in shutdown hooks to ensure
        no handler is cut off mid-execution.
        """
        if self._pending:
            await asyncio.gather(*self._pending, return_exceptions=True)

    async def _dispatch(self, handler: EventHandler, event: object) -> None:
        try:
            await handler.handle(event)
        except Exception:
            _logger.error(
                "Unhandled exception in %s while handling %s",
                type(handler).__name__,
                type(event).__name__,
                exc_info=True,
            )
