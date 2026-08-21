# Điểm khởi động ứng dụng - Xime Framework

## Cấu trúc tối thiểu

Một ứng dụng Xime chỉ yêu cầu hai thư mục ở cấp gốc:

```
my-service/
├── app/        ← toàn bộ code ứng dụng
│   └── main.py ← entry point duy nhất
└── test/       ← test code
```

Ngoài `./app` và `./test`, các thứ còn lại (`.github/`, `.gitignore`, `Dockerfile`, `pyproject.toml`, ...) là tùy chọn của người dùng.

---

## `./app` - Source root

`./app` chứa **toàn bộ** code ứng dụng: business logic, config, domain, infrastructure, API handler, v.v.

Framework **không yêu cầu** cấu trúc thư mục cụ thể bên trong `./app`. Người lập trình tự do tổ chức theo cách phù hợp với dự án - Hexagonal, Layered, Modular hay bất kỳ convention nào.

Tuy nhiên, Xime **khuyến khích** tuân theo cấu trúc chuẩn bên dưới. Đây là cấu trúc được thiết kế cho ứng dụng microservice theo kiến trúc Hexagonal, phù hợp với cách DI scan và exclude mặc định của framework.

---

## Cấu trúc khuyến nghị

```
my-service/
│
├── app/
│   ├── main.py
│   │
│   ├── api/                        ← Adapter layer: nhận request từ bên ngoài
│   │   ├── grpc/
│   │   │   ├── external/           ← gRPC handler phục vụ client bên ngoài
│   │   │   └── internal/           ← gRPC handler phục vụ service nội bộ
│   │   └── rest/
│   │       ├── external/           ← REST handler phục vụ client bên ngoài
│   │       └── internal/           ← REST handler phục vụ service nội bộ
│   │
│   ├── application/                ← Application layer
│   │   ├── dto/                    ← Data Transfer Objects (excluded from DI)
│   │   ├── port/
│   │   │   ├── inbound/            ← Input port interfaces / Protocol (excluded from DI)
│   │   │   └── outbound/           ← Output port interfaces / Protocol (excluded from DI)
│   │   ├── usecase/                ← Use case implementations (scanned)
│   │   ├── service/                ← Application services (scanned)
│   │   └── mapper/                 ← Object mappers (excluded from DI)
│   │
│   ├── common/                     ← Shared utilities (excluded from DI)
│   │   ├── constants/
│   │   ├── exception/
│   │   └── util/
│   │
│   ├── config/                     ← Xime framework configuration
│   │   ├── dependency.py           ← DI: scan packages + bind interfaces
│   │   ├── routing.py              ← Route registration
│   │   └── security.py             ← Security config
│   │
│   ├── domain/                     ← Domain layer: entities, value objects (excluded from DI)
│   │
│   ├── integration/                ← External service clients
│   │   ├── identity/
│   │   │   └── client/             ← scanned
│   │   └── trust/                  ← scanned
│   │
│   └── infrastructure/             ← Infrastructure implementations
│       ├── persistence/
│       │   └── repository/         ← scanned (implements outbound ports)
│       ├── redis/                  ← scanned
│       └── cache/                  ← scanned
│
└── test/
```

### Lý do khuyến nghị cấu trúc này

- `config/dependency.py` nằm ở vị trí cố định để framework tự tìm được khi bootstrap
- Phân tách rõ `port/inbound` (interface nhận) và `port/outbound` (interface gửi ra) - các Protocol này bị exclude khỏi DI scan, chỉ đóng vai trò contract
- `domain/` và `dto/` excluded khỏi DI - không phải service, không cần inject
- `infrastructure/` chứa implementation của `port/outbound` - được scan và bind qua `config/dependency.py`

---

## Khởi tạo project bằng CLI (tùy chọn)

Xime cung cấp lệnh CLI để scaffold cây thư mục theo cấu trúc khuyến nghị, tương tự `mvn archetype:generate` trong Java:

```bash
xime new my-service
```

Lệnh này tạo toàn bộ cây thư mục chuẩn kèm các file mẫu (`main.py`, `config/dependency.py`, ...) để người lập trình bắt đầu ngay mà không cần tạo thủ công.

Đây là **công cụ tùy chọn** - không dùng CLI vẫn chạy được hoàn toàn bình thường.

---

## `main.py` - Entry point

`main.py` là file duy nhất người dùng cần chạy để khởi động toàn bộ ứng dụng:

```python
from xime import Application

app = Application()

if __name__ == "__main__":
    app.run()
```

`Application` là điểm vào của framework. Nó đọc cấu hình từ `app/config/`, thực hiện toàn bộ trình tự startup (scan → resolve → build graph → validate → start adapters) rồi giữ ứng dụng chạy.

---

## Cách chạy

```bash
python -m app.main
```

---

## Logging - Framework tự cấu hình mặc định

Python mặc định để root logger ở mức `WARNING` và không gắn handler, nên mọi log
`INFO` (kể cả luồng startup của framework) đều bị nuốt - app chạy đúng nhưng im
lặng, dễ tưởng bị treo.

Để tránh cú vấp này, `Application` tự cấu hình root logging lúc bootstrap, đọc từ
khối `logging:` trong `application.yml`:

```yaml
logging:
  enabled: true        # đặt false để framework không đụng tới logging
  level: INFO          # DEBUG / INFO / WARNING / ERROR ... (không phân biệt hoa thường)
  format: "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
  datefmt: "%H:%M:%S"
```

Toàn bộ khối là tùy chọn - không khai báo thì dùng mặc định ở trên (enabled,
INFO).

Quy tắc an toàn: framework **chỉ** cấu hình khi `enabled: true` **và** root logger
chưa có handler nào. Nếu app tự gọi `logging.basicConfig`/`dictConfig` (hoặc chạy
dưới một harness đã cấu hình logging như pytest), framework **không** ghi đè -
setup của app luôn được ưu tiên. Muốn tự lo hoàn toàn thì đặt `enabled: false`.

---

## `sys.path` - Framework tự xử lý

Khi `main.py` chạy, Python coi thư mục gốc của project (không phải `./app`) là working directory. Điều này có nghĩa import như `from application.service import UserService` sẽ thất bại vì Python không biết về `./app`.

Framework tự giải quyết vấn đề này trong bước bootstrap: trước khi làm bất cứ điều gì khác, `Application` thêm `./app` vào `sys.path`. Người lập trình không cần can thiệp.

```python
# Framework tự động thực hiện điều này khi khởi động:
sys.path.insert(0, os.path.join(os.getcwd(), "app"))
```

---

## Quy ước duy nhất

| Quy ước | Bắt buộc | Ghi chú |
|---|---|---|
| `./app/` là source root | Có | Framework bootstrap dựa vào đây |
| `./app/main.py` là entry point | Có | File duy nhất người dùng chạy |
| Cấu trúc bên trong `./app/` | Không | Tự do hoàn toàn |
| `./test/` cho test | Khuyến nghị | Không bắt buộc |
