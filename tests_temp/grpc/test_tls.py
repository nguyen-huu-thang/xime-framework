"""
Test build_server_credentials():

  - Trả về grpc.ServerCredentials (không raise)
  - TLS thông thường: require_client_auth=False khi mutual=False
  - mTLS: require_client_auth=True khi mutual=True
  - Không có ca_file: root_certificates=None (server-side TLS only)
  - Có ca_file: root_certificates chứa nội dung file
  - FileNotFoundError khi cert_file không tồn tại
  - FileNotFoundError khi key_file không tồn tại
  - FileNotFoundError khi ca_file được đặt nhưng không tồn tại
"""
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import grpc
import pytest

from adapters.grpc._config import GrpcTlsConfig
from adapters.grpc.tls._credentials import build_server_credentials


# ---------------------------------------------------------------------------
# Fixtures — tạo file cert/key giả trong tmp_path
# ---------------------------------------------------------------------------

@pytest.fixture()
def tls_files(tmp_path: Path):
    """Tạo cert, key, ca file giả để dùng trong test."""
    cert = tmp_path / "server.crt"
    key  = tmp_path / "server.key"
    ca   = tmp_path / "ca.crt"

    cert.write_bytes(b"FAKE_CERT")
    key.write_bytes(b"FAKE_KEY")
    ca.write_bytes(b"FAKE_CA")

    return {"cert": str(cert), "key": str(key), "ca": str(ca)}


# ---------------------------------------------------------------------------
# Happy path — trả về ServerCredentials
# ---------------------------------------------------------------------------

class TestBuildServerCredentials:
    def test_returns_server_credentials_object(self, tls_files):
        tls = GrpcTlsConfig(
            enabled=True,
            cert_file=tls_files["cert"],
            key_file=tls_files["key"],
        )
        result = build_server_credentials(tls)
        assert isinstance(result, grpc.ServerCredentials)

    def test_tls_without_ca_passes_none_as_root_certificates(self, tls_files):
        """Server-side TLS only: ca_file không có → root_certificates=None."""
        tls = GrpcTlsConfig(
            enabled=True,
            cert_file=tls_files["cert"],
            key_file=tls_files["key"],
            ca_file=None,
            mutual=False,
        )
        with patch("grpc.ssl_server_credentials") as mock_ssl:
            mock_ssl.return_value = MagicMock(spec=grpc.ServerCredentials)
            build_server_credentials(tls)
            mock_ssl.assert_called_once_with(
                [(b"FAKE_KEY", b"FAKE_CERT")],
                root_certificates=None,
                require_client_auth=False,
            )

    def test_mtls_passes_ca_bytes_as_root_certificates(self, tls_files):
        """mTLS: ca_file có → root_certificates = nội dung file ca."""
        tls = GrpcTlsConfig(
            enabled=True,
            cert_file=tls_files["cert"],
            key_file=tls_files["key"],
            ca_file=tls_files["ca"],
            mutual=True,
        )
        with patch("grpc.ssl_server_credentials") as mock_ssl:
            mock_ssl.return_value = MagicMock(spec=grpc.ServerCredentials)
            build_server_credentials(tls)
            mock_ssl.assert_called_once_with(
                [(b"FAKE_KEY", b"FAKE_CERT")],
                root_certificates=b"FAKE_CA",
                require_client_auth=True,
            )

    def test_mutual_false_sets_require_client_auth_false(self, tls_files):
        tls = GrpcTlsConfig(
            enabled=True,
            cert_file=tls_files["cert"],
            key_file=tls_files["key"],
            mutual=False,
        )
        with patch("grpc.ssl_server_credentials") as mock_ssl:
            mock_ssl.return_value = MagicMock(spec=grpc.ServerCredentials)
            build_server_credentials(tls)
            _args, kwargs = mock_ssl.call_args
            assert kwargs["require_client_auth"] is False

    def test_mutual_true_sets_require_client_auth_true(self, tls_files):
        tls = GrpcTlsConfig(
            enabled=True,
            cert_file=tls_files["cert"],
            key_file=tls_files["key"],
            ca_file=tls_files["ca"],
            mutual=True,
        )
        with patch("grpc.ssl_server_credentials") as mock_ssl:
            mock_ssl.return_value = MagicMock(spec=grpc.ServerCredentials)
            build_server_credentials(tls)
            _args, kwargs = mock_ssl.call_args
            assert kwargs["require_client_auth"] is True

    def test_cert_and_key_are_read_as_bytes(self, tls_files):
        """Key và cert phải được pass dưới dạng bytes, không phải str."""
        tls = GrpcTlsConfig(
            enabled=True,
            cert_file=tls_files["cert"],
            key_file=tls_files["key"],
        )
        with patch("grpc.ssl_server_credentials") as mock_ssl:
            mock_ssl.return_value = MagicMock(spec=grpc.ServerCredentials)
            build_server_credentials(tls)
            positional_args = mock_ssl.call_args[0]
            key_cert_pair = positional_args[0][0]  # [(key, cert)][0]
            key_bytes, cert_bytes = key_cert_pair
            assert isinstance(key_bytes, bytes)
            assert isinstance(cert_bytes, bytes)


# ---------------------------------------------------------------------------
# Error path — file không tồn tại
# ---------------------------------------------------------------------------

class TestBuildServerCredentialsErrors:
    def test_raises_when_cert_file_missing(self, tmp_path: Path):
        tls = GrpcTlsConfig(
            enabled=True,
            cert_file=str(tmp_path / "missing.crt"),
            key_file=str(tmp_path / "missing.key"),
        )
        with pytest.raises(FileNotFoundError):
            build_server_credentials(tls)

    def test_raises_when_key_file_missing(self, tmp_path: Path):
        cert = tmp_path / "server.crt"
        cert.write_bytes(b"FAKE_CERT")
        tls = GrpcTlsConfig(
            enabled=True,
            cert_file=str(cert),
            key_file=str(tmp_path / "missing.key"),
        )
        with pytest.raises(FileNotFoundError):
            build_server_credentials(tls)

    def test_raises_when_ca_file_set_but_missing(self, tmp_path: Path):
        cert = tmp_path / "server.crt"
        key  = tmp_path / "server.key"
        cert.write_bytes(b"FAKE_CERT")
        key.write_bytes(b"FAKE_KEY")
        tls = GrpcTlsConfig(
            enabled=True,
            cert_file=str(cert),
            key_file=str(key),
            ca_file=str(tmp_path / "missing_ca.crt"),
            mutual=True,
        )
        with pytest.raises(FileNotFoundError):
            build_server_credentials(tls)

    def test_no_error_when_ca_file_is_none(self, tmp_path: Path):
        """ca_file=None (không set) → không đọc file, không raise."""
        cert = tmp_path / "server.crt"
        key  = tmp_path / "server.key"
        cert.write_bytes(b"FAKE_CERT")
        key.write_bytes(b"FAKE_KEY")
        tls = GrpcTlsConfig(
            enabled=True,
            cert_file=str(cert),
            key_file=str(key),
            ca_file=None,
        )
        with patch("grpc.ssl_server_credentials") as mock_ssl:
            mock_ssl.return_value = MagicMock(spec=grpc.ServerCredentials)
            build_server_credentials(tls)   # không raise
