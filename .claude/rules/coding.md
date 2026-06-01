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
