# Modbus Adapter

**English** | [Tiếng Việt](../vn/modbus.md)

[← MQTT Adapter](mqtt.md) · **Modbus Adapter** · [OPC UA Adapter →](opcua.md)

---

The Modbus adapter lets XIME talk **directly** to PLCs, inverters, meters and other plant-floor devices - no edge gateway in between. It is XIME's **third interaction model**:

| Model | Adapter | Who initiates |
| --- | --- | --- |
| Request/response | web, gRPC, socket, MQTT `@rpc` | The outside calls into XIME |
| Pub/sub | MQTT `@subscribe` | The device pushes |
| **Polling / master** | **modbus** | **XIME actively reads the device** |

> **Requires:** `pip install "xime[modbus]"` (pulls in `pymodbus>=3.14`).

---

## The problem this adapter solves

Modbus carries **no type information**. Every read returns a raw array of 16-bit words. Turning that into `voltage = 220.5` means doing all of this yourself:

1. knowing which two consecutive registers to read,
2. joining two words into four bytes,
3. guessing the byte order right (big/little endian),
4. guessing the word order right (some vendors swap, some do not),
5. applying the scale factor from the datasheet.

Getting any step wrong **produces no error** - it produces a perfectly plausible number. That is the number-one source of bugs when talking to PLCs, and exactly what XIME's device model exists to eliminate.

---

## Quick start

### 1. Declare a device model

```python
# domain/devices/inverter.py   (a "DTO" - NOT in a DI-scanned package)
from xime.adapters.modbus import device, Holding, Input, Coil, Discrete

@device(unit=1)
class Inverter:
    voltage:    float = Holding(modicon=40001, type="float32", scale=0.1)
    current:    float = Holding(2, type="float32")
    setpoint:   int   = Holding(4, type="uint16")
    run_state:  bool  = Coil(0)
    fault_code: int   = Input(9, type="uint16")
    alarm:      bool  = Discrete(3)
```

### 2. Configure the devices

```yaml
# resources/application.yml
modbus:
  timeout: 3.0
  word_order: big
  max_gap: 8
  devices:
    inverter_1: { host: 10.0.0.5, port: 502, unit: 1 }
    meter_a:    { host: 10.0.0.6, unit: 3, timeout: 5.0 }
```

### 3. Read on demand

```python
from xime.adapters.modbus import ModbusClient

class TelemetryService:
    def __init__(self, modbus: ModbusClient) -> None:
        self._modbus = modbus

    async def snapshot(self) -> Inverter:
        return await self._modbus.read(Inverter)

    async def stop(self) -> None:
        await self._modbus.write(Inverter.run_state, False)
```

```python
# config/dependency.py
dependency.register(ModbusClient)
```

### 4. Run the adapter

```python
# main.py
app = Application()
app.use(WebAdapter()).use(ModbusAdapter("inverter_1"))
app.run()
```

---

## Addresses: two explicit entry points

Datasheets almost always use **Modicon** numbering (40001, 30010...) while the wire protocol uses **0-based offsets**. XIME never guesses - the two forms are two different parameters:

```python
Holding(2)              # protocol address, 0-based
Holding(modicon=40003)  # datasheet number -> the framework subtracts, giving 2
```

Why they are separate: if one parameter accepted both loosely, then on a device that really has more than 40002 registers, `Holding(40001)` would read **the wrong register with no error at all**.

Declaration fails immediately if you pass both, pass neither, or use a Modicon prefix that disagrees with the area (`Coil(modicon=40001)`).

| Area | Class | Modicon | Read function code | Writable |
| --- | --- | --- | --- | --- |
| Coil | `Coil` | 1-9999 | 1 | yes (5/15) |
| Discrete Input | `Discrete` | 10001-19999 | 2 | no |
| Input Register | `Input` | 30001-39999 | 4 | no |
| Holding Register | `Holding` | 40001-49999 | 3 | yes (6/16) |

The four areas are **four separate address spaces**: holding 0 and coil 0 are unrelated storage.

---

## Data types and value conversion

```python
Holding(0, type="float32", word_order="little", scale=0.1, offset=-40)
```

| Parameter | Meaning |
| --- | --- |
| `type` | `int16`/`uint16`/`int32`/`uint32`/`int64`/`uint64`/`float32`/`float64`/`string`/`bool` |
| `word_order` | word order for multi-register types; overrides the `@device` default |
| `byte_order` | byte order **inside** each register (the spec says big; some devices swap) |
| `scale` / `offset` | `value = raw * scale + offset`; encoding inverts it |
| `count` | register count for `string`, bit count for multi-bit coil/discrete fields |

Integer fields are **rounded** when written, not truncated - truncation would make a 220.5 round-trip through `scale=0.1` come back as 220.4.

`string` requires `count`: Modbus sends no length, so the framework cannot know where the text ends.

---

## How reads are planned

Modbus has exactly one read command: "give me N consecutive addresses starting at X". A model with scattered fields must be translated into several commands, and how that is done affects **correctness**, not just efficiency:

- Reading one big block from the lowest to the highest address is simpler, **but** if any address in between does not exist on the device, the slave answers `ILLEGAL DATA ADDRESS` and the **whole read fails** - even though every field you declared is valid. That is hard to diagnose, because both the model and the config look correct.
- So XIME groups fields by `max_gap`: fields closer than `max_gap` share one command, anything further apart is split.

```yaml
modbus:
  max_gap: 8     # 0 = read exactly the declared addresses (safest, most commands)
```

The planner also splits at the protocol ceilings (125 registers or 2000 bits per command), and **fails at startup** if a single field is larger than the ceiling (it cannot be split, since it has to be decoded as a whole).

Inspect the real plan while debugging:

