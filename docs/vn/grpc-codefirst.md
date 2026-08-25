# Code-First gRPC

[English](../en/grpc-codefirst.md) | **Tiếng Việt**

[← Routing](routing.md) · **7/9 - Code-First gRPC** · [Starters →](starters.md)

---

XIME hỗ trợ hai chế độ phát triển gRPC:

- **Proto-First** (có sẵn) - bạn viết file `.proto`, XIME phục vụ servicer của bạn.
- **Code-First** (trang này) - bạn viết Python controller và DTO, XIME sinh file `.proto` cho bạn.

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

1. **Drift** - bạn cập nhật Pydantic DTO nhưng quên cập nhật `.proto`. Hai file lệch
   nhau mà không ai hay.
2. **Trùng lặp** - mỗi field phải định nghĩa hai lần: một lần trong Python, một lần
   trong protobuf.

Code-First loại bỏ cả hai. Proto được sinh từ type Python - không thể drift, và không
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
    server_id = "default"   # phục vụ bởi GrpcAdapter() mặc định

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
    packages=["my_service.api.grpc"],
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
└── default/
    ├── crypto.proto
    ├── crypto_pb2.py
    └── crypto_pb2_grpc.py
```

và tạo `proto.lock.json` (commit file này vào git).

### 4. Chạy app

```python
# main.py
from xime.adapters.grpc import GrpcAdapter
from xime.core.bootstrap import Application

import config

app = Application()
app.add_config(config)
app.use(GrpcAdapter())

if __name__ == "__main__":
    app.run()
```

`GrpcAdapter` tự động phát hiện và phục vụ tất cả controller code-first đã cấu hình qua
`configure_grpc_codefirst`.

---

## Các loại Endpoint

Cùng hai decorator với Socket Adapter - một controller có thể phục vụ cả gRPC lẫn UDS
nếu bạn đăng ký cho cả hai.

### `@command` - RPC đơn

```python
@command("hash")
async def hash(self, request: HashRequest) -> HashResponse: ...
```

Proto sinh ra:

```protobuf
rpc Hash(HashRequest) returns (HashResponse);
```

### `@stream` + `UploadStream` - client streaming

```python
@stream("encrypt")
async def encrypt(self, request: EncryptRequest, upload: UploadStream) -> EncryptResponse:
    total = 0
    async for chunk in upload:
        total += len(chunk)
    return EncryptResponse(total=total)
```

Proto sinh ra dùng wrapper `oneof` - message đầu chứa metadata, các message sau chứa raw
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

### `@stream` + `DownloadStream` - server streaming

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

Dạng này dành cho **byte**: tải file, xuất dữ liệu thô. Muốn stream **bản ghi có kiểu** thì
dùng dạng ngay dưới.

### `@stream` + `yield` - server streaming CÓ KIỂU (0.7.1)

Handler là một **async generator**, mỗi `yield` là một message:

```python
from collections.abc import AsyncIterator

@stream("watch_changed_accounts")
async def watch_changed_accounts(
    self, request: WatchRequest
) -> AsyncIterator[AccountChanged]:
    async for event in self.feed.follow(request.after_sequence):
        yield AccountChanged(sequence=event.sequence, account_id=event.account_id)
```

Proto sinh ra **không có wrapper** - response chính là DTO của bạn:

```protobuf
rpc WatchChangedAccounts(WatchRequest) returns (stream AccountChanged);
```

Nhờ vậy một peer Java đọc `.proto` là hiểu ngay, không cần biết quy ước chunk của xime.

Ba ràng buộc, đều báo lỗi lúc **khởi động** chứ không phải lúc gọi RPC đầu tiên:

| Viết sai | Lỗi |
| --- | --- |
| `@command` mà có `yield` | `@command` nợ đúng một response, không được là async generator |
| Vừa có `DownloadStream` vừa có `yield` | Chọn một: byte hoặc bản ghi có kiểu |
| Thiếu annotation `-> AsyncIterator[<BaseModel>]` | Model yield ra chính là message của stream, không suy ra được nếu không khai |

**Dọn dẹp khi client bỏ đi:** framework gọi `aclose()` trên generator của bạn ngay khi
client huỷ, nên khối `finally:` (đóng session DB, nhả khoá) chạy đúng lúc đó - không chờ
tới lượt thu gom rác. Cứ viết `try/finally` như bình thường.

---

## Ổn định Field Number

> Đây là điều quan trọng nhất về Code-First gRPC.

Protobuf xác định field bằng **số**, không phải tên. Nếu generator gán lại số khi
generate lại, client cũ đọc nhầm response - một lỗi corruption khó debug.

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
- Field bị xoá trở thành `reserved` - số đó không bao giờ được tái dùng.

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
generated/default/
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
  File: generated/default/crypto.proto
  Hint: chạy `xime grpc generate`
```

