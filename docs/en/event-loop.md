# Event loop

**English** | [Tiếng Việt](../vn/event-loop.md)

[← Multi-process](multi-process.md) · **Event loop** · [Testing →](testing.md)

---

Everything in Xime runs on an asyncio event loop. Normally you never think about
it. This page is for the two moments when you do: when you want to know **which
loop you are actually running on today**, and when you are wondering whether
**switching loops would make you faster**.

Since `0.8.1`, Xime picks the best available loop implementation for the platform
it is running on. **You declare nothing** - no configuration key, no switch.

---

## Which loop is running - ask the application

On every startup, Xime logs one line at `INFO`:

```text
INFO | xime.bootstrap | event loop: uvloop.Loop
```

```text
INFO | xime.bootstrap | event loop: asyncio.windows_events.ProactorEventLoop
```

That line reports the implementation **actually running**, not the intent. The
difference is not pedantry: before `0.8.1`, `uvloop` **was already on disk in
every Linux install** of Xime (it ships with `uvicorn[standard]`) and **never ran
once**, with nothing to signal it. Seeing the package in `pip list` and
concluding *"it is enabled"* was wrong.

> To know which loop you are on, **read that process's own log**. Do not infer it
> from the list of installed packages.

---

## How Xime picks

| Platform | Loop | Why |
| --- | --- | --- |
| Linux, macOS | **uvloop** if importable, otherwise the default | Faster for most kinds of work - see the measurements below |
| Windows, with `share_load()` sharing a port | `SelectorEventLoop` | The default proactor loop cannot accept on a socket another process has already bound to its IOCP (`WinError 87`) |
| Windows, otherwise | default (proactor) | |

`uvloop` has no Windows build and never will. On Windows, that row of the table
simply does not exist.

### Where uvloop comes from

```bash
pip install 'xime[web]'     # pulls uvicorn[standard], which includes uvloop
```

Skip the `web` extra, or install plain `uvicorn`, and there is no `uvloop`: the
application runs on the default loop. **The cost is zero**: Xime tries the
import, moves on if it fails, and says nothing.

Xime does **not** declare `uvloop` as a dependency of its own, and does **not**
call `uvloop.install()`. That function sets a process-wide policy, which means
reaching into code that is not Xime's.

---

## ⚠ uvloop does NOT speed up REST - it costs about 10%

This is the part of this page worth reading, and it contradicts most of what is
written about uvloop.

Measured on **the same Xime application**, Debian 13, Python 3.13.5, uvloop
0.22.1, under 2% variance, two runs an hour apart agreeing:

| Kind of work | uvloop vs. the default loop |
| --- | --- |
| **Handling an HTTP-shaped request**: REST `0.91x` · WebSocket handshake `0.93x` | **8-9% slower** |
| **Moving data on an open connection**: WebSocket messages `1.11x` · raw TCP echo `1.38x` | **11-38% faster** |

The dividing line is **not the protocol**. A WebSocket handshake is an
HTTP-upgrade request, so it lands **on the same side as REST** - the opposite
side from the very messages that follow it **over that same socket**.

The reading: uvloop is faster at the **I/O** part, but an HTTP request spends
most of its time elsewhere (parsing, routing, building objects, running your
code). The gain underneath is not enough to pay for the rest, and on Python's
HTTP stack it comes out negative.

### So why does Xime use uvloop anyway

- **Nothing is lost when it is absent.** Without uvloop the application runs
  exactly as it did in every earlier version.
- **REST is not the whole framework.** The other five adapters (gRPC, socket,
  MQTT, Modbus, OPC UA) all live on **open connections** - the side that gains.
- **Throughput per %CPU always wins** (1.31x to 1.64x). On a per-CPU billing
  model that matters more than peak throughput.

### 📌 The useful knob is not the event loop

If you came here looking for speed, this is the number to remember:

| Change | Throughput |
| --- | --- |
| Add one process (`count:` in the `processes:` block) | **+100%** |
| Change the event loop | **-10%** for REST |

See [Multi-process](multi-process.md). A Xime cluster scales close to linearly:
2.00x on two processes, 3.88x on four.

---

## Why there is no on/off switch

The natural follow-up: *"then let me turn uvloop off for REST"*.

Xime deliberately has no such key, because **an operator does not have the
information to choose**. Answering *"which loop should my application use"*
requires knowing the ratio of HTTP-shaped requests to open-connection work,
knowing where each handler spends its time, and measuring on the machine that
actually runs it. The framework author had to measure too, and the measurement
overturned the original assumption.

A configuration key here produces only two outcomes: nobody touches it, or
somebody sets it wrong based on a blog post.

If you truly need it, you can still decide at install time: install plain
`uvicorn` instead of `uvicorn[standard]`, or remove `uvloop` from the
environment. Xime notices and moves on.

---

## Related

- [Multi-process](multi-process.md) - `share_load()`, the `processes:` block,
  and why Windows must switch to the selector loop when sharing a port.
- [WebSocket](websocket.md) - the adapter that gains most from uvloop, in its
  messages rather than its handshake.
