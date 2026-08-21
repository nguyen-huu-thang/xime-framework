"""OPC UA adapter - the modern industrial protocol, both directions.

Where Modbus gives you raw 16-bit words, OPC UA carries types, names and real
subscriptions. So the model here is thinner (nothing to decode) and the adapter
does not poll: the server pushes.

Public API (0.7):
    from xime.adapters.opcua import (
        node_model, Node,
        on_node_change, serve_nodes, on_node_write,
        OpcuaAdapter, OpcuaServerAdapter, OpcuaClient,
        configure_opcua_nodes, configure_opcua_server,
    )

Usage:
    # domain/nodes/tank.py - a plain data class, NOT scanned into DI
    from xime.adapters.opcua import node_model, Node

    @node_model
    class Tank:
        level:    float = Node("ns=2;s=Tank.Level")
        setpoint: float = Node("ns=2;s=Tank.Setpoint")

    # api/opcua/tank_monitor.py
    from xime.adapters.opcua import on_node_change

    class TankMonitor:
        def __init__(self, alerts: AlertService) -> None:
            self._alerts = alerts

        @on_node_change(Tank.level, deadband=0.5)
        async def level_changed(self, value: float) -> None:
            await self._alerts.record(value)

    # config/opcua.py
    from xime.adapters.opcua import configure_opcua_nodes
    configure_opcua_nodes("api.opcua")

    # config/dependency.py
    dependency.scan("api.opcua")
    dependency.register(OpcuaClient)

Requires the extra: pip install 'xime[opcua]'
"""

from ._adapter import OpcuaAdapter
from ._client import OpcuaClient
from ._config import (
    DEFAULT_SERVER,
    OpcuaConfig,
    OpcuaServerConfig,
    configure_opcua_nodes,
    configure_opcua_server,
    opcua_registry,
)
from ._decorators import on_node_change, on_node_write, serve_nodes
from ._errors import OpcuaConnectionError, OpcuaError, OpcuaNodeError
from ._model import (
    Node,
    NodeModelInfo,
    OpcuaNode,
    get_node_model_info,
    node_model,
    require_node_model_info,
)
from ._runtime import OpcuaConnection
from ._security import SECURITY_MODES, build_security_string, normalize_mode
from ._server import OpcuaServerAdapter

__all__ = [
    # node model
    "node_model",
    "Node",
    "OpcuaNode",
    "NodeModelInfo",
    "get_node_model_info",
    "require_node_model_info",
    # handlers
    "on_node_change",
    "serve_nodes",
    "on_node_write",
    # client & adapters
    "OpcuaAdapter",
    "OpcuaServerAdapter",
    "OpcuaClient",
    "OpcuaConnection",
    # configuration
    "configure_opcua_nodes",
    "configure_opcua_server",
    "OpcuaConfig",
    "OpcuaServerConfig",
    "opcua_registry",
    "DEFAULT_SERVER",
    # security
    "SECURITY_MODES",
    "normalize_mode",
    "build_security_string",
    # errors
    "OpcuaError",
    "OpcuaConnectionError",
    "OpcuaNodeError",
]
