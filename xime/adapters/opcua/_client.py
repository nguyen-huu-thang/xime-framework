"""Injectable façade for reading and writing OPC UA nodes.

    class TankService:
        def __init__(self, opcua: OpcuaClient) -> None:
            self._opcua = opcua

        async def level(self) -> float:
            return await self._opcua.read("ns=2;s=Tank.Level")

        async def snapshot(self) -> Tank:
            return await self._opcua.read_model(Tank)

        async def set_target(self, value: float) -> None:
            await self._opcua.write(Tank.setpoint, value)

Register it as a singleton in config/dependency.py:

    dependency.register(OpcuaClient)
"""

from __future__ import annotations

from typing import Any, TypeVar

from ._config import DEFAULT_SERVER, OpcuaConfig, opcua_registry
from ._errors import OpcuaNodeError
from ._model import OpcuaNode, require_node_model_info

T = TypeVar("T")


class OpcuaClient:
    """Read and write nodes over the shared connection(s)."""

    # `server` has a default, so the container treats it as optional - see the
    # same note on ModbusClient.__init__.
    def __init__(self, server: str = DEFAULT_SERVER) -> None:
        self._default_server = server

    def servers_of(self, kind: str | None = None) -> list[str]:
        """Every entity of `kind` this process holds, in configuration order.

            for srv in opcua.servers_of("tram-bom"):
                tank = await opcua.read_model(Tank, server=srv)

        Đối xứng với `ModbusClient.devices_of` - đọc phần giải thích *loại* và
        *thực thể* ở đó (thiết kế 5.7.3). Khác đúng một chỗ: **từ vựng**. OPC UA
        nói *server*, Modbus nói *device*, và mỗi adapter giữ chữ của miền nó vì
        cái tên ở đây nói về **thứ thật ngoài kia**, không nói về framework.

        ⏭ **0.8 mới khai chữ ký; phần dựng N kết nối lùi sang một bản 0.8.x, chưa chốt.**
        """
        name = kind or self._default_server
        connection = opcua_registry.connection(name)
        return [name] if connection.is_served else []

    async def read(self, node_id: str, *, server: str | None = None) -> Any:
        """Read a single node by its raw NodeId string."""
        values = await self._connection(server).read_values(
            [node_id], timeout=self._config(server).timeout
        )
        return values[0]

    async def read_node(self, node: OpcuaNode, *, server: str | None = None) -> Any:
        """Read one declared node, e.g. `await opcua.read_node(Tank.level)`."""
        return await self.read(_node_id_of(node), server=server)

    async def read_model(self, model: type[T], *, server: str | None = None) -> T:
        """Read every node of a model in ONE request and return an instance."""
        info = require_node_model_info(model)
        names = list(info.nodes)
        values = await self._connection(server).read_values(
            [info.nodes[name].node_id for name in names],
            timeout=self._config(server).timeout,
        )
        instance: Any = object.__new__(info.cls)
        for name, value in zip(names, values):
            setattr(instance, name, value)
        return instance  # type: ignore[return-value]

    async def write(
        self, node: OpcuaNode | str, value: Any, *, server: str | None = None
    ) -> None:
        """Write one node, given either a declared node or a NodeId string."""
        if isinstance(node, OpcuaNode) and not node.writable:
            raise OpcuaNodeError(
                f"node '{node.name}' is declared writable=False. Change the "
                f"model if the server really does accept writes to it."
            )
        await self._connection(server).write_value(
            _node_id_of(node), value, timeout=self._config(server).timeout
        )

    async def write_model(self, instance: Any, *, server: str | None = None) -> None:
        """Write every writable node of a model instance that holds a value.

        Nodes left as None are skipped, so a partially filled instance updates
        only what it names.
        """
        info = require_node_model_info(instance)
        for name, node in info.nodes.items():
            if not node.writable:
                continue
            value = getattr(instance, name, None)
            if value is None:
                continue
            await self.write(node, value, server=server)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _connection(self, server: str | None):
        return opcua_registry.connection(server or self._default_server)

    def _config(self, server: str | None) -> OpcuaConfig:
        name = server or self._default_server
        config = _resolved_configs.get(name)
        if config is None:
            config = OpcuaConfig(name=name, endpoint="")
        return config


def _node_id_of(node: OpcuaNode | str) -> str:
    if isinstance(node, OpcuaNode):
        return node.node_id
    if isinstance(node, str):
        return node
    raise OpcuaNodeError(
        f"expected a NodeId string or a model node (e.g. Tank.level), got "
        f"{type(node).__name__}"
    )


# Configs resolved by OpcuaAdapter at startup, keyed by server name.
_resolved_configs: dict[str, OpcuaConfig] = {}


def register_resolved_config(config: OpcuaConfig) -> None:
    """Called by OpcuaAdapter.start() once the runtime config is available."""
    _resolved_configs[config.name] = config


def clear_resolved_configs() -> None:
    """Test cleanup only."""
    _resolved_configs.clear()
