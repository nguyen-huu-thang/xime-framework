# Shared reference data (RefData)

**English** | [Tiếng Việt](../vn/refdata.md)

[← Store](store.md) · **RefData** · [ProcessLink →](process-link.md)

---

When an application runs several processes, the things **every process needs to
read** - JWT verification keys, the app registry, resolved configuration - end
up being loaded once per process. Four processes means four calls to Trust at
startup, four copies in RAM, and four different moments of key rotation.

`RefData` keeps one copy in shared memory: **the primary loads and publishes,
every process reads.**

Nothing extra to install - it lives in `xime.core`.

---

## RefData or Store: pick by **durable source**

Xime has two inter-process stores, and the boundary between them is not size or
frequency but **can this data be reloaded if it is lost**.

| | **`RefData`** (this page) | [`Store`](store.md) (LMDB) |
|---|---|---|
| Examples | JWT keys · app registry · configuration | rate limits · passkey challenges · deduplication |
| If lost | **reloadable from its source** | **gone for good** |
| Writes | rare, and **replace the whole value** | frequent, per-key |
| Who writes | **the primary only** | every process |
| Atomic ops (`incr`) | none, none needed | **yes** |

> **Self-test:** *does this data exist somewhere else?* If it does (Trust, a
> database, a config file) it belongs in `RefData`. If it does not, it belongs
> in `Store`.

⛔ Both are scoped to **one machine, always**. Several machines are handled by
sharding, not by a shared store.

---

## Declaring a table

```python
# app/refdata/jwt_keys.py
import msgpack

from xime.core.refdata import RefData

from app.domain.keys import JwtKeySet


class JwtKeyRefData(RefData[JwtKeySet], name="jwt-keys", max_bytes=64 * 1024):
    """The verification key set fetched from Trust."""

    def encode(self, value: JwtKeySet) -> bytes:
        return msgpack.packb(value.to_dict())

    def decode(self, raw: memoryview) -> JwtKeySet:
        return JwtKeySet.from_dict(msgpack.unpackb(raw))
```

Configuration is passed as **class parameters** rather than attributes in the
class body, so it never shares a namespace with whatever the application adds -
and forgetting `name` leaves the class abstract, which means it **cannot reach
DI**. Same convention as `Store`.

| Parameter | |
|---|---|
| `name` | **required**. Also the shared-memory name |
| `max_bytes` | ceiling for one version. Defaults to 64 KB |

⚠ **The block costs `2 x max_bytes`**, because two versions are always kept so a
reader never sees a half-written one. On Windows it is allocated **for real** at
startup, so do not round up "just in case".

---

## Declaring it to the framework

Tables must be declared in `config/`, because **the root process allocates the
shared memory before DI exists** - at that point it only has the class.

```python
# config/refdata.py
from xime.core.refdata import configure_refdata

from app.refdata.app_registry import AppRegistryRefData
from app.refdata.jwt_keys import JwtKeyRefData

configure_refdata([JwtKeyRefData, AppRegistryRefData])
```

Then import it from `config/__init__.py` like every other configuration module.

---

## Reading: `read()` and `read_or_fail()`

```python
class TrustKeyProvider:
    def __init__(self, keys: JwtKeyRefData) -> None:
        self._keys = keys

    def resolve(self, kid: str | None) -> Sequence[KeyContext]:
        return self._keys.read_or_fail().resolve(kid)
```

The table is injected **directly and typed**, so the IDE and `mypy` know what
`read()` returns.

| | |
|---|---|
| `read()` | the value, or `None` when **nobody has published yet** |
| `read_or_fail()` | the same, but raises `RefDataNotReadyError` when not ready |

### ⚠ `None` means NOT READY, not "empty"

This is the easiest thing to get wrong, and it fails **silently**:

```python
keys = self._keys.read()
if not keys:                      # ⛔ WRONG
    return True                   # "no keys to check against" -> lets everything through
```

A table that published an **empty** set returns an empty object, not `None`.
Collapsing the two opens a startup window in which authentication requests are
**wrongly rejected, or worse, wrongly allowed**.

```python
keys = self._keys.read()
if keys is None:                  # ✅ RIGHT - the two are distinct
    raise ServiceNotReady(...)
```

### ⚠ The returned object is SHARED - do not mutate it

`read()` returns **the** object held in this process, not a copy. Mutating it
mutates everyone's copy in this process. The framework does **not** prevent it -
preventing it would cost runtime on every read, the same boundary already
settled for `read_only()`.

### It is fast because the common path is a single comparison

`read()` keeps a cache in this process's own memory, keyed by the **generation**
number. If the generation has not moved it returns the cached object straight
away: no shared-memory read, no decode, no copy. `decode()` runs **once per
publish**, not once per read.

---

## Writing: `publish()`, and **the primary only**

