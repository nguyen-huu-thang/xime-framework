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

from xime.adapters.grpc._config import GrpcTlsConfig
from xime.adapters.grpc.tls._credentials import build_server_credentials


# ---------------------------------------------------------------------------
# Fixtures - tạo file cert/key giả trong tmp_path
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
# Happy path - trả về ServerCredentials
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
# Error path - file không tồn tại
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


# ---------------------------------------------------------------------------
# Dynamic credentials - provider + fetcher (cert rotation không restart)
# ---------------------------------------------------------------------------

from xime.adapters.grpc.tls._config import _GrpcTlsRegistry, configure_grpc_tls, grpc_tls_registry
from xime.adapters.grpc.tls._credentials import build_dynamic_server_credentials
from xime.adapters.grpc.tls._provider import ServerCertificates


class FakeProvider:
    """Provider giả: cert trong memory, rotate() đổi version + chất liệu."""

    def __init__(self, root_ca: str | None = "CA_V1"):
        self._version = "v1"
        self._certs = ServerCertificates(
            private_key_pem="KEY_V1",
            cert_chain_pem="CERT_V1",
            root_ca_pem=root_ca,
        )
        self.current_calls = 0

    def version(self) -> str:
        return self._version

    def current(self) -> ServerCertificates:
        self.current_calls += 1
        return self._certs

    def rotate(self, version: str, certs: ServerCertificates) -> None:
        self._version = version
        self._certs = certs


class TestBuildDynamicServerCredentials:
    def test_returns_server_credentials_object(self):
        result = build_dynamic_server_credentials(FakeProvider(), mutual=True)
        assert isinstance(result, grpc.ServerCredentials)

    def test_initial_config_built_from_provider(self):
        provider = FakeProvider()
        with patch("grpc.dynamic_ssl_server_credentials") as mock_dyn, \
             patch("grpc.ssl_server_certificate_configuration") as mock_cfg:
            build_dynamic_server_credentials(provider, mutual=True)
            mock_cfg.assert_called_once_with(
                [(b"KEY_V1", b"CERT_V1")],
                root_certificates=b"CA_V1",
            )
            _args, kwargs = mock_dyn.call_args
            assert kwargs["require_client_authentication"] is True
        assert provider.current_calls == 1

    def test_mutual_false_passed_through(self):
        with patch("grpc.dynamic_ssl_server_credentials") as mock_dyn:
            build_dynamic_server_credentials(FakeProvider(), mutual=False)
            _args, kwargs = mock_dyn.call_args
            assert kwargs["require_client_authentication"] is False

    def test_mutual_without_root_ca_raises(self):
        """mTLS mà provider không trả root CA → fail fast."""
        with pytest.raises(RuntimeError, match="root_ca_pem"):
            build_dynamic_server_credentials(FakeProvider(root_ca=None), mutual=True)

    def test_tls_only_without_root_ca_is_allowed(self):
        """TLS một chiều (mutual=False) không cần root CA."""
        result = build_dynamic_server_credentials(FakeProvider(root_ca=None), mutual=False)
        assert isinstance(result, grpc.ServerCredentials)

    def _capture_fetcher(self, provider, mutual=True):
        """Build dynamic credentials và bắt lấy fetcher closure."""
        with patch("grpc.dynamic_ssl_server_credentials") as mock_dyn:
            build_dynamic_server_credentials(provider, mutual=mutual)
            initial_config, fetcher = mock_dyn.call_args[0]
        return initial_config, fetcher

    def test_fetcher_returns_none_when_version_unchanged(self):
        provider = FakeProvider()
        _initial, fetcher = self._capture_fetcher(provider)

        assert fetcher() is None
        assert fetcher() is None
        # current() chỉ được gọi 1 lần lúc build initial, không gọi lại
        assert provider.current_calls == 1

    def test_fetcher_returns_new_config_when_version_changes(self):
        provider = FakeProvider()
        _initial, fetcher = self._capture_fetcher(provider)

        provider.rotate("v2", ServerCertificates("KEY_V2", "CERT_V2", "CA_V2"))
        with patch("grpc.ssl_server_certificate_configuration") as mock_cfg:
            sentinel = MagicMock()
            mock_cfg.return_value = sentinel
            result = fetcher()
            assert result is sentinel
            mock_cfg.assert_called_once_with(
                [(b"KEY_V2", b"CERT_V2")],
                root_certificates=b"CA_V2",
            )
        # Sau khi nhận version mới, handshake tiếp theo không rebuild nữa
        assert fetcher() is None

    def test_fetcher_swallows_provider_errors_and_keeps_current(self):
        """Provider lỗi giữa chừng → fetcher trả None, không giết handshake."""
        provider = FakeProvider()
        _initial, fetcher = self._capture_fetcher(provider)

        def boom():
            raise RuntimeError("resolver empty")

        provider.version = boom
        assert fetcher() is None   # không raise


# ---------------------------------------------------------------------------
# TLS registry - configure_grpc_tls + fallback per-server
# ---------------------------------------------------------------------------

class TestGrpcTlsRegistry:
    def test_default_provider_applies_to_all_servers(self):
        registry = _GrpcTlsRegistry()
        registry.set_provider(FakeProvider)
        assert registry.get_provider("default") is FakeProvider
        assert registry.get_provider("internal") is FakeProvider

    def test_server_specific_provider_overrides_default(self):
        class PublicProvider: ...

        registry = _GrpcTlsRegistry()
        registry.set_provider(FakeProvider)
        registry.set_provider(PublicProvider, server_id="public")
        assert registry.get_provider("public") is PublicProvider
        assert registry.get_provider("internal") is FakeProvider

    def test_no_provider_returns_none(self):
        registry = _GrpcTlsRegistry()
        assert registry.get_provider("default") is None

    def test_configure_grpc_tls_writes_global_registry(self):
        configure_grpc_tls(provider=FakeProvider)
        assert grpc_tls_registry.get_provider("default") is FakeProvider
        # conftest reset_grpc_tls_registry sẽ dọn dẹp

    def test_reset_clears_registrations(self):
        registry = _GrpcTlsRegistry()
        registry.set_provider(FakeProvider)
        registry.reset()
        assert registry.get_provider("default") is None
