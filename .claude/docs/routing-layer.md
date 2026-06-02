# Thiết kế Routing Layer — Xime Framework

## Vấn đề cần giải quyết

FastAPI có DI riêng dựa trên `Depends()`. Xime có DI riêng dựa trên constructor injection. Nếu không có routing layer, developer phải tự kéo service ra tay, phá vỡ triết lý DI:

```python
# Cách cũ — SAI về kiến trúc
@fastapi_app.get("/users")
async def get_users():
    service = app_instance.get(UserService)  # bypass DI
    return await service.get_all()
```

Routing layer tạo cầu nối: controller là **DI singleton** (Xime quản lý), method của nó được đăng ký tự động vào FastAPI router.

---

## Triết lý thiết kế

- **Không dùng decorator trên class**: không có `@Controller`. Class trở thành controller khi có ít nhất một method được đánh dấu `@get/@post/...` và nằm trong package được khai báo qua `configure_controllers()`.
- **Explicit**: developer phải khai báo rõ `configure_controllers("api.rest")`, framework không tự quét codebase.
- **Controller là DI singleton**: inject dependency qua constructor giống service/usecase.
- **Follows `configure_*()` pattern**: nhất quán với `configure_openapi()`, `configure_jwt()`, `configure_scheduler()`.

---

## Cách sử dụng (Developer Experience)

```python
# api/rest/user_controller.py
from xime.adapters.web.routing import get, post, delete

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

    @delete("/{user_id}", status_code=204)
    async def delete_user(self, user_id: int) -> None:
        await self._use_case.delete(user_id)
```

```python
# config/dependency.py
dependency.scan("api.rest", "application.usecase", "infrastructure.repository")

# config/routing.py
from xime.adapters.web.routing import configure_controllers
configure_controllers("api.rest")

# main.py
from xime.adapters.web import WebAdapter
from core.bootstrap import Application

application = Application()
app = WebAdapter(application).build()
```

---

## Các thành phần

### `_decorators.py` — Route Decorators

Đính kèm metadata vào method, không register route tại thời điểm định nghĩa class (khác Flask). Metadata là `RouteInfo` dataclass với HTTP method, path, status_code, response_model, và các tham số OpenAPI đầy đủ.

```python
ROUTE_ATTR = "_xime_route_info"

@dataclass
class RouteInfo:
    method: str
    path: str
    status_code: int = 200
    response_model: Any = None
    summary: str | None = None
    # ... các tham số FastAPI add_api_route() khác
```

### `_config.py` — Controller Registry

Module-level singleton, lưu danh sách package từ `configure_controllers()`. WebAdapter đọc khi startup.

### `_scanner.py` — Controller Scanner

Walk toàn bộ submodule trong package, tìm class có ít nhất một method với attribute `_xime_route_info`. **Chỉ trả về `type` (class), không tạo instance.** Instance được lấy từ DI container ở bước sau.

### `_builder.py` — Route Builder (phần kỹ thuật quan trọng nhất)

**Vấn đề**: FastAPI dùng `inspect.signature()` để biết tham số nào là path param, body, query param. Nếu pass raw method vào FastAPI có edge cases.

**Giải pháp — `_make_handler(bound_method)`**: tạo wrapper function với `__signature__` rõ ràng:

```python
def _make_handler(bound_method):
    original_sig = inspect.signature(bound_method)  # 'self' đã được bind → không có trong sig

    @functools.wraps(bound_method)
    async def handler(**kwargs):
        return await bound_method(**kwargs)

    handler.__signature__ = original_sig  # bắt buộc — functools.wraps không copy signature
    return handler
```

`inspect.signature(bound_method)` trả về signature **không có `self`** (đã bind). Gán `__signature__` tường minh vì `functools.wraps` copy `__wrapped__` và annotations nhưng **không copy signature object**.

**Thứ tự route**: dùng `vars() + reversed(cls.__mro__)` thay vì `inspect.getmembers()`. Lý do: `getmembers()` trả về alphabetical order, trong khi `vars()` giữ thứ tự khai báo (Python 3.7+ dict là insertion-ordered).

---

## Startup sequence trong WebAdapter

```
WebAdapter.build() → tạo FastAPI app với lifespan

[uvicorn start]
  → lifespan bắt đầu
  → application.start()         ← DI build xong, singletons sẵn sàng
  → _register_controllers()     ← scanner + builder chạy ở đây
      → scanner tìm controller classes
      → lấy instance từ DI container
      → builder tạo APIRouter
      → app.include_router(router)
  → yield                       ← server bắt đầu nhận request
```

Phải đăng ký sau `application.start()` vì controller instance chỉ tồn tại sau khi DI container build xong. FastAPI chấp nhận route thêm trong lifespan vì schema được generate lazily (trước request đầu tiên).

---

## Cấu trúc file

```
adapters/web/routing/
├── __init__.py          ← public API: get, post, put, patch, delete, configure_controllers
├── _decorators.py       ← RouteInfo, @get/@post/...
├── _config.py           ← _ControllerRegistry, configure_controllers()
├── _scanner.py          ← ControllerScanner.find_controllers()
└── _builder.py          ← RouteBuilder.build(), _make_handler()
```

`adapters/web/__init__.py` re-export thêm `configure_controllers` và decorators.

---

## Giới hạn đã biết / Tính năng tương lai

**Hai lần khai báo package** — hiện tại phải gọi cả `dependency.scan("api.rest")` và `configure_controllers("api.rest")`. Có thể tối ưu sau để `configure_controllers()` tự thêm vào DI scan, nhưng phiên bản đầu để rõ ràng.

**Exception → HTTP status code mapping** — khi controller raise business exception, FastAPI trả về 500. Cần cơ chế map exception → status code, thiết kế và implement riêng.

**`ControllerScanner` không hỗ trợ `__all__`** — khác với `PackageScanner` trong DI. Minor inconsistency, có thể thêm sau.

**Middleware per-route** — FastAPI hỗ trợ nhưng cần thiết kế thêm.

**Không nằm trong scope này**: gRPC routing, WebSocket routing, request validation error handling, BackgroundTasks (FastAPI tự xử lý).
