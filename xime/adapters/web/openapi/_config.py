from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict


class SecurityScheme(Protocol):
    """Contract cho mọi security scheme — dùng bởi builder để type-check."""

    scheme_name: str

    def to_openapi_dict(self) -> dict[str, str]: ...


@dataclass
class JwtBearer:
    """HTTP Bearer token với format JWT.

    Sinh ra security scheme:
        {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    """

    scheme_name: str = "BearerAuth"

    def to_openapi_dict(self) -> dict[str, str]:
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}


@dataclass
class ApiKey:
    """API Key truyền qua header, query string, hoặc cookie.

    Sinh ra security scheme:
        {"type": "apiKey", "in": "<location>", "name": "<name>"}
    """

    name: str
    location: Literal["header", "query", "cookie"] = "header"
    scheme_name: str = "ApiKeyAuth"

    def to_openapi_dict(self) -> dict[str, str]:
        return {"type": "apiKey", "in": self.location, "name": self.name}


class OpenApiConfig(BaseModel):
    """Cấu hình OpenAPI/Swagger cho web adapter.

    Ví dụ sử dụng trong config/web.py:

        from xime.adapters.web.openapi import configure_openapi, OpenApiConfig, JwtBearer

        configure_openapi(OpenApiConfig(
            title="My Service",
            version="1.0.0",
            description="Mô tả service",
            security=JwtBearer(),
            public_paths=["/auth/login", "/health"],
        ))
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    title: str
    version: str
    description: str = ""
    security: JwtBearer | ApiKey | None = None
    public_paths: list[str] = []
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"
    openapi_url: str | None = "/openapi.json"
    swagger_ui_title: str | None = None
