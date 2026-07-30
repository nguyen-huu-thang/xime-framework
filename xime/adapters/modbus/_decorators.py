"""Decorators marking controller methods as device-driven handlers.

Modbus is the third interaction model in Xime: web/gRPC/socket are
request/response, MQTT is pub/sub, and here the FRAMEWORK drives — it reads the
device on a timer and calls your code with the result. Hence dedicated
decorators rather than reusing @subscribe.
Ở đây FRAMEWORK là bên chủ động: nó đọc thiết bị theo nhịp rồi gọi code của bạn.

    class InverterMonitor:
        def __init__(self, alerts: AlertService) -> None:
            self._alerts = alerts

        @poll(Inverter, interval=1.0)
        async def on_sample(self, inverter: Inverter) -> None:
            await self._alerts.record(inverter.voltage)

        @on_change(Inverter.fault_code)
        async def on_fault(self, value: int) -> None:
            await self._alerts.raise_fault(value)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

# Attribute name marking Modbus handler methods — internal to the framework.
# Mirrors MQTT_ATTR (mqtt) / ROUTE_ATTR (web).
MODBUS_ATTR = "_xime_modbus_info"


class ModbusKind(Enum):
    """What drives a handler."""

    POLL = "poll"            # every cycle, with the whole model
    ON_CHANGE = "on_change"  # only when one field's value changed
    SERVE = "serve"          # master asked us (slave mode) for values
    ON_WRITE = "on_write"    # master wrote to us (slave mode)


@dataclass
class ModbusHandlerInfo:
    """Metadata attached to a controller method by the decorators."""

    kind: ModbusKind
    model: type | None = None
    field: Any = None                 # ModbusField, kept loose to avoid a cycle
    interval: float | None = None
    deadband: float | None = None
    device: str | None = None         # None -> whichever adapter runs it


def poll(model: type, *, interval: float = 1.0, device: str | None = None) -> Callable:
    """Read `model` every `interval` seconds and hand the instance to the method.

        @poll(Inverter, interval=0.5)
        async def on_sample(self, inverter: Inverter) -> None: ...

    A model may be polled at several intervals by different handlers; the
    adapter runs one loop per (model, interval) pair, so two handlers sharing
    both never cause two reads.
    Một model có thể poll ở nhiều nhịp; adapter chạy một vòng cho mỗi cặp
    (model, interval) nên hai handler cùng nhịp không gây hai lần đọc.

    `device` targets a specific named device; leave it out to use the one the
    adapter serves.
    """
    def decorator(func: Callable) -> Callable:
        setattr(
            func,
            MODBUS_ATTR,
            ModbusHandlerInfo(
                ModbusKind.POLL, model=model, interval=interval, device=device
            ),
        )
        return func

    return decorator


def on_change(
    field: Any,
    *,
    deadband: float | None = None,
    device: str | None = None,
) -> Callable:
    """Call the method only when `field`'s value changed between two reads.

        @on_change(Inverter.fault_code)
        async def on_fault(self, value: int) -> None: ...

        @on_change(Tank.level, deadband=0.5)      # ignore drift under 0.5
        async def on_level(self, value: float) -> None: ...

    The field's model must also be polled somewhere — @on_change observes the
    value the poll loop already read rather than issuing its own request. If the
    model is polled at several intervals, the FASTEST one drives the comparison,
    since that is the earliest a change could be noticed.
    @on_change quan sát giá trị vòng poll đã đọc, không tự gửi lệnh riêng.

    `deadband` matters for analogue readings: without it, sensor noise in the
    last digit makes a float handler fire on nearly every cycle. A change is
    reported only once the value moved by more than `deadband`.
    Không có deadband thì nhiễu đo ở chữ số cuối làm handler bắn gần như mỗi
    chu kỳ.
    """
    def decorator(func: Callable) -> Callable:
        setattr(
            func,
            MODBUS_ATTR,
            ModbusHandlerInfo(
                ModbusKind.ON_CHANGE, field=field, deadband=deadband, device=device
            ),
        )
        return func

    return decorator


def serve(model: type) -> Callable:
    """Expose `model` while Xime acts as a Modbus slave.

        @serve(Inverter)
        async def provide(self) -> Inverter: ...

    The framework calls the method to refresh the values it serves to masters.
    See _server.py for the full slave-mode picture.
    """
    def decorator(func: Callable) -> Callable:
        setattr(func, MODBUS_ATTR, ModbusHandlerInfo(ModbusKind.SERVE, model=model))
        return func

    return decorator


def on_write(field: Any) -> Callable:
    """Call the method when a master writes `field` while Xime is a slave.

        @on_write(Inverter.run_state)
        async def handle_command(self, value: bool) -> None: ...
    """
    def decorator(func: Callable) -> Callable:
        setattr(func, MODBUS_ATTR, ModbusHandlerInfo(ModbusKind.ON_WRITE, field=field))
        return func

    return decorator


def get_modbus_info(func: Any) -> ModbusHandlerInfo | None:
    """Return the ModbusHandlerInfo attached to a method, or None."""
    return getattr(func, MODBUS_ATTR, None)
