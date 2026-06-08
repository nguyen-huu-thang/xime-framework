# Kế hoạch triển khai — 2 tính năng mới

> Trạng thái: `[ ]` chưa làm · `[x]` đã xong · `[~]` đang làm

---

## Phần 1 — Multi-server (nhiều WebAdapter / GrpcAdapter)

### Tổng quan thiết kế

```
app.use(WebAdapter())                              # server_id="default", host/port từ config
app.use(WebAdapter("admin", "0.0.0.0", 8081))     # server_id="admin",   host/port bắt buộc

app.use(GrpcAdapter())                             # server_id="default", port từ config
app.use(GrpcAdapter("internal", "0.0.0.0", 50052)) # server_id="internal", port bắt buộc
```

Controller / servicer khai báo mình thuộc server nào:
```python
class AdminController:
    prefix = "/admin"
    server_id = "admin"     # ghi tường minh

class PublicController:
    prefix = "/api/v1"
    # không ghi → mặc định "default"
```

Quy tắc:
- Không có `server_id` hoặc `server_id = "default"` → thuộc server default
- Không được có 2 adapter cùng loại trùng `server_id`
- Adapter non-default bắt buộc phải truyền `host` và `port` vào constructor
- Adapter default vẫn đọc host/port từ `application.yml` như cũ

---

### Bước 1.1 — [x] WebAdapter: thêm `server_id`, `host`, `port` bắt buộc cho non-default

**File:** `xime/adapters/web/_adapter.py`

Thay đổi `__init__`:
```python
# Trước:
def __init__(self, host=None, port=None)

# Sau:
def __init__(self, server_id: str = "default", host: str | None = None, port: int | None = None)
```

Validate trong `__init__`: nếu `server_id != "default"` mà thiếu `host` hoặc `port` → raise `ValueError` ngay.

Lưu `self._server_id = server_id`.

Trong `start()`: nếu là default thì đọc host/port từ runtime config như cũ; nếu non-default thì dùng giá trị từ constructor.

**Trạng thái:** `[x]`

---

### Bước 1.2 — WebAdapter: lọc controller theo `server_id`

**File:** `xime/adapters/web/_adapter.py` — method `_register_controllers()`

Hiện tại scan tất cả controller rồi đăng ký hết. Thêm bước lọc:

```python
cls_server_id = getattr(cls, 'server_id', 'default')
if cls_server_id != self._server_id:
    continue
```

Không cần sửa `ControllerScanner` — scanner vẫn trả về tất cả, adapter tự lọc.

**Trạng thái:** `[x]`

---

### Bước 1.3 — `_WebRegistry`: hỗ trợ nhiều OpenAPI config theo `server_id`

**File:** `xime/adapters/web/_registry.py`

Thay đổi từ lưu một config → dict keyed by server_id:
```python
# Trước:
_openapi: OpenApiConfig | None = None

# Sau:
_openapi: dict[str, OpenApiConfig] = {}

def set_openapi(self, config: OpenApiConfig, server_id: str = "default") -> None: ...
def get_openapi(self, server_id: str = "default") -> OpenApiConfig | None: ...
```

**Trạng thái:** `[x]`

---

### Bước 1.4 — `configure_openapi()`: thêm tham số `server_id`

**Files:** `xime/adapters/web/openapi/__init__.py`

```python
# Trước:
def configure_openapi(config: OpenApiConfig) -> None

# Sau:
def configure_openapi(config: OpenApiConfig, server_id: str = "default") -> None
```

Backward compatible: không truyền `server_id` → vẫn hoạt động như cũ.

**Trạng thái:** `[x]`

---

### Bước 1.5 — WebAdapter đọc OpenAPI config đúng server

**File:** `xime/adapters/web/_adapter.py` — method `build_app()`

Thay:
```python
# Trước:
openapi_config = registry.get_openapi()

# Sau:
openapi_config = registry.get_openapi(self._server_id)
```

**Trạng thái:** `[x]`

---

### Bước 1.6 — GrpcAdapter: thêm `server_id`, validate non-default

**File:** `xime/adapters/grpc/_adapter.py`

Tương tự Bước 1.1 nhưng cho gRPC:
```python
def __init__(self, server_id: str = "default", host: str | None = None, port: int | None = None)
```

Validate: non-default mà thiếu port → raise `ValueError`.

Trong `start()`: default đọc port từ `GrpcServerConfig.from_runtime()`; non-default dùng port từ constructor.

**Trạng thái:** `[x]`

---

### Bước 1.7 — GrpcAdapter: lọc servicer theo `server_id`

**File:** `xime/adapters/grpc/routing/_builder.py`

Trong `register_all()`, thêm bước lọc binding theo `server_id` của servicer class:

```python
cls_server_id = getattr(handler_cls, 'server_id', 'default')
if cls_server_id != self._server_id:
    continue
```

`GrpcServiceBuilder` cần nhận `server_id` từ `GrpcAdapter` khi được tạo.

**Trạng thái:** `[x]`

---

### Bước 1.8 — Validation trong `Application.use()`

**File:** `xime/core/bootstrap/application.py`

Khi gọi `app.use(adapter)`, validate ngay:
- Nếu đã có adapter cùng loại (`WebAdapter`/`GrpcAdapter`) với cùng `server_id` → raise rõ ràng:

```
Duplicate WebAdapter id: "default"
Already registered: WebAdapter(server_id="default")
```

- Port conflict: nếu `host` và `port` được truyền tường minh (non-default) thì kiểm tra trùng port ngay tại `use()`. Port của default adapter không kiểm tra được lúc này (chưa load config) — bỏ qua.

**Trạng thái:** `[x]`

---

### Bước 1.9 — Tests

