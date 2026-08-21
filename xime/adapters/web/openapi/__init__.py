from .._registry import registry
from ._config import ApiKey, JwtBearer, OpenApiConfig, SecurityScheme


def configure_openapi(config: OpenApiConfig, server_id: str = "default") -> None:
    """Đăng ký cấu hình OpenAPI cho web adapter.

    Gọi hàm này trong config/web.py khi khởi động ứng dụng:

        from xime.adapters.web.openapi import configure_openapi, OpenApiConfig, JwtBearer

        # Server mặc định (không cần truyền server_id):
        configure_openapi(OpenApiConfig(
            title="My Service",
            version="1.0.0",
            description="Mô tả service",
            security=JwtBearer(),
            public_paths=["/auth/login", "/health"],
        ))

        # Nhiều server - mỗi server một config:
        configure_openapi(OpenApiConfig(title="Public API", version="1.0.0"), server_id="public")
        configure_openapi(OpenApiConfig(title="Admin API", version="1.0.0"), server_id="admin")
    """
    registry.set_openapi(config, server_id)


__all__ = [
    "configure_openapi",
    "OpenApiConfig",
    "JwtBearer",
    "ApiKey",
    "SecurityScheme",
]
