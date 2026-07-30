"""Runtime configuration and registry for the OPC UA adapter.

    opcua:
      endpoint: opc.tcp://10.0.0.6:4840          # required
      security: SignAndEncrypt                   # None | Sign | SignAndEncrypt
      certificate: /etc/xime/opcua-client.der
      private_key: /etc/xime/opcua-client.pem
      username: svc                              # omit for anonymous
      password: secret
      reconnect_delay: 3.0
      max_concurrency: 16
      subscription_period: 200                   # milliseconds
      server:
        endpoint: opc.tcp://0.0.0.0:4840/xime
        name: Xime OPC UA Server
        security: None

Servers are keyed by a logical name like Modbus devices and MQTT clients, so an
application can talk to more than one OPC UA server.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from xime.core.config.runtime import RuntimeConfig
from xime.core.exception.framework import StartupException

from ._runtime import OpcuaConnection
from ._security import normalize_mode

DEFAULT_SERVER = "default"


class OpcuaConfig(BaseModel):
    """Resolved client settings for ONE named OPC UA server."""

    name: str
    endpoint: str
    security: str = "None"
    certificate: str | None = None
    private_key: str | None = None
    # Must equal the URI in the client certificate's SubjectAltName once
    # security is Sign or SignAndEncrypt: the server checks the two agree and
    # answers BadCertificateUriInvalid when they do not. asyncua's default is
    # its own placeholder (urn:example.org:FreeOpcUa:opcua-asyncio) and it never
    # derives the value from the certificate, so without this setting a real
    # certificate could not be used at all.
    # Phải khớp URI trong SubjectAltName của cert client khi bật Sign/
    # SignAndEncrypt - server đối chiếu hai giá trị và trả BadCertificateUriInvalid
    # nếu lệch. asyncua để mặc định URI của chính nó và KHÔNG tự đọc từ cert.
    application_uri: str | None = None
    username: str | None = None
    password: str | None = None
    timeout: float = 4.0
    reconnect_delay: float = 3.0
    max_concurrency: int = 16
    subscription_period: float = 200.0   # milliseconds

    @classmethod
    def resolve(cls, runtime: RuntimeConfig, name: str) -> OpcuaConfig:
        """Build the config for one server; fail-fast with an actionable message.

        A single-server application writes the settings directly under `opcua:`;
        a multi-server one nests them under `opcua.servers.<name>`. Both forms
        are supported so the common case stays short.
        App một server viết thẳng dưới `opcua:`; nhiều server thì lồng trong
        `opcua.servers.<tên>`.
        """
        raw = runtime.get("opcua")
        raw = raw if isinstance(raw, dict) else {}
        servers = raw.get("servers")
        servers = servers if isinstance(servers, dict) else {}

        if name in servers and isinstance(servers[name], dict):
            entry: dict[str, Any] = servers[name]
        elif name == DEFAULT_SERVER:
            entry = raw
        else:
            known = ", ".join(sorted(servers)) or "(none)"
            raise StartupException(
                f"\nUnknown OPC UA server\n"
                f"  Server: {name}\n"
                f"  Known : {known}\n"
                f"  Fix   : add it under 'opcua.servers.{name}' in "
                f"resources/application.yml."
            )

        def pick(key: str, fallback: Any) -> Any:
            if key in entry:
                return entry[key]
            if key in raw:
                return raw[key]
            return fallback

        endpoint = entry.get("endpoint") or (
            raw.get("endpoint") if entry is not raw else None
        )
        if not endpoint:
            where = f"opcua.servers.{name}.endpoint" if entry is not raw else "opcua.endpoint"
            raise StartupException(
                f"\nMissing OPC UA endpoint\n"
                f"  Server: {name}\n"
                f"  Fix   : set '{where}' in resources/application.yml, e.g.\n"
                f"            opc.tcp://10.0.0.6:4840"
            )

        return cls(
            name=name,
            endpoint=str(endpoint),
            security=normalize_mode(pick("security", "None")),
            certificate=pick("certificate", None),
            private_key=pick("private_key", None),
            application_uri=pick("application_uri", None),
            username=pick("username", None),
            password=pick("password", None),
            timeout=float(pick("timeout", 4.0)),
            reconnect_delay=float(pick("reconnect_delay", 3.0)),
            max_concurrency=int(pick("max_concurrency", 16)),
            subscription_period=float(pick("subscription_period", 200.0)),
        )


class OpcuaServerConfig(BaseModel):
    """Settings for serving OPC UA, read from the `opcua.server` block."""

    endpoint: str = "opc.tcp://0.0.0.0:4840/xime"
    name: str = "Xime OPC UA Server"
    security: str = "None"
    certificate: str | None = None
    private_key: str | None = None
    # Same rule as the client side: connecting clients validate this against
    # the URI in our certificate once security is on. See OpcuaConfig.
    application_uri: str | None = None

    @classmethod
    def resolve(cls, runtime: RuntimeConfig) -> OpcuaServerConfig:
        raw = runtime.get("opcua")
        raw = raw if isinstance(raw, dict) else {}
        server = raw.get("server")
        server = server if isinstance(server, dict) else {}
        return cls(
            endpoint=str(server.get("endpoint", "opc.tcp://0.0.0.0:4840/xime")),
            name=str(server.get("name", "Xime OPC UA Server")),
            security=normalize_mode(server.get("security", "None")),
            certificate=server.get("certificate"),
            private_key=server.get("private_key"),
            application_uri=server.get("application_uri"),
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class _OpcuaRegistry:
    """Module-level singleton shared by the adapter and the client."""

    def __init__(self) -> None:
        self._packages: list[str] = []
        self._server_packages: list[str] = []
        self._connections: dict[str, OpcuaConnection] = {}

    def add_packages(self, *packages: str) -> None:
        self._packages.extend(packages)

    def get_packages(self) -> list[str]:
        return list(self._packages)

    def add_server_packages(self, *packages: str) -> None:
        self._server_packages.extend(packages)

    def get_server_packages(self) -> list[str]:
        return list(self._server_packages)

    def connection(self, name: str) -> OpcuaConnection:
        conn = self._connections.get(name)
        if conn is None:
            conn = OpcuaConnection(name)
            self._connections[name] = conn
        return conn

    def reset(self) -> None:
        """Clear all registrations - test cleanup only."""
        self._packages.clear()
        self._server_packages.clear()
        self._connections.clear()


opcua_registry = _OpcuaRegistry()


def configure_opcua_nodes(*packages: str) -> None:
    """Register packages containing @on_node_change controller classes.

    Call once in your config layer (e.g. config/opcua.py); these packages must
    ALSO be in dependency.scan() so DI creates the instances.
    """
    opcua_registry.add_packages(*packages)


def configure_opcua_server(*packages: str) -> None:
    """Register packages containing @serve_nodes / @on_node_write classes.

    Separate from configure_opcua_nodes for the same reason as Modbus: serving
    and consuming are independent, and merging them would open a listening
    endpoint for an application that only reads.
    """
    opcua_registry.add_server_packages(*packages)
