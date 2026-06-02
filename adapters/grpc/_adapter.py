from __future__ import annotations

import grpc.aio

from core.bootstrap.application import Application
from core.config.runtime import RuntimeConfig

from ._config import GrpcServerConfig
from .interceptors._config import grpc_interceptor_registry
from .interceptors._context import RequestContextInterceptor
from .interceptors._error import ErrorMappingInterceptor
from .routing._builder import GrpcServiceBuilder
from .routing._config import grpc_service_registry
from .routing._scanner import GrpcServiceScanner
from .tls._credentials import build_server_credentials


class GrpcAdapter:
    """Manages the lifecycle of a grpc.aio.Server.

    Integrates with Xime's DI container and lifecycle system:
      - start(): build interceptor stack, register servicers, bind port, start server
      - stop():  graceful shutdown with a 5-second grace period

    Interceptor order (outermost first):
      1. RequestContextInterceptor  — always present, sets request_id + cleans up
      2. ErrorMappingInterceptor    — always present, maps exceptions → StatusCode
      3. user-declared interceptors — registered via configure_grpc_interceptors()

    TLS / mTLS is configured entirely through application.yml:
      grpc.tls.enabled = false  → insecure port (default)
      grpc.tls.mutual  = false  → TLS (server-side only)
      grpc.tls.mutual  = true   → mTLS (both sides authenticate)

    Usage in main.py:
        from xime.adapters.grpc import GrpcAdapter
        from core.bootstrap.application import Application

        app = Application()
        adapter = GrpcAdapter(app)
        # adapter.start() / adapter.stop() are called by Application.use() hooks
    """

    def __init__(self, application: Application) -> None:
        self._application = application
        self._server: grpc.aio.Server | None = None

    async def start(self, runtime: RuntimeConfig) -> None:
        """Build and start the gRPC server.

        Called by Application after the DI container is fully built, so
        GrpcServiceBuilder can fetch handler instances from the container.
        """
        config = GrpcServerConfig.from_runtime(runtime)
        interceptors = self._build_interceptors()

        self._server = grpc.aio.server(interceptors=interceptors)

        # Validate packages are importable before trying to fetch instances.
        scanner = GrpcServiceScanner()
        scanner.validate_packages(*grpc_service_registry.get_packages())

        # Register every declared servicer with the server.
        builder = GrpcServiceBuilder(self._application)
        builder.register_all(self._server, grpc_service_registry.get_bindings())

        # Bind port — TLS/mTLS or plain.
        if config.tls.enabled:
            credentials = build_server_credentials(config.tls)
            self._server.add_secure_port(f"[::]:{config.port}", credentials)
        else:
            self._server.add_insecure_port(f"[::]:{config.port}")

        await self._server.start()

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
