# Running multiple processes (share_load)

**English** | [Tiếng Việt](../vn/multi-process.md)

[← ProcessLink](process-link.md) · **Multi-process** · [Event loop →](event-loop.md)

---

One Python process uses one CPU core. `share_load()` runs the same application
across several processes **without changing a line of business code**.

> **The central principle: no process id ever appears in code.** `main.py`
> declares *which doors this application HAS*; configuration declares *which
> process IS opening which door, on which port*.

---

## Single-process applications change nothing

Without `share_load()` everything behaves exactly as before: `server.port`,
`grpc.port`, constructor arguments. Everything below is **additive**.

---

## `main.py`

```python
from xime.adapters.grpc import GrpcAdapter
from xime.adapters.web import WebAdapter
from xime.core.bootstrap import Application

import config

app = Application()
app.add_config(config)
app.use(WebAdapter()).use(GrpcAdapter("internal")).use(GrpcAdapter("external"))

if __name__ == "__main__":
    app.share_load().run()
```

⭐ **The three middle lines are at MODULE level, not inside `if __name__`.** A
child process **re-runs this very file** to rebuild the application, and there
`__name__` is `__mp_main__`, so the `if` block does not fire. Put `use()` inside
it and the child ends up with no adapters and an empty DI container.

The framework enforces this: `app` must be a module-level variable of
`__main__`, otherwise `share_load()` fails with the correct shape spelled out.

### `add_config(config)` is required, not cosmetic

```python
# config/__init__.py
from config.dependency import dependency

from config import grpc, scheduler, web   # noqa: F401  - runs configure_* on import

__all__ = ["dependency"]
```

The old discovery mechanism located the config package through
`__main__.__spec__.parent`, and that value **differs in a child process**. The
framework looked in the wrong place and **silently** fell back to an empty DI
container: the child started fine, served no routes, and nothing reported it.

---

## ⚠ Module-level code runs `N+1` times

The parent process re-runs `main.py` too, and only then branches at
`share_load()`. So with `N` worker processes, everything outside
`if __name__ == "__main__":` runs **`N+1`** times.

> **The module level is for DECLARING, not for DOING.**

| At module level | |
|---|---|
| `import config`, `app = Application()`, `app.use(...)` | ✅ nothing is opened yet |
| class, constant and type declarations | ✅ every process rebuilds them identically |
| **opening a connection** (DB, Redis, MQTT, gRPC channel, HTTP session) | ⛔ |
| **reading/writing files**, network calls, fetching certificates | ⛔ |
| **non-deterministic values** (`uuid4()`, `time.time()`, `os.getpid()`) | ⛔ |

⭐ **Those two groups break in completely different ways**, which is why there
are two probes rather than one:

| | How it breaks |
|---|---|
| A connection opened at module level | **wasteful** - `N+1` connections instead of one, but every process is still correct |
| `uuid4()` at module level | **wrong** - every process gets a different value, while the code reading it assumes the cluster shares one |

```python
INSTANCE_ID = uuid4()          # ⛔ four processes, four ids, nobody notices
STARTED_AT  = time.time()      # ⛔ four different marks
```

⚠ The worst part of both: **they are right today and wrong tomorrow, with no
code change.** On one process everything at module level runs exactly once. Add
`count: 3` to `application.yml` and the same lines run four times - **what
changed lives in the config file, not in the file that is now wrong.**

The question to ask yourself: *if this line ran four times instead of once,
would anything break or be wasted?*

### ⚠ Logging at module level: half of it vanishes, the other half comes out raw

The framework configures logging **inside `run()`**, because the level and format
are read from `application.yml` and the runtime config is not loaded before that.
Meanwhile `config/web.py`, `config/jwt.py` and friends are imported at the **top of
`main.py`**, before `run()`.

So a `logger` call made during import is **not** simply swallowed - it fails in two
different ways, and that is the expensive part:

| Level called during import | Result |
|---|---|
| `DEBUG` / `INFO` | **gone entirely**, no trace |
| `WARNING` and above | **shown, but raw** - it escapes through `logging.lastResort`: no level, no timestamp, ignoring your `logging.format` |

```python
# config/jwt.py - runs at import time, BEFORE the framework configures logging
_log.info("fetching keys from Trust")   # gone entirely
_log.warning("could not fetch keys")    # shown, but in no configured format
```

⭐ **Why it misleads:** you see your warning appear, conclude that logging works,
then your `logger.info` in the same file disappears and you go looking for the
reason somewhere else. Half the evidence, and that half points the wrong way.

**There is no fix for this, and there should not be.** Configuring logging earlier
means configuring it from guessed values and then configuring it again, and it
legitimises exactly what this section forbids: writing a log line **is doing work**,
and it runs `N+1` times.

**Three right places for that log line:**

| Place | Runs |
|---|---|
| `post_construct()` | in every process, after DI and logging are up |
| `run_once()` | **once for the whole cluster** - right for a line about shared state |
| an adapter's own line | e.g. the `web ...: JWT middleware active (...)` line the framework prints at `lifespan` |

⚠ If you truly need output **before** the framework starts, call
`logging.basicConfig` yourself at the top of `main.py` - but remember it runs `N+1`
times and the framework will reconfigure over it afterwards.

### Probe 1 - `share_load()` measures the time

`share_load()` is the first point where the framework takes control back after
module-level code has run, so it can measure that window without knowing what is
inside it. Above **3 seconds** the parent logs **one** line, once for the whole
cluster:

```text
Module-Level Code Is Heavy
  Measured: 6.1s from the first Xime import to share_load()
  Cost    : x5 (parent + 4 worker(s)) = 30.5s spent before serving
  Detail  : module-level code runs once per process. Move connections,
            file reads and network calls into post_construct(), run_once()
            or an adapter - the module level is for DECLARING only.
```

