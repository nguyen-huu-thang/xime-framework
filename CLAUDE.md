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

**XIME** là một Python backend framework mang lại trải nghiệm phát triển tương tự Spring Boot nhưng vẫn tôn trọng triết lý Python. Toàn bộ core, sáu adapter (web, gRPC, socket, MQTT, **Modbus TCP**, **OPC UA**) và các starter đều đã triển khai đầy đủ và có test - framework **không còn ở giai đoạn thiết kế**.

Ba trụ của nó: **DI tự viết hoàn toàn** (quét package, phân giải type hint, dựng và kiểm tra dependency graph, fail fast lúc khởi động) · **transaction tường minh** bằng context manager thay vì `@transactional` · và **đa tiến trình** với kho, bus, cấu hình cùng hình dạng cho một hay nhiều tiến trình.

> ⚠ **File này cố ý KHÔNG ghi số hiệu bản.** Câu *"đã phát hành 0.x"* là dòng lỗi thời mỗi lần phát hành, và nó đã sai suốt ba bản liền. Tra bản hiện tại ở [`.claude/docs/lo-trinh-phien-ban.md`](.claude/docs/lo-trinh-phien-ban.md), hoặc hỏi thẳng PyPI:
>
> ```bash
> python -c "import urllib.request,json; print(sorted(json.load(urllib.request.urlopen('https://pypi.org/pypi/xime/json'))['releases']))"
> ```

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

**Core** (`core/`) - Nền tảng framework, không phụ thuộc vào adapter:

- `bootstrap/` - Điểm khởi động, điều phối startup, và **đa tiến trình**: `share_load()`, supervisor giữ socket, thăng cấp primary, watchdog
- `container/` - DI tự viết hoàn toàn: quét package, phân giải type hint, xây dựng và kiểm tra dependency graph, và lớp lưu trữ/khởi tạo singleton (dict dùng class làm key + `RLock`, từ 0.6 không còn dùng `dependency-injector`)
- `config/` - Hệ thống cấu hình hai tầng: Framework config viết bằng Python, Runtime config viết bằng YAML. Env var **chỉ chọn file profile** (`XIME_ENV`/`APP_ENV` -> `application-{env}.yml`); không có nội suy `${VAR}` và không có override từng key qua env var
- `context/` - Dữ liệu theo phạm vi request thông qua `ContextVar`
- `contract/` - Định nghĩa endpoint contract dùng chung cho Socket và gRPC code-first
- `lifecycle/` - Hook khởi động/tắt: `PostConstruct` (mọi tiến trình), `PreDestroy`, và **`RunOnce`** (một lần cho cả cụm)
- `event/` - Event bus **trong một tiến trình** (fire and forget, có trần task cấu hình qua `configure_event_bus`)
- `link/` - **`ProcessLink`**, bus **liên tiến trình**: bộ nhớ chung, mỗi tiến trình một vùng ghi riêng, cha không nằm trên đường đi. ⚠ Khác hẳn `event/`
- `refdata/` - **`RefData`**, kho tham chiếu liên tiến trình cho dữ liệu **có nguồn bền vững** (khoá JWT, danh bạ app): hai bản đổi con trỏ, chỉ primary ghi
- `security/` - `SecurityContext`, `AuthenticationManager`, `AuthorizationManager`
- `transaction/` - `TransactionManager`, `TransactionContext`, và `ReadOnlyManager`/`ReadOnlyContext` cho khối chỉ đọc
- `metadata/` - Tiện ích type metadata và reflection
- `exception/` - Hệ thống phân cấp exception của framework

**Adapters** (`adapters/`) - Tích hợp giao thức, mỗi adapter thiết lập request `Context`:

