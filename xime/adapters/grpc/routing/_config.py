from __future__ import annotations

from collections.abc import Callable
from typing import Any


class _GrpcServiceRegistry:
    """Module-level singleton that stores gRPC service bindings and packages.

    Read by GrpcAdapter during startup to register servicers with the gRPC server.

    'packages' is advisory metadata — the developer still must add the same
    packages to dependency.scan() so the DI container creates handler instances.
    'bindings' maps each handler class to the generated add_XxxServicer_to_server
    function from the proto-generated stub module.
    """

    def __init__(self) -> None:
        self._packages: list[str] = []
        self._bindings: dict[type, Callable[..., Any]] = {}

    def register(
        self,
        packages: list[str],
        bindings: dict[type, Callable[..., Any]],
    ) -> None:
        """Merge packages and bindings into the registry.

        Safe to call multiple times — entries accumulate across calls.
        Later bindings for the same class overwrite earlier ones.
        """
        self._packages.extend(packages)
        self._bindings.update(bindings)

    def get_packages(self) -> list[str]:
        return list(self._packages)

    def get_bindings(self) -> dict[type, Callable[..., Any]]:
        return dict(self._bindings)

    def reset(self) -> None:
        """Clear all registrations - test cleanup only."""
        self._packages.clear()
        self._bindings.clear()


grpc_service_registry = _GrpcServiceRegistry()


def configure_grpc_services(
    packages: list[str],
    bindings: dict[type, Callable[..., Any]],
) -> None:
    """Register gRPC handler classes and their proto add-servicer functions.

    Call this once (or more) in your config layer (e.g. config/routing.py).
    GrpcAdapter reads this registry after DI startup and adds each handler
    to the grpc.aio.Server via the corresponding add_XxxServicer_to_server call.

    Follows the same explicit-call pattern as configure_controllers() and
    configure_openapi(): no auto-scan magic, developer opts in explicitly.

    Note: handler packages must also be passed to dependency.scan() so the DI
    container creates instances before service registration runs.

    Example:
        from xime.adapters.grpc.routing import configure_grpc_services
        import proto.user_pb2_grpc as user_grpc
        from api.grpc.user_servicer import UserServicer

        configure_grpc_services(
            packages=["api.grpc"],
            bindings={
                UserServicer: user_grpc.add_UserServiceServicer_to_server,
            },
        )
    """
    grpc_service_registry.register(packages, bindings)
