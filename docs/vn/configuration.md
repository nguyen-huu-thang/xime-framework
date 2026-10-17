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
webserver:
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
webserver:
  port: 443

database:
  host: prod-db.internal
```

File env-specific được **merge** lên base file. Key không có trong env file giữ nguyên giá trị base.

### HTTPS, reload chứng chỉ và cổng management

```yaml
webserver:
  ssl:
    certfile: /etc/letsencrypt/live/example/fullchain.pem
    keyfile: /etc/letsencrypt/live/example/privkey.pem
    reload:
      mode: both                 # off, watch, api, both
      interval_seconds: 300      # watcher; mặc định 300 giây
  management:
    enabled: true
    host: 127.0.0.1              # chỉ nhận IP loopback, gồm IPv6 loopback
    port: 9180
```

`webserver.ssl` là TLS mặc định cho các web listener. Cặp cert/key được đọc trực tiếp từ file (kể cả symlink Certbot). Khi file mới chưa hợp lệ hoặc cert/key chưa khớp, Xime giữ context cũ và thử lại; kết nối TLS đang mở tiếp tục dùng phiên bản đã bắt tay, còn kết nối mới dùng cert sau khi nạp thành công.

**Tương thích cipher:** trên Uvicorn 0.47.0, phép đo Windows/Python 3.14.8/OpenSSL 3.5.9 cho thấy mặc định `TLSv1` không bắt tay được với client Python mặc định khi ép TLS 1.2; TLS 1.3 vẫn hoạt động. Uvicorn 0.48.0 đổi sang cipher mặc định của OpenSSL và đạt phép đo TLS 1.2 này. Nếu dùng Uvicorn 0.47.0 và cần TLS 1.2, hãy khai `ciphers` phía server (ví dụ `ECDHE+AESGCM`) hoặc nâng Uvicorn; kiểm chứng với các client thực tế của ứng dụng.

`mode: watch` tự dò file trên **mỗi worker đang phục vụ TLS**. `api` tắt watcher và bật đường gọi tức thời; `both` bật cả hai; `off` không tự theo dõi và không mở endpoint HTTP reload. Mặc định 300 giây chỉ là nhịp dự phòng của watcher, không làm chậm hàm hoặc API. Lập trình viên vẫn có thể gọi trực tiếp:

```python
from xime.adapters.web import reload_tls

result = await reload_tls(app, server_id="default")
```

Hàm này không cần cổng management và dùng được cả khi `mode: off`. Mỗi worker đọc file cục bộ; nếu watcher, API hoặc hàm cùng báo một bộ file, khóa và dấu phiên bản trong RAM làm cho mỗi worker chỉ nạp một lần. Dữ liệu chứng chỉ/private key không đi qua `ProcessLink`.

Khi bật `management`, Xime tự thêm một web listener HTTP chỉ trên địa chỉ loopback. Trong `processes:`, listener này là singleton nội bộ: primary hiện tại giữ cổng, và primary mới bind lại cùng cổng sau khi được thăng cấp. Cấu hình `process`/`processes` của ứng dụng không phải thay đổi. Management luôn có `/healthz` và `/readyz` chi tiết; `/tls/reload` chỉ được thêm khi `mode` là `api` hoặc `both`, và nhận `{"server_id":"default"}`.

Certbot deploy hook có thể yêu cầu nạp ngay sau khi gia hạn thành công:

```bash
curl --fail-with-body -X POST http://127.0.0.1:9180/tls/reload \
  -H 'Content-Type: application/json' \
  -d '{"server_id":"default"}'
```

HTTP trả kết quả của từng worker; lỗi hoặc worker không phản hồi làm hook nhận mã lỗi. Bản hiện tại chỉ giới hạn listener vào loopback, chưa thêm xác thực cho API management. Cổng management không dùng cert public, không có controller nghiệp vụ hoặc Swagger.

`management.enabled` mặc định `false`. Khi bật, `port` bắt buộc và `host` phải là IP loopback; API reload yêu cầu management bật. Hai khối `webserver:` và `server:` không được khai đồng thời. `server:` cũ vẫn được chấp nhận làm alias tương thích; `environments.server` vẫn là tên nhánh môi trường riêng.

Các endpoint public `/healthz` và `/readyz` vẫn phải bật riêng bằng `configure_health()`. Thân phản hồi public chỉ có `{"status":"ok"}` hoặc `{"status":"unavailable"}`; báo cáo chi tiết nằm trên cổng management loopback khi được bật.

### Môi trường hoạt động

Set môi trường bằng env var trước khi khởi động:

```bash
XIME_ENV=prod python -m app.main
# hoặc
APP_ENV=prod python -m app.main
```

XIME kiểm tra `XIME_ENV` trước, sau đó fallback về `APP_ENV`. Nếu không set, chỉ `application.yml` được nạp. Cách dùng profile này tiếp tục hỗ trợ các ứng dụng hiện có.

### Chọn local/server trong cùng một file

Khi một ứng dụng cần mang cả hai bộ giá trị trong cùng `application.yml`, khai báo `xime.dev` và hai nhánh `environments`:

```yaml
xime:
  dev: true # true = local; false = server/VPS

webserver:
  port: 8178