- `web/` - HTTP server (FastAPI), routing decorators (`@get`, `@post`, `@ws`), middleware (pure-ASGI), OpenAPI/Swagger, WebSocket, streaming file (`files/`: Range download, chunked upload), TLS/HTTPS qua khối `server.ssl`
- `grpc/` - gRPC server thông qua `grpc.aio`, code-first proto generation, client SDK, TLS/mTLS động, interceptors
- `socket/` - Unix domain socket RPC, frame protocol, peer authentication (Linux SO_PEERCRED)
- `mqtt/` - MQTT pub/sub (`@subscribe`) + RPC over MQTT v5 (`@rpc`), `MqttPublisher`, auto-reconnect (extra `xime[mqtt]`, aiomqtt)
- `modbus/` - Modbus TCP master + slave: Device Model khai báo (`@device` + `Holding/Input/Coil/Discrete`) tự giải mã thanh ghi, lập kế hoạch đọc theo `max_gap`, `@poll`/`@on_change`, `@serve`/`@on_write` (extra `xime[modbus]`, pymodbus)
- `opcua/` - OPC UA client + server: Node Model (`@node_model` + `Node`), subscription thật (`@on_node_change`), đủ ba mức bảo mật (extra `xime[opcua]`, asyncua)

**Starters** (`starters/`) - Module quickstart tùy chọn, tương tự `spring-boot-starter-*`:

- `sqlalchemy/` - Async DB session, `SqlAlchemyTransactionManager`
- `jwt/` - Xác thực JWT (HS/RSA/EC/EdDSA), middleware tự động, ép `audience`/`issuer`
- `scheduler/` - Lập lịch tác vụ (APScheduler v4), cron và interval jobs
- `cache/` + `redis/` - Protocol `CacheService` và backend Redis
- `storage/` + `localfs/` + `s3/` - Protocol `StorageService` và backend filesystem / S3-MinIO (extra `xime[s3]`, aioboto3)
- `mail/` - Protocol `MailService` + backend SMTP `SmtpMailService` (async, HTML + text; extra `xime[mail]`, aiosmtplib)
- `lmdb/` - **`Store` / `CounterStore`** trên LMDB cho dữ liệu **không có nguồn bền vững** (hãm nhịp, thử thách passkey, chống lặp). Phạm vi **một máy**; nhiều máy thì dùng `CacheService` (extra `xime[lmdb]`)

**Testing** (`testing/`) - Tiện ích test và DI overrides.

**CLI** (`cli/`) - `xime init` dựng dự án · `xime config --print` in bản mô tả cấu hình · `xime check config` · `xime check module-level` · `xime grpc generate/check/client`.

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

- **FastAPI** - HTTP, routing, OpenAPI, middleware, lifespan
- **Pydantic** - Validation, serialization, định nghĩa DTO/command, config binding
- **SQLAlchemy** (qua starter) - `AsyncSession`, ORM
- **grpc.aio** (qua adapter) - gRPC server
- **PyJWT** (qua starter) - JWT signing và verification
- **APScheduler** (qua starter) - Task scheduling

> **Về DI container:** Toàn bộ DI được **tự viết** trong `core/container/` - cả *logic* (quét package, phân giải type hint, dựng/kiểm tra dependency graph, topological sort, phát hiện circular dependency) lẫn *lớp lưu trữ/khởi tạo singleton* (`core/container/registry.py`: một dict dùng chính class làm key + `RLock` double-checked locking). Từ bản 0.6, framework **không còn phụ thuộc** thư viện DI bên thứ ba nào (trước đây `core/container/registry.py` dùng `dependency-injector` làm backend singleton; nay đã thay bằng dict tự viết, API người dùng không đổi).

---

## Tài liệu chi tiết

Các tài liệu dưới đây nằm trong thư mục `.claude/` - đọc khi cần thông tin cụ thể hơn:

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

**Thiết kế tổng thể** → `.claude/docs/thiet-ke/01-tong-quan.md`

- Toàn bộ thiết kế từ nguyên tắc đến lifecycle, starters
- Ví dụ cấu hình, error reporting chi tiết

**Giới thiệu & triết lý** → `.claude/docs/thiet-ke/00-gioi-thieu.md`

- Vai trò của Xime so với Dependency Injector
- Triết lý DI và mục tiêu cuối cùng

**Cây thư mục** → `.claude/docs/thiet-ke/02-cay-thu-muc.md`

**Bản đồ toàn bộ tài liệu nội bộ** → [`.claude/docs/README.md`](.claude/docs/README.md)

Bảy loại tài liệu, luật đặt tên, và một dòng cho mỗi file. Đọc file đó thay vì tự quét thư mục - `.claude/docs/` có bảy thư mục con và không phải thư mục nào cũng mô tả hiện trạng (`da-phu-dinh/` là thứ đã bị lật, `nhap/` là giấy nháp việc đã xong).
