# Cấu hình

[English](../en/configuration.md) | **Tiếng Việt**

[← Khái niệm cốt lõi](core-concepts.md) · **3/9 — Cấu hình** · [Routing →](routing.md)

---

XIME dùng mô hình cấu hình hai tầng được thiết kế cho hai đối tượng khác nhau: developer và operator.

---

## Tầng 1 — Framework Configuration (Developer)

Framework configuration được viết bằng Python. Nó khai báo cách XIME hoạt động: package nào cần scan, interface ánh xạ đến implementation nào, route nào cần expose.

Vị trí: `app/config/`

```text
config/
├── dependency.py   ← DI: scan + bind
├── routing.py      ← đăng ký controller
└── security.py     ← cấu hình security
```

### `config/dependency.py`

File cấu hình DI trung tâm. XIME tự tìm nó lúc startup theo thứ tự: `{main_package}.config.dependency` trước (ví dụ `app.config.dependency` khi chạy `python -m app.main`), rồi fallback về `config.dependency`.

```python
from xime import BindingConfig
from application.port.outbound.user_repository import UserRepository
from infrastructure.persistence.repository.jpa_user_repository import JpaUserRepository

dependency = BindingConfig()

# Khai báo package nào cần scan để tìm class được DI quản lý
dependency.scan(
    "application.usecase",
    "application.service",
    "infrastructure.persistence.repository",
    "infrastructure.client",
    "api.rest",
)

# Bind tường minh Protocol interface đến implementation
dependency.bind({
    UserRepository: JpaUserRepository,
})
```

Tên biến `dependency` là convention mà XIME tìm kiếm. Bạn cũng có thể truyền `BindingConfig` trực tiếp vào `Application`:

```python
app = Application(binding=my_custom_binding)
```

### `config/routing.py`

Khai báo package nào chứa controller:

```python
from xime.adapters.web.routing import configure_controllers

configure_controllers("api.rest")
```

`configure_controllers()` lưu package vào module-level registry. `WebAdapter` đọc registry này khi build FastAPI app.

### `config/security.py`

Cấu hình liên quan đến security (xác thực, quy tắc phân quyền). Chi tiết phụ thuộc vào tính năng security bạn dùng.

---

## Tầng 2 — Runtime Configuration (Operator)

Runtime configuration là YAML. Nó chứa giá trị theo môi trường: host, port, secret, database URL.

Vị trí: `app/resources/`

```text
resources/
├── application.yml          ← base config (luôn được nạp)
├── application-dev.yml      ← override cho dev (khi XIME_ENV=dev)
├── application-prod.yml     ← override cho prod (khi XIME_ENV=prod)
└── application-test.yml     ← override cho test (khi XIME_ENV=test)
```

### Base Config

```yaml
# resources/application.yml
server:
  host: 0.0.0.0
  port: 8080

database:
  host: localhost
  port: 5432
  name: mydb

redis:
  host: localhost
  port: 6379
```

### Environment Override

```yaml
# resources/application-prod.yml
server:
  port: 443

database:
  host: prod-db.internal
```

File env-specific được **merge** lên base file. Key không có trong env file giữ nguyên giá trị base.

### Môi trường hoạt động

Set môi trường bằng env var trước khi khởi động:

```bash
XIME_ENV=prod python -m app.main
# hoặc
APP_ENV=prod python -m app.main
```

XIME kiểm tra `XIME_ENV` trước, sau đó fallback về `APP_ENV`. Mặc định là `dev` nếu không set.

### Logging

Python mặc định để root logger ở mức `WARNING` và không gắn handler, nên mọi log `INFO` (kể cả thông điệp startup của chính framework) đều bị nuốt - app chạy đúng nhưng im lặng, dễ tưởng bị treo.

Để tránh điều này, XIME tự cấu hình root logger lúc bootstrap, đọc khối `logging:` (tùy chọn) trong `application.yml`:

```yaml
logging:
  enabled: true        # đặt false để framework không đụng tới logging
  level: INFO          # DEBUG / INFO / WARNING / ERROR ... (không phân biệt hoa thường)
  format: "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
  datefmt: "%H:%M:%S"
```

Toàn bộ khối là tùy chọn - không khai báo thì dùng mặc định ở trên (enabled, `INFO`).

**Quy tắc an toàn:** framework **chỉ** cấu hình khi `enabled: true` **và** root logger chưa có handler nào. Nếu app tự gọi `logging.basicConfig`/`dictConfig` (hoặc chạy dưới một harness đã cấu hình logging như pytest), framework **không** ghi đè - setup của app luôn được ưu tiên. Muốn tự lo hoàn toàn thì đặt `enabled: false`.

### Tùy chọn DI

```yaml
xime:
  di:
    dynamic-binding: false   # mặc định; đặt true để bật đổi implementation lúc runtime
```

`xime.di.dynamic-binding` bật [dynamic interface binding](core-concepts.md#41-dynamic-binding-nhiều-implementation): khi value của `bind` là một tuple implementation, bật cờ này khiến mọi impl thành singleton eager, inject một proxy trong suốt vào consumer, và cho phép một `Switcher` đổi interface toàn cục lúc runtime. Mặc định tắt - khi đó tuple binding hành xử y hệt bind riêng phần tử đầu.

---

## Truy cập Runtime Config trong Code

Inject `RuntimeConfig` như dependency:

```python
from xime.core.config import RuntimeConfig

class DatabasePool:
    def __init__(self, config: RuntimeConfig) -> None:
        self._host = config.get("database.host")
        self._port = config.get("database.port", default=5432)
```

Key lồng nhau dùng dấu chấm.

---

## Config Discovery — Tường minh, không Magic

XIME **không tự scan** file config. Mọi config source phải được:

1. Truyền trực tiếp vào `Application(binding=...)`, hoặc
2. Import tường minh bằng lời gọi `configure_*()`

Điều này làm bề mặt cấu hình rõ ràng và dễ debug. Nếu config không được áp dụng, bạn có thể trace chính xác nơi nó nên được đăng ký.

```python
# SAI — XIME sẽ không tìm thấy cái này
class WebConfig:
    openapi_title = "My Service"

# ĐÚNG — đăng ký tường minh
from xime.adapters.web.openapi import configure_openapi, OpenApiConfig

configure_openapi(OpenApiConfig(
    title="My Service",
    version="1.0.0",
))
```

---

## Cấu hình OpenAPI

```python
# config/openapi.py  (được import từ main.py hoặc routing.py)
from xime.adapters.web.openapi import configure_openapi, OpenApiConfig, JwtBearer

configure_openapi(OpenApiConfig(
    title="User Service",
    version="1.0.0",
    description="Quản lý tài khoản người dùng",
    security=JwtBearer(),
    public_paths=["/auth/login", "/health"],
))
```

---

## Truyền Config vào Application

Thư mục resources hoặc config module tùy chỉnh:

```python
app = Application(
    resources_dir="conf",              # mặc định: "resources"
    config_module="infra.di_config",   # mặc định: None (tự detect từ package của __main__)
)
```

---

[← Khái niệm cốt lõi](core-concepts.md) · **3/9 — Cấu hình** · [Routing →](routing.md)
