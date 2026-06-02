from __future__ import annotations

from pydantic import BaseModel, Field

from core.config.runtime import RuntimeConfig


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

        grpc:
          port: 50051
          max_workers: 10
          tls:
            enabled: true
            cert_file: certs/server.crt
            key_file:  certs/server.key
            ca_file:   certs/ca.crt
            mutual:    true
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
