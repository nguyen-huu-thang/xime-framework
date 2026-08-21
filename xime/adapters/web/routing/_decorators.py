from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Attribute name used to mark route methods - internal to the framework.
ROUTE_ATTR = "_xime_route_info"


@dataclass
class RouteInfo:
    """Metadata attached to a controller method by a route decorator."""

    method: str
    path: str
    status_code: int = 200
    response_model: Any = None
    summary: str | None = None
    description: str | None = None
    deprecated: bool = False
    include_in_schema: bool = True
    tags: list[str] | None = None
    name: str | None = None
    operation_id: str | None = None


def _route(method: str, path: str, **kwargs: Any) -> Callable:
    """Factory that creates an HTTP-method-specific decorator.

    The decorator attaches a RouteInfo instance to the method - nothing else.
    Actual route registration happens later in WebAdapter startup.
    """
    def decorator(func: Callable) -> Callable:
        setattr(func, ROUTE_ATTR, RouteInfo(method=method, path=path, **kwargs))
        return func

    return decorator


def get(path: str, **kwargs: Any) -> Callable:
    """Mark a controller method as a GET route."""
    return _route("GET", path, **kwargs)


def post(path: str, **kwargs: Any) -> Callable:
    """Mark a controller method as a POST route."""
    return _route("POST", path, **kwargs)


def put(path: str, **kwargs: Any) -> Callable:
    """Mark a controller method as a PUT route."""
    return _route("PUT", path, **kwargs)


def patch(path: str, **kwargs: Any) -> Callable:
    """Mark a controller method as a PATCH route."""
    return _route("PATCH", path, **kwargs)


def delete(path: str, **kwargs: Any) -> Callable:
    """Mark a controller method as a DELETE route."""
    return _route("DELETE", path, **kwargs)
