# Socket Adapter

[English](../en/socket-adapter.md) | **Tiếng Việt**

[← Starters](starters.md) · **8/9 — Socket Adapter** · [Đóng góp →](contributing.md)

---

Socket Adapter thêm hỗ trợ **Unix Domain Socket (UDS)** cho XIME — một transport IPC
ít overhead cho việc gọi **Native Engine** (C++, Rust, Go) chạy cùng máy Linux.

Đây không phải thay thế cho HTTP hay gRPC adapter. Nó giải quyết một bài toán cụ thể:
gọi một worker nặng về tính toán (mã hoá, nén, xử lý video, hashing) mà không cần
overhead của TCP.

```text
Python Service  ──UDS──►  Native Engine (C++/Rust/Go)
                  nhanh      tính toán nặng
```

> **Lưu ý nền tảng:** Unix Domain Socket yêu cầu Linux (hoặc macOS). Adapter không
> khả dụng trên Windows. Cài `msgpack` trước: `pip install "xime[socket]"`.

---

## Khi nào dùng

| Dùng UDS (Socket Adapter) | Dùng gRPC hoặc HTTP |
| --- | --- |
| IPC cùng máy, cùng host | Giao tiếp service-to-service qua mạng |
| Native Engine (C++/Rust/Go) như local worker | Giao tiếp microservice chuẩn |
| Streaming file / nhị phân (mã hoá, video) | Public API |
| Bảo mật bằng kernel (không cần TLS) | Endpoint hướng ra internet |

---

## Bắt đầu nhanh

### 1. Viết controller

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
    total: int    # bytes đã xử lý

class DownloadRequest(BaseModel):
    parts: int

class CryptoController:
    server_id = "crypto"     # khớp với SocketAdapter("crypto")

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

### 2. Đăng ký package

```python
# config/socket.py
from xime.adapters.socket import configure_socket_controllers

configure_socket_controllers("api.socket")
```

Cũng thêm `api.socket` vào `dependency.scan(...)` trong `config/dependency.py` để DI
container tạo instance controller.

### 3. Thêm adapter

```python
# main.py
from xime import Application
from xime.adapters.web import WebAdapter
from xime.adapters.socket import SocketAdapter

app = Application()
app.use(WebAdapter())
app.use(SocketAdapter("crypto"))    # lắng nghe trên /run/xime/crypto.sock
app.run()
```

---

## Các loại Endpoint

Cả ba loại dùng cùng hai decorator — builder xác định upload hay download từ type hint
của tham số stream:

### `@command` — request/response đơn

```python
@command("hash")
async def hash(self, request: HashRequest) -> HashResponse:
    ...
```

Client gửi request dict, server trả response dict.

### `@stream` + `UploadStream` — client gửi stream lên server

```python
@stream("encrypt")
async def encrypt(
    self, request: EncryptRequest, upload: UploadStream
) -> EncryptResponse:
    total = 0
    async for chunk in upload:        # lặp qua các chunk bytes đến
        total += len(chunk)
    return EncryptResponse(total=total)
```

Client gửi metadata trước, sau đó stream raw bytes. `UploadStream` là async iterator;
có thể dùng `await upload.read()` để đọc từng chunk thủ công.

### `@stream` + `DownloadStream` — server gửi stream về client

```python
@stream("download")
async def download(
    self, request: DownloadRequest, download: DownloadStream
) -> None:
    for i in range(request.parts):
        chunk = await file.read(65536)
        await download.write(chunk)
```

Server ghi raw bytes; client nhận chúng dưới dạng stream.

---

## Cấu hình

### `application.yml`

```yaml
socket:
  dir: /run/xime           # thư mục chứa file *.sock tự sinh tên
  permission: "0600"       # quyền file sau khi bind
  owner: xime-storage      # optional: chown sang user này
  group: xime-storage      # optional: chown sang group này
  allowed_uids: [1001]     # optional: whitelist SO_PEERCRED; rỗng = chấp nhận mọi UID
  session_timeout: 30      # giây; session không hoạt động được dọn dẹp
  max_chunk_size: 1048576  # 1 MiB; chunk quá lớn bị từ chối
  recv_queue_size: 16      # độ sâu buffer mỗi session trước khi backpressure
```

### Xác định đường dẫn socket

- Truyền `path` tường minh: `SocketAdapter("crypto", path="/var/run/x.sock")` → `/var/run/x.sock`
- Không truyền `path`: suy từ `server_id` — `SocketAdapter("crypto")` → `/run/xime/crypto.sock`

### Nhiều socket server

```python
app.use(SocketAdapter("crypto"))       # → /run/xime/crypto.sock
app.use(SocketAdapter("thumbnail"))    # → /run/xime/thumbnail.sock
```

Mỗi adapter quản lý socket hoàn toàn độc lập. `server_id` phải duy nhất theo loại adapter.

---

## Error Mapping

Ánh xạ exception nghiệp vụ sang mã lỗi client nhận được:

```python
# config/socket.py
from xime.adapters.socket import configure_socket_error_mappings

configure_socket_error_mappings({
    NotFoundException:   "NOT_FOUND",
    ValidationException: "INVALID_ARGUMENT",
    AuthException:       "PERMISSION_DENIED",
})
```

Exception không được ánh xạ → `INTERNAL`. Handler không crash — chỉ session gây lỗi
đó bị kết thúc.

---

## Bảo mật

Socket Adapter dùng **bảo mật kernel** thay vì TLS hoặc token. Hai lớp:

**File permission:** Sau khi bind, socket file được `chmod` và tuỳ chọn `chown`. Process
chạy sai user không thể kết nối — kernel chặn ngay tại `connect()`.

**SO_PEERCRED:** Khi client kết nối, server đọc UID client từ kernel. Nếu `allowed_uids`
được cấu hình, kết nối từ UID không có trong danh sách bị từ chối ngay trước khi đọc bất
kỳ dữ liệu nào.

```yaml
socket:
  permission: "0600"
  owner: xime-storage
  allowed_uids: [1001]   # chỉ UID 1001 được kết nối
```

Mô hình này phù hợp cho IPC cùng host nơi systemd kiểm soát user mỗi process chạy dưới.
Bạn có bảo mật mạnh mà không cần overhead mã hoá.

---

## Python Client SDK

Dành cho Python-to-Python IPC. Native Engine (C++/Rust/Go) tự implement cùng binary
protocol.

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

Client xử lý session multiplexing — có thể gọi nhiều `command()` đồng thời trên một
connection mà chúng không can thiệp lẫn nhau.

---

## Cài đặt

```bash
pip install "xime[socket]"   # thêm msgpack
```

---

## Wire Protocol (cho người implement Native Engine)

Protocol dùng **header cố định 16 byte + payload**:

```text
┌────────┬─────────┬──────────┬──────────────┬─────────────┬───────────────┐
│ MAGIC  │ VERSION │ MSG_TYPE │  SESSION_ID  │ PAYLOAD_LEN │   PAYLOAD     │
│  "XM"  │  0x01   │  1 byte  │  8-byte u64  │  4-byte u32 │  variable     │
└────────┴─────────┴──────────┴──────────────┴─────────────┴───────────────┘
```

- **Envelope** (request/stream start): MessagePack `{"endpoint": "hash", "data": {...}}`
- **Response**: MessagePack `response.model_dump()`
- **Chunk**: raw bytes — không wrapper, overhead tối thiểu
- **Error**: MessagePack `{"code": "NOT_FOUND", "message": "..."}`

Session ID cho phép nhiều stream đồng thời trên một connection.

---

[← Starters](starters.md) · **8/9 — Socket Adapter** · [Đóng góp →](contributing.md)
