# Thiết kế — Code-First gRPC (Xime Framework)

> Tài liệu thiết kế triển khai. Snippet code dùng định danh tiếng Anh; diễn giải
> bằng tiếng Việt. Comment trong code thực tế tuân quy ước "English ở trên, tiếng
> Việt ở dưới".

---

## 1. Mục tiêu & Phạm vi

Xime áp dụng mô hình **Code-First gRPC**: nguồn chân lý duy nhất là **Python code**
(Controller + DTO + type hint). Developer **không viết `.proto` thủ công**.

```text
Controller + DTO + type hint  (Python — nguồn chân lý)
        │  xime grpc generate
        ▼
ContractModel  (IR — biểu diễn trung gian)
        ├──► .proto              → Java / Go / Rust / C++ consume
        ├──► proto.lock.json     → cố định field number (ổn định binary)
        └──► Python servicer glue → GrpcAdapter phục vụ (Pydantic ↔ proto)
```

Hai mục tiêu cốt lõi:

1. **Tránh lệch DTO ↔ proto** — sửa DTO Python, proto tự sinh lại.
2. **Giảm boilerplate** — chỉ viết DTO, không phải viết DTO + proto + stub song song.

### Phạm vi v1

| Có trong v1 | Chưa có |
|---|---|
| `xime grpc generate` (.proto + lock + Python glue) | `Union` tổng quát, generic lồng sâu |
| `xime grpc check` (phát hiện drift trong CI) | gRPC streaming hai chiều (bidi) |
| Command (unary) + Upload (client-stream) + Download (server-stream) | proto `import` thư viện ngoài tuỳ ý |
| Field-number stability qua lock file | Sinh SDK client đa ngôn ngữ tự động |
| Type mapping đầy đủ | gRPC reflection / health-check tự động |
| Tổ chức proto theo `server_id` | |

### Quan hệ với GrpcAdapter proto-first

Code-First **không xoá** mô hình proto-first (`configure_grpc_services`). Hai mô
hình cùng tồn tại trong một `GrpcAdapter`; `GrpcAdapter.start()` chạy cả hai.

### Quan hệ với Socket Adapter

Code-First gRPC **dùng chung lớp Contract với Socket Adapter** — cùng `@command`/
`@stream`, cùng `UploadStream`/`DownloadStream`, cùng `ControllerScanner`. Đây là
"Long-Term Vision": **một Controller → nhiều transport** (gRPC proto + Socket UDS)
mà **không định nghĩa contract hai lần**.

---

## 2. Triết lý

> Nguồn chân lý duy nhất là Python code.

Developer chỉ viết:

```python
class HashRequest(BaseModel):
    file_id: str

class HashResponse(BaseModel):
    digest: str

class CryptoController:
    server_id = "public"

    @command("hash")
    async def hash(self, request: HashRequest) -> HashResponse: ...
```

Framework sinh:

```protobuf
message HashRequest  { string file_id = 1; }
message HashResponse { string digest = 1; }

service CryptoController {
    rpc Hash(HashRequest) returns (HashResponse);
}
```

---

## 3. Cấu trúc module

### Lớp Contract dùng chung (`core/contract/`)

```text
xime/core/contract/
├── __init__.py      # export: command, stream, UploadStream, DownloadStream, ControllerScanner
├── _decorators.py   # @command, @stream, EndpointInfo, ENDPOINT_ATTR="_xime_endpoint"
├── _scanner.py      # ControllerScanner (tìm ENDPOINT_ATTR) — dùng chung Socket + gRPC
└── _streams.py      # UploadStream, DownloadStream (abstract base)
```

**Lưu ý:** `ContractModel`, `ContractBuilder`, `ProtoEmitter` ở trong `adapters/grpc/codefirst/`
(không ở `core/contract/`) vì chúng là chi tiết gRPC, không cần dùng chung.

### Code-First gRPC (`adapters/grpc/codefirst/`)

```text
xime/adapters/grpc/codefirst/
├── __init__.py
├── _builder.py          # ContractBuilder — scan Controller/DTO → ContractModel
├── _model.py            # ContractModel + các dataclass IR
├── _type_map.py         # Python type → proto type, ProtoInt32/ProtoUInt64
├── _lock.py             # LockFile — đọc/ghi proto.lock.json, assign_numbers
├── _proto_emitter.py    # ContractModel → văn bản .proto
├── _generator.py        # generate() / check() — orchestration
├── _service_builder.py  # CodeFirstGrpcBuilder — serve qua grpc.aio
├── _pb2_loader.py       # load *_pb2.py/*.grpc.py sau khi protoc
├── _marshal.py          # Pydantic ↔ proto marshalling
└── _config.py           # _CodeFirstRegistry, configure_grpc_codefirst
```

### CLI (`cli/`)

