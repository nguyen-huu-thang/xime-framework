# Running multiple processes (share_load)

**English** | [Tiếng Việt](../vn/multi-process.md)

[← ProcessLink](process-link.md) · **Multi-process** · [Testing →](testing.md)

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
| `ssl` / `tls` | web / grpc | Omit and web inherits `server.ssl` - see below |
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

### TLS: the cell first, `server.ssl` second

A cell without `ssl` **inherits `server.ssl`**, and that is a security property
rather than a convenience: a secondary server **quietly serving HTTP** while the
main one serves HTTPS is a hole nobody notices, because it still answers 200. To
opt an endpoint out deliberately, declare it empty:

```yaml
process:
  web:
    public:   { port: 8086 }                # inherits server.ssl
    internal: { port: 8082, ssl: {} }       # deliberately plain HTTP
```

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
   ├─ bind() + listen() the shared addresses (if any)
   ├─ allocate the shared memory: RefData · ProcessLink · watchdog beats
   ├─ spawn the PRIMARY, then WAIT for it to report run_once() done
   ├─ spawn the remaining children
   └─ watch: restart a dead child and promote · kill a hung one · Ctrl+C stops the tree
      NEVER accept() · NEVER builds DI · NEVER runs business code
```

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
| What the parent needs | A client, timeouts, retries | **Nothing** - it reads 8 bytes |
| A busy child | Cannot answer **even though it is fine** | Still pats, as long as the loop turns |

The child writes a timestamp every **1 second**; silence for more than **10
seconds** and the parent **kills it**, so its sentinel fires on the next pass and
promotion still goes through `waitpid`.

⚠ A child that has **never patted** is *starting up*, not *hung* - the parent
gives it 60 seconds. Collapsing those two meanings kills every child the moment
it is born.

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

### ⛔ Neither path is authenticated

Deliberately. They have to answer **when everything else is broken**, including
when no verification key could be fetched - a `/healthz` that demands a token is a
`/healthz` that goes silent exactly when you need it. In exchange, the body
carries nothing sensitive: no host, no port, no version, no error message.

⭐ The safest shape in production: put them on a **secondary server bound to
`127.0.0.1`**. Operators and systemd can reach them; the internet cannot.

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
| mqtt, modbus, opcua | **sharded kind** - lands in 0.8.1 | - | - |

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

### Sharded adapters (mqtt, modbus, opcua)

These three **cannot be replicated by duplicating the connection**: two
processes polling one PLC double the load on real hardware, and two MQTT clients
with the same `client_id` make the broker kick the older session off. Each
process must own a **different slice**, and the configuration shape for that
lands in **0.8.1**. Until then, run applications that use them as a single
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
| **Load splitting for fieldbus and MQTT** | Signatures were settled in 0.8; the implementation lands in **0.8.1** |

⚠ The second row is the easiest one to misread: everything above **is** reported
correctly into the parent's log, so `journalctl -u app` shows it all. What is
missing is the path that pushes it to a monitoring system.

---

## Writing your own adapter

The contract changed in 0.8, and `app.use(...)` **checks it right there**:

```python
from xime.core.bootstrap.adapter import Adapter

class MyAdapter(Adapter, scaling="replicated"):
    adapter_kind = "my"                      # second key level in processes:

    def __init__(self, server_id: str = "default") -> None:
        self.adapter_id = server_id

    async def start(self, app) -> None:      # take resources, then RETURN
        ...

    async def serve(self) -> None:           # serve, BLOCK until stopped
        ...

    async def stop(self) -> None:            # must be idempotent
        ...
```

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

A sharded adapter also declares *what must differ between processes*:

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
