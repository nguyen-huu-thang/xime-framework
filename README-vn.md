<div align="center">

# XIME Framework

**Trải nghiệm phát triển kiểu Spring Boot cho Python - mà vẫn tôn trọng triết lý Python.**

[![PyPI version](https://img.shields.io/pypi/v/xime.svg)](https://pypi.org/project/xime/)
<!-- Badge tĩnh tạm thời. Sau khi publish bản PyPI mới (classifiers 3.12+), khôi phục badge động bằng dòng dưới đây:
     [![Python](https://img.shields.io/pypi/pyversions/xime.svg)](https://pypi.org/project/xime/) -->
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://pypi.org/project/xime/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[English](README.md) · [Tiếng Việt](README-vn.md) · [Tài liệu](docs/vn/getting-started.md) · [Ví dụ](#-dự-án-ví-dụ)

</div>

---

XIME không phải một HTTP framework khác. Nó nằm **phía trên** FastAPI, SQLAlchemy và gRPC - cung cấp convention engine, dependency injection tự động và các guardrail kiến trúc để bạn tập trung vào nghiệp vụ thay vì dây nhợ cấu hình.

```python
# Trước XIME - tự kết nối mọi thứ thủ công
container.user_service = providers.Singleton(
    UserService,
    repository=container.user_repository,
    transaction=container.transaction_manager,
)

# Với XIME - chỉ cần viết class
class UserService:
    def __init__(
        self,
        repository: UserRepository,
        transaction: TransactionManager,
    ):
        self.repository = repository
        self.transaction = transaction
```

XIME đọc type hint, quét package, xây dựng dependency graph, validate tại startup và kết nối mọi thứ - tự động.

---

## Tại sao cần XIME?

Python có các thư viện xuất sắc cho HTTP, database và serialization. Điều còn thiếu là một **tầng convention** có thể:

- Tự động phát hiện và kết nối dependency từ type hint của constructor
- Áp dụng ranh giới kiến trúc thông qua cấu trúc thư mục
- Validate dependency graph lúc startup - không phải lúc runtime khi user gọi endpoint
- Cung cấp cấu trúc nhất quán cho các project theo Clean Architecture / DDD / Modular Monolith

XIME lấp đầy khoảng trống đó. Nó không thay thế FastAPI hay SQLAlchemy - nó giúp chúng dễ dùng hơn ở quy mô lớn.

---

## Cách hoạt động

```text
Application Code
      ↓
   XIME Core          ← scanning, DI, lifecycle, config
      ↓
  DI Container        ← core/container, tích hợp sẵn
      ↓
Python Objects
```

Trình tự khởi động của XIME:

1. Nạp framework configuration (`config/dependency.py`)
2. Nạp runtime configuration (`resources/application.yml`)
3. Quét các package được khai báo
4. Phân giải type hint
5. Xây dựng dependency graph
6. **Validate graph** - phát hiện vòng lặp, thiếu implementation, binding mơ hồ
7. Tạo singleton
8. Khởi động adapter (FastAPI, gRPC, ...)

Nếu có vấn đề, app **thất bại ngay lúc startup** với thông báo rõ ràng - không phải sau đó trên production.

---

## Cài đặt

```bash
pip install xime
```

Adapter và starter là tùy chọn - chỉ cài cái bạn cần:

```bash
pip install "xime[web]"          # Uvicorn ASGI server
pip install "xime[sqlalchemy]"   # async DB session + transaction
pip install "xime[jwt]"          # xác thực JWT
pip install "xime[scheduler]"    # lập lịch tác vụ kiểu cron
pip install "xime[grpc]"         # gRPC adapter (code-first)
pip install "xime[socket]"       # IPC qua Unix domain socket
pip install "xime[all]"          # tất cả ở trên
```

> Yêu cầu **Python 3.12+**.

---

## Bắt đầu nhanh

**1. Định nghĩa controller** - một class thông thường; method ánh xạ thành route.

```python
# app/api/rest/user_controller.py
from xime.adapters.web.routing import get

class UserController:
    prefix = "/users"

    def __init__(self, use_case: GetUserUseCase) -> None:
        self._use_case = use_case

    @get("/{user_id}", response_model=UserResponse)
    async def get_user(self, user_id: int) -> UserResponse:
        return await self._use_case.execute(user_id)
```

**2. Cấu hình dependency injection** - khai báo package cần quét và bind interface với implementation.

```python
# app/config/dependency.py
from xime import BindingConfig

dependency = BindingConfig()
dependency.scan("application.usecase", "infrastructure.repository")
dependency.bind({UserRepository: JpaUserRepository})
```

**3. Khởi động ứng dụng.**

```python
# app/main.py
from xime import Application
from xime.adapters.web import WebAdapter

app = Application()
app.use(WebAdapter())
app.run()
```

**4. Chạy.**

```bash
python app/main.py
```

<details>
<summary><b>Đi xa hơn - nhiều giao thức & nhiều server</b></summary>

```python
# REST + gRPC đồng thời
from xime import Application
from xime.adapters.web import WebAdapter
from xime.adapters.grpc import GrpcAdapter

app = Application()
app.use(WebAdapter())
app.use(GrpcAdapter())
app.run()
```

```python
# Nhiều server trong cùng một tiến trình (public API + internal admin)
from xime import Application
from xime.adapters.web import WebAdapter

app = Application()
app.use(WebAdapter())                              # server_id="default", port từ application.yml
app.use(WebAdapter("admin", "127.0.0.1", 8081))   # server_id="admin", host/port tường minh
app.run()
```

</details>

---

## 📦 Dự án ví dụ

Cách tốt nhất để học XIME là đọc code thật. Các dự án mã nguồn mở dưới đây được xây dựng trên framework - hãy clone, chạy thử và dùng chúng làm tài liệu tham khảo để cấu trúc service của bạn:

| Dự án | Minh họa điều gì | Phù hợp với |
| --- | --- | --- |
| [**xime-shop-example**](https://github.com/nguyen-huu-thang/xime-shop-example) | Demo thương mại điện tử với kiến trúc đa lớp đơn giản, dễ tiếp cận. | 🟢 Mới bắt đầu |
| [**data-service**](https://github.com/nguyen-huu-thang/data-service) | Microservice cấp production: Hexagonal / DDD, gRPC, SQLAlchemy, sharding đa tenant. Tài liệu tham khảo đầy đủ nhất. | 🔵 Pattern thực chiến |
| [**notification-service**](https://github.com/nguyen-huu-thang/notification-service) | Microservice thông báo async, thiên về IO, theo mô hình hướng sự kiện. | 🔵 Async & event |

> Mới làm quen XIME? Hãy bắt đầu với **xime-shop-example** để nắm nền tảng, sau đó nghiên cứu **data-service** để học trọn bộ pattern Hexagonal/DDD ở quy mô production.

---

## Tính năng

| Tính năng | Mô tả |
| --- | --- |
| **Constructor Injection** | Khai báo dependency qua tham số constructor - XIME tự kết nối |
| **Directory-Driven DI** | Vị trí package quyết định vai trò component - không annotation |
| **Interface Binding** | Ánh xạ `Protocol` → implementation tường minh, validate lúc startup |
| **Fail Fast** | Vòng lặp, thiếu implementation, binding mơ hồ → lỗi startup |
| **Lifecycle Hooks** | `PostConstruct`, `PreDestroy` cho startup/shutdown được quản lý |
| **Thứ tự khởi tạo** | `dependency.order([A, B, C])` - kiểm soát thứ tự chạy `post_construct()` giữa các class độc lập |
| **Multi-Server** | Nhiều `WebAdapter` / `GrpcAdapter` / `SocketAdapter` cùng tiến trình, mỗi cái có `server_id` riêng |
| **Event Bus** | Pub/sub nội bộ cho domain event |
| **Request Context** | Dữ liệu theo request qua `ContextVar`, được thiết lập bởi adapter |
| **Security Context** | `AuthenticationManager`, `AuthorizationManager` trong core |
| **Two-Layer Config** | Framework config (Python) + Runtime config (YAML) |
| **Transaction API** | `async with self.transaction():` tường minh - không có AOP ẩn |
| **Class-Based Controllers** | Controller là DI singleton, method ánh xạ thành route |
| **Code-First gRPC** | Viết Python DTO, XIME sinh `.proto` + stub; ổn định field number qua lock file |
| **Socket Adapter** | IPC qua Unix Domain Socket cho Native Engine cùng máy (Linux); `@command` / `@stream` |

---

## Starters

Module tùy chọn, tương tự `spring-boot-starter-*`:

| Starter | Cung cấp gì | Trạng thái |
| --- | --- | --- |
| `xime.starters.sqlalchemy` | Async DB session, `SqlAlchemyTransactionManager` | ✅ Đã implement |
| `xime.starters.jwt` | JWT signing, verification, middleware | ✅ Đã implement |
| `xime.starters.scheduler` | Lập lịch tác vụ kiểu cron | ✅ Đã implement |
| `xime.starters.redis` | Tích hợp Redis client | 🔲 Đang kế hoạch |
| `xime.starters.cache` | Abstraction layer cho caching | 🔲 Đang kế hoạch |

---

## Nguyên tắc thiết kế

- **Explicit hơn implicit** - binding, routing, config luôn được khai báo tường minh, không tự động phát hiện bằng magic
- **Chỉ constructor injection** - không có `@inject`, field injection, hay `@autowired`
- **Không annotation cho vai trò** - `@service`, `@repository`, `@component` không tồn tại; thư mục quyết định vai trò
- **Fail fast** - lỗi xuất hiện lúc startup, không phải lúc runtime
- **Wrapper mỏng** - XIME không viết lại FastAPI, SQLAlchemy hay gRPC; nó điều phối chúng

---

## Trạng thái dự án

XIME đang trong **giai đoạn phát triển tích cực**. Đã implement: core DI, lifecycle, event bus, security context, configuration, JWT starter, scheduler starter, SQLAlchemy starter, Web adapter (FastAPI + routing), gRPC adapter (proto-first + **code-first**), **Socket adapter** (Unix Domain Socket IPC), multi-server support và thứ tự khởi tạo (`dependency.order()`). WebSocket đang hoàn thiện. Redis và Cache starter đang được kế hoạch.

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
| [Code-First gRPC](docs/vn/grpc-codefirst.md) | Sinh `.proto` từ Python DTO; ổn định field number; `xime grpc generate/check` |
| [Socket Adapter](docs/vn/socket-adapter.md) | IPC qua Unix Domain Socket cho Native Engine cùng máy |
| [Starters](docs/vn/starters.md) | SQLAlchemy, JWT, Scheduler |
| [Testing](docs/vn/testing.md) | DI override, fake, test utilities |
| [Đóng góp](docs/vn/contributing.md) | Cách đóng góp, roadmap |

---

## Đóng góp

XIME là dự án cá nhân cần sự giúp đỡ của cộng đồng để phát triển. Còn việc cần làm: hoàn thiện WebSocket, Redis/Cache starter, CLI scaffolding, testing utilities và nhiều hơn nữa.

**Cách đóng góp:**

- Đọc [tài liệu kiến trúc](docs/vn/architecture.md) để hiểu thiết kế
- Chọn một mảng từ [roadmap](docs/vn/contributing.md#roadmap)
- Mở issue để thảo luận tính năng hoặc bug
- Gửi pull request

Vui lòng đọc [CONTRIBUTING](docs/vn/contributing.md) trước khi mở PR.

---

## Giấy phép

Phát hành theo [Giấy phép MIT](LICENSE).
