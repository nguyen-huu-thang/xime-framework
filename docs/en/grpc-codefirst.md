# Code-First gRPC

**English** | [Tiếng Việt](../vn/grpc-codefirst.md)

[← Routing](routing.md) · **7/9 — Code-First gRPC** · [Starters →](starters.md)

---

XIME supports two gRPC development modes:

- **Proto-First** (existing) — you write `.proto` files, XIME serves your handwritten servicers.
- **Code-First** (this page) — you write Python controllers and DTOs, XIME generates the `.proto` files for you.

With Code-First, your Python code is the **single source of truth**. You never write or maintain `.proto` files manually.

```
Controller + DTO  →  xime grpc generate  →  .proto + Python stubs
                                              ↓
                                         GrpcAdapter serves it
```

> **Requires:** `pip install "xime[grpc]"` (adds `grpcio`, `grpcio-tools`, `protobuf`)

---

## Why Code-First?

Two problems with proto-first at scale:

1. **Drift** — you update a Pydantic DTO but forget to update the `.proto`. The two diverge silently.
2. **Duplication** — every field is defined twice: once in Python, once in protobuf.

Code-First eliminates both. The proto is generated from your Python types — it cannot drift, and there is nothing to duplicate.

---

## Quick Start

### 1. Write the controller

```python
# api/grpc/crypto_controller.py
from xime.core.contract import command, stream, UploadStream, DownloadStream
from pydantic import BaseModel

class HashRequest(BaseModel):
    file_id: str

class HashResponse(BaseModel):
    digest: str

class EncryptRequest(BaseModel):
    name: str

class EncryptResponse(BaseModel):
    total: int

class DownloadRequest(BaseModel):
    parts: int

class CryptoController:
    server_id = "public"   # matches GrpcAdapter("public") or default

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
# config/grpc.py
from xime.adapters.grpc.codefirst import configure_grpc_codefirst

configure_grpc_codefirst(
    packages=["api.grpc"],
    output_dir="generated",
    lock_file="proto.lock.json",
)
```

### 3. Generate `.proto` files

```bash
xime grpc generate
```

This produces:

```
generated/
└── public/
    ├── crypto.proto
    └── crypto_pb2.py
    └── crypto_pb2_grpc.py
```

and creates `proto.lock.json` (commit this to git).

### 4. Run the app

```python
# main.py
from xime import Application
from xime.adapters.grpc import GrpcAdapter

app = Application()
app.use(GrpcAdapter())
app.run()
```

`GrpcAdapter` automatically detects and serves all code-first controllers configured via `configure_grpc_codefirst`.

---

## Endpoint Types

The same two decorators from Socket Adapter work here — the same controller can serve both gRPC and UDS if you register it for both.

### `@command` — unary RPC

```python
@command("hash")
async def hash(self, request: HashRequest) -> HashResponse: ...
```

Generated proto:

```protobuf
rpc Hash(HashRequest) returns (HashResponse);
```

### `@stream` + `UploadStream` — client streaming

```python
@stream("encrypt")
async def encrypt(self, request: EncryptRequest, upload: UploadStream) -> EncryptResponse:
    total = 0
    async for chunk in upload:
        total += len(chunk)
    return EncryptResponse(total=total)
```

Generated proto uses a `oneof` wrapper — the first message carries metadata, subsequent messages carry raw bytes:

```protobuf
message EncryptChunk {
    oneof payload {
        EncryptRequest metadata = 1;
        bytes          chunk    = 2;
    }
}

rpc Encrypt(stream EncryptChunk) returns (EncryptResponse);
```

Your business code never sees `EncryptChunk`. XIME handles the marshalling.

### `@stream` + `DownloadStream` — server streaming

```python
@stream("download")
async def download(self, request: DownloadRequest, download: DownloadStream) -> None:
    for i in range(request.parts):
        await download.write(f"part{i}".encode())
```

Generated proto:

```protobuf
message DownloadChunk { bytes chunk = 1; }

rpc Download(DownloadRequest) returns (stream DownloadChunk);
```

---

## Field Number Stability

