# Tài liệu thiết kế - Xime Framework

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

Hiện tại (0.5):

```text
Xime Core
    ↑
 ┌──┼─────┬───────┬──────┐
 │  │     │       │      │
HTTP gRPC Socket  MQTT  WebSocket
```

Tương lai: fieldbus công nghiệp (Modbus TCP / OPC UA - xem `../phien-ban/0.7-ke-hoach.md`).

**Nguyên tắc:** Core không phụ thuộc vào FastAPI, grpc.aio, aiomqtt hay aioboto3. Core chỉ chứa: Dependency Injection, Lifecycle, Event Bus, Security, Configuration, Context.

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

#### Đăng ký thủ công (tương đương `@Bean` bên Spring Boot)

Package `domain` bị loại trừ khỏi auto-scan, nhưng một số class domain vẫn cần vào DI (domain factory, domain service). Dùng hai cơ chế sau trong `config/dependency.py`:

**`register()` - class đơn giản, framework tự inject:**

```python
from domain.sharedkernel.factory import IdFactory
from domain.authentication.factory import CredentialAuthenticationFactory

dependency.register(
    IdFactory,
    CredentialAuthenticationFactory,
)
```

**`configure()` - cần logic khởi tạo tùy chỉnh (đọc config, gọi factory method):**

```python
class DomainConfig:
    def credential_factory(self) -> CredentialAuthenticationFactory:
        return CredentialAuthenticationFactory()

    def key_service(self, cfg: AppConfig) -> KeyEncryptionService:
        return AesKeyEncryptionService(cfg.secret_key)

dependency.configure(DomainConfig)
```

Quy tắc `configure()`: mỗi public method có return type → tạo một singleton; tham số method → được inject bởi container; config class không được có tham số constructor.

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
  # Bỏ trống khối ssl -> HTTP thuần. Khai certfile + keyfile -> HTTPS (0.6.3).
  # Cấu hình nửa vời (thiếu một trong hai, file không tồn tại/không đọc được)
  # -> StartupException, KHÔNG im lặng rơi về HTTP.
  ssl:
    certfile: /etc/letsencrypt/live/example.com/fullchain.pem
    keyfile: /etc/letsencrypt/live/example.com/privkey.pem
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

Class bị bỏ qua khi scan (thiếu type hint → không đưa vào DI, không có lỗi):

