# CLAUDE.md

File này cung cấp hướng dẫn cho Claude Code khi làm việc với dự án này.

## Tổng quan dự án

**XIME** là một Python backend framework mang lại trải nghiệm phát triển tương tự Spring Boot nhưng vẫn tôn trọng triết lý Python. Dự án hiện đang trong **giai đoạn thiết kế/lên kế hoạch** — cấu trúc thư mục đã có nhưng các file triển khai chưa được viết.

XIME không thay thế FastAPI, SQLAlchemy hay gRPC. Nó cung cấp một tầng kiến trúc phía trên các thư viện này để tự động hóa dependency injection, chuẩn hóa cấu trúc dự án và quản lý vòng đời component.

---

## Kiến trúc

```text
Application Code
        ↓
      Xime Core
        ↓
Dependency Injector (python-dependency-injector)
        ↓
Python Objects
```

**Core** (`core/`) — Nền tảng framework, không phụ thuộc vào adapter:

- `container/` — Quét package, phân giải type hint, xây dựng và kiểm tra dependency graph
- `context/` — Dữ liệu theo phạm vi request thông qua `ContextVar`
- `lifecycle/` — Hook khởi động/tắt (`PostConstruct`, `PreDestroy`)
- `event/` — Event bus nội bộ
- `security/` — `SecurityContext`, `AuthenticationManager`, `AuthorizationManager`
- `config/` — Hệ thống cấu hình hai tầng
- `bootstrap/` — Điểm khởi động ứng dụng và điều phối startup
- `metadata/` — Tiện ích type metadata
- `exception/` — Hệ thống phân cấp exception của framework

**Adapters** (`adapters/`) — Tích hợp giao thức, mỗi adapter thiết lập request `Context`:

- `fastapi/` — HTTP server, routing, middleware, OpenAPI
- `grpc/` — gRPC server thông qua `grpc.aio`
- `mq/` — Tích hợp message queue
- `websocket/` — Hỗ trợ WebSocket

**Starters** (`starters/`) — Module quickstart tùy chọn, tương tự `spring-boot-starter-*`:

- `sqlalchemy/` — Async DB session, `SqlAlchemyTransactionManager`
- `redis/` — Redis client
- `jwt/` — Xác thực JWT
- `cache/` — Abstraction caching
- `scheduler/` — Lập lịch tác vụ

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
- **python-dependency-injector** — `Singleton`, `Factory`, `Resource` providers lúc runtime
- **Pydantic** — Validation, serialization, định nghĩa DTO/command, config binding
- **SQLAlchemy** (qua starter) — `AsyncSession`, ORM
- **grpc.aio** (qua adapter) — gRPC server

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
