# Inter-process Store

**English** | [Tiếng Việt](../vn/store.md)

[← Starters](starters.md) · **Store** · [RefData →](refdata.md)

---

Once an application runs several processes, any state kept in one process's
memory becomes wrong: a rate-limit counter is multiplied by the number of
processes, and a passkey challenge started in process A cannot be finished in
process B, so the feature breaks intermittently.

`Store` is where that state goes instead. It is a key-value store on LMDB,
shared by every process of **one machine**.

```bash
pip install 'xime[lmdb]'
```

---

## The self-test before putting anything here

The store lives on shared memory (`/dev/shm` on Linux), so it **vanishes when
the machine reboots**.

> **The machine restarts and this table is empty - does the application still
> behave correctly?**

If not, that data belongs in a **database**, not here.

| | Has a durable source | No source |
|---|---|---|
| **Can be lost** | cache reloaded from its source | ✅ **`Store`** |
| **Cannot be lost** | - | ⛔ **a database** |

⚠ The word *"database"* inside the name LMDB is the single most common reason
people get this wrong. The store does survive an **application restart** (the
cache stays warm across a deploy), but never a **machine reboot**.

⛔ **Scope is ONE machine, always.** Several machines are handled by sharding:
every request for a given subject goes to the same shard, hence the same
machine, so state those requests share only needs to be shared within it.

---

## Declaring a table

Configuration is passed as **class parameters** rather than attributes in the
class body, so it never shares a namespace with whatever the application adds,
and `mypy` catches a mistyped parameter name.

```python
# app/infrastructure/store/LoginRateLimit.py
from xime.starters.lmdb import CounterStore


class LoginRateLimit(
    CounterStore,
    name="login-rate-limit",   # required - also the directory name in the store
    ttl=900,                   # optional, defaults to 3600 seconds
    parts=4,                   # optional, defaults to 1
):
    """Counts failed logins per (account, ip)."""
```

Three base classes:

| Base class | Value type | Extra |
|---|---|---|
| `Store` | `bytes` | - |
| `CounterStore` | `int` | atomic **`incr()`** |
| `Store[T]` | your own type | you write `encode()` / `decode()` |

```python
class WebhookDedup(Store, name="webhook-dedup", ttl=86400):
    """Bytes in, bytes out - the default."""


class PasskeyChallenge(Store[Challenge], name="passkey-challenge", ttl=300):
    def encode(self, value: Challenge) -> bytes:
        return value.to_bytes()

    def decode(self, raw: memoryview) -> Challenge:
        return Challenge.from_bytes(bytes(raw))
```

⚠ `raw` in `decode()` is a view into the store's memory and is **only valid
during that call**. Consume it there, do not keep it.

### Reaching DI

```python
# config/dependency.py
dependency.scan(
    "xime.starters.lmdb",              # LmdbEnvironment + StoreCleanupJob
    "app.infrastructure.store",        # your tables
)
```

A table is injected like a repository:

```python
class LoginUseCase:
    def __init__(self, rate_limit: LoginRateLimit, users: UserRepository) -> None:
        self._rate_limit = rate_limit
        self._users = users
```

> **Forgetting to declare `name` keeps the class out of DI.** The base classes
> are abstract because `name` is an abstract property; declaring `name` is what
> makes a subclass concrete. So the mistake fails at startup instead of quietly
> running as an unnamed table.

---

## Five operations

```python
await store.get(key)                          # -> T | None
await store.set(key, value, ttl=None)         # -> None
await store.delete(key)                       # -> None
await store.set_if_absent(key, value, ttl=None)   # -> bool, ATOMIC
await counter.incr(key, by=1, ttl=None)       # -> int,  ATOMIC, CounterStore only
```

Keys are strings the application composes - the framework imposes no convention:

```python
key = f"{username}|{ip}"        # rate limit per account and IP
key = f"org:{org_id}"           # quota per organisation
```

`set_if_absent` is where atomicity is genuinely needed: when two processes
receive the same webhook, exactly one gets `True`.

```python
first = await self._dedup.set_if_absent(event_id, b"1")
if not first:
    return                      # already handled
await self._handle(event)
```

⛔ **There is no `exists()` and no `keys()`.** `get() is None` covers the first;
the second is an invitation to scan a whole table on the request path.

---

## Expiry

The deadline is stored as an **absolute instant**, so every **write** resets it
while a **read** never touches it.

| Operation | Effect on the deadline |
|---|---|
| `set()` | **sets a new one** |
| `incr()` | **sets a new one** |
| `set_if_absent()` | sets a new one (when it claims) |
| `get()` | **leaves it alone** |
| `delete()` | removes the entry |

