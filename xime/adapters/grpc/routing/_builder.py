from __future__ import annotations

from collections.abc import Callable
from typing import Any

import grpc.aio

from xime.core.bootstrap.application import Application


class GrpcServiceBuilder:
    """Registers gRPC handler instances with a grpc.aio.Server.

    For each (HandlerClass, add_fn) pair in the binding dict:
      1. Skip handlers whose server_id class variable does not match this builder's server_id.
      2. Fetch the DI-managed singleton from the Application container.
      3. Call add_fn(instance, server) — the generated proto helper that
         attaches the servicer to the server's method dispatch table.

    Handlers without a server_id class variable default to "default".

    Duck typing is sufficient: grpc's add_XxxServicer_to_server only
    requires that the object has the right method names, not that it
    inherits from the generated base class.
    """

    def __init__(self, application: Application, server_id: str = "default") -> None:
        self._application = application
        self._server_id = server_id

    def register_all(
        self,
        server: grpc.aio.Server,
        bindings: dict[type, Callable[..., Any]],
    ) -> None:
        """Register handlers matching this builder's server_id with the given server."""
        for handler_cls, add_fn in bindings.items():
            if getattr(handler_cls, "server_id", "default") != self._server_id:
                continue
            instance = self._application.get(handler_cls)
            add_fn(instance, server)
