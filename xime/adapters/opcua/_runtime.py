"""The shared, live connection to one named OPC UA server.

Same role as ModbusConnection and MqttConnection: the adapter owns the
lifecycle, the injectable client borrows it. This is the only module that
touches asyncua client objects, so everything above it works in plain values.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ._errors import OpcuaConnectionError, OpcuaNodeError


class OpcuaConnection:
    """Holder for the live asyncua client of one server name."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._client: Any = None
        self._connected = asyncio.Event()
        self._served = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    @property
    def is_served(self) -> bool:
        return self._served

    def mark_served(self) -> None:
        """Called by OpcuaAdapter at construction to claim this server name."""
        self._served = True

    def attach(self, client: Any) -> None:
        self._client = client
        self._connected.set()

    def detach(self) -> None:
        self._client = None
        self._connected.clear()

    # ------------------------------------------------------------------
    # Requests
    # ------------------------------------------------------------------

    async def read_values(
        self, node_ids: list[str], *, timeout: float | None = None
    ) -> list[Any]:
        """Read several nodes in ONE request, checking each node's status.

        Batching matters more here than it looks: OPC UA round trips carry real
        latency, and a model with ten nodes read one at a time is ten times the
        wait for no benefit.
        Gộp nhiều node vào MỘT request - đọc lẻ từng node là nhân độ trễ lên
        đúng bằng số node.

        This deliberately uses read_attributes() rather than asyncua's
        read_values(): the latter throws the per-node StatusCode away, so a
        typo in a NodeId comes back as a silent None that looks exactly like a
        node holding no value. Reading the status turns that into an error
        naming the node.
        Dùng read_attributes() chứ KHÔNG dùng read_values() của asyncua: hàm đó
        vứt StatusCode từng node, nên gõ sai NodeId trả về None im lặng - trông
        y hệt node chưa có giá trị.
        """
        from asyncua import ua

        client = await self._require_client(timeout)
        nodes = [client.get_node(node_id) for node_id in node_ids]
        try:
            results = await client.read_attributes(nodes, ua.AttributeIds.Value)
        except Exception as exc:
            raise _translate(exc, f"reading {node_ids}", self._name) from exc

        values: list[Any] = []
        for node_id, data_value in zip(node_ids, results):
            status = data_value.StatusCode
            if status is not None and not status.is_good():
                raise OpcuaNodeError(
                    f"OPC UA server '{self._name}' refused node '{node_id}': "
                    f"{status.name}"
                )
            values.append(data_value.Value.Value if data_value.Value else None)
        return values

    async def write_value(
        self, node_id: str, value: Any, *, timeout: float | None = None
    ) -> None:
        client = await self._require_client(timeout)
        node = client.get_node(node_id)
        try:
            await node.write_value(value)
        except Exception as exc:
            raise _translate(exc, f"writing {node_id}", self._name) from exc

    async def create_subscription(self, period_ms: float, handler: Any) -> Any:
        client = await self._require_client(None)
        try:
            return await client.create_subscription(period_ms, handler)
        except Exception as exc:
            raise _translate(exc, "creating a subscription", self._name) from exc

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _require_client(self, timeout: float | None) -> Any:
        if not self._connected.is_set():
            if not self._served:
                raise OpcuaConnectionError(
                    f"No OpcuaAdapter serves server '{self._name}', so this "
                    f"request would block forever. Register the adapter, e.g. "
                    f"app.use(OpcuaAdapter('{self._name}'))."
                )
            if timeout is None:
                await self._connected.wait()
            else:
                try:
                    await asyncio.wait_for(self._connected.wait(), timeout)
                except TimeoutError:
                    raise OpcuaConnectionError(
                        f"Timed out after {timeout}s waiting for OPC UA server "
                        f"'{self._name}' to connect."
                    ) from None
        client = self._client
        if client is None:
            raise OpcuaConnectionError(
                f"OPC UA connection '{self._name}' is not available"
            )
        return client


def _translate(exc: Exception, what: str, server: str) -> Exception:
    """Sort an asyncua failure into 'the node is wrong' vs 'the link is down'.

    The distinction is what tells an operator whether to check the cable or the
    NodeId, so it is worth making rather than raising one vague error.
    Phân biệt để người vận hành biết nên kiểm dây mạng hay kiểm NodeId.
    """
    text = str(exc)
    marker = type(exc).__name__ + text
    if "BadNodeId" in marker or "BadAttributeId" in marker or "BadNotReadable" in marker:
        return OpcuaNodeError(f"OPC UA rejected {what} on '{server}': {exc}")
    return OpcuaConnectionError(f"OPC UA failed {what} on '{server}': {exc}")
