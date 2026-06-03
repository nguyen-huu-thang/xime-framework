from __future__ import annotations

from pathlib import Path

import grpc

from xime.adapters.grpc._config import GrpcTlsConfig


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
