"""Decorators for OPC UA controllers.

Unlike Modbus, OPC UA has real subscriptions: the SERVER pushes a notification
when a value changes, so there is no poll loop and no interval to choose. What
the framework adds is turning that notification into a call on your service
with the value already extracted.
OPC UA có subscription thật: SERVER đẩy thông báo khi giá trị đổi, nên không có
vòng poll và không phải chọn nhịp.

    class TankMonitor:
        @on_node_change(Tank.level, deadband=0.5)
        async def level_changed(self, value: float) -> None: ...

    class TankEmulator:
        @serve_nodes(Tank)
        async def provide(self) -> Tank: ...

        @on_node_write(Tank.setpoint)
        async def setpoint_written(self, value: float) -> None: ...
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

OPCUA_ATTR = "_xime_opcua_info"


class OpcuaKind(Enum):
    """What drives a handler."""

    ON_CHANGE = "on_change"    # server pushed a new value (client side)
    SERVE = "serve"            # we publish these nodes (server side)
    ON_WRITE = "on_write"      # a client wrote to us (server side)


@dataclass
class OpcuaHandlerInfo:
    """Metadata attached to a controller method by the decorators."""

    kind: OpcuaKind
    node: Any = None            # OpcuaNode, kept loose to avoid an import cycle
    model: type | None = None
    deadband: float | None = None
    initial: bool = False
    server: str | None = None


def on_node_change(
    node: Any,
    *,
    deadband: float | None = None,
    initial: bool = False,
    server: str | None = None,
) -> Callable:
    """Call the method when the server reports a new value for `node`.

        @on_node_change(Tank.level, deadband=0.5)
        async def changed(self, value: float) -> None: ...

    `deadband` filters analogue noise the same way as the Modbus @on_change:
    the handler runs only once the value moved by MORE than the deadband.

    `initial` decides what to do with the value OPC UA delivers immediately on
    subscribing. It defaults to False so this behaves like Modbus @on_change —
    the first reading establishes a baseline and is not reported as news.
    Set it True when the handler genuinely wants the current state at startup.
    `initial=False` (mặc định) để giống @on_change của Modbus: lần đầu chỉ lấy
    mốc, không coi là thay đổi.
    """
    def decorator(func: Callable) -> Callable:
        setattr(
            func,
            OPCUA_ATTR,
            OpcuaHandlerInfo(
                OpcuaKind.ON_CHANGE, node=node, deadband=deadband,
                initial=initial, server=server,
            ),
        )
        return func

    return decorator


def serve_nodes(model: type) -> Callable:
    """Publish `model`'s nodes while Xime acts as an OPC UA server.

        @serve_nodes(Tank)
        async def provide(self) -> Tank: ...

    The framework calls the method on a timer and writes the returned values
    into the served address space.
    """
    def decorator(func: Callable) -> Callable:
        setattr(func, OPCUA_ATTR, OpcuaHandlerInfo(OpcuaKind.SERVE, model=model))
        return func

    return decorator


def on_node_write(node: Any) -> Callable:
    """Call the method when a client writes `node` while Xime is a server.

        @on_node_write(Tank.setpoint)
        async def setpoint_written(self, value: float) -> None: ...
    """
    def decorator(func: Callable) -> Callable:
        setattr(func, OPCUA_ATTR, OpcuaHandlerInfo(OpcuaKind.ON_WRITE, node=node))
        return func

    return decorator


def get_opcua_info(func: Any) -> OpcuaHandlerInfo | None:
    """Return the OpcuaHandlerInfo attached to a method, or None."""
    return getattr(func, OPCUA_ATTR, None)
