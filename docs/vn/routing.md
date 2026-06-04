# Routing

[English](../en/routing.md) | **Tiếng Việt**

[← Cấu hình](configuration.md) · **4/9 — Routing** · [Transaction →](transaction.md)

---

XIME dùng class-based controller. Controller là DI singleton có các method được tự động đăng ký thành FastAPI route.

---

## Controller cơ bản

```python
# app/api/rest/user_controller.py
from pydantic import BaseModel
from xime.adapters.web.routing import get, post, put, delete

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

class CreateUserRequest(BaseModel):
    name: str
    email: str

class UserController:
    prefix = "/users"
    tags = ["users"]

    def __init__(self, use_case: UserUseCase) -> None:
        self._use_case = use_case

    @get("/{user_id}", response_model=UserResponse)
    async def get_user(self, user_id: int) -> UserResponse:
        return await self._use_case.get(user_id)

    @post("", response_model=UserResponse, status_code=201)
    async def create_user(self, body: CreateUserRequest) -> UserResponse:
        return await self._use_case.create(body)

    @put("/{user_id}", response_model=UserResponse)
    async def update_user(self, user_id: int, body: CreateUserRequest) -> UserResponse:
        return await self._use_case.update(user_id, body)

    @delete("/{user_id}", status_code=204)
    async def delete_user(self, user_id: int) -> None:
        await self._use_case.delete(user_id)
```

---

## Route Decorator

| Decorator | HTTP Method |
|---|---|
| `@get(path, ...)` | GET |
| `@post(path, ...)` | POST |
| `@put(path, ...)` | PUT |
| `@patch(path, ...)` | PATCH |
| `@delete(path, ...)` | DELETE |

Tất cả decorator nhận các tham số của `add_api_route()` trong FastAPI:

```python
@get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Lấy user theo ID",
    tags=["users"],
    status_code=200,
    deprecated=False,
)
async def get_user(self, user_id: int) -> UserResponse:
    ...
```

---

## Đăng ký Controller

Khai báo package controller trong `config/routing.py`:

```python
# config/routing.py
from xime.adapters.web.routing import configure_controllers

configure_controllers("api.rest")
configure_controllers("api.internal")  # hỗ trợ nhiều package
```

Controller cũng phải có trong danh sách DI scan:

```python
# config/dependency.py
dependency.scan("api.rest", "api.internal", ...)
```

**Lưu ý:** yêu cầu khai báo package ở cả hai chỗ là hạn chế đã biết. Phiên bản tương lai có thể cho phép `configure_controllers()` tự thêm vào DI scan.

---

## Điều gì làm một Class thành Controller?

Một class trở thành controller khi:

1. Có ít nhất một method được đánh dấu bằng `@get`, `@post`, `@put`, `@patch`, hoặc `@delete`
2. Package của nó được đăng ký qua `configure_controllers()`

Không có annotation `@Controller`. Decorator trên method là tín hiệu.

---

## Cách đăng ký Route hoạt động

XIME đăng ký route **sau** khi tất cả singleton được tạo, bên trong FastAPI lifespan:

```
WebAdapter.build() → tạo FastAPI app với lifespan
[uvicorn khởi động]
  lifespan bắt đầu
  → application.start()          ← DI build singleton
  → _register_controllers()
      → scan controller class
      → lấy instance từ DI container
      → build FastAPI route
      → app.include_router(router)
  → yield                        ← server nhận request
```

Thứ tự này quan trọng: instance controller chỉ tồn tại sau khi DI hoàn tất.

---

## Path Parameter

Path parameter được định nghĩa trong path string và khai báo là tham số method với cùng tên:

```python
@get("/{user_id}/orders/{order_id}")
async def get_order(self, user_id: int, order_id: int) -> OrderResponse:
    ...
```

FastAPI suy luận path vs query vs body từ signature method.

---

## Request Body

Pydantic model trong signature method trở thành request body:

```python
class CreateOrderRequest(BaseModel):
    product_id: int
    quantity: int

@post("/{user_id}/orders", response_model=OrderResponse, status_code=201)
async def create_order(self, user_id: int, body: CreateOrderRequest) -> OrderResponse:
    ...
```

---

## Query Parameter

Kiểu đơn giản (str, int, bool) không phải path parameter sẽ trở thành query parameter:

```python
@get("")
async def list_users(self, page: int = 1, size: int = 20, active: bool = True) -> list[UserResponse]:
    ...
```

URL sinh ra: `GET /users?page=2&size=10&active=true`

---

## Controller là DI Singleton

Controller tham gia đầy đủ vào DI. Chúng có thể inject use case, service hay bất kỳ component nào được DI quản lý:

```python
class OrderController:
    prefix = "/orders"

    def __init__(
        self,
        create_order: CreateOrderUseCase,
        get_order: GetOrderUseCase,
        cancel_order: CancelOrderUseCase,
    ) -> None:
        self._create = create_order
        self._get = get_order
        self._cancel = cancel_order
```

---

## Thứ tự Route

Route được đăng ký theo **thứ tự khai báo** trong class (Python 3.7+ dict insertion order). Điều này quan trọng với FastAPI khi path trùng nhau:

```python
@get("/me")          # đăng ký trước — matched trước /{user_id}
async def get_me(self) -> UserResponse: ...

@get("/{user_id}")   # đăng ký sau
async def get_user(self, user_id: int) -> UserResponse: ...
```

---

## Hạn chế đã biết

- **Khai báo hai package** — phải liệt kê trong cả `dependency.scan()` và `configure_controllers()`
- **Exception → HTTP status mapping** — exception chưa được xử lý sẽ trả về 500; chưa có cơ chế map lỗi tùy chỉnh
- **`__all__` không được controller scanner tôn trọng** — tất cả controller class trong package đều được tìm bất kể `__all__`
- **WebSocket và gRPC routing** — chưa trong scope của class-based controller


---

[← Cấu hình](configuration.md) · **4/9 — Routing** · [Transaction →](transaction.md)
