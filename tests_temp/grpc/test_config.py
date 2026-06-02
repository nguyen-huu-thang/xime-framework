"""
Test GrpcTlsConfig và GrpcServerConfig:

  GrpcTlsConfig:
    - default: disabled, cert/key rỗng, ca_file None, mutual False
    - parse đúng tất cả fields từ dict

  GrpcServerConfig:
    - default: port=50051, max_workers=10, tls=GrpcTlsConfig()
    - from_runtime() với grpc block đầy đủ
    - from_runtime() với grpc block chỉ một phần → missing fields dùng default
    - from_runtime() khi không có key 'grpc' → trả về toàn default
    - from_runtime() khi grpc: null trong YAML (value = None) → trả về toàn default
    - from_runtime() với tls block lồng nhau đầy đủ
    - from_runtime() với mTLS bật (mutual=true)
    - GrpcServerConfig.tls là GrpcTlsConfig instance (không phải dict)
"""
import pytest

from adapters.grpc._config import GrpcServerConfig, GrpcTlsConfig
from core.config.runtime import RuntimeConfig


# ---------------------------------------------------------------------------
# GrpcTlsConfig — giá trị mặc định
# ---------------------------------------------------------------------------

class TestGrpcTlsConfigDefaults:
    def test_enabled_defaults_to_false(self):
        cfg = GrpcTlsConfig()
        assert cfg.enabled is False

    def test_cert_file_defaults_to_empty_string(self):
        cfg = GrpcTlsConfig()
        assert cfg.cert_file == ""

    def test_key_file_defaults_to_empty_string(self):
        cfg = GrpcTlsConfig()
        assert cfg.key_file == ""

    def test_ca_file_defaults_to_none(self):
        cfg = GrpcTlsConfig()
        assert cfg.ca_file is None

    def test_mutual_defaults_to_false(self):
        cfg = GrpcTlsConfig()
        assert cfg.mutual is False


# ---------------------------------------------------------------------------
# GrpcTlsConfig — parse từ dict
# ---------------------------------------------------------------------------

class TestGrpcTlsConfigParsing:
    def test_parse_all_fields(self):
        cfg = GrpcTlsConfig.model_validate({
            "enabled": True,
            "cert_file": "certs/server.crt",
            "key_file": "certs/server.key",
            "ca_file": "certs/ca.crt",
            "mutual": True,
        })
        assert cfg.enabled is True
        assert cfg.cert_file == "certs/server.crt"
        assert cfg.key_file == "certs/server.key"
        assert cfg.ca_file == "certs/ca.crt"
        assert cfg.mutual is True

    def test_parse_partial_uses_defaults_for_missing(self):
        cfg = GrpcTlsConfig.model_validate({"enabled": True, "cert_file": "a.crt"})
        assert cfg.enabled is True
        assert cfg.cert_file == "a.crt"
        assert cfg.key_file == ""
        assert cfg.ca_file is None
        assert cfg.mutual is False

    def test_ca_file_can_be_none_explicitly(self):
        cfg = GrpcTlsConfig.model_validate({"ca_file": None})
        assert cfg.ca_file is None

    def test_mutual_false_means_server_side_tls_only(self):
        cfg = GrpcTlsConfig.model_validate({"enabled": True, "mutual": False})
        assert cfg.mutual is False

    def test_mutual_true_means_mtls(self):
        cfg = GrpcTlsConfig.model_validate({"enabled": True, "mutual": True})
        assert cfg.mutual is True


# ---------------------------------------------------------------------------
# GrpcServerConfig — giá trị mặc định
# ---------------------------------------------------------------------------

class TestGrpcServerConfigDefaults:
    def test_port_defaults_to_50051(self):
        cfg = GrpcServerConfig()
        assert cfg.port == 50051

    def test_max_workers_defaults_to_10(self):
        cfg = GrpcServerConfig()
        assert cfg.max_workers == 10

    def test_tls_defaults_to_disabled_config(self):
        cfg = GrpcServerConfig()
        assert isinstance(cfg.tls, GrpcTlsConfig)
        assert cfg.tls.enabled is False

    def test_each_instance_has_independent_tls(self):
        """Field(default_factory=...) → instances không chia sẻ tls object."""
        a = GrpcServerConfig()
        b = GrpcServerConfig()
        assert a.tls is not b.tls


