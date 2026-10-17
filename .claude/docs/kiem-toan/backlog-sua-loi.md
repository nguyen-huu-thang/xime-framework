# Backlog - Lỗi cần điều tra/sửa trong framework

> **TRẠNG THÁI 2026-10-17: sáu lỗi F1–F6 đã vá và kiểm chứng theo nhóm trên
> Windows; đã commit Bước 0–6 tại e5a5b5c.** Hậu kiểm F7 và nhánh parse YAML của
> F4 cũng đã vá/kiểm, lưu cùng commit bổ sung. Bước 7 Windows đạt; còn cổng Linux.
> Baseline: `2ad5274`; kết quả bản vá thuộc worktree. Nhận định fingerprint
> đã được rút lại như một lỗi chức năng. Mười một mục lịch sử phía dưới đã đóng.
>
> Hai mục theo dõi B1 (ép kiểu cờ `xime.di.dynamic-binding`) và B2 (thứ tự
> `post_construct` khi bật dynamic binding) ghi nhận ở kiểm toán 0.6 cũng đã xử lý tại
> **0.6.3** - xem `../sap-toi/wishlist-tinh-nang.md` mục "Core DI / Interface Binding".
>
> Các mục trong phần “Đã sửa” là lịch sử; những việc mới được ghi ở đầu file.

## Kiểm toán framework và dependency (2026-10-17)

Báo cáo đầy đủ và kết quả nhóm vá đầu tiên:
[`kiem-toan-framework-va-dependency.md`](kiem-toan-framework-va-dependency.md).
Kế hoạch đã được chủ dự án duyệt:
[`ke-hoach-va-loi-kiem-toan-framework.md`](../sap-toi/ke-hoach-va-loi-kiem-toan-framework.md).

| ID | Mức | Vấn đề | Trạng thái |
|---|---|---|---|
| F1 | P2 | JWT khóa tĩnh trả 500 khi JSON header lồng quá sâu | Đã vá; 12 test mới đạt cả trên PyJWT cũ; full 2.881 passed trên hai bộ dependency |
| F2 | P2 | Download bỏ qua If-Range, có thể trộn hai phiên bản file | Đã vá; web_files/storage 95 passed, 6 skip |
| F3 | P2 | Session ContextVar chưa reset nếu close lỗi/bị hủy | Đã vá; SQLAlchemy 43 passed, gồm fault injection và SQLite |
| F4 | P2 | Checker bỏ sót typo trong nhánh environments | Đã vá; config/SQLAlchemy 307 passed; gồm endpoint tên động và kế thừa |
| F5 | P2 | Uvicorn 0.47.0 mặc định không hợp một số client TLS 1.2 | Đã nâng sàn 0.48.0; 110 test TLS/management/health đạt, 1 skip |
| F6 | P3 | Suffix Range trên object rỗng tạo Content-Range vô hiệu | Đã vá cùng F2; Range hợp lệ trên object rỗng trả 416 |
| F7 | P2 | Extra jwt sạch thiếu crypto cho RSA/EC/EdDSA | Đã vá; 15/15 ca wheel runtime đạt ở mỗi bộ resolver/sàn; [báo cáo](jwt-extra-thieu-crypto.md) |

Sàn khai báo mới: PyJWT >=2.15.0 trong extra jwt; AnyIO >=4.14.2 trong
runtime; Uvicorn >=0.48.0 ở web. 14 advisory PyJWT và 2 AnyIO đã có kết luận từng mục. Bộ sàn và tập
dependency khai báo thực cài chỉ còn advisory APScheduler đã chấp nhận từ
trước; cài `[web,jwt]` sạch không báo advisory. Các thay đổi khai báo chưa tự
nâng package trong môi trường đang dùng chung; cần bước triển khai riêng.

Bước 6: mypy từ **49 lỗi / 28 file xuống 0 / 250 file**, giữ cấu hình kiểm kiểu;
cả kiểm Windows lẫn phân tích tĩnh `--platform linux` đều đạt. Phân tích tĩnh
không thay cho chạy Linux. Các tên thiếu trong EN/VN đã có mô tả và
[phân loại từng mục](phan-loai-api-cong-khai.md): 152 lượt export, 94 API/kiểu,
54 hạ tầng, 4 alias. Counter thô còn **0/317** ở mỗi ngôn ngữ; không đổi __all__.