An entry with 10 seconds left, written with `set(..., ttl=300)`, expires **300
seconds from now**, not 310. Redis behaves the same way.

> ⭐ Why reads do not extend: if they did, **every read would be a write**, and a
> read-heavy table would queue behind a single write lock. For the same reason,
> this store does **not** evict by LRU.

### `ttl=None` is not `ttl=NEVER`

| Value | On the class | At a call site |
|---|---|---|
| not declared | 3600 seconds | - |
| `ttl=None` | - | use the table default |
| `ttl=NEVER` | never expires by itself | this entry never expires |
| `ttl=300` | the table default is 300 | this entry lasts 300 seconds |

```python
from xime.starters.lmdb import NEVER

class FeatureFlags(Store, name="feature-flags", ttl=NEVER):
    """Deliberately lives until deleted, or until the machine reboots."""
```

⚠ `NEVER` does **not** make it durable - see the self-test at the top.

### ⚠ Pitfall: do not `incr` while the caller is already locked out

Since a write resets the deadline, counting while the user is blocked pushes the
deadline further away on every attempt, and **the lockout lasts forever**. A real
person who mistypes a password and retries a few times locks themselves out
permanently, with nothing to signal it.

```python
MAX_FAILURES = 5

failures = await self._rate_limit.get(key) or 0
if failures >= MAX_FAILURES:
    raise TooManyFailures()       # <- return HERE, do NOT incr

user = await self._users.find_by_name(name)
if user is None or not user.matches_password(password):
    await self._rate_limit.incr(key)
    raise InvalidCredentials()

await self._rate_limit.delete(key)   # a successful login clears the counter
```

---

## Splitting a table across files

LMDB allows **one writer per file** at a time. `parts` splits that write lock:

```text
runtime/store/login-rate-limit/
    .parts   0.mdb   1.mdb   2.mdb   3.mdb

"thang|1.2.3.4"  ->  crc32(...) % 4  ->  1.mdb
"hoa|5.6.7.8"    ->  crc32(...) % 4  ->  3.mdb
```

The application sees none of this - `store.incr("thang|1.2.3.4")` is unchanged.

- Defaults to **1**. Raise it for a table that is **written often**, meaning one
  write per request (rate limiting is the typical case).
- ⛔ **Never derive `parts` from the number of processes.** The count must stay
  fixed for the life of the store: changing it puts every key in the wrong file.
  The framework detects the mismatch and **drops and recreates** the table with a
  log line - losing the cache once, in exchange for never running against a
  misplaced store.

---

## Operational configuration

```yaml
# resources/application.yml
lmdb:
  path: /dev/shm/my-service-store   # Linux: straight on RAM
  # path: runtime/store             # Windows (dev machine): an ordinary directory
  map_size: 64MB                    # STARTING size of EACH partition file
  total_max: 1GB                    # hard ceiling across the WHOLE store
  # file_mode: "0600"               # default; see the permissions section below
  # dir_mode: "0700"
```

| Key | Default | |
|---|---|---|
| `path` | **none** | Required. The framework deliberately refuses to guess: several Xime services share a machine, and a shared default directory would silently mix their tables |
| `map_size` | 64MB | Each file **doubles** when full, with a `WARNING` log |
| `total_max` | 1GB | Reaching it **raises**, rather than silently discarding somebody's data |
| `file_mode` | `"0600"` | Mode of every store file. POSIX only; no effect on Windows |
| `dir_mode` | `"0700"` | Mode of the table directory |

### ⛔ File permissions: owner only, and why that is not fussiness

This store holds **login rate-limit counters, passkey challenges, webhook
replay keys**. And the path recommended just above is `/dev/shm` - a directory
with mode **`1777`**: **every user on the machine can enter it, no privileges
needed**. The sticky bit only stops others from **deleting** your files; it does
not stop them **reading** them.

So from 0.8 the framework passes the mode **explicitly** at creation: `0600` for
files, `0700` for the directory. Before that it passed nothing, and `python-lmdb`
defaulted to `0o755`, landing at **`0644`** - world readable.

⚠ **Do not rely on `umask`.** Measured on Linux: `umask 022` and `umask 002`
both give `0644`; only `umask 077` gives `0600`. A tightly configured machine
therefore looks fine while the one next to it is exposed, from the same source.
Passing `mode` explicitly removes that dependency entirely.

