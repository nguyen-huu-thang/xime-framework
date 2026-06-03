# Nguyên tắc Code — Xime Framework

## Không dùng Annotation cho DI

Không bao giờ dùng `@service`, `@repository`, `@component`, `@inject`, hay `@autowired`.
Loại component được suy luận từ **vị trí thư mục**:

```
application/service/       → tầng service
application/usecase/       → tầng use case
infrastructure/repository/ → tầng repository
infrastructure/client/     → external client
```

---

## Constructor Injection Only

Tất cả dependency được khai báo qua tham số constructor. Framework đọc type hint để tự động xây dựng dependency graph:

```python
class UserService:
    def __init__(
        self,
        transaction: TransactionManager,
        repository: UserRepository,
    ):
        self.transaction = transaction
        self.repository = repository
```

---

## Điều kiện đăng ký Class

Một class chỉ được đăng ký vào DI container khi:

- Không phải `ABC` hay `Protocol`
- Tất cả tham số constructor có type hint (thiếu hint → coi như class đó không đăng kí mà là class ngoài DI)
- Không thuộc package bị loại trừ: `domain`, `dto`, `entity`, `vo`, `constant`, `exception`

### Thiếu type hint = class thường, KHÔNG phải lỗi

**Đây là thiết kế có chủ đích, không phải bug.**

Nếu một tham số constructor thiếu type hint, framework **bỏ qua tham số đó** — class vẫn được đưa vào resolved map nhưng với dep rỗng. Tham số đó sẽ không được inject.

```python
class Helper:
    def do_something(self): ...

class MyService:
    def __init__(self, helper):  # thiếu type hint → helper không được inject
        self.helper = helper
```

Lý do thiết kế:
- Type hint là **tín hiệu opt-in** cho DI. Không có hint = developer không muốn framework quản lý dep đó.
- Cho phép class "lai" tồn tại trong cùng package được scan mà không cần tách riêng.
- Nhất quán với triết lý Python: **Explicit is better than implicit** — chỉ inject những gì được khai báo rõ ràng.

Áp dụng cho cả `scan()` lẫn `register()`:

```python
# scan(): class bị SKIP hoàn toàn nếu có ít nhất một param thiếu hint
# register(): class được đưa vào DI nhưng param thiếu hint → không inject → TypeError lúc get()

# Nếu muốn class vào DI, bắt buộc phải có đủ type hint cho mọi dep cần inject:
class MyService:
    def __init__(self, helper: Helper):  # có hint → inject đúng
        self.helper = helper
```

> **Ghi chú cho người review:** Nếu thấy class trong scan package nhận về instance thiếu dep, hãy kiểm tra type hint trước khi báo lỗi framework.

---

## Quét Package

Cấu hình trong `config/dependency.py`:

```python
dependency.scan(
    "application.service",
    "application.usecase",
    "infrastructure.repository",
    "infrastructure.client",
)
```

Quy tắc `__init__.py`:

- Không có `__all__` → scan toàn bộ package
- Có `__all__` → chỉ scan các class được export

```python
__all__ = ["UserService", "AuthService"]
```

---

## Đăng ký Thủ công (Manual Registration)

Hai cơ chế để đưa class vào DI mà không cần auto-scan package, dùng trong `config/dependency.py`.

### 1. `dependency.register()` — Class đơn giản, framework tự inject

Dùng cho domain service, domain factory, hoặc bất kỳ class nào trong package bị loại trừ nhưng vẫn cần là singleton.

```python
from domain.sharedkernel.factory import IdFactory
from domain.sharedkernel.service import IdService
from domain.authentication.factory import CredentialAuthenticationFactory

dependency.register(
    IdFactory,
    IdService,
    CredentialAuthenticationFactory,
)
```

Framework áp dụng constructor injection như bình thường — đọc type hint, resolve dependency, tạo singleton. Mọi tham số `__init__` phải có type hint; thiếu hint → startup thất bại.

### 2. `dependency.configure()` — Config class với factory method (Option B)

Dùng khi cần logic khởi tạo tùy chỉnh: đọc config YAML, tạo object từ secret, gọi factory method tĩnh, v.v.

```python
class DomainConfig:
    def credential_factory(self) -> CredentialAuthenticationFactory:
        return CredentialAuthenticationFactory()

    def key_encryption_service(self, app_config: AppConfig) -> KeyEncryptionService:
        # Đọc secret từ config để khởi tạo
        return AesKeyEncryptionService(app_config.secret_key)

dependency.configure(DomainConfig)
```

**Quy tắc config class:**
- Mỗi public method có return type annotation → tạo một singleton với kiểu đó
- Tham số của method (trừ `self`) → được inject bởi container khi startup
- Config class **không được có tham số constructor** — phải stateless
- Tham số method là Protocol → phải có `dependency.bind(...)` tương ứng

Framework gọi method một lần, lưu kết quả là singleton, inject vào mọi nơi phụ thuộc kiểu đó.

### Tổng thể `config/dependency.py`

```python
# Auto-scan các tầng thông thường
dependency.scan(
    "application.service",
    "application.usecase",
    "infrastructure.repository",
    "infrastructure.client",
)

# Interface binding
dependency.bind({
    UserRepository: JpaUserRepository,
    KeyEncryptionService: AesKeyEncryptionService,
})

# Thủ công: domain class đơn giản (framework tự inject)
dependency.register(
    IdFactory,
    IdService,
)

# Thủ công: class cần logic khởi tạo tùy chỉnh
dependency.configure(DomainConfig)
```

---

## Interface Binding

Interface được định nghĩa bằng `Protocol` (không phải `ABC`). Implementation là class thông thường, không bắt buộc kế thừa Protocol.

Binding được khai báo tường minh trong `config/dependency.py`:

```python
dependency.bind({
    UserRepository: JpaUserRepository,
    CacheService: RedisCacheService,
})
```

Khi startup, framework validate implementation thỏa mãn Protocol — thiếu method → startup thất bại.

Không binding + nhiều candidate → **startup thất bại**.

> Chi tiết đầy đủ: `rules/interface-binding.md`

---

## Phạm vi Dependency (Scope)

- `Singleton` — mặc định cho tầng service/usecase/repository
- `Factory` — một instance mới mỗi lần gọi
- Tương lai: `Request`, `Session` (request-scoped via ContextVar)

---

## Fail Fast

Startup **phải thất bại ngay** với thông báo lỗi rõ ràng khi:

- Interface không có implementation nào được đăng ký
- Interface có nhiều implementation nhưng không có binding tường minh
- Dependency graph có circular dependency

Ví dụ thông báo lỗi:

```text
Missing Type Hint
  Class: UserService
  Parameter: repository
```

```text
No Implementation Found
  Interface: UserRepository
```

```text
Multiple Implementations Found
  Interface: UserRepository
  Candidates: JpaUserRepository, RedisUserRepository
```

```text
Circular dependency detected:
  UserService → AuthService → TokenService → UserService
```

---

## Cấu hình Hai Tầng

**Framework config** — dành cho Developer, viết Python (`config/dependency.py`, `config/routing.py`, …):
cấu hình DI scanning, bindings, lifecycle, routing.

**Runtime config** — dành cho Operator, viết YAML (`resources/application.yml`, `application-{env}.yml`):
host, port, secrets, database, Redis.
