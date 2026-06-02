"""
Test xime package root — kiểm tra toàn bộ public API có thể import được:
  - from xime import Application
  - from xime.adapters.web import WebAdapter, WebSocketHandler, route decorators
  - from xime.adapters.web.routing import decorators, configure_controllers
  - from xime.adapters.web.openapi import configure_openapi, OpenApiConfig, JwtBearer, ApiKey
  - xime.starters.jwt (skip nếu PyJWT chưa cài)
  - xime.starters.sqlalchemy (skip nếu SQLAlchemy chưa cài)
  - xime.starters.scheduler (skip nếu APScheduler chưa cài)

Các test này kiểm tra rằng xime/ là thin re-export layer đúng cách:
  - Symbol identity (xime.X là cùng object với implementation thực sự)
  - Callable check cho functions
  - Class check cho types
"""
import pytest


# ---------------------------------------------------------------------------
# xime root
# ---------------------------------------------------------------------------

def test_import_application_from_xime():
    from xime import Application
    assert Application is not None


def test_application_is_same_object_as_implementation():
    """xime.Application phải là cùng class với core.bootstrap.application.Application."""
    from xime import Application
    from core.bootstrap.application import Application as _Impl
    assert Application is _Impl


def test_xime_all_exports_application():
    import xime
    assert "Application" in xime.__all__


# ---------------------------------------------------------------------------
# xime.adapters.web
# ---------------------------------------------------------------------------

def test_import_web_adapter():
    from xime.adapters.web import WebAdapter
    assert WebAdapter is not None


def test_web_adapter_is_correct_class():
    from xime.adapters.web import WebAdapter
    from adapters.web._adapter import WebAdapter as _Impl
    assert WebAdapter is _Impl


def test_import_websocket_handler():
    from xime.adapters.web import WebSocketHandler
    assert WebSocketHandler is not None


def test_import_route_decorators_from_adapters_web():
    from xime.adapters.web import get, post, put, patch, delete
    assert all(callable(f) for f in [get, post, put, patch, delete])


def test_import_configure_controllers_from_adapters_web():
    from xime.adapters.web import configure_controllers
    assert callable(configure_controllers)


# ---------------------------------------------------------------------------
# xime.adapters.web.routing
# ---------------------------------------------------------------------------

def test_import_decorators_from_routing_subpackage():
    from xime.adapters.web.routing import get, post, put, patch, delete
    assert all(callable(f) for f in [get, post, put, patch, delete])


def test_import_configure_controllers_from_routing_subpackage():
    from xime.adapters.web.routing import configure_controllers
    assert callable(configure_controllers)


def test_routing_and_web_expose_same_decorator_objects():
    """xime.adapters.web.get và xime.adapters.web.routing.get phải là cùng object."""
    from xime.adapters.web import get as web_get
    from xime.adapters.web.routing import get as routing_get
    assert web_get is routing_get


def test_routing_and_web_expose_same_configure_controllers():
    from xime.adapters.web import configure_controllers as web_cc
    from xime.adapters.web.routing import configure_controllers as routing_cc
    assert web_cc is routing_cc


# ---------------------------------------------------------------------------
# xime.adapters.web.openapi
# ---------------------------------------------------------------------------

def test_import_configure_openapi():
    from xime.adapters.web.openapi import configure_openapi
    assert callable(configure_openapi)


def test_import_openapi_config():
    from xime.adapters.web.openapi import OpenApiConfig
    assert OpenApiConfig is not None


def test_import_jwt_bearer():
    from xime.adapters.web.openapi import JwtBearer
    assert JwtBearer is not None


def test_import_api_key():
    from xime.adapters.web.openapi import ApiKey
    assert ApiKey is not None


def test_import_security_scheme():
    from xime.adapters.web.openapi import SecurityScheme
    assert SecurityScheme is not None


def test_openapi_symbols_match_implementation():
    from xime.adapters.web.openapi import OpenApiConfig, configure_openapi
    from adapters.web.openapi import OpenApiConfig as _Cfg, configure_openapi as _fn
    assert OpenApiConfig is _Cfg
    assert configure_openapi is _fn


