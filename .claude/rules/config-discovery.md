# Quy tắc Config Discovery — Xime Framework

## Nguyên tắc

Framework **không tự quét** file config. Developer chủ động import một hàm/object từ framework và gọi nó — framework nhận config qua lời gọi đó.

```python
# config/web.py
from xime.adapters.web.openapi import configure_openapi, OpenApiConfig, JwtBearer

configure_openapi(OpenApiConfig(
    title="My Service",
    version="1.0.0",
    description="...",
    security=JwtBearer(),
    public_paths=["/auth/login", "/health"]
))
```

## Tại sao không auto-scan config

- Auto-scan config file là magic ẩn — khó debug khi cấu hình không được áp dụng
- Xime ưu tiên **Explicit is better than implicit**
- Developer biết chính xác khi nào config được đăng ký (lúc gọi hàm)

## Áp dụng cho tất cả config

Mọi loại config đều theo pattern này — không có ngoại lệ:
- OpenAPI → `configure_openapi(...)`
- Routing → `configure_routing(...)`  
- Security → `configure_security(...)`
- Middleware → `configure_middleware(...)`
- CORS → `configure_cors(...)`
- Exception handler → `configure_exception_handlers(...)`

## Middleware cần dependency từ DI / runtime config

`configure_middleware(cls, **options)` chỉ nhận option **tĩnh**. Khi middleware
tự viết cần service từ DI container hoặc giá trị từ runtime config (chỉ biết sau
khi container dựng xong), **không** subclass `WebAdapter` để gọi `xime_app.get()`.
Thay vào đó dùng hai marker làm giá trị option — framework phân giải lúc
`build_app` (hiện thực: `adapters/web/_markers.py`):

```python
from xime.adapters.web import configure_middleware, Inject, FromConfig

configure_middleware(
    JwtMiddleware,
    auth_svc=Inject(AuthenticationService),      # lấy singleton từ DI container
    user_svc=Inject(UserService),
    blacklist_svc=Inject(BlacklistTokenService),
    realm=FromConfig("auth.realm", "default"),   # đọc RuntimeConfig (dot-notation)
)
```

- `Inject(SomeType)` → `xime_app.get(SomeType)`; thiếu binding → startup báo lỗi rõ.
- `FromConfig("a.b", default)` → `RuntimeConfig.get("a.b", default)`.
- Giá trị không phải marker giữ nguyên (tương thích ngược hoàn toàn).

CORS có helper riêng `configure_cors(...)` (`adapters/web/_cors.py`): tham số để
trống tự đọc `cors.<tên>` từ `application.yml`, thiếu thì về mặc định Starlette.

```python
from xime.adapters.web import configure_cors

configure_cors(allow_origins=["http://localhost:3000"], allow_credentials=True)
# hoặc configure_cors()  → đọc toàn bộ từ khối cors.* trong application.yml
```

## Cơ chế hoạt động

Hàm `configure_*` ghi vào một registry singleton bên trong framework. Khi adapter khởi động, nó đọc registry đó để áp dụng config.

```text
Developer gọi configure_openapi(config)
        ↓
WebRegistry.set_openapi(config)   ← lưu vào registry
        ↓
WebAdapter.start()                ← đọc registry, build custom_openapi, gắn vào FastAPI
```
