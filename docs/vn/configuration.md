# Cấu hình

[English](../en/configuration.md) | **Tiếng Việt**

[← Khái niệm cốt lõi](core-concepts.md) · **3/9 - Cấu hình** · [Routing →](routing.md)

---

XIME dùng mô hình cấu hình hai tầng được thiết kế cho hai đối tượng khác nhau: developer và operator.

---

## Tầng 1 - Framework Configuration (Developer)

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
    "my_service.application.usecase",
    "my_service.application.service",
    "my_service.infrastructure.persistence.repository",
    "my_service.infrastructure.client",
    "my_service.api.rest",
)

# Bind tường minh Protocol interface đến implementation
dependency.bind({
    UserRepository: JpaUserRepository,
})
```

Scanner tự bỏ qua module có đoạn đường dẫn là `domain`, `dto`, `entity`, `vo`, `constant`,
`exception`. Đó là **mặc định, không phải luật** - khai lại bằng `dependency.exclude_segments(...)`,
kể cả khai rỗng để không loại gì. ⚠ Không gọi và gọi rỗng là hai chuyện khác nhau; chi tiết
ở [core-concepts.md](core-concepts.md) mục 2.

Tên biến `dependency` là convention mà XIME tìm kiếm. Bạn cũng có thể truyền `BindingConfig` trực tiếp vào `Application`:

```python
app = Application(binding=my_custom_binding)
```

### `config/web.py`

Khai báo package nào chứa controller:

```python
from xime.adapters.web.routing import configure_controllers

configure_controllers("my_service.api.rest")
```

`configure_controllers()` lưu package vào module-level registry. `WebAdapter` đọc registry này khi build FastAPI app.

### `config/security.py`

Cấu hình liên quan đến security (xác thực, quy tắc phân quyền). Chi tiết phụ thuộc vào tính năng security bạn dùng.

---

## Tầng 2 - Runtime Configuration (Operator)

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

## Config Discovery - Tường minh, không Magic

XIME **không tự scan** file config. Mọi config source phải được:

1. Truyền trực tiếp vào `Application(binding=...)`, hoặc
2. Import tường minh bằng lời gọi `configure_*()`

Điều này làm bề mặt cấu hình rõ ràng và dễ debug. Nếu config không được áp dụng, bạn có thể trace chính xác nơi nó nên được đăng ký.

```python
# SAI - XIME sẽ không tìm thấy cái này
class WebConfig:
    openapi_title = "My Service"

# ĐÚNG - đăng ký tường minh
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

`configure_openapi()` nói tài liệu **nằm ở đâu**. Việc có phục vụ nó hay không thì
do một công tắc khác quyết, xem ngay dưới.

---

## `xime.dev` - một công tắc cho mọi thứ chỉ dành cho môi trường phát triển

```yaml
# resources/application-local.yml
xime:
  dev: true
```

**Mặc định TẮT, muốn thì phải bật lên.** Hôm nay nó quyết định đúng một chuyện, và
là chuyện hay bị quên nhất khi lên production:

| | `xime.dev` tắt (mặc định) | bật |
|---|---|---|
| `/docs`, `/redoc`, `/openapi.json` | không tồn tại, trả 404 | phục vụ như thường |

Schema OpenAPI là bản đồ đầy đủ của API: mọi đường dẫn, mọi tham số, mọi tên
trường, mọi mã lỗi. Mở cho bất kỳ ai chạm được cổng là rút giai đoạn thăm dò xuống
gần bằng không, nên nó không nên có mặt ở production. FastAPI mặc định phục vụ cả
ba; **Xime thì không, và chỗ khác nhau đó là cố ý.**

Dòng log khởi động luôn khai đang ở trạng thái nào, nên bạn không bao giờ phải đoán:

```text
web default: API docs off - set xime.dev: true to serve them
web default: API docs EXPOSED at /docs, /redoc, /openapi.json (xime.dev is on)
```

Dòng thứ hai xuất hiện trong log production nghĩa là công tắc dev đã đi theo bản
triển khai tới chỗ nó không nên tới.

> ### Giấu `/docs` sau xác thực KHÔNG phải đường thay thế
>
> Swagger UI là một trang mở bằng **trình duyệt**, mà trình duyệt không gắn header
> `Authorization` khi bạn gõ URL. Bỏ `/docs` ra khỏi `public_paths` là trả 401 cho
> đúng người muốn đọc nó. Lựa chọn thật không phải *"công khai hay sau đăng nhập"*
> mà là **bật ở dev, tắt ở production** - đúng việc công tắc này làm.

`xime init` ghi sẵn `dev: true` vào `resources/application.yml`, file mà `.gitignore`
nó sinh ra đã giữ lại ngoài git. Bản `application.yml.example` đi theo git thì không
có dòng đó.

Code của bạn cần biết mình đang ở dev hay không thì hỏi cùng một chỗ, đừng đọc khoá
bằng tay - hai chỗ cùng quyết định một thứ thì sớm muộn lệch nhau:

```python
from xime.core.config import DEV_KEY, is_dev_mode

if is_dev_mode(config):        # config: RuntimeConfig
    ...
print(DEV_KEY)                 # "xime.dev"
```

Thứ gì không phải một `RuntimeConfig` thật thì `is_dev_mode` trả `False` - fail-closed
có chủ ý, vì *"tôi không đọc được cấu hình"* không bao giờ được ra thành *"đang ở dev,
cứ mở ra đi"*. Giá trị không phải boolean nhận dạng được thì **nổ lúc khởi động** chứ
không đoán.

⚠ Ba trường `docs_url`, `redoc_url`, `openapi_url` của `OpenApiConfig` là **đường
dẫn**, không phải công tắc: chúng chỉ được đọc sau khi `xime.dev` đã trả lời có.
Đặt `openapi_url=None` là tắt cả ba, vì cả Swagger UI lẫn ReDoc đều tải schema từ
đó bằng trình duyệt.

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

[← Khái niệm cốt lõi](core-concepts.md) · **3/9 - Cấu hình** · [Routing →](routing.md)
