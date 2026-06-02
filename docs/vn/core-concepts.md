# Khái niệm cốt lõi

[English](../en/core-concepts.md) | **Tiếng Việt**

---

## 1. Constructor Injection

XIME chỉ dùng constructor injection. Mọi dependency được khai báo là tham số constructor có type hint:

```python
class UserService:
    def __init__(
        self,
        repository: UserRepository,
        transaction: TransactionManager,
    ):
        self.repository = repository
        self.transaction = transaction
```

XIME đọc type hint, giải quyết từng dependency và tạo object — bạn không bao giờ phải gọi `UserService(...)` thủ công.

**Quy tắc:**
- Mỗi tham số phải có type hint. Thiếu hint đồng nghĩa XIME không thể giải quyết nó, class đó được coi là nằm ngoài DI system.
- Không `@inject`, không `@autowired`, không field injection.

---

## 2. Directory-Driven Registration

Phát hiện dựa trên annotation (`@Service`, `@Component`) được thay bằng phát hiện dựa trên thư mục:

| Thư mục | Vai trò |
|---|---|
| `application/usecase/` | Use case layer |
| `application/service/` | Application service layer |
| `infrastructure/repository/` | Repository layer |
| `infrastructure/client/` | External service client |

Bạn khai báo package nào cần quét trong `config/dependency.py`:

```python
dependency.scan(
    "application.usecase",
    "application.service",
    "infrastructure.repository",
    "infrastructure.client",
)
```

Package **bị loại trừ** khỏi DI (class ở đây không bao giờ được đăng ký):

- `domain`, `dto`, `entity`, `vo`, `constant`, `exception`

Bị loại trừ vì chúng là data object, không phải service — inject chúng không có ý nghĩa.

---

## 3. Điều kiện đăng ký Class

Một class được đăng ký vào DI container khi **tất cả** điều kiện sau đúng:

1. Không phải subclass của `ABC` hay `Protocol`
2. Tất cả tham số `__init__` có type hint
3. Package của nó nằm trong danh sách scan và không trong danh sách exclude

Nếu class có tham số thiếu type hint, nó bị bỏ qua yên lặng — không phải lỗi. Điều này cho phép class bên thứ ba tồn tại trong package được scan mà không gây vấn đề.

---

## 4. Interface Binding bằng Protocol

`Protocol` của Python cho phép structural typing — một class thỏa mãn Protocol nếu có đúng method, không cần kế thừa tường minh.

Định nghĩa interface:

```python
from typing import Protocol

class UserRepository(Protocol):
    async def find_by_id(self, user_id: int) -> User | None: ...
    async def save(self, user: User) -> None: ...
```

Viết implementation — **không bắt buộc kế thừa**:

```python
class JpaUserRepository:
    async def find_by_id(self, user_id: int) -> User | None:
        ...
    async def save(self, user: User) -> None:
        ...
```

Khai báo binding tường minh trong `config/dependency.py`:

```python
dependency.bind({
    UserRepository: JpaUserRepository,
})
```

XIME validate lúc startup rằng `JpaUserRepository` implement đủ mọi method được khai báo trong `UserRepository`. Nếu thiếu method, startup thất bại:

```
Binding Validation Failed
  Protocol: UserRepository
  Implementation: JpaUserRepository
  Missing methods:
    - save
```

**Tại sao cần binding tường minh?**

`Protocol` dùng structural typing — Python không thể biết class có cố ý implement interface hay chỉ tình cờ có cùng method. Binding tường minh làm quyết định kiến trúc rõ ràng trong code. Xem [Interface Binding](../en/core-concepts.md) để biết lý do đầy đủ.

---

## 5. Dependency Scope

| Scope | Mô tả | Mặc định |
|---|---|---|
| `Singleton` | Một instance cho toàn bộ vòng đời ứng dụng | Có |
| `Factory` | Instance mới mỗi lần gọi | Không |

Tất cả service, use case và repository là singleton theo mặc định. Factory scope sẽ có thể cấu hình trong phiên bản tương lai.

---

## 6. Fail Fast Validation

XIME validate toàn bộ dependency graph trước khi tạo bất kỳ object nào. Startup thất bại ngay với lỗi mô tả rõ ràng cho:

**Thiếu implementation:**
```
No Implementation Found
  Interface: UserRepository
  Hint: add dependency.bind({UserRepository: YourImpl}) in config/dependency.py
```

**Implementation mơ hồ** (nhiều candidate, không có binding tường minh):
```
Multiple Implementations Found
  Interface: UserRepository
  Candidates: JpaUserRepository, RedisUserRepository
  Hint: add dependency.bind({UserRepository: <chosen impl>}) in config/dependency.py
```

**Circular dependency:**
```
Circular dependency detected:
  UserService → AuthService → TokenService → UserService
```

**Thiếu type hint:**
```
Missing Type Hint
  Class: UserService
  Parameter: repository
  Hint: add a type annotation — def __init__(self, repository: UserRepository)
```

---

## 7. Package Scanning và `__init__.py`

Mặc định, scan một package sẽ tìm tất cả class trong tất cả submodule. Bạn có thể giới hạn class nào được export bằng `__all__`:

```python
# application/usecase/__init__.py
__all__ = ["GetUserUseCase", "CreateUserUseCase"]
```

Khi có `__all__`, chỉ class được liệt kê mới được scan. Không có `__all__` thì scan hết.

---

## 8. Lifecycle Hooks

Class có thể hook vào vòng đời ứng dụng:

```python
from xime.lifecycle import PostConstruct, PreDestroy

class DatabasePool:
    def __init__(self) -> None:
        self._pool = None

    async def on_start(self) -> None:   # gọi sau khi tất cả singleton được tạo
        self._pool = await create_pool()

    async def on_stop(self) -> None:    # gọi trước khi shutdown
        await self._pool.close()

PostConstruct.register(DatabasePool, "on_start")
PreDestroy.register(DatabasePool, "on_stop")
```

---

## 9. Event Bus

Event bus nội bộ tách biệt các component không nên phụ thuộc trực tiếp vào nhau:

```python
from xime.event import EventBus, EventHandler

class UserCreatedEvent:
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id

class NotificationHandler(EventHandler[UserCreatedEvent]):
    async def handle(self, event: UserCreatedEvent) -> None:
        await send_welcome_email(event.user_id)
```

Publish từ use case:

```python
class CreateUserUseCase:
    def __init__(self, bus: EventBus, repository: UserRepository) -> None:
        self._bus = bus
        self._repository = repository

    async def execute(self, command: CreateUserCommand) -> User:
        user = await self._repository.save(User(...))
        await self._bus.publish(UserCreatedEvent(user.id))
        return user
```

---

## 10. Request Context

Dữ liệu theo phạm vi request chạy qua `ContextVar`, không qua tham số hàm hay global state:

```python
from xime.context import current_user, request_id
```

Adapter (middleware) thiết lập context lúc bắt đầu mỗi request. Business code đọc nó:

```python
class AuditService:
    async def log(self, action: str) -> None:
        user = current_user.get()
        rid = request_id.get()
        await self._repository.save_log(user.id, rid, action)
```

Vì `ContextVar` an toàn với async, mỗi request đồng thời có context được cô lập riêng.
