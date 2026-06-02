# Bắt đầu nhanh

[English](../en/getting-started.md) | **Tiếng Việt**

Hướng dẫn này giúp bạn tạo ứng dụng XIME đầu tiên.

---

## Yêu cầu

- Python 3.11+
- Biết cơ bản async/await
- Biết FastAPI sẽ giúp nhưng không bắt buộc

---

## Cài đặt

XIME chưa có trên PyPI. Cài từ source:

```bash
git clone https://github.com/your-org/xime-framework
cd xime-framework
pip install -e .
```

---

## Cấu trúc dự án

Một ứng dụng XIME tối thiểu chỉ cần hai thư mục:

```
my-service/
├── app/
│   └── main.py
└── test/
```

Cấu trúc đầy đủ khuyến nghị cho microservice:

```
my-service/
├── app/
│   ├── main.py
│   ├── api/
│   │   └── rest/
│   │       └── user_controller.py
│   ├── application/
│   │   ├── usecase/
│   │   │   └── get_user_use_case.py
│   │   └── port/
│   │       └── outbound/
│   │           └── user_repository.py   ← Protocol (interface)
│   ├── infrastructure/
│   │   └── persistence/
│   │       └── repository/
│   │           └── jpa_user_repository.py
│   ├── domain/
│   │   └── user.py
│   ├── config/
│   │   ├── dependency.py
│   │   └── routing.py
│   └── resources/
│       └── application.yml
└── test/
```

---

## Bước 1 — Định nghĩa Domain

```python
# app/domain/user.py
from dataclasses import dataclass

@dataclass
class User:
    id: int
    name: str
    email: str
```

---

## Bước 2 — Định nghĩa Interface (Protocol)

```python
# app/application/port/outbound/user_repository.py
from typing import Protocol
from domain.user import User

class UserRepository(Protocol):
    async def find_by_id(self, user_id: int) -> User | None: ...
```

---

## Bước 3 — Viết Use Case

```python
# app/application/usecase/get_user_use_case.py
from application.port.outbound.user_repository import UserRepository
from domain.user import User

class GetUserUseCase:
    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def execute(self, user_id: int) -> User:
        user = await self._repository.find_by_id(user_id)
        if user is None:
            raise ValueError(f"User {user_id} không tồn tại")
        return user
```

Không annotation. Không `@service`. XIME tự phát hiện class này từ package scan và tự giải quyết `UserRepository`.

---

## Bước 4 — Viết Implementation

```python
# app/infrastructure/persistence/repository/jpa_user_repository.py
from application.port.outbound.user_repository import UserRepository
from domain.user import User

class JpaUserRepository:
    async def find_by_id(self, user_id: int) -> User | None:
        # query database ở đây
        return User(id=user_id, name="Alice", email="alice@example.com")
```

---

## Bước 5 — Viết Controller

```python
# app/api/rest/user_controller.py
from pydantic import BaseModel
from xime.adapters.web.routing import get
from application.usecase.get_user_use_case import GetUserUseCase

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

class UserController:
    prefix = "/users"
    tags = ["users"]

    def __init__(self, use_case: GetUserUseCase) -> None:
        self._use_case = use_case

    @get("/{user_id}", response_model=UserResponse)
    async def get_user(self, user_id: int) -> UserResponse:
        user = await self._use_case.execute(user_id)
        return UserResponse(id=user.id, name=user.name, email=user.email)
```

---

## Bước 6 — Cấu hình DI

```python
# app/config/dependency.py
from xime import BindingConfig
from application.port.outbound.user_repository import UserRepository
from infrastructure.persistence.repository.jpa_user_repository import JpaUserRepository

dependency = BindingConfig()

dependency.scan(
    "application.usecase",
    "infrastructure.persistence.repository",
    "api.rest",
)

dependency.bind({
    UserRepository: JpaUserRepository,
})
```

---

## Bước 7 — Cấu hình Routing

```python
# app/config/routing.py
from xime.adapters.web.routing import configure_controllers

configure_controllers("api.rest")
```

---

## Bước 8 — Runtime Configuration

```yaml
# app/resources/application.yml
server:
  host: 0.0.0.0
  port: 8080
```

---

## Bước 9 — Entry Point

```python
# app/main.py
from xime import Application
from xime.adapters.web import WebAdapter

application = Application()
app = WebAdapter(application).build()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
```

---

## Bước 10 — Chạy ứng dụng

```bash
python app/main.py
```

Vào `http://localhost:8080/docs` để xem Swagger UI được tạo tự động.

---

## Chuyện gì vừa xảy ra?

Khi `Application` khởi động:

1. Import `config/dependency.py`, đọc biến `dependency`
2. Quét `application.usecase`, `infrastructure.persistence.repository`, `api.rest`
3. Tìm thấy `GetUserUseCase`, `JpaUserRepository`, `UserController`
4. Giải quyết: `UserController → GetUserUseCase → UserRepository`
5. Kiểm tra binding: `UserRepository → JpaUserRepository` ✓
6. Tạo singleton theo thứ tự dependency
7. `WebAdapter` đăng ký method của `UserController` thành route FastAPI

Tất cả điều này xảy ra trước request đầu tiên. Nếu có gì sai, bạn nhận được lỗi rõ ràng ngay lúc startup.

---

## Ví dụ lỗi startup

Thiếu implementation binding:

```
No Implementation Found
  Interface: UserRepository
  Hint: declare dependency.bind({UserRepository: YourImpl}) in config/dependency.py
```

Circular dependency:

```
Circular dependency detected:
  UserService → AuthService → TokenService → UserService
```

Thiếu type hint:

```
Missing Type Hint
  Class: GetUserUseCase
  Parameter: repository
  Hint: add a type annotation — def __init__(self, repository: UserRepository)
```

---

## Bước tiếp theo

- [Khái niệm cốt lõi](core-concepts.md) — hiểu DI, interface binding, scope
- [Routing](routing.md) — các pattern controller nâng cao
- [Transaction](transaction.md) — quản lý transaction database
- [Starters](starters.md) — thêm SQLAlchemy, JWT, Scheduler
