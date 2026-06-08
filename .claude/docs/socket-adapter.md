# Thiết kế — Socket Adapter (Xime Framework)

> Tài liệu thiết kế triển khai. Snippet code dùng định danh tiếng Anh; diễn giải
> bằng tiếng Việt. Comment trong code thực tế tuân quy ước "English ở trên, tiếng
> Việt ở dưới".

---

## 1. Mục tiêu & Phạm vi

Socket Adapter là **transport layer** cho **Local IPC** (Inter-Process Communication)
giữa các process trên **cùng một máy Linux**, thông qua **Unix Domain Socket (UDS)**.

Mục tiêu: cho phép một Xime Service (Python) gọi sang **Native Engine** (C++/Rust/Go)
xử lý tác vụ nặng (encryption, compression, hashing, thumbnail, video) mà:

- Developer chỉ làm việc với `@command`, `@stream`, Request/Response DTO, `UploadStream`, `DownloadStream`.
- Framework che giấu toàn bộ socket, framing, serialization, session, dispatch —
  giống cách WebAdapter che giấu FastAPI và GrpcAdapter che giấu grpc.aio.

### Phạm vi v1

| Có trong v1 | KHÔNG có trong v1 |
|---|---|
| Unix Domain Socket (Linux) | TCP / TCP-localhost transport |
| Command endpoint (request → response) | Named Pipe / Windows support |
| Upload stream (metadata + stream → response) | Bidirectional stream đồng thời 2 chiều |
| Download stream (metadata → response stream) | Credit-based flow control |
| Multi-server theo `server_id` | Reconnect / retry tự động |
| Bảo mật bằng file permission + SO_PEERCRED | TLS / token |
| Session multiplex trên 1 connection | Distributed session |

### Vì sao không dùng gRPC cho việc này

`Microservice ≠ Native Engine`. gRPC tối ưu cho `Service ↔ Service` (TCP, HTTP/2,
proto, distributed). Native Engine bản chất giống FFmpeg/ImageMagick: `Input →
Process → Output`. Với nó:

- **Ít tầng hơn:** `Python → UDS → C++` thay vì `Python → TCP → HTTP/2 → proto → C++`.
- **Ít copy, ít overhead, latency thấp** trên cùng máy.
- **Bảo mật bằng kernel Linux** (file permission, `SO_PEERCRED`) thay vì TLS/token.

gRPC vẫn là lựa chọn chính cho Service ↔ Service. Socket Adapter **bổ sung**, không
thay thế.

---

## 2. Vị trí trong Framework

Socket là transport layer, ngang hàng WebAdapter và GrpcAdapter — **không phải starter**.

```text
xime/adapters/socket/
├── __init__.py          # export công khai: SocketAdapter, configure_*
├── _adapter.py          # SocketAdapter — vòng đời, accept loop, dispatch
├── _config.py           # SocketServerConfig + registry + configure_*
├── _protocol.py         # MessageType, Frame, encode_frame, read_frame
├── _session.py          # Session, SessionManager, ConnectionWriter
├── _peercred.py         # read_peer_cred, authorize_peer, secure_socket_file
└── _client.py           # SocketClient SDK (Python ↔ Python)
```

**Lưu ý quan trọng:** `@command`, `@stream`, `UploadStream`, `DownloadStream`,
`ControllerScanner` KHÔNG nằm trong `adapters/socket/routing/` như thiết kế ban đầu.
Chúng được chuyển vào **`xime/core/contract/`** để dùng chung với Code-First gRPC.

```text
xime/core/contract/
├── __init__.py          # export: command, stream, UploadStream, DownloadStream, ControllerScanner
├── _decorators.py       # @command, @stream, EndpointInfo, ENDPOINT_ATTR="_xime_endpoint"
├── _scanner.py          # ControllerScanner (tìm ENDPOINT_ATTR)
└── _streams.py          # UploadStream, DownloadStream (abstract base)
```

---

## 3. Kiến trúc tổng quan