[Nghiệm thu Bước 7 Windows](nghiem-thu-windows-framework.md): 12 consumer đạt
6.557 passed/8 skipped, config/DI và artifact đạt. Không còn mục F1–F6 mở theo
bằng chứng Windows; Linux/uvloop/Certbot và nghiệm thu live consumer vẫn là cổng
môi trường trước phát hành, không được đánh dấu đã kiểm.

Hậu kiểm: F4 đã che giá trị cả ở parse failure; lỗi vẫn inconclusive, giữ
loại lỗi/dòng/cột. Full suite cuối **2.884 passed, 25 skipped, 1 deselected**
trên mỗi bộ dependency; [đối chiếu yêu cầu](doi-chieu-nghiem-thu-ke-hoach.md).

## Kết quả rà TLS và cấu hình môi trường (2026-10-15)

Lượt đầu chỉ đọc mã; lượt kiểm chứng bổ sung đã chạy listener thật, cụm hai worker,
ma trận cipher và test có sẵn. Không sửa mã thực thi hoặc YAML consumer.
Chi tiết, kết quả đối chứng và giới hạn ở
[`tls-web-va-cau-hinh-moi-truong.md`](tls-web-va-cau-hinh-moi-truong.md).

### 1. [P2 — đã xác nhận] Checker bỏ sót khóa TLS gõ sai trong `environments`

`YamlConfigLoader._load_single_file_environment()` chỉ kiểm tra hình dạng hai nhánh rồi
chọn nhánh hiệu lực (`xime/core/config/loader.py:134-159`). `xime check config` gọi loader
để kiểm tra cấu trúc, nhưng schema của `environments.local/server` không khai báo khóa
con nên checker không rà nội dung bên trong (`xime/cli/_config_check.py:144-158`,
`xime/cli/_config_spec.py:364-375`).

Ví dụ, gõ `websever` thay cho `webserver` trong `environments.server` vẫn qua phép kiểm
cấu trúc. `WebServerConfig.from_runtime()` không thấy `webserver` hoặc alias `server` nên
dùng cấu hình mặc định không TLS; `WebAdapter.resolve_tls()` kế thừa cấu hình đó và listener
có thể phục vụ HTTP thuần (`xime/adapters/web/_adapter.py:392-414`). Nếu listener công khai
được kỳ vọng dùng HTTPS, đây là đường cấu hình fail-open.

**Cần làm:** kiểm tra các khóa do framework sở hữu trong cấu hình hiệu lực và nhánh cần
triển khai, gồm cấu hình web và `ssl` trong endpoint, đồng thời giữ nguyên các khối riêng
của ứng dụng. Bổ sung đối chứng để checker phát hiện các lỗi gõ sai đã tái hiện. Không
đổi quy tắc chung thành “thiếu TLS thì cấm startup”, vì HTTP vẫn là chế độ được hỗ trợ.

**Đã tái hiện:** `websever` hoặc `ss1` trong overlay cho checker `clean`, Application khởi
động và trả HTTP 200, HTTPS bị từ chối. Đối chứng đặt cùng lỗi ở root được checker phát
hiện; cấu hình TLS đúng trả HTTPS 200. Lỗi riêng một nửa cert/key bị startup chặn.

**Đính chính mức ảnh hưởng:** hạ đánh giá “cao” ban đầu xuống P2. Cần lỗi cấu hình và
không có TLS chung để kế thừa; client HTTPS gặp lỗi kết nối, không tự chuyển sang HTTP.
Nguy cơ lộ dữ liệu chỉ khi client gửi HTTP thật. 12 cấu hình consumer nguồn được khảo sát
đang có khối TLS server được nhận dạng đúng; chưa thấy điều kiện lỗi này trong các khối đó.

### 2. [P2 — đã xác nhận] Mặc định Uvicorn 0.47.0 không giao cipher với một số client TLS 1.2

