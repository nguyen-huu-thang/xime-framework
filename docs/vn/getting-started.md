# Bắt đầu nhanh

[English](../en/getting-started.md) | **Tiếng Việt**

**1/9 - Bắt đầu nhanh** · [Khái niệm cốt lõi →](core-concepts.md)

---

Hướng dẫn này giúp bạn tạo ứng dụng XIME đầu tiên.

---

## Yêu cầu

- Python 3.11+
- Biết cơ bản async/await
- Biết FastAPI sẽ giúp nhưng không bắt buộc

---

## Cài đặt

**Ổn định (khuyến nghị):**

```bash
pip install xime
```

**Mới nhất từ source** (có thể mới hơn phiên bản trên PyPI một chút):

```bash
git clone https://github.com/nguyen-huu-thang/xime-framework
cd xime-framework
pip install -e .
```

---

## Đường ngắn: `xime init`

Framework có sẵn trình tạo dự án. Ba lệnh là có một ứng dụng chạy được:

```bash
xime init my-service
cd my-service
python main.py
```

Nó sinh ra đúng bố cục mà bài này dạy, kèm một route `/ping` để bạn xoá đi. Phần còn lại của
bài dựng tay từng file trên **cùng bố cục đó**, để bạn thấy rõ mỗi mảnh ghép làm gì.

---

## Cấu trúc dự án

Một ứng dụng XIME tối thiểu chỉ cần một file:

```text
my-service/
└── main.py
```

Nên có thêm `config/` để cấu hình DI:

```text
my-service/
├── main.py
└── config/
    ├── __init__.py
    └── dependency.py
```

Cấu trúc đầy đủ khuyến nghị cho microservice:

```text
my-service/
├── main.py                     ← điểm vào, nằm ở GỐC
├── config/                     ← cấu hình kiến trúc, nằm ở GỐC
│   ├── __init__.py             ← gom mọi thứ phải chạy lúc import
│   ├── dependency.py           ← DI: scan + bind
│   └── web.py                  ← routing, middleware, CORS
├── my_service/                 ← code nghiệp vụ, tên gói theo tên dự án
│   ├── __init__.py
│   ├── api/
│   │   └── user_controller.py
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
│   └── domain/
│       └── user.py
├── resources/                  ← cấu hình vận hành, nằm ở GỐC
│   └── application.yml
└── test/
```

⚠ **Ba thứ `main.py`, `config/`, `resources/` nằm ở GỐC dự án, không nằm trong gói nghiệp
vụ.** Framework tìm `resources/application.yml` theo đường dẫn **tương đối với thư mục bạn
chạy lệnh**, mà lệnh chạy là `python main.py` từ gốc. Để nhầm nó vào trong gói thì file **bị
bỏ qua im lặng**: app vẫn khởi động, chạy bằng giá trị mặc định của framework, và không có gì
báo.

⚠ **Tên gói nghiệp vụ (`my_service`) là của bạn, framework không ép.** Nhưng nó phải khớp với
đường dẫn bạn viết trong `dependency.scan()` và `configure_controllers()`. `xime init` lấy tên
dự án rồi đổi dấu `-` thành `_`.

---

## Bước 1 - Định nghĩa Domain

```python
# my_service/domain/user.py
from dataclasses import dataclass


@dataclass
class User:
    id: int
    name: str
    email: str
```

---

## Bước 2 - Định nghĩa Interface (Protocol)

```python
# my_service/application/port/outbound/user_repository.py
from typing import Protocol

from my_service.domain.user import User


class UserRepository(Protocol):
    async def find_by_id(self, user_id: int) -> User | None: ...
```

---

## Bước 3 - Viết Use Case

```python
# my_service/application/usecase/get_user_use_case.py
from my_service.application.port.outbound.user_repository import UserRepository
from my_service.domain.user import User


class GetUserUseCase:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    async def execute(self, user_id: int) -> User | None:
        return await self.repository.find_by_id(user_id)
```

Dependency khai bằng **type hint trong constructor**. Không annotation, không decorator.

---

## Bước 4 - Viết Implementation

```python
# my_service/infrastructure/persistence/repository/jpa_user_repository.py
from my_service.domain.user import User


class JpaUserRepository:
    async def find_by_id(self, user_id: int) -> User | None:
        return User(id=user_id, name="Alice", email="alice@example.com")
```

Không cần kế thừa `UserRepository`. `Protocol` dùng structural typing, và ánh xạ được khai
tường minh ở bước 6.

---

## Bước 5 - Viết Controller

```python
# my_service/api/user_controller.py
from pydantic import BaseModel
from xime.adapters.web import get

from my_service.application.usecase.get_user_use_case import GetUserUseCase


class UserResponse(BaseModel):
    id: int
    name: str
    email: str


class UserController:
    def __init__(self, get_user: GetUserUseCase):
        self.get_user = get_user

    @get("/users/{user_id}")
    async def get_user_by_id(self, user_id: int) -> UserResponse:
        user = await self.get_user.execute(user_id)
        return UserResponse(id=user.id, name=user.name, email=user.email)
```

Controller cũng là một singleton trong DI container, nên nó nhận use case qua constructor y
như mọi class khác.

---

## Bước 6 - Cấu hình DI

```python
# config/dependency.py
from xime.core.config import BindingConfig

from my_service.application.port.outbound.user_repository import UserRepository
from my_service.infrastructure.persistence.repository.jpa_user_repository import JpaUserRepository

dependency = BindingConfig()

# Quét theo TẦNG, không quét cả cây: một class vào container vì chỗ nó nằm.
dependency.scan(
    "my_service.api",
    "my_service.application.usecase",
    "my_service.infrastructure.persistence.repository",
)

# Interface (Protocol) -> implementation, khai tường minh.
dependency.bind({
    UserRepository: JpaUserRepository,
})
```