⭐ The number on its own says nothing actionable; the **multiplication** is what
makes people go and fix it.

⚠ **This probe catches the EXPENSIVE, not the WRONG.** A `uuid4()` takes
microseconds, so it never shows up. The 3-second threshold is not a round number
either: two real, healthy applications measured **0.99s** and **1.05s** on
2026-08-20, so a lower threshold would fire on every single boot - and a probe
that cries wolf is a probe that gets turned off.

### Probe 2 - `xime check module-level`

This covers exactly the blind spot of probe 1. It statically scans `main.py` and
every module **inside the project** that it imports at module level:

```bash
xime check module-level                 # finds app/main.py, main.py or src/main.py
xime check module-level --main app/main.py --root .
```

```text
  app/config/dependency.py:14  uuid.uuid4()   RUN_ID = uuid4()

1 non-deterministic call(s) at module level, across 174 file(s).
```

It also covers the three easily forgotten places that still run at import time:
**class bodies** (`class C: ID = uuid4()`), **decorators**, and **default
argument values** (`def f(at=time.time())`). The `if __name__ == "__main__":`
block is excluded - it is the only block that does **not** run in a child
process.

⭐ **Three exit codes, not two:**

| | |
|---|---|
| `0` | clean |
| `1` | violations found |
| `2` | **inconclusive** - no entry point found, or some file could not be parsed |

⚠ Code `2` exists because *"found no violation"* and *"could not read it to look"*
are different answers. Merging them lets a CI run report green on a check that
never ran.

⚠ **This is a probe over a LIST OF NAMES, so its zero proves nothing.** It cannot
see a helper of your own that calls `uuid4()` underneath, and it cannot see a
third-party library generating values. The two probes **do not replace each
other**: one measures the *consequence* without knowing the cause, the other
finds the *cause* by name without seeing the consequence.

---

## One configuration shape, two spellings

> **`process:` is one block. `processes:` is several named blocks. The inside of
> the two is identical.**

### One process - `process:`

```yaml
process:
  web:
    public:   { host: 0.0.0.0,   port: 8086 }
    admin:    { host: 127.0.0.1, port: 8081 }
  grpc:
    internal: { host: 127.0.0.1, port: 9095 }
```

One process, three ports. ⭐ **Calling `use(WebAdapter(...))` again gives you
another web server** - that has nothing to do with the number of processes.
`public` and `admin` are the ids the developer chose in `main.py`, and
configuration may only talk about those names.

### Several processes - `processes:`

```yaml
processes:
  main:
    primary: true
    web:
      public:   { host: 0.0.0.0,   port: 8086, shared: true }
      admin:    { host: 127.0.0.1, port: 8081 }
    grpc:
      internal: { host: 127.0.0.1, port: 9095 }

  api-2:
    web:
      public:   { host: 0.0.0.0,   port: 8086, shared: true }
      admin:    { host: 127.0.0.1, port: 8082 }
    grpc:
      internal: { host: 127.0.0.1, port: 9096 }
```

| | |
|---|---|
| **`web.public` repeats port 8086 in both blocks** | It repeats **at the `use` position carrying the id `public`**, and both declare `shared: true`. The kernel spreads requests across the two processes |
| **`web.admin` does not** (8081 and 8082) | Without `shared`, each process gets its own port - two different addresses never collide |

Going from one to many: rename `process:` to `processes:`, indent one level,
give the block a name, duplicate it, add `shared` on the address you want to
share, and change `run()` to `share_load().run()`. **Nothing inside changes.**

### Keys of a cell

| Key | Which adapters | Note |
|---|---|---|
| `host` | web, grpc | Omit to keep the adapter default |
| `port` | web, grpc | |
| `path` | socket | Replaces `host`/`port`; omit to derive `<socket.dir>/<id>.sock` |
| `ssl` / `tls` | web / grpc | Omit and the cell **inherits the shared block** (`server.ssl` / `grpc.tls`) - see below |
| `shared` | web, grpc, socket | **Only under `processes:`** - see below |

Process-level keys: `primary` (exactly **one** block declares it) and `count`.

### Three keys that mean nothing with one process, and are ERRORS

| Key | Why it fails |
|---|---|
| `primary` | The only process is always the primary one - declaring it adds nothing |
| `count` | Nothing spawns children without `share_load()` |
| `shared` | Sharing one address needs **at least two processes** - alone there is nobody to share it with |

Not silently ignored: a key that is silently ignored is a place for someone to
believe in something that does not happen.

### Why `shared` must be explicit

*"Bind succeeded"* means **two different things**: *I own this port* and *I am
sharing it with someone else*. Declare the same port twice by mistake and Windows
fails loudly, while Linux runs quietly (gRPC enables `SO_REUSEPORT` by default)
with **half the requests going to a process nobody meant to send them to**.

### TLS: the cell first, the shared block second

A cell without `ssl` / `tls` **inherits the shared block** - web takes
`server.ssl`, gRPC takes `grpc.tls`. That is a security property rather than a
convenience: a secondary server **quietly serving HTTP** while the main one
serves HTTPS is a hole nobody notices, because it still answers 200. On gRPC it
costs even more - an endpoint that drops to plaintext **still accepts clients
with no certificate**, so existing callers do not break and nobody notices that
the filter on the client CN has lost the thing it was filtering.

To opt an endpoint out deliberately, declare it empty:

```yaml
process:
  web:
    public:   { port: 8086 }                # inherits server.ssl
    internal: { port: 8082, ssl: {} }       # deliberately plain HTTP
  grpc:
    internal: { port: 9095 }                # inherits grpc.tls
    public:   { port: 9096, tls: {} }       # deliberately plaintext
```

⚠ **The cell wins over the shared block, not the other way round.** Whatever the
cell declares is what runs; the shared block only speaks when the cell is silent.

