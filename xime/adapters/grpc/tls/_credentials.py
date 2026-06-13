from __future__ import annotations

import logging
from pathlib import Path

import grpc

from xime.adapters.grpc._config import GrpcTlsConfig

from ._provider import GrpcCertificateProvider, ServerCertificates

_log = logging.getLogger(__name__)


def build_server_credentials(tls: GrpcTlsConfig) -> grpc.ServerCredentials:
    """Build a grpc.ServerCredentials from GrpcTlsConfig.

    TLS (server-side only):  tls.mutual = False, tls.ca_file may be omitted.
    mTLS (both sides):       tls.mutual = True,  tls.ca_file required to verify clients.

    Raises FileNotFoundError when cert_file, key_file, or ca_file paths do not exist.
    """
    cert = Path(tls.cert_file).read_bytes()
    key = Path(tls.key_file).read_bytes()
    ca = Path(tls.ca_file).read_bytes() if tls.ca_file else None

    return grpc.ssl_server_credentials(
        [(key, cert)],
        root_certificates=ca,
        require_client_auth=tls.mutual,
    )


def build_dynamic_server_credentials(
    provider: GrpcCertificateProvider,
    mutual: bool,
) -> grpc.ServerCredentials:
    """Build server credentials that re-read the provider on every new handshake.

    Wraps grpc.dynamic_ssl_server_credentials: gRPC core invokes the fetcher
    for each NEW TLS handshake. The fetcher compares provider.version() with
    the last seen version - unchanged returns None (keep current configuration,
    cost of a string compare), changed rebuilds the certificate configuration
    from provider.current(). Established sessions are never affected.
    Bọc grpc.dynamic_ssl_server_credentials: gRPC core gọi fetcher ở mỗi
    handshake MỚI. Fetcher so provider.version() với version lần trước - không
    đổi trả None (giữ config cũ, chi phí so chuỗi), đổi thì build lại config từ
    provider.current(). Phiên đã thiết lập không bị ảnh hưởng.

    Raises RuntimeError when mutual=True but the provider supplies no root CA
    (cannot verify client certificates). Propagates provider errors so the
    adapter can fail fast at startup.
    """
    initial_version = provider.version()
    initial_config = _certificate_configuration(provider.current(), mutual)

    # Mutable cell shared with the fetcher closure.
    # Ô trạng thái chia sẻ với closure fetcher.
    last_version = [initial_version]

    def fetch() -> grpc.ServerCertificateConfiguration | None:
        try:
            version = provider.version()
            if version == last_version[0]:
                return None
            config = _certificate_configuration(provider.current(), mutual)
            last_version[0] = version
            _log.info("gRPC server certificate rotated (version=%s).", version)
            return config
        except Exception:
            # A failing fetcher must not kill new handshakes - keep serving
            # with the current certificate and let the app's rotation
            # machinery alert on the underlying problem.
            # Fetcher lỗi không được giết handshake mới - giữ cert hiện tại,
            # việc cảnh báo thuộc về bộ máy rotation của app.
            _log.exception("Certificate provider failed; keeping current certificate.")
            return None

    return grpc.dynamic_ssl_server_credentials(
        initial_config,
        fetch,
        require_client_authentication=mutual,
    )


def _certificate_configuration(
    certs: ServerCertificates,
    mutual: bool,
) -> grpc.ServerCertificateConfiguration:
    if mutual and not certs.root_ca_pem:
        raise RuntimeError(
            "mTLS (mutual=true) requires root_ca_pem from the certificate "
            "provider to verify client certificates, but it returned None."
        )
    key = certs.private_key_pem.encode("utf-8")
    chain = certs.cert_chain_pem.encode("utf-8")
    ca = certs.root_ca_pem.encode("utf-8") if certs.root_ca_pem else None
    return grpc.ssl_server_certificate_configuration(
        [(key, chain)],
        root_certificates=ca,
    )