# ---------------------------------------------------------------------------
# GrpcServerConfig.from_runtime()
# ---------------------------------------------------------------------------

class TestGrpcServerConfigFromRuntime:
    def _runtime(self, data: dict) -> RuntimeConfig:
        return RuntimeConfig.from_dict(data)

    def test_returns_defaults_when_no_grpc_key(self):
        runtime = self._runtime({})
        cfg = GrpcServerConfig.from_runtime(runtime)
        assert cfg.port == 50051
        assert cfg.max_workers == 10
        assert cfg.tls.enabled is False

    def test_returns_defaults_when_grpc_is_null(self):
        """grpc: null → runtime.get('grpc') trả về None → dùng defaults."""
        runtime = self._runtime({"grpc": None})
        cfg = GrpcServerConfig.from_runtime(runtime)
        assert cfg.port == 50051

    def test_parses_port(self):
        runtime = self._runtime({"grpc": {"port": 9090}})
        cfg = GrpcServerConfig.from_runtime(runtime)
        assert cfg.port == 9090

    def test_parses_max_workers(self):
        runtime = self._runtime({"grpc": {"max_workers": 20}})
        cfg = GrpcServerConfig.from_runtime(runtime)
        assert cfg.max_workers == 20

    def test_parses_full_config(self):
        runtime = self._runtime({
            "grpc": {
                "port": 50052,
                "max_workers": 4,
                "tls": {
                    "enabled": True,
                    "cert_file": "certs/server.crt",
                    "key_file": "certs/server.key",
                    "ca_file": "certs/ca.crt",
                    "mutual": True,
                },
            }
        })
        cfg = GrpcServerConfig.from_runtime(runtime)
        assert cfg.port == 50052
        assert cfg.max_workers == 4
        assert cfg.tls.enabled is True
        assert cfg.tls.cert_file == "certs/server.crt"
        assert cfg.tls.key_file == "certs/server.key"
        assert cfg.tls.ca_file == "certs/ca.crt"
        assert cfg.tls.mutual is True

    def test_partial_grpc_block_uses_defaults_for_missing_fields(self):
        runtime = self._runtime({"grpc": {"port": 9000}})
        cfg = GrpcServerConfig.from_runtime(runtime)
        assert cfg.port == 9000
        assert cfg.max_workers == 10   # default
        assert cfg.tls.enabled is False  # default

    def test_tls_block_absent_gives_disabled_tls(self):
        runtime = self._runtime({"grpc": {"port": 50051}})
        cfg = GrpcServerConfig.from_runtime(runtime)
        assert isinstance(cfg.tls, GrpcTlsConfig)
        assert cfg.tls.enabled is False

    def test_tls_only_enabled_no_mutual(self):
        """TLS server-side only: mutual phải False."""
        runtime = self._runtime({
            "grpc": {
                "tls": {
                    "enabled": True,
                    "cert_file": "s.crt",
                    "key_file": "s.key",
                    "mutual": False,
                }
            }
        })
        cfg = GrpcServerConfig.from_runtime(runtime)
        assert cfg.tls.enabled is True
        assert cfg.tls.mutual is False
        assert cfg.tls.ca_file is None

    def test_mtls_requires_ca_file(self):
        """mTLS: mutual=True thường đi kèm ca_file — kiểm tra parse đúng."""
        runtime = self._runtime({
            "grpc": {
                "tls": {
                    "enabled": True,
                    "cert_file": "s.crt",
                    "key_file": "s.key",
                    "ca_file": "ca.crt",
                    "mutual": True,
                }
            }
        })
        cfg = GrpcServerConfig.from_runtime(runtime)
        assert cfg.tls.mutual is True
        assert cfg.tls.ca_file == "ca.crt"

    def test_tls_is_grpc_tls_config_instance(self):
        """tls field phải là GrpcTlsConfig, không phải dict thô."""
        runtime = self._runtime({
            "grpc": {"tls": {"enabled": True, "cert_file": "a.crt", "key_file": "b.key"}}
        })
        cfg = GrpcServerConfig.from_runtime(runtime)
        assert isinstance(cfg.tls, GrpcTlsConfig)
