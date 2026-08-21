"""Cấu hình mạng và TLS của **web adapter** - không phải của core.

⚠ Hai lớp dưới đây từng nằm ở `core/config/runtime.py`, nơi `ServerConfig` có
docstring *"Network binding for the HTTP adapter"*.

> **Core của framework biết về khái niệm "HTTP adapter".** Năm adapter kia không
> có một dòng nào trong core.

Bất đối xứng đó **không có lý do thiết kế nào** - nó là di sản của việc web ra
đời trước. Cùng khuôn với `PEER_APP_ID` đã gỡ 2026-08-17 (*"framework không được
phụ thuộc gì khái niệm ngoài cả"*), chỉ khác là lần đó core biết về **Xime**,
lần này core biết về **một adapter cụ thể**.

⚠ Gỡ ở đây là gỡ **thuộc tính Python trên `RuntimeConfig`**, không phải gỡ khoá
YAML: khối `server:` giữ nguyên từng chữ, và 25 app không phải sửa một dòng cấu
hình. Chỗ đổi là **AI đọc nó**.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from xime.core.config.runtime import RuntimeConfig


class ServerTlsConfig(BaseModel):
    """TLS (HTTPS) for the HTTP adapter, off unless certfile/keyfile are set.

    The platform deliberately runs without a gateway or reverse proxy, so each
    service terminates TLS itself. Paths point at PEM files on disk, which is
    what a public CA client such as certbot produces; certificates issued by the
    internal Trust CA are meant for service-to-service mTLS and are NOT trusted
    by browsers, so they do not belong here.
    Platform cố ý không có gateway/reverse proxy nên mỗi service tự kết thúc TLS.
    Đường dẫn trỏ tới file PEM trên đĩa - đúng thứ certbot sinh ra; cert do CA nội
    bộ Trust cấp là để service nhận diện nhau qua mTLS, trình duyệt KHÔNG tin, nên
    không dùng ở đây.

    Leaving everything unset keeps the plain-HTTP behaviour unchanged.
    Để trống toàn bộ thì giữ nguyên hành vi HTTP thuần như cũ.
    """

    certfile: str | None = None
    keyfile: str | None = None
    keyfile_password: str | None = None

    # Client-certificate verification (mTLS over REST). ca_certs is the CA bundle
    # used to verify client certificates; cert_reqs says whether one is demanded.
    # Xác thực client cert (mTLS trên REST). ca_certs là bundle CA để verify cert
    # của client; cert_reqs quyết định có bắt buộc client xuất trình hay không.
    ca_certs: str | None = None

    # Spelled out rather than taking ssl.CERT_* integers: an operator reading
    # `cert_reqs: required` in YAML understands it, `cert_reqs: 2` they do not.
    # Dùng chữ thay vì số ssl.CERT_*: operator đọc `cert_reqs: required` là hiểu,
    # `cert_reqs: 2` thì không.
    cert_reqs: Literal["none", "optional", "required"] | None = None

    ciphers: str | None = None

    @property
    def enabled(self) -> bool:
        """True when TLS is configured at all (mirrors uvicorn's own is_ssl)."""
        return bool(self.certfile or self.keyfile)


class ServerConfig(BaseModel):
    """Network binding for the HTTP adapter."""

    host: str = "0.0.0.0"
    port: int = 8080
    ssl: ServerTlsConfig = Field(default_factory=ServerTlsConfig)


class WebServerConfig(BaseModel):
    """Khối `server:` trong `application.yml`, do chính web adapter đọc."""

    host: str = "0.0.0.0"
    port: int = 8080
    ssl: ServerTlsConfig = Field(default_factory=ServerTlsConfig)

    @classmethod
    def from_runtime(cls, runtime: RuntimeConfig) -> WebServerConfig:
        """Đọc khối `server:`. Vắng hoặc sai kiểu thì về mặc định như cũ."""
        raw = runtime.get("server")
        if not isinstance(raw, dict):
            return cls()
        return cls.model_validate(raw)
