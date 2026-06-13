from __future__ import annotations

from pydantic import BaseModel, Field

from xime.core.config.runtime import RuntimeConfig


class GrpcTlsConfig(BaseModel):
    """TLS / mTLS configuration for the gRPC server.

    All fields map 1-to-1 with the 'grpc.tls' block in application.yml:

        grpc:
          tls:
            enabled: true
            cert_file: certs/server.crt
            key_file:  certs/server.key
            ca_file:   certs/ca.crt   # optional — needed for mTLS
            mutual:    true            # true = require client certificate
    """

    enabled: bool = False
    cert_file: str = ""
    key_file: str = ""
    ca_file: str | None = None
    mutual: bool = False


class GrpcServerConfig(BaseModel):
    """Runtime configuration for the gRPC adapter.

    Populated automatically from the 'grpc' key in application.yml.
    All fields have sensible defaults so the block is optional.

    The default server reads the top-level block; non-default servers read
    their own block under 'grpc.servers.<server_id>' (TLS only - port stays
    in the GrpcAdapter constructor for non-default servers).
    Server default đọc block ngoài cùng; server khác đọc block riêng dưới
    'grpc.servers.<server_id>' (chỉ TLS - port của server khác default vẫn
    khai trong constructor của GrpcAdapter).

        grpc:
          port: 50051
          max_workers: 10
          tls:
            enabled: true
            cert_file: certs/server.crt
            key_file:  certs/server.key
            ca_file:   certs/ca.crt
            mutual:    true
          servers:
            internal:
              tls:
                enabled: true
                mutual: true
    """

    port: int = 50051
    max_workers: int = 10
    tls: GrpcTlsConfig = Field(default_factory=GrpcTlsConfig)

    @classmethod
    def from_runtime(cls, runtime: RuntimeConfig) -> GrpcServerConfig:
        """Build a GrpcServerConfig from a RuntimeConfig instance.

        Reads the 'grpc' key via dot-notation. Returns all-defaults when the
        key is absent or not a dict (e.g. grpc: null in YAML).
        """
        raw = runtime.get("grpc")
        if not isinstance(raw, dict):
            return cls()
        return cls.model_validate(raw)

    @classmethod
    def for_server(cls, runtime: RuntimeConfig, server_id: str) -> GrpcServerConfig:
        """Build the config for a non-default server from grpc.servers.<server_id>.

        Returns all-defaults (TLS disabled) when the block is absent, so the
        previous behavior - non-default servers without YAML - keeps working.
        The caller overrides port from the adapter constructor.
        Trả về toàn default (TLS tắt) khi không có block - giữ tương thích với
        hành vi cũ. Port do caller override từ constructor của adapter.
        """
        raw = runtime.get("grpc")
        if not isinstance(raw, dict):
            return cls()
        servers = raw.get("servers")
        if not isinstance(servers, dict):
            return cls()
        block = servers.get(server_id)
        if not isinstance(block, dict):
            return cls()
        return cls.model_validate(block)
