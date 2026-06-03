from ._config import ApiKey, JwtBearer, OpenApiConfig, SecurityScheme
from .._registry import registry


def configure_openapi(config: OpenApiConfig) -> None:
    """Đăng ký cấu hình OpenAPI cho web adapter.

    Gọi hàm này trong config/web.py khi khởi động ứng dụng:

        from xime.adapters.web.openapi import configure_openapi, OpenApiConfig, JwtBearer

        configure_openapi(OpenApiConfig(
            title="My Service",
            version="1.0.0",
            description="Mô tả service",
            security=JwtBearer(),
            public_paths=["/auth/login", "/health"],
        ))
    """
    registry.set_openapi(config)


__all__ = [
    "configure_openapi",
    "OpenApiConfig",
    "JwtBearer",
    "ApiKey",
    "SecurityScheme",
]
