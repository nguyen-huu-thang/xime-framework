from __future__ import annotations

from typing import Any

import grpc


class _GrpcInterceptorRegistry:
    """Module-level singleton that stores user-declared gRPC interceptors
    and exception-to-StatusCode mappings.

    GrpcAdapter reads this registry at startup and prepends the built-in
    RequestContextInterceptor and ErrorMappingInterceptor before the
    user-declared ones so that context setup always runs outermost.
    """

    def __init__(self) -> None:
        self._interceptors: list[grpc.aio.ServerInterceptor] = []
        self._error_mappings: dict[type[Exception], grpc.StatusCode] = {}

    def add_interceptors(self, interceptors: list[grpc.aio.ServerInterceptor]) -> None:
        self._interceptors.extend(interceptors)

    def set_error_mappings(self, mappings: dict[type[Exception], grpc.StatusCode]) -> None:
        self._error_mappings.update(mappings)

    def get_interceptors(self) -> list[grpc.aio.ServerInterceptor]:
        return list(self._interceptors)

    def get_error_mappings(self) -> dict[type[Exception], grpc.StatusCode]:
        return dict(self._error_mappings)


grpc_interceptor_registry = _GrpcInterceptorRegistry()


def configure_grpc_interceptors(interceptors: list[grpc.aio.ServerInterceptor]) -> None:
    """Register user-defined gRPC server interceptors.

    These are appended after the built-in interceptors (RequestContext, ErrorMapping)
    that GrpcAdapter always installs. Follows the same configure_*() pattern used
    across all Xime adapters.

    Example:
        from xime.adapters.grpc.interceptors import configure_grpc_interceptors

        configure_grpc_interceptors([LoggingInterceptor(), TracingInterceptor()])
    """
    grpc_interceptor_registry.add_interceptors(interceptors)


def configure_grpc_error_mappings(
    mappings: dict[type[Exception], grpc.StatusCode],
) -> None:
    """Declare which exception types map to which gRPC StatusCodes.

    The ErrorMappingInterceptor reads these mappings and converts matching
    exceptions to gRPC status codes automatically. Unmapped exceptions become
    StatusCode.INTERNAL.

    Example:
        from xime.adapters.grpc.interceptors import configure_grpc_error_mappings
        import grpc

        configure_grpc_error_mappings({
            NotFoundException:   grpc.StatusCode.NOT_FOUND,
            ValidationException: grpc.StatusCode.INVALID_ARGUMENT,
        })
    """
    grpc_interceptor_registry.set_error_mappings(mappings)
