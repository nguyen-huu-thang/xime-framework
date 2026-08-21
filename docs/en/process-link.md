# Inter-process Bus (ProcessLink)

**English** | [Tiếng Việt](../vn/process-link.md)

[← RefData](refdata.md) · **ProcessLink** · [Multi-process →](multi-process.md)

---

Once an application runs several processes, some things cannot be solved with
shared data. The classic case: a user presses *"stop conveyor BT-02"* in the web UI,
the request lands in process `main`, but the Modbus wire to BT-02 belongs to
process `line-2`. That is a **command**, not a piece of data - writing it to a
database does not stop the conveyor.

`ProcessLink` carries exactly that: **signals, commands and questions** between
the processes of one application, on one machine.

---

## ⚠ It is NOT `EventBus`

This is the easiest thing to confuse here, and confusing them has **no
symptom**: the message never leaves the process, no error, no log.

| | `EventBus` (`xime.core.event`) | **`ProcessLink`** |
|---|---|---|
| Scope | within **ONE** process | **BETWEEN** processes |
| Carries | Python objects, no serialisation | **bytes** |
| Carries what kind | **events** - already happened, whoever cares listens | **commands and questions** - addressed, may await an answer |
| Reply | none | **yes** (`ask`) |
| Handlers run | concurrently (`create_task`) | **sequentially per channel** |
| Registration | `subscribe(Type, handler)` | `@on_announce` / `@on_request` |

The names deliberately share no root: `link.ask(...)` and
`event_bus.publish(...)` cannot be typed for one another by accident.

> **A practical boundary: if it does not fit in 4 KB it is DATA, not a signal.**
> Data goes through the [Store](store.md) or a database; the bus carries signals.

---

## Declaring channels and handlers

```python
# config/link.py
from xime.core.link import ChannelSpec, configure_link

from app.link.fieldbus import FieldbusHandler

configure_link(
    channels={
        "fieldbus": ChannelSpec(rows=256, payload_bytes=512),
        "config":   ChannelSpec(rows=64,  payload_bytes=4096),
    },
    handlers=[FieldbusHandler],
)
```

```python
# app/link/fieldbus.py
from xime.core.link import on_announce, on_request


class FieldbusHandler:
    def __init__(self, modbus: ModbusClient, cfg: RuntimeConfig) -> None:
        self._modbus = modbus
        self._mine = cfg.get("...")          # keys come from CONFIGURATION

    @on_request("fieldbus")
    async def control(self, key: str, payload: bytes) -> bytes | None:
        if key not in self._mine:
            return None                      # never touched the payload
        await self._modbus.write(..., device=key)
        return b"ok"

    @on_announce("config")
    async def config_changed(self, key: str, payload: bytes) -> None:
        ...
```

Four deliberate details:

| | |
|---|---|
| **`handlers=` takes CLASSES** | The framework resolves them from DI, so a handler is injected like anything else. Same shape as `configure_jwt(key_provider=...)` |
| **Channels and handlers are declared separately** | One handler may serve several channels, and a channel may exist only to **send** |
| **`channels` must match in every process** | The memory is shared. That holds automatically because `config/` is imported identically everywhere - but the framework still verifies it on attach |
| **Sizes are declared in Python, not YAML** | Choosing row count and payload size requires knowing *how long handlers run* and *how large messages are* - two things an operator does not know |

---

## Three ways to send

Split by **what the sender needs to know**, not by how many receivers exist.

```python
await link.announce("config", payload=b"keys rotated")          # to everyone
await link.send("fieldbus", key="BT-01", payload=b"stop")       # addressed, no wait
result = await link.ask("fieldbus", key="BT-01", payload=b"stop", timeout=2.0)
```

### The four outcomes of `ask`

```python
match await link.ask("fieldbus", key="BT-01", payload=b"stop"):
    case Done(value):    ...   # a handler took it and answered
    case NoOwner():      ...   # NOBODY took it -> a CONFIGURATION error, do not retry
    case NoAnswer():     ...   # taken but overdue -> check whether that process is alive
    case Failed(detail): ...   # taken, and that handler FAILED -> a business error
```

Four situations that make the caller do **four different things**, so they must
be four values. Folding `Failed` into `NoAnswer` says *"nobody answered"* about a
case where somebody did, and the operator goes looking in the wrong place.

⚠ **`Done` means "the handler took it and answered", NOT necessarily "the work
is finished".** A handler that queues the command and returns `b"accepted"`
makes `Done` mean *accepted*. That meaning belongs to the application; the
framework does not promise it on your behalf.

---

## Routing: channel plus key, filtered by the receiver

> The sender says *"on channel `fieldbus`, for `BT-01`"*.
> It **never** says *"to process `line-2`"*.

There is no process name anywhere, because once process names are available
somebody will eventually write `if process_id == "main"` inside a use case - and
from then on moving a Modbus wire to another process means **changing code**
instead of changing configuration.

**The key lives in the row header, so a receiver filters without touching the
payload.** Three unrelated processes skip a message **without a single decode**.

**Returning `None` is how a handler says "not mine"**:

| Handler returns | The framework does |
|---|---|
| `None` | clears its bit only, does **not** record a taker |
| `bytes` | records the taker, and sends the reply if this was an `ask` |

