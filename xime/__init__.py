"""
Xime Framework — Python backend framework inspired by Spring Boot.

Entry-point for application code:
    from xime import Application

Sub-packages:
    xime.adapters.web        — HTTP adapter (FastAPI), WebSocket, route decorators
    xime.adapters.web.openapi — OpenAPI / Swagger configuration
    xime.starters.jwt        — JWT authentication
    xime.starters.sqlalchemy — Async SQLAlchemy integration
    xime.starters.scheduler  — Task scheduling (APScheduler)
"""

from xime.core.bootstrap.application import Application

__all__ = ["Application"]
