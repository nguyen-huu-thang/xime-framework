"""
xime.adapters.web.openapi — OpenAPI / Swagger configuration.

Usage:
    from xime.adapters.web.openapi import configure_openapi, OpenApiConfig
    from xime.adapters.web.openapi import JwtBearer, ApiKey

Example:
    configure_openapi(OpenApiConfig(
        title="My Service",
        version="1.0.0",
        security=JwtBearer(),
        public_paths=["/auth/login", "/health"],
    ))
"""

from adapters.web.openapi import (
    ApiKey,
    JwtBearer,
    OpenApiConfig,
    SecurityScheme,
    configure_openapi,
)

__all__ = [
    "configure_openapi",
    "OpenApiConfig",
    "JwtBearer",
    "ApiKey",
    "SecurityScheme",
]
