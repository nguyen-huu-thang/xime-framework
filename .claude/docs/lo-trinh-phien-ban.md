# Lộ trình phiên bản Xime Framework

> Chỉ mục tổng các mốc phiên bản đã chốt, để tra nhanh "việc X làm ở bản nào".
> Chi tiết từng mục nằm ở các doc được trỏ tới. Cập nhật 2026-07-29.
> Hiện tại: **0.7.0** (pyproject + CHANGELOG + `xime/__init__.py` đã đồng bộ 0.7.0).

| Bản | Chủ đề | Trạng thái |
| --- | --- | --- |
| 0.3 | Hardening + hoàn tất gRPC | Đã phát hành (2026-06-20) |
| 0.4 | Cross-cutting + starters | Đã phát hành (2026-06-20) |
| 0.5 | Kiểm toán toàn diện + Messaging/IoT (MQTT) + File | Đã phát hành (2026-06-22) |
| 0.6 | Thay `dependency-injector` + dynamic interface binding | Đã phát hành (2026-06-23) |
| 0.6.1 | Web adapter: middleware lấy DI/config qua marker + `configure_cors`; SQLAlchemy starter: `CrudRepository` | Đã phát hành (2026-06-29) |
| 0.6.2 | Starter `mail` (SMTP) + hardening sau kiểm toán toàn diện | Đã phát hành (2026-06-30) |
| 0.6.3 | Gỡ chặn app chạy thật: `PEER_APP_ID` (định danh app từ SAN cert) + **TLS/HTTPS cho web adapter** + **khối chỉ đọc `read_only()`**; kèm `get_bool` ép kiểu cờ + metadata gói | Đã phát hành (2026-07-29) |
| 0.7 | Fieldbus công nghiệp (Modbus TCP + OPC UA) | **Code xong (2026-07-30), chưa commit** - 1463 test. Đã kiểm toán trước khi đẩy PyPI, xem `kiem-toan-0.7.md` |
| 0.8 | Multi-process Runtime + Bus liên Worker + config cải thiện | Thiết kế ban đầu chốt 2026-06-27; chưa code |
| 0.9 | Beta - config nốt + bug fix + phản hồi người dùng | Mở |

---

## Mức độ chín (PyPI `Development Status`) theo phiên bản

> Quyết định của chủ dự án 2026-06-23. `Development Status` là classifier trong
> `pyproject.toml`, phản ánh độ ổn định API chứ không buộc cứng theo số version.

| Bản | Classifier | Lý do |
| --- | --- | --- |
| 0.6 -> 0.7 (hiện tại) | `3 - Alpha` | Đang dùng |
| 0.7 | `3 - Alpha` | **Vẫn còn thêm tính năng lớn** (Fieldbus). API chưa đông cứng. |
| 0.8 | `3 - Alpha` | **Vẫn còn thêm tính năng lớn** (Multi-process Runtime). API chưa đông cứng. |
| 0.9 | `4 - Beta` | Chỉ sửa nhỏ + chờ feedback; API coi như đã chốt, hardening trước 1.0. |
| 1.0 trở đi | `5 - Production/Stable` | Bản ổn định. |

Quá trình tiến tới 1.0: 0.8 thêm tính năng Runtime + chỉnh config một phần, 0.9 dọn
nốt config + chờ feedback, 1.0 stable.

**Việc cần làm khi phát hành các bản tương ứng** (chỉ sửa `pyproject.toml`):

- **0.7:** ✅ đã giữ `Development Status :: 3 - Alpha` khi phát hành. (Phần vá
  metadata từng xếp vào đây - classifier `Typing :: Typed` + license PEP 639 -
  đã làm ở 0.6.3.)
- **0.8:** giữ `Development Status :: 3 - Alpha`.
- **0.9:** đổi `3 - Alpha` -> `4 - Beta`.
- **1.0:** đổi `4 - Beta` -> `5 - Production/Stable`.

---

## 0.3 - Hardening & hoàn tất gRPC

Chi tiết đầy đủ: `ke-hoach-0.3.md`.