environments:
  local:
    webserver:
      host: 0.0.0.0
    database:
      url: postgresql+asyncpg://localhost/my_app
  server:
    webserver:
      host: 127.0.0.1
      ssl:
        certfile: /etc/letsencrypt/live/example/fullchain.pem
        keyfile: /etc/letsencrypt/live/example/privkey.pem
    database:
      url: postgresql+asyncpg://db.internal/my_app
```

Loader merge nhánh được chọn vào khóa chung rồi bỏ khối `environments` khỏi runtime config. Mapping được merge sâu; list ở nhánh được chọn thay list chung. Hai nhánh phải cùng có mặt và là mapping. `xime.dev` phải khai rõ kiểu boolean, không được khai lại bên trong một nhánh. Khối này không kết hợp với `XIME_ENV`/`APP_ENV`; trộn hai bộ chọn sẽ chặn startup. `xime check config` hiện chỉ kiểm cấu trúc nhánh, chưa kiểm schema các khóa framework nằm bên trong overlay. Một lỗi gõ sai TLS trong nhánh có thể khiến HTTPS không được cấu hình mà checker vẫn báo `clean`. Nếu overlay chứa TLS, hãy rà cấu hình hiệu lực và xác nhận bằng HTTPS handshake. Nếu không khai `environments`, hành vi cũ không đổi.

Với cấu hình topology, nhánh có khai `process:` hoặc `processes:` sẽ thay cả nhóm topology chung; nhánh không khai thì kế thừa topology chung. Nhờ vậy có thể giữ `processes:` hiện tại ở phần chung cho local, rồi chỉ khai `process:` ở nhánh server RAM thấp. Dùng `app.run_configured()` để Xime tự gọi supervisor đúng khi cấu hình đang hoạt động có `processes:`. Không để đồng thời `process:` và `processes:` trong cấu hình có hiệu lực.

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
# resources/application.yml
xime:
  dev: true
environments:
  local: { ... }
  server: { ... }
```

**Mặc định TẮT, muốn thì phải bật lên.** Nó quyết định hai chuyện, và cả hai đều
hay bị quên khi lên production:

| | `xime.dev` tắt (mặc định) | bật |
|---|---|---|
| `/docs`, `/redoc`, `/openapi.json` | không tồn tại, trả 404 | phục vụ như thường |
| access log của uvicorn (một dòng mỗi request) | không in | in như thường |

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

### Access log: vì sao nó cũng nằm sau công tắc này

Một dòng `INFO: 127.0.0.1:52341 - "GET /api/v1/products" 200 OK` cho mỗi request là
thứ quan trắc rẻ nhất khi đang phát triển. Nó cũng là chi phí trả trên **từng**
request, và đo trên một máy dev thì nó không nhỏ như vẻ ngoài:

| | µs mỗi dòng | phần của một request |
|---|---|---|
| tắt (chỉ một phép `if`) | 0,04 | ~0% |
| ghi ra file, như dưới `systemd` hay `nohup` | 31 | **~14%** |
| ghi ra terminal có màu, khi chạy tay | 34 | ~15% |

Mốc so sánh là 227 µs cho trọn một request qua `WebAdapter` (4.396 req/s, đo ở bản
0.8.1). Con số này của **máy này**, đĩa này, hệ điều hành này - đo lại trên máy của
bạn thì khác, nhưng bậc độ lớn thì không.

⚠ **Chỉ access log tắt. Log khởi động vẫn còn nguyên** - hai thứ đó đi qua hai logger
khác nhau (`uvicorn.access` và `uvicorn.error`), nên bạn vẫn thấy đủ dòng adapter mở
cổng ở đâu, xác thực cài chưa, tài liệu có phục vụ không.

⚠ **Access log biến mất là hỏng im lặng** - không 404, không lỗi, chỉ là một màn hình
trống mà người ta rất dễ đọc thành *"app không nhận được request nào"*. Vì vậy dòng
khởi động tự nói ra nó:

```text
web default: process main serving on 0.0.0.0:8100 (HTTP) [access log off - set xime.dev: true]
web default: process main serving on 0.0.0.0:8100 (HTTP) [access log on]
```

Cần access log ở production thật thì đặt một reverse proxy phía trước và lấy ở đó:
nginx, Caddy hay Traefik đều ghi cùng thông tin đó bằng mã C, không tốn một phần chi
phí nào của tiến trình Python.

---

## Phạm vi checker và sàn dependency (Unreleased)

`xime check config` kiểm khóa framework ở common và cả hai nhánh
`environments.local/server`, gồm nhánh chưa được chọn. Field bắt buộc và xung
đột server/webserver được xét sau khi merge để overlay có thể kế thừa giá trị.
ID trong `process.web.<id>` hoặc `processes.<process_id>.web.<id>` là tên động;
khóa SSL bên trong vẫn được kiểm. Khối riêng của app nằm ngoài schema framework.
HTTP chủ ý và khối SSL rỗng vẫn hợp lệ. Checker báo đường dẫn khóa thay vì
giá trị credential; file không đọc được có kết quả inconclusive.

Sàn dependency của checkout phát triển: PyJWT 2.15.0 ở jwt, AnyIO 4.14.2 ở
runtime và Uvicorn 0.48.0 ở web. Đổi metadata source không tự nâng môi trường đã
cài; cập nhật dependency qua quy trình triển khai app. Cipher khai tường minh
vẫn được tôn trọng.

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