> This is the most important thing about Code-First gRPC.

Protobuf identifies fields by **number**, not name. If the generator reassigns numbers when regenerating, old clients silently misread responses — a hard-to-debug corruption.

XIME solves this with `proto.lock.json`:

```json
{
  "messages": {
    "HashRequest": {
      "fields": { "file_id": 1 },
      "reserved_numbers": [],
      "reserved_names": []
    }
  }
}
```

**Rules:**
- Fields already in the lock keep their number forever.
- New fields get the next available number, skipping reserved ones.
- Deleted fields become `reserved` — their number is never reused.

**Commit `proto.lock.json` to git.** It is part of your source of truth.

```protobuf
// If you delete "email" from UserResponse:
message UserResponse {
    reserved 3;       // "email" was field 3
    reserved "email";
    int64  id = 1;
    string username = 2;
    string role = 4;
}
```

---

## Type Mapping

| Python | Proto | Notes |
|---|---|---|
| `str` | `string` | |
| `bytes` | `bytes` | |
| `bool` | `bool` | |
| `int` | `int64` | default; override with `Annotated` |
| `float` | `double` | |
| `list[T]` | `repeated <T>` | |
| `dict[K, V]` | `map<K, V>` | K must be scalar |
| `Optional[T]` / `T \| None` | `optional <T>` | proto3 explicit presence |
| `datetime.datetime` | `google.protobuf.Timestamp` | |
| `Decimal` | `string` | avoids precision loss |
| `UUID` | `string` | |
| `IntEnum` / `StrEnum` | `enum` | members become enum values |
| nested `BaseModel` | `message <Name>` | |

**Override integer type** with `Annotated`:

```python
from typing import Annotated
from xime.adapters.grpc.codefirst import ProtoInt32, ProtoUInt64

class Page(BaseModel):
    size:  Annotated[int, ProtoInt32]   # → int32
    cursor: Annotated[int, ProtoUInt64] # → uint64
```

Unsupported types raise `UnsupportedTypeError` at generate time, not at runtime.

---

## Shared DTOs → `common.proto`

When a DTO is used by two or more controllers in the same `server_id`, XIME places it in `common.proto` automatically:

```
generated/public/
├── crypto.proto     # imports common.proto
├── user.proto       # imports common.proto
└── common.proto     # shared: UserResponse, PageInfo, ...
```

---

## CLI

### Generate

```bash
xime grpc generate           # generate .proto + run protoc
xime grpc generate --no-protoc  # only generate .proto files (skip protoc)
```

### Check (use in CI)

```bash
xime grpc check
```

Compares the proto that *would* be generated against what is on disk. Exits with code 1 if anything differs. Use this as a CI gate to catch "DTO changed but proto not regenerated":

```
Proto Out Of Date
  File: generated/public/crypto.proto
  Hint: run `xime grpc generate`
```

---

## Multi-Server

Just like the HTTP and gRPC proto-first adapters, code-first controllers are routed to the correct server by `server_id`:

```python
class PublicCryptoController:
    server_id = "public"      # served by GrpcAdapter() or GrpcAdapter("public")
    ...

class InternalCryptoController:
    server_id = "internal"    # served by GrpcAdapter("internal", port=50052)
    ...
```

```python
app.use(GrpcAdapter())                         # serves server_id="public"
app.use(GrpcAdapter("internal", port=50052))   # serves server_id="internal"
```

---

## Coexistence with Proto-First

Code-First and proto-first servicers can live in the same `GrpcAdapter`. Configure each independently:

```python
# config/grpc.py — proto-first
from xime.adapters.grpc import configure_grpc_services
configure_grpc_services("api.grpc.proto_first")

# config/grpc_codefirst.py — code-first
from xime.adapters.grpc.codefirst import configure_grpc_codefirst
configure_grpc_codefirst(packages=["api.grpc.codefirst"])
```

---

## Installation

```bash
pip install "xime[grpc]"   # adds grpcio, grpcio-tools, protobuf
```

---

[← Routing](routing.md) · **7/9 — Code-First gRPC** · [Starters →](starters.md)
