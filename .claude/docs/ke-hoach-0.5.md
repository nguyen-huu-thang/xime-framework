# Kế hoạch phiên bản 0.5 - "Kiểm toán toàn diện + Messaging/IoT + File"

> Chốt phạm vi ngày 2026-06-21 (nối tiếp sau khi phát hành 0.4.0).
>
> **Thay đổi định nghĩa 0.5:** bản gốc (chốt 2026-06-19) định nghĩa 0.5 là bản
> KHÔNG thêm tính năng, chỉ kiểm toán. Ngày 2026-06-21 chủ dự án quyết định
> **gộp thêm hai mảng tính năng mới** vào 0.5: (1) adapter messaging/IoT (MQTT),
> (2) hỗ trợ làm việc với file (storage starter + streaming ở web adapter). Phần
> kiểm toán vẫn giữ nguyên là trục chính.
>
> Nguồn gốc từng việc:
> - Audit toàn diện: định nghĩa 0.5 cũ trong `lo-trinh-phien-ban.md`.
> - Adapter MQTT/embedded: đề xuất trực tiếp của chủ dự án (2026-06-21).
> - File storage + streaming: đề xuất trực tiếp của chủ dự án (2026-06-21).
> - Issue context bleeding khi test ASGI in-process: phát hiện ở dự án
>   dental-clinic (`D:\code\Monolithic\dental-clinic\.claude\framework-issues\issue-001-security-context-shared-asgi.md`).

---

## Nguyên tắc xuyên suốt

1. **Audit trước, feature sau.** Đọc kỹ và vá lõi trước khi chồng thêm hai
   adapter/starter mới lên, để không kiểm toán trên nền đang thay đổi.
2. **Theo đúng pattern đã có.** MQTT đứng ngang `web/grpc/socket` trong
   `adapters/`; storage đứng ngang `cache/redis` trong `starters/`. Cùng quy ước:
   `__init__.py` + `_*.py` private, `__all__` chỉ liệt kê class DI quản lý, đọc
   runtime config qua `RuntimeConfig`, đóng tài nguyên ở `pre_destroy()`.
3. **Framework chỉ cấp cơ chế, không ôm chính sách.** Storage trả/nhận dữ liệu
   thô; authorization, định dạng, đặt tên file là việc của app.
4. **Không thêm dependency bắt buộc.** Thư viện MQTT và S3 import lười ở module
   private (giống `scheduler` nạp apscheduler, `redis` nạp redis.asyncio), khai
   báo qua extras (`xime[mqtt]`, `xime[s3]`). Service không dùng thì không phải cài.
5. **Nhất quán vòng đời context.** Mọi adapter mới phải set `request_id` lúc nhận
   message/request và `clear()` + `clear_security()` lúc teardown, giống web/grpc/
   socket (đây cũng là một trục audit ở Nhóm A).

---

## Nhóm A - Kiểm toán toàn diện (trục chính, làm TRƯỚC)

> Bản gốc: đọc kỹ, chi tiết TỪNG FILE để tìm mọi vấn đề tiềm ẩn và mâu thuẫn
> logic giữa các phần. KHÔNG vừa đọc vừa sửa lung tung - ghi phát hiện vào báo
> cáo `docs/kiem-toan-0.5.md`, phân loại theo mức nghiêm trọng, rồi mới vá.

Phạm vi kiểm toán (đọc thật kỹ, không lướt):

- **Toàn bộ `xime/core/`** - DI container (scan, resolver, graph, registry),
  lifecycle, config hai tầng, context (`ContextVar`), event bus, security,
  transaction, exception hierarchy, metadata. Đây là nền, soi trước.
- **Toàn bộ `xime/adapters/`** - web, grpc (codefirst + client + tls +
  interceptors), socket. Soi từng file.
- **Toàn bộ `xime/starters/`** - sqlalchemy, jwt, scheduler, cache, redis.

Các trục cần soi xuyên suốt:

1. **Mâu thuẫn logic giữa các phần** - thứ tự interceptor (RequestContext ->
   Error -> custom), vòng đời context set/clear nhất quán giữa web/grpc/socket,
   error mapping có đồng nhất ba transport không.
2. **Nhất quán cross-cutting** - các key trong `request_context` (request_id,
   peer_*, caller...), `clear_security()` luôn chạy ở teardown mọi adapter, quy
   ước mã lỗi/exception giống nhau giữa REST/gRPC/socket.
3. **An toàn async / race condition** - tiền lệ #7 (channel rotation). Soi mọi
   chỗ chia sẻ state mutable giữa coroutine: registry, tls registry, client
   channels, event bus tasks.
4. **Rò rỉ tài nguyên** - channel (retired pool), AsyncSession, socket, scheduler
   job, gRPC server, redis pool. PreDestroy đóng đủ và đúng thứ tự không.
5. **Fail-fast lúc startup** - mọi sai cấu hình (thiếu binding, thiếu type hint,
   circular, thiếu provider TLS, controller lệch server_id) có nổ rõ ràng lúc
   startup không, hay âm thầm hỏng lúc runtime.
6. **Edge case marshal/serialize** - bytes/decimal/uuid/date/optional/repeated/
   map/nested/enum. Đã từng có bug ở đây (#3, #marshal bytes) -> soi kỹ lại.
7. **Khoảng trống test** - `tests_temp/` (tên gợi ý thư mục tạm, cân nhắc chuẩn
   hóa thành `tests/`). Tìm nhánh code chưa có test, nhất là đường lỗi và teardown.
8. **Dọn backlog tồn đọng** - đối chiếu `backlog-sua-loi.md`, mục `[ ]` còn mở ở
   `grpc-client-mtls-plan.md`, TODO rải trong code.

### A.x - Mục cụ thể đã biết: context bleeding khi test ASGI in-process (issue dental-clinic #001)

- **Hiện tượng:** test bằng `httpx.ASGITransport` (in-process, không qua uvicorn),
  trong cùng một `AsyncClient`: request 1 có Bearer token -> request 2 KHÔNG token
  vẫn "thấy" user cũ -> endpoint cần đăng nhập trả 200 thay vì 401.
- **Mức độ:** THẤP. Production (uvicorn) KHÔNG dính - mỗi request một asyncio task,
  context copy riêng. Chỉ ảnh hưởng test in-process dùng chung client/context.
- **Đã có sẵn cái gì:** `RequestContextMiddleware.dispatch()` ĐÃ gọi
  `clear_security()` trong `finally` (`xime/adapters/web/middleware/_context.py:29-31`).
  Nên đây KHÔNG phải "quên clear".
- **Gốc rễ (giả định mạnh):** lỗi kinh điển của Starlette `BaseHTTPMiddleware` -
  nó chạy `call_next` trong một **context con tách biệt** (anyio task), nên
  ContextVar mà `JwtAuthMiddleware` (lớp trong) set KHÔNG cùng context với
  `clear_security()` của middleware ngoài -> lệnh clear "trượt" sang context khác,
  giá trị thật giữ lại sang request sau khi context được tái dùng.
- **Hướng sửa đề xuất:** chuyển `RequestContextMiddleware` (và cân nhắc cả
  `JwtAuthMiddleware`) từ `BaseHTTPMiddleware` sang **pure ASGI middleware**
  (`async def __call__(self, scope, receive, send)`), set/clear ContextVar trong
  CÙNG một context với app downstream. Đây là cách Starlette khuyến nghị cho
  ContextVar. Kiểm tra lại toàn bộ middleware web có dùng `BaseHTTPMiddleware`
  hay không khi audit.
- **Test cần thêm:** một test ASGITransport tái hiện đúng kịch bản (request có
  token -> request không token kỳ vọng 401) trong `tests_temp/web/`, để chốt là
  đã hết rò rỉ.

---

## Nhóm B - Adapter Messaging / IoT (MQTT)

> Mục tiêu: thêm một adapter cho thiết bị nhúng/IoT giao tiếp qua MQTT. Đây là
> adapter **message-driven (pub/sub)**, KHÁC mô hình request/response của
> web/grpc/socket -> thiết kế riêng, KHÔNG bê nguyên `contract.json` của
> gRPC/socket sang.

### B.1 - Định vị kiến trúc

- Thư mục: `xime/adapters/mqtt/` (mở rộng tương lai có thể gom thành họ
  `adapters/messaging/` nếu thêm CoAP/AMQP, nhưng 0.5 chỉ làm MQTT - chưa cần
  trừu tượng hóa sớm).
- Mô hình: subscribe topic -> nhận message -> dispatch tới handler; publish ra
  topic. Gần với event hơn là RPC. KHÔNG có khái niệm "response bắt buộc" như RPC.
- Thư viện đề xuất: `aiomqtt` (asyncio thuần, bọc paho-mqtt). Import lười ở module
  private, khai báo extra `xime[mqtt]`.

### B.2 - Đăng ký handler (routing)

- Decorator kiểu `@subscribe("sensors/+/temperature", qos=1)` trên method của
  controller (đặt cùng tầng routing như `@get`/`@command`). Topic wildcard MQTT
  (`+`, `#`) hỗ trợ.
- Handler nhận payload (`bytes` thô + topic + thuộc tính message). Framework KHÔNG
  tự deserialize - app tự parse JSON/protobuf tùy ý (nhất quán với chính sách
  "không ôm serialize" của `CacheService`).
- Class-based controller giống `routing-layer.md`: `_make_handler` đọc decorator,
  build bảng topic -> bound method, resolve qua DI.

### B.3 - Publish

- Cấp một `MqttPublisher` (singleton DI) để code nghiệp vụ `await publisher.publish(topic, payload, qos=..., retain=...)`.
- Đặt ở chỗ inject được qua constructor như mọi service khác.

### B.4 - Vòng đời + cấu hình

- Provider giữ kết nối: connect lúc adapter `start()`, `pre_destroy()` ->
  disconnect sạch. **Auto-reconnect** khi mất kết nối (aiomqtt có sẵn cơ chế, cần
  bọc lại để re-subscribe toàn bộ topic sau reconnect).
- Runtime config (`mqtt.*` trong `application.yml`): `host`, `port`, `username`/
  `password` (tùy chọn), `client_id`, `tls` (tùy chọn), `keepalive`, LWT (last
  will), QoS mặc định. Thiếu `host` -> fail-fast `ValueError`.
- request_context: mỗi message set `request_id` mới (UUID) + `clear()` +
  `clear_security()` lúc xử lý xong, ĐÚNG như các adapter khác (xem Nhóm A trục 2).

### B.5 - Câu hỏi mở (quyết khi thiết kế chi tiết)

- Có cần "RPC over MQTT" (request/reply qua `response_topic` + correlation id) hay
  0.5 chỉ làm pub/sub một chiều? Đề xuất: 0.5 chỉ pub/sub, RPC để wishlist.
- Một controller có nên dùng chung được cho cả MQTT lẫn web/grpc không, hay MQTT
  có controller riêng? (pub/sub không có return value nên khả năng dùng chung thấp).
- Backpressure/concurrency: xử lý message tuần tự hay song song có giới hạn?
- TLS client cert cho MQTT (giống mTLS gRPC) - có lưu danh tính peer vào
  request_context như `peer_cn` không?

> **Đã dời khỏi 0.5:** fieldbus công nghiệp (Modbus TCP + OPC UA) ban đầu định
> gộp vào đây, nay dời sang **0.7** (quyết 2026-06-21) để 0.5 không phình. Chi
> tiết thiết kế: `ke-hoach-0.7.md`.

---

## Nhóm C - Làm việc với File (Storage starter + Streaming web)

> Phạm vi chốt 2026-06-21: **storage backend (starter) + streaming ở web adapter**
> (mức rộng, không chỉ storage). Hiện framework để FastAPI tự lo upload/download;
> cái thiếu là abstraction lưu trữ và tiện ích streaming file lớn.

### C.1 - Storage starter (abstraction backend) - theo pattern cache/redis

- `xime/starters/storage/` - Protocol `StorageService` (interface thuần, tách
  backend), giống cách `cache/` định nghĩa `CacheService`.
- Method (chốt khi thiết kế, nháp):
  - `async def put(self, key: str, data: ...) -> None`
  - `async def get(self, key: str) -> ...`
  - `async def open_stream(self, key: str) -> AsyncIterator[bytes]` (đọc file lớn
    không nạp hết vào RAM)
  - `async def delete(self, key: str) -> None`
  - `async def exists(self, key: str) -> bool`
  - `async def url(self, key: str, expires: int | None = None) -> str` (presigned
    URL - backend nào không hỗ trợ thì raise rõ ràng)
- **Câu hỏi mở - kiểu dữ liệu:** `bytes` thô cho file nhỏ vs **async stream
  (AsyncIterator[bytes] / file-like)** cho file lớn. Đề xuất hỗ trợ cả hai:
  `put`/`get` cho nhỏ, `put_stream`/`open_stream` cho lớn. Cần chốt để không phá
  interface về sau.
- Backend ship trong 0.5 (câu hỏi mở):
  - `local` (filesystem) - chắc chắn làm, không cần dependency ngoài.
  - `s3`/MinIO - dùng `aioboto3`/`aiobotocore`, extra `xime[s3]`, import lười. Cân
    nhắc có kịp 0.5 hay đẩy 0.6.

### C.2 - Streaming ở web adapter

- Tiện ích **download stream**: helper trả `StreamingResponse` từ
  `StorageService.open_stream(key)`, hỗ trợ `Range` request (resume tải), set
  `Content-Type`/`Content-Disposition` đúng.
- Tiện ích **upload lớn**: nhận multipart/stream từ FastAPI `UploadFile` và ghi
  thẳng vào storage theo chunk (không nạp hết vào RAM), có giới hạn dung lượng
  (fail rõ ràng khi vượt).
- Cân nhắc: presigned URL upload trực tiếp lên S3 (client upload thẳng, không qua
  service) - tiện cho file lớn, giảm tải service. Có thể để 0.6.

### C.3 - Câu hỏi mở

- Storage shipping 0.5: chỉ `local`, hay `local` + `s3` cùng đợt?
- Multipart resumable / chunked upload (tUS-style) có làm 0.5 không hay để sau?
- Quản lý metadata file (size, content-type, checksum) - framework lưu hay app tự lo?

---

## Thứ tự thực thi đề xuất

```text
Nhóm A (audit)   → core → adapters → starters, ghi kiem-toan-0.5.md, vá theo mức
                   nghiêm trọng (gồm fix issue #001 chuyển sang pure ASGI middleware)
Nhóm C (file)    → C.1 storage starter (local trước) → C.2 streaming web → test
Nhóm B (MQTT)    → B.1-B.4 adapter + publisher + lifecycle → test
Phát hành        → cập nhật cay-thu-muc.md, tai-lieu-thiet-ke.md, CHANGELOG,
                   bump 0.5.0, chạy full pytest
```

Lý do thứ tự: audit trước (nền sạch mới chồng feature); file (theo pattern starter
quen thuộc, rủi ro thấp) trước MQTT (adapter mới, mô hình pub/sub khác, rủi ro cao
hơn). Fieldbus công nghiệp (Modbus/OPC UA) đã dời sang 0.7 (`ke-hoach-0.7.md`).

## Việc cần xác nhận trước khi code

1. **MQTT:** 0.5 chỉ pub/sub một chiều hay làm luôn request/reply over MQTT?
2. **MQTT:** thư viện `aiomqtt` có ổn không, hay muốn paho thuần / gmqtt?
3. **Storage:** ship `local` thôi hay `local` + `s3` trong 0.5?
4. **Storage:** interface dùng `bytes` + stream song song, hay ép tất cả về stream?
5. **Upload lớn:** có cần multipart resumable trong 0.5 không?
6. **Audit:** có chuẩn hóa `tests_temp/` -> `tests/` trong đợt này luôn không?