```python
from xime.adapters.modbus import plan_reads, describe_plan, require_device_info

print(describe_plan(plan_reads(require_device_info(Inverter), max_gap=8)))
```

---

## Polling: `@poll` and `@on_change`

```python
# api/modbus/inverter_monitor.py
from xime.adapters.modbus import poll, on_change

class InverterMonitor:
    def __init__(self, alerts: AlertService) -> None:
        self._alerts = alerts

    @poll(Inverter, interval=1.0)
    async def on_sample(self, inverter: Inverter) -> None:
        await self._alerts.record(inverter.voltage)

    @on_change(Inverter.fault_code)
    async def on_fault(self, value: int) -> None:
        await self._alerts.raise_fault(value)

    @on_change(Inverter.voltage, deadband=0.5)
    async def on_voltage(self, value: float) -> None:
        await self._alerts.note(value)
```

```python
# config/modbus.py
from xime.adapters.modbus import configure_modbus_devices
configure_modbus_devices("api.modbus")

# config/dependency.py
dependency.scan("api.modbus")
```

Things worth knowing:

- **Grouping:** the adapter runs one loop per `(model, interval)` pair. Two handlers on the same model and cadence never cause two reads.
- **`@on_change` issues no request of its own**: it observes the value the poll loop already read. If a model is polled at several intervals, the watch joins the **fastest** loop.
- **The first reading is only a baseline**: `@on_change` does not fire on the first cycle. Firing there would mean every handler shouts at every startup - that is noise, not news.
- **`deadband` for analogue readings**: without it, last-digit sensor noise makes a float handler fire on nearly every cycle. A change is reported only once the value moved by **more** than the deadband.
- **The cadence does not drift**: the adapter subtracts the cycle time from the next sleep, so `interval=1.0` stays once per second however slow the device is.
- **Failures do not stop the loop**: a failed cycle is logged and polling continues. Devices on a plant floor drop off the network routinely; one bad reading must not kill the monitoring for the rest of the shift.
- **Bounded concurrency**: handlers run in tasks limited by `max_concurrency` (default 16), applying backpressure to the poll loop when saturated.

---

## Slave mode: XIME emulating a device

```python
# api/modbus/plc_emulator.py
from xime.adapters.modbus import serve, on_write

class PlcEmulator:
    @serve(Inverter)
    async def provide(self) -> Inverter:
        return Inverter(voltage=self._voltage, run_state=self._running)

    @on_write(Inverter.run_state)
    async def handle_command(self, value: bool) -> None:
        self._running = value
```

```yaml
modbus:
  server:
    host: 0.0.0.0
    port: 5020
```

```python
from xime.adapters.modbus import ModbusServerAdapter, configure_modbus_server

configure_modbus_server("api.modbus")
app.use(ModbusServerAdapter())
```

Two different mechanisms, for a reason:

- **Serving values is a push on a timer.** The framework calls `@serve` every `refresh` seconds and stores the result. Pulling on every master request would run business code inside the protocol reply path, where a slow handler stalls the answer.
- **Accepting writes is a hook.** There is no other moment to learn that a master wrote something.

Also:

- **Each `@device(unit=N)` becomes its own device.** One XIME process can present itself as several devices behind one port, the way an RTU gateway does.
- **Addresses outside the declared span stay undefined on purpose** - a master reading them gets `ILLEGAL DATA ADDRESS` instead of a plausible zero.
- `refresh_once()` is public: push an update immediately after something important changed instead of waiting for the next tick.

---

## Error handling

Three failure modes, kept apart because the right reaction differs:

| Exception | Meaning | What to do |
| --- | --- | --- |
| `ModbusConnectionError` | the device is unreachable (cable, switch, firewall, reboot) | retrying later usually helps |
| `ModbusDeviceError` | the device answered, and the answer was a refusal | retrying the **same** request fails again - the request or the model is wrong |
| `ModbusCodecError` | the bytes arrived but the model cannot make sense of them | always a code/model problem |

`ModbusDeviceError` keeps the raw `code` and expands it into words, because the number alone means nothing in a log:

```text
Modbus exception 2: ILLEGAL DATA ADDRESS - the address (or part of the range)
does not exist on this device (reading holding 5000+1)
```

---

## Full configuration

```yaml
modbus:
  # Defaults shared by every device; each device may override them.
  timeout: 3.0
  byte_order: big
  word_order: big
  reconnect_delay: 3.0
  max_concurrency: 16
  max_gap: 8
  devices:
    inverter_1:
      host: 10.0.0.5
      port: 502
      unit: 1
    meter_a:
      host: 10.0.0.6
      port: 502
      unit: 3
      timeout: 5.0
  server:              # only when running ModbusServerAdapter
    host: 0.0.0.0
    port: 5020
```

Devices are addressed by **logical name**, matching MQTT's `client_id` and gRPC/web's `server_id`. Re-cabling a plant means editing YAML, not code.

---

## Pitfalls

- **`app.use(ModbusAdapter(...))` is required**, even for on-demand reads only - the adapter owns the connection. Without it `ModbusClient` fails fast rather than hanging.
- **`unit` in `@device` is the model's default.** Three identical inverters at unit 1, 2, 3 share one model and pass `unit=` to `read`/`write`; do not inherit the model three times.
- **Overlapping addresses in one area are refused at class definition** - almost always a copy-paste slip that would otherwise make two attributes silently agree.
- **`pymodbus` below 3.14 will not work**: `pymodbus.payload.BinaryPayloadDecoder` was removed and the slave parameter was renamed to `device_id`.

---

[← MQTT Adapter](mqtt.md) · **Modbus Adapter** · [OPC UA Adapter →](opcua.md)
