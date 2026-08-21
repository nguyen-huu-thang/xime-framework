"""
Xime Framework - Python backend framework inspired by Spring Boot.

Entry-point for application code:
    from xime import Application, BindingConfig

Sub-packages:
    xime.adapters.web - HTTP adapter (FastAPI), WebSocket, route decorators
    xime.adapters.web.openapi - OpenAPI / Swagger configuration
    xime.starters.jwt - JWT authentication
    xime.starters.sqlalchemy - Async SQLAlchemy integration
    xime.starters.scheduler - Task scheduling (APScheduler)
"""

# ⚠ PHẢI là import Xime đầu tiên: nó ghi mốc thời gian dùng cho phép dò
# "code ở mức module phải nhẹ". Đặt sau một import nặng nào đó là đo thiếu đúng
# phần mình muốn đo. Module này chỉ dùng stdlib nên nó không kéo theo gì.
from xime import _startup as _startup  # noqa: I001 - phải đứng trước mọi import khác

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version

from xime.core.bootstrap.application import Application
from xime.core.config.binding import BindingConfig

# Single source of truth for the framework version: read from the installed
# distribution metadata (pyproject.toml). Falls back to the literal below only
# when running from an uninstalled source tree.
# Nguồn version duy nhất: đọc từ metadata distribution; chỉ fallback khi chạy
# từ source tree chưa cài.
try:
    __version__ = _dist_version("xime")
except PackageNotFoundError:  # pragma: no cover - chỉ xảy ra khi chưa cài đặt
    __version__ = "0.8.0"

__all__ = ["Application", "BindingConfig", "__version__"]
