"""
gRPC Client SDK - runtime + generator + managed channel.

Public API:
    from xime.adapters.grpc.client import SdkRuntime           # dùng bởi SDK sinh ra
    from xime.adapters.grpc.client import generate_client_sdk  # dùng bởi CLI
    from xime.adapters.grpc.client import XimeGrpcChannel      # channel có quản lý
    from xime.adapters.grpc import configure_grpc_clients      # đăng ký client vào DI

Sinh SDK từ .proto (+ contract.json sidecar nếu có):
    xime grpc client --proto contracts/trust --out clients/trust

Đăng ký vào DI (config/grpc.py) + YAML grpc.clients.<id>:
    configure_grpc_clients("trust", KeyClient, CertClient)
"""

from ._channel import XimeGrpcChannel
from ._codegen import ClientGenResult, generate_client_sdk
from ._config import GrpcClientConfig, GrpcClientTlsConfig, configure_grpc_clients
from ._runtime import SdkRuntime

__all__ = [
    "ClientGenResult",
    "GrpcClientConfig",
    "GrpcClientTlsConfig",
    "SdkRuntime",
    "XimeGrpcChannel",
    "configure_grpc_clients",
    "generate_client_sdk",
]