> ⭐ **The first 0.8 build had no inheritance path for gRPC**, and that was a real
> hole: migrating from the flat keys to `process:` exactly as this page describes
> **lost mTLS**, and the only sign was one WARNING line among the startup log.
> Reported by `Base Platform/data` on 2026-08-21, reproduced in both directions.
> The two paths now behave the same.

### The old flat keys still work

```yaml
server:
  port: 8086
  ssl: { certfile: ..., keyfile: ... }
```

This is a **translation** into `process.web.default`, not a second code path -
once translated, only one path remains. A single-port application changes
nothing. Want a second port? Write `process:`.

### Writing N identical processes

```yaml
processes:
  main:
    primary: true
    web: { default: { port: 8086, shared: true } }

  workers:
    count: 3          # produces workers-1, workers-2, workers-3
    web: { default: { port: 8086, shared: true } }
```

⚠ `count` requires **every address in the block to be `shared: true`** - all the
processes it expands into bind the same address. The framework **does not invent
a port range**: doing so would leave you with N ports nobody registered.

### The one-letter trap

`process` and `processes` differ by a single character, so the framework catches
**both directions**:

| Configuration | Code | |
|---|---|---|
| `process:` | `run()` | ✅ |
| `processes:` | `share_load().run()` | ✅ |
| `processes:` | `run()` | ⛔ *"several processes declared but nothing spawns them"* |
| `process:` | `share_load().run()` | ⛔ *"share_load() needs `processes:`"* |
| Both present | any | ⛔ two sources for one value |

---

## The three branches of `run()`

| Condition | What `run()` does |
|---|---|
| `share_load()` not called | single process, exactly as before |
| `share_load()`, no `XIME_PROCESS_ID` | **supervisor** |
| `share_load()`, `XIME_PROCESS_ID` set | **worker** |

The third branch runs when the parent spawns a child, and also when you debug
one process by hand:

```bash
XIME_PROCESS_ID=api-2 python -m app.main
```

⚠ **Do not leave `XIME_PROCESS_ID` set in your shell.** The framework sets it
when spawning children; if it is already there, `python -m app.main` starts a
single orphan worker instead of the whole cluster.

---

## What the parent does

```text
python -m app.main          (no arguments, no env)
│
├─ import config            -> registries populated
├─ app = Application()      -> empty object, nothing opened
├─ app.use(...)             -> adapter objects, NOT started, no port taken
│
└─ share_load().run()
   ├─ validate the configuration
   ├─ SWEEP orphaned shared memory left by earlier runs that were kill -9'd
   ├─ bind() + listen() the shared addresses (if any), chmod 0600 BEFORE listen()
   ├─ allocate the shared memory: RefData · ProcessLink · watchdog beats
   ├─ spawn the PRIMARY, then WAIT for it to report run_once() done
   ├─ spawn the remaining children
   └─ watch: restart a dead child and promote · kill a hung one · Ctrl+C stops the tree
      NEVER accept() · NEVER builds DI · NEVER runs business code
```

### Sweeping at startup

A process killed with `kill -9` never returns its shared memory, and on Linux it
**stays in `/dev/shm` until the machine reboots**. So the parent sweeps before
allocating anything new: a block's name carries the **pid of whoever created
it**, which makes *"is anyone still holding this"* answerable with signal 0.

All **three families** are swept: `xime-link-` (bus), `xime-ref-` (RefData) and
`xime-beat-` (watchdog beats).

⚠ The operating system **reuses pids**, so occasionally a stale block survives
one more round because its pid happens to match a live process. Solving that
exactly is not worth the price of a few megabytes of RAM.

✅ Unlinking a block does **not** break a process that already mapped it - the
mapping stays valid, only attaching by name stops working.

### A child that keeps dying: progressive backoff, but never giving up

If a child dies at startup (bad configuration, a private port already taken, a
broken migration) and the parent restarts it every second, every attempt is a
**full re-import of the module tree** - measured at roughly 83 MB RSS and about
a second of CPU. That burns a whole core, and the log is the same `WARNING`
repeating forever.

| Consecutive deaths | Wait before restarting |
|---|---|
| 1 | 1 second |
| 2 | 2 seconds |
| 3 | 4 seconds |
| ... | doubling |
| from there | **capped at 30 seconds** |

From the **10th** attempt the log rises to `CRITICAL`: repeating an identical
`WARNING` is the surest way to make everyone stop reading it.

⭐ **The backoff resets once a child survives 60 seconds** - past that mark it is
a child that served, not a child thrashing. Without the reset, a healthy cluster
that happened to restart a few times over several months would wait 30 seconds
every time.

✅ **The "always restart" promise is unchanged.** This is throttling, not giving
up: a cluster broken by configuration must recover the moment the configuration
is fixed.

The parent **must not exit**: nothing would restart a dead child, and `Ctrl+C`
would have no place to sequence shutdown. It handles `SIGINT`, `SIGTERM` (what
`systemd` sends) and `SIGBREAK` on Windows.

⭐ A useful side effect: **a port already in use fails in the parent at startup**,
instead of four children failing one by one and you reading four identical
stack traces.

---

## `run_once()` - work done ONCE for the whole cluster

With one process, *"run at startup"* has one meaning. With four, it has **two**,
and they pull in opposite directions:

| | Every process | **Once for the cluster** |
|---|---|---|
| **Runs once, then done** | `post_construct()` | **`run_once()`** |
| **Runs forever** | `Adapter.start()` | `scaling="singleton"` |

Before 0.8 only the left column existed, so both kinds of work lived in
`post_construct` - and in a four-process cluster the migration ran four times,
the reminder emails went out four times, and the sync cursor advanced four times.

