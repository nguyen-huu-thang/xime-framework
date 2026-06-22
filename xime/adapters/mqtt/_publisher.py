from __future__ import annotations

from ._config import mqtt_registry

# Client id of the connection a default MqttPublisher binds to. Services running
# a single MQTT adapter use this; multi-server publishing can subclass and pass
# a different id (a future enhancement).
# client_id mặc định publisher bám vào.
_DEFAULT_CLIENT_ID = "default"


class MqttPublisher:
    """Injectable façade for publishing MQTT messages from business code.

    Register as a singleton in config/dependency.py:

        dependency.register(MqttPublisher)

    then inject it like any service:

        class AlertService:
            def __init__(self, publisher: MqttPublisher) -> None:
                self._publisher = publisher

            async def raise_alert(self) -> None:
                await self._publisher.publish("alerts/fire", b"1", qos=1, retain=True)

    The publisher holds no connection of its own: it delegates to the shared
    MqttConnection that MqttAdapter attaches its live client to. Publishing
    before the adapter has connected blocks until it does (or `timeout`).
    Publisher không giữ kết nối riêng - uỷ thác cho MqttConnection dùng chung.

    The framework imposes no payload format: pass raw bytes (or str). Encode
    JSON/protobuf in your code, consistent with the rest of Xime.
    """

    def __init__(self) -> None:
        self._connection = mqtt_registry.connection(_DEFAULT_CLIENT_ID)

    async def publish(
        self,
        topic: str,
        payload: bytes | str,
        *,
        qos: int = 0,
        retain: bool = False,
        timeout: float | None = None,
    ) -> None:
        """Publish `payload` to `topic`.

        Waits up to `timeout` seconds for a live connection (None = wait
        indefinitely); raises TimeoutError if it never connects in time.
        """
        await self._connection.publish(
            topic, payload, qos=qos, retain=retain, timeout=timeout
        )
