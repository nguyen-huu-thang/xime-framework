# XIME Framework

[English](README.md) | **Tiếng Việt**

> Framework backend Python mang lại trải nghiệm phát triển kiểu Spring Boot nhưng vẫn tôn trọng triết lý Python.

---

XIME không phải một HTTP framework khác. Nó nằm **phía trên** FastAPI, SQLAlchemy và gRPC — cung cấp convention engine, dependency injection tự động và các guardrail kiến trúc để bạn tập trung vào nghiệp vụ thay vì dây nhợ cấu hình.

```python
# Trước XIME — tự kết nối mọi thứ thủ công
container.user_service = providers.Singleton(
    UserService,
    repository=container.user_repository,
    transaction=container.transaction_manager,
)

# Với XIME — chỉ cần viết class
class UserService:
    def __init__(
        self,
        repository: UserRepository,
        transaction: TransactionManager,
    ):
        self.repository = repository
        self.transaction = transaction
```

XIME đọc type hint, quét package, xây dựng dependency graph, validate tại startup và kết nối mọi thứ — tự động.

---

## Tại sao cần XIME?

Python có các thư viện xuất sắc cho HTTP, database và serialization. Điều còn thiếu là một **tầng convention** có thể:

- Tự động phát hiện và kết nối dependency từ type hint của constructor
- Áp dụng ranh giới kiến trúc thông qua cấu trúc thư mục
- Validate dependency graph lúc startup — không phải lúc runtime khi user gọi endpoint
- Cung cấp cấu trúc nhất quán cho các project theo Clean Architecture / DDD / Modular Monolith

XIME lấp đầy khoảng trống đó. Nó không thay thế FastAPI hay SQLAlchemy — nó giúp chúng dễ dùng hơn ở quy mô lớn.

---

## Cách hoạt động

```text
Application Code
      ↓
   XIME Core          ← scanning, DI, lifecycle, config
      ↓
Dependency Injector   ← DI engine runtime
      ↓
Python Objects
```

Trình tự khởi động của XIME:

1. Nạp framework configuration (`config/dependency.py`)
2. Nạp runtime configuration (`resources/application.yml`)
3. Quét các package được khai báo
4. Phân giải type hint
5. Xây dựng dependency graph
6. **Validate graph** — phát hiện vòng lặp, thiếu implementation, binding mơ hồ
7. Tạo singleton
8. Khởi động adapter (FastAPI, gRPC, ...)

Nếu có vấn đề, app **thất bại ngay lúc startup** với thông báo rõ ràng — không phải sau đó trên production.

---

## Bắt đầu nhanh

```python
# app/main.py — REST only
from xime import Application
from xime.adapters.web import WebAdapter

app = Application()
app.use(WebAdapter())
app.run()
```

```python
# app/main.py — REST + gRPC đồng thời
from xime import Application
from xime.adapters.web import WebAdapter
from xime.adapters.grpc import GrpcAdapter

app = Application()
app.use(WebAdapter())
app.use(GrpcAdapter())
app.run()
```

```python
# app/config/dependency.py
from xime import BindingConfig

dependency = BindingConfig()
dependency.scan("application.usecase", "infrastructure.repository")
dependency.bind({UserRepository: JpaUserRepository})
```

```python
# app/api/rest/user_controller.py
from xime.adapters.web.routing import get, post

class UserController:
    prefix = "/users"

    def __init__(self, use_case: GetUserUseCase) -> None:
        self._use_case = use_case

    @get("/{user_id}", response_model=UserResponse)
    async def get_user(self, user_id: int) -> UserResponse:
        return await self._use_case.execute(user_id)
```

```bash
python app/main.py
```

---

## Tính năng