```python
class KeyRefreshJob:
    async def post_construct(self) -> None:      # EVERY process, and must be LIGHT
        self._cache = {}

    async def run_once(self) -> None:            # ONCE for the whole cluster
        await self._refdata.publish(await self._trust.fetch_keys())
```

No decorator, nothing to declare in `config/` - just **a method name by
convention**, the same family as `post_construct` and `pre_destroy`. The
framework prints the list it found at startup, so you can still see the whole
picture without reading code.

### The parent WAITS for it before spawning the next child

```text
PARENT:  spawn PRIMARY
PRIMARY: attach shared memory -> build DI -> post_construct -> RUN_ONCE -> report done
PARENT:  got the report -> spawn the remaining children
CHILD:   attach -> build DI -> post_construct -> (SKIP run_once) -> adapters start
```

This is what separates `run_once` from a scheduler's *"run once"* job, and the
difference is **timing**: a scheduler job means *run once at some point*;
`run_once` means **run once, and everything else waits for it**. The migration
finishes before the second process opens a connection.

⚠ If the primary does not report within 60 seconds the parent **continues with a
warning** rather than hanging forever: a cluster serving nothing is worse than a
cluster whose migration has not finished.

### Two constraints worth remembering

| | |
|---|---|
| **`run_once()` must be REPEATABLE** | If the primary dies partway, the promoted child **runs it again**. The parent only skips it once it has received the *done* signal |
| **There is no undo hook** | `post_construct` has `pre_destroy`; `run_once` **deliberately does not**. Fetching keys, migrating, consuming a bootstrap ticket - none of them leave anything to clean up |

⚠ A **single-process** application runs `run_once()` too: it *is* the whole
cluster. There is no branch to forget.

---

## Promoting a new primary

When the primary dies the parent **hands the role to a live child** instead of
waiting for a fresh process. That child starts its singleton adapters and keeps
serving HTTP exactly as before.

```text
primary dies  ->  waitpid confirms it exited  ->  parent picks a live child
              ->  sends "you are primary" over the internal channel
              ->  child start()s its singleton adapters  ->  reports back
```

### ⛔ The promotion signal is `waitpid`, not a health check

This is where a parent-child model is **immune** to a failure every election
system has to handle: the primary stalls briefly (a long GC, a slow disk, swap),
a health check reads that as *"dead"*, the cluster elects B, and then A wakes up
still believing it is primary. **Two primaries running background jobs.**

Xime only trusts `waitpid` - **the kernel's truth**, not a guess over a network.
A hung child is **killed first, confirmed exited, and only then** replaced; A
cannot wake up, because it is genuinely dead.

### ⭐ A failing `start()` during promotion REFUSES the role instead of crashing

The concrete case: child B is promoted, and `start()` on the certificate-rotation
job raises because the certificate is broken. Applying the plain rule *"a failure
in `start()` crashes"* means B crashes, the parent promotes C, C crashes - and you
have lost three processes **that were serving real users** over one certificate.

> **A `start()` failure at STARTUP crashes. A `start()` failure during PROMOTION
> refuses the role.** Child B keeps serving HTTP normally; it just does not become
> primary.

### Anti-domino

More than **3 promotions in 60 seconds** and the parent **stops handing out the
primary role**, says so loudly, and the cluster carries on **without background
jobs**.

⚠ **Two separate switches, do not confuse them:** *restarting dead children*
still happens; only *granting the primary role* stops. Losing background jobs
beats losing the ability to serve.

---

## Watchdog - catching a HUNG child

`waitpid` sees a child **die**. It does not see a child **hang**: a coroutine that
makes a synchronous I/O call, or runs a long CPU loop, blocks the whole event loop
- the process is still alive as far as the kernel is concerned, and the cluster
quietly loses a process.

| | Health check | **Watchdog** |
|---|---|---|
| Direction | Parent **asks**, child **answers** | Child **proves itself**, parent just reads |
| What the parent needs | A client, timeouts, retries | **Nothing** - it reads 16 bytes |
| A busy child | Cannot answer **even though it is fine** | Still pats, as long as the loop turns |

The child writes a timestamp every **1 second**. The parent does **not** stay
silent and then kill - it escalates, and every step carries the **stack of the
stuck child**, so you learn *where* it is stuck:

| Stuck for | Level | What happens |
|---|---|---|
| 5 seconds | `WARNING` | reported, with a stack |
| 15 seconds | `ERROR` | reported again, with a **fresh** stack - has it moved, or is it in the same place? |
| 30 seconds | `CRITICAL` | loud, and it says the parent is about to kill |
| 60 seconds | - | the parent **kills it**, so its sentinel fires on the next pass and promotion still goes through `waitpid` |

Each level prints **once per stall**, not once per loop - because if the thing
blocking the loop *is* writing to the console (on Windows that is synchronous
I/O), printing every round would **make the exact problem worse**.

