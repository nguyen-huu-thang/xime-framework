# Cấu hình

[English](../en/configuration.md) | **Tiếng Việt**

XIME dùng mô hình cấu hình hai tầng được thiết kế cho hai đối tượng khác nhau: developer và operator.

---

## Tầng 1 — Framework Configuration (Developer)

Framework configuration được viết bằng Python. Nó khai báo cách XIME hoạt động: package nào cần scan, interface ánh xạ đến implementation nào, route nào cần expose.

Vị trí: `app/config/`

```
config/
├── dependency.py   ← DI: scan + bind
├── routing.py      ← đăng ký controller
└── security.py     ← cấu hình security
```

### `config/dependency.py`

File cấu hình DI trung tâm. XIME tự tìm nó lúc startup từ `config.dependency`.

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

```
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
XIME_ENV=prod python app/main.py
# hoặc
APP_ENV=prod python app/main.py
```

XIME kiểm tra `XIME_ENV` trước, sau đó fallback về `APP_ENV`. Mặc định là `dev` nếu không set.

---

## Truy cập Runtime Config trong Code

Inject `RuntimeConfig` như dependency:

```python
from xime.config import RuntimeConfig

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
    config_module="infra.di_config",   # mặc định: "config.dependency"
)
```
