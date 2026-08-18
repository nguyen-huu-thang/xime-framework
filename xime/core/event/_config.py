from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EventBusConfig:
    """How the in-process EventBus behaves when handlers pile up (F15).

    This is a FRAMEWORK config, not a runtime one: how many in-flight handlers
    an application can carry is a property of its design - how heavy its
    handlers are, how large its events are, which of its events must never be
    lost - not an environment setting an operator tunes per deployment. It
    therefore lives in Python (config/*.py) like routing and DI bindings, not in
    application.yml.
    Đây là FRAMEWORK config, không phải runtime config: gánh được bao nhiêu
    handler cùng lúc, và event nào không được phép mất, là thuộc tính THIẾT KẾ
    của app - không phải thứ người vận hành chỉnh theo môi trường. Nên nó nằm
    trong Python (config/*.py) cạnh routing và DI binding, không nằm trong
    application.yml.

    Attributes:
        max_pending: ceiling on in-flight handler tasks. `None` = no ceiling at
            all (the pre-0.7.2 behaviour), an explicit choice a developer can
            make; it is not the default.
        never_drop: event types exempt from the ceiling. Use for events whose
            loss is worse than the memory they cost - audit trails, money,
            anything with a legal or accounting meaning. Matched by EXACT type,
            like handler lookup: no inheritance matching.
            Loại event được miễn trần. Dùng cho event mà MẤT còn tệ hơn tốn bộ
            nhớ: nhật ký kiểm toán, tiền, thứ có ý nghĩa pháp lý hoặc kế toán.
            Khớp theo KIỂU CHÍNH XÁC, giống cách tra handler - không khớp kế thừa.
    """

    max_pending: int | None = 10_000
    never_drop: frozenset[type] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.max_pending is not None and self.max_pending < 1:
            raise ValueError(
                f"EventBusConfig.max_pending must be >= 1 or None, got {self.max_pending}. "
                "Use None to state 'no ceiling' on purpose."
            )
        bad = [t for t in self.never_drop if not isinstance(t, type)]
        if bad:
            raise ValueError(
                f"EventBusConfig.never_drop must contain event CLASSES, got {bad!r}. "
                "Pass the type itself (AuditEvent), not an instance or a name."
            )


class _EventBusRegistry:
    """Module-level singleton read by the startup orchestrator.

    Same explicit-call pattern as configure_socket_controllers() and friends:
    the framework never scans for config, the developer calls a function.
    Cùng khuôn gọi tường minh với configure_socket_controllers(): framework
    không đi quét config, lập trình viên gọi hàm.
    """

    def __init__(self) -> None:
        self._config = EventBusConfig()

    def set_config(self, config: EventBusConfig) -> None:
        self._config = config

    def get_config(self) -> EventBusConfig:
        return self._config

    def reset(self) -> None:
        """Restore defaults. For tests - production code calls this never."""
        self._config = EventBusConfig()


event_bus_registry = _EventBusRegistry()


def configure_event_bus(
    *,
    max_pending: int | None = 10_000,
    never_drop: tuple[type, ...] | list[type] | frozenset[type] = (),
) -> None:
    """Set the in-flight ceiling for EventBus handler tasks, and its exemptions.

    `publish()` schedules one asyncio Task per subscribed handler and returns
    immediately. Without a ceiling, any user-reachable path that publishes lets
    a caller multiply tasks by request count; each pending task also keeps the
    event object alive, so memory grows with EVENT SIZE, not with a fixed
    per-task overhead.
    `publish()` sinh một task cho mỗi handler rồi trả về ngay. Không có trần thì
    mọi đường đi người dùng có publish đều cho phép nhân số task theo số request;
    mỗi task đang chờ còn GIỮ SỐNG object event, nên bộ nhớ tăng theo KÍCH THƯỚC
    EVENT chứ không theo một hằng số overhead.

    Over the ceiling an event is dropped WHOLE (never half its handlers) and a
    WARNING is logged. Pick the number from your own handlers: how long they
    run, and how big your events are.
    Quá trần thì event bị bỏ NGUYÊN CON (không bao giờ bỏ nửa số handler) và có
    log WARNING. Chọn con số theo handler của chính bạn.

    Two ways to say "do not drop this":

        # config/event.py
        from xime.core.event import configure_event_bus

        # 1. Miễn trần cho vài loại event - phần còn lại vẫn có trần
        configure_event_bus(max_pending=10_000, never_drop=(AuditEvent, PaymentEvent))

        # 2. Bỏ trần hoàn toàn - hành vi trước 0.7.2, cố ý chọn
        configure_event_bus(max_pending=None)

    ⚠ `never_drop` moves the risk, it does not remove it: a flood of an exempt
    event still grows without bound. Exempt what you cannot afford to lose, not
    what you would merely prefer to keep.
    ⚠ `never_drop` DỜI rủi ro chứ không xoá nó: lũ event được miễn vẫn phình vô
    hạn. Chỉ miễn thứ KHÔNG ĐƯỢC PHÉP mất, đừng miễn thứ chỉ "muốn giữ".
    """
    event_bus_registry.set_config(
        EventBusConfig(max_pending=max_pending, never_drop=frozenset(never_drop))
    )
