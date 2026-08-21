"""I1 - integration tests for the MQTT adapter against a REAL broker (MQTT v5).

Skipped unless `aiomqtt` is installed AND a broker is reachable. Point them at a
broker via env XIME_TEST_MQTT_HOST / XIME_TEST_MQTT_PORT (default 127.0.0.1:1883),
e.g. `docker run -p 1883:1883 eclipse-mosquitto` with anonymous access.
Bị skip trừ khi có `aiomqtt` VÀ broker chạy thật (cấu hình qua env).

These exercise the live paths that unit tests (fake client) cannot:
- MqttAdapter.start -> connect -> subscribe (with Subscription Identifier) ->
  receive loop -> dispatch (pub/sub + RPC), then stop().
- The MQTT v5 features the adapter relies on: Subscription Identifier echo (M4),
  RPC ResponseTopic + CorrelationData.
"""
import asyncio
import contextlib
import os
import socket

import pytest
from pydantic import BaseModel

aiomqtt = pytest.importorskip("aiomqtt")

from xime.adapters.mqtt import MqttAdapter, rpc, subscribe  # noqa: E402
from xime.adapters.mqtt.routing import _scanner as scanner_mod  # noqa: E402
from xime.core.config.runtime import RuntimeConfig  # noqa: E402

_HOST = os.environ.get("XIME_TEST_MQTT_HOST", "127.0.0.1")
_PORT = int(os.environ.get("XIME_TEST_MQTT_PORT", "1883"))


def _broker_reachable() -> bool:
    try:
        sock = socket.create_connection((_HOST, _PORT), 0.5)
        sock.close()
        return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.skipif(
        not _broker_reachable(), reason=f"no MQTT broker at {_HOST}:{_PORT}"
    ),
    pytest.mark.asyncio,
]


class Echo(BaseModel):
    msg: str


class _Ctrl:
    def __init__(self) -> None:
        self.seen: dict = {}
        self.got = asyncio.Event()

    @subscribe("xime/it/+/data", qos=1)
    async def on_data(self, payload: bytes, topic: str) -> None:
        self.seen["payload"] = payload
        self.seen["topic"] = topic
        self.got.set()

    @rpc("xime/it/echo")
    async def echo(self, request: Echo) -> Echo:
        return Echo(msg=request.msg.upper())


class _FakeApp:
    def __init__(self, runtime: RuntimeConfig, ctrl: _Ctrl) -> None:
        self._runtime = runtime
        self._ctrl = ctrl

    def get(self, cls):
        return self._runtime if cls is RuntimeConfig else self._ctrl


@contextlib.asynccontextmanager
async def _running_adapter(monkeypatch, ctrl: _Ctrl):
    # Bypass package scanning: feed the controller class directly.
    monkeypatch.setattr(
        scanner_mod.MqttControllerScanner, "find_controllers", lambda self, *p: [_Ctrl]
    )
    runtime = RuntimeConfig.from_dict({"mqtt": {"host": _HOST, "port": _PORT}})
    adapter = MqttAdapter("default")
    await adapter.start(_FakeApp(runtime, ctrl))
    task = asyncio.create_task(adapter.serve())
    try:
        await asyncio.sleep(0.7)  # allow connect + subscribe
        yield adapter
    finally:
        await adapter.stop()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task


async def test_pubsub_end_to_end(monkeypatch):
    ctrl = _Ctrl()
    async with _running_adapter(monkeypatch, ctrl):
        async with aiomqtt.Client(
            _HOST, port=_PORT, protocol=aiomqtt.ProtocolVersion.V5, identifier="xime-it-pub"
        ) as pub:
            await pub.publish("xime/it/sensorA/data", b"42", qos=1)
        async with asyncio.timeout(5):
            await ctrl.got.wait()
    assert ctrl.seen["payload"] == b"42"
    assert ctrl.seen["topic"] == "xime/it/sensorA/data"


async def test_rpc_round_trip(monkeypatch):
    from paho.mqtt.packettypes import PacketTypes
    from paho.mqtt.properties import Properties

    ctrl = _Ctrl()
    reply_topic = "xime/it/echo/reply"
    async with _running_adapter(monkeypatch, ctrl):
        async with aiomqtt.Client(
            _HOST, port=_PORT, protocol=aiomqtt.ProtocolVersion.V5, identifier="xime-it-rpc"
        ) as client:
            await client.subscribe(reply_topic, qos=1)
            props = Properties(PacketTypes.PUBLISH)
            props.ResponseTopic = reply_topic
            props.CorrelationData = b"corr-1"
            await client.publish(
                "xime/it/echo", b'{"msg": "hi"}', qos=1, properties=props
            )
            async with asyncio.timeout(5):
                async for msg in client.messages:
                    import json

                    assert json.loads(msg.payload) == {"msg": "HI"}
                    assert msg.properties.CorrelationData == b"corr-1"
                    break