```text
         CLIENT (Python Service)                  SERVER (SocketAdapter)
         ──────────────────────                   ───────────────────────
business → SocketClient.command()/stream()
                  │ encode frame
                  ▼
         ┌─────────────────┐  Unix Domain  ┌──────────────────────────┐
         │ /run/xime/*.sock ◄──────────────► asyncio.start_unix_server │
         └─────────────────┘   Socket       └───────────┬──────────────┘
                                                        │ 1 read loop / connection
                                                        ▼
                                           ┌──────────────────────────┐
                                           │ SessionManager             │
                                           │ demux frame → Session      │
                                           │ {session_id: asyncio.Queue}│
                                           └───────────┬──────────────┘
                                                       ▼
                                           EndpointTable.lookup(endpoint)
                                                       ▼
                                           Controller (DI singleton)
                                                       ▼
                                           Service → Repository
```

---

## 4. Vòng đời Adapter

`SocketAdapter` tuân theo `Adapter` Protocol: `async def start(app)` (blocking đến
khi stop) và `async def stop()` (idempotent).

```python
app = Application()
app.use(WebAdapter())             # HTTP public API
app.use(GrpcAdapter("internal"))  # service ↔ service
app.use(SocketAdapter("crypto"))  # ↔ crypto-engine
app.use(SocketAdapter("thumbnail"))
app.run()
```

- `start(app)` được gọi **sau khi DI container đã build xong**.
- `Application.use()` chặn trùng `(type, server_id)` — hai `SocketAdapter` cùng
  `server_id` sẽ báo lỗi.
- Shutdown LIFO: `SocketAdapter.stop()` → cleanup file socket.

---

## 5. Cấu hình

### 5.1 Quy tắc Socket Path

- Có `path` → dùng path đó.
- Không có `path` → sinh từ `server_id`: `{socket.dir}/{server_id}.sock`.
  - `socket.dir` đọc từ `application.yml`, mặc định `/run/xime`.

```text
SocketAdapter("crypto")                          → /run/xime/crypto.sock
SocketAdapter("crypto", path="/var/run/x.sock")  → /var/run/x.sock
```

### 5.2 Runtime config — `application.yml`

```yaml
socket:
  dir: /run/xime
  permission: "0600"
  owner: xime-storage    # optional
  group: xime-storage    # optional
  allowed_uids: [1001]   # rỗng = chấp nhận mọi UID
  session_timeout: 30
  max_chunk_size: 1048576
  recv_queue_size: 16
```

### 5.3 Đăng ký Controller — `configure_socket_controllers`

```python
# config/socket.py
from xime.adapters.socket import configure_socket_controllers

configure_socket_controllers("api.socket")
```

Registry module-level singleton (giống các adapter khác). Package cũng phải trong
`dependency.scan(...)` để DI tạo instance.

```python
# Cũng đăng ký error mapping nếu cần
from xime.adapters.socket import configure_socket_error_mappings

configure_socket_error_mappings({
    NotFoundException:   "NOT_FOUND",
    ValidationException: "INVALID_ARGUMENT",
})
```

---

## 6. Controller Model & Decorators

```python
class CryptoController:
    server_id = "crypto"

    def __init__(self, crypto_service: CryptoService):
        self.crypto_service = crypto_service

    @command("hash")
    async def hash(self, request: HashRequest) -> HashResponse:
        return await self.crypto_service.hash(request)

    @stream("encrypt")
    async def encrypt(
        self, request: EncryptFileRequest, upload: UploadStream
    ) -> EncryptFileResponse:
        return await self.crypto_service.encrypt(request, upload)

    @stream("download")
    async def download(
        self, request: DownloadFileRequest, download: DownloadStream
    ) -> None:
        await self.crypto_service.download(request, download)
```

### Decorators (`core/contract/_decorators.py`)

```python
ENDPOINT_ATTR = "_xime_endpoint"   # chung với Code-First gRPC

@dataclass
class EndpointInfo:
    name: str
    kind: EndpointKind   # COMMAND hoặc STREAM
```