Scanner tự bỏ qua module có đoạn đường dẫn là `domain`, `dto`, `entity`, `vo`, `constant`,
`exception` - nên `my_service/domain/` không cần khai gì. Nó cũng bỏ qua `Protocol`, lớp trừu
tượng, và Pydantic `BaseModel`. Mặc định đó **ghi đè được** bằng
`dependency.exclude_segments(...)`; chi tiết ở [Khái niệm cốt lõi](core-concepts.md) mục 2.

---

## Bước 7 - Cấu hình Routing

```python
# config/web.py
from xime.adapters.web import configure_controllers

configure_controllers("my_service.api")
```

Cùng một chuỗi xuất hiện ở hai chỗ, và đó là cố ý: `dependency.scan()` **dựng instance**, còn
`configure_controllers()` nói **chỗ nào chứa controller** để đăng ký route từ những instance
đó. Thêm một file vào `my_service/api/` là nó tự được nhận, không phải sửa dòng nào.

---

## Bước 8 - Gói `config`

```python
# config/__init__.py
from config.dependency import dependency

from config import web  # noqa: F401  - import chạy configure_* lúc khởi động

__all__ = ["dependency"]
```

⭐ **File này không phải cho gọn.** Nó là nơi **khai tường minh mọi thứ phải chạy lúc import**,
và thứ tự viết ra là thứ tự chạy. `configure_controllers`, `configure_cors`, `configure_jwt`,
`configure_grpc_tls`... chỉ có hiệu lực khi module chứa chúng được import, nên chúng phải xuất
hiện ở đây.

⚠ **Đừng dựa vào cơ chế tự dò của các bản cũ.** Nó tìm gói config qua
`__main__.__spec__.parent`, mà giá trị đó **khác ở tiến trình con**: framework đi tìm sai chỗ
rồi **im lặng** dùng một DI rỗng - con khởi động được, không route nào, và không gì báo. Khai
bằng `add_config()` ở bước 10 là cách đúng cho cả một lẫn nhiều tiến trình.

---

## Bước 9 - Runtime Configuration

```yaml
# resources/application.yml
server:
  host: 127.0.0.1
  port: 8080

# Tùy chọn - XIME mặc định cấu hình logging mức INFO; chỉnh hoặc tắt ở đây.
logging:
  level: INFO
```

Xem **mọi khoá** framework hiểu, kèm chú thích và giá trị mặc định:

```bash
xime config --print
```

Logging được cấu hình tự động lúc khởi động nên app in log `INFO` ngay từ đầu. Xem
[Cấu hình → Logging](configuration.md) để biết đầy đủ khối config và quy tắc tắt.

---

## Bước 10 - Entry Point

```python
# main.py
from xime.adapters.web import WebAdapter
from xime.core.bootstrap import Application

import config

app = Application()
app.add_config(config)
app.use(WebAdapter())

if __name__ == "__main__":
    app.run()
```

⭐ **Ba dòng giữa nằm ở MỨC MODULE, không nằm trong `if __name__`.** Ngày bạn chạy nhiều tiến
trình, mỗi tiến trình con **chạy lại chính file này** để dựng lại ứng dụng, và ở đó `__name__`
là `__mp_main__` nên khối `if` không kích hoạt. Đặt `use()` vào trong khối đó thì con có một
ứng dụng không adapter nào và một DI rỗng.

⚠ Đổi lại, **mức module chỉ để KHAI BÁO, không để LÀM**: mọi thứ ngoài `if __name__` chạy
`N+1` lần với `N` tiến trình con. Đừng mở kết nối, đọc file, hay gọi `uuid4()` ở đây. Kiểm
bằng `xime check module-level`. Chi tiết: [Đa tiến trình](multi-process.md).

---

## Bước 11 - Chạy ứng dụng

```bash
python main.py
```

Thử:

```bash
curl http://localhost:8080/users/1
# {"id":1,"name":"Alice","email":"alice@example.com"}
```

Vào `http://localhost:8080/docs` để xem Swagger UI được tạo tự động.

---

## Chuyện gì vừa xảy ra?

Khi `Application` khởi động:

1. Đọc gói `config` bạn truyền qua `add_config()`, lấy biến `dependency`
2. Import `config/web.py` (vì `config/__init__.py` import nó), chạy `configure_controllers`
3. Quét `my_service.api`, `my_service.application.usecase`, `my_service.infrastructure.persistence.repository`
4. Tìm thấy `UserController`, `GetUserUseCase`, `JpaUserRepository`
5. Giải quyết: `UserController → GetUserUseCase → UserRepository`
6. Kiểm tra binding: `UserRepository → JpaUserRepository` ✓
7. Tạo singleton theo thứ tự dependency
8. `WebAdapter` đăng ký method của `UserController` thành route FastAPI

Tất cả điều này xảy ra trước request đầu tiên. Nếu có gì sai, bạn nhận được lỗi rõ ràng ngay
lúc startup.

---

## Ví dụ lỗi startup

Thiếu implementation binding:

```text
No Implementation Found
  Interface: UserRepository
  Hint: declare dependency.bind({UserRepository: YourImpl}) in config/dependency.py
```

Circular dependency:

```text
Circular dependency detected:
  UserService → AuthService → TokenService → UserService
```

Thiếu type hint:

```text
Missing Type Hint
  Class: GetUserUseCase
  Parameter: repository
  Hint: add a type annotation - def __init__(self, repository: UserRepository)
```

---

## Bước tiếp theo

Nhấn link bên dưới để đọc trang tiếp theo.

---

**1/9 - Bắt đầu nhanh** · [Khái niệm cốt lõi →](core-concepts.md)
