from __future__ import annotations

from typing import TYPE_CHECKING

import grpc.aio

from ._config import GrpcServerConfig
from .interceptors._config import grpc_interceptor_registry
from .interceptors._context import RequestContextInterceptor
from .interceptors._error import ErrorMappingInterceptor
from .routing._builder import GrpcServiceBuilder
from .routing._config import grpc_service_registry
from .routing._scanner import GrpcServiceScanner
from .tls._credentials import build_server_credentials

if TYPE_CHECKING:
    from core.bootstrap.application import Application


class GrpcAdapter:
    """gRPC adapter — wraps grpc.aio.Server into the Xime adapter lifecycle.

    Register via app.use() and start via app.run():

        app = Application()
        app.use(WebAdapter())
        app.use(GrpcAdapter())
        app.run()

    Both adapters start concurrently after the DI container is fully built.

    TLS / mTLS is configured entirely through application.yml:
        grpc:
          port: 50051
          tls:
            enabled: true
            cert_file: certs/server.crt
            key_file:  certs/server.key
            ca_file:   certs/ca.crt   # optional — needed for mTLS
            mutual:    true            # true = require client certificate

    Interceptor order (outermost first):
        1. RequestContextInterceptor  — always present, sets request_id + cleans up
        2. ErrorMappingInterceptor    — always present, maps exceptions → StatusCode
        3. user-declared interceptors — registered via configure_grpc_interceptors()
    """

    def __init__(self) -> None:
        self._server: grpc.aio.Server | None = None
        self._app: "Application | None" = None

    # ------------------------------------------------------------------
    # Adapter protocol
    # ------------------------------------------------------------------

    async def start(self, app: "Application") -> None:
        """Build and start the gRPC server.

        Called by Application._run_async() after the DI container is fully built,
        so GrpcServiceBuilder can fetch handler instances from the container.
        Blocks until the server is stopped (via stop() or SIGINT).
        """
        from core.config.runtime import RuntimeConfig
        runtime: RuntimeConfig = app.get(RuntimeConfig)  # type: ignore[assignment]

        self._app = app
        config = GrpcServerConfig.from_runtime(runtime)
        interceptors = self._build_interceptors()

        self._server = grpc.aio.server(interceptors=interceptors)

        # Validate packages are importable before trying to fetch instances.
        scanner = GrpcServiceScanner()
        scanner.validate_packages(*grpc_service_registry.get_packages())

        # Register every declared servicer with the server.
        builder = GrpcServiceBuilder(app)
        builder.register_all(self._server, grpc_service_registry.get_bindings())

        # Bind port — TLS/mTLS or plain.
        if config.tls.enabled:
            credentials = build_server_credentials(config.tls)
            self._server.add_secure_port(f"[::]:{config.port}", credentials)
        else:
            self._server.add_insecure_port(f"[::]:{config.port}")

        await self._server.start()
        await self._server.wait_for_termination()

    async def stop(self) -> None:
        """Gracefully stop the gRPC server.

        Waits up to 5 seconds for in-flight RPCs to complete before forcing
        a shutdown. No-op if start() was never called.
        """
        if self._server is not None:
            await self._server.stop(grace=5)
            self._server = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_interceptors(self) -> list[grpc.aio.ServerInterceptor]:
        """Compose the full interceptor stack.

        Built-in interceptors always lead so that context setup and error
        handling wrap every user-declared interceptor and every handler.
        """
        mappings = grpc_interceptor_registry.get_error_mappings()
        built_in: list[grpc.aio.ServerInterceptor] = [
            RequestContextInterceptor(),
            ErrorMappingInterceptor(mappings),
        ]
        return built_in + grpc_interceptor_registry.get_interceptors()
