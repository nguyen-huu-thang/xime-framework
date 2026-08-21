# Tiến độ thi công - Code-First gRPC

> | | |
> |---|---|
> | **Trạng thái** | 📋 **GIẤY NHÁP** - việc đã xong. Nội dung **không sai**, chỉ hết vai |
> | **Là gì** | Checklist thi công của mảng gRPC code-first, **100% `[x]`** |
> | **Thiết kế ở** | [`../thiet-ke/05-grpc-codefirst.md`](../thiet-ke/05-grpc-codefirst.md) |
> | **Hiện trạng ở** | chính cây mã `xime/adapters/grpc/codefirst/` - nó trả lời chính xác hơn và không bao giờ lỗi thời |
>
> ⚠ **Con số *"781 tests passed"* là của thời điểm viết**, nay đã hơn **2400**. Đừng trích
> nó như hiện trạng - đó đúng là lý do file này nằm ở `nhap/` chứ không nằm ở `thiet-ke/`.

## Trạng thái tổng quan

**Hoàn thành toàn bộ.** 781 tests passed (bao gồm e2e test gRPC qua TCP - hoạt động
trên mọi OS vì gRPC dùng TCP, không phụ thuộc Unix socket). gRPC extras
(`grpcio`, `grpcio-tools`, `protobuf`) cần được cài để chạy e2e.

---

## Checklist triển khai

### Lớp Contract dùng chung (nền tảng)

- [x] **1. `core/contract/_decorators.py`** - `@command`, `@stream`, `EndpointInfo`,
      `ENDPOINT_ATTR = "_xime_endpoint"`. Dùng chung với Socket Adapter.

- [x] **2. `core/contract/_scanner.py`** - `ControllerScanner` tìm `ENDPOINT_ATTR`.
      Dùng bởi cả `_generator.py` (generate/check) và `GrpcAdapter._register_codefirst()`.

- [x] **3. `core/contract/_streams.py`** - `UploadStream`, `DownloadStream` abstract
      base. Concrete implementation trong `adapters/socket/_session.py` (Socket)
      và `adapters/grpc/codefirst/_service_builder.py` (gRPC).

### Code-First gRPC Core

- [x] **4. `adapters/grpc/codefirst/_type_map.py`** - `map_type`, `ProtoInt32`,
      `ProtoUInt64`, `UnsupportedTypeError`. Unit test đầy đủ từng kiểu scalar,
      `list`, `dict`, `Optional`, `Annotated`, `datetime`, nested `BaseModel`, `Enum`.

- [x] **5. `adapters/grpc/codefirst/_lock.py`** - `LockFile`, `assign_numbers`,
      `reserved`. Test: thêm field, xoá field, re-add field không tái dùng số cũ,
      roundtrip save/load.

- [x] **6. `adapters/grpc/codefirst/_model.py`** - `ContractModel`, `ServiceContract`,
      `MethodContract`, `MessageContract`, `FieldContract`, `StreamKind`.

- [x] **7. `adapters/grpc/codefirst/_builder.py`** - `ContractBuilder` (scan Controller
      → IR, gọi lock + type_map + stream convention, gom shared message → common).
      Test: command/upload/download, shared message, missing response raises `StartupException`.

- [x] **8. `adapters/grpc/codefirst/_proto_emitter.py`** - `ProtoEmitter` IR → text
      proto (deterministic, ổn định để `check` so sánh). Test golden-file:
      header, package, enum UNSPECIFIED=0, upload oneof wrapper, shared → common.proto,
      import statement.

- [x] **9. `adapters/grpc/codefirst/_generator.py`** - `generate()`, `check()`,
      `_run_protoc()`, `GenerateResult`, `CheckResult`. Test: generate writes proto
      + lock, check ok sau generate, check detects drift (tampered file, missing file).

- [x] **10. `adapters/grpc/codefirst/_config.py`** - `_CodeFirstRegistry`,
      `configure_grpc_codefirst`, `reset()` (cho test cleanup).

### CLI

- [x] **11. `cli/_main.py`** - entry point `argparse`: `xime grpc generate [--no-protoc]`,
      `xime grpc check`. Import config/grpc.py từ thư mục làm việc. Exit code 0/1.
      *Lưu ý: thiết kế gốc chia thành `cli/grpc/_generate.py` + `cli/grpc/_check.py`;
      triển khai thực tế gộp vào `cli/_main.py` duy nhất.*

- [x] **12. `pyproject.toml` - `[project.scripts]`** `xime = "xime.cli._main:main"`.
      Extras `xime[grpc]` = `grpcio>=1.60`, `grpcio-tools>=1.60`, `protobuf>=4.25`.

### Serving Layer

- [x] **13. `adapters/grpc/codefirst/_pb2_loader.py`** - `load_message_classes(output_dir, server_id)`:
      add thư mục vào `sys.path`, import tất cả `*_pb2` và `*_pb2_grpc` của server,
      trả `dict[str, type]` message classes.

- [x] **14. `adapters/grpc/codefirst/_service_builder.py`** - `CodeFirstGrpcBuilder`
      (marshalling Pydantic ↔ proto, 3 biến thể: `unary_unary`, `stream_unary`,
      `unary_stream`). Upload: đọc message đầu = metadata, các message sau = chunk
      → bơm vào `UploadStream`. Download: `await download.write(b)` → `yield DownloadChunk`.

- [x] **15. `GrpcAdapter._register_codefirst()`** - lazy import code-first modules,
      chạy sau khi đăng ký proto-first services.

### Tests

- [x] **16. Tests unit** (`tests_temp/grpc_codefirst/test_codefirst.py`) - type mapping,
      lock file stability (add/remove/re-add field), builder + emitter (command/upload/download,
      oneof wrapper, shared→common, enum, missing response raises error), generator
      (generate + check drift), CLI (generate then check then tamper).

- [x] **17. Tests e2e** (`tests_temp/grpc_codefirst/test_codefirst_e2e.py`) -
      generate → protoc → serve → call qua TCP thực: command (unary), upload (client
      streaming với oneof), download (server streaming).
      `pytest.importorskip("grpc")` / `importorskip("grpc_tools")` - tự động skip
      nếu chưa cài extras.

---

## Thay đổi so với thiết kế gốc (`grpc.txt`)

| Thiết kế gốc | Triển khai thực tế |
|---|---|
| `ContractModel` trong `core/contract/_model.py` | Trong `adapters/grpc/codefirst/_model.py` |
| `ContractBuilder` trong `core/contract/_builder.py` | Trong `adapters/grpc/codefirst/_builder.py` |
| CLI: `cli/grpc/_generate.py` + `cli/grpc/_check.py` riêng | Gộp vào `cli/_main.py` duy nhất |
| `_stream_convention.py` riêng | Logic gộp vào `_builder.py` + `_proto_emitter.py` |
| `_marshal.py` không đề cập trong checklist | Có thêm `_pb2_loader.py` và `_marshal.py` |

Lý do `ContractModel`/`ContractBuilder` ở `adapters/grpc/codefirst/` thay vì
`core/contract/`: chúng chứa logic gRPC-specific (field number lock, type mapping
proto), không cần thiết cho Socket Adapter. Socket chỉ cần decorator metadata để
dispatch - không cần sinh proto.

---

## Cách chạy tests

```bash
# Tests unit (không cần grpc extras):
pytest tests_temp/grpc_codefirst/test_codefirst.py

# Tests e2e (cần grpc extras):
pip install xime[grpc]
pytest tests_temp/grpc_codefirst/test_codefirst_e2e.py

# Toàn bộ:
pytest tests_temp/
```