⛔ **Exception: a stall inside `accept()` has a 10-second deadline, not 60.** On
Windows a worker stuck inside `accept()` is the worker **holding the accept
lock**, and while it is stuck **nobody in the cluster accepts a connection** -
see the [accept lock](#-windows-the-accept-lock)
below. Past that short deadline the process **exits itself**, because that is the
fastest way to give the lock back.

⭐ The ladder is **on by default**, not a dev-only feature: it adds nothing to the
request path - it is one thread re-reading **the same heartbeat the child already
writes**. Measured: throughput differs by **-0.22%** (inside the noise), one stack
snapshot costs **0.11 ms**, and only once something is already stuck. The
incidents worth knowing about happen in production, where nobody has a debug flag
turned on.

⚠ A child that has **never patted** is *starting up*, not *hung* - the parent
gives it 60 seconds. Collapsing those two meanings kills every child the moment
it is born.

⭐ Each heartbeat slot carries **two** values: a timestamp **and a pat count**.
Thanks to the second one, *"has this child ever patted?"* is something the parent
can **prove** with one comparison, rather than infer from a timestamp of zero -
and zero is also what a freshly allocated slot and a half-finished write look
like. Before the counter existed those three situations were indistinguishable,
and a worker was once killed with *"never sent a heartbeat"* while the log proved
it had been patting normally.

⛔ **The timestamp uses a MONOTONIC clock, not wall time.** Wall time jumps: NTP
steps the clock, an operator corrects it, a virtual machine restores a snapshot.
A **forward jump of 30 seconds** pushes the silence window of **every healthy
child** over the threshold at once, so the parent kills the whole set - and then
the anti-domino guard counts three promotions and **stops handing out the primary
role for good**. Both ends of the measurement (child writes, parent reads) must
use the **same clock**; fixing only one end yields the difference between two
frames of reference, a number the size of the epoch.

### You do not have to do anything

No API, no configuration. The pat is a task on the child's **main event loop**,
and the framework sets it up.

⚠ Where the pat lives is part of the **contract**: put it on a separate thread and
it only measures *"the process still exists"* - which `waitpid` already answered -
and the watchdog stays green forever. The framework has a test guarding exactly
that.

### Who watches the PARENT: `systemd`

```ini
[Service]
Type=notify
WatchdogSec=30
ExecStart=/usr/bin/python -m app.main
```

The parent sends `READY=1` once the cluster is up and `WATCHDOG=1` on every watch
pass. With no `NOTIFY_SOCKET` (run by hand, Windows) it is **silently skipped**.

⭐ The framework does not write its own parent-watching process, because the next
question would be *"who watches that one"*. The principle is borrowed from
hardware: **a watchdog does not live on the CPU it watches**.

⚠ A hung parent is **less dangerous than it sounds**: it never `accept()`s, so the
children keep serving. What is lost is the ability to **self-heal**, and nobody
notices until the first child dies.

---

### When the parent dies, the children follow - and why you cannot find an orphan

The parent traps `SIGINT` / `SIGTERM` / `SIGBREAK` and shuts the whole group down
in order. The other three ways it can die **cannot be trapped by anyone**, and
all three happen in real life:

| How the parent dies | Handler runs? |
|---|---|
| `Ctrl+C`, `systemd stop`, `taskkill` (no `/F`) | ✅ parent stops the group |
| `SIGKILL`, `Stop-Process -Force`, `taskkill /F` | ⛔ **nothing can trap it** |
| The parent itself crashes | ⛔ |
| The machine runs out of memory and the kernel kills it | ⛔ |

So **each child watches its parent**: when the parent disappears, the child shuts
itself down along the very same graceful path it uses when the parent asks it to
stop. Nothing to declare, no configuration key.

```text
CRITICAL | orphan guard: the supervisor (pid 23032) is gone - this process is
           now an orphan holding a shared socket, so it is shutting down.
           Nothing will restart it; restart the cluster from main.py.
```

If the graceful path has not finished after 15 seconds (the loop is blocked) it
**exits hard with code 3**. Blunt, and deliberately so: by then the only thing
still worth doing is **releasing the port**.

#### ⭐⭐ Why this deserves its own section: an orphan is INVISIBLE to the obvious checks

This is the expensive part, and it cost one session four rounds of debugging. An
orphan does not merely *exist* - it **hides from both checks you would reach
for**, and both answer in the **reassuring** direction.

**Check 1 - filter by command line. Returns 1 process while 12 are running.**

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*app.main*' }     # ⛔ finds only the PARENT
```

Children **do not carry `app.main` in their command line** - `multiprocessing`
starts them with `spawn`, so their command line is:

```text
parent:  python -m app.main
child:   python -c "from multiprocessing.spawn import spawn_main; ..."
```

**Check 2 - `netstat`. Points at PIDs that no longer exist.**

```text
TCP  0.0.0.0:8122  LISTENING  3084      <- Get-Process 3084 -> does not exist
```

The socket is still alive because **the children inherited the handle**, but
`netstat` attributes a socket to the PID that **created** it - the parent's
corpse. The reader concludes *"just a stale entry, ignore it"*, and that
conclusion is wrong.

> Two reassuring answers add up to a cluster still serving **old code** while you
> believe you just restarted it.

From 0.8.x on you will not meet this: children leave when the parent leaves. But
if you are debugging a cluster running an older build, the two commands below
find the right thing - they ask about the **parent-child relationship** and the
**real owner of the socket**, not about command lines:

```powershell
# Windows: search by PARENT RELATIONSHIP
$deadParents = @(3084, 10188, 13056)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $deadParents -contains $_.ParentProcessId } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# The REAL owner of the port, not netstat
Get-NetTCPConnection -LocalPort 8122 -State Listen | Select-Object OwningProcess
```

```bash
# Linux
pkill -f 'multiprocessing.spawn'      # or: ss -lptn 'sport = :8122'
```

#### ⛔ On Windows, `-15` is NOT a signal from outside

This sent one session half a day in the wrong direction, so it is worth
remembering.

When you see:

```text
WARNING | supervisor: api-3 exited with code -15 (...) - restarting
```

the natural reflex is *"something sent `SIGTERM` to my child"*. **Not on
Windows.** CPython (`multiprocessing/popen_spawn_win32.py`) reads
`GetExitCodeProcess`, and when the code equals the constant
`TERMINATE = 0x10000` it **rewrites it** to `-signal.SIGTERM`. And `0x10000` is
only ever written by `multiprocessing` itself. External tools write very
different codes:

| Who killed it | Exit code Python reports |
|---|---|
| `multiprocessing` (`terminate()`/`kill()`) | `-15` |
| `taskkill /F` | `1` |
| `Stop-Process -Force` (.NET `Process.Kill()`) | `4294967295` |

> So on Windows, `-15` on a child that **this parent did not kill** is evidence
> that **an older cluster is still running** and killing the new one's children.

That is why the log line now states **who did it**, not just the exit code:

```text
... exited with code -15 (my watchdog killed it: event loop blocked for 12.3s) - restarting
... exited with code -15 (NOT me - another multiprocessing parent terminated it; ...) - restarting
```

Those two sentences lead to opposite actions: the first is an internal matter
already handled, the second means *go find the older cluster*. On POSIX, `-N`
literally means signal `N` - no rewriting involved.


---

## `/healthz` and `/readyz`

**Off** by default. One line turns them on:

```python
# config/web.py
from xime.adapters.web import configure_health

