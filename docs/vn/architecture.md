# Kiến trúc

[English](../en/architecture.md) | **Tiếng Việt**

[← Testing](testing.md) · **8/9 - Kiến trúc** · [Đóng góp →](contributing.md)

---

## Tổng quan tầng

```text
Application Code   ← nghiệp vụ, controller, use case của bạn
      ↓
   XIME Core       ← scanning, DI, lifecycle, config, event, security
      ↓
  DI Container     ← core/container, tích hợp sẵn
      ↓
Python Objects
```

XIME nằm giữa code ứng dụng và DI container. Nó tự động hóa scanning, xây dựng graph và kết nối dependency để bạn không bao giờ phải tự dây singleton hay truyền dependency thủ công. Container là một **registry singleton tự viết** (một dict dùng chính class làm key), nên XIME không phụ thuộc thư viện DI bên thứ ba nào.

---

## Core Modules

```text
core/
├── bootstrap/    ← Entry point ứng dụng, điều phối startup
├── container/    ← Package scanning, type resolution, dependency graph, singleton registry, dynamic binding
├── metadata/     ← Tiện ích xử lý type hint
├── config/       ← Hệ thống config hai tầng
├── lifecycle/    ← PostConstruct / PreDestroy hook
├── context/      ← Dữ liệu theo request qua ContextVar
├── contract/     ← Endpoint contract dùng chung cho Socket và gRPC code-first
├── security/     ← SecurityContext, AuthenticationManager, AuthorizationManager
├── event/        ← Internal event bus (fire and forget, background task)
├── transaction/  ← TransactionManager + ReadOnlyManager (khối chỉ đọc), context tương ứng
└── exception/    ← Hệ thống exception của framework
```

**Core không phụ thuộc vào FastAPI, gRPC hay bất kỳ thư viện giao thức nào.** Nó hoạt động ở tầng Python object thuần.

---

## Adapters

Adapter dịch giữa giao thức và XIME Core. Mỗi adapter:

1. Nhận tin nhắn đến (HTTP request, gRPC call, MQ message)
2. Thiết lập request `Context` (user, trace ID, v.v.)
3. Gọi handler tương ứng (controller, service handler)
4. Dọn dẹp context sau khi xử lý xong

```text
adapters/
├── web/           ← HTTP + WebSocket qua FastAPI (ASGI)
│   ├── openapi/   ← Cấu hình OpenAPI, security scheme
│   ├── routing/   ← Đăng ký class-based controller
│   ├── middleware/ ← Context middleware
│   └── ws/        ← WebSocket support
├── grpc/          ← gRPC server qua grpc.aio, code-first proto generation, TLS/mTLS
└── socket/        ← IPC qua Unix Domain Socket, frame protocol, peer auth (Linux)
```

---

## Starters

Module tích hợp tùy chọn, tương tự `spring-boot-starter-*` trong Spring Boot.

```text
starters/
├── sqlalchemy/   ← AsyncSession, transaction + read-only, CrudRepository  ✅ đã implement
├── jwt/          ← JWT sign/verify (PyJWT), middleware        ✅ đã implement
├── scheduler/    ← Cron-style task runner (APScheduler)      ✅ đã implement
├── redis/        ← Redis client                              🔲 đang kế hoạch
└── cache/        ← Cache abstraction                         🔲 đang kế hoạch
```

Starter phụ thuộc vào Core nhưng không bắt buộc. Chúng đăng ký component vào DI container giống như bất kỳ class nào khác.

---

## Trình tự Startup

```text
Application.start()
  │
  ├─ 1. Load BindingConfig     (từ config/dependency.py)
  ├─ 2. Load RuntimeConfig     (từ resources/application.yml)
  ├─ 3. Quét package           (PackageScanner)
  ├─ 4. Phân giải type hint    (TypeResolver)
  ├─ 5. Xây dựng dependency graph (GraphBuilder)
  ├─ 6. Validate graph         (GraphValidator)
  │       ├─ phát hiện circular dependency
  │       ├─ tìm binding thiếu
  │       └─ validate Protocol implementation
  ├─ 7. Tạo singleton          (core/container)
  └─ 8. Khởi động adapter      (WebAdapter, GrpcAdapter, ...)
```

