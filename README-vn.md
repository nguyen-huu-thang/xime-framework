<div align="center">

# XIME Framework

**Trải nghiệm phát triển kiểu Spring Boot cho Python - mà vẫn tôn trọng triết lý Python.**

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://pypi.org/project/xime/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[English](README.md) | **Tiếng Việt**

[Tài liệu](docs/vn/getting-started.md) · [Ví dụ](#-dự-án-ví-dụ)

</div>

---

XIME là một tầng convention cho microservice Python. Nó nằm **phía trên** FastAPI, SQLAlchemy và gRPC - cung cấp dependency injection tự động, validation dependency graph ngay lúc startup và các guardrail kiến trúc để bạn tập trung vào nghiệp vụ thay vì dây nhợ cấu hình.

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

## Tại sao không dùng dependency-injector, injector hay lagom?

Đây là những thư viện tốt. Trước đây XIME dùng `dependency-injector` bên trong làm lớp lưu trữ singleton, nhưng từ bản 0.6 lớp registry được tự viết (một dict đơn giản dùng chính class làm key), nên XIME không còn phụ thuộc thư viện DI bên thứ ba nào. Sự khác biệt nằm ở phạm vi:

| | dependency-injector / injector | lagom | XIME |
|---|---|---|---|
| Tự động quét package theo thư mục | Không - phải wire thủ công | Không | Có |
| Validate dependency graph lúc startup | Không | Một phần | Có - vòng lặp, thiếu impl, binding mơ hồ |
| Sinh gRPC code-first | Không | Không | Có |
| Tích hợp web framework | Không | Không | Có - controller, middleware, lifecycle |
| Quản lý transaction tường minh | Không | Không | Có - `async with self.transaction():` |
| Thiết kế cho cấu trúc microservice | Không | Không | Có |

Nếu bạn chỉ cần DI, hãy dùng `dependency-injector` hay `lagom`. Nếu bạn muốn một tầng convention đầy đủ kết nối DI, HTTP, gRPC, transaction và lifecycle lại với nhau - hãy dùng XIME.

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
pip install "xime[redis]"        # Redis client + backend cache
pip install "xime[grpc]"         # gRPC adapter (code-first)
pip install "xime[socket]"       # IPC qua Unix domain socket
pip install "xime[mqtt]"         # MQTT adapter (pub/sub + RPC over MQTT v5)
pip install "xime[s3]"           # backend storage S3 / MinIO
pip install "xime[mail]"         # gửi email qua SMTP (aiosmtplib)
pip install "xime[modbus]"       # adapter Modbus TCP (master + slave)
pip install "xime[opcua]"        # adapter OPC UA (client + server)
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
python -m app.main
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
| [**xime-grpc-socket-example**](https://github.com/nguyen-huu-thang/xime-grpc-socket-example) | Một app phục vụ song song gRPC (code-first, mTLS động) và Unix Domain Socket, dùng chung contract `@command` / `@stream` với hai mô hình bảo mật khác nhau. | 🟣 Đa giao thức |

> Mới làm quen XIME? Hãy bắt đầu với **xime-shop-example** để nắm nền tảng, sau đó nghiên cứu **data-service** để học trọn bộ pattern Hexagonal/DDD ở quy mô production. Muốn xem một app vừa nói gRPC vừa nói socket, đọc **xime-grpc-socket-example**.

---

## Tính năng

| Tính năng | Mô tả |
| --- | --- |
| **Constructor Injection** | Khai báo dependency qua tham số constructor - XIME tự kết nối |
| **Directory-Driven DI** | Vị trí package quyết định vai trò component - không annotation |
| **Interface Binding** | Ánh xạ `Protocol` → implementation tường minh, validate lúc startup |
| **Dynamic Binding** | Bind một `Protocol` tới nhiều impl (một tuple) và đổi toàn cục lúc runtime qua `Switcher`; mặc định tắt, consumer giữ nguyên code |
| **Fail Fast** | Vòng lặp, thiếu implementation, binding mơ hồ → lỗi startup |
| **Lifecycle Hooks** | `PostConstruct`, `PreDestroy` cho startup/shutdown được quản lý |
| **Thứ tự khởi tạo** | `dependency.order([A, B, C])` - kiểm soát thứ tự chạy `post_construct()` giữa các class độc lập |
| **Multi-Server** | Nhiều `WebAdapter` / `GrpcAdapter` / `SocketAdapter` cùng tiến trình, mỗi cái có `server_id` riêng |
| **Event Bus** | Pub/sub nội bộ cho domain event |
| **Request Context** | Dữ liệu theo request qua `ContextVar`, được thiết lập bởi adapter |
| **Security Context** | `AuthenticationManager`, `AuthorizationManager` trong core |
| **Two-Layer Config** | Framework config (Python) + Runtime config (YAML) |
| **Transaction API** | `async with self.transaction():` tường minh - không có AOP ẩn; đường đọc dùng `async with self.read_only():` |
| **Class-Based Controllers** | Controller là DI singleton, method ánh xạ thành route |
| **Code-First gRPC** | Viết Python DTO, XIME sinh `.proto` + stub; ổn định field number qua lock file |
| **gRPC Client SDK** | Sinh client Pydantic typed từ `.proto`, inject qua DI; deadline, lỗi typed, retry tự động |
| **mTLS động** | Xoay chứng chỉ không cần restart, cho cả server inbound lẫn client outbound |
| **Danh tính peer** | gRPC đọc client cert đã verify vào request context (fail-soft): `current_caller()` cho CN, `current_peer_sans()` cho mọi Subject Alternative Name - thô và không diễn giải, nên bạn tự khớp scheme của mình (SPIFFE ID hay gì khác) |
| **Socket Adapter** | IPC qua Unix Domain Socket cho Native Engine cùng máy (Linux); `@command` / `@stream` |
| **MQTT Adapter** | Transport message-driven cho IoT/embedded: `@subscribe` (pub/sub) + `@rpc` (request/reply qua MQTT v5); auto-reconnect; giới hạn đồng thời |
| **Modbus Adapter** | Nói chuyện thẳng với PLC: device model khai báo tự giải mã thanh ghi (endian, thứ tự word, scale), lập kế hoạch đọc an toàn, `@poll` / `@on_change`, và chế độ slave (`@serve` / `@on_write`) |
| **OPC UA Adapter** | Client và server cho chuẩn công nghiệp hiện đại: node model, subscription thật (`@on_node_change`), đủ ba mức bảo mật |
| **File Storage** | `StorageService` trung lập backend (filesystem local / S3 / MinIO); API bytes + streaming; helper download HTTP Range và upload theo chunk |

---

## Starters

Module tùy chọn, tương tự `spring-boot-starter-*`:

| Starter | Cung cấp gì | Trạng thái |
| --- | --- | --- |
| `xime.starters.sqlalchemy` | Async DB session, `SqlAlchemyTransactionManager`, `SqlAlchemyReadOnlyManager` (khối chỉ đọc), `CrudRepository` (CRUD chung) | ✅ Đã implement |
| `xime.starters.jwt` | JWT signing, verification, middleware, **khóa xoay theo `kid`** | ✅ Đã implement |
| `xime.starters.scheduler` | Lập lịch tác vụ kiểu cron | ✅ Đã implement |
| `xime.starters.cache` | Abstraction `CacheService` (trung lập backend) | ✅ Đã implement |
| `xime.starters.redis` | Async Redis client + backend cho `CacheService` | ✅ Đã implement |
| `xime.starters.storage` | Abstraction `StorageService` (object/blob store) | ✅ Đã implement |
| `xime.starters.localfs` | Backend `StorageService` trên filesystem local | ✅ Đã implement |
| `xime.starters.s3` | Backend `StorageService` S3 / MinIO (multipart, presigned URL) | ✅ Đã implement |
| `xime.starters.mail` | Abstraction `MailService` + backend SMTP (async, HTML + text) | ✅ Đã implement |

---

## Nguyên tắc thiết kế

- **Explicit hơn implicit** - binding, routing, config luôn được khai báo tường minh, không tự động phát hiện bằng magic
- **Chỉ constructor injection** - không có `@inject`, field injection, hay `@autowired`
- **Không annotation cho vai trò** - `@service`, `@repository`, `@component` không tồn tại; thư mục quyết định vai trò
- **Fail fast** - lỗi xuất hiện lúc startup, không phải lúc runtime
- **Wrapper mỏng** - XIME không viết lại FastAPI, SQLAlchemy hay gRPC; nó điều phối chúng

---

## Trạng thái dự án

XIME đang trong **giai đoạn phát triển tích cực**. Đã implement: core DI (registry singleton tự viết, **không phụ thuộc thư viện DI bên thứ ba**) với **dynamic interface binding** (một Protocol → nhiều impl, đổi được lúc runtime), lifecycle, event bus, security context, configuration, JWT starter (ép `audience`/`issuer`, **bộ khóa định địa chỉ bằng `kid`**, dung sai đồng hồ, claim bắt buộc), scheduler starter, SQLAlchemy starter, Cache + Redis starter, **Storage starter** (filesystem local + S3/MinIO) kèm **streaming file HTTP** (download Range, upload theo chunk), Web adapter (FastAPI + routing, middleware request-context & JWT kiểu pure-ASGI, middleware & exception handler tùy chỉnh, **middleware lấy được DI/config qua marker `Inject`/`FromConfig` + helper `configure_cors` hạng nhất**), gRPC adapter (proto-first + **code-first**, **server streaming có kiểu**, **mTLS động**), **gRPC client SDK** (typed, inject qua DI, deadline + lỗi typed + retry tự động), **Socket adapter** (Unix Domain Socket IPC), **MQTT adapter** (pub/sub + RPC over MQTT v5), **Modbus adapter** (device model khai báo, master polling + chế độ slave), **OPC UA adapter** (node model, subscription, chế độ server, đủ mức bảo mật), multi-server support, **WebSocket** (định tuyến `@ws`, xác thực bắt tay qua `Sec-WebSocket-Protocol`, đóng kết nối khi token hết hạn) và thứ tự khởi tạo (`dependency.order()`).

Core được bao phủ bởi **1400+ test**.

Xem [CHANGELOG](CHANGELOG.md) để biết lịch sử phiên bản.

---

## Tài liệu

| Tài liệu | Mô tả |
| --- | --- |
| [Bắt đầu nhanh](docs/vn/getting-started.md) | App đầu tiên trong 5 phút |
| [Kiến trúc](docs/vn/architecture.md) | Cấu trúc nội bộ của XIME |
| [Khái niệm cốt lõi](docs/vn/core-concepts.md) | DI, interface binding, scope |
| [Cấu hình](docs/vn/configuration.md) | Framework config + runtime YAML |
| [Routing](docs/vn/routing.md) | Class-based controller, route decorator |
| [Transaction](docs/vn/transaction.md) | Quản lý transaction tường minh + khối chỉ đọc |
| [Code-First gRPC](docs/vn/grpc-codefirst.md) | Sinh `.proto` từ Python DTO; ổn định field number; `xime grpc generate/check`; mTLS động |
| [gRPC Client SDK](docs/vn/grpc-client.md) | Sinh client SDK typed; inject qua DI; deadline, lỗi typed, retry, mTLS động |
| [WebSocket](docs/vn/websocket.md) | Route `@ws`, token đi trong subprotocol, xác thực trước khi vào handler, đóng khi token hết hạn |
| [Socket Adapter](docs/vn/socket-adapter.md) | IPC qua Unix Domain Socket cho Native Engine cùng máy |
| [MQTT Adapter](docs/vn/mqtt.md) | Pub/sub message-driven + RPC over MQTT v5 cho IoT/embedded |
| [Modbus Adapter](docs/vn/modbus.md) | Device model khai báo, lập kế hoạch đọc, polling và chế độ slave cho PLC |
| [OPC UA Adapter](docs/vn/opcua.md) | Node model, subscription, chế độ server và đủ ba mức bảo mật |
| [File Storage](docs/vn/file-storage.md) | `StorageService` (local / S3 / MinIO) + download HTTP Range & upload theo chunk |
| [Store liên tiến trình](docs/vn/store.md) | Kho khoá-giá trị trên LMDB cho trạng thái không có nguồn bền vững: hãm nhịp, thử thách passkey, chống lặp |
| [Dữ liệu tham chiếu dùng chung](docs/vn/refdata.md) | `RefData` - một bản trong bộ nhớ chung cho khoá JWT, danh bạ app: primary publish, mọi tiến trình đọc |
| [Bus liên tiến trình](docs/vn/process-link.md) | `ProcessLink` - lệnh và câu hỏi giữa các tiến trình, bốn kết cục của `ask`, thứ tự theo kênh |
| [Công cụ dòng lệnh](docs/vn/cli.md) | `xime init` dựng dự án · `xime config --print` in mọi khoá kèm mặc định · `xime check config` bắt khoá gõ sai |
| [Chạy nhiều tiến trình](docs/vn/multi-process.md) | `share_load()` - khối `processes:`, cổng dùng chung, supervisor, `run_once()`, thăng cấp primary, watchdog, `/healthz`, và hai phép dò cho code mức module |
| [Starters](docs/vn/starters.md) | SQLAlchemy, JWT, Scheduler, Cache, Redis, Storage (local / S3 + streaming HTTP) |
| [Testing](docs/vn/testing.md) | DI override, fake, test utilities |
| [Đóng góp](docs/vn/contributing.md) | Cách đóng góp, roadmap |

---

## Đóng góp

XIME là dự án cá nhân cần sự giúp đỡ của cộng đồng để phát triển. Còn việc cần làm: runtime đa tiến trình, CLI scaffolding, testing utilities và nhiều hơn nữa.

**Cách đóng góp:**

- Đọc [tài liệu kiến trúc](docs/vn/architecture.md) để hiểu thiết kế
- Chọn một mảng từ [roadmap](docs/vn/contributing.md#roadmap)
- Mở issue để thảo luận tính năng hoặc bug
- Gửi pull request

Vui lòng đọc [CONTRIBUTING](docs/vn/contributing.md) trước khi mở PR.

---

## Giấy phép

Phát hành theo [Giấy phép MIT](LICENSE).
