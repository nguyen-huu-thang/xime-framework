from __future__ import annotations

import asyncio
from typing import Any


class MqttConnection:
    """Shared holder for the live aiomqtt client of one MQTT server.

    Bridges the adapter (which owns the connection lifecycle) and the publisher
    (a DI singleton used by business code). The adapter calls attach() once
    connected and detach() on disconnect/reconnect; publish() waits until a
    client is attached, then delegates.
    Cầu nối giữa adapter (sở hữu kết nối) và publisher (singleton DI): adapter
    attach() khi kết nối, detach() khi mất; publish() chờ tới khi có client.

    One instance per client_id, owned by the mqtt registry so both the adapter
    and the publisher resolve the same object.
    """

    def __init__(self, client_id: str) -> None:
        self._client_id = client_id
        self._client: Any = None
        self._connected = asyncio.Event()
        # True once an MqttAdapter has claimed this client_id (in its __init__).
        # If no adapter ever claims it, a publisher bound here would block
        # forever waiting for a connection that never arrives -> fail fast.
        # True khi đã có MqttAdapter nhận client_id này. Không adapter nào nhận thì
        # publisher bám vào đây sẽ chờ vô hạn -> phải fail fast.
        self._served = False

    @property
    def client_id(self) -> str:
        return self._client_id

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    @property
    def is_served(self) -> bool:
        """True if an MqttAdapter manages this connection's client_id."""
        return self._served

    def mark_served(self) -> None:
        """Called by MqttAdapter (at construction) to claim this client_id."""
        self._served = True

    def attach(self, client: Any) -> None:
        """Bind the live client and mark the connection ready."""
        self._client = client
        self._connected.set()

    def detach(self) -> None:
        """Drop the client reference; publishers will block until re-attached."""
        self._client = None
        self._connected.clear()

    async def publish(
        self,
        topic: str,
        payload: bytes | str,
        *,
        qos: int = 0,
        retain: bool = False,
        timeout: float | None = None,
        properties: Any = None,
    ) -> None:
        """Publish a message, waiting up to `timeout` for a live connection.

        Raises TimeoutError if no client is attached within `timeout` (None =
        wait indefinitely). This lets business code publish during a transient
        reconnect without crashing.
        Chờ tối đa timeout giây để có kết nối; quá hạn -> TimeoutError.

        Raises RuntimeError immediately when no MqttAdapter serves this
        client_id - otherwise a default (timeout=None) publish would hang
        forever waiting for a connection that will never arrive.
        Nếu không adapter nào phục vụ client_id này -> RuntimeError ngay, tránh
        publish (timeout=None) treo vô hạn.
        """
        if not self._connected.is_set():
            if not self._served:
                raise RuntimeError(
                    f"No MqttAdapter serves MQTT client_id '{self._client_id}', so "
                    "this publish would block forever. Register the adapter with a "
                    f"matching id, e.g. app.use(MqttAdapter('{self._client_id}')), "
                    "or publish through the connection of the adapter you did register."
                )
            if timeout is None:
                await self._connected.wait()
            else:
                await asyncio.wait_for(self._connected.wait(), timeout)
        client = self._client
        if client is None:  # detached between the wait and here
            raise ConnectionError(
                f"MQTT connection '{self._client_id}' is not available"
            )
        await client.publish(topic, payload, qos=qos, retain=retain, properties=properties)