# ---------------------------------------------------------------------------
# xime.starters.jwt (optional — skip nếu PyJWT chưa cài)
# ---------------------------------------------------------------------------

def test_import_jwt_configure():
    pytest.importorskip("jwt", reason="PyJWT not installed — skip JWT starter tests")
    from xime.starters.jwt import configure_jwt
    assert callable(configure_jwt)


def test_import_jwt_middleware_config():
    pytest.importorskip("jwt", reason="PyJWT not installed")
    from xime.starters.jwt import JwtMiddlewareConfig
    assert JwtMiddlewareConfig is not None


def test_import_jwt_key_context():
    pytest.importorskip("jwt", reason="PyJWT not installed")
    from xime.starters.jwt import KeyContext
    assert KeyContext is not None


def test_import_jwt_token_interfaces():
    pytest.importorskip("jwt", reason="PyJWT not installed")
    from xime.starters.jwt import JwtTokenSigner, JwtTokenVerifier
    assert JwtTokenSigner is not None
    assert JwtTokenVerifier is not None


def test_import_jwt_pyjwt_implementations():
    pytest.importorskip("jwt", reason="PyJWT not installed")
    from xime.starters.jwt import PyJwtTokenSigner, PyJwtTokenVerifier
    assert PyJwtTokenSigner is not None
    assert PyJwtTokenVerifier is not None


def test_jwt_symbols_match_implementation():
    pytest.importorskip("jwt", reason="PyJWT not installed")
    from xime.starters.jwt import configure_jwt as xime_fn
    from starters.jwt import configure_jwt as impl_fn
    assert xime_fn is impl_fn


# ---------------------------------------------------------------------------
# xime.starters.sqlalchemy (optional — skip nếu SQLAlchemy chưa cài)
# ---------------------------------------------------------------------------

def test_import_sqlalchemy_base():
    pytest.importorskip("sqlalchemy", reason="SQLAlchemy not installed")
    from xime.starters.sqlalchemy import Base, TimestampMixin
    assert Base is not None
    assert TimestampMixin is not None


def test_import_sqlalchemy_transaction_manager():
    pytest.importorskip("sqlalchemy", reason="SQLAlchemy not installed")
    from xime.starters.sqlalchemy import SqlAlchemyTransactionManager
    assert SqlAlchemyTransactionManager is not None


def test_import_sqlalchemy_session():
    pytest.importorskip("sqlalchemy", reason="SQLAlchemy not installed")
    from xime.starters.sqlalchemy import AsyncEngineProvider, AsyncSessionFactory
    assert AsyncEngineProvider is not None
    assert AsyncSessionFactory is not None


def test_import_sqlalchemy_transaction_context():
    pytest.importorskip("sqlalchemy", reason="SQLAlchemy not installed")
    from xime.starters.sqlalchemy import SqlAlchemyTransactionContext
    assert SqlAlchemyTransactionContext is not None


# ---------------------------------------------------------------------------
# xime.starters.scheduler (optional — skip nếu APScheduler chưa cài)
# ---------------------------------------------------------------------------

def test_import_scheduler_configure():
    pytest.importorskip("apscheduler", reason="APScheduler not installed")
    from xime.starters.scheduler import configure_scheduler
    assert callable(configure_scheduler)


def test_import_scheduler_config():
    pytest.importorskip("apscheduler", reason="APScheduler not installed")
    from xime.starters.scheduler import SchedulerConfig, CronJob, IntervalJob
    assert SchedulerConfig is not None
    assert CronJob is not None
    assert IntervalJob is not None


def test_import_scheduled_job_protocol():
    pytest.importorskip("apscheduler", reason="APScheduler not installed")
    from xime.starters.scheduler import ScheduledJob
    assert ScheduledJob is not None


def test_scheduler_symbols_match_implementation():
    pytest.importorskip("apscheduler", reason="APScheduler not installed")
    from xime.starters.scheduler import configure_scheduler as xime_fn
    from starters.scheduler import configure_scheduler as impl_fn
    assert xime_fn is impl_fn