> ⭐ **The primary role changes at runtime.** The parent promotes a survivor when
> the old primary dies, and that survivor may **refuse the role** and fall back to
> standby. `RefData` asks for the role on **every** `publish()` rather than
> capturing a copy at construction - otherwise the process that just took the role
> is still blocked from writing, while the parent's log says it is the primary and
> `/healthz` agrees.

```python
# Typically in the primary's startup path
keyset = await self._trust.fetch_keys()
await self._keys.publish(keyset)
```

Any other process calling `publish()` **raises** (`RefDataNotWriterError`). The
two-slot mechanism is only correct with exactly one writer; two writers filling
the spare slot at once corrupt it, and corrupt it **silently**.

`publish()` **replaces the whole value**. There is no partial-update API - that
is part of the definition of this kind of data, not a gap.

---

## Waiting for the first version: `wait_ready()`

At startup a secondary process may come up before the primary has published.
Wait in the **startup path**, never in the serving path:

```python
class WarmUp:
    def __init__(self, keys: JwtKeyRefData) -> None:
        self._keys = keys

    async def post_construct(self) -> None:
        await self._keys.wait_ready(timeout=10)
```

| | |
|---|---|
| ⛔ `read()` **never waits** | Waiting inside `read()` would hang a request |
| ⚠ `timeout` is **required** | The primary can die before it publishes, and waiting forever hangs the whole process with nobody knowing why |

---

## Observing: `stats()`

```python
stats = self._keys.stats()
```

| Field | |
|---|---|
| `generation` | the generation **in shared memory** - the newest version the cluster has. `0` = nobody published yet |
| `served_generation` | the generation **this process** is serving. ⭐ A gap against `generation` is the **only signal** that a process is serving a stale version |
| `written_at_ms` | how long ago the last publish happened |
| `used_bytes` / `limit_bytes` / `fill_ratio` | current version size against the ceiling |
| `writer` | index of the process that published the current version |
| `stale` | ⭐ **the last publish FAILED because it exceeded the ceiling**, so the whole cluster is serving the OLD version |

⚠ It is an **approximate** snapshot - it reads while somebody may be writing. Do
not use it as a guard in logic; use `read()` for that.

---

## Exceeding the ceiling: three layers, and the first is the one that saves you

Exceeding the ceiling here is worse than on the [bus](process-link.md): the bus
loses **one message**, while here a primary that cannot publish means **the whole
cluster keeps using the old version forever** - keys have rotated but every
process still verifies with the old ones, and **no request fails** until a token
signed with a new key shows up.

| Layer | |
|---|---|
| **Warning at 80% of the ceiling** | ⭐ **The layer that actually saves you**, because it warns in advance |
| `publish()` raises `RefDataTooLargeError` | The **old version is untouched** - a correct old version beats a torn new one |
| `stats().stale = True` | A failed publish nobody knows about is the worst outcome |

Raising `max_bytes` is the fix, and remember it costs double in shared memory.

### ⭐ From 0.8, `stale` is visible from EVERY process

The flag lives in the **shared-memory header**, not in the primary's RAM. Any
process - including one that is not the primary, including its `/healthz` - can
answer *"is the data I am serving out of date"*.

Before that it was an instance attribute, so it was only visible from **the very
process that had failed**, and a **newly promoted** primary started with
`stale=False` while the data was still old. The three defence layers in the table
above collapsed into one, and the remaining one sat where no operator looks.

```python
if self._keys.stats().stale:
    # The whole cluster is serving the old version. Raise max_bytes.
    ...
```

---

## What about a single process

Exactly the same. An application that does not call `share_load()` **is its own
primary**, allocates its own block, and both `publish()` and `read()` work. No
branch has to be written twice.

⚠ Running **one** child process by hand to debug it (`XIME_PROCESS_ID=api-2
python -m app.main`) means it has no parent, so it allocates its **own private**
block, shared with nobody. The framework logs a warning in that case, because
otherwise the process starts fine, `read()` returns `None` forever, and nothing
looks like an error.

---

## Large tables: segments

The shape is in place from the first release (`encode_segments` /
`decode_segments`), but the current version **uses exactly one segment**. When
data grows large enough to need splitting, override those two methods and feed a
**streaming decoder** (`msgpack` has `unpacker.feed`) - do not join the segments
first, because joining them into one `bytes` is a full copy, which throws away
the very thing segmentation is protecting.

---

## See also

- [Starters](starters.md) - the **three-way table**: `RefData` / `Store` / `CacheService`
- [Store](store.md) - the other half: data with **no durable source**
- [ProcessLink](process-link.md) - sending **signals and commands** between processes
- [Multi-process](multi-process.md) - `share_load()`, the `processes:` block, primary

---

[← Store](store.md) · **RefData** · [ProcessLink →](process-link.md)
