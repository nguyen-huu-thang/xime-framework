from __future__ import annotations

import functools
import inspect
from typing import Any

from fastapi import APIRouter

from ._decorators import ROUTE_ATTR, RouteInfo


def _make_handler(bound_method: Any) -> Any:
    """Wrap a bound controller method into a FastAPI-compatible async function.

    FastAPI introspects the handler's signature via inspect.signature() to
    determine which parameters are path params, query params, or request body.
    By the time we call this, 'self' is already bound - the signature only
    contains the parameters that FastAPI needs to know about.

    We must expose that signature explicitly on the wrapper function because
    functools.wraps alone does not copy __signature__. Without this, FastAPI
    would see the wrapper's (**kwargs) signature and fail to parse the request.

    Pattern is identical to what FastAPI uses internally for its own wrappers.
    """
    original_sig = inspect.signature(bound_method)

    if inspect.iscoroutinefunction(bound_method):
        @functools.wraps(bound_method)
        async def async_handler(**kwargs: Any) -> Any:
            return await bound_method(**kwargs)

        async_handler.__signature__ = original_sig  # type: ignore[attr-defined]
        return async_handler
    else:
        @functools.wraps(bound_method)
        def sync_handler(**kwargs: Any) -> Any:
            return bound_method(**kwargs)

        sync_handler.__signature__ = original_sig  # type: ignore[attr-defined]
        return sync_handler


class RouteBuilder:
    """Builds an APIRouter from a controller class and its DI-resolved instance.

    Reads RouteInfo metadata from each decorated method and calls
    APIRouter.add_api_route() - one call per decorated method.

    The controller's class-level attributes drive the router:
      prefix : URL prefix applied to all routes in this controller (e.g. "/users")
      tags   : OpenAPI tags applied to all routes (e.g. ["users"])
    """

    def build(self, cls: type, instance: object) -> APIRouter:
        prefix: str = getattr(cls, "prefix", "")
        tags: list[str] = getattr(cls, "tags", [])

        router = APIRouter(prefix=prefix, tags=tags)

        # Use vars() + MRO traversal to preserve declaration order.
        # inspect.getmembers() returns alphabetically - routes would appear
        # out-of-order on Swagger UI.
        seen_names: set[str] = set()
        ordered_methods: list[tuple[str, Any]] = []
        for klass in reversed(cls.__mro__):
            for attr_name, val in vars(klass).items():
                if attr_name not in seen_names and inspect.isfunction(val):
                    seen_names.add(attr_name)
                    ordered_methods.append((attr_name, val))

        for attr_name, _unbound_method in ordered_methods:
            # Read the decorator metadata from the most-derived definition
            # (getattr resolves the MRO) so a subclass that overrides a route
            # method controls its own RouteInfo, instead of inheriting the base
            # class's first-seen one while binding the override's implementation.
            # Đọc metadata từ định nghĩa dẫn xuất nhất (getattr theo MRO) để
            # subclass override route tự quyết RouteInfo, thay vì lấy của lớp cha.
            route_info: RouteInfo | None = getattr(
                getattr(cls, attr_name, None), ROUTE_ATTR, None
            )
            if route_info is None:
                continue

            bound_method = getattr(instance, attr_name)
            handler = _make_handler(bound_method)

            router.add_api_route(
                path=route_info.path,
                endpoint=handler,
                methods=[route_info.method],
                status_code=route_info.status_code,
                response_model=route_info.response_model,
                summary=route_info.summary,
                description=route_info.description,
                deprecated=route_info.deprecated,
                include_in_schema=route_info.include_in_schema,
                tags=route_info.tags,
                name=route_info.name,
                operation_id=route_info.operation_id,
            )

        return router
