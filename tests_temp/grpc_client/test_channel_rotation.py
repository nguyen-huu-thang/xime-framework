"""
Test mTLS động phía client (Phase 3):

  XimeGrpcChannel (tls.dynamic):
    - lần gọi đầu build channel từ provider.current()
    - version không đổi → dùng lại channel, không gọi current() lại
    - version đổi → channel MỚI với cert mới, channel cũ retire + đóng graceful
    - provider chưa attach → RuntimeError hướng dẫn configure_grpc_tls
    - provider không có root CA → RuntimeError
    - close() đóng cả channel hiện tại lẫn channel retired

  wire_dynamic_certificates() qua orchestrator:
    - provider được attach vào channel dynamic sau khi container build
    - dynamic bật nhưng chưa configure_grpc_tls → startup fail fast
    - provider không có trong DI → startup fail fast với chỉ dẫn
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xime.adapters.grpc.client._channel import XimeGrpcChannel
from xime.adapters.grpc.client._config import GrpcClientConfig, configure_grpc_clients
from xime.adapters.grpc.tls import ServerCertificates, configure_grpc_tls, grpc_tls_registry
from xime.core.bootstrap.orchestrator import StartupOrchestrator
from xime.core.config.binding import BindingConfig
from xime.core.config.runtime import RuntimeConfig


@pytest.fixture(autouse=True)
def reset_tls_registry():
    yield
    grpc_tls_registry.reset()


class FakeProvider:
    def __init__(self):
        self._version = "v1"
        self._certs = ServerCertificates("KEY_V1", "CERT_V1", "CA_V1")
        self.current_calls = 0

    def version(self) -> str:
        return self._version

    def current(self) -> ServerCertificates:
        self.current_calls += 1
        return self._certs

    def rotate(self, version: str, certs: ServerCertificates) -> None:
        self._version = version
        self._certs = certs


def _dynamic_channel() -> tuple[XimeGrpcChannel, FakeProvider]:
    config = GrpcClientConfig(port=9090, tls={"enabled": True, "dynamic": True})
    channel = XimeGrpcChannel("trust", config)
    provider = FakeProvider()
    channel.attach_certificate_provider(provider)
    return channel, provider


def _mock_grpc_channel() -> MagicMock:
    fake = MagicMock()
    fake.close = AsyncMock()
    return fake


# ---------------------------------------------------------------------------
# Rotation
# ---------------------------------------------------------------------------

class TestDynamicChannelRotation:
    def test_first_call_builds_channel_from_provider(self):
        channel, provider = _dynamic_channel()
        with patch("grpc.aio.secure_channel", return_value=_mock_grpc_channel()) as mock_secure, \
             patch("grpc.ssl_channel_credentials") as mock_creds:
            channel._grpc_channel()
            mock_creds.assert_called_once_with(
                root_certificates=b"CA_V1",
                private_key=b"KEY_V1",
                certificate_chain=b"CERT_V1",
            )
            mock_secure.assert_called_once_with("localhost:9090", mock_creds.return_value)
        assert provider.current_calls == 1

    def test_same_version_reuses_channel(self):
        channel, provider = _dynamic_channel()
        with patch("grpc.aio.secure_channel", side_effect=lambda *a: _mock_grpc_channel()):
            first = channel._grpc_channel()
            second = channel._grpc_channel()
        assert first is second
        assert provider.current_calls == 1   # current() chỉ gọi khi build

    @pytest.mark.asyncio
    async def test_rotation_rebuilds_and_retires_old_channel(self):
        channel, provider = _dynamic_channel()
        with patch("grpc.aio.secure_channel", side_effect=lambda *a: _mock_grpc_channel()):
            old = channel._grpc_channel()
            provider.rotate("v2", ServerCertificates("KEY_V2", "CERT_V2", "CA_V2"))
            new = channel._grpc_channel()

            assert new is not old
            # channel cũ được đóng graceful trong background
            # cho task close_later chạy
            await asyncio.sleep(0)
            old.close.assert_awaited_once()
            await channel.close()

    @pytest.mark.asyncio
    async def test_close_also_closes_retired_channels(self):
        channel, provider = _dynamic_channel()
        with patch("grpc.aio.secure_channel", side_effect=lambda *a: _mock_grpc_channel()):
            old = channel._grpc_channel()
            # retire khi KHÔNG có background close (giả lập bằng cách chặn create_task)
            provider.rotate("v2", ServerCertificates("K2", "C2", "CA2"))
            with patch("asyncio.get_running_loop", side_effect=RuntimeError):
                current = channel._grpc_channel()
            await channel.close()
        old.close.assert_awaited()
        current.close.assert_awaited()

    def test_concurrent_first_access_builds_one_channel(self):
        # Backlog #7: many OS threads hitting _grpc_channel() at once must not
        # each build a channel and leak all but one. The rotation lock makes the
        # check-and-replace atomic, so exactly one channel is created.
        import threading

        channel, provider = _dynamic_channel()
        barrier = threading.Barrier(20)
        errors: list[BaseException] = []

        def worker():
            try:
                barrier.wait()          # maximize contention
                channel._grpc_channel()
            except BaseException as exc:  # noqa: BLE001 - surfaced via errors
                errors.append(exc)

        with patch("grpc.aio.secure_channel", side_effect=lambda *a: _mock_grpc_channel()) as mock_secure:
            threads = [threading.Thread(target=worker) for _ in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert not errors
        assert mock_secure.call_count == 1       # only one channel ever built
        assert provider.current_calls == 1
        assert channel._retired == []            # nothing leaked / retired

    def test_missing_provider_raises_with_guidance(self):
        config = GrpcClientConfig(port=9090, tls={"enabled": True, "dynamic": True})
        channel = XimeGrpcChannel("trust", config)
        with pytest.raises(RuntimeError, match="configure_grpc_tls"):
            channel._grpc_channel()

    def test_provider_without_root_ca_raises(self):
        channel, provider = _dynamic_channel()
        provider.rotate("v1", ServerCertificates("KEY", "CERT", None))
        with pytest.raises(RuntimeError, match="root_ca_pem"):
            channel._grpc_channel()


# ---------------------------------------------------------------------------
# Wiring qua orchestrator
# ---------------------------------------------------------------------------

class FakeTrustClient:
    def __init__(self, channel) -> None:
        self.channel = channel


class DiFakeProvider:
    """Provider nằm trong DI (không tham số constructor)."""

    def version(self) -> str:
        return "v1"

    def current(self) -> ServerCertificates:
        return ServerCertificates("KEY", "CERT", "CA")


class DiPublicProvider:
    """A second provider, registered under a non-default server_id."""

    def version(self) -> str:
        return "v1"

    def current(self) -> ServerCertificates:
        return ServerCertificates("PKEY", "PCERT", "PCA")


def _runtime_dynamic() -> RuntimeConfig:
    return RuntimeConfig.from_dict({
        "grpc": {"clients": {"trust": {
            "port": 9090,
            "tls": {"enabled": True, "dynamic": True},
        }}}
    })


def _runtime_dynamic_server_id(server_id: str) -> RuntimeConfig:
    return RuntimeConfig.from_dict({
        "grpc": {"clients": {"trust": {
            "port": 9090,
            "tls": {"enabled": True, "dynamic": True, "server_id": server_id},
        }}}
    })


class TestWireDynamicCertificates:
    @pytest.mark.asyncio
    async def test_provider_attached_after_container_build(self):
        configure_grpc_clients("trust", FakeTrustClient)
        configure_grpc_tls(provider=DiFakeProvider)

        binding = BindingConfig()
        binding.register(DiFakeProvider)

        orchestrator = StartupOrchestrator(binding, _runtime_dynamic())
        await orchestrator.start()
        try:
            client = orchestrator.get(FakeTrustClient)
            assert isinstance(client.channel._provider, DiFakeProvider)
        finally:
            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_non_default_server_id_uses_matching_provider(self):
        # Backlog #8: a client with tls.server_id != "default" must receive the
        # provider registered for that server_id, not the hardcoded "default".
        configure_grpc_clients("trust", FakeTrustClient)
        configure_grpc_tls(provider=DiFakeProvider)                      # default
        configure_grpc_tls(provider=DiPublicProvider, server_id="public")

        binding = BindingConfig()
        binding.register(DiFakeProvider)
        binding.register(DiPublicProvider)

        orchestrator = StartupOrchestrator(binding, _runtime_dynamic_server_id("public"))
        await orchestrator.start()
        try:
            client = orchestrator.get(FakeTrustClient)
            assert isinstance(client.channel._provider, DiPublicProvider)
        finally:
            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_dynamic_without_configure_grpc_tls_fails_startup(self):
        configure_grpc_clients("trust", FakeTrustClient)
        orchestrator = StartupOrchestrator(BindingConfig(), _runtime_dynamic())
        with pytest.raises(RuntimeError, match="configure_grpc_tls"):
            await orchestrator.start()

    @pytest.mark.asyncio
    async def test_provider_not_in_di_fails_startup(self):
        configure_grpc_clients("trust", FakeTrustClient)
        configure_grpc_tls(provider=DiFakeProvider)   # nhưng KHÔNG register vào DI
        orchestrator = StartupOrchestrator(BindingConfig(), _runtime_dynamic())
        with pytest.raises(RuntimeError, match="dependency.scan|dependency.register"):
            await orchestrator.start()

    @pytest.mark.asyncio
    async def test_static_tls_channels_are_not_wired(self):
        configure_grpc_clients("trust", FakeTrustClient)
        runtime = RuntimeConfig.from_dict({
            "grpc": {"clients": {"trust": {"port": 9090}}}
        })
        orchestrator = StartupOrchestrator(BindingConfig(), runtime)
        await orchestrator.start()   # không cần provider, không raise
        try:
            client = orchestrator.get(FakeTrustClient)
            assert client.channel._provider is None
        finally:
            await orchestrator.stop()
