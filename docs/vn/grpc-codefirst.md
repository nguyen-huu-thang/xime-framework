# Code-First gRPC

[English](../en/grpc-codefirst.md) | **Tiếng Việt**

[← Routing](routing.md) · **7/9 — Code-First gRPC** · [Starters →](starters.md)

---

XIME hỗ trợ hai chế độ phát triển gRPC:

- **Proto-First** (có sẵn) — bạn viết file `.proto`, XIME phục vụ servicer của bạn.
- **Code-First** (trang này) — bạn viết Python controller và DTO, XIME sinh file `.proto` cho bạn.

Với Code-First, Python code là **nguồn chân lý duy nhất**. Bạn không bao giờ phải viết
hay duy trì file `.proto` thủ công.

```text
Controller + DTO  →  xime grpc generate  →  .proto + Python stubs
                                              ↓
                                         GrpcAdapter phục vụ
```

> **Yêu cầu:** `pip install "xime[grpc]"` (thêm `grpcio`, `grpcio-tools`, `protobuf`)

---

## Tại sao dùng Code-First?

Hai vấn đề của proto-first ở quy mô lớn:

1. **Drift** — bạn cập nhật Pydantic DTO nhưng quên cập nhật `.proto`. Hai file lệch
   nhau mà không ai hay.
2. **Trùng lặp** — mỗi field phải định nghĩa hai lần: một lần trong Python, một lần
   trong protobuf.

Code-First loại bỏ cả hai. Proto được sinh từ type Python — không thể drift, và không
có gì để trùng lặp.

---

## Bắt đầu nhanh

### 1. Viết controller

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
    server_id = "public"   # khớp với GrpcAdapter("public") hoặc default

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
# config/grpc.py
from xime.adapters.grpc.codefirst import configure_grpc_codefirst

configure_grpc_codefirst(
    packages=["api.grpc"],
    output_dir="generated",
    lock_file="proto.lock.json",
)
```

### 3. Sinh file `.proto`

```bash
xime grpc generate
```

Lệnh này tạo ra:

```text
generated/
└── public/
    ├── crypto.proto
    ├── crypto_pb2.py
    └── crypto_pb2_grpc.py
```

và tạo `proto.lock.json` (commit file này vào git).

### 4. Chạy app

```python
# main.py
from xime import Application
from xime.adapters.grpc import GrpcAdapter

app = Application()
app.use(GrpcAdapter())
app.run()
```

`GrpcAdapter` tự động phát hiện và phục vụ tất cả controller code-first đã cấu hình qua
`configure_grpc_codefirst`.

---

## Các loại Endpoint

Cùng hai decorator với Socket Adapter — một controller có thể phục vụ cả gRPC lẫn UDS
nếu bạn đăng ký cho cả hai.

### `@command` — RPC đơn

```python
@command("hash")
async def hash(self, request: HashRequest) -> HashResponse: ...
```

Proto sinh ra:

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

Proto sinh ra dùng wrapper `oneof` — message đầu chứa metadata, các message sau chứa raw
bytes:

```protobuf
message EncryptChunk {
    oneof payload {
        EncryptRequest metadata = 1;
        bytes          chunk    = 2;
    }
}

rpc Encrypt(stream EncryptChunk) returns (EncryptResponse);
```

Business code không bao giờ thấy `EncryptChunk`. XIME xử lý marshalling.

### `@stream` + `DownloadStream` — server streaming

```python
@stream("download")
async def download(self, request: DownloadRequest, download: DownloadStream) -> None:
    for i in range(request.parts):
        await download.write(f"part{i}".encode())
```

Proto sinh ra:

```protobuf
message DownloadChunk { bytes chunk = 1; }

