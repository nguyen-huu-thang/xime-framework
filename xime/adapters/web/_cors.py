"""
configure_cors() — helper hạng nhất để bật CORS cho web adapter mà không phải tự
wire Starlette CORSMiddleware hay subclass WebAdapter.

Theo pattern configure_* (config-discovery): gọi một lần trong config/web.py.
Mỗi tham số: truyền tường minh thì dùng giá trị đó; bỏ trống (None) thì đọc từ
RuntimeConfig khóa `cors.<tên>` lúc build_app, không có trong YAML thì rơi về mặc
định an toàn của Starlette. Nhờ vậy Operator chỉnh CORS qua application.yml mà
không đụng code:

    # resources/application.yml
    cors:
      allow_origins: ["https://app.example.com"]
      allow_credentials: true

    # config/web.py
    from xime.adapters.web import configure_cors
    configure_cors()                      # đọc toàn bộ từ cors.* trong YAML
    # hoặc cố định trong code:
    configure_cors(allow_origins=["http://localhost:3000"], allow_credentials=True)

Lưu ý bảo mật: KHÔNG dùng allow_origins=["*"] khi allow_credentials=True (trình
duyệt sẽ chặn). Liệt kê origin cụ thể, hoặc dùng allow_origin_regex cho dev.
"""
from __future__ import annotations

from typing import Any

from ._markers import FromConfig
from ._registry import registry

# Mặc định của Starlette CORSMiddleware — dùng khi không truyền tường minh và
# YAML cũng không có khóa tương ứng. Giữ nguyên để hành vi dễ đoán, an toàn.
_CORS_DEFAULTS: dict[str, Any] = {
    "allow_origins": (),
    "allow_methods": ("GET",),
    "allow_headers": (),
    "allow_credentials": False,
    "allow_origin_regex": None,
    "expose_headers": (),
    "max_age": 600,
}


def configure_cors(
    *,
    allow_origins: list[str] | None = None,
    allow_methods: list[str] | None = None,
    allow_headers: list[str] | None = None,
    allow_credentials: bool | None = None,
    allow_origin_regex: str | None = None,
    expose_headers: list[str] | None = None,
    max_age: int | None = None,
    server_id: str = "default",
) -> None:
    """Bật CORS cho web adapter (server_id chỉ định).

    Tham số nào để None sẽ được đọc từ RuntimeConfig (`cors.<tên>`) lúc build_app,
    thiếu nốt thì dùng mặc định Starlette. CORS được đăng ký như một user
    middleware nên nằm ngoài JwtAuthMiddleware — preflight OPTIONS được xử lý
    trước khi xác thực.
    """
    try:
        from starlette.middleware.cors import CORSMiddleware
    except ImportError:  # pragma: no cover - starlette luôn đi kèm FastAPI
        raise RuntimeError(
            "configure_cors yêu cầu Starlette/FastAPI. "
            "Chạy: pip install 'xime[web]'"
        ) from None

    explicit = {
        "allow_origins": allow_origins,
        "allow_methods": allow_methods,
        "allow_headers": allow_headers,
        "allow_credentials": allow_credentials,
        "allow_origin_regex": allow_origin_regex,
        "expose_headers": expose_headers,
        "max_age": max_age,
    }

    # Giá trị tường minh thắng; nếu None → FromConfig("cors.<tên>", mặc định
    # Starlette) để Operator override qua YAML, không có thì về mặc định.
    options: dict[str, Any] = {}
    for name, value in explicit.items():
        if value is not None:
            options[name] = value
        else:
            options[name] = FromConfig(f"cors.{name}", _CORS_DEFAULTS[name])

    registry.add_middleware(CORSMiddleware, options, server_id)
