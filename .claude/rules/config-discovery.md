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

## Cơ chế hoạt động

Hàm `configure_*` ghi vào một registry singleton bên trong framework. Khi adapter khởi động, nó đọc registry đó để áp dụng config.

```text
Developer gọi configure_openapi(config)
        ↓
WebRegistry.set_openapi(config)   ← lưu vào registry
        ↓
WebAdapter.start()                ← đọc registry, build custom_openapi, gắn vào FastAPI
```