`@stream` không phân biệt upload/download tại khai báo — **builder suy ra từ type hint**:

| Loại | Chữ ký | Nhận biết |
|---|---|---|
| **Command** | `(self, request: Req) -> Resp` | `@command` |
| **Upload** | `(self, request: Req, upload: UploadStream) -> Resp` | `@stream` + param `UploadStream` |
| **Download** | `(self, request: Req, download: DownloadStream) -> None` | `@stream` + param `DownloadStream` |

---

## 7. Protocol nội bộ (`_protocol.py`)

### Frame header — 16 byte cố định

```text
┌────────┬─────────┬──────────┬─────────────────┬─────────────┬───────────────┐
│ MAGIC  │ VERSION │ MSG_TYPE │   SESSION_ID     │ PAYLOAD_LEN │   PAYLOAD     │
│ 2 byte │  1 byte │  1 byte  │   8 byte u64     │  4 byte u32 │  PAYLOAD_LEN  │
└────────┴─────────┴──────────┴─────────────────┴─────────────┴───────────────┘
   "XM"      0x01                  big-endian       big-endian     bytes
```

```python
MAGIC = b"XM"
VERSION = 1
HEADER_FORMAT = ">2sBBQI"    # = 16 bytes
```

### Message types

```python
class MessageType(enum.IntEnum):
    COMMAND_REQUEST  = 1   # client→server, payload = envelope msgpack
    COMMAND_RESPONSE = 2   # server→client, payload = data msgpack
    STREAM_START     = 3   # client→server, payload = envelope msgpack
    STREAM_CHUNK     = 4   # 2 chiều, payload = raw bytes
    STREAM_END       = 5   # báo hết chunk, payload rỗng
    STREAM_RESPONSE  = 6   # server→client sau upload, payload msgpack
    ERROR            = 7   # payload = {code, message} msgpack
    CANCEL           = 8   # huỷ session, payload rỗng
```

### Quy ước payload

- **Envelope** (COMMAND_REQUEST, STREAM_START): MessagePack `{"endpoint": "<name>", "data": {...}}`.
- **Response** (COMMAND_RESPONSE, STREAM_RESPONSE): MessagePack `response.model_dump()`.
- **Chunk** (STREAM_CHUNK): **raw bytes** — không msgpack, tránh overhead.
- **Error**: MessagePack `{"code": "<CODE>", "message": "<str>"}`.

`msgpack` là optional dependency (`xime[socket]`). `start()` raise `RuntimeError`
hướng dẫn cài nếu thiếu.

---

## 8. Session Manager & Async Dispatch

Đây là trái tim của adapter. Bài toán: **một connection** chạy **nhiều stream
đồng thời** (encrypt=101, thumbnail=202). Khi `STREAM_CHUNK(session=101)` tới,
nó phải vào đúng coroutine handler đang `await upload.read()`.

### Cốt lõi: `{session_id: asyncio.Queue}`

> **Một read loop cho mỗi connection** đọc tuần tự từng frame và **demux** theo
> `session_id` vào `asyncio.Queue` riêng của session. Handler khi `await
> upload.read()` thực chất đang `await queue.get()`.

### Session, SessionManager (`_session.py`)

```python
_END = object()             # sentinel: hết chunk
class _ErrorSignal:         # bọc exception đẩy vào queue

class Session:
    session_id: int
    queue: asyncio.Queue
    task: asyncio.Task | None
    last_active: float

class SessionManager:
    def create(self, session_id) → Session
    def get(self, session_id) → Session | None      # cập nhật last_active
    def destroy(self, session_id)                   # cancel task
    def destroy_all()
    def reap_expired()                              # đẩy _ErrorSignal rồi destroy
```

### ConnectionWriter — serialize ghi frame

```python
class ConnectionWriter:
    # asyncio.Lock + drain() — tránh chèn frame, có backpressure miễn phí
    async def send(self, msg_type, session_id, payload=b"") -> None
```

### Backpressure & Head-of-line (quyết định v1)

