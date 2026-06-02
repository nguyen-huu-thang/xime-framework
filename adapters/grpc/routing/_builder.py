from __future__ import annotations

from typing import Any, Callable

import grpc.aio

from core.bootstrap.application import Application


class GrpcServiceBuilder:
    """Registers gRPC handler instances with a grpc.aio.Server.

    For each (HandlerClass, add_fn) pair in the binding dict:
      1. Fetch the DI-managed singleton from the Application container.
      2. Call add_fn(instance, server) — the generated proto helper that
         attaches the servicer to the server's method dispatch table.

    Duck typing is sufficient: grpc's add_XxxServicer_to_server only
    requires that the object has the right method names, not that it
    inherits from the generated base class.
    """

    def __init__(self, application: Application) -> None:
        self._application = application

    def register_all(
        self,
        server: grpc.aio.Server,
        bindings: dict[type, Callable[..., Any]],
    ) -> None:
        """Register every handler in bindings with the given server."""
        for handler_cls, add_fn in bindings.items():
            instance = self._application.get(handler_cls)
            add_fn(instance, server)