```text
xime/cli/
└── _main.py    # entry point: `xime grpc generate`, `xime grpc check`
```

---

## 4. Decorator & Metadata

```python
# core/contract/_decorators.py
ENDPOINT_ATTR = "_xime_endpoint"   # dùng chung với Socket Adapter

class EndpointKind(enum.Enum):
    COMMAND = "command"   # unary
    STREAM  = "stream"    # upload hoặc download — builder suy từ chữ ký

@dataclass
class EndpointInfo:
    name: str             # "hash", "encrypt"...
    kind: EndpointKind
```

`@stream` không phân biệt upload/download tại khai báo. `ContractBuilder` đọc
`inspect.signature`:
- `@command` → `UNARY`.
- `@stream` + param annotate `UploadStream` → `CLIENT_STREAM`.
- `@stream` + param annotate `DownloadStream` → `SERVER_STREAM`.

---

## 5. ContractModel — IR trung tâm (`_model.py`)

```python
class StreamKind(enum.Enum):
    UNARY = "unary"
    CLIENT_STREAM = "client_stream"   # upload
    SERVER_STREAM = "server_stream"   # download

@dataclass
class FieldContract:
    name: str
    proto_type: str    # "string", "int64", "repeated string", "MessageX"...
    number: int        # ổn định qua lock file
    optional: bool = False

@dataclass
class MessageContract:
    name: str
    fields: list[FieldContract]
    reserved_numbers: list[int]
    reserved_names: list[str]

@dataclass
class MethodContract:
    rpc_name: str      # "Hash" (PascalCase từ endpoint name)
    request: MessageContract | str
    response: MessageContract | str | None
    kind: StreamKind

@dataclass
class ServiceContract:
    name: str          # "CryptoController"
    server_id: str
    proto_file: str    # "crypto.proto"
    methods: list[MethodContract]

@dataclass
class ContractModel:
    services: list[ServiceContract]
    messages: dict[str, MessageContract]   # toàn bộ (kể cả shared)
    server_id: str
```

---

## 6. Field Number Stability — VẤN ĐỀ CỐT LÕI

Protobuf định danh field bằng **số**, không bằng tên. Nếu generate lại mà số đổi →
**phá vỡ tương thích nhị phân**, lỗi âm thầm, khó debug.

### Giải pháp — Lock File (`proto.lock.json`)

`proto.lock.json` được **commit vào git**, ghi nhớ số field từng message.

```json
{
  "version": 1,
  "messages": {
    "UserResponse": {
      "fields": {"id": 1, "username": 2, "role": 3},
      "reserved_numbers": [],
      "reserved_names": []
    }
  }
}
```

### Thuật toán `assign_numbers` (`_lock.py`)

1. Field đã có trong lock → **giữ nguyên số cũ**.
2. Field mới → cấp số kế tiếp, **không đụng số đã reserved**.
3. Field bị xoá → đưa vào `reserved_numbers`/`reserved_names`, **không bao giờ
   tái dùng**.

### Field bị xoá → `reserved` trong proto

```protobuf
message UserResponse {
    reserved 4;        // field "email" đã xoá
    reserved "email";
    int64  id = 1;
    string username = 2;
    string role = 3;
}
```

---

## 7. Type Mapping (`_type_map.py`)

| Python | Proto | Ghi chú |
|---|---|---|
| `str` | `string` | |
| `bytes` | `bytes` | |
| `bool` | `bool` | |
| `int` | `int64` | mặc định; override bằng `Annotated` |
| `float` | `double` | |
| `list[T]` | `repeated <T>` | |
| `dict[K, V]` | `map<K, V>` | K phải scalar |
| `Optional[T]` / `T \| None` | `optional <T>` | proto3 explicit presence |
| `datetime.datetime` | `google.protobuf.Timestamp` | |
| `Decimal` | `string` | tránh mất chính xác |
| `UUID` | `string` | |
| `IntEnum` / `StrEnum` | `enum` sinh kèm | |
| nested `BaseModel` | `message <Name>` | |

**Override kiểu số nguyên** với `Annotated`:

```python
from xime.adapters.grpc.codefirst import ProtoInt32, ProtoUInt64

class Page(BaseModel):
    size:  Annotated[int, ProtoInt32]   # → int32
    total: Annotated[int, ProtoUInt64]  # → uint64
```

Kiểu không hỗ trợ → `UnsupportedTypeError` **lúc generate**, không phải lúc chạy.

---

## 8. Streaming Mapping (`_proto_emitter.py` + `_service_builder.py`)

### Upload (client streaming)

Python controller có `upload: UploadStream` → sinh **chunk-wrapper message** dùng `oneof`:

```protobuf
message EncryptChunk {
    oneof payload {
        EncryptRequest metadata = 1;  // message ĐẦU TIÊN
        bytes          chunk    = 2;  // các message SAU
    }
}

service CryptoController {
    rpc Encrypt(stream EncryptChunk) returns (EncryptResponse);
}
```

Server glue tách metadata → dựng `EncryptRequest`; các chunk → bơm vào `UploadStream`.
Business code không thấy `EncryptChunk`.

### Download (server streaming)

```protobuf
message DownloadChunk { bytes chunk = 1; }

service CryptoController {
    rpc Download(DownloadRequest) returns (stream DownloadChunk);
}
```

Mỗi `await download.write(b)` → yield `DownloadChunk(chunk=b)`.

---

## 9. Tổ chức Proto theo `server_id`

```text
generated/
├── public/
│   ├── crypto.proto       # CryptoController
│   ├── user.proto         # UserController
│   └── common.proto       # message dùng chung ≥ 2 controller
└── internal/
    ├── user_internal.proto
    └── common.proto
```

DTO dùng bởi ≥ 2 controller trong cùng `server_id` → đặt ở `common.proto`, các
proto khác `import "common.proto"`.

Header mỗi file:

```protobuf
// Code generated by `xime grpc generate`. DO NOT EDIT.
syntax = "proto3";
package xime.public;
```

---

## 10. CLI — `xime grpc generate` / `xime grpc check`

### Generate

```bash
xime grpc generate [--no-protoc]
```

Luồng:

```text
1. Import config/grpc.py → nạp configure_grpc_codefirst → biết packages + output
2. ControllerScanner.find(*packages) → danh sách Controller
3. ContractBuilder.build(controllers) → ContractModel (đọc/ghi lock)
4. Ghi proto.lock.json
5. ProtoEmitter.emit(model) → ghi *.proto theo server_id
6. (nếu không --no-protoc) _run_protoc → *_pb2.py / *_pb2_grpc.py
```

### Check (dùng trong CI)

```bash
xime grpc check
```

So sánh proto sẽ sinh với proto đang có trên đĩa. Trả exit code ≠ 0 khi có drift.

```text
Proto Out Of Date
  File   : generated/public/user.proto
  Reason : field 'email' added but not regenerated
```

---

## 11. Serving — `CodeFirstGrpcBuilder` (`_service_builder.py`)

Sau khi `generate` chạy protoc sinh `*_pb2.py`, `CodeFirstGrpcBuilder` đăng ký mỗi
Controller với `grpc.aio.Server` qua handler động, **marshalling Pydantic ↔ proto
tại biên**.

```python
class CodeFirstGrpcBuilder:
    def __init__(self, app, model: ContractModel, messages: dict) -> None:
        ...

    def register_all(self, server: grpc.aio.Server) -> None:
        # Với mỗi ServiceContract: tạo RpcMethodHandler đúng biến thể
        # (unary_unary / stream_unary / unary_stream)
        ...
```

`GrpcAdapter.start()` gọi `_register_codefirst()` sau khi đăng ký proto-first
services — cả hai cùng tồn tại trên một server.

---

## 12. Cấu hình

```python
# config/grpc.py
from xime.adapters.grpc.codefirst import configure_grpc_codefirst

configure_grpc_codefirst(
    packages=["api.grpc"],
    output_dir="generated",
    lock_file="proto.lock.json",
)
```

Registry module-level singleton (`_CodeFirstRegistry`) có `reset()` cho test cleanup.
CLI và `GrpcAdapter` cùng đọc registry này.

---

## 13. Quyết định thiết kế & Tradeoff

1. **ContractModel là IR trung tâm.** Mọi đầu ra đọc từ IR → một Controller, nhiều
   transport.
2. **Lock file commit vào git.** Đổi lại: an toàn binary tuyệt đối.
3. **Chunk-wrapper `oneof` cho upload.** Giải quyết ràng buộc "client-stream cùng
   type", ẩn hoàn toàn khỏi business code.
4. **`int → int64` mặc định, override bằng `Annotated`.** An toàn, linh hoạt.
5. **Code-First sống cạnh proto-first cũ.** Không phá vỡ người đang dùng
   `configure_grpc_services`.
6. **Marshalling Pydantic ↔ proto tại biên.** Business code thuần Pydantic.
7. **Generate là bước build tường minh** (không generate lúc runtime) → proto là
   artifact review được, CI kiểm soát được.
8. **`@command`/`@stream` dùng chung với Socket** (`core/contract/`) — không trùng
   lặp contract.

---

## 14. Lộ trình tương lai

- `@proto_field(rename_from=..., number=...)` — rename giữ số, pin số thủ công.
- Bidi streaming.
- Sinh SDK client đa ngôn ngữ từ ContractModel.
- gRPC reflection + health checking tự động.
- Map `Union` tổng quát → `oneof`.
