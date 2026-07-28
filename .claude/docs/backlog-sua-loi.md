# Backlog - Lỗi cần điều tra/sửa trong framework

> **TRẠNG THÁI 2026-07-27: KHÔNG CÒN MỤC NÀO MỞ.** Cả 11 mục dưới đây đã đóng.
> Đừng đọc file này để tìm việc - nó chỉ còn giá trị tra cứu "lỗi X trước đây sửa thế
> nào, ở file nào, test regression nằm đâu".
>
> Hai mục theo dõi B1 (ép kiểu cờ `xime.di.dynamic-binding`) và B2 (thứ tự
> `post_construct` khi bật dynamic binding) ghi nhận ở kiểm toán 0.6 cũng đã xử lý tại
> **0.6.3** - xem `wishlist-tinh-nang.md` mục "Core DI / Interface Binding".
>
> Nơi tìm việc tiếp theo: `lo-trinh-phien-ban.md` (0.7 Fieldbus) và `wishlist-tinh-nang.md`.

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

## Đã sửa (0.3, 2026-06-19)

### ~~7. `XimeGrpcChannel._dynamic_channel()` không thread-safe khi cert rotate~~ ĐÃ SỬA

`_channel.py`: thêm `threading.Lock` (`self._rotation_lock`) bảo vệ đoạn
check-and-replace trong `_dynamic_channel()`. Dùng `threading.Lock` chứ KHÔNG
phải `asyncio.Lock` như gợi ý gốc, vì method đồng bộ (không có `await` bên
trong) nên dưới asyncio vốn đã atomic - lock chỉ cần khi channel bị chạm từ
nhiều OS thread, đúng trường hợp duy nhất race xảy ra. Test đa luồng (20 thread
+ Barrier) khẳng định chỉ một channel được dựng, không rò:
`tests_temp/grpc_client/test_channel_rotation.py::test_concurrent_first_access_builds_one_channel`.

### ~~8. `wire_dynamic_certificates()` hardcode `server_id="default"`~~ ĐÃ SỬA

`_config.py` (client): thêm field `tls.server_id` (mặc định `"default"`) vào
`GrpcClientTlsConfig`; `wire_dynamic_certificates()` giờ tra provider theo
`server_id` của TỪNG channel (cùng class resolve một lần). `get_provider()` vẫn
fallback về `"default"` nếu chưa đăng ký riêng. Test:
`test_channel_rotation.py::test_non_default_server_id_uses_matching_provider`.

### ~~9. Không warn khi endpoint code-first là `def` thay vì `async def`~~ ĐÃ SỬA

`_builder.py` `_resolve()`: thêm `inspect.iscoroutinefunction(func)` ở đầu, không
phải coroutine (kể cả `async def` có `yield` = async generator) → ném
`StartupException` rõ ràng. Test:
`tests_temp/grpc_codefirst/test_codefirst.py::test_builder_rejects_sync_command`
và `::test_builder_rejects_async_generator_command`.

### ~~(note data-service #2) Interceptor lỗi abort hai lần~~ ĐÃ SỬA

`interceptors/_error.py`: hai nhánh except re-raise cả `grpc.aio.AbortError`
(không kế thừa `grpc.RpcError`) để khỏi abort lần hai khi interceptor/handler
bên trong đã abort. Test:
`tests_temp/grpc/test_interceptors.py::test_unary_handler_reraises_abort_error_without_second_abort`.

### ~~(note data-service #1a) Default `str(exc)` lộ chi tiết nội bộ~~ ĐÃ SỬA

`interceptors/_error.py`: thêm `_safe_details()` - lỗi đã map giữ message có chủ
đích, lỗi CHƯA map trả message chung `"Internal server error"` thay vì
`str(exc)`. Phần redaction theo visibility (Private/System/Public, #1b) vẫn để
0.4. Test cập nhật:
`test_interceptors.py::test_unary_handler_uses_internal_for_unmapped_exception`.
