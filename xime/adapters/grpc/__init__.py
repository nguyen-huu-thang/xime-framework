from __future__ import annotations

# Guard: translate a missing grpcio into a message that names the extra. Raises
# ImportError (not the RuntimeError used by mqtt/modbus/opcua) because this fires
# at IMPORT time, where ImportError is the correct type — and because the
# framework itself relies on `except ImportError` around this package to mean
# "the grpc extra is absent, skip the check" (core/bootstrap/application.py,
# core/bootstrap/orchestrator.py). Switching to RuntimeError would turn those
# graceful skips into start-up crashes for every app without the extra.
# Guard dịch lỗi thiếu grpcio thành thông điệp có tên extra. Ném ImportError chứ
# không phải RuntimeError như mqtt/modbus/opcua vì chỗ này nổ lúc IMPORT, và vì
# chính framework dựa vào `except ImportError` quanh package này để hiểu "chưa
# cài extra grpc, bỏ qua" - đổi sang RuntimeError là biến những chỗ bỏ qua êm ái
# đó thành lỗi sập lúc khởi động cho mọi app không cài extra.
try:
    from ._adapter import GrpcAdapter as GrpcAdapter
    from .client._config import configure_grpc_clients as configure_grpc_clients
    from .interceptors._config import (
        configure_grpc_error_mappings as configure_grpc_error_mappings,
    )
    from .interceptors._config import (
        configure_grpc_interceptors as configure_grpc_interceptors,
    )
    from .routing._config import configure_grpc_services as configure_grpc_services
    from .tls import GrpcCertificateProvider as GrpcCertificateProvider
    from .tls import ServerCertificates as ServerCertificates
    from .tls import configure_grpc_tls as configure_grpc_tls
except ImportError as exc:  # pragma: no cover - needs an install without the extra
    # Only a missing gRPC stack is translated. An ImportError from anywhere else
    # is a real bug and must not be disguised as a missing dependency.
    if (exc.name or "").split(".")[0] not in {"grpc", "grpc_tools", "google"}:
        raise
    raise ImportError(
        "The gRPC adapter requires grpcio. Run: pip install 'xime[grpc]'"
    ) from exc

__all__ = [
    "GrpcAdapter",
    "GrpcCertificateProvider",
    "ServerCertificates",
    "configure_grpc_services",
    "configure_grpc_clients",
    "configure_grpc_interceptors",
    "configure_grpc_error_mappings",
    "configure_grpc_tls",
]