| Tính năng | Mô tả |
| --- | --- |
| **Constructor Injection** | Khai báo dependency qua tham số constructor — XIME tự kết nối |
| **Directory-Driven DI** | Vị trí package quyết định vai trò component — không annotation |
| **Interface Binding** | Ánh xạ `Protocol` → implementation tường minh, validate lúc startup |
| **Fail Fast** | Vòng lặp, thiếu implementation, binding mơ hồ → lỗi startup |
| **Lifecycle Hooks** | `PostConstruct`, `PreDestroy` cho startup/shutdown được quản lý |
| **Event Bus** | Pub/sub nội bộ cho domain event |
| **Request Context** | Dữ liệu theo request qua `ContextVar`, được thiết lập bởi adapter |
| **Security Context** | `AuthenticationManager`, `AuthorizationManager` trong core |
| **Two-Layer Config** | Framework config (Python) + Runtime config (YAML) |
| **Transaction API** | `async with self.transaction():` tường minh — không có AOP ẩn |
| **Class-Based Controllers** | Controller là DI singleton, method ánh xạ thành route |

---

## Starters

Module tùy chọn, tương tự `spring-boot-starter-*`:

| Starter | Cung cấp gì |
| --- | --- |
| `xime.starters.sqlalchemy` | Async DB session, `SqlAlchemyTransactionManager` |
| `xime.starters.jwt` | JWT signing, verification, middleware |
| `xime.starters.scheduler` | Lập lịch tác vụ kiểu cron |
| `xime.starters.redis` | Tích hợp Redis client |
| `xime.starters.cache` | Abstraction layer cho caching |

---

## Nguyên tắc thiết kế

- **Explicit hơn implicit** — binding, routing, config luôn được khai báo tường minh, không tự động phát hiện bằng magic
- **Chỉ constructor injection** — không có `@inject`, field injection, hay `@autowired`
- **Không annotation cho vai trò** — `@service`, `@repository`, `@component` không tồn tại; thư mục quyết định vai trò
- **Fail fast** — lỗi xuất hiện lúc startup, không phải lúc runtime
- **Wrapper mỏng** — XIME không viết lại FastAPI, SQLAlchemy hay gRPC; nó điều phối chúng

---

## Trạng thái dự án

XIME đang trong **giai đoạn phát triển tích cực**. Core DI, lifecycle, event bus, security context, configuration, JWT starter, scheduler starter và routing layer của Web adapter đã được triển khai. Framework chưa được publish lên PyPI.

---

## Đóng góp

XIME là dự án cá nhân cần sự giúp đỡ của cộng đồng để phát triển. Còn rất nhiều việc cần làm: gRPC adapter, WebSocket, Redis/Cache starter, CLI scaffolding, tài liệu, testing utilities và nhiều hơn nữa.

**Cách đóng góp:**

- Đọc [tài liệu kiến trúc](docs/vn/architecture.md) để hiểu thiết kế
- Chọn một mảng từ [roadmap](docs/vn/contributing.md#roadmap)
- Mở issue để thảo luận tính năng hoặc bug
- Gửi pull request

Vui lòng đọc [CONTRIBUTING](docs/vn/contributing.md) trước khi mở PR.

---

## Tài liệu

| Tài liệu | Mô tả |
| --- | --- |
| [Bắt đầu nhanh](docs/vn/getting-started.md) | App đầu tiên trong 5 phút |
| [Kiến trúc](docs/vn/architecture.md) | Cấu trúc nội bộ của XIME |
| [Khái niệm cốt lõi](docs/vn/core-concepts.md) | DI, interface binding, scope |
| [Cấu hình](docs/vn/configuration.md) | Framework config + runtime YAML |
| [Routing](docs/vn/routing.md) | Class-based controller, route decorator |
| [Transaction](docs/vn/transaction.md) | Quản lý transaction tường minh |
| [Starters](docs/vn/starters.md) | SQLAlchemy, JWT, Scheduler, Redis |
| [Testing](docs/vn/testing.md) | DI override, fake, test utilities |
| [Đóng góp](docs/vn/contributing.md) | Cách đóng góp, roadmap |

---

## Giấy phép

MIT
