"""MqttPublisher + MqttConnection: attach/detach, wait-for-connection, timeout,
fail-fast khi không adapter nào phục vụ client_id (0.5)."""
import asyncio

import pytest

from xime.adapters.mqtt import MqttPublisher
from xime.adapters.mqtt._config import mqtt_registry


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def publish(self, topic, payload, *, qos=0, retain=False, properties=None):
        self.calls.append({"topic": topic, "payload": payload, "qos": qos, "retain": retain})


class TestPublisher:
    @pytest.mark.asyncio
    async def test_publish_after_attach(self):
        publisher = MqttPublisher()  # binds to the "default" connection
        client = _FakeClient()
        conn = mqtt_registry.connection("default")
        conn.mark_served()  # an adapter serves this client_id
        conn.attach(client)

        await publisher.publish("alerts/x", b"1", qos=1, retain=True)
        assert client.calls == [
            {"topic": "alerts/x", "payload": b"1", "qos": 1, "retain": True}
        ]

    @pytest.mark.asyncio
    async def test_publish_waits_for_connection(self):
        publisher = MqttPublisher()
        conn = mqtt_registry.connection("default")
        conn.mark_served()  # adapter exists but is (re)connecting
        client = _FakeClient()

        async def attach_later():
            await asyncio.sleep(0.02)
            conn.attach(client)

        # publish blocks until attach happens, then proceeds.
        await asyncio.gather(publisher.publish("t", b"p"), attach_later())
        assert client.calls and client.calls[0]["topic"] == "t"

    @pytest.mark.asyncio
    async def test_publish_timeout_when_served_but_never_connects(self):
        publisher = MqttPublisher()
        mqtt_registry.connection("default").mark_served()  # adapter exists, broker down
        with pytest.raises(TimeoutError):
            await publisher.publish("t", b"p", timeout=0.01)

    @pytest.mark.asyncio
    async def test_publish_fails_fast_when_no_adapter_serves_client_id(self):
        # No adapter ever claimed "default" -> publishing must raise immediately
        # instead of blocking forever (default timeout=None).
        publisher = MqttPublisher()
        with pytest.raises(RuntimeError, match="No MqttAdapter serves"):
            await publisher.publish("t", b"p")


class TestConnection:
    @pytest.mark.asyncio
    async def test_detach_blocks_again(self):
        conn = mqtt_registry.connection("default")
        conn.mark_served()
        client = _FakeClient()
        conn.attach(client)
        assert conn.is_connected is True
        conn.detach()
        assert conn.is_connected is False
        with pytest.raises(TimeoutError):
            await conn.publish("t", b"p", timeout=0.01)

    @pytest.mark.asyncio
    async def test_unserved_connection_fails_fast(self):
        conn = mqtt_registry.connection("orphan")
        assert conn.is_served is False
        with pytest.raises(RuntimeError, match="No MqttAdapter serves"):
            await conn.publish("t", b"p")
