from __future__ import annotations

from collections import defaultdict

from core.event.handler import EventHandler


class EventBus:
    """
    In-process synchronous event bus.

    Events are plain Python objects — no base class required. Any class
    instance can be published. The bus dispatches to all handlers subscribed
    for that exact type (no inheritance matching).

    Registration is explicit: call subscribe() for each (event_type, handler)
    pair, typically from PostConstruct hooks or application config.

    publish() behaviour on errors:
        Every handler is called even when previous ones raise. All exceptions
        are collected and re-raised together as ExceptionGroup so no handler
        failure silently swallows another handler's work.

    Typical usage:
        # Registration — e.g. in PostConstruct
        event_bus.subscribe(UserCreatedEvent, self.welcome_email_handler)
        event_bus.subscribe(UserCreatedEvent, self.audit_handler)

        # Publishing — anywhere a business operation completes
        await event_bus.publish(UserCreatedEvent(user_id=user.id))
    """

    def __init__(self) -> None:
        self._handlers: dict[type, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        """
        Register handler for the given event type.

        Multiple handlers may be registered for the same type; they are
        called in subscription order. The same handler instance may be
        registered more than once and will be called that many times.
        """
        self._handlers[event_type].append(handler)

    async def publish(self, event: object) -> None:
        """
        Dispatch event to all handlers registered for its exact type.

        All handlers are invoked even when some raise. Exceptions are
        collected and re-raised as ExceptionGroup after every handler
        has been attempted.

        No-op when no handlers are registered for the event type.
        """
        handlers = self._handlers[type(event)]
        if not handlers:
            return

        errors: list[Exception] = []
        for handler in handlers:
            try:
                await handler.handle(event)
            except Exception as exc:
                errors.append(exc)

        if errors:
            raise ExceptionGroup(
                f"Errors handling {type(event).__name__}", errors
            )