rpc Download(DownloadRequest) returns (stream DownloadChunk);
```

---

## Ổn định Field Number

> Đây là điều quan trọng nhất về Code-First gRPC.

Protobuf xác định field bằng **số**, không phải tên. Nếu generator gán lại số khi
generate lại, client cũ đọc nhầm response — một lỗi corruption khó debug.

XIME giải quyết bằng `proto.lock.json`:

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

**Quy tắc:**

- Field đã có trong lock giữ số cũ mãi mãi.
- Field mới nhận số kế tiếp, bỏ qua số đã reserved.
- Field bị xoá trở thành `reserved` — số đó không bao giờ được tái dùng.

**Commit `proto.lock.json` vào git.** Nó là một phần nguồn chân lý của bạn.

```protobuf
// Nếu bạn xoá "email" khỏi UserResponse:
message UserResponse {
    reserved 3;       // "email" từng là field 3
    reserved "email";
    int64  id = 1;
    string username = 2;
    string role = 4;
}
```

---

## Ánh xạ kiểu

| Python | Proto | Ghi chú |
| --- | --- | --- |
| `str` | `string` | |
| `bytes` | `bytes` | |
| `bool` | `bool` | |
| `int` | `int64` | mặc định; override bằng `Annotated` |
| `float` | `double` | |
| `list[T]` | `repeated <T>` | |
| `dict[K, V]` | `map<K, V>` | K phải là scalar |
| `Optional[T]` / `T \| None` | `optional <T>` | proto3 explicit presence |
| `datetime.datetime` | `google.protobuf.Timestamp` | |
| `Decimal` | `string` | tránh mất chính xác |
| `UUID` | `string` | |
| `IntEnum` / `StrEnum` | `enum` | thành viên thành giá trị enum |
| nested `BaseModel` | `message <Name>` | |

**Override kiểu số nguyên** bằng `Annotated`:

```python
from typing import Annotated
from xime.adapters.grpc.codefirst import ProtoInt32, ProtoUInt64

class Page(BaseModel):
    size:   Annotated[int, ProtoInt32]   # → int32
    cursor: Annotated[int, ProtoUInt64]  # → uint64
```

Kiểu không hỗ trợ raise `UnsupportedTypeError` lúc generate, không phải lúc runtime.

---

## DTO dùng chung → `common.proto`

Khi một DTO được dùng bởi hai controller trở lên cùng `server_id`, XIME tự động đặt
nó vào `common.proto`:

```text
generated/public/
├── crypto.proto     # import common.proto
├── user.proto       # import common.proto
└── common.proto     # dùng chung: UserResponse, PageInfo, ...
```

---

## CLI

### Generate

```bash
xime grpc generate               # sinh .proto + chạy protoc
xime grpc generate --no-protoc   # chỉ sinh .proto (bỏ qua protoc)
```

### Check (dùng trong CI)

```bash
xime grpc check
```

So sánh proto *sẽ được sinh* với proto đang có trên đĩa. Trả exit code 1 nếu có sự
khác biệt. Dùng làm CI gate để bắt "DTO đã sửa nhưng chưa generate lại":

```text
Proto Out Of Date
  File: generated/public/crypto.proto
  Hint: chạy `xime grpc generate`
```

---

## Multi-Server

Giống HTTP và gRPC proto-first, controller code-first được định tuyến đến server đúng
bằng `server_id`:

```python
class PublicCryptoController:
    server_id = "public"      # phục vụ bởi GrpcAdapter() hoặc GrpcAdapter("public")
    ...

class InternalCryptoController:
    server_id = "internal"    # phục vụ bởi GrpcAdapter("internal", port=50052)
    ...
```

```python
app.use(GrpcAdapter())                         # phục vụ server_id="public"
app.use(GrpcAdapter("internal", port=50052))   # phục vụ server_id="internal"
```

---

## Sống cùng Proto-First

Code-First và proto-first servicer có thể cùng tồn tại trong một `GrpcAdapter`. Cấu
hình độc lập:

```python
# config/grpc.py — proto-first
from xime.adapters.grpc import configure_grpc_services
configure_grpc_services("api.grpc.proto_first")

# config/grpc_codefirst.py — code-first
from xime.adapters.grpc.codefirst import configure_grpc_codefirst
configure_grpc_codefirst(packages=["api.grpc.codefirst"])
```

---

## Cài đặt

```bash
pip install "xime[grpc]"   # thêm grpcio, grpcio-tools, protobuf
```

---

[← Routing](routing.md) · **7/9 — Code-First gRPC** · [Starters →](starters.md)
