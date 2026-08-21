# Socket Adapter

**English** | [Tiếng Việt](../vn/socket-adapter.md)

[← Starters](starters.md) · **8/9 - Socket Adapter** · [Contributing →](contributing.md)

---

The Socket Adapter adds **Unix Domain Socket (UDS)** support to XIME - a low-overhead IPC transport for calling a **Native Engine** (C++, Rust, Go) running on the same Linux machine.

This is not a replacement for the HTTP or gRPC adapters. It solves a specific problem: calling a compute-intensive local worker (encryption, compression, video transcoding, hashing) without the network stack overhead of TCP.

```text
Python Service  ──UDS──►  Native Engine (C++/Rust/Go)
                  fast        cpu-intensive
```

> **Platform note:** Unix Domain Socket requires Linux (or macOS). The adapter is not available on Windows. Install `msgpack` first: `pip install "xime[socket]"`.

---

## When to Use

| Use UDS (Socket Adapter) | Use gRPC or HTTP |
| --- | --- |
| Same-machine, same-host IPC | Service-to-service across hosts |
| Native Engine (C++/Rust/Go) as a local worker | Standard microservice communication |
| File / binary streaming (encryption, video) | Public APIs |
| Kernel-level security (no TLS needed) | Internet-facing endpoints |

---

## Quick Start

### 1. Write the controller

```python
# api/socket/crypto_controller.py
from xime.core.contract import command, stream, UploadStream, DownloadStream
from pydantic import BaseModel

class HashRequest(BaseModel):
    file_id: str

class HashResponse(BaseModel):
    digest: str

class EncryptRequest(BaseModel):
    name: str

class EncryptResponse(BaseModel):
    total: int    # bytes processed

class DownloadRequest(BaseModel):
    parts: int

class CryptoController:
    server_id = "crypto"     # matches SocketAdapter("crypto")

    def __init__(self, crypto_service: CryptoService) -> None:
        self.crypto_service = crypto_service

    @command("hash")
    async def hash(self, request: HashRequest) -> HashResponse:
        return await self.crypto_service.hash(request)

    @stream("encrypt")
    async def encrypt(self, request: EncryptRequest, upload: UploadStream) -> EncryptResponse:
        return await self.crypto_service.encrypt(request, upload)

    @stream("download")
    async def download(self, request: DownloadRequest, download: DownloadStream) -> None:
        await self.crypto_service.download(request, download)
```

### 2. Register the package

```python
# config/socket.py
from xime.adapters.socket import configure_socket_controllers

configure_socket_controllers("api.socket")
```

Also add `api.socket` to `dependency.scan(...)` in `config/dependency.py` so the DI container creates the controller instance.

### 3. Add the adapter

```python
# main.py
from xime import Application
from xime.adapters.web import WebAdapter
from xime.adapters.socket import SocketAdapter

app = Application()
app.use(WebAdapter())
app.use(SocketAdapter("crypto"))    # listens on /run/xime/crypto.sock
app.run()
```

---

## Endpoint Types

All three types use the same two decorators - the builder determines upload vs. download from the type hint of the stream parameter:

### `@command` - unary request/response

```python
@command("hash")
async def hash(self, request: HashRequest) -> HashResponse:
    ...
```

Client sends a request dict, server returns a response dict.

### `@stream` + `UploadStream` - client-to-server streaming

```python
@stream("encrypt")
async def encrypt(
    self, request: EncryptRequest, upload: UploadStream
) -> EncryptResponse:
    total = 0
    async for chunk in upload:        # iterate over incoming bytes chunks
        total += len(chunk)
    return EncryptResponse(total=total)
```

The client sends a metadata message first, then streams raw bytes. `UploadStream` is an async iterator; you can also call `await upload.read()` for manual chunk-by-chunk reading.

### `@stream` + `DownloadStream` - server-to-client streaming

```python
@stream("download")
async def download(
    self, request: DownloadRequest, download: DownloadStream
) -> None:
    for i in range(request.parts):
        chunk = await file.read(65536)
        await download.write(chunk)
```

The server writes raw bytes; the client receives them as a stream.

---

## Configuration

### `application.yml`

```yaml
socket:
  dir: /run/xime         # directory for auto-named *.sock files
  permission: "0600"     # file permission after bind
  owner: xime-storage    # optional: chown to this user
  group: xime-storage    # optional: chown to this group
  allowed_uids: [1001]   # optional: SO_PEERCRED whitelist; empty = accept all
  session_timeout: 30    # seconds; idle sessions are cleaned up
  max_chunk_size: 1048576  # 1 MiB; oversized chunks are rejected
  recv_queue_size: 16    # per-session buffer depth before backpressure
```

