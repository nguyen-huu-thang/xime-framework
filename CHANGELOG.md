# Changelog

Tất cả thay đổi đáng chú ý của Xime Framework được ghi ở đây.

Định dạng theo [Keep a Changelog](https://keepachangelog.com/), phiên bản theo
[Semantic Versioning](https://semver.org/lang/vi/).

## [0.6.2] - 2026-06-30

Thêm **starter `mail`** - gửi email qua SMTP theo đúng khuôn mẫu starter sẵn có
(`storage`/`cache`): một Protocol `MailService` + backend `SmtpMailService`, app
bind trong `config/dependency.py`. Tương thích ngược hoàn toàn. Test starter:
17 passed.

### Added

- **Starter `mail` (`xime.starters.mail`)** - gửi email bất đồng bộ qua SMTP:
  - **`MailService` (Protocol)** - contract trung lập: `async def send(message:
    EmailMessage) -> None`. Logic đồng bộ (await tới khi gửi xong, thành công ->
    return, thất bại -> raise `MailSendError`, có timeout nội bộ) - dùng cho email
    bảo mật (OTP, reset mật khẩu). Gửi nền là việc của app (tự bọc
    `asyncio.create_task(...)`), starter không ôm hàng đợi.
  - **`SmtpMailService` (backend)** - hiện thực qua **`aiosmtplib`** (async, không
    chặn event loop; extra `xime[mail]`, import lười). Đọc `mail.from` và
    `mail.smtp.*` (`host` bắt buộc -> `ValueError` fail-fast; `port` mặc định 587,
    `timeout` 10s, `use_tls` true) từ `RuntimeConfig`. Mỗi `send()` mở một kết nối
    SMTP mới rồi đóng (bền hơn pool cho lượng email giao dịch/OTP). Tự chọn
    STARTTLS (587) hoặc TLS ngầm (465) theo cổng.
  - **`EmailMessage`** - value object `@dataclass(frozen=True, slots=True)`: `to`,
    `subject`, `html`, `text`, `cc`, `reply_to`, `sender` (override `mail.from`).
    Validate lúc tạo: `to` không rỗng và có ít nhất một trong `html`/`text`. Có cả
    hai -> `multipart/alternative`.
  - **Exception** `MailError` (base) + `MailSendError` (gửi thất bại: SMTP từ
    chối, timeout, mất kết nối; giữ lỗi gốc ở `__cause__`) - mẫu
    `storage._exceptions`.
  - Dùng: `dependency.scan("xime.starters.mail")` +
    `dependency.bind({ MailService: SmtpMailService })`.

### Fixed

Hardening sau kiểm toán toàn diện 0.6.2 (chi tiết: `.claude/docs/kiem-toan-0.6.md`).
Không có lỗi gãy chức năng; toàn bộ là nhất quán / hardening nhỏ. Test: 1125 passed,
4 skipped.

- **`EmailMessage.to`/`cc` thật sự bất biến**: `__post_init__` snapshot sang
  `tuple` nên mutate list gốc của caller không ảnh hưởng message frozen (trước
  đây `frozen=True` chỉ chặn gán lại, không chặn `msg.to.append(...)`).
- **Mail SMTP `username`/`password` dùng `is not None`** thay falsy-check: chuỗi
  rỗng cấu hình tường minh vẫn truyền tới server; chỉ giá trị thật sự vắng mới bỏ
  qua xác thực.
- **Version fallback đồng bộ**: `xime.__version__` fallback `0.6.1` -> `0.6.2`;
  generator SDK gRPC (`_codegen.py`) nay ủy quyền `xime.__version__` để chỉ còn
  một literal version duy nhất (trước trả lệch `"0.5.0"`).
- **Error message middleware marker sang tiếng Anh** cho nhất quán; xóa sentinel
  `_NO_DEFAULT` thừa; bỏ tạo `DynamicProxy` thừa khi interface đã có override.

## [0.6.1] - 2026-06-29

Bản vá nhỏ cho web adapter: middleware tự viết lấy được dependency từ DI container
và runtime config qua marker, nên **app không phải subclass `WebAdapter`** nữa;
thêm helper CORS hạng nhất. Bổ sung `CrudRepository` cho starter SQLAlchemy để app
hết phải tự viết base repository. Tương thích ngược hoàn toàn, không đổi API cũ.
Toàn bộ test: 1101 passed, 4 skipped.

### Added

- **`CrudRepository[T]` (starter SQLAlchemy)** - lớp repository nền generic cho
  sẵn CRUD chung như `JpaRepository`/`CrudRepository` của Spring Data:
  `find` · `find_or_fail` · `find_all` · `exists` · `count` · `save` · `save_all`
  · `delete`. App chỉ cần `class CategoryRepository(CrudRepository[Category]):
  model = Category` rồi viết thêm query đặc thù bằng `select()` - hết lặp lại
  `BaseRepository` ở mỗi dự án. `model` khai báo dạng abstract property nên chính
  `CrudRepository` là abstract (`inspect.isabstract` = True) -> DI scanner bỏ qua
  lớp nền; chỉ subclass concrete (đã set `model`) mới thành singleton, không sinh
  singleton thừa. Mọi method đọc session đang hoạt động qua `AsyncSessionFactory`
  nên phải gọi trong `async with self.transaction():`. `find_or_fail` ném
  `EntityNotFoundError` (lỗi runtime cục bộ của starter) khi không có bản ghi.
- **Middleware lấy dependency từ DI / runtime config (web adapter)** - hai marker
  `Inject(SomeType)` và `FromConfig("a.b", default)` dùng làm giá trị option khi
  gọi `configure_middleware(...)`. Framework phân giải marker lúc `build_app`
  (sau khi DI container đã dựng): `Inject` lấy singleton từ container,
  `FromConfig` đọc `RuntimeConfig` theo dot-notation (thiếu thì về default). Nhờ
  vậy middleware tự viết (vd JWT middleware cần auth/user/blacklist service) khai
  báo gọn trong `config/web.py`, **không phải subclass `WebAdapter`** để tự gọi
  `xime_app.get(...)`. Giá trị không phải marker giữ nguyên (tương thích ngược).
- **`configure_cors(...)`** - helper hạng nhất bật CORS cho web adapter theo
  pattern `configure_*`. Tham số để trống tự đọc từ `RuntimeConfig` khóa
  `cors.<tên>` (qua `FromConfig`), thiếu nốt thì về mặc định Starlette - Operator
  chỉnh CORS qua `application.yml` mà không đụng code. CORS đăng ký như user
  middleware nên nằm ngoài JwtAuth (preflight OPTIONS xử lý trước xác thực).

## [0.6.0] - 2026-06-23

Bản DI: **tự viết lớp lưu/dựng singleton** (gỡ hẳn thư viện `dependency-injector`)
và **dynamic interface binding** (một interface bind nhiều implementation, đổi
được lúc runtime). Không đổi API người dùng đang dùng; dự án cũ chạy nguyên không
phải sửa. Toàn bộ test: 1084 passed, 4 skipped.

### Added

- **Dynamic interface binding** - `bind` nay chấp nhận value là **tuple nhiều
  implementation** (phần tử đầu = mặc định) bên cạnh value một class như cũ.
  Bật/tắt bằng cờ runtime `xime.di.dynamic-binding` trong `application.yml` (mặc
  định **tắt**). Khi tắt, tuple hành xử y hệt bind phần tử đầu (impl phụ không
  dựng) - bằng đúng kiến trúc cũ. Khi bật: mọi impl là singleton eager (chạy
  `PostConstruct`/`PreDestroy`), consumer nhận một **proxy trong suốt**
  (`DynamicProxy`) nên giữ nguyên code, và một **`Switcher`** (inject được) đổi
  implementation **toàn cục** lúc runtime qua `use(Interface, Impl)` /
  `reset(Interface)` / `reset()`. Validate fail-fast: mọi impl trong tuple phải
  thỏa Protocol. `Switcher` luôn inject được; khi cờ tắt, `use/reset` báo lỗi rõ.

### Changed

- **Gỡ phụ thuộc `dependency-injector`** - lớp lưu/dựng singleton ở
  `core/container/registry.py` viết lại bằng dict thuần (key là chính class) +
  `RLock` double-checked locking. API public (`XimeContainer`,
  `DependencyRegistry.register/get`) không đổi. Lý do: Xime eager-build mọi
  singleton lúc startup rồi giữ reference qua constructor injection, không gọi
  provider mỗi request - nên ưu thế Cython của thư viện không phát huy, trong khi
  vẫn tốn phí sinh tên (md5 + regex) mỗi class và một lớp gián tiếp mỗi `get()`.
  Bản tự viết bỏ cả hai: `get()` warm là đúng một `dict.get`, lock chỉ chạm khi
  cache miss (gần như chỉ lúc startup). Benchmark đối chiếu: build ~8x, warm
  `get()` ~2x nhanh hơn backend cũ. Đã gỡ `dependency-injector` khỏi
  `pyproject.toml` - Xime không còn phụ thuộc thư viện DI bên thứ ba nào.
- Bump version `0.5.0` -> `0.6.0`.

## [0.5.0] - 2026-06-22

Bản kiểm toán toàn diện + hai mảng tính năng mới: **adapter MQTT** (messaging/IoT)
và **làm việc với file** (storage starter + streaming web). Toàn bộ test: 1051
passed, 4 skipped (2 skip là test tích hợp MQTT/S3 - chạy khi có broker/MinIO).
Chi tiết kiểm toán: `.claude/docs/kiem-toan-0.5.md`.

### Added

- **Adapter MQTT** (`pip install xime[mqtt]`, `aiomqtt` import lười): pub/sub
  một chiều (`@subscribe`) + **RPC over MQTT v5** (`@rpc`, qua `ResponseTopic` +
  `CorrelationData`). `MqttPublisher` (DI singleton) để publish; auto-reconnect +
  re-subscribe; xử lý message giới hạn đồng thời (`max_concurrency`, backpressure);
  định tuyến bằng **MQTT v5 Subscription Identifier** để filter chồng lấn không
  double-dispatch; teardown `request_context`/`clear_security()` nhất quán mọi adapter.
- **Starter `storage`** (Protocol `StorageService`): hai dạng truy cập song song
  - `put`/`get` (bytes) cho object nhỏ và `put_stream`/`open_stream` (stream) cho
  object lớn; `delete`/`exists`/`stat`/`url`. Value là bytes thô, framework không
  áp đặt định dạng. Key được chuẩn hóa chung (từ chối rỗng/tuyệt đối/`..`) cho mọi
  backend.
- **Backend `localfs`** (`LocalFileStorage`): lưu file dưới `storage.local.root`,
  chống path traversal 3 lớp, ghi nguyên tử (`.part` + `os.replace`), stream qua
  `asyncio.to_thread` (không cần `aiofiles`).
- **Backend `s3`** (`pip install xime[s3]`, `aioboto3` import lười): `S3ClientProvider`
  (vòng đời client ở `post_construct`/`pre_destroy`) + `S3FileStorage` (multipart
  upload, ranged GET, presigned `url()`); tương thích MinIO (`addressing_style`).
- **Streaming file ở web adapter** (`xime.adapters.web.files`): `stream_object`
  (HTTP Range 200/206/416, `Content-Range`, `ETag`, đọc lười không nạp hết RAM) và
  `save_upload` (đọc `UploadFile` theo chunk -> `put_stream`, giới hạn `max_bytes`
  -> 413).
- **JWT `audience`/`issuer`** (`JwtMiddlewareConfig`): ép khớp `aud`/`iss` khi cấu
  hình; middleware phơi toàn bộ claim qua `request_context[JWT_CLAIMS]` để app
  authorize tiếp.

### Fixed

- **Context bleeding ở web HTTP middleware** (dental-clinic #001): chuyển
  `RequestContextMiddleware` và `JwtAuthMiddleware` từ `BaseHTTPMiddleware` sang
  **pure-ASGI middleware** -> set/clear `ContextVar` cùng context với handler, hết
  rò identity giữa các request.
- **JWT từ chối token có claim `aud`**: trước đây `jwt.decode` không truyền
  `audience` khiến PyJWT reject mọi token mang `aud` (401). Nay đặt
  `verify_aud=False` khi chưa cấu hình audience và ép khớp khi có.
- **`MqttPublisher` treo vô hạn** khi không adapter nào phục vụ client_id: nay
  fail-fast `RuntimeError` rõ ràng.
- **HTTP Range sai cú pháp trả 416**: nay bỏ qua header rác và phục vụ full 200
  (đúng RFC 7233); chỉ 416 cho range hợp lệ-nhưng-không-thoả.
- **Scanner nuốt lỗi import thật của submodule**: nay re-raise lỗi import thật
  (thiếu dependency, circular...), chỉ bỏ qua khi module thực sự vắng.
- **`get_protocol_methods` bỏ dunder**: nay giữ dunder mang ý nghĩa contract
  (`__call__`, `__aenter__`, `__aexit__`...) để binding validation đầy đủ hơn.
- **MQTT `#`/`+` cấp đầu khớp `$SYS`**: nay không khớp topic hệ thống `$...`.
- **Socket `STREAM_START` payload hỏng làm rớt connection**: nay gửi frame ERROR.
- **`XimeGrpcChannel` task đóng channel nền có thể bị GC**: nay giữ strong-ref.
- **OpenAPI `public_paths` không chuẩn hóa trailing slash** như JWT middleware:
  nay đồng nhất.
- **MQTT RPC: lỗi gửi reply che lỗi gốc**: nay reply lỗi là best-effort, luôn
  giữ lỗi nghiệp vụ gốc trong log.

### Changed

- **`scheduler` extra**: `apscheduler>=3.6` -> `apscheduler>=4.0.0a6` cho khớp code
  dùng API v4 (`AsyncScheduler`/`run_until_stopped`/`add_schedule`); `>=3.6` cho
  phép cài 3.x stable thiếu API v4 -> `ImportError` lúc chạy.
- Thêm extra `s3`, `mqtt`; gộp vào `all`.
- Bump version `0.4.0` -> `0.5.0`.

## [0.4.0] - 2026-06-20

Bản cross-cutting + starters: thêm danh tính peer mTLS cho gRPC và hai starter
còn thiếu (`cache`, `redis`). Không đụng lõi DI. Toàn bộ test: 929 passed,
2 skipped.

### Added

- **Danh tính peer mTLS cho gRPC -> request_context**: `RequestContextInterceptor`
  nay đọc Common Name của client certificate đã verify (qua `auth_context()`) và
  lưu vào `request_context` dưới key trung tính `peer_cn`. **Fail-soft**: không
  mTLS / không có CN / lỗi đọc -> không set key, request vẫn chạy. Thêm helper
  `current_caller()` (`xime.core.security`) trả CN thô; authorization vẫn ở app.
- **Starter `cache`**: Protocol `CacheService` (`get`/`set`/`delete`/`exists`),
  value là `bytes` thô (framework không áp đặt serialize), TTL theo giây,
  `None` = không hết hạn. Tách hoàn toàn khỏi backend.
- **Starter `redis`** (`pip install xime[redis]`): `RedisClientProvider` (đọc
  `redis.url` + `redis.max_connections` từ `application.yml`, `pre_destroy` đóng
  connection pool) và `RedisCacheService` (implement `CacheService`). `redis`
  được import lười để module vẫn import được khi chưa cài extra.

### Changed

- Bump version `0.3.0` -> `0.4.0`.

## [0.3.0] - 2026-06-19

Bản hardening: vá bug đã xác nhận, tăng an toàn mặc định và khép kín mảng gRPC
client. Không thêm tính năng lớn. Toàn bộ test: 899 passed, 2 skipped.

### Added

- **Retry policy cho gRPC client (`grpc.clients.<id>.retry`)**: `GrpcRetryConfig`
  với `enabled` / `max_attempts` / `initial_backoff_ms` / `max_backoff_ms` /
  `backoff_multiplier` / `retryable_status`. Tắt mặc định; chỉ retry call UNARY
  (stream không replay được an toàn); mặc định chỉ retry `UNAVAILABLE`; backoff
  mũ có cap; mỗi lần thử có deadline riêng.
- **`tls.server_id` cho gRPC client**: chọn certificate provider theo `server_id`
  trong thiết lập multi-server (mặc định `"default"`).

### Fixed

- **gRPC client cert rotation không thread-safe** (backlog #7): thêm
  `threading.Lock` quanh đoạn check-and-replace trong
  `XimeGrpcChannel._dynamic_channel()` để hai luồng song song không cùng dựng
  channel rồi rò một cái.
- **`wire_dynamic_certificates()` hardcode `server_id="default"`** (backlog #8):
  giờ tra provider theo `server_id` của từng channel.
- **Endpoint gRPC code-first viết `def` thay vì `async def`** (backlog #9): nay
  fail fast bằng `StartupException` lúc startup (kể cả `async def` có `yield`),
  thay vì crash `TypeError` lúc RPC đầu tiên.
- **Interceptor lỗi gRPC abort hai lần** (notification/data note #2): re-raise
  `grpc.aio.AbortError` như terminal để không abort lần hai khi interceptor/
  handler bên trong đã abort.
- **Interceptor lỗi để lộ `str(exc)` ra client** (notification/data note #1a):
  lỗi chưa map nay trả message chung `"Internal server error"`; lỗi đã map vẫn
  giữ message có chủ đích.

### Changed

- Bump version `0.2.0` -> `0.3.0`.

## [0.2.0] - 2026-06-14

Bản hoàn thiện đầu tiên: core (DI / lifecycle / config / context / event bus /
security / transaction), các adapter (web, gRPC code-first + client SDK + mTLS
động, socket) và các starter (sqlalchemy, jwt, scheduler).

[0.6.1]: https://github.com/nguyen-huu-thang/xime-framework/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/nguyen-huu-thang/xime-framework/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/nguyen-huu-thang/xime-framework/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/nguyen-huu-thang/xime-framework/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/nguyen-huu-thang/xime-framework/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/nguyen-huu-thang/xime-framework/releases/tag/v0.2.0
