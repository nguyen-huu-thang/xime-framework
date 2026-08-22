from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from ._config import ApiKey, JwtBearer, OpenApiConfig


def build_custom_openapi(app: FastAPI, config: OpenApiConfig) -> Callable[[], dict]:
    """Tạo hàm custom_openapi từ OpenApiConfig và gắn vào FastAPI app.

    Trả về closure - gắn vào app.openapi để FastAPI dùng khi sinh schema.
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


def _normalize_path(path: str) -> str:
    """Strip trailing slash, keep bare '/'.

    ⚠ Kept only for the schema side of the comparison. The public list itself is
    read through split_public_paths(), the SAME function the middleware uses, so
    a "/*" entry documents the branch it actually opens. Two hand-written copies
    of one matching rule is how the padlock in Swagger starts disagreeing with
    the middleware, and nothing fails when it does.
    ⚠ Chỉ còn dùng cho vế schema. Danh sách công khai thì đọc qua
    split_public_paths() - CÙNG hàm middleware dùng - nên mục "/*" ghi tài liệu
    đúng nhánh nó thật sự mở. Hai bản chép tay của một luật khớp chính là cách ổ
    khoá trên Swagger bắt đầu nói khác middleware, mà không gì đỏ khi nó lệch.
    """
    return path.rstrip("/") or "/"


def _apply_security(
    schema: dict,
    scheme: JwtBearer | ApiKey,
    public_paths: list[str],
) -> None:
    # Đăng ký security scheme vào components
    schema.setdefault("components", {})
    schema["components"].setdefault("securitySchemes", {})
    schema["components"]["securitySchemes"][scheme.scheme_name] = scheme.to_openapi_dict()

    from xime.starters.jwt._config import path_is_public, split_public_paths

    public, public_prefixes = split_public_paths(public_paths)
    security_req: list[dict[str, list[str]]] = [{scheme.scheme_name: []}]

    # Apply security cho tất cả endpoint, bỏ qua public_paths (cùng luật khớp
    # với middleware, kể cả mục "/*")
    for path, path_item in schema.get("paths", {}).items():
        if path_is_public(path, public, public_prefixes):
            continue
        for method_spec in path_item.values():
            # path_item có thể chứa key không phải method (vd: "summary", "$ref")
            if isinstance(method_spec, dict):
                method_spec["security"] = security_req