configure_health()                                  # /healthz and /readyz
configure_health(healthz="/_alive", readyz=None)    # custom path, one turned off
```

If you would rather not have endpoints, read the data directly: `app.health()` is
always there, with nothing to declare.

### ⚠ The two paths answer TWO questions - do not merge them

| | Question | Who reads it | What red means to them |
|---|---|---|---|
| `/healthz` | *"is this process still usable"* | systemd, k8s | **restart** |
| `/readyz` | *"can it take new requests"* | load balancer | **pull it out of rotation** |

One broken adapter while three others still serve **should** make the load
balancer pull the process out, and systemd **should not** kill it - killing trades
*partially broken* for *entirely broken*, and loses the logs with it.

### ⭐ A non-primary process stays GREEN when the cluster has no primary

`/readyz` asks *"can it take new requests"*, and a non-primary process **can**;
what the cluster loses without a primary is **background jobs**. Answer the other
way and the load balancer pulls out every process, killing the cluster entirely
over one background job that is not running.

A singleton adapter waiting on a non-primary process sits in the `standby` state,
and `standby` does **not** turn `ready` red. The fact that *the cluster has no
primary* is still visible - in the `primary` field of that same response.

```json
{
  "alive": true,
  "ready": true,
  "primary": false,
  "adapters": [
    {"id": "default", "kind": "web", "state": "serving"},
    {"id": "default", "kind": "scheduler", "state": "standby"}
  ]
}
```

⭐ **Cluster background jobs run on the primary only, and that is the design** - no
configuration key changes it. If you need a periodic loop on **every** process, that is not
a scheduler job but an adapter's, and **writing an adapter is not a public extension
point** - both kinds of work that genuinely need one already have an answer. The full
reasoning lives in [`starters.md`](starters.md) under *"A job runs ONCE for the whole
cluster"*.

### ⛔ Neither path is authenticated

Deliberately. They have to answer **when everything else is broken**, including
when no verification key could be fetched - a `/healthz` that demands a token is a
`/healthz` that goes silent exactly when you need it. In exchange, the body
carries nothing sensitive: no host, no port, no version, no error message.

⭐ The safest shape in production: put them on a **secondary server bound to
`127.0.0.1`**. Operators and systemd can reach them; the internet cannot.

### Middleware you wrote yourself: ask `public_health_paths()`

The *"not authenticated"* line above holds for the framework's **own** JWT
middleware: it adds both paths to `public_paths` before installing itself. The
framework knows nothing about yours, so ask for them:

```python
# config/web.py
from xime.adapters.web import configure_health, configure_middleware, public_health_paths

configure_health()                       # ⚠ declare it FIRST, see the warning below

