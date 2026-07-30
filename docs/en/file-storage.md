# File Storage

**English** | [Tiếng Việt](../vn/file-storage.md)

[← OPC UA Adapter](opcua.md) · **File Storage** · [Testing →](testing.md)

---

XIME's file support has two parts that work together:

1. **`StorageService`** - a backend-neutral object/blob store contract (a `Protocol`), with two ready backends: **local filesystem** and **S3 / MinIO**.
2. **Web file helpers** (`xime.adapters.web.files`) - stream stored objects to/from HTTP without buffering, honouring HTTP **Range** downloads and chunked, size-capped uploads.

Business code depends only on `StorageService`; swapping local ⇆ S3 is a one-line binding change. Objects are raw `bytes` (or raw byte streams) - the framework imposes no naming, authorization, content-type, or encoding policy.

---

## The `StorageService` Contract

```python
from collections.abc import AsyncIterator
from xime.starters.storage import StorageService, StorageStat

class StorageService(Protocol):
    async def put(self, key, data: bytes, *, content_type=None) -> None: ...
    async def get(self, key) -> bytes | None: ...
    def open_stream(self, key, *, offset=0, length=None) -> AsyncIterator[bytes]: ...
    async def put_stream(self, key, chunks: AsyncIterator[bytes], *, content_type=None) -> None: ...
    async def delete(self, key) -> None: ...
    async def exists(self, key) -> bool: ...
    async def stat(self, key) -> StorageStat | None: ...   # size / content_type / etag
    async def url(self, key, *, expires=None) -> str: ...   # presigned URL (where supported)
```

Two access shapes by design:

| Shape | Methods | Use for |
| --- | --- | --- |
| Whole-object | `put` / `get` | small objects, convenient bytes in/out |
| Streaming | `put_stream` / `open_stream` | large objects that must not be fully buffered in memory |

`open_stream` takes `offset` / `length` to serve a byte range (used by HTTP Range downloads). Note it is **not** `async def` - it returns an async iterator directly, so call it as `async for chunk in storage.open_stream(key): ...`.

### Key contract (all backends)

`key` is a backend-relative identifier (e.g. `"avatars/u123.png"`). **Every backend** rejects empty, absolute, and traversal (`..`) keys identically (`storage._keys.validate_object_key`), so switching backend never changes which keys are accepted.

---

## Local Filesystem Backend — `xime.starters.localfs`

```python
# config/dependency.py
from xime.starters.storage import StorageService
from xime.starters.localfs import LocalFileStorage

dependency.scan("xime.starters.localfs")
dependency.bind({ StorageService: LocalFileStorage })
```

```yaml
# resources/application.yml
storage:
  local:
    root: /var/lib/myapp/objects   # required - missing it fails fast at startup
```

- **Atomic writes:** `put_stream` stages to a `.part` temp file then `os.replace`, so a reader never sees a half-written object.
- **Path-traversal guard:** keys are rejected if they would escape `root` (including via symlinks, checked after `realpath`).
- **No blocking event loop:** file IO runs in worker threads (`asyncio.to_thread`) - no `aiofiles` dependency, no extra install needed.
- `url()` raises `UnsupportedOperation` - serve files via the web helper below.

---

## S3 / MinIO Backend — `xime.starters.s3`

Install with `pip install "xime[s3]"` (adds `aioboto3`).

```python
# config/dependency.py
from xime.starters.storage import StorageService
from xime.starters.s3 import S3FileStorage

dependency.scan("xime.starters.s3")
dependency.bind({ StorageService: S3FileStorage })
```

```yaml
# resources/application.yml
storage:
  s3:
    bucket: my-bucket            # required
    region: us-east-1            # optional
    endpoint_url: http://minio:9000   # optional (MinIO / S3-compatible)
    access_key: ...              # optional (else from env / instance role)
    secret_key: ...
    addressing_style: path       # optional: "path" (MinIO) | "virtual"
```

- `S3ClientProvider` owns the async client lifecycle: it opens in `PostConstruct` and closes in `PreDestroy`.
- `put_stream` uses **multipart upload** (5 MiB parts, aborted on any error so no dangling upload is left).
- `open_stream` issues a **ranged GET**.
- `url()` returns a **presigned URL** (default 3600s; pass `expires=`).
- `aioboto3` is imported lazily, so the starter module stays importable without the extra.

---

## Streaming over HTTP — `xime.adapters.web.files`

Two helper functions, called from inside a controller (they are NOT DI components):

```python
from fastapi import Request, UploadFile
from xime.adapters.web.routing import get, post
from xime.adapters.web.files import stream_object, save_upload, PayloadTooLarge
from xime.starters.storage import StorageService

class FileController:
    def __init__(self, storage: StorageService) -> None:
        self._storage = storage

    @get("/files/{key:path}")
    async def download(self, key: str, request: Request):
        return await stream_object(self._storage, key, request=request)

    @post("/files/{key:path}")
    async def upload(self, key: str, file: UploadFile):
        await save_upload(self._storage, key, file, max_bytes=50 * 1024 * 1024)
        return {"key": key}
```

### `stream_object(storage, key, *, request=None, filename=None, content_type=None, download=False)`

- Looks up metadata via `stat()`; a missing object yields **404**.
- With a satisfiable `Range` header → **206 Partial Content** + `Content-Range`; otherwise a full **200** stream.
- A malformed `Range` header is **ignored** (full 200, per RFC 7233); a syntactically-valid but unsatisfiable range → **416** with `Content-Range: */<total>`.
- Sets `Accept-Ranges`, `Content-Length`, `ETag` (when known), and `Content-Disposition` (`inline`, or `attachment` when `download=True` and a `filename` is given).
- Reads lazily from `open_stream` - large objects never load fully into memory.

### `save_upload(storage, key, upload_file, *, max_bytes=None, content_type=None)`

- Streams the `UploadFile` in chunks straight into `put_stream` - never fully buffered.
- If the running total exceeds `max_bytes`, raises `PayloadTooLarge` (HTTP **413**) before the whole body is read. The partial object is cleaned up (local `.part` removed; S3 multipart aborted).
- Returns the number of bytes written.

---

## Switching Backend

Because business code (and the controller) depend only on `StorageService`, moving from local to S3 - or to an in-memory fake in tests - is a one-line binding change:

```python
# Production (cloud): S3 / MinIO
dependency.bind({ StorageService: S3FileStorage })

# Local / single-node deployment
dependency.bind({ StorageService: LocalFileStorage })

# Testing: a fake that satisfies the StorageService Protocol
dependency.bind({ StorageService: InMemoryStorage })
```

---

## Installation

```bash
# local filesystem backend - no extra needed (ships with xime)
pip install "xime[s3]"   # S3 / MinIO backend (adds aioboto3)
```

---

[← OPC UA Adapter](opcua.md) · **File Storage** · [Testing →](testing.md)
