# Interface Binding bằng Protocol — Xime Framework

## 1. Mục tiêu

Xime không dùng annotation kiểu Spring (`@Repository`, `@Service`, `@Component`) và cũng không tự động suy luận implementation của interface bằng cơ chế scan phức tạp.

Thay vào đó, Xime chọn cách tiếp cận tường minh:

- Interface được định nghĩa bằng `Protocol`
- Implementation là class thông thường
- Ánh xạ Interface → Implementation được khai báo trong cấu hình

Mục tiêu: **Đơn giản, dễ đọc, dễ debug, ít magic, phù hợp triết lý Explicit Architecture.**

---

## 2. Tại sao không tự động tìm Implementation

Trong Java, Spring có thể tự động phát hiện implementation nhờ từ khóa `implements`:

```java
public class JpaUserRepository implements UserRepository {}
```

Framework biết rõ `JpaUserRepository` là implementation của `UserRepository`.

**Python không có cơ chế tương đương.**

```python
from typing import Protocol

class UserRepository(Protocol):
    async def save_user(self) -> None: ...

class JpaUserRepository:
    async def save_user(self) -> None: ...
```

Framework không thể biết chắc `JpaUserRepository` là implementation của `UserRepository` hay chỉ là một class tình cờ có cùng method.

`Protocol` sử dụng **Structural Typing** — "nếu hình dạng giống nhau thì được xem là tương thích." Điều này rất hữu ích cho Type Checker nhưng **không phù hợp** để framework tự động xây dựng Dependency Graph.

---

## 3. Khai báo Interface

Interface được định nghĩa bằng `Protocol`:

```python
from typing import Protocol

class UserRepository(Protocol):
    async def save_user(self) -> None: ...
```

`Protocol` chỉ đóng vai trò:

- Contract
- Type Hint
- Hỗ trợ IDE
- Hỗ trợ MyPy / Pyright

`Protocol` **không** chịu trách nhiệm: Dependency Injection, Lifecycle, Auto Discovery, Auto Binding.

---

## 4. Khai báo Implementation

Implementation là class bình thường — **không bắt buộc** kế thừa Protocol:

```python
class JpaUserRepository:
    async def save_user(self) -> None:
        ...
```

Việc kế thừa (`class JpaUserRepository(UserRepository): ...`) là tùy chọn vì ánh xạ đã được khai báo tường minh trong cấu hình.

---

## 5. Binding Configuration

Khai báo binding tường minh trong `config/dependency.py`:

```python
dependency.bind({
    UserRepository: JpaUserRepository,
    CacheService: RedisCacheService,
    MailService: SmtpMailService,
})
```

Framework không cần suy đoán. Mọi quyết định kiến trúc được khai báo rõ ràng.

---

## 6. Sử dụng trong Business Layer

```python
class UserService:
    def __init__(
        self,
        repository: UserRepository
    ):
        self.repository = repository
```

Business Layer chỉ phụ thuộc vào abstraction (`UserRepository`), không phụ thuộc implementation cụ thể (`JpaUserRepository`).

---

## 7. Luồng Resolve Dependency

Khi framework gặp `repository: UserRepository` trong constructor:

```text
Tra cứu Binding Registry
    UserRepository → JpaUserRepository
            ↓
    Tạo JpaUserRepository
            ↓
    Inject vào UserService
```

---

## 8. Validation khi Startup

Framework kiểm tra tính hợp lệ của mọi binding khi khởi động:

- Interface tồn tại
- Implementation tồn tại
- Implementation thỏa mãn Protocol (có đủ các method được khai báo)

Nếu implementation không thỏa mãn:

```text
Binding Validation Failed

Protocol: UserRepository
Implementation: JpaUserRepository

Missing methods:
  - save_user
```

Nguyên tắc **Fail Fast**: lỗi phải được phát hiện khi startup, không phải khi chạy nghiệp vụ.

---

## 9. Thay thế Implementation theo môi trường

```python
# Production
dependency.bind({UserRepository: JpaUserRepository})

# Testing
dependency.bind({UserRepository: FakeUserRepository})

# Development
dependency.bind({UserRepository: InMemoryUserRepository})
```

Business Layer không cần thay đổi.

---

## 10. So sánh với Spring

| | Spring | Xime |
|---|---|---|
| Interface | `interface` + `implements` | `Protocol` |
| Discovery | Annotation Scan → Auto Binding | Explicit Binding Configuration |
| Triết lý | Convention, Automation, Magic | Explicit, Predictable, Readable |

---

## 11. Triết lý thiết kế

> "Những quyết định kiến trúc quan trọng nên được thể hiện rõ trong code hoặc cấu hình, thay vì được ẩn phía sau cơ chế tự động của framework."

Binding là quyết định kiến trúc quan trọng — Xime khai báo tường minh trong cấu hình, không để framework tự suy đoán.

Nguyên tắc này phù hợp với các giá trị cốt lõi của Xime:

- Explicit Architecture
- Constructor Injection
- Type Hint Driven
- Fail Fast
- Minimal Magic
- Easy Debugging

và tôn trọng triết lý Python: **Explicit is better than implicit.**