Kiểm tra:
- `WebAdapter()` vẫn chạy như cũ (backward compatible)
- `GrpcAdapter()` vẫn chạy như cũ
- Controller không có `server_id` → thuộc default server
- Controller có `server_id = "admin"` → chỉ đăng ký vào `WebAdapter("admin", ...)`
- Duplicate `server_id` → lỗi rõ ràng tại `app.use()`
- Non-default adapter không truyền port → lỗi rõ ràng

**Trạng thái:** `[x]`

---

## Phần 2 — `dependency.order()` (thứ tự post_construct)

### Tổng quan thiết kế

Tương đương `@DependsOn` của Spring Boot, khai báo trong config file:

```python
# app/config/dependency.py

dependency.order(
    [TrustSelfCertificateLoader, GrpcExternalServerCredentialsProvider],
    [DatabasePool, UserRepository, UserService],
)
```

Nghĩa:
- `[A, B, C]` → A.post_construct() xong → B.post_construct() xong → C.post_construct()
- Mỗi list là một chuỗi thứ tự
- Nhiều list = nhiều chuỗi, framework gộp lại thành một đồ thị tổng

Quy tắc:
- Tất cả class trong rules phải có trong DI container → không thì startup thất bại
- Không được có cycle trong rules (kể cả cycle chéo giữa các list)
- Không được mâu thuẫn với thứ tự constructor dependency

---

### Bước 2.1 — `BindingConfig`: thêm `order()` method

**File:** `xime/core/config/binding.py`

Thêm field và method:
```python
self._order_rules: list[list[type]] = []

def order(self, *rules: list[type]) -> None:
    """
    Khai báo thứ tự gọi post_construct() cho các class không có
    constructor dependency trực tiếp với nhau.

    Tương đương @DependsOn trong Spring Boot, nhưng khai báo
    tập trung trong config file thay vì annotation trên class.

    Mỗi list là một chuỗi thứ tự:
        [A, B, C] → A.post_construct() chạy xong trước B,
                    B.post_construct() chạy xong trước C.

    Có thể gọi nhiều lần hoặc truyền nhiều list cùng lúc:
        dependency.order(
            [TrustLoader, CredentialsProvider],
            [DatabasePool, UserRepo, UserService],
        )

    Framework kiểm tra tại startup:
    - Mọi class phải có trong DI container
    - Không được có cycle (kể cả chéo giữa các list)
    - Không được mâu thuẫn với thứ tự constructor dependency
    """
    self._order_rules.extend(rules)
```

Thêm property `order_rules`:
```python
@property
def order_rules(self) -> tuple[list[type], ...]:
    return tuple(self._order_rules)
```

**Trạng thái:** `[x]`

---

### Bước 2.2 — `DependencyGraph`: thêm method sort có rules

**File:** `xime/core/container/graph.py`

Thêm method `topological_order_with_rules()`:

```python
def topological_order_with_rules(
    self,
    rules: list[list[type]],
) -> list[type]:
```

Logic:
1. Trích xuất các cặp (A, B) từ mỗi rule list: `[A, B, C]` → `(A→B)`, `(B→C)` nghĩa là "A phải trước B"
2. Validate: mọi class trong rules phải có trong `self._nodes` → nếu không → raise với tên class cụ thể
3. Gộp rule edges vào `_edges` (tạo bản copy, không sửa gốc)
4. Chạy lại Kahn's algorithm trên đồ thị kết hợp
5. Nếu cycle → raise `StartupException` với thông báo rõ ràng:

```
Initialization Order Conflict

Declared rule creates a cycle:
  TrustLoader → CredentialsProvider → TrustLoader

Check dependency.order() in config/dependency.py
```

**Trạng thái:** `[x]`

---

### Bước 2.3 — `XimeContainer`: dùng order rules khi build

**File:** `xime/core/container/__init__.py`

Thêm field và method:
```python
self._order_rules: list[list[type]] = []

def order(self, *rules: list[type]) -> "XimeContainer":
    """Khai báo thứ tự post_construct(). Xem BindingConfig.order() để biết chi tiết."""
    self._guard_not_built("order")
    self._order_rules.extend(rules)
    return self
```

Trong `build()`, sau khi có `graph`, thay:
```python
# Trước:
self._topological_order = graph.topological_order()

# Sau:
self._topological_order = graph.topological_order_with_rules(self._order_rules)
```

**Trạng thái:** `[x]`

---

### Bước 2.4 — `StartupOrchestrator`: truyền order rules vào container

**File:** `xime/core/bootstrap/orchestrator.py`

Trong `start()`, sau `.configure()`, thêm:
```python
container = (
    XimeContainer()
    ...
    .configure(config_cls)  # đã có
)
# Thêm:
if self._binding.order_rules:
    container.order(*self._binding.order_rules)

self._container = container.build()
```

**Trạng thái:** `[x]`

---

### Bước 2.5 — Tests

Kiểm tra:
- `dependency.order([A, B])` → B.post_construct() chạy sau A
- Cycle trong rules → lỗi rõ ràng với tên class và rule gây ra
- Class không trong DI container → lỗi rõ ràng
- Conflict với constructor dep (A phụ thuộc B trong constructor, rule khai báo [A, B] → hợp lệ; rule khai báo [B, A] khi B phụ thuộc A → cycle → lỗi)
- Nhiều list rules không xung đột → chạy đúng thứ tự

**Trạng thái:** `[x]`

---

## Thứ tự triển khai gợi ý

Hai phần độc lập, có thể làm theo thứ tự nào cũng được. Gợi ý:

1. Phần 2 trước — ít file hơn, logic gọn hơn, dễ test độc lập
2. Phần 1 sau — nhiều file hơn, cần test end-to-end nhiều hơn