If nobody returns anything but `None` before the asker times out, the outcome is
`NoOwner`. The four-outcome mechanism works without any extra concept.

---

## Handlers run SEQUENTIALLY per channel

```text
each CHANNEL = its own processing loop, messages within it run in order
channels     = independent, concurrent with each other
```

This is not a limitation, it is the **reason the whole mechanism exists**: if a
process sends `on`, `off`, `on` and those three run concurrently, the final
state is *whichever won the race* rather than the last one sent.

Two consequences to accept:

- **A slow handler blocks its own channel.** That is the price of ordering, and
  it is right: the next command should not run before the previous one finished.
- **To get concurrency, split the CHANNEL, not the task.** A channel is the unit
  of ordering.

> ⚠ **Handlers must be fast.** Queue long work and return. A handler still
> running when the asker times out makes the asker see `NoOwner` (*"fix your
> configuration"*) when the truth is *"that process is busy"* - the framework
> deliberately does not paper over this, because every way of doing so breaks
> `NoOwner`, the most important of the four outcomes.

---

## Message loss: at-most-once, and a full table overwrites

The bus makes **no delivery guarantee**, and that is a deliberate choice:

| | If it dies mid-way | |
|---|---|---|
| Clear the bit **first**, then work | the message is **lost** | ✅ chosen: **at-most-once** |
| Work first, clear **afterwards** | a restart **does it again** | at-least-once |

An application that needs certainty **adds its own durable queue**: the handler
enqueues and returns immediately; durability is the application's business.

When a writer's region is full it **wraps around and overwrites the oldest
row**, regardless of who has not read it - but before overwriting it **counts
that loss for whoever missed it** (`missed` in `stats()`).

⭐ Because of that, **a stalled process suffers alone** rather than blocking
everyone. Had the design chosen *"wait until everyone has read"*, one stalled
reader would hold a slot forever and jam the whole cluster.

> ⚠ On a signal bus, **a full table is a SYMPTOM, not a sizing problem**:
> traffic here is sparse, so full almost certainly means a process has stalled.
> Find it before raising `ChannelSpec.rows`.

---

## Observability

```python
stats = link.stats()
for channel in stats.channels:
    print(channel.name, channel.rows_used, "/", channel.rows_total)
    print("  oldest:", channel.oldest_unread_age_ms, "ms")
    for reader in channel.readers:
        print(f"  process {reader.process_index}: "
              f"{reader.unread} unread, {reader.missed} missed")
```

⭐ **`stats()` reports the WHOLE cluster**, not just the calling process - the
bitmap lives in shared memory so anyone can read everyone's numbers. A health
endpoint in the web process can answer for the entire herd, including processes
that open no port at all.

⚠ Three things to remember:

- **It is an APPROXIMATE snapshot**, taken without a lock. Never use it as a
  logic gate - `if stats.rows_used == 0:` will be wrong once in a thousand times.
- **`missed` accumulates and never resets.** For *"how many in the last five
  minutes"*, subtract two readings.
- **`dump(channel)` is a DEBUGGING tool**, kept separate on purpose: it carries
  every payload out, so do not call it every ten seconds from a health endpoint.

The framework also **speaks up on its own**: overwriting an unread row, a
handler running past five seconds, a table over 80% full - each logs a
rate-limited `WARNING`.

---

## Error handling

| Case | The framework does |
|---|---|
| An `@on_request` handler raises | catches it and sends a failure flag -> the asker gets **`Failed`** |
| An `@on_announce` handler raises | **logs and moves on** - nobody is waiting |
| A handler hangs | **does not cancel it**, logs a warning |
| Payload over the declared size | **raises at send time** |

`Failed.detail` carries the exception class and message, hard-capped at 200
bytes. It deliberately **carries no traceback**: an asker in another process
cannot debug with that process's traceback - no context, no variables. The full
traceback is logged **where the failure happened**, where everything is present.

An oversized payload **raises** rather than returning an outcome, because it is
a **bug in the application**, not a runtime state - returning an outcome invites
somebody to `except` it and move on.

A hung handler is **never cancelled**: a handler halfway through writing to a
Modbus device, cancelled mid-write, leaves the device in a state nobody designed
for.

---

## Limits worth knowing

| | |
|---|---|
| **One machine** | Shared memory does not span machines. Several machines are handled by sharding |
| **One thread per process** | The bus's unit is the **process**. `N > 1` threads needs no change to the shared structures, only a dispatch layer inside the process |
| **No delivery guarantee** | See above. A message is only lost when the destination process dies - and if it died it was also holding the device connection, so no software path could have delivered that command anyway. Fail-safe belongs in the device's own watchdog |
| **Payloads are raw bytes** | The framework does not decode them and keeps no type registry. ⛔ And **do not use `pickle`**: payloads come from another process, and `pickle` is arbitrary code execution |

---

## Related

- [Store](store.md) - the inter-process store, for **data**; the bus is for **signals**
- [Starters](starters.md) - `EventBus` lives in core, see the comparison at the top

---

[← RefData](refdata.md) · **ProcessLink** · [Multi-process →](multi-process.md)
