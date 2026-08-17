from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ServerCertificates:
    """PEM material a gRPC server presents during TLS handshakes.

    Returned by GrpcCertificateProvider.current(). All fields are PEM text
    (with -----BEGIN ...----- headers).
    Chất liệu PEM mà server gRPC trình ra lúc TLS handshake. Trả về từ
    GrpcCertificateProvider.current(). Mọi field là PEM text đầy đủ header.

    root_ca_pem is required for mTLS (mutual=True) to verify client
    certificates; optional for server-side TLS only.
    root_ca_pem bắt buộc khi mTLS (mutual=True) để verify cert của client;
    không bắt buộc nếu chỉ TLS một chiều.
    """

    private_key_pem: str
    cert_chain_pem: str
    root_ca_pem: str | None = None


@runtime_checkable
class GrpcCertificateProvider(Protocol):
    """Source of dynamic TLS certificates for gRPC servers.

    Implementations live in application code (e.g. backed by a certificate
    resolver kept in sync with whatever issues your certificates). The framework
    polls this provider on every NEW TLS handshake - established sessions are
    never affected by rotation (TLS semantics: certificates are only used during
    the handshake).
    Implementation nằm ở code ứng dụng (vd đọc từ resolver đồng bộ với nơi cấp
    cert của bạn). Framework hỏi provider ở mỗi handshake MỚI - phiên đã thiết
    lập không bị ảnh hưởng khi rotate (cert chỉ dùng lúc handshake).

    Contract:
    - version(): cheap identity of the current certificate (e.g. certificate
      id). A changed version means the certificate has rotated. Called on
      every new handshake, so it must be an in-memory read - NEVER a network
      call.
      version(): định danh rẻ của cert hiện tại (vd certificate_id). Đổi
      version nghĩa là đã rotate. Được gọi mỗi handshake mới nên bắt buộc đọc
      memory - KHÔNG BAO GIỜ gọi mạng.
    - current(): the full PEM material for the current version. Only called
      when version() changes (and once at startup).
      current(): toàn bộ PEM của version hiện tại. Chỉ được gọi khi version()
      thay đổi (và một lần lúc startup).

    Register via configure_grpc_tls(provider=YourProvider) in config/grpc.py.
    The provider class must be resolvable from the DI container.
    Đăng ký qua configure_grpc_tls(provider=YourProvider) trong config/grpc.py.
    Class provider phải resolve được từ DI container.
    """

    def version(self) -> str: ...

    def current(self) -> ServerCertificates: ...