```python
class UserService:
    def __init__(self, repository):  # ← thiếu type hint → class bình thường, không inject
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

**Chỉ có MỘT scope: singleton, dựng eager lúc khởi động.** Không có prototype, không có
request/session scope trong container.

⚠ Bản trước ghi `Factory - instance mới mỗi lần gọi` và `Tương lai: Request, Session`.
**Cả hai dòng đều SAI**: `FactoryEntry` của `dependency.configure()` được gọi đúng một
lần rồi cache thành singleton, còn request/session thì đã có sẵn nhưng cố ý nằm **ngoài**
container (ContextVar ở `core/context/`, `core/security/context.py`,
`starters/sqlalchemy/session.py`).

Cần một instance mới thì **DI giữ NGƯỜI TẠO, không giữ CÁI ĐƯỢC TẠO** - khuôn chuẩn là
`AsyncSessionFactory`. Lý do đầy đủ, bốn lập luận chống prototype, và điều kiện kích hoạt
nếu có ngày thêm: **`rules/coding.md` mục "Phạm vi Dependency (Scope)"** (nguồn sự thật,
rà 2026-08-20).

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

- SQLAlchemy Starter (transaction + khối chỉ đọc + `CrudRepository`)
- JWT Starter
- Scheduler Starter
- Cache Starter + Redis Starter (backend của `CacheService`)
- Storage Starter + LocalFS / S3 Backend (backend của `StorageService`)
- Mail Starter (backend SMTP của `MailService`)

Tương tự `spring-boot-starter-*` trong Spring Boot.

---

## 15. Mục tiêu cuối cùng

Xime không thay thế FastAPI, grpc.aio, SQLAlchemy, Pydantic.

Xime cung cấp: Convention Engine, Dependency Injection Automation, Dependency Graph Validation, Lifecycle Management, Configuration System, Adapter Integration.

Developer chỉ cần tập trung vào nghiệp vụ. Framework tự động xây dựng phần còn lại.

## 16. Trạng thái từng mảng, và cạm bẫy khi sửa

> Chuyển từ `.claude/CLAUDE.md` ngày 2026-08-21. Đây là **nguồn sự thật duy nhất** về
> "mảng X đã có gì, và sửa nó thì dễ phá chỗ nào" - trước đây nó nằm trong file nạp mọi
> phiên và bị trùng lặp với `CLAUDE.md` ở gốc repo.
>
> ⚠ Ngày ghi trong ngoặc là **ngày mục đó được viết**, không phải ngày kiểm lại. Kiểm bằng
> cách đọc code trong `xime/` và chạy `pytest`, đừng kiểm bằng dòng này.


- **Core DI / lifecycle / config / event bus:** hoàn thành. **Bản 0.6** đã gỡ hẳn
  `dependency-injector` (registry singleton viết lại bằng dict dùng class làm key +
  `RLock` double-checked, API không đổi) và thêm **dynamic interface binding**:
  `bind` chấp nhận value tuple nhiều impl (phần tử đầu = mặc định), cờ runtime
  `xime.di.dynamic-binding` (mặc định tắt = hành vi cũ); khi bật, consumer nhận
  `DynamicProxy` trong suốt và `Switcher` đổi impl toàn cục lúc runtime. Chi tiết:
  `docs/phien-ban/0.6-ke-hoach.md`, `rules/interface-binding.md` mục 12.
- **Web adapter:** hoàn thành, có `configure_middleware` /
  `configure_exception_handlers`. **Mới (0.6.1):** middleware lấy
  dependency từ DI / runtime config qua marker `Inject(...)` / `FromConfig(...)`
  làm giá trị option (phân giải lúc `build_app`, `adapters/web/_markers.py`) +
  helper `configure_cors(...)` (`adapters/web/_cors.py`) - app không phải subclass
  `WebAdapter` nữa. `RequestContextMiddleware` + `JwtAuthMiddleware`
  là **pure-ASGI** (0.5, sửa context-bleeding). File streaming ở
  `adapters/web/files` (`stream_object` Range, `save_upload`).
  **Mới (0.6.3): HTTPS.** Khối `server.ssl` trong `application.yml` ->
  `ServerTlsConfig` (`certfile`/`keyfile`/`keyfile_password`/`ca_certs`/
  `cert_reqs`/`ciphers`); để trống = HTTP thuần như cũ. `cert_reqs` dùng **chữ**
  (`none`/`optional`/`required`), không phải số `ssl.CERT_*`. Validate fail-fast ở
  `_tls_kwargs()` (`adapters/web/_adapter.py`) vì lỗi gốc của uvicorn khi cert
  khai nửa vời không debug được (`AssertionError` rỗng message); chỉ forward
  option thực sự được cấu hình - truyền `ssl_cert_reqs=None` sẽ ném `ValueError`.
  Multi-server: `WebAdapter(..., ssl=...)`, để trống thì **kế thừa** `server.ssl`
  (server phụ không được âm thầm chạy HTTP). Cert phải là **CA công cộng**
  (certbot), KHÔNG dùng cert Trust - browser không tin CA nội bộ. Thiết kế, phần
  đã bỏ (mức 2) và hướng nâng cấp: `docs/thiet-ke/07-tls-web-adapter.md`.
- **gRPC code-first (server):** hoàn thành - `xime grpc generate/check`, sinh
  proto + lock + sidecar `contract.json`, serve qua nối dây động, mTLS động
  (`configure_grpc_tls`).
- **gRPC client SDK:** hoàn thành Phase 1-4 - `xime grpc client` sinh SDK
  (kèm `--package`), `configure_grpc_clients` + DI, `XimeGrpcChannel` (deadline,
  lỗi typed, mTLS động, retry policy 0.3 chỉ unary, `tls.server_id` multi-server).
- **Socket adapter:** hoàn thành (dùng chung contract với gRPC code-first).
- **MQTT adapter (0.5):** hoàn thành - `@subscribe` (pub/sub) + `@rpc` (RPC over
  MQTT v5), `MqttPublisher`, auto-reconnect, định tuyến bằng Subscription
  Identifier, extra `xime[mqtt]` (aiomqtt import lười). Vòng lặp live cần broker
  thật để test E2E (`tests_temp/mqtt/test_integration.py`, guard-skip).
- **Storage starter (0.5):** hoàn thành - Protocol `StorageService` + backend
  `localfs` (chống path traversal, ghi nguyên tử) và `s3` (multipart, presigned,
  MinIO; extra `xime[s3]`). Key chuẩn hóa chung qua `storage/_keys.py`.
- **Mail starter (0.6.2):** hoàn thành - Protocol `MailService` + backend
  `SmtpMailService` (aiosmtplib, extra `xime[mail]`, import lười). `send(EmailMessage)`
  async đồng-bộ-logic: await tới khi gửi xong, timeout nội bộ, thất bại ->
  `MailSendError` (giữ `__cause__`). `EmailMessage` (frozen dataclass) hỗ trợ
  HTML + text (cả hai -> multipart/alternative), nhiều người nhận, `cc`, `reply_to`,
  `sender` override `mail.from`. Mỗi `send()` mở/đóng một kết nối SMTP (không pool),
  tự chọn STARTTLS (587) / TLS ngầm (465) theo cổng. Đọc `mail.*` từ `RuntimeConfig`
  (`mail.smtp.host` bắt buộc). Gửi nền là việc của app (tự `create_task`). Hiện thực:
  `xime/starters/mail/`.
- **SQLAlchemy starter:** thêm `CrudRepository[T]` (0.6.1) - base repository generic
  cho sẵn `find/find_or_fail/find_all/exists/count/save/save_all/delete`; `model`
  là abstract property nên lớp nền là abstract (scanner bỏ qua), chỉ subclass set
  `model` mới vào DI. `find_or_fail` ném `EntityNotFoundError`. Hiện thực:
  `xime/starters/sqlalchemy/repository.py`.
- **Khối chỉ đọc `read_only()` (0.6.3):** usecase không ghi dùng `ReadOnlyManager`
  (`core/transaction/readonly.py`) - manager **riêng, cùng cấp** với
  `TransactionManager`, KHÔNG phải method của nó (tách binding để sau này trỏ đường
  đọc sang read replica bằng một dòng `bind`, không sửa code nghiệp vụ). Impl:
  `starters/sqlalchemy/readonly.py`. Bốn điểm dễ phá khi sửa: (1) **không bao giờ
  commit**; (2) lồng trong khối đang chạy thì **mượn session**, thoát ra không làm
  gì - đừng đổi thành ném lỗi, ca "service chỉ đọc ghép vào usecase có ghi" là ca
  thật; (3) **`expunge_all()` phải chạy TRƯỚC `rollback()`**, bỏ dòng đó thì entity
  trả ra ngoài ném `DetachedInstanceError` (có 2 test canh, đã kiểm chứng bằng cách
  xóa thử); (4) không gọi `begin()` tường minh, để autobegin. **Ranh giới đã chốt:**
  framework KHÔNG chặn việc sửa entity đọc ngoài transaction (thay đổi bị bỏ im
  lặng) - cố ý, bù bằng quy tắc tài liệu, đừng đề xuất hook SQLAlchemy event. Chi
  tiết: `rules/transaction.md`.
- **Modbus adapter (0.7):** hoàn thành - master (đọc theo yêu cầu + `@poll`/
  `@on_change`) và slave (`@serve`/`@on_write`). Trục chính là **Device Model khai
  báo** (`@device` + `Holding/Input/Coil/Discrete`) tự giải mã thanh ghi. Bốn điểm
  dễ phá khi sửa: (1) **địa chỉ có hai đường vào tường minh** - `Holding(2)` là
  0-based, `Holding(modicon=40003)` là số datasheet; đừng gộp thành một tham số
  "thông minh", nhập nhèm sẽ đọc nhầm thanh ghi mà KHÔNG báo lỗi; (2) **planner gom
  range theo `max_gap`, KHÔNG đọc một block lớn** - block lớn quét trúng địa chỉ
  không tồn tại là hỏng cả lần đọc (`ILLEGAL DATA ADDRESS`); (3) **`@on_change`
  không bắn ở lần đọc đầu** (chỉ lấy mốc) - đổi thành bắn là mọi handler kêu lúc
  khởi động; (4) **bốn vùng nhớ là bốn không gian tách biệt**, một lệnh đọc không
  bao giờ trải qua hai vùng. Phần slave dùng `SimData`/`SimDevice`, KHÔNG dùng
  `ModbusServerContext` (đã deprecated, xóa ở pymodbus v4, và trên 3.14 còn lệch
  địa chỉ một đơn vị). Extra `xime[modbus]`, floor `pymodbus>=3.14`. Tài liệu:
  `docs/{vn,en}/modbus.md`.
- **OPC UA adapter (0.7):** hoàn thành - client (`read`/`read_model`/`write`,
  `@on_node_change`) và server (`@serve_nodes`/`@on_node_write`), đủ ba mức bảo
  mật None/Sign/SignAndEncrypt. Ba điểm dễ phá: (1) **đọc bằng
  `read_attributes()`, KHÔNG dùng `read_values()`** - hàm sau vứt StatusCode từng
  node nên NodeId sai trả `None` im lặng; (2) **giá trị đầu tiên chỉ là mốc**
  (`initial=False` mặc định) để giống quy tắc `@on_change` của Modbus; (3) **node
  có `@on_node_write` thì client làm chủ**, vòng refresh không ghi đè. Handler
  chạy trong task riêng vì `asyncua` gọi callback ĐỒNG BỘ. Extra `xime[opcua]`.
  Tài liệu: `docs/{vn,en}/opcua.md`.
- **JWT (0.5):** thêm ép `audience`/`issuer`, phơi claim qua `request_context[JWT_CLAIMS]`.
- **Danh tính peer mTLS (0.6.3):** ngoài `PEER_CN` (định danh **tiến trình** gọi, có từ
  0.4) nay còn **`PEER_APP_ID`** - định danh **APPLICATION** sở hữu tiến trình đó, đọc từ
  SAN URI `xime-app://<Base62 33 ký tự>` của client cert. Helper `current_app_id()` cạnh
  `current_caller()` (`core/security/peer.py`); trích xuất ở
  `adapters/grpc/interceptors/_context.py` (`_read_peer_app_id`, gọi trong
  `_set_peer_identity` nên cả unary lẫn streaming đều có). SAN là property **nhiều giá
  trị** -> duyệt hết entry, chấp nhận cả dạng `URI:` prefix, fail-soft tuyệt đối (cert lạ
  -> `None`, không bao giờ ném). Framework chỉ cấp sự thật thô: KHÔNG giải Base62, KHÔNG
  kiểm app tồn tại, KHÔNG kiểm quyền. Bối cảnh: `docs/da-phu-dinh/peer-app-id-tu-san-cert.md`.
