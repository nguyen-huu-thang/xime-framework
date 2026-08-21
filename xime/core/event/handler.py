from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EventHandler(Protocol):
    """
    Contract for handling a domain event.

    Implement this Protocol to react to a specific event type published
    on the EventBus. A single handler class should handle one event type;
    register it explicitly via EventBus.subscribe().

    Example:
        class UserCreatedHandler:
            def __init__(self, mailer: MailService): ...

            async def handle(self, event: UserCreatedEvent) -> None:
                await self.mailer.send_welcome(event.email)

    Note: @runtime_checkable checks only for the presence of `handle` -
    not its signature. LifecycleManager.subscribe() accepts any object
    that has a callable `handle` attribute.
    """

    async def handle(self, event: Any) -> None: ...
