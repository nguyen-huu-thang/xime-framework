"""Cấu hình mạng và TLS của **web adapter** - không phải của core.

⚠ Hai lớp dưới đây từng nằm ở `core/config/runtime.py`, nơi `ServerConfig` có
docstring *"Network binding for the HTTP adapter"*.

> **Core của framework biết về khái niệm "HTTP adapter".** Năm adapter kia không
> có một dòng nào trong core.

Bất đối xứng đó **không có lý do thiết kế nào** - nó là di sản của việc web ra
đời trước. Cùng khuôn với `PEER_APP_ID` đã gỡ 2026-08-17 (*"framework không được
phụ thuộc gì khái niệm ngoài cả"*), chỉ khác là lần đó core biết về **Xime**,
lần này core biết về **một adapter cụ thể**.

⚠ Cấu hình mới dùng `webserver:`. `server:` được giữ làm alias tương thích, để
ứng dụng hiện có không phải đổi cấu hình ngay; khi khai cả hai root, startup báo
lỗi thay vì tự chọn một nguồn.
"""

from __future__ import annotations

import ipaddress
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from xime.core.config.runtime import RuntimeConfig
from xime.core.exception.framework import StartupException


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


class TlsReloadConfig(BaseModel):
    """How certificate files are reloaded after the listener starts."""

    mode: Literal["off", "watch", "api", "both"] = "off"
    interval_seconds: int = Field(default=300, strict=True, gt=0)


class WebServerTlsConfig(ServerTlsConfig):
    """TLS defaults plus the framework's certificate-reload policy."""

    reload: TlsReloadConfig = Field(default_factory=TlsReloadConfig)


class ManagementServerConfig(BaseModel):
    """Optional loopback-only management listener."""

    enabled: bool = False
    host: str = "127.0.0.1"
    port: int | None = Field(default=None, strict=True, ge=1, le=65535)

    @field_validator("host")
    @classmethod
    def _loopback_only(cls, value: str) -> str:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise ValueError("host must be an IPv4 or IPv6 loopback address") from exc
        if not address.is_loopback:
            raise ValueError("host must be an IPv4 or IPv6 loopback address")
        return value

    @model_validator(mode="after")
    def _enabled_requires_port(self) -> ManagementServerConfig:
        if self.enabled and self.port is None:
            raise ValueError("port is required when management.enabled is true")
        return self


class ServerConfig(BaseModel):
    """Network binding for the HTTP adapter."""

    host: str = "0.0.0.0"
    port: int = 8080
    ssl: ServerTlsConfig = Field(default_factory=ServerTlsConfig)


class WebServerConfig(BaseModel):
    """Khối `webserver:`; `server:` remains a compatibility alias."""

    host: str = "0.0.0.0"
    port: int = 8080
    ssl: WebServerTlsConfig = Field(default_factory=WebServerTlsConfig)
    management: ManagementServerConfig = Field(default_factory=ManagementServerConfig)

    @model_validator(mode="after")
    def _management_needed_for_api(self) -> WebServerConfig:
        if self.ssl.reload.mode in {"api", "both"} and not self.management.enabled:
            raise ValueError(
                "webserver.management.enabled must be true when TLS reload mode is api or both"
            )
        return self

    @classmethod
    def from_runtime(cls, runtime: RuntimeConfig) -> WebServerConfig:
        """Read the new block or the legacy alias with path-aware errors."""
        current = runtime.get("webserver")
        legacy = runtime.get("server")
        if current is not None and legacy is not None:
            raise StartupException(
                "\nConflicting Web Server Configuration\n"
                "  Config : declare either `webserver:` or legacy `server:`, not both.\n"
                "  Detail : `environments.server` is a profile name and is unaffected."
            )
        raw = current if current is not None else legacy
        where = "webserver" if current is not None else "server"
        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise StartupException(
                f"\nInvalid Web Server Configuration\n  Config : {where}\n"
                "  Detail : expected a YAML mapping."
            )
        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            details = []
            for error in exc.errors(include_input=False):
                field = ".".join(str(part) for part in error["loc"])
                details.append(f"  {where}.{field}: {error['msg']}")
            raise StartupException(
                "\nInvalid Web Server Configuration\n" + "\n".join(details)
            ) from exc
