# MQTT Adapter

**English** | [Tiếng Việt](../vn/mqtt.md)

[← Socket Adapter](socket-adapter.md) · **MQTT Adapter** · [File Storage →](file-storage.md)

---

The MQTT Adapter adds a **message-driven** transport to XIME for IoT / embedded peers. Unlike the HTTP, gRPC, and Socket adapters (request/response), MQTT is **publish/subscribe**: the adapter subscribes to the topic filters your controllers declare and dispatches each incoming message. On top of plain pub/sub it also supports **RPC over MQTT v5** (request/reply via `ResponseTopic` + `CorrelationData`).

```text
Devices / sensors ──publish──►  MQTT Broker  ──deliver──►  XIME (@subscribe / @rpc)
XIME (MqttPublisher) ─────────► MQTT Broker  ──────────►  Devices
```

> **Requirements:** an MQTT **v5** broker (e.g. Mosquitto, EMQX, HiveMQ). Install the extra first: `pip install "xime[mqtt]"` (pulls `aiomqtt`). MQTT v5 is required for RPC (`ResponseTopic` / `CorrelationData`) and for the Subscription Identifier routing described below.

---

## When to Use

| Use MQTT | Use gRPC / HTTP / Socket |
| --- | --- |
| IoT / embedded devices, telemetry | Service-to-service RPC |
| Fan-out pub/sub, many publishers | Point-to-point request/response |
| Unreliable / intermittent connectivity | Stable internal network |
| Lightweight devices behind a broker | Browser / public API clients |

---

## Quick Start

### 1. Write the controller

A controller is a plain class; `@subscribe` marks a fire-and-forget handler, `@rpc` marks a request/reply handler.

```python
# api/mqtt/sensor_controller.py
from pydantic import BaseModel
from xime.adapters.mqtt import subscribe, rpc

class CalibrateRequest(BaseModel):
    sensor_id: str
    offset: float

class CalibrateResponse(BaseModel):
    ok: bool

class SensorController:
    def __init__(self, ingest: IngestService) -> None:
        self._ingest = ingest

    @subscribe("sensors/+/temperature", qos=1)
    async def on_temperature(self, payload: bytes, topic: str) -> None:
        await self._ingest.record(topic, payload)

    @rpc("sensors/calibrate")
    async def calibrate(self, request: CalibrateRequest) -> CalibrateResponse:
        return await self._ingest.calibrate(request)
```

### 2. Register the package

```python
# config/mqtt.py
from xime.adapters.mqtt import configure_mqtt_controllers

configure_mqtt_controllers("api.mqtt")
```

Also add `api.mqtt` to `dependency.scan(...)` in `config/dependency.py` so the DI container creates the controller instance.

### 3. Add the adapter (and the publisher, if you publish)

```python
# main.py
from xime import Application
from xime.adapters.mqtt import MqttAdapter

app = Application()
app.use(MqttAdapter())     # client_id "default"; reads the mqtt: block from application.yml
app.run()
```

```python
# config/dependency.py — only if business code publishes
from xime.adapters.mqtt import MqttPublisher

dependency.register(MqttPublisher)
```

---

## Handler Types

### `@subscribe` — fire-and-forget (pub/sub)

The handler receives the **raw** message; the framework does NOT deserialize the payload (consistent with `StorageService` / `CacheService`: mechanism, not policy). Declare only the parameters you need - matched **by name**, all optional:

| Parameter | Type | Value |
| --- | --- | --- |
| `payload` | `bytes` | the raw message body |
| `topic` | `str` | the concrete topic the message arrived on |
| `message` | `Any` | the underlying `aiomqtt` message object |

```python
@subscribe("alerts/#", qos=1)
async def on_alert(self, payload: bytes, topic: str) -> None:
    ...
```

### `@rpc` — request/reply over MQTT v5

The handler takes a Pydantic **request** model and returns a Pydantic **response** model. The adapter decodes the request payload as JSON, calls the handler, and publishes the JSON-encoded response to the request's `ResponseTopic` with the same `CorrelationData`. An optional `topic: str` parameter is also injected if declared.

```python
@rpc("svc/echo")
async def echo(self, request: EchoRequest) -> EchoResponse:
    return EchoResponse(text=request.text.upper())
```