**Stores created by an older version are repaired on open.** If a file or
directory is **wider** than the declared mode, the framework tightens it and
logs one `INFO` line saying what changed. The repair is **one-way**: a file you
deliberately made stricter (`0400`, say) is never widened.

> A fix that only applies to new files leaves every running installation exposed
> after the upgrade, and that is where the real data is. This store also
> **deliberately survives a restart**, so it will not recreate itself.

Set `file_mode` / `dir_mode` to choose otherwise - the repair then targets **the
value you declared**, rather than overriding your intent.

⭐ **See every key with its explanation instead of memorising them:**
`xime config --print`. Compare your own file: `xime check config`.

### ⚠ Putting the store in RAM (tmpfs) - supported, and the framework says so

On Linux, `/dev/shm/...` or `/run/<service>` (systemd `RuntimeDirectory=`) is
tmpfs, so the store sits directly in RAM. No special privilege is needed at
runtime:

```ini
[Service]
RuntimeDirectory=my-service
RuntimeDirectoryMode=0700
RuntimeDirectorySize=256M
RuntimeDirectoryPreserve=restart   # survives a restart, cleaned on stop
```

⚠ That last line is the easy one to miss: by default systemd **removes the
directory when the service stops**, so every restart wipes the store - exactly
what breaks `Store`, whose whole reason to exist is *"the next call depends on
the previous one"*.

⛔ **`/tmp` is not reliably RAM.** Debian/Ubuntu keep it on disk; Fedora/RHEL use
tmpfs. Check with `findmnt -no FSTYPE -T /tmp` rather than assuming.

The framework logs **one line at startup** saying what the store sits on,
because *"the store is at `/dev/shm/x`"* carries two meanings with nothing to
separate them:

```text
store: /dev/shm/my-service-store (tmpfs, RAM-backed - contents are lost on
reboot) - 1.9GiB free, total_max=1.0GiB
```

⚠⚠ **And a `total_max` larger than the filesystem's free space STOPS STARTUP.**
On tmpfs those pages **cannot be evicted** - only swapped, and a VPS often has no
swap. So the promise does not break as a *slowdown*, it breaks as an **OOM kill
of the whole process**. The most common case: Docker gives `/dev/shm` **64 MB**
by default; use `--shm-size`.

⚠ On tmpfs the data is **lost on reboot**. Harmless for rate limits and passkey
challenges; think twice for **replay protection** - wiping the nonce table means
an old token becomes replayable.

⚠ **This store never makes room for itself.** Full means grow; hitting
`total_max` means `StoreFullError` and a `CRITICAL` log. Do not read the word
"cache" and expect Redis behaviour - Redis evicts old keys, this does not.

That is acceptable because **every table has a TTL**, so data retires steadily.
The store only truly fills when writes outpace expiry, and that is **real load**
- it needs a higher ceiling, not eviction.

⚠ On Windows an LMDB file is allocated for real the moment it opens, so keep
`map_size` modest on a development machine.

---

## Cleaning up expired entries

An expired entry is already invisible to `get()` and already counts as free for
`set_if_absent()`, so the cleanup job only **reclaims space**. It is optional.

```python
# config/scheduler.py
from xime.starters.lmdb import StoreCleanupJob

configure_scheduler(SchedulerConfig(jobs=[
    IntervalJob(job_class=StoreCleanupJob, minutes=10),
]))
```

Running it twice is merely **wasteful**, never wrong, so it needs no distributed
lock. But writing to LMDB is exclusive per file, so with several processes
schedule it in **one** of them.

---

## Errors

The store reports failures as **exceptions**, not as a third outcome in the
return type:

| Exception | Meaning |
|---|---|
| `StoreUnavailableError` | Could not read or write. Wraps lmdb's error so you never import lmdb |
| `StoreFullError` | Needs to grow but the store is at `total_max`. An operator must raise the ceiling |
| `StoreError` | Base class of both |

> ⭐ Why exceptions: for `incr` and `set_if_absent` an exception is **fail-closed
> by nature** - forget to catch it and the request fails, so nobody claims the
> lock. A forgotten branch of a three-way return value is **fail-open in
> silence**: a rate limiter that lets everything through.

An application that wants fail-soft behaviour **catches it itself** - that is a
decision for the application, never a framework default.

---

## Related

- [Starters](starters.md) - Cache/Redis, and where the boundary lies
- [RefData](refdata.md) - the other half: data that **does** have a durable source
- [Configuration](configuration.md) - the two configuration tiers
- [Testing](testing.md) - testing with DI overrides

---

[← Starters](starters.md) · **Store** · [RefData →](refdata.md)