Queue bị giới hạn (`recv_queue_size`). Khi handler xử lý chậm, queue đầy →
`await queue.put()` trong read loop **chặn cả connection** (các session khác
cũng bị). Đây là **head-of-line blocking** — chấp nhận ở v1 vì mô hình Native
Engine thường mở một connection cho mỗi job nặng. Hướng nâng cấp v2: credit-based
flow control per-session.

---

## 9. Bảo mật Linux (`_peercred.py`)

Hai lớp phòng thủ:

1. **File permission** (sau khi bind): `chmod 0600`, `chown xime-storage` → kernel
   chặn process không đúng user ngay ở `connect()`.

2. **SO_PEERCRED** — server tự xác minh UID client ngay khi accept:

```python
def read_peer_cred(writer) -> tuple[int, int, int]:   # (pid, uid, gid)
    sock = writer.get_extra_info("socket")
    raw = sock.getsockopt(SOL_SOCKET, SO_PEERCRED, ...)
    return struct.unpack("3i", raw)

def authorize_peer(writer, allowed_uids) -> bool:
    pid, uid, gid = read_peer_cred(writer)
    request_context.set("peer_pid", pid)   # cho audit/logging
    request_context.set("peer_uid", uid)
    if not allowed_uids:
        return True    # rỗng = chấp nhận mọi UID (đã có file perm)
    return uid in allowed_uids
```

---

## 10. Vòng đời Socket Path (`start`/`stop`)

```python
async def start(self, app):
    # 1) Kiểm tra msgpack
    # 2) Resolve config (path, perm, timeout...)
    # 3) mkdir thư mục socket
    # 4) Xoá socket cũ (stale)
    # 5) Build EndpointTable từ controller (DI đã sẵn)
    # 6) asyncio.start_unix_server
    # 7) secure_socket_file (chmod + chown)
    # 8) Spawn reaper task
    # 9) serve_forever()  ← block

async def stop(self):
    # cancel reaper, close server, xoá socket file (idempotent)
```

---

## 11. Client SDK Python (`_client.py`)

Cho phía Python ↔ Python. Native Engine C++/Rust/Go tự implement cùng protocol.

```python
client = SocketClient("/run/xime/crypto.sock")
await client.connect()

# Command
resp = await client.command("hash", HashRequest(file_id="f1"))

# Upload stream
async with client.stream("encrypt", EncryptFileRequest(...)) as up:
    while chunk := await file.read(65536):
        await up.write(chunk)
    response = await up.finish()
```

`_read_loop` client demux y như server: COMMAND_RESPONSE → set `Future`;
STREAM_CHUNK (download) → đẩy vào inbound queue; ERROR → set exception.

---

## 12. Quyết định thiết kế & Tradeoff

1. **Chỉ UDS, chỉ Linux (v1).** Interface `Transport` mỏng để sau cộng đồng cắm TCP/Named Pipe.
2. **Frame header 16 byte + payload.** Đơn giản, đủ cho IPC. MessagePack cho envelope/response, raw bytes cho chunk.
3. **`{session_id: asyncio.Queue}` + một read loop/connection.** Đơn giản, đúng, dễ debug. Đánh đổi: head-of-line blocking — chấp nhận v1.
4. **Ghi frame qua `asyncio.Lock` + `drain()`.** Tránh chèn frame, backpressure miễn phí.
5. **Bảo mật bằng kernel (file perm + SO_PEERCRED), không TLS/token.** Đúng bản chất Local IPC.
6. **Explicit config, không auto-scan** (tuân `rules/config-discovery.md`).
7. **`@command`/`@stream` dùng chung với Code-First gRPC** (`core/contract/`) — một Controller, nhiều transport.

---

## 13. Lộ trình tương lai

- Credit-based flow control per-session (bỏ head-of-line).
- `Transport` trừu tượng → TCP / Named Pipe (cộng đồng đóng góp).
- Bidirectional stream.
- Sinh Contract Model dùng chung với Code-First gRPC → một Controller → Socket + gRPC proto.
- Client SDK đa ngôn ngữ generate từ Contract Model.