`pyproject.toml` đặt sàn `uvicorn[standard]>=0.47.0`. Khi ứng dụng không khai
`webserver.ssl.ciphers`, framework để Uvicorn chọn cipher mặc định. Hồ sơ đo ngày
2026-10-11 ghi nhận Uvicorn 0.47.0 dùng `TLSv1`; trên Windows/Python 3.14.8/OpenSSL 3.5.9,
client Python mặc định không có cipher chung ở TLS 1.2. Phép thử TLS 1.2 đạt khi
khai tường minh `ECDHE+AESGCM`. Xem
[`ke-hoach-reload-tls-web-va-management.md`](../sap-toi/ke-hoach-reload-tls-web-va-management.md)
mục 3.4. Uvicorn 0.48.0 đổi mặc định sang `None` để dùng cipher mặc định của OpenSSL
([release notes tại tag 0.48.0](https://github.com/Kludex/uvicorn/blob/0.48.0/docs/release-notes.md)).

**Tác động:** cài đúng phiên bản sàn 0.47.0 có thể làm client TLS 1.2 với danh sách cipher
không giao với server không kết nối được. TLS 1.3 đã đo hoạt động. Bằng chứng này không
kết luận mọi hệ điều hành hoặc mọi client TLS 1.2 đều lỗi.

**Cần làm:** cân nhắc nâng sàn lên 0.48.0 hoặc chọn giá trị mặc định đã kiểm chứng trên các
OpenSSL/client còn hỗ trợ. Không coi test dùng cipher tường minh là bằng chứng cho mặc định.

**Kiểm chứng mới:** RSA và ECDSA, TLS 1.2/1.3, cả startup lẫn sau reload. Uvicorn 0.47.0
mặc định bị reset ở TLS 1.2 với client mặc định; TLS 1.3 đạt. Khai `ECDHE+AESGCM` hoặc dùng
Uvicorn 0.48.0 mặc định thì cả hai protocol đạt. Hai file test TLS cũng đạt 42 ca trên 0.48.0.
Client TLS 1.2 chấp nhận cipher cũ tương thích vẫn kết nối được với 0.47.0; không kết luận
mọi client TLS 1.2 đều hỏng. Đây là lỗi tương thích có từ startup, không riêng thuật toán reload.

12/12 nhánh server consumer nguồn không khai cipher tường minh. Chưa đo runtime VPS nên
chưa thể nói các dịch vụ đã triển khai đang dùng 0.47.0 hoặc đang lỗi.

### 3. [Đã đính chính] Khác fingerprint chưa chứng minh lỗi reload hoặc mất an toàn TLS

Cụm hai worker thật với hai chứng thư khác nhau nhưng đều hợp lệ cho hostname trả
HTTP management 200 và 24/24 kết nối HTTPS xác thực thành công. Cùng một chứng thư DER,
chỉ thêm dòng trắng vào một file PEM, cũng tạo hai `certificate_fingerprint` khác nhau:
field hiện tại là hash nội dung file PEM/fullchain.

Ngược lại, hai worker cùng nạp một chứng thư hết hạn vẫn có cùng fingerprint và API 200,
nhưng cả 24 client đều từ chối TLS. Một worker dùng sai hostname cũng bị client từ chối.
Với cert/key không khớp, API trả 503/partial và context cũ tiếp tục phục vụ đúng.

**Rút lại khuyến nghị mặc định ép fingerprint bằng nhau hoặc đánh dấu partial chỉ vì
khác fingerprint.** HTTP 200 hiện xác nhận nạp được cấu hình file tại từng worker;
không cam kết kiểm định hostname/thời hạn thay client. Không thấy đường bỏ qua xác thực TLS.
Nên làm rõ ý nghĩa kết quả và fingerprint file trong tài liệu API; không mở việc sửa
thuật toán chỉ từ nhận định này.

**Cập nhật 2026-10-17:** mục 1 đã vá checker; mục 2 đã nâng sàn Uvicorn và đo TLS
theo Bước 4/5. Nhận định thứ ba vẫn được rút lại như lỗi chức năng; ý nghĩa
fingerprint và succeeded đã được làm rõ trong API reference song ngữ. Nội dung
phía trên giữ bằng chứng của lượt 15/10, không phải trạng thái bản vá hiện tại.

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
`docs/thiet-ke/03-diem-khoi-dong.md` mục Logging. Test:
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
