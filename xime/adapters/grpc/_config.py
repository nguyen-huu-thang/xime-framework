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


class GrpcServerKeepaliveConfig(BaseModel):
    """HTTP/2 keepalive + client ping policy for the gRPC server (off by default).

        grpc:
          keepalive:
            time_ms: 30000                        # server pings idle peers; 0 = off
            timeout_ms: 20000
            permit_without_calls: true            # ping even with no active RPC
            min_ping_interval_without_data_ms: 30000  # tolerate client pings this often

    The last key is the one to remember when a client enables keepalive: gRPC
    servers default to 5 minutes and answer GOAWAY "too_many_pings" to anything
    faster, which kills exactly the long-lived streams keepalive was meant to
    protect. Set it to the client's time_ms (or lower).
    Khoá cuối là thứ phải nhớ khi client bật keepalive: server mặc định 5 phút
    và trả GOAWAY "too_many_pings" với nhịp nhanh hơn - giết đúng những luồng
    dài mà keepalive sinh ra để bảo vệ. Đặt bằng time_ms của client (hoặc thấp hơn).
    """

    time_ms: int = 0
    timeout_ms: int = 20000
    permit_without_calls: bool = False
    min_ping_interval_without_data_ms: int = 0  # 0 = leave the gRPC default

    def server_options(self) -> list[tuple[str, int]]:
        """gRPC server args; empty when nothing is configured (defaults intact)."""
        options: list[tuple[str, int]] = []
        if self.time_ms > 0:
            options += [
                ("grpc.keepalive_time_ms", self.time_ms),
                ("grpc.keepalive_timeout_ms", self.timeout_ms),
                ("grpc.keepalive_permit_without_calls", 1 if self.permit_without_calls else 0),
            ]
        if self.min_ping_interval_without_data_ms > 0:
            options.append(
                ("grpc.http2.min_ping_interval_without_data_ms",
                 self.min_ping_interval_without_data_ms)
            )
        return options


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
    keepalive: GrpcServerKeepaliveConfig = Field(default_factory=GrpcServerKeepaliveConfig)

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
