"""Private adapter contributions supplied by framework-owned adapters.

This is an internal bridge, not an application adapter extension API. A
protocol package may register a provider for framework-owned listeners whose
configuration is outside ``process``/``processes`` but still needs normal
topology validation and adapter lifecycle handling.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from xime.core.bootstrap._processes import (
    ProcessTopology,
    topology_error,
    with_internal_endpoint,
)
from xime.core.bootstrap._slot import adapter_id_of, adapter_kind_of

if TYPE_CHECKING:
    from xime.core.bootstrap.adapter import Adapter
    from xime.core.config.runtime import RuntimeConfig


@dataclass(frozen=True)
class InternalAdapterContribution:
    """One framework-owned listener placed at the current primary."""

    adapter: Adapter
    host: str | None
    port: int | None
    options: Mapping[str, Any] = field(default_factory=dict)
    where: str = "framework internal listener"


Provider = Callable[[Any, tuple[Any, ...]], Iterable[InternalAdapterContribution]]
ControlHandler = Callable[[Any, bytes], Awaitable[bytes | None]]

_providers: list[Provider] = []
_control_handlers: list[ControlHandler] = []


def register_internal_adapter_provider(provider: Provider) -> None:
    """Register one private provider. Re-imports are idempotent."""
    if provider not in _providers:
        _providers.append(provider)


def collect_internal_adapters(
    runtime: RuntimeConfig, adapters: tuple[Adapter, ...]
) -> tuple[InternalAdapterContribution, ...]:
    return tuple(
        contribution
        for provider in tuple(_providers)
        for contribution in provider(runtime, adapters)
    )


def register_internal_control_handler(handler: ControlHandler) -> None:
    """Register a private handler for opaque framework adapter commands."""
    if handler not in _control_handlers:
        _control_handlers.append(handler)


async def dispatch_internal_control(app: Any, payload: bytes) -> bytes:
    for handler in tuple(_control_handlers):
        result = await handler(app, payload)
        if result is not None:
            return result[:495]
    return b"unhandled"


def apply_internal_adapters(
    topology: ProcessTopology,
    contributions: tuple[InternalAdapterContribution, ...],
) -> ProcessTopology:
    """Add internal listeners after parsing user topology, then recheck binds."""
    seen: set[tuple[str, str]] = set()
    for contribution in contributions:
        adapter = contribution.adapter
        key = (adapter_kind_of(adapter), adapter_id_of(adapter))
        if key in seen:
            raise topology_error(
                "Duplicate Internal Adapter",
                f"Adapter: {key[0]}.{key[1]}",
                "Detail : two framework features requested the same reserved listener.",
            )
        seen.add(key)
        topology = with_internal_endpoint(
            topology,
            kind=key[0],
            adapter_id=key[1],
            host=contribution.host,
            port=contribution.port,
            options=dict(contribution.options),
            where=contribution.where,
        )
    return topology


__all__ = [
    "InternalAdapterContribution",
    "apply_internal_adapters",
    "collect_internal_adapters",
    "dispatch_internal_control",
    "register_internal_adapter_provider",
    "register_internal_control_handler",
]
