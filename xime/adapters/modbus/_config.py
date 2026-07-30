"""Runtime configuration and the module-level registry.

Devices are addressed by a LOGICAL NAME rather than by host:port, matching how
MQTT keys connections by client_id and gRPC/web key servers by server_id:

    modbus:
      timeout: 3.0            # defaults shared by every device
      word_order: big
      max_gap: 8
      devices:
        inverter_1: { host: 10.0.0.5, port: 502, unit: 1 }
        meter_a:    { host: 10.0.0.6, unit: 3, timeout: 5.0 }

A name is what the code refers to (`ModbusAdapter("inverter_1")`,
`modbus.read(Inverter, device="meter_a")`), so re-cabling a plant means editing
YAML, not code.
Tên logic là thứ code nhắc tới, nên đổi dây trong nhà máy chỉ phải sửa YAML.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from xime.core.config.runtime import RuntimeConfig
from xime.core.exception.framework import StartupException

from ._planner import DEFAULT_MAX_GAP
from ._runtime import ModbusConnection

# Device name used when the application never says which one it means. A
# single-device app can just call it "default" in YAML and never pass a name.
DEFAULT_DEVICE = "default"


class ModbusConfig(BaseModel):
    """Resolved settings for ONE named device.

    Every field except `host` falls back to the top-level `modbus` block, so
    shared settings are written once. `host` has no sensible shared value and
    is required per device.
    Mọi thiết lập trừ `host` đều rơi về khối `modbus` chung.
    """

    name: str
    host: str
    port: int = 502
    unit: int = 1
    timeout: float = 3.0
    byte_order: str = "big"
    word_order: str = "big"
    reconnect_delay: float = 3.0
    max_concurrency: int = 16
    max_gap: int = DEFAULT_MAX_GAP

    @classmethod
    def resolve(cls, runtime: RuntimeConfig, name: str) -> ModbusConfig:
        """Build the config for one device; fail-fast with an actionable message.

        Startup is the only place these mistakes are cheap to find: a missing
        device entry discovered at the first read means a plant already running.
        """
        raw = runtime.get("modbus")
        raw = raw if isinstance(raw, dict) else {}
        devices = raw.get("devices")
        devices = devices if isinstance(devices, dict) else {}

        entry = devices.get(name)
        if not isinstance(entry, dict):
            known = ", ".join(sorted(devices)) or "(none)"
            raise StartupException(
                f"\nUnknown Modbus device\n"
                f"  Device : {name}\n"
                f"  Known  : {known}\n"
                f"  Fix    : add it under 'modbus.devices.{name}' in "
                f"resources/application.yml, e.g.\n"
                f"             modbus:\n"
                f"               devices:\n"
                f"                 {name}: {{ host: 10.0.0.5, port: 502, unit: 1 }}"
            )

        host = entry.get("host")
        if not host:
            raise StartupException(
                f"\nMissing Modbus host\n"
                f"  Device: {name}\n"
                f"  Fix   : set 'modbus.devices.{name}.host' in "
                f"resources/application.yml."
            )

        def pick(key: str, fallback: Any) -> Any:
            """Device entry wins, then the shared block, then the default."""
            if key in entry:
                return entry[key]
            if key in raw:
                return raw[key]
            return fallback

        config = cls(
            name=name,
            host=str(host),
            port=int(pick("port", 502)),
            unit=int(pick("unit", 1)),
            timeout=float(pick("timeout", 3.0)),
            byte_order=str(pick("byte_order", "big")),
            word_order=str(pick("word_order", "big")),
            reconnect_delay=float(pick("reconnect_delay", 3.0)),
            max_concurrency=int(pick("max_concurrency", 16)),
            max_gap=int(pick("max_gap", DEFAULT_MAX_GAP)),
        )
        config._validate()
        return config

    def _validate(self) -> None:
        for label, value in (("byte_order", self.byte_order), ("word_order", self.word_order)):
            if value not in ("big", "little"):
                raise StartupException(
                    f"\nInvalid Modbus {label}\n"
                    f"  Device: {self.name}\n"
                    f"  Value : {value!r}\n"
                    f"  Fix   : use 'big' or 'little'."
                )
        if not 0 <= self.unit <= 255:
            raise StartupException(
                f"\nInvalid Modbus unit id\n"
                f"  Device: {self.name}\n"
                f"  Value : {self.unit}\n"
                f"  Fix   : the unit id travels in one byte, so use 0-255."
            )
        if self.max_gap < 0:
            raise StartupException(
                f"\nInvalid Modbus max_gap\n"
                f"  Device: {self.name}\n"
                f"  Value : {self.max_gap}\n"
                f"  Fix   : use 0 (read exactly the declared addresses) or more."
            )
        if self.max_concurrency < 1:
            raise StartupException(
                f"\nInvalid Modbus max_concurrency\n"
                f"  Device: {self.name}\n"
                f"  Value : {self.max_concurrency}\n"
                f"  Fix   : use 1 (sequential) or more."
            )


class ModbusServerConfig(BaseModel):
    """Settings for the slave server, read from the 'modbus.server' block.

        modbus:
          server:
            host: 0.0.0.0
            port: 5020
    """

    host: str = "0.0.0.0"
    port: int = 5020

    @classmethod
    def resolve(cls, runtime: RuntimeConfig) -> ModbusServerConfig:
        raw = runtime.get("modbus")
        raw = raw if isinstance(raw, dict) else {}
        server = raw.get("server")
        server = server if isinstance(server, dict) else {}
        return cls(
            host=str(server.get("host", "0.0.0.0")),
            port=int(server.get("port", 5020)),
        )


# ---------------------------------------------------------------------------
# Registry — controller packages and shared connections
# ---------------------------------------------------------------------------

class _ModbusRegistry:
    """Module-level singleton read by the adapter and the client.

    Holds one shared ModbusConnection per device name so the adapter (which owns
    the connection) and ModbusClient (a DI singleton used by business code)
    resolve the same object. Mirrors mqtt_registry.
    """

    def __init__(self) -> None:
        self._packages: list[str] = []
        self._server_packages: list[str] = []
        self._connections: dict[str, ModbusConnection] = {}

    def add_packages(self, *packages: str) -> None:
        self._packages.extend(packages)

    def get_packages(self) -> list[str]:
        return list(self._packages)

    def add_server_packages(self, *packages: str) -> None:
        self._server_packages.extend(packages)

    def get_server_packages(self) -> list[str]:
        return list(self._server_packages)

    def connection(self, name: str) -> ModbusConnection:
        """Get or create the shared connection holder for a device name."""
        conn = self._connections.get(name)
        if conn is None:
            conn = ModbusConnection(name)
            self._connections[name] = conn
        return conn

    def connection_names(self) -> list[str]:
        return list(self._connections)

    def reset(self) -> None:
        """Clear all registrations - test cleanup only."""
        self._packages.clear()
        self._server_packages.clear()
        self._connections.clear()


modbus_registry = _ModbusRegistry()


def configure_modbus_devices(*packages: str) -> None:
    """Register packages containing @poll / @on_change controller classes.

    Call once in your config layer (e.g. config/modbus.py). ModbusAdapter reads
    this registry after DI startup and builds the poll table. These packages
    must ALSO be in dependency.scan() so DI creates the instances.

    Example:
        from xime.adapters.modbus import configure_modbus_devices
        configure_modbus_devices("api.modbus")
    """
    modbus_registry.add_packages(*packages)


def configure_modbus_server(*packages: str) -> None:
    """Register packages containing @serve / @on_write controller classes.

    Kept separate from configure_modbus_devices because serving as a slave and
    polling as a master are independent capabilities: most applications do one
    or the other, and mixing the two registries would start a TCP listener for
    an app that only ever reads.
    Tách riêng vì làm slave và làm master là hai việc độc lập - gộp chung sẽ mở
    cổng lắng nghe cho cả app chỉ đọc.
    """
    modbus_registry.add_server_packages(*packages)
