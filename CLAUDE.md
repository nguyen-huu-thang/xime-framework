# CLAUDE.md

File này cung cấp hướng dẫn cho Claude Code khi làm việc với dự án này.

> **Chạy service Base / đổi cấu hình service đang chạy (áp dụng cho MỌI phiên):**
> `D:\code\xime\tools\chay-base\chay-base.bat` khởi động cả 9 service Base theo đúng thứ tự phụ thuộc ·
> `trang-thai.bat` xem đang chạy gì · `dung-base.bat` dừng.
> **Đọc `D:\temp\xime\service base\trang-thai.md` TRƯỚC khi tự khởi động bất cứ service nào** -
> đó là nơi mọi phiên biết cái gì đang chạy, khỏi tranh cổng nhau.
> Cập nhật danh bạ app, cert, key, quyền, callback thì **gọi kênh admin, ĐỪNG khởi động lại**:
> [`../.claude/docs/khoi-dong-va-kenh-admin.md`](../.claude/docs/khoi-dong-va-kenh-admin.md)
> (có bảng "API hay khởi động lại" - thứ trong database thì có API, thứ trong `application.yml` thì không).

## Tổng quan dự án

**XIME** là một Python backend framework mang lại trải nghiệm phát triển tương tự Spring Boot nhưng vẫn tôn trọng triết lý Python. Đã **phát hành 0.7.0** - toàn bộ core, các adapter (web, gRPC, socket, MQTT, **Modbus TCP**, **OPC UA**) và starters (gồm storage local + S3/MinIO, mail SMTP) đã được triển khai đầy đủ và có test. Bản 0.6 **gỡ hẳn thư viện `dependency-injector`** (lớp lưu/dựng singleton viết lại bằng dict tự viết) và thêm **dynamic interface binding** (một interface bind nhiều implementation, đổi được lúc runtime qua `Switcher`). Bản 0.6.1 thêm cho web adapter: middleware lấy được dependency từ DI / runtime config qua marker `Inject`/`FromConfig` và helper `configure_cors` (app không phải subclass `WebAdapter`). Bản 0.6.2 thêm **starter `mail`**: Protocol `MailService` + backend SMTP `SmtpMailService` (async qua aiosmtplib, gửi đồng bộ có timeout + `MailSendError`). Bản 0.6.3 gỡ chặn cho app chạy thật: **`PEER_APP_ID`** (đọc định danh APPLICATION từ SAN `xime-app://` của client cert mTLS, lưu cạnh `PEER_CN` trong request context, phơi qua `current_app_id()`), **TLS/HTTPS cho web adapter** (khối `server.ssl` trong `application.yml`, để trống thì vẫn HTTP thuần như cũ) và **khối chỉ đọc `read_only()`** (usecase không ghi khỏi phải bọc transaction; `ReadOnlyManager` là manager riêng cùng cấp với `TransactionManager`), kèm `RuntimeConfig.get_bool()` ép kiểu chặt cho cờ boolean. Bản **0.7.0** thêm **fieldbus công nghiệp**: adapter **Modbus TCP** (Device Model khai báo tự giải mã thanh ghi, lập kế hoạch đọc an toàn theo `max_gap`, `@poll`/`@on_change`, và chế độ slave `@serve`/`@on_write`) và adapter **OPC UA** (Node Model, subscription thật `@on_node_change`, chế độ server, đủ ba mức bảo mật None/Sign/SignAndEncrypt).

XIME không thay thế FastAPI, SQLAlchemy hay gRPC. Nó cung cấp một tầng kiến trúc phía trên các thư viện này để tự động hóa dependency injection, chuẩn hóa cấu trúc dự án và quản lý vòng đời component.

---

## Kiến trúc

```text
Application Code
        ↓
      Xime Core
        ↓
  DI Container (core/container)
        ↓
Python Objects
```

**Core** (`core/`) — Nền tảng framework, không phụ thuộc vào adapter:

- `bootstrap/` — Điểm khởi động ứng dụng và điều phối startup
- `container/` — DI tự viết hoàn toàn: quét package, phân giải type hint, xây dựng và kiểm tra dependency graph, và lớp lưu trữ/khởi tạo singleton (dict dùng class làm key + `RLock`, từ 0.6 không còn dùng `dependency-injector`)
- `config/` — Hệ thống cấu hình hai tầng: Framework config viết bằng Python, Runtime config viết bằng YAML. Env var **chỉ chọn file profile** (`XIME_ENV`/`APP_ENV` -> `application-{env}.yml`); không có nội suy `${VAR}` và không có override từng key qua env var
- `context/` — Dữ liệu theo phạm vi request thông qua `ContextVar`
- `contract/` — Định nghĩa endpoint contract dùng chung cho Socket và gRPC code-first
- `lifecycle/` — Hook khởi động/tắt (`PostConstruct`, `PreDestroy`)
- `event/` — Event bus nội bộ (fire and forget, async background tasks)
- `security/` — `SecurityContext`, `AuthenticationManager`, `AuthorizationManager`
- `transaction/` — `TransactionManager`, `TransactionContext`, và `ReadOnlyManager`/`ReadOnlyContext` cho khối chỉ đọc
- `metadata/` — Tiện ích type metadata và reflection
- `exception/` — Hệ thống phân cấp exception của framework