Bước 6 là điểm khác biệt chính - validation xảy ra **trước** khi tạo bất kỳ singleton nào. Ứng dụng cấu hình sai không bao giờ khởi động thầm lặng.

---

## Dependency Graph

Graph là directed acyclic graph (DAG) của các dependency constructor.

```text
UserController → GetUserUseCase → UserRepository (Protocol)
                                        ↓ (binding)
                               JpaUserRepository
```

XIME xây dựng graph bằng cách:

1. Inspect signature `__init__` của mỗi class được scan
2. Đọc type hint của mỗi tham số
3. Giải quyết Protocol → concrete class qua binding registry
4. Kiểm tra vòng lặp

---

## Hệ thống Config

XIME dùng mô hình config hai tầng:

| Tầng | Người viết | Định dạng | Mục đích |
| --- | --- | --- | --- |
| Framework config | Developer | Python | DI scan, binding, routing, security |
| Runtime config | Operator | YAML | host, port, DB URL, secret |

Framework config được import lúc startup. Runtime config được nạp từ `resources/application.yml` và merge với `resources/application-{env}.yml`. Env được đọc từ `XIME_ENV` hoặc `APP_ENV`.

---

## Request Context

Mỗi adapter thiết lập context dựa trên `ContextVar` lúc bắt đầu request:

```python
# Trong middleware / request handler
current_user.set(authenticated_user)
request_id.set(generate_id())
```

Business logic đọc context một cách thụ động:

```python
user = current_user.get()
```

Context được tự động cô lập theo từng request vì `ContextVar` an toàn với async - mỗi asyncio task có bản sao riêng.

---

## Mô hình Security

Security được chia giữa Core và adapter:

- **Core** - `SecurityContext`, `AuthenticationManager`, `AuthorizationManager`, `SecuritySession`
- **Adapter** - HTTP middleware thực hiện xác thực và điền vào `SecurityContext`

Business logic gọi `AuthorizationManager` để kiểm tra quyền. Nó không bao giờ đụng vào HTTP header hay token trực tiếp.

---

## Mô hình Transaction

Transaction là **tường minh** - context manager, không phải AOP proxy ẩn:

```python
async with self.transaction():
    await self.repository.save(entity)
```

`TransactionManager` là interface của Core. `SqlAlchemyTransactionManager` (trong SQLAlchemy starter) là implementation cụ thể. Business code chỉ phụ thuộc vào interface.

Usecase **chỉ đọc** dùng `ReadOnlyManager` - một interface riêng, cùng cấp, không phải method của `TransactionManager`:

```python
async with self.read_only():
    return await self.repository.find_all()
```

Khối chỉ đọc không bao giờ commit. Tách thành interface riêng để về sau trỏ đường đọc sang read replica chỉ bằng một dòng `bind`. Chi tiết: [Transaction](transaction.md).

---

## Testing

Module `testing/` cung cấp:

- `FakeTransactionManager` / `FakeReadOnlyManager` - transaction và khối chỉ đọc in-memory cho unit test
- DI override helper - thay thế singleton bằng test double mà không đụng vào production config

```python
dependency.bind({UserRepository: FakeUserRepository})
```

---

## XIME KHÔNG làm gì

- Không implement HTTP routing logic (FastAPI làm)
- Không implement SQL query (SQLAlchemy làm)
- Không implement JWT cryptography (PyJWT làm)
- Không tạo ORM, HTTP server hay gRPC runtime mới

XIME điều phối các công cụ này. Nó không thay thế chúng.

---

[← Testing](testing.md) · **8/9 - Kiến trúc** · [Đóng góp →](contributing.md)