- Nhóm 1 vá bug: warn `def` vs `async def` (#9), interceptor abort hai lần (#2),
  default `str(exc)` lộ nội bộ (#1a), `asyncio.Lock` cert rotate (#7), bỏ
  hardcode `server_id="default"` (#8).
- Nhóm 2: retry policy YAML cho gRPC client.
- Nhóm 4: bump `0.3.0` + cập nhật docs + CHANGELOG.

## 0.4 - Cross-cutting + starters

Chi tiết kế hoạch: `ke-hoach-0.4.md`. Nguồn ý tưởng: `wishlist-tinh-nang.md`
(mục "Security / Cross-cutting" và "Starters").

- Trích xuất danh tính peer mTLS (CN client cert) -> `request_context`, key
  trung tính + helper `current_caller()`. (đề xuất notification mục 1)
- `cache/` starter (Protocol `CacheService`) + `redis/` starter (client +
  impl của CacheService).
- Cân nhắc thêm (chưa chốt cứng): gRPC reflection + health checking; error
  catalog visibility-aware (#1b).

## 0.5 - Kiểm toán toàn diện + Messaging/IoT + File

> **ĐÃ PHÁT HÀNH 2026-06-22.** Cả ba nhóm hoàn tất: audit toàn diện (báo cáo
> `kiem-toan-0.5.md`, mọi phát hiện đã xử lý), adapter MQTT (pub/sub + RPC over
> MQTT v5), storage starter (local + s3/MinIO) + streaming web. Test: 1051 passed,
> 4 skipped. Chi tiết thực thi: `ke-hoach-trien-khai-0.5.md`.

Chi tiết đầy đủ: `ke-hoach-0.5.md`. Kế hoạch THỰC THI chi tiết (thứ tự code,
file nào, pattern nào) + các quyết định đã chốt 2026-06-22:
`ke-hoach-trien-khai-0.5.md`.

> **Đổi phạm vi 2026-06-21:** bản gốc (chốt 2026-06-19) là bản KHÔNG thêm tính
> năng, chỉ kiểm toán. Chủ dự án quyết định gộp thêm hai mảng feature: **adapter
> MQTT (messaging/IoT)** và **làm việc với file (storage starter + streaming web)**.
> Audit vẫn là trục chính, làm trước; feature làm sau trên nền đã sạch.

- **Nhóm A - Kiểm toán toàn diện** (trục chính): đọc kỹ TỪNG FILE core/adapters/
  starters, ghi `docs/kiem-toan-0.5.md`, phân loại theo mức nghiêm trọng rồi mới
  vá. Gồm fix issue context-bleeding khi test ASGI in-process (dental-clinic #001):
  chuyển `RequestContextMiddleware` từ `BaseHTTPMiddleware` sang pure ASGI middleware.
- **Nhóm B - Adapter MQTT**: pub/sub message-driven (`@subscribe`) và RPC over
  MQTT v5 (`@rpc`), `MqttPublisher`, auto-reconnect, định tuyến bằng Subscription
  Identifier, extra `xime[mqtt]` (aiomqtt import lười).
- **Nhóm C - File**: storage starter (Protocol `StorageService`, backend local
  và s3/MinIO) theo pattern cache/redis, kèm streaming upload/download lớn ở web
  adapter (Range, multipart, chunked).

Phạm vi kiểm toán (đọc thật kỹ, không lướt):

- **Toàn bộ `xime/core/`** - DI container (scan, resolver, graph, registry),
  lifecycle, config hai tầng, context (`ContextVar`), event bus, security,
  transaction, exception hierarchy, metadata. Đây là nền, soi trước.
- **Toàn bộ `xime/adapters/`** - web, grpc (codefirst + client + tls +
  interceptors), socket. Soi từng file.
- **Toàn bộ `xime/starters/`** - sqlalchemy, jwt, scheduler (+ cache/redis nếu
  0.4 đã thêm).

Các trục cần soi xuyên suốt:

1. **Mâu thuẫn logic giữa các phần** - vd thứ tự interceptor (RequestContext ->
   Error -> custom), vòng đời context được set/clear nhất quán giữa web/grpc/
   socket, error mapping có đồng nhất ba transport không.
2. **Nhất quán cross-cutting** - các key trong `request_context` (request_id,
   peer_*, caller...), việc `clear_security()` luôn chạy ở teardown mọi adapter,
   quy ước mã lỗi/exception giống nhau giữa REST/gRPC/socket.
3. **An toàn async / race condition** - đã có tiền lệ #7 (channel rotation).
   Soi mọi chỗ chia sẻ state mutable giữa coroutine: registry, tls registry,
   client channels, event bus tasks.
4. **Rò rỉ tài nguyên** - channel (retired pool), AsyncSession, socket, scheduler
   job, gRPC server. PreDestroy có đóng đủ và đúng thứ tự không.
5. **Fail-fast lúc startup** - mọi sai cấu hình (thiếu binding, thiếu type hint,
   circular, thiếu provider TLS, controller lệch server_id) có nổ rõ ràng lúc
   startup không, hay âm thầm hỏng lúc runtime.
6. **Edge case marshal/serialize** - bytes/decimal/uuid/date/optional/repeated/
   map/nested/enum. Đã từng có bug ở đây (#3, #marshal bytes) -> soi kỹ lại.
7. **Khoảng trống test** - `tests_temp/` (tên cho thấy có thể là thư mục tạm,
   cân nhắc chuẩn hóa thành `tests/`). Tìm nhánh code chưa có test, nhất là
   đường lỗi và teardown.
8. **Dọn backlog tồn đọng** - đối chiếu `backlog-sua-loi.md`, các mục `[ ]` còn
   mở ở `grpc-client-mtls-plan.md` (dọn dẹp data-service phía service), TODO
   rải trong code.

Cách làm đề xuất khi tới 0.5: đi theo từng package, mỗi file ghi phát hiện vào
một báo cáo kiểm toán (`docs/kiem-toan-0.5.md`), phân loại theo mức nghiêm trọng,
rồi mới vá. KHÔNG vừa đọc vừa sửa lung tung để tránh bỏ sót.

## 0.6 - Thay `dependency-injector` + dynamic interface binding

Kế hoạch chi tiết: `ke-hoach-0.6.md`. **Cả hai việc ĐÃ CODE XONG 2026-06-23**;
full suite **1084 passed / 4 skipped**.

- **Việc 1** - thay `dependency-injector` bằng registry singleton tự viết:
  `registry.py` viết lại bằng dict + `RLock` double-checked, API không đổi, đã gỡ
  thư viện khỏi `pyproject.toml`; benchmark build ~8x / warm get() ~2x nhanh hơn
  backend cũ.
- **Việc 2** - dynamic interface binding: **mở rộng chính `bind`** - value có thể
  là tuple nhiều impl (phần tử đầu = mặc định); bật/tắt bằng cờ runtime
  `xime.di.dynamic-binding` (mặc định tắt = hành vi cũ); khi bật, đổi động **toàn
  cục** qua `Switcher` (`use`/`reset`) với **proxy trong suốt** (`DynamicProxy`)
  nên consumer giữ nguyên code. KHÔNG thêm `bind_many`/`Switchable`. Chuẩn hóa
  binding làm trong `_prepare_dynamic_binding()` (không sửa resolver); `Switcher`
  luôn đăng ký (disabled khi tắt cờ); cờ tắt không auto-register impl. Chi tiết +
  ghi chú thực thi: `ke-hoach-0.6.md` mục 2.5/2.7.

Đã phát hành: version `pyproject.toml` + CHANGELOG đồng bộ 0.6.0 (commit `v 0.6.0`).

## 0.6.1 - Web adapter: middleware lấy DI/config qua marker + `configure_cors`

Bản vá nhỏ (phát hành 2026-06-29), tương thích ngược hoàn toàn. Xuất phát từ thực
tế hai app (`shop`, `dental-clinic` ở `D:\code\Monolithic`) phải subclass
`WebAdapter` chỉ để gắn JWT middleware cần service từ DI và CORS đọc từ config.

- **Marker `Inject` / `FromConfig`** (`adapters/web/_markers.py`): dùng làm giá trị
  option khi gọi `configure_middleware(...)`, framework phân giải lúc `build_app`
  (sau khi DI container dựng xong). `Inject(SomeType)` -> singleton DI;
  `FromConfig("a.b", default)` -> `RuntimeConfig` theo dot-notation. Giá trị không
  phải marker giữ nguyên.
- **`configure_cors(...)`** (`adapters/web/_cors.py`): helper CORS hạng nhất theo
  pattern `configure_*`; tham số để trống tự đọc `cors.<tên>` từ `application.yml`,
  thiếu thì về mặc định Starlette.
- **`CrudRepository[T]`** (`starters/sqlalchemy/repository.py`): base repository
  generic cho sẵn CRUD chung (`find/find_or_fail/find_all/exists/count/save/
  save_all/delete`) + exception `EntityNotFoundError` - giảm boilerplate
  `BaseRepository` mỗi app tự viết (xuất phát từ issue-003 của `shop`). `model` là
  abstract property -> lớp nền là abstract, DI scanner bỏ qua; chỉ subclass set
  `model` mới vào DI nên không sinh singleton thừa.
- Full suite **1101 passed / 4 skipped**. Không có doc kế hoạch riêng; chi tiết
  trong CHANGELOG mục `[0.6.1]`, `rules/config-discovery.md` và `docs/.../starters.md`.

## 0.6.2 - Starter `mail` (SMTP) + hardening sau kiểm toán

Phát hành 2026-06-30. Thêm starter `mail` theo đúng khuôn starter sẵn có
(Protocol `MailService` + backend `SmtpMailService` qua aiosmtplib, extra
`xime[mail]`), kèm hardening từ **kiểm toán toàn diện** (`kiem-toan-0.6.md`:
không có lỗi CAO). Full suite **1125 passed / 4 skipped**. Chi tiết: CHANGELOG
mục `[0.6.2]`.

## 0.6.3 - Gỡ chặn app chạy thật: `PEER_APP_ID` + TLS web adapter + `read_only()`

Phát hành 2026-07-29. Tương thích ngược hoàn toàn. Full suite **1223 passed /
5 skipped**. Chi tiết: CHANGELOG mục `[0.6.3]`.

Hai việc đầu xuất phát từ khảo sát "4 mắt xích còn đứt" khi đưa 6 app lên chạy
thật (`D:\code\xime\.claude\docs\khao-sat-ha-tang-cho-app-chay-that.md`); việc
thứ ba đến từ phản hồi khi viết app.

- **`PEER_APP_ID` - định danh APPLICATION từ SAN client cert.** Cert của tiến
  trình thuộc một app mang SAN URI `xime-app://<Base62 33 ký tự>`; framework đọc
  ra, cắt scheme, lưu cạnh `PEER_CN` trong `request_context`, phơi qua
  `current_app_id()`. `PEER_CN` = tiến trình gọi, `PEER_APP_ID` = app sở hữu tiến
  trình đó. SAN là property **nhiều giá trị** nên duyệt hết entry; fail-soft
  tuyệt đối; framework không giải mã, không kiểm quyền. Bối cảnh + kiểm chứng:
  `peer-app-id-tu-san-cert.md`.
- **TLS/HTTPS cho web adapter** (mục A1 của khảo sát). Khối `server.ssl` trong
  `application.yml` -> `ServerTlsConfig`; để trống = HTTP thuần như cũ.
  `cert_reqs` dùng chữ (`none`/`optional`/`required`) thay vì số `ssl.CERT_*`.
  Validate fail-fast trong `_tls_kwargs()` vì lỗi gốc của uvicorn khi cert khai
  nửa vời là không debug được (`AssertionError` rỗng message). Multi-server:
  `WebAdapter(..., ssl=...)`, để trống thì **kế thừa** `server.ssl` để server phụ
  không âm thầm chạy HTTP. **Mức 2 (cert in-memory) đã BỎ HẲN** - nó không tránh
  được việc key chạm đĩa nên không giải quyết được vấn đề nó sinh ra để giải
  quyết; thay bằng ghi chú "mức 1.5" (nạp đè `load_cert_chain` lên context đang
  phục vụ, đã kiểm chứng bằng handshake thật) cho lúc cần gia hạn không restart.
  Chi tiết + quyết định: `tls-cho-web-adapter.md`.
- **Khối chỉ đọc `read_only()`** - trước đó mọi truy cập DB, kể cả một câu
  `SELECT`, đều phải bọc `async with self.transaction():`, nên service chỉ đọc vẫn
  phải nhận `TransactionManager` và khối transaction xuất hiện dày tới mức không
  còn cho biết chỗ nào thật sự có ghi. Nay có `ReadOnlyManager` -
  manager **riêng, cùng cấp** với `TransactionManager` (chốt như vậy để sau này
  trỏ đường đọc sang read replica chỉ bằng một dòng `bind`). Không bao giờ commit;
  lồng nhau thì mượn session đang chạy; `expunge_all()` trước `rollback()` để
  entity còn dùng được sau khối. Framework **không chặn** việc sửa entity đọc
  ngoài transaction - cố ý, bù bằng quy tắc tài liệu. Chi tiết:
  `rules/transaction.md`, `docs/{vn,en}/transaction.md`.
- **`RuntimeConfig.get_bool()`** - vá B1: cờ `xime.di.dynamic-binding` từng đọc
  bằng `bool()` trần nên `"false"` dạng chuỗi bật nhầm tính năng. Nay ép kiểu
  bằng chính bộ parse boolean của Pydantic, giá trị lạ -> `StartupException`.
- **Metadata gói**: classifier `Typing :: Typed` + license PEP 639 (dời từ 0.7).
  Thêm `cryptography` vào extra `dev` (test TLS cần sinh cert tự ký).
- **Docstring `DynamicProxy`** - ghi caveat B2 về thứ tự `post_construct` khi bật
  dynamic binding (không đổi code).

## 0.7 - Fieldbus công nghiệp (Modbus TCP + OPC UA)

Chi tiết đầy đủ + thiết kế đã chốt: `ke-hoach-0.7.md`. Dời từ 0.5 (quyết 2026-06-21).
**Thiết kế chốt 2026-06-23** (chủ dự án trả lời hết câu hỏi mở); **bốn điểm chờ
quyết cuối cùng chốt 2026-07-29** - không còn gì chặn việc bắt tay code.

- **Chốt 2026-07-29:** pool connection Modbus **key theo TÊN LOGIC** của thiết bị
  (`modbus.devices.<tên>`, đúng khuôn `client_id` của MQTT); `read(device)` **gom
  nhiều range** thay vì một block lớn (block lớn quét trúng địa chỉ thiết bị không
  có -> ILLEGAL DATA ADDRESS, hỏng cả lần đọc); slave **tách datastore theo
  `unit_id`**; phát hành **trọn gói `0.7.0`** cả Modbus lẫn OPC UA. Kèm **bước 0**
  bắt buộc: cài `pymodbus` (nay đã 3.14) + `asyncua` và xác minh API thật trước
  khi viết codec.

- Xime đóng vai client/master chủ động đọc PLC/thiết bị nhà máy - mô hình
  polling/subscribe, khác cả RPC lẫn pub/sub của MQTT.
- **Đã chốt:** không edge gateway (giao tiếp trực tiếp) -> CẦN làm; Modbus làm CẢ
  client lẫn server; CẢ polling + on-demand; OPC UA hỗ trợ TẤT CẢ mức security;
  làm CẢ Modbus và OPC UA trong 0.7.
- **Trục chính = Device Model khai báo** (`@device`/`@node_model` + field
  descriptor `Holding/Coil/Input/Node`, framework lo decode/encode thanh ghi -
  tương đương DTO/contract của fieldbus, đây là chỗ "framework làm nhiều việc").
- Luồng device-driven dùng decorator riêng `@poll`/`@on_change`/`@serve`/
  `@on_write` trong adapter (tái dùng hạ tầng concurrency của MQTT), KHÔNG dựa
  scheduler. Hai adapter độc lập, import lười, extra `xime[modbus]`/`xime[opcua]`.

## 0.8 - Multi-process Runtime + Bus liên Worker + config cải thiện

Trạng thái: **Thiết kế ban đầu chốt 2026-06-27**, chưa code. Chi tiết đầy đủ:
`ke-hoach-0.8.md`.

Hai mảng chính:

**Mảng 1 - Multi-process Runtime với Bus liên Worker** (tính năng mới lớn):

- **Mặc định TẮT** - phải bật tường minh trong cấu hình (giống dynamic-binding
  0.6); khi tắt, ứng dụng chạy single-process như hiện tại, không ảnh hưởng gì.
- N worker process (mặc định = số nhân CPU), mỗi worker: FastAPI app + DI
  container + singleton + event loop, hoàn toàn độc lập về dữ liệu.
- Một shared queue duy nhất + mutex ghi (không phải per-worker SPSC) - đủ vì
  traffic inter-worker thấp (config sync, cert rotation, cache invalidation).
- Bus Manager quản lý queue, route message, quản lý lifecycle worker.
- DI scope mới: `global` (một instance duy nhất toàn hệ thống, sống ở Worker 0;
  worker khác inject vào → startup fail; Worker 0 chết → restart, không được →
  crash toàn chương trình) và `worker` (mặc định, một instance mỗi worker).
- API 0.8 chỉ có broadcast; point-to-point để sau.
- Transport abstraction (SharedMemory / UnixSocket / Redis / TCP) giữ nguyên
  như ý tưởng ban đầu; 0.8 implement SharedMemoryTransport.
- `core/event/` (intra-process) và Bus này (inter-process) độc lập nhau.
- Còn mở: tên các hàm API Bus, cú pháp khai báo scope trong DI, HTTP request
  routing đến worker (defer hẳn).

**Mảng 2 - Config cải thiện** (nhỏ, phần còn lại để 0.9):

- Rà pattern `configure_*`, ranh giới hai tầng Framework/Runtime config.
- Chi tiết xác định khi bắt tay code.

## 0.9 - Beta: config nốt + bug fix + phản hồi người dùng

Trạng thái: **Mở**.

- Phần config cải thiện còn lại từ 0.8 (nếu có).
- Bug fix từ phản hồi người dùng sau 0.8.
- Đổi classifier sang `4 - Beta` khi phát hành.
- KHÔNG thêm tính năng lớn mới.

## Chưa gắn mốc (wishlist thuần)

Xem `wishlist-tinh-nang.md`: bidi streaming, `@proto_field`, sinh SDK từ
ContractModel, SDK đa ngôn ngữ, socket Transport -> TCP/Named Pipe, idempotency
helper, gRPC reflection/health (nếu 0.4 không lấy).
