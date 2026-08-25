# OPC UA Adapter

**English** | [Tiếng Việt](../vn/opcua.md)

[← Modbus Adapter](modbus.md) · **OPC UA Adapter** · [File Storage →](file-storage.md)

---

The OPC UA adapter lets XIME act as a **client** (read, write, subscribe) and as a **server** (publishing nodes to other systems) for the most modern industrial protocol.

Compared with Modbus, OPC UA already carries types, names and **real subscriptions**. So this adapter is thinner at the data layer (nothing to decode) and does **no polling** - the server pushes when a value changes.

> **Requires:** `pip install "xime[opcua]"` (pulls in `asyncua>=2.0`).

---

## Quick start

### 1. Declare a node model

```python
# domain/nodes/tank.py   (a "DTO" - NOT in a DI-scanned package)
from xime.adapters.opcua import node_model, Node

@node_model
class Tank:
    level:    float = Node("ns=2;s=Tank.Level")
    setpoint: float = Node("ns=2;s=Tank.Setpoint")
    alarm:    bool  = Node("ns=2;s=Tank.Alarm", writable=False)
```

The model here is **not for decoding** (OPC UA already carries types) but for **naming** NodeIds - turning `client.get_node("ns=2;s=Tank.Level")` scattered through the code into `Tank.level` declared once.

### 2. Configure

```yaml
# resources/application.yml
opcua:
  endpoint: opc.tcp://10.0.0.6:4840
  security: SignAndEncrypt
  certificate: /etc/xime/opcua-client.der
  private_key: /etc/xime/opcua-client.pem
  application_uri: urn:my-plant:xime:client  # matches the cert's SAN URI
  username: svc
  password: secret
```

### 3. Read and write

```python
from xime.adapters.opcua import OpcuaClient

class TankService:
    def __init__(self, opcua: OpcuaClient) -> None:
        self._opcua = opcua

    async def level(self) -> float:
        return await self._opcua.read("ns=2;s=Tank.Level")

    async def snapshot(self) -> Tank:
        return await self._opcua.read_model(Tank)      # ONE request for every node

    async def set_target(self, value: float) -> None:
        await self._opcua.write(Tank.setpoint, value)
```

```python
# config/dependency.py
dependency.register(OpcuaClient)

# main.py
app.use(OpcuaAdapter())
```

`read_model` batches every node into **one** request. That matters more than it looks: OPC UA round trips carry real latency, and reading ten nodes one at a time is ten times the wait for no benefit.

---

## Subscriptions: `@on_node_change`

```python
# api/opcua/tank_monitor.py
from xime.adapters.opcua import on_node_change

class TankMonitor:
    def __init__(self, alerts: AlertService) -> None:
        self._alerts = alerts

    @on_node_change(Tank.level, deadband=0.5)
    async def level_changed(self, value: float) -> None:
        await self._alerts.record(value)

    @on_node_change(Tank.alarm, initial=True)
    async def alarm_changed(self, value: bool) -> None:
        await self._alerts.set_alarm(value)
```

```python
# config/opcua.py
from xime.adapters.opcua import configure_opcua_nodes
configure_opcua_nodes("my_service.api.opcua")

# config/dependency.py
dependency.scan("my_service.api.opcua")
```

Things worth knowing:

- **There is no `interval`.** The server pushes on change; `opcua.subscription_period` (default 200 ms) is only how often the server batches notifications.
- **The first value is only a baseline.** OPC UA delivers the current value the moment you subscribe. By default XIME does **not** treat that as a change - the same rule as Modbus `@on_change`, so handlers do not shout at every startup. Set `initial=True` when the handler genuinely wants the state at startup.
- **`deadband`** works exactly as in Modbus: reported only once the value moved by **more** than the deadband.
- **Handlers run in their own tasks.** `asyncua` delivers notifications through a **synchronous** callback; awaiting there would block the library's receive loop and stall every other subscription.
- **A failing handler does not stop the subscription.**

### Knowing which server you are handling: the `server` parameter (0.8)

