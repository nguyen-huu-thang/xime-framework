from __future__ import annotations

from typing import Callable

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from ._config import ApiKey, JwtBearer, OpenApiConfig


def build_custom_openapi(app: FastAPI, config: OpenApiConfig) -> Callable[[], dict]:
    """Tạo hàm custom_openapi từ OpenApiConfig và gắn vào FastAPI app.

    Trả về closure — gắn vào app.openapi để FastAPI dùng khi sinh schema.
    """

    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=config.title,
            version=config.version,
            description=config.description,
            routes=app.routes,
        )

        if config.security is not None:
            _apply_security(schema, config.security, config.public_paths)

        app.openapi_schema = schema
        return schema

    return custom_openapi


def _apply_security(
    schema: dict,
    scheme: JwtBearer | ApiKey,
    public_paths: list[str],
) -> None:
    # Đăng ký security scheme vào components
    schema.setdefault("components", {})
    schema["components"].setdefault("securitySchemes", {})
    schema["components"]["securitySchemes"][scheme.scheme_name] = scheme.to_openapi_dict()

    public = set(public_paths)
    security_req = [{scheme.scheme_name: []}]

    # Apply security cho tất cả endpoint, bỏ qua public_paths
    for path, path_item in schema.get("paths", {}).items():
        if path in public:
            continue
        for method_spec in path_item.values():
            # path_item có thể chứa key không phải method (vd: "summary", "$ref")
            if isinstance(method_spec, dict):
                method_spec["security"] = security_req
