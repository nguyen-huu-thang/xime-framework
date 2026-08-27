from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict


class SecurityScheme(Protocol):
    """Contract cho mọi security scheme - dùng bởi builder để type-check."""

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

    ### `/docs`, `/redoc`, `/openapi.json`: mặc định TẮT, muốn thì phải bật lên

    Chúng chỉ được phục vụ khi ứng dụng khai **`xime.dev: true`** trong
    `application.yml`. Đó là MỘT công tắc chung cho mọi bề mặt chỉ dành cho môi
    trường phát triển, không phải một công tắc riêng của OpenAPI - xem
    `xime.core.config.is_dev_mode`.

        # resources/application-local.yml
        xime:
          dev: true

    An OpenAPI schema is a complete map of the API: every path, every parameter,
    every field name, every error code. Served to anyone, it removes the
    reconnaissance step almost entirely, which is the usual reason for keeping it
    out of production. FastAPI serves all three by default; Xime does not, and
    that difference is deliberate. The start-up log says which state you are in,
    so the change is never silent.
    Schema OpenAPI là bản đồ đầy đủ của API: mọi đường dẫn, mọi tham số, mọi tên
    trường, mọi mã lỗi. Mở cho bất kỳ ai là rút giai đoạn thăm dò xuống gần bằng
    không. FastAPI mặc định phục vụ cả ba, Xime thì không, và chỗ khác nhau đó là
    cố ý. Dòng log khởi động khai đang ở trạng thái nào, nên nó không im lặng.

    ⚠ Hiding the schema behind the JWT middleware is NOT the alternative, and the
    reason is worth knowing before reaching for it. Swagger UI is a page opened in
    a browser, and a browser attaches no `Authorization` header when you type a
    URL - so a `/docs` left out of `public_paths` returns 401 to the very person
    who wants to read it. The real choice is on in development and off in
    production, which is what `xime.dev` decides.
    ⚠ Giấu sau middleware JWT KHÔNG phải đường thay thế, và lý do đáng biết trước
    khi với tay tới nó: Swagger UI là trang mở bằng trình duyệt, mà trình duyệt
    không gắn header `Authorization` khi gõ URL, nên `/docs` nằm ngoài
    `public_paths` trả 401 cho đúng người muốn đọc nó. Lựa chọn thật là bật ở dev
    và tắt ở production, và `xime.dev` quyết chuyện đó.

    The three `*_url` fields below are PATHS, not switches: they say *where* the
    documentation lives once `xime.dev` has said *whether*. Set one to None to
    drop just that one; setting `openapi_url` to None drops all three, because
    both UIs fetch the schema from it.
    Ba trường `*_url` dưới đây là ĐƯỜNG DẪN chứ không phải công tắc: chúng nói
    tài liệu nằm Ở ĐÂU, sau khi `xime.dev` đã trả lời CÓ HAY KHÔNG. Đặt một cái
    thành None là bỏ riêng cái đó; đặt `openapi_url` thành None là bỏ cả ba, vì
    cả hai giao diện đều tải schema từ nó.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    title: str
    version: str
    description: str = ""
    security: JwtBearer | ApiKey | None = None
    public_paths: list[str] = []

    # Paths, consulted only once `xime.dev` is on.
    # Đường dẫn, chỉ được đọc khi `xime.dev` đã bật.
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"
    openapi_url: str | None = "/openapi.json"
    swagger_ui_title: str | None = None
