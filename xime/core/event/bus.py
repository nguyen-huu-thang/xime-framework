from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from xime.core.event.handler import EventHandler

_logger = logging.getLogger(__name__)


class EventBus:
    """
    In-process async event bus — fire and forget.

    Events are plain Python objects — no base class required. Any class
    instance can be published. The bus dispatches to all handlers subscribed
    for that exact type (no inheritance matching).

    Registration is explicit: call subscribe() for each (event_type, handler)
    pair, typically from PostConstruct hooks or application config.

    publish() behaviour:
        Each handler is scheduled as an independent asyncio Task. The caller
        is NOT blocked — publish() returns as soon as all tasks are scheduled.
        Handlers run concurrently in the background.

    Error handling:
        Handler exceptions are logged and do not propagate back to the
        publisher. A failed handler does not affect other handlers.

    Testing / graceful shutdown:
        Call await event_bus.drain() to wait for all in-flight handlers to
        finish before asserting results or stopping the application.

    Typical usage:
        # Registration — e.g. in PostConstruct
        event_bus.subscribe(UserCreatedEvent, self.welcome_email_handler)
        event_bus.subscribe(UserCreatedEvent, self.audit_handler)

        # Publishing — caller returns immediately, handlers run in background
        await event_bus.publish(UserCreatedEvent(user_id=user.id))
    """

    def __init__(self) -> None:
        self._handlers: dict[type, list[EventHandler]] = defaultdict(list)
        self._pending: set[asyncio.Task] = set()

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        """
        Register handler for the given event type.

        Multiple handlers may be registered for the same type; they are
        scheduled concurrently when the event is published. The same handler
        instance may be registered more than once and will be called that
        many times.
        """
        self._handlers[event_type].append(handler)

    async def publish(self, event: object) -> None:
        """
        Schedule all handlers for the event type as background tasks.

        Returns immediately after scheduling — does not wait for handlers
        to complete. No-op when no handlers are registered for the event type.
        """
        handlers = self._handlers[type(event)]
        if not handlers:
            return

        for handler in handlers:
            task = asyncio.create_task(self._dispatch(handler, event))
            self._pending.add(task)
            task.add_done_callback(self._pending.discard)

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
