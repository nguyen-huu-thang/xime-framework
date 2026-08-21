from __future__ import annotations

import importlib


class GrpcServiceScanner:
    """Validates that gRPC handler packages are importable.

    Unlike the web ControllerScanner which walks packages looking for
    decorated methods, gRPC handlers have no identifying decorator -
    the binding dict in configure_grpc_services() already enumerates
    every handler class explicitly.

    This scanner's role is narrower: fail fast at startup if a declared
    package cannot be imported, giving a clear error before the DI
    container tries to instantiate handlers.
    """

    def validate_packages(self, *packages: str) -> None:
        """Attempt to import each package; raise ImportError if any fail."""
        for package in packages:
            try:
                importlib.import_module(package)
            except ImportError as exc:
                raise ImportError(
                    f"gRPC service package '{package}' could not be imported: {exc}"
                ) from exc
