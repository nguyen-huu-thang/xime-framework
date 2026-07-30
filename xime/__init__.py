"""
Xime Framework — Python backend framework inspired by Spring Boot.

Entry-point for application code:
    from xime import Application, BindingConfig

Sub-packages:
    xime.adapters.web        — HTTP adapter (FastAPI), WebSocket, route decorators
    xime.adapters.web.openapi — OpenAPI / Swagger configuration
    xime.starters.jwt        — JWT authentication
    xime.starters.sqlalchemy — Async SQLAlchemy integration
    xime.starters.scheduler  — Task scheduling (APScheduler)
"""

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
    __version__ = "0.7.0"

__all__ = ["Application", "BindingConfig", "__version__"]
