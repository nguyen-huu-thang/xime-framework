# Backlog - Lỗi cần điều tra/sửa trong framework

> Các vấn đề đã xác nhận. Phiên sau làm việc tại repo này chọn việc từ đây.

## Đã sửa (2026-06-13)

### ~~1. 10 test fail ở `tests_temp/event/test_bus.py`~~ ĐÃ SỬA

Nguyên nhân: test lỗi thời, không phải bug code. `EventBus` đã chuyển sang
fire-and-forget (handler chạy nền bằng asyncio Task, lỗi chỉ log không
propagate, có `drain()`), nhưng test cũ còn assert theo ngữ nghĩa cũ (gọi tuần
tự, publish raise ExceptionGroup). Đã viết lại toàn bộ test theo semantics mới
(dùng `drain()`, kiểm tra log lỗi qua `caplog`, bỏ kỳ vọng ExceptionGroup).
18 test pass.

### ~~2. Pb2 loader collision giữa các server_id~~ ĐÃ SỬA

Đã thống nhất cơ chế load: tạo `adapters/grpc/_descriptors.py`
(`load_messages_from_descriptor_set` + `DESCRIPTOR_SET_NAME`) dùng chung cho cả
server (`codefirst/_pb2_loader.py`) lẫn client SDK (`client/_runtime.py`).
`xime grpc generate` giờ phát thêm `_descriptors.binpb` (FileDescriptorSet qua
`protoc --descriptor_set_out --include_imports`) mỗi thư mục server_id; server
nạp message class từ đó qua DescriptorPool RIÊNG, không còn import `*_pb2.py`
nên không đụng tên module `common_pb2` giữa các server_id. Regression test:
`tests_temp/grpc_codefirst/test_pb2_loader_isolation.py`.

### ~~3. Field `bytes` trong DTO bị marshal sai~~ ĐÃ SỬA

`codefirst/_marshal.py`: chiều đi dùng `model_dump(mode="python")` + `_sanitize`
(base64 cho bytes, khớp các kiểu JSON khác); chiều về `_decode_bytes_fields`
duyệt descriptor decode base64 thành bytes thật (xử lý cả repeated, map,
nested). Test roundtrip binary (kể cả byte không utf-8) qua wire thật:
`tests_temp/grpc_codefirst/test_marshal_bytes.py`.

### ~~4. `RequestContextInterceptor` await async generator -> hỏng mọi server-streaming RPC~~ ĐÃ SỬA

`interceptors/_context.py` cũ bọc mọi handler bằng một `_wrap_fn` duy nhất dùng
`return await fn(...)`. Với handler response-streaming (`unary_stream`,
`stream_stream`) thì `fn` là async generator function -> `await async_generator`
ném `TypeError`, mọi RPC server-streaming/bidi trả `UNKNOWN`. Đã tách hai
wrapper giống `ErrorMappingInterceptor`: `_wrap_unary` (`await fn`) và
`_wrap_streaming` (`async for ... yield`). Regression test (server-stream +
bidi + clear context khi raise giữa stream):
`tests_temp/grpc/test_interceptors.py`.

### ~~5. Controller code-first lệch `server_id` -> thoát im lặng, mọi RPC UNIMPLEMENTED~~ ĐÃ SỬA

`GrpcAdapter._register_codefirst` lọc controller theo `server_id` của adapter và
return im lặng nếu không khớp -> server lên bình thường, không log, mọi RPC trả
`UNIMPLEMENTED`. Đã thêm `Application._validate_grpc_codefirst_targets()` chạy
ở `_run_async` (đường có adapter): khi đã `configure_grpc_codefirst()` mà
controller mang `server_id` không adapter nào phục vụ (kể cả khi quên
`app.use(GrpcAdapter())`) -> nổ `StartupException` liệt kê controller, server_id
và các adapter đang có. Đặt ở `_run_async` nên dùng qua context manager (test)
không bị ảnh hưởng. Test: `tests_temp/bootstrap/test_application_grpc_codefirst.py`.

### ~~6. Framework không cấu hình logging -> app chạy im lặng~~ ĐÃ XỬ LÝ (DX)

Không phải bug mà là friction: root logger mặc định WARNING + không handler nên
mọi log INFO bị nuốt, app tưởng treo. Đã thêm khối `logging:` (enabled/level/
format/datefmt) vào `RuntimeConfig` (`core/config/runtime.py`, model
`LoggingConfig`) và `Application._configure_logging()` áp dụng lúc bootstrap
(`core/bootstrap/application.py`, gọi trong `start()`). An toàn: chỉ cấu hình khi
enabled VÀ root chưa có handler -> không ghi đè app/pytest đã tự cấu hình; tham
số `root=` để test inject. Mặc định enabled=true, INFO. Tài liệu:
`docs/app-entry-point.md` mục Logging. Test:
`tests_temp/bootstrap/test_application_logging.py`.

## Còn mở

Phát hiện lúc review trước khi publish v0.2.0 (2026-06-14). Không chặn publish -
để dành phiên bản tiếp theo.

### 7. `XimeGrpcChannel._dynamic_channel()` không thread-safe khi cert rotate + concurrent requests

**File:** `xime/adapters/grpc/client/_channel.py`, method `_dynamic_channel()`

Khi cert version thay đổi, hai coroutine đến đồng thời đều thấy
`version != self._cert_version`, cùng tạo channel mới và retire channel cũ.
Channel đầu bị ghi đè bởi channel thứ hai trong `self._channel`, nhưng không
được đưa vào `_retired` - bị leak.

Trigger: cert rotate đúng lúc có 2+ request song song. Rất hiếm trong thực tế.
Fix gợi ý: thêm `asyncio.Lock` bảo vệ đoạn check-and-replace.

### 8. `wire_dynamic_certificates()` hardcode `server_id="default"`

**File:** `xime/adapters/grpc/client/_config.py`, dòng `grpc_tls_registry.get_provider("default")`

Client mTLS động luôn lấy cert provider từ server "default". Nếu setup
multi-server (server_id khác "default") và muốn client dùng cert từ server đó,
hiện không có cách cấu hình.

Chỉ ảnh hưởng: multi-server + dynamic mTLS client. Fix gợi ý: cho phép truyền
`server_id` vào `configure_grpc_clients()` hoặc từng client config.

### 9. Không warn khi endpoint code-first là `def` thay vì `async def`

**File:** `xime/adapters/grpc/codefirst/_builder.py`, method `_resolve()`

Framework không kiểm tra endpoint có phải coroutine không lúc startup. Nếu
developer viết `def` thay vì `async def`, server khởi động bình thường nhưng mọi
RPC đó sẽ crash lúc runtime với `TypeError: object NoneType can't be used in
'await' expression`.

Fix gợi ý: trong `_resolve()`, thêm `inspect.iscoroutinefunction(func)` và
ném `StartupException` nếu không phải async.
