# CLAUDE.md

File này cung cấp hướng dẫn cho Claude Code khi làm việc với dự án này.

## Tổng quan dự án

**XIME** là một Python backend framework mang lại trải nghiệm phát triển tương tự Spring Boot nhưng vẫn tôn trọng triết lý Python. Framework đã **hoàn thiện ~95%** — toàn bộ core, các adapter chính và starters đã được triển khai đầy đủ.

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
- `container/` — Logic DI tự viết: quét package, phân giải type hint, xây dựng và kiểm tra dependency graph (lớp lưu trữ/khởi tạo singleton bên dưới dùng `dependency-injector`)
- `config/` — Hệ thống cấu hình hai tầng (YAML + env vars)
- `context/` — Dữ liệu theo phạm vi request thông qua `ContextVar`
- `contract/` — Định nghĩa endpoint contract dùng chung cho Socket và gRPC code-first
- `lifecycle/` — Hook khởi động/tắt (`PostConstruct`, `PreDestroy`)
- `event/` — Event bus nội bộ (fire and forget, async background tasks)
- `security/` — `SecurityContext`, `AuthenticationManager`, `AuthorizationManager`
- `transaction/` — `TransactionManager`, `TransactionContext`
- `metadata/` — Tiện ích type metadata và reflection
- `exception/` — Hệ thống phân cấp exception của framework

**Adapters** (`adapters/`) — Tích hợp giao thức, mỗi adapter thiết lập request `Context`:

- `web/` — HTTP server (FastAPI), routing decorators (`@get`, `@post`, `@ws`), middleware, OpenAPI/Swagger, WebSocket
- `grpc/` — gRPC server thông qua `grpc.aio`, code-first proto generation, TLS/mTLS, interceptors
- `socket/` — Unix domain socket RPC, frame protocol, peer authentication (Linux SO_PEERCRED)

**Starters** (`starters/`) — Module quickstart tùy chọn, tương tự `spring-boot-starter-*`:

- `sqlalchemy/` — Async DB session, `TransactionProvider`, `@transactional`
- `jwt/` — Xác thực JWT (RSA / HS256), middleware tự động
- `scheduler/` — Lập lịch tác vụ (APScheduler), cron và interval jobs

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
- **dependency-injector** — chỉ làm lớp lưu trữ provider bên dưới (xem ghi chú phía dưới)

> **Về DI container:** Toàn bộ *logic* DI (quét package, phân giải type hint, dựng/kiểm tra dependency graph, topological sort, phát hiện circular dependency) được **tự viết** trong `core/container/`. Framework chỉ dùng thư viện `dependency-injector` ở một điểm duy nhất — `core/container/registry.py` — làm lớp lưu trữ/khởi tạo singleton bên dưới (`DynamicContainer` + `providers.Singleton`/`providers.Object`). Các tính năng đặc trưng của thư viện (wiring `@inject`/`Provide`, `Configuration`/`Resource`/`Factory` provider, declarative container) **không** được sử dụng, và lớp backend này có thể thay bằng một dict singleton tự viết mà không ảnh hưởng kiến trúc.

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