**Adapters** (`adapters/`) — Tích hợp giao thức, mỗi adapter thiết lập request `Context`:

- `web/` — HTTP server (FastAPI), routing decorators (`@get`, `@post`, `@ws`), middleware (pure-ASGI), OpenAPI/Swagger, WebSocket, streaming file (`files/`: Range download, chunked upload), TLS/HTTPS qua khối `server.ssl`
- `grpc/` — gRPC server thông qua `grpc.aio`, code-first proto generation, client SDK, TLS/mTLS động, interceptors
- `socket/` — Unix domain socket RPC, frame protocol, peer authentication (Linux SO_PEERCRED)
- `mqtt/` — MQTT pub/sub (`@subscribe`) + RPC over MQTT v5 (`@rpc`), `MqttPublisher`, auto-reconnect (extra `xime[mqtt]`, aiomqtt)
- `modbus/` — Modbus TCP master + slave: Device Model khai báo (`@device` + `Holding/Input/Coil/Discrete`) tự giải mã thanh ghi, lập kế hoạch đọc theo `max_gap`, `@poll`/`@on_change`, `@serve`/`@on_write` (extra `xime[modbus]`, pymodbus)
- `opcua/` — OPC UA client + server: Node Model (`@node_model` + `Node`), subscription thật (`@on_node_change`), đủ ba mức bảo mật (extra `xime[opcua]`, asyncua)

**Starters** (`starters/`) — Module quickstart tùy chọn, tương tự `spring-boot-starter-*`:

- `sqlalchemy/` — Async DB session, `SqlAlchemyTransactionManager`
- `jwt/` — Xác thực JWT (HS/RSA/EC/EdDSA), middleware tự động, ép `audience`/`issuer`
- `scheduler/` — Lập lịch tác vụ (APScheduler v4), cron và interval jobs
- `cache/` + `redis/` — Protocol `CacheService` và backend Redis
- `storage/` + `localfs/` + `s3/` — Protocol `StorageService` và backend filesystem / S3-MinIO (extra `xime[s3]`, aioboto3)
- `mail/` — Protocol `MailService` + backend SMTP `SmtpMailService` (async, HTML + text; extra `xime[mail]`, aiosmtplib)

**Testing** (`testing/`) — Tiện ích test và DI overrides.

**CLI** (`cli/`) — Công cụ cho developer.

---

## Trình tự Khởi động

1. Nạp Framework Configuration
2. Nạp Runtime Configuration
3. Quét Package
4. Phân giải Type Hint
5. Xây dựng Dependency Graph
6. Kiểm tra Graph (cycles, missing implementations, missing type hints)
7. Tạo Singleton
8. Khởi động Adapter

---

## Thư viện nền tảng

XIME xây dựng trên (không viết lại):

- **FastAPI** — HTTP, routing, OpenAPI, middleware, lifespan
- **Pydantic** — Validation, serialization, định nghĩa DTO/command, config binding
- **SQLAlchemy** (qua starter) — `AsyncSession`, ORM
- **grpc.aio** (qua adapter) — gRPC server
- **PyJWT** (qua starter) — JWT signing và verification
- **APScheduler** (qua starter) — Task scheduling

> **Về DI container:** Toàn bộ DI được **tự viết** trong `core/container/` — cả *logic* (quét package, phân giải type hint, dựng/kiểm tra dependency graph, topological sort, phát hiện circular dependency) lẫn *lớp lưu trữ/khởi tạo singleton* (`core/container/registry.py`: một dict dùng chính class làm key + `RLock` double-checked locking). Từ bản 0.6, framework **không còn phụ thuộc** thư viện DI bên thứ ba nào (trước đây `core/container/registry.py` dùng `dependency-injector` làm backend singleton; nay đã thay bằng dict tự viết, API người dùng không đổi).

---

## Tài liệu chi tiết

Các tài liệu dưới đây nằm trong thư mục `.claude/` — đọc khi cần thông tin cụ thể hơn:

**Nguyên tắc & Quy tắc code** → `.claude/rules/coding.md`

- Quy tắc DI (không annotation, constructor injection)
- Điều kiện đăng ký class, quét package
- Interface binding, dependency scope
- Fail fast và báo lỗi startup

**Thiết kế Transaction** → `.claude/rules/transaction.md`

- Lý do không dùng `@transactional`
- Cách dùng `async with self.transaction()`
- Triển khai `TransactionManager`, `TransactionContext`
- Tích hợp với SQLAlchemy

**Thiết kế tổng thể** → `.claude/docs/tai-lieu-thiet-ke.md`

- Toàn bộ thiết kế từ nguyên tắc đến lifecycle, starters
- Ví dụ cấu hình, error reporting chi tiết

**Giới thiệu & triết lý** → `.claude/docs/gioi-thieu-framework.md`

- Vai trò của Xime so với Dependency Injector
- Triết lý DI và mục tiêu cuối cùng

**Cây thư mục** → `.claude/docs/cay-thu-muc.md`

**Thông tin cập nhật**

- bạn hãy tìm kiếm và đọc các file nội dung hướng dẫn trong `.claude/docs` và `.claude/rules` để tìm kiếm thông tin hướng dẫn đầy đủ nhất.

- Cấu trúc thư mục đầy đủ với giải thích từng folder