---

## Multi-Server

Giống HTTP và gRPC proto-first, controller code-first được định tuyến đến server đúng
bằng `server_id`:

```python
class PublicCryptoController:
    server_id = "default"     # phục vụ bởi GrpcAdapter() mặc định
    ...

class InternalCryptoController:
    server_id = "internal"    # phục vụ bởi GrpcAdapter("internal")
    ...
```

```python
app.use(GrpcAdapter())                         # phục vụ server_id="default"
app.use(GrpcAdapter("internal"))   # cổng từ process.grpc.internal trong application.yml
```

> **`server_id` phải khớp một adapter đã đăng ký.** `GrpcAdapter()` mặc định mang
> `server_id="default"` - nó **không** phục vụ controller có `server_id` khác.
> Nếu một controller code-first nhắm tới `server_id` mà không `GrpcAdapter` nào
> phục vụ (ví dụ `server_id="public"` trong khi chỉ đăng ký adapter mặc định),
> XIME **báo lỗi ngay lúc startup** với thông điệp rõ ràng, thay vì cho server lên
> rồi mọi RPC trả `UNIMPLEMENTED` không một dòng log. Hãy đăng ký
> `GrpcAdapter("public", port=...)` tương ứng, hoặc đổi `server_id` của controller.

---

## Sống cùng Proto-First

Code-First và proto-first servicer có thể cùng tồn tại trong một `GrpcAdapter`. Cấu
hình độc lập:

```python
# config/grpc.py - proto-first
from xime.adapters.grpc import configure_grpc_services
configure_grpc_services("my_service.api.grpc.proto_first")

# config/grpc_codefirst.py - code-first
from xime.adapters.grpc.codefirst import configure_grpc_codefirst
configure_grpc_codefirst(packages=["my_service.api.grpc.codefirst"])
```

---

## TLS / mTLS

Bật TLS cho server qua `application.yml`. Server `default` đọc `grpc.tls`; server
khác đọc `grpc.servers.<server_id>.tls`:

```yaml
grpc:
  port: 50051
  tls:
    enabled: true
    mutual: true                 # true = yêu cầu client cert (mTLS)
    cert_file: certs/server.crt  # chế độ tĩnh: đọc cert từ file
    key_file:  certs/server.key
    ca_file:   certs/ca.crt
```

**mTLS động (cert xoay không restart).** Khi cert được cấp động (ví dụ từ một
một CA nội bộ và xoay định kỳ), đăng ký một `GrpcCertificateProvider` thay cho
khai file. Provider đọc cert hiện hành từ bộ nhớ; framework hỏi lại nó ở **mỗi
TLS handshake mới**, nên cert xoay không cần restart và không cắt phiên đang mở:

```python
# config/grpc.py
from xime.adapters.grpc import configure_grpc_tls

configure_grpc_tls(provider=MyCertificateProvider)
#   provider là class trong DI, có version() -> str và current() -> ServerCertificates
```

```yaml
grpc:
  tls:
    enabled: true
    mutual: true     # cert_file/key_file không cần khi có provider
```

Provider áp dụng cho mọi server; override cho một server cụ thể bằng
`configure_grpc_tls(provider=PublicCaProvider, server_id="public")` (ví dụ server
nội bộ dùng cert Trust, server public dùng cert public CA).

---

## Gọi từ service khác

Trang này lo phía **server**. Để một service khác **gọi** vào server code-first
này như gọi hàm nội bộ - sinh client SDK typed, đưa vào DI, dùng chung cert động
- xem [gRPC Client SDK + mTLS động](grpc-client.md).

---

## Cài đặt

```bash
pip install "xime[grpc]"   # thêm grpcio, grpcio-tools, protobuf
```

---

[← Routing](routing.md) · **7/9 - Code-First gRPC** · [Starters →](starters.md) · [gRPC Client SDK →](grpc-client.md)
