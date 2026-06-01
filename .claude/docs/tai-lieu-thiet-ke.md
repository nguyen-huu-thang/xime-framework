# Tài liệu thiết kế — Xime Framework

## 1. Giới thiệu

Xime là một framework backend Python được xây dựng nhằm đơn giản hóa việc phát triển các hệ thống theo Clean Architecture, DDD, Modular Monolith và Microservice.

Xime không cố gắng thay thế FastAPI, gRPC hay SQLAlchemy. Thay vào đó, Xime cung cấp một tầng kiến trúc phía trên các thư viện này để giảm boilerplate, chuẩn hóa cấu trúc dự án và tự động hóa việc quản lý dependency.

---

## 2. Triết lý thiết kế

Framework phải đảm bảo:

- Convention Over Configuration
- Constructor Injection
- Type Hint Driven
- Directory Driven
- Fail Fast
- Minimal Boilerplate
- Explicit Architecture

Developer tập trung viết nghiệp vụ, framework tự xây dựng phần còn lại.

---

## 3. Nguyên tắc cốt lõi

### Không sử dụng Annotation

Không sử dụng `@service`, `@repository`, `@component`, `@inject` (cả Java lẫn Python style). Lý do: annotation làm code khó đọc, metadata bị phân tán, Python có Type Hint đủ mạnh để suy luận dependency.

### Constructor Injection

```python
class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository
```

Framework tự phân giải: `UserService → UserRepository`.

### Type Hint Driven

Type Hint là nguồn thông tin chính để xây dựng Dependency Graph.

### Directory Driven

```text
application/service    → Service layer
application/usecase    → Use case layer
infrastructure/repository → Repository layer
infrastructure/client  → External client
```

---

## 4. Kiến trúc tổng thể

Hiện tại:

```text
Xime Core
    ↑
 ┌──┴──┐
 │     │
HTTP  gRPC
```

Tương lai:

```text
Xime Core
    ↑
 ┌──┼────┬────────┐
 │  │    │        │
HTTP gRPC MQ  WebSocket
```

**Nguyên tắc:** Core không phụ thuộc vào FastAPI, grpc.aio, RabbitMQ hay Kafka. Core chỉ chứa: Dependency Injection, Lifecycle, Event Bus, Security, Configuration, Context.

---

## 5. Thành phần của Core

### Context

```python
current_user = ContextVar("current_user", default=None)
```

Adapter thiết lập context. Business chỉ đọc: `user = current_user.get()`.

### Security

Core chứa `SecurityContext`, `AuthenticationManager`, `AuthorizationManager`. HTTP Middleware thuộc về adapter.

### Validation

Dùng trực tiếp Pydantic:

```python
class LoginCommand(BaseModel):
    username: str
    password: str
```

### Event Bus

Quản lý: Event, EventHandler, Publish, Subscribe.

### Lifecycle

Quản lý: Startup, Shutdown, PostConstruct, PreDestroy.

---

## 6. Hai tầng cấu hình

### Framework Configuration (Developer)

```text
config/
├── dependency.py
├── routing.py
├── security.py
└── module.py
```

```python
dependency.scan("application.service", "application.usecase")
dependency.exclude("domain", "dto")
```

### Runtime Configuration (Operator)

```text
resources/
├── application.yml
├── application-dev.yml
├── application-prod.yml
└── application-test.yml
```

```yaml
server:
  port: 8080
database:
  host: localhost
redis:
  host: localhost
```

---

## 7. Package Scanning

```python
dependency.scan(
    "application.service",
    "application.usecase",
    "infrastructure.repository",
    "infrastructure.client"
)
```

Package bị loại trừ: `domain`, `dto`, `entity`, `vo`, `constant`, `exception`.

Quy tắc `__init__.py`:

- Không có `__all__` → scan toàn bộ
- Có `__all__` → chỉ scan class được export

---

## 8. Điều kiện đăng ký Dependency

Hợp lệ:

```python
class UserService:
    def __init__(self, repository: UserRepository):
        ...
```

Không hợp lệ (thiếu type hint → startup fail):

```python
class UserService:
    def __init__(self, repository):  # ← thiếu type hint
        ...
```

---

## 9. Dependency Graph

```text
UserController → UserService → UserRepository
```

Dùng để: Resolve Dependency, Detect Cycle, Validate Startup.

---

## 10. Interface Binding

Interface dùng `Protocol` (không phải `ABC`). Implementation là class thường, không bắt buộc kế thừa:

```python
class UserRepository(Protocol):
    async def save_user(self) -> None: ...

class JpaUserRepository:
    async def save_user(self) -> None: ...
```

Binding tường minh trong cấu hình:

```python
dependency.bind({
    UserRepository: JpaUserRepository,
})
```

Nhiều implementation không có binding → startup fail.
Startup cũng fail nếu implementation thiếu method của Protocol.

> Chi tiết: `rules/interface-binding.md`

---

## 11. Scope

- `Singleton` — mặc định
- `Factory` — instance mới mỗi lần gọi
- Tương lai: `Request`, `Session`

---

## 12. Circular Dependency Detection

```text
Circular dependency detected:
  UserService → AuthService → TokenService → UserService
```

Startup fail ngay với thông báo rõ ràng.

---

## 13. Lifecycle

**Startup:**

1. Load Framework Configuration
2. Load Runtime Configuration
3. Scan Packages
4. Resolve Type Hints
5. Build Dependency Graph
6. Validate Graph & Detect Cycles
7. Create Singletons
8. Start Adapters

**Shutdown:**

1. Execute PreDestroy
2. Dispose Resources
3. Close Database / Redis / gRPC Channels

---

## 14. Starters

Tùy chọn, không bắt buộc:

- SQLAlchemy Starter
- Redis Starter
- JWT Starter
- Cache Starter
- Scheduler Starter

Tương tự `spring-boot-starter-*` trong Spring Boot.

---

## 15. Mục tiêu cuối cùng

Xime không thay thế FastAPI, grpc.aio, SQLAlchemy, Pydantic.

Xime cung cấp: Convention Engine, Dependency Injection Automation, Dependency Graph Validation, Lifecycle Management, Configuration System, Adapter Integration.

Developer chỉ cần tập trung vào nghiệp vụ. Framework tự động xây dựng phần còn lại.
