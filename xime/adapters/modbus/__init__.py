"""Modbus TCP adapter - talk to PLCs and field devices directly.

Where web/gRPC/socket are request/response and MQTT is pub/sub, Modbus is a
third model: Xime acts as the MASTER and actively reads the device. The adapter
is built around a declarative device model that carries the decoding knowledge
Modbus itself does not transmit.

Public API (0.7):
    from xime.adapters.modbus import (
        device, Holding, Input, Coil, Discrete,
        ModbusClient, configure_modbus_devices,
    )

Usage:
    # domain/devices/inverter.py - a plain data class, NOT scanned into DI
    from xime.adapters.modbus import device, Holding, Coil, Input

    @device(unit=1)
    class Inverter:
        voltage:    float = Holding(modicon=40001, type="float32", scale=0.1)
        current:    float = Holding(2, type="float32")
        run_state:  bool  = Coil(0)
        fault_code: int   = Input(9, type="uint16")

Addresses come in two explicit forms, never guessed: `Holding(2)` is the 0-based
protocol address, `Holding(modicon=40003)` is the number printed in the device
datasheet. Mixing them in one call is an error.
Địa chỉ có hai đường vào tường minh: số 0-based của giao thức, hoặc số Modicon
in trên datasheet - không bao giờ đoán.

Requires the extra: pip install 'xime[modbus]'
"""

from ._adapter import ModbusAdapter
from ._client import ModbusClient
from ._codec import decode_device, decode_field, encode_field
from ._config import (
    DEFAULT_DEVICE,
    ModbusConfig,
    ModbusServerConfig,
    configure_modbus_devices,
    configure_modbus_server,
    modbus_registry,
)
from ._decorators import on_change, on_write, poll, serve
from ._errors import (
    ModbusCodecError,
    ModbusConnectionError,
    ModbusDeviceError,
    ModbusError,
)
from ._model import (
    Area,
    Coil,
    DataType,
    DeviceInfo,
    Discrete,
    Holding,
    Input,
    ModbusField,
    device,
    get_device_info,
    require_device_info,
)
from ._planner import ReadCommand, describe_plan, plan_reads
from ._runtime import ModbusConnection
from ._server import ModbusServerAdapter

__all__ = [
    # device model
    "device",
    "Holding",
    "Input",
    "Coil",
    "Discrete",
    "Area",
    "DataType",
    "DeviceInfo",
    "ModbusField",
    "get_device_info",
    "require_device_info",
    # handlers
    "poll",
    "on_change",
    "serve",
    "on_write",
    # client & adapters
    "ModbusAdapter",
    "ModbusServerAdapter",
    "ModbusClient",
    "ModbusConnection",
    # configuration
    "configure_modbus_devices",
    "configure_modbus_server",
    "ModbusConfig",
    "ModbusServerConfig",
    "modbus_registry",
    "DEFAULT_DEVICE",
    # codec
    "decode_field",
    "encode_field",
    "decode_device",
    # errors
    "ModbusError",
    "ModbusCodecError",
    "ModbusConnectionError",
    "ModbusDeviceError",
    # read planning
    "ReadCommand",
    "plan_reads",
    "describe_plan",
]
