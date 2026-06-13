"""
Test tích hợp DI (Phase 2): configure_grpc_clients → orchestrator pre-register
→ class user nhận client qua constructor injection.

  - Client instance lấy được từ container theo type
  - Class user khai `keys: FakeKeyClient` được inject đúng instance
  - Hai class cùng client_id chia sẻ một channel
  - GrpcClientChannels có trong lifecycle (đóng channel lúc stop, không lỗi)
  - Thiếu block YAML → startup fail fast
"""
from __future__ import annotations

import pytest

from xime.adapters.grpc.client._channel import XimeGrpcChannel
from xime.adapters.grpc.client._config import configure_grpc_clients
from xime.core.bootstrap.orchestrator import StartupOrchestrator
from xime.core.config.binding import BindingConfig
from xime.core.config.runtime import RuntimeConfig


class FakeKeyClient:
    def __init__(self, channel) -> None:
        self.channel = channel


class FakeCertClient:
    def __init__(self, channel) -> None:
        self.channel = channel


class TrustConsumer:
    """Class user bình thường - chỉ khai constructor injection."""

    def __init__(self, keys: FakeKeyClient, certs: FakeCertClient) -> None:
        self.keys = keys
        self.certs = certs


def _runtime() -> RuntimeConfig:
    return RuntimeConfig.from_dict(
        {"grpc": {"clients": {"trust": {"port": 9090, "deadline_ms": 1000}}}}
    )


@pytest.mark.asyncio
async def test_clients_are_injected_into_user_classes():
    configure_grpc_clients("trust", FakeKeyClient, FakeCertClient)

    binding = BindingConfig()
    binding.register(TrustConsumer)

    orchestrator = StartupOrchestrator(binding, _runtime())
    await orchestrator.start()
    try:
        consumer = orchestrator.get(TrustConsumer)
        assert isinstance(consumer.keys, FakeKeyClient)
        assert isinstance(consumer.certs, FakeCertClient)
        # cùng client_id → cùng channel có quản lý
        assert isinstance(consumer.keys.channel, XimeGrpcChannel)
        assert consumer.keys.channel is consumer.certs.channel
        assert consumer.keys.channel.client_id == "trust"
    finally:
        await orchestrator.stop()   # GrpcClientChannels.pre_destroy chạy, không lỗi


@pytest.mark.asyncio
async def test_missing_yaml_block_fails_startup():
    configure_grpc_clients("trust", FakeKeyClient)
    orchestrator = StartupOrchestrator(
        BindingConfig(), RuntimeConfig.from_dict({})
    )
    with pytest.raises(RuntimeError, match="grpc.clients.trust"):
        await orchestrator.start()


@pytest.mark.asyncio
async def test_no_configured_clients_is_a_noop():
    orchestrator = StartupOrchestrator(
        BindingConfig(), RuntimeConfig.from_dict({})
    )
    await orchestrator.start()   # không raise dù không có YAML grpc
    await orchestrator.stop()