- **Cờ boolean trong runtime config (0.6.3):** đọc bằng `RuntimeConfig.get_bool(key)`, đừng
  dùng `bool(runtime.get(key))` - `bool("false")` là `True` nên chuỗi trong YAML sẽ bật
  nhầm tính năng. `get_bool` ép kiểu bằng chính bộ parse của Pydantic, giá trị lạ ném
  `StartupException`.
- **Kiểm toán toàn diện 0.5:** xem `docs/kiem-toan/0.5.md` (mọi phát hiện đã xử lý).
- **Kiểm toán trước khi đẩy PyPI (0.7.0): XONG 2026-07-30** - xem
  `docs/kiem-toan/0.7-truoc-phat-hanh.md`. Khác hai đợt trước ở chỗ soi thêm **lớp đóng gói/phát
  hành** (build, nội dung wheel/sdist, cài vào venv trắng, floor deps,
  `mypy --strict` phía người dùng) và **tính đúng đắn của tài liệu** - hai lớp mà
  1427 test không chạm tới. 16 phát hiện, **đã vá hết**, +27 test canh.
- **Kiểm toán toàn diện 0.6.2:** xem `docs/kiem-toan/0.6.md` (không có lỗi CAO;
  M1a/b/c "thiếu test" là báo động giả - đã có test; M2 version fallback + L1-L5
  hardening nhỏ đã vá; bài học: kiểm "có test cho X" bằng Grep nội dung, không Glob tên file).
- **Backlog lỗi: HIỆN KHÔNG CÒN MỤC NÀO MỞ** (`docs/kiem-toan/backlog-sua-loi.md` - cả 11 mục
  đã đóng). Đừng đọc file đó để "tìm việc"; nó chỉ còn giá trị tra cứu lỗi cũ đã sửa
  thế nào. Hai mục theo dõi B1/B2 từ kiểm toán 0.6 cũng đã xử lý ở 0.6.3.