### Socket path resolution

- With `path` in configuration: `process.socket.crypto.path: /var/run/x.sock` → `/var/run/x.sock`.
  ⚠ **The `path` argument was dropped in 0.8** - a path belongs to the pair `(process, adapter)`
- Without `path`: the path is derived from `server_id` - `SocketAdapter("crypto")` → `/run/xime/crypto.sock`

### Multiple socket servers

```python
app.use(SocketAdapter("crypto"))       # → /run/xime/crypto.sock
app.use(SocketAdapter("thumbnail"))    # → /run/xime/thumbnail.sock
```

Each adapter manages a completely independent socket. `server_id` must be unique per adapter type.

---

## Error Mapping

Map business exceptions to error codes the client receives:

```python
# config/socket.py
from xime.adapters.socket import configure_socket_error_mappings

configure_socket_error_mappings({
    NotFoundException:   "NOT_FOUND",
    ValidationException: "INVALID_ARGUMENT",
    AuthException:       "PERMISSION_DENIED",
})
```

Unmapped exceptions become `INTERNAL`. The handler does not crash - only the session that raised the exception is terminated.

---

## Security

Socket Adapter uses **kernel-level security** instead of TLS or tokens. Two layers:

**File permission:** After binding, the socket file is `chmod`'ed and optionally `chown`'ed. Processes running as the wrong user cannot connect - the kernel blocks them at `connect()`.

> ⛔ **Multi-process (`share_load()`): the parent tightens the mode BEFORE `listen()`.**
>
> On that branch the **parent** binds the shared socket and hands it to the
> children, and only a child reads `socket.<id>.permission` - the parent never
> builds DI. Between those two moments there is a **window** that covers a full
> re-import of `main.py`, building DI, opening pools, fetching certificates and
> running `run_once()` (migrations). The framework itself states that window
> **can last 60 seconds**, and from the moment `listen()` returns the socket
> accepts connections.
>
> So the order is **tighten first, widen later**: the parent sets `0600` right
> after `bind()` and before `listen()`, and a child widens it if you declared
> something broader. The parent **refuses to start** if it cannot restrict the
> path - `allowed_uids` defaults to empty, so in that window the file mode is the
> **only** gate.

**SO_PEERCRED:** When a client connects, the server reads the client's UID from the kernel. If `allowed_uids` is configured, connections from unlisted UIDs are dropped immediately before any data is read.

```yaml
socket:
  permission: "0600"
  owner: xime-storage
  allowed_uids: [1001]   # only UID 1001 can connect
```

This model is appropriate for same-host IPC where systemd controls which users each process runs as. You get strong security without any cryptographic overhead.

---

## Python Client SDK

For Python-to-Python IPC. Native Engine clients (C++/Rust/Go) implement the same binary protocol directly.

```python
from xime.adapters.socket import SocketClient

client = SocketClient("/run/xime/crypto.sock")
await client.connect()

# Command
resp = await client.command("hash", HashRequest(file_id="abc"))

# Upload stream
async with client.stream("encrypt", EncryptRequest(name="doc")) as up:
    async with open("file.bin", "rb") as f:
        while chunk := await f.read(65536):
            await up.write(chunk)
    response = await up.finish()

await client.close()
```

The client handles session multiplexing - you can fire multiple `command()` calls concurrently on a single connection and they will not interfere with each other.

---

## Installation

```bash
pip install "xime[socket]"   # adds msgpack
```

---

## Wire Protocol (for Native Engine implementors)

The protocol uses a **16-byte fixed header + payload**:

```text
┌────────┬─────────┬──────────┬──────────────┬─────────────┬───────────────┐
│ MAGIC  │ VERSION │ MSG_TYPE │  SESSION_ID  │ PAYLOAD_LEN │   PAYLOAD     │
│  "XM"  │  0x01   │  1 byte  │  8-byte u64  │  4-byte u32 │  variable     │
└────────┴─────────┴──────────┴──────────────┴─────────────┴───────────────┘
```

- **Envelope** (request/stream start): MessagePack `{"endpoint": "hash", "data": {...}}`
- **Response**: MessagePack `response.model_dump()`
- **Chunk**: raw bytes - no wrapping, minimal overhead
- **Error**: MessagePack `{"code": "NOT_FOUND", "message": "..."}`

Session IDs allow multiple concurrent streams over one connection.

---

[← Starters](starters.md) · **8/9 - Socket Adapter** · [Contributing →](contributing.md)