The mirror of Modbus's `device` parameter - see
[modbus.md](modbus.md#knowing-which-machine-you-are-handling-the-device-parameter-08)
for why **kind** and **instance** are separated. The word here is `server` because
that is OPC UA's own vocabulary:

```python
@on_node_change(Tank.level, deadband=0.5)
async def on_level(self, value: float, server: str) -> None:
    await self._store.save(server, value)
```

```python
for srv in opcua.servers_of("pump-station"):
    tank = await opcua.read_model(Tank, server=srv)
```

Matched **by name**; a second parameter under another name is a startup error.

⏭ **0.8 declares the signature only**; several connections per kind land in **0.8.1**.
⛔ **`@on_node_change(..., server=...)` is gone in 0.8** - a handler runs for every
instance of its kind.

---

## Security: all three levels

```yaml
opcua:
  security: SignAndEncrypt     # None | Sign | SignAndEncrypt
  certificate: /etc/xime/opcua-client.der
  private_key: /etc/xime/opcua-client.pem
  application_uri: urn:my-plant:xime:client   # must match the cert's SAN URI
```

| Level | Meaning | Use when |
| --- | --- | --- |
| `None` | no signing, no encryption | isolated machine network, **never** over anything routable |
| `Sign` | signed: tampering is detected, payload travels in clear | integrity matters, secrecy does not |
| `SignAndEncrypt` | signed and encrypted | the sensible default outside an isolated network |

Both `Sign` and `SignAndEncrypt` need a certificate and private key. Missing either **fails at startup** rather than silently falling back to an unprotected connection - a fallback would be the worst possible outcome for a setting whose entire purpose is protection.

The concrete policy is `Basic256Sha256`. A server configured for `Sign` still accepts a client bringing `SignAndEncrypt`: refusing **stronger** protection than required would be perverse.

### `application_uri` - the usual stumbling block once security is on

With `Sign` or `SignAndEncrypt`, the server compares the URI a client declares when opening a session against the **URI inside the client certificate's SubjectAltName**. A mismatch is refused with `BadCertificateUriInvalid`, a message that never mentions the URI as the cause.

The underlying library defaults to its own URI (`urn:example.org:FreeOpcUa:opcua-asyncio`) and **never reads the URI out of the certificate**, so a certificate you generated yourself almost always needs this set:

```yaml
opcua:
  application_uri: urn:my-plant:xime:client   # exactly the URI used to issue the cert

  server:
    application_uri: urn:my-plant:xime:server
```

Leave it out to keep the library default - usable only when the certificate carries that same URI, or when `security: None`.

---

## Server mode: XIME publishing nodes

```python
# api/opcua/tank_emulator.py
from xime.adapters.opcua import serve_nodes, on_node_write

class TankEmulator:
    @serve_nodes(Tank)
    async def provide(self) -> Tank:
        return Tank(level=self._level)

    @on_node_write(Tank.setpoint)
    async def setpoint_written(self, value: float) -> None:
        self._setpoint = value
```

```yaml
opcua:
  server:
    endpoint: opc.tcp://0.0.0.0:4840/xime
    name: Xime OPC UA Server
    security: None
```

```python
from xime.adapters.opcua import OpcuaServerAdapter, configure_opcua_server

configure_opcua_server("my_service.api.opcua")
app.use(OpcuaServerAdapter())
```

Same split as the Modbus server: **values are pushed on a timer**, **writes arrive through a callback**.

One important rule: **a node with `@on_node_write` is owned by the CLIENT**, so the refresh loop never overwrites it. Overwriting would fight whoever just set the value, and would make every write notification ambiguous.

NodeIds are taken **verbatim** from the model, so a client using the same model class addresses exactly the nodes this server publishes.

> **`namespace` and the `ns=` index inside a NodeId are SEPARATE things.** `@node_model(namespace="http://...")` makes the server register that URI in its namespace table, but nodes are still created at exactly the `ns=` index written in the NodeId. The two can disagree with nothing reporting it. To land nodes in the namespace you registered, write the matching index into the NodeId yourself.

**A node's type must be knowable at startup.** An OPC UA variable takes its data type from the value it is created with and afterwards **refuses values of any other type**. XIME resolves the type in this order: an explicit `default=` first, then the annotation in the model (`running: bool = Node(...)`). With neither, startup **fails** naming the node - rather than creating a Double and letting the first publish die quietly with `BadTypeMismatch`.

Recognised types: `bool`, `int`, `float`, `str`, `bytes`. For anything else, pass `default=<initial value>`.

---

## Error handling

| Exception | Meaning |
| --- | --- |
| `OpcuaConnectionError` | the server is unreachable or the session dropped - retrying may help |
| `OpcuaNodeError` | the server answered and refused: unknown NodeId, wrong attribute, unreadable/unwritable node |

> **A detail worth knowing:** XIME reads through `read_attributes()` rather than `asyncua`'s `read_values()`. The latter throws away the per-node StatusCode, so a typo in a NodeId comes back as a **silent** `None` that looks exactly like a node holding no value. Checking the status turns that into an error naming the node.

NodeIds are also shape-checked at class definition: `Node("Tank.Level")` (missing `ns=`/`s=`) fails right there instead of surfacing as a `BadNodeId` at 3 a.m.

---

## Full configuration

```yaml
opcua:
  endpoint: opc.tcp://10.0.0.6:4840
  security: SignAndEncrypt
  certificate: /etc/xime/opcua-client.der
  private_key: /etc/xime/opcua-client.pem
  username: svc
  password: secret
  timeout: 4.0
  reconnect_delay: 3.0
  max_concurrency: 16
  subscription_period: 200        # ms
  servers:                        # only when talking to several servers
    plant_b:
      endpoint: opc.tcp://10.0.0.7:4840
      security: None
  server:                         # only when running OpcuaServerAdapter
    endpoint: opc.tcp://0.0.0.0:4840/xime
    name: Xime OPC UA Server
    security: None
```

A single-server application writes the settings directly under `opcua:`; a multi-server one nests them under `opcua.servers.<name>` and uses `app.use(OpcuaAdapter("plant_b"))`. ⚠ That argument is named `target_id` since 0.8 (it used to be `server`).

---

## Quick comparison with Modbus

| | Modbus | OPC UA |
| --- | --- | --- |
| Data types | none - the framework must decode | built into the protocol |
| Addressing | integers per area | NodeId strings |
| Change detection | XIME polls and compares | the server pushes (subscription) |
| Security | not in the protocol | None / Sign / SignAndEncrypt |
| Device support | almost everything, including very old gear | modern devices and SCADA |

The two adapters are fully independent with separate lazy imports. XIME deliberately does **not** abstract them into a common "fieldbus": their data models are too far apart.

---

[← Modbus Adapter](modbus.md) · **OPC UA Adapter** · [File Storage →](file-storage.md)