A caller publishes the request with MQTT v5 `ResponseTopic` + `CorrelationData` properties and subscribes to that reply topic. If no `ResponseTopic` is present, the handler still runs but no reply is sent.

Startup validation (fail-fast): handlers must be `async def`; the topic filter must be valid; `qos` must be 0/1/2; `@rpc` request/response must be `BaseModel`; the same exact filter must not be declared twice (see *Overlapping filters* below).

---

## Publishing

Inject `MqttPublisher` and call `publish`:

```python
from xime.adapters.mqtt import MqttPublisher

class AlertService:
    def __init__(self, publisher: MqttPublisher) -> None:
        self._publisher = publisher

    async def raise_alert(self) -> None:
        await self._publisher.publish("alerts/fire", b"1", qos=1, retain=True)
```

The publisher holds no connection of its own - it delegates to the live client the `MqttAdapter` owns. Publishing before the adapter has connected **waits** until it connects (or the optional `timeout`). The framework imposes no payload format: pass raw `bytes` (or `str`); encode JSON/protobuf yourself.

> **The publisher binds to the `"default"` client_id.** If you run the adapter under a different id (`MqttAdapter("sensors")`) and inject a plain `MqttPublisher`, publishing raises a clear `RuntimeError` instead of hanging forever. Run the adapter with the default id for the publisher to work.

---

## Configuration — `application.yml`

```yaml
mqtt:
  host: broker.local        # required - missing it fails fast at startup
  port: 1883
  username: svc             # optional
  password: secret          # optional
  client_id: data-service   # optional - defaults to the adapter's id
  keepalive: 60
  default_qos: 0
  max_concurrency: 16       # in-flight message handlers (see Ordering)
  reconnect_delay: 3.0      # seconds between reconnect attempts
  tls:                      # optional
    ca_certs: /etc/ssl/ca.pem
    certfile: /etc/ssl/client.pem
    keyfile:  /etc/ssl/client.key
  lwt:                      # optional - Last Will & Testament
    topic: status/data-service
    payload: offline
    qos: 1
    retain: true
```

---

## Message Ordering & Concurrency

Each message is dispatched in a bounded-concurrency task. With `max_concurrency > 1`, messages are processed **concurrently**, so per-topic delivery order is **not** preserved. Set `max_concurrency: 1` for strict sequential, in-order processing (lower throughput). When the limit is saturated, the receive loop applies backpressure.

---

## Overlapping Filters & Subscription Identifiers

The adapter assigns each route a unique **MQTT v5 Subscription Identifier** and subscribes with it; on each delivery the broker reports which subscription matched, so the dispatcher routes to exactly the right handler(s). This means **overlapping** filters (e.g. `sensors/#` and `sensors/+/temp`) each fire once - no double-dispatch.

Because subscribing the **same exact** filter twice makes a broker *replace* the earlier subscription (only the last identifier survives), two handlers on an **identical** filter are rejected at startup. Use distinct/overlapping filters - the dispatcher fans out to all matching routes - or merge the handlers.

Leading wildcards (`#` / `+`) do not match broker system topics (`$SYS/...`), per the MQTT spec.

---

## Resilience

On connection loss the adapter reconnects and **re-subscribes** all topics automatically (interval = `reconnect_delay`). In-flight handler tasks are cancelled on shutdown; the connection is dropped cleanly.

---

## Error Mapping (RPC)

Map business exceptions to error codes returned to the caller on the reply topic:

```python
# config/mqtt.py
from xime.adapters.mqtt import configure_mqtt_error_mappings

configure_mqtt_error_mappings({
    NotFoundException:   "NOT_FOUND",
    ValidationException: "INVALID_ARGUMENT",
})
```

On an RPC error the adapter publishes `{"error": {"code": ..., "message": ...}}` to the `ResponseTopic`. Unmapped exceptions become `INTERNAL` with a generic message, so internal details never leak - mirroring the gRPC / Socket error policy. A failing handler is logged and never stops the dispatch loop.

---

## Installation

```bash
pip install "xime[mqtt]"   # adds aiomqtt (which pulls paho-mqtt)
```

---

[← Socket Adapter](socket-adapter.md) · **MQTT Adapter** · [File Storage →](file-storage.md)