configure_middleware(
    IpFenceMiddleware,
    public_paths=[*your_own_config, *public_health_paths()],
)
```

⭐ **Not only an auth concern.** An IP fence, an access log, a rate limiter, a
metrics counter: each has a reason to skip the health paths, and none of those
reasons **goes away** once the application moves to `configure_jwt`.

⛔ **On `configure_jwt`, do NOT add them again.** The framework already did; a
hand-written copy is a second implementation that drifts the day the path
matching rule changes.

⚠ **Call it AFTER `configure_health()`.** It reads the registry at the moment it
is called, so calling it early returns an **empty** tuple - and empty here looks
exactly like *"this app has no health endpoints"*. Your fence then blocks
`/healthz` with **nothing to warn you**, because it refuses very tidily.

---

## Adapters take an IDENTITY only; addresses come from configuration

```python
app.use(WebAdapter("admin"))          # ✅ just the id
app.use(WebAdapter("admin", 8081))    # ⛔ TypeError - no other argument exists
```

The three serving adapters (`web`, `grpc`, `socket`) **dropped** `host` / `port`
/ `ssl` / `path` from their constructors in 0.8, for two different reasons:

| | |
|---|---|
| `host` / `port` / `path` | **Describing reality** - under load sharing the parent `bind()`s and hands the socket down, so a child **has no way to pick its own port**. An argument there is a promise the framework cannot keep |
| `ssl` | **An exception that lost its reason** - it existed for a secondary server needing a different certificate, and a secondary server now has its own configuration cell |

⭐ Removing the argument outright means no check is needed: Python refuses it at
the signature, and *"the operator edited the YAML and the port did not change"*
stops existing.

---

## Each adapter shares an address its own way

| Adapter | How an address is shared | Linux | Windows |
|---|---|---|---|
| **web** | parent holds the socket, hands it down | ✅ | ✅ (see note) |
| **socket** (unix) | parent holds the socket | ✅ | - |
| **grpc** | `SO_REUSEPORT` | ✅ | ⛔ **startup error** |
| mqtt, modbus, opcua | **sharded kind** - deferred to some 0.8.x | - | - |

`grpc.aio` only accepts an address string, with no API for an externally
supplied socket, so it cannot use the socket-passing route. Windows has no
`SO_REUSEPORT`, and the framework **fails at startup** rather than letting the
second process die from `WinError 10048` mid-run. On Windows, give each process
its own gRPC port - the other adapters still run multi-process.

### ⚠ Windows note: the framework switches event loop

A child process that **inherits a shared socket** on Windows runs on the
**selector event loop** instead of the default proactor one, and the framework
logs a `WARNING` saying so.

The reason: IOCP association belongs to the **kernel socket**, not to the
**handle**. Once the first process associates the socket with its IOCP, a second
process cannot - it starts successfully, logs *"serving"*, and then **never
accepts a single connection**. The selector loop calls `accept()` directly and is
unaffected.

The cost: `select()` on Windows is limited to 512 sockets, and that loop cannot
run subprocesses. Acceptable because Windows is a development machine;
production runs on Linux, where `epoll` has no such limit.

### ⛔ Windows: the accept lock

Same root cause as the note above, and its second consequence. Because Windows is
forced down to the selector loop, `accept()` runs **directly inside an event loop
callback** - and there it hits an operating-system bug.

When several processes call `accept()` on one shared listening socket, the process
that **loses the race** is held by the kernel **inside `accept()`** until the
client on the other end gives up, even though the socket is correctly
non-blocking and `select()` has just reported it ready. That process's entire
event loop stands still for the whole time.

⭐ **The stall tracks the CLIENT's timeout, not anything you can tune**: a client
waiting 5 seconds produces a 5.4-second stall, one waiting 40 seconds produces
40.5. And **a new connection does not rescue it**.

The framework wraps the shared socket in a **Win32 named mutex**: exactly one
process may sit in `accept()` at a time. This is nginx's `accept_mutex` and
Apache's `AcceptMutex`.

| Measured on a 3-process cluster | |
|---|---|
| Stalls | **15 → 0** |
| Load spread | still even across processes |
| Cost | **2.5%** throughput |

⭐ **The lock does not touch the network port.** The port stays `LISTEN`, the
kernel still completes TCP handshakes and still queues connections. The lock only
decides *who may call `accept()` right now*, and it is held **around that one call
only** - reading the request, running your logic, querying the database and
writing the response all happen without it, so the parallelism you actually came
for is untouched.

**You do not have to do anything**: no API, no configuration, and **off Windows
the wrapper returns the original socket** unchanged. Measured on Linux: the
underlying bug does not reproduce across 49,600 requests (epoll, uvloop, uvicorn
with 1-4 workers, 6 processes).

⚠ This is why the escalation ladder under [Watchdog](#watchdog---catching-a-hung-child)
gives a stall inside `accept()` a **10-second** deadline instead of 60: a worker
stuck there is the worker holding the lock, so it does not merely harm itself -
it **blocks the whole cluster**.

### Sharded adapters (mqtt, modbus, opcua)

These three **cannot be replicated by duplicating the connection**: two
processes polling one PLC double the load on real hardware, and two MQTT clients
with the same `client_id` make the broker kick the older session off. Each
process must own a **different slice**, and the configuration shape for that
is deferred to **some 0.8.x release**, not yet pinned. Until then, run
applications that use them as a single
process.

---

## Four startup checks

All four run **inside one process**, with no coordination, because every process
reads the same file.

| # | Check | Outcome |
|---|---|---|
| 1 | No block declares `primary: true`, or two do | **error** |
| 2 | A name in the configuration that `main.py` never declared | **error** - certainly a typo |
| 3 | An adapter declared in `main.py` that this block omits | **skipped** + one `WARNING` line |
| 4 | One address used by two blocks without `shared` | **error** |

### Reading the startup log: every endpoint leaves a line, with its security mode

Each adapter writes **one `INFO` line** once it has bound, saying where it came up
and **which mode it is running**:

```text
INFO | web default: process main serving on 0.0.0.0:8086 (HTTPS+mTLS)
INFO | grpc default: process main serving on 0.0.0.0:9095 (mTLS)
INFO | socket default: process main serving on /run/x.sock (0600, any uid)
```

The mode sits on the **same line** as the address rather than in a separate
warning, because an operator reads the startup log to answer *"what came up"* -
they see this line **every time**, right where they are already looking. Asking
someone to notice the **absence** of a warning is not a measurement anyone can
make.

| Adapter | Modes you can see |
|---|---|
| `web` | `HTTP` · `HTTPS` · `HTTPS+mTLS` |
| `grpc` | `PLAINTEXT` · `TLS` · `mTLS` |
| `socket` | file mode plus `any uid`, or the list of permitted uids |

⚠ The `socket` line says `any uid` when `allowed_uids` is empty - at that point
**the file mode is the only gate**, and that deserves to be stated rather than
inferred from a blank.

> ⭐ **Before this build, gRPC only logged when something was wrong, and `socket`
> logged nothing at all.** So a **healthy** gRPC cluster produced a log
> **identical** to a **broken** one: the good state left no trace to compare
> against. Reported by `Base Platform/data` on 2026-08-21, alongside the TLS hole
> above - and the two **compound**, because when everything the log says about
> gRPC is a warning, there is no positive marker to check against.

Plus three more around *being on the wrong branch*:

- `processes:` present but `share_load()` never called -> error.
- `share_load()` with no `processes:` block -> error.
- `share_load()` with no adapters at all -> error.

⭐ Check 2 catches something the old model could not: typing `web: publik`
instead of `public` used to give you a silent server with no controllers.

---

## ⚠ Several MACHINES (Docker, k8s) - what "cluster" means here

Everything on this page is about the **group of processes inside ONE machine**:
the parent spawns children with `multiprocessing`, watches them with `waitpid`,
and shares memory through `shared_memory`. All three stop at a machine boundary,
and **a container is a machine**.

⭐ That is **not a temporary limitation**, it is the mechanism: a `shared_memory`
block and an LMDB file do not span machines, and something that does would
already be a different technology.

Running `N` replicas (a k8s Deployment, `docker compose scale`, several VPS) is
perfectly normal - just read this table:

| | Actual scope |
|---|---|
| `share_load()`, `count:`, primary promotion, watchdog | **one cluster per machine** |
| `RefData`, `Store`, `ProcessLink` | **one copy per machine** |
| `run_once()`, an adapter with `scaling="singleton"` | **once per machine** |
| `CacheService` (Redis) | **shared across machines** |

### ⛔ The trap: `run_once()` runs once PER MACHINE

`run_once()` is documented as *"once for the whole cluster"*, and with three pods
*"the cluster"* means **three clusters**, not one.

```text
1 machine, count: 4       ->  run_once() runs once
3 pods, count: 4 each     ->  run_once() runs three times, concurrently
```

⚠ So **do not put a database migration in `run_once()` if you run replicas**. The
framework cannot prevent it - it does not know the other pod exists.

✅ If you need *"once for the whole system"*, that is a different problem and it
needs a lock every machine can see: `CacheService` + `SET NX`, a database
advisory lock, or a separate Job that runs before the Deployment. See
[Starters](starters.md).

### Ports and load balancers

Within one machine the framework **splits a port itself** across N processes (the
parent holds the socket, or `SO_REUSEPORT`). Across machines that belongs to the
layer above - a k8s Service, nginx, whatever you already run. The framework stays
out of it on purpose: *do not write a load balancer*.

---

## What 0.8 does not have yet

| | |
|---|---|
| **Zero-downtime code upgrades** | The parent holds the sockets, so changing its code needs a parent restart, and restarting the parent drops connections. The way out is known (`exec` the new build inheriting the fds, the way nginx does it); not built yet |
| **The parent speaking outward** | The parent logs, but it has no alerting channel and no cluster-wide `/healthz`. A warning like *"a child refused the primary role"* reaches journald today, **not a person** |
| **Graceful shutdown** | A child in the middle of a request is still `terminate()`d once the grace period runs out |
| **Load splitting for fieldbus and MQTT** | Signatures were settled in 0.8; the implementation is deferred to **some 0.8.x release**, not yet pinned |

⚠ The second row is the easiest one to misread: everything above **is** reported
correctly into the parent's log, so `journalctl -u app` shows it all. What is
missing is the path that pushes it to a monitoring system.

---

## The adapter contract

> ⛔ **Adapters are not a public extension point.** The six that ship with the
> framework (web, gRPC, socket, MQTT, Modbus TCP, OPC UA) are the six there are,
> and adding another one is the framework's job, not the application's.
> `xime.core.bootstrap.adapter` and everything around it (`AdapterSlot`,
> `assign_slot()`, `adapter_kind`, `share_port_by`) are **internal details** and
> may change in any release without notice.
>
> This section exists because that contract **explains behaviour you can
> observe**: why `/readyz` turns green exactly when it does, why the startup log
> is ordered the way it is, and why one adapter runs in every process while
> another runs only on the primary. If you need a protocol that is not here,
> **tell the team that maintains the framework** - do not build an adapter
> outside it, because it will break on the next upgrade, and break silently.

An adapter's lifecycle has **three** steps, not two, and `app.use(...)` checks
the contract right at that line:

| Step | Meaning |
|---|---|
| `start()` | **Acquire resources and RETURN** - open the port, connect the broker, build the session |
| `serve()` | **Serve and BLOCK** until stopped |
| `stop()` | Stop. Must be **idempotent** - it is called both on the graceful path and by the watchdog |

### Why `start()` and `serve()` are separate

A single `start()` leaves **nothing that says "resource acquisition finished"**,
while three things need exactly that: the parent deciding when to spawn the next
child · telling *"could not start serving"* apart from *"broke while serving"* ·
and `/readyz`.

⭐ It **imposes no new shape**: gRPC already has `start()` +
`wait_for_termination()`, uvicorn already has `startup()` + `main_loop()`,
asyncio already has `start_unix_server()` + `serve_forever()`. The framework
simply stops hiding the structure that was already there.

| Error raised from | What the framework does |
|---|---|
| `start()` | **Kills the process** - there is no point continuing when nothing can be served |
| `serve()` | **Isolates that adapter**, logs `CRITICAL`, the others keep running |

✅ **The process survives losing its last adapter.** While it lives, `/healthz`
still answers, logs are still readable, and it can still be debugged.

### `scaling` is mandatory

| Value | Meaning | What the framework does |
|---|---|---|
| `"replicated"` | N identical copies, the kernel spreads load | Runs in **every** process that declares it |
| `"sharded"` | Each copy owns a **slice** of the work | Runs in every process that declares it, **plus the two checks** below |
| `"singleton"` | Only the primary runs it | `start()` **on the primary only** |

There is no default. Defaulting to `replicated` is **dangerous** - an adapter
that never considered replication gets replicated, and it fails **silently**;
defaulting to `singleton` makes the app slow with nobody knowing why. ⭐ A
subclass of an adapter that already declared one **inherits** it.

A sharded adapter also declares *what must differ between processes*. This is how the
MQTT adapter **that ships with the framework** declares itself, quoted to show the shape
rather than as a template:

```python
class MqttAdapter(
    Adapter,
    scaling="sharded",
    unique_per_process=("client_id",),    # values must DIFFER
    disjoint_per_process=("topics",),     # sets must NOT OVERLAP
): ...
```

⭐ The two checks are **genuinely different**, and MQTT needs both at once:
"differ" applies to a **single value**, "not overlap" applies to a **set**. The
framework runs them at startup, reading the `processes:` block.

---

## Related

- [Store](store.md) - move state out of process memory.
- [ProcessLink](process-link.md) - send commands and questions between processes.
- [RefData](refdata.md) - one shared copy of data that has a durable source.
- [Configuration](configuration.md) - the two config layers and their boundary.

---

[← ProcessLink](process-link.md) · **Multi-process** · [Testing →](testing.md)
