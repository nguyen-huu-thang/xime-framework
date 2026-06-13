"""
Test cấu hình gRPC client (Phase 2):

  GrpcClientConfig.from_runtime():
    - parse block grpc.clients.<id> đầy đủ
    - default: host=localhost, deadline_ms=5000, tls disabled
    - thiếu block → RuntimeError có tên client_id + hướng dẫn YAML

  configure_grpc_clients() / registry:
    - đăng ký nhiều class một client_id, nhiều client_id
    - không truyền class → ValueError
    - reset() dọn sạch

  build_client_instances():
    - các class cùng client_id nhận CÙNG một XimeGrpcChannel
    - client_id khác nhau nhận channel khác nhau
    - có GrpcClientChannels holder để đóng channel lúc shutdown
    - một class đăng ký 2 client_id → RuntimeError
"""
from __future__ import annotations

import pytest

from xime.adapters.grpc.client._channel import XimeGrpcChannel
from xime.adapters.grpc.client._config import (
    GrpcClientChannels,
    GrpcClientConfig,
    build_client_instances,
    configure_grpc_clients,
    grpc_clients_registry,
)
from xime.core.config.runtime import RuntimeConfig


class FakeKeyClient:
    def __init__(self, channel) -> None:
        self.channel = channel


class FakeCertClient:
    def __init__(self, channel) -> None:
        self.channel = channel


class FakeUserClient:
    def __init__(self, channel) -> None:
        self.channel = channel


def _runtime(data: dict) -> RuntimeConfig:
    return RuntimeConfig.from_dict(data)


class TestGrpcClientConfig:
    def test_parses_full_block(self):
        runtime = _runtime({
            "grpc": {"clients": {"trust": {
                "host": "trust.internal",
                "port": 9090,
                "deadline_ms": 3000,
                "tls": {"enabled": True, "ca_file": "ca.pem"},
            }}}
        })
        cfg = GrpcClientConfig.from_runtime(runtime, "trust")
        assert cfg.host == "trust.internal"
        assert cfg.port == 9090
        assert cfg.deadline_ms == 3000
        assert cfg.tls.enabled is True
        assert cfg.tls.ca_file == "ca.pem"

    def test_defaults(self):
        runtime = _runtime({"grpc": {"clients": {"trust": {"port": 9090}}}})
        cfg = GrpcClientConfig.from_runtime(runtime, "trust")
        assert cfg.host == "localhost"
        assert cfg.deadline_ms == 5000
        assert cfg.tls.enabled is False

    def test_missing_block_fails_fast_with_client_id(self):
        runtime = _runtime({"grpc": {"port": 50051}})
        with pytest.raises(RuntimeError, match="grpc.clients.trust"):
            GrpcClientConfig.from_runtime(runtime, "trust")

    def test_missing_grpc_key_fails_fast(self):
        with pytest.raises(RuntimeError, match="trust"):
            GrpcClientConfig.from_runtime(_runtime({}), "trust")


class TestConfigureGrpcClients:
    def test_registers_classes_per_client_id(self):
        configure_grpc_clients("trust", FakeKeyClient, FakeCertClient)
        configure_grpc_clients("user", FakeUserClient)
        items = grpc_clients_registry.items()
        assert items["trust"] == [FakeKeyClient, FakeCertClient]
        assert items["user"] == [FakeUserClient]

    def test_no_classes_raises(self):
        with pytest.raises(ValueError, match="at least one client class"):
            configure_grpc_clients("trust")

    def test_reset_clears(self):
        configure_grpc_clients("trust", FakeKeyClient)
        grpc_clients_registry.reset()
        assert grpc_clients_registry.items() == {}


class TestBuildClientInstances:
    def _runtime_two_targets(self) -> RuntimeConfig:
        return _runtime({
            "grpc": {"clients": {
                "trust": {"port": 9090},
                "user": {"port": 9092},
            }}
        })

    def test_same_client_id_shares_one_channel(self):
        configure_grpc_clients("trust", FakeKeyClient, FakeCertClient)
        instances = build_client_instances(_runtime({
            "grpc": {"clients": {"trust": {"port": 9090}}}
        }))
        key = instances[FakeKeyClient]
        cert = instances[FakeCertClient]
        assert isinstance(key.channel, XimeGrpcChannel)
        assert key.channel is cert.channel
        assert key.channel.client_id == "trust"

    def test_different_client_ids_get_different_channels(self):
        configure_grpc_clients("trust", FakeKeyClient)
        configure_grpc_clients("user", FakeUserClient)
        instances = build_client_instances(self._runtime_two_targets())
        assert instances[FakeKeyClient].channel is not instances[FakeUserClient].channel

    def test_channels_holder_included_for_shutdown(self):
        configure_grpc_clients("trust", FakeKeyClient)
        instances = build_client_instances(_runtime({
            "grpc": {"clients": {"trust": {"port": 9090}}}
        }))
        assert GrpcClientChannels in instances

    def test_class_in_two_client_ids_raises(self):
        configure_grpc_clients("trust", FakeKeyClient)
        configure_grpc_clients("user", FakeKeyClient)
        with pytest.raises(RuntimeError, match="FakeKeyClient"):
            build_client_instances(self._runtime_two_targets())
