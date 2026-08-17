"""
Test GrpcAdapter:

  start():
    - gọi grpc.aio.server() với interceptor stack
    - interceptor stack luôn bắt đầu bằng RequestContextInterceptor, ErrorMappingInterceptor
    - user-declared interceptors nằm sau built-in interceptors
    - gọi add_insecure_port khi tls.enabled=False
    - gọi add_secure_port khi tls.enabled=True
    - gọi server.start()
    - gọi GrpcServiceBuilder.register_all() với bindings từ registry
    - gọi GrpcServiceScanner.validate_packages() với packages từ registry

  stop():
    - gọi server.stop(grace=5)
    - không raise khi server là None (start chưa được gọi)
    - đặt _server về None sau stop

  _build_interceptors():
    - không có user interceptors → chỉ 2 built-in
    - có user interceptors → built-in đứng trước
    - ErrorMappingInterceptor nhận error_mappings từ registry
"""
from unittest.mock import AsyncMock, MagicMock, patch

import grpc
import grpc.aio
import pytest

from xime.adapters.grpc._adapter import GrpcAdapter
from xime.adapters.grpc._config import GrpcServerConfig, GrpcTlsConfig
from xime.adapters.grpc.interceptors._config import grpc_interceptor_registry
from xime.adapters.grpc.interceptors._context import RequestContextInterceptor
from xime.adapters.grpc.interceptors._error import ErrorMappingInterceptor
from xime.adapters.grpc.routing._config import grpc_service_registry
from xime.core.config.runtime import RuntimeConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_runtime(grpc_cfg: dict | None = None) -> RuntimeConfig:
    data = {}
    if grpc_cfg is not None:
        data["grpc"] = grpc_cfg
    return RuntimeConfig.from_dict(data)


def _make_app(runtime: RuntimeConfig | None = None) -> MagicMock:
    """Build a mock Application that returns the given runtime from get(RuntimeConfig)."""
    app = MagicMock()
    app.get.return_value = runtime or _make_runtime()
    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_registries():
    yield
    grpc_service_registry._packages.clear()
    grpc_service_registry._bindings.clear()
    grpc_interceptor_registry._interceptors.clear()
    grpc_interceptor_registry._error_mappings.clear()


@pytest.fixture()
def mock_app():
    return _make_app()


@pytest.fixture()
def mock_grpc_server():
    server = AsyncMock(spec=grpc.aio.Server)
    server.add_insecure_port = MagicMock()
    server.add_secure_port = MagicMock()
    return server


# ---------------------------------------------------------------------------
# _build_interceptors
# ---------------------------------------------------------------------------

class TestGrpcAdapterBuildInterceptors:
    def test_always_starts_with_request_context_interceptor(self):
        adapter = GrpcAdapter()
        interceptors = adapter._build_interceptors()
        assert isinstance(interceptors[0], RequestContextInterceptor)

    def test_always_has_error_mapping_interceptor_second(self):
        adapter = GrpcAdapter()
        interceptors = adapter._build_interceptors()
        assert isinstance(interceptors[1], ErrorMappingInterceptor)

    def test_no_user_interceptors_gives_two_built_ins(self):
        adapter = GrpcAdapter()
        interceptors = adapter._build_interceptors()
        assert len(interceptors) == 2

    def test_user_interceptors_appended_after_built_ins(self):
        user_interceptor = MagicMock(spec=grpc.aio.ServerInterceptor)
        grpc_interceptor_registry.add_interceptors([user_interceptor])

        adapter = GrpcAdapter()
        interceptors = adapter._build_interceptors()
        assert len(interceptors) == 3
        assert interceptors[2] is user_interceptor

    def test_error_mapping_interceptor_receives_registry_mappings(self):
        class _E(Exception): pass
        grpc_interceptor_registry.set_error_mappings({_E: grpc.StatusCode.NOT_FOUND})

        adapter = GrpcAdapter()
        interceptors = adapter._build_interceptors()
        error_interceptor: ErrorMappingInterceptor = interceptors[1]
        assert error_interceptor._mappings[_E] == grpc.StatusCode.NOT_FOUND


# ---------------------------------------------------------------------------
# start() — insecure
# ---------------------------------------------------------------------------

class TestGrpcAdapterStartInsecure:
    @pytest.mark.asyncio
    async def test_creates_grpc_server_with_interceptors(self, mock_app, mock_grpc_server):
        with patch("grpc.aio.server", return_value=mock_grpc_server) as mock_server_fn:
            adapter = GrpcAdapter()
            await adapter.start(mock_app)

            mock_server_fn.assert_called_once()
            interceptors_arg = mock_server_fn.call_args[1]["interceptors"]
            assert len(interceptors_arg) == 2  # built-ins only

    @pytest.mark.asyncio
    async def test_adds_insecure_port_when_tls_disabled(self, mock_grpc_server):
        app = _make_app(_make_runtime({"port": 50051}))
        with patch("grpc.aio.server", return_value=mock_grpc_server):
            adapter = GrpcAdapter()
            await adapter.start(app)

            mock_grpc_server.add_insecure_port.assert_called_once_with("[::]:50051")
            mock_grpc_server.add_secure_port.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_server_start(self, mock_app, mock_grpc_server):
        with patch("grpc.aio.server", return_value=mock_grpc_server):
            adapter = GrpcAdapter()
            await adapter.start(mock_app)

            mock_grpc_server.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_port_from_config(self, mock_grpc_server):
        app = _make_app(_make_runtime({"port": 9090}))
        with patch("grpc.aio.server", return_value=mock_grpc_server):
            adapter = GrpcAdapter()
            await adapter.start(app)

            mock_grpc_server.add_insecure_port.assert_called_once_with("[::]:9090")


# ---------------------------------------------------------------------------
# start() — TLS / mTLS
# ---------------------------------------------------------------------------

class TestGrpcAdapterStartTls:
    @pytest.mark.asyncio
    async def test_adds_secure_port_when_tls_enabled(self, mock_grpc_server, tmp_path):
        cert = tmp_path / "server.crt"
        key  = tmp_path / "server.key"
        cert.write_bytes(b"CERT")
        key.write_bytes(b"KEY")

        runtime = _make_runtime({
            "port": 50051,
            "tls": {
                "enabled": True,
                "cert_file": str(cert),
                "key_file": str(key),
            },
        })
        fake_credentials = MagicMock(spec=grpc.ServerCredentials)
        app = _make_app(runtime)

        with patch("grpc.aio.server", return_value=mock_grpc_server):
            with patch(
                "xime.adapters.grpc._adapter.build_server_credentials",
                return_value=fake_credentials,
            ):
                adapter = GrpcAdapter()
                await adapter.start(app)

                mock_grpc_server.add_secure_port.assert_called_once_with(
                    "[::]:50051", fake_credentials
                )
                mock_grpc_server.add_insecure_port.assert_not_called()


# ---------------------------------------------------------------------------
# start() — servicer registration
# ---------------------------------------------------------------------------

class TestGrpcAdapterStartServicers:
    @pytest.mark.asyncio
    async def test_calls_register_all_with_bindings(self, mock_grpc_server):
        class _Handler: pass
        def _add_fn(servicer, server): pass

        grpc_service_registry.register([], {_Handler: _add_fn})

        app = _make_app()
        app.get.side_effect = lambda cls: (
            _make_runtime() if cls.__name__ == "RuntimeConfig" else _Handler()
        )

        with patch("grpc.aio.server", return_value=mock_grpc_server):
            with patch("xime.adapters.grpc._adapter.GrpcServiceBuilder") as MockBuilder:
                mock_builder_instance = MagicMock()
                MockBuilder.return_value = mock_builder_instance

                adapter = GrpcAdapter()
                await adapter.start(app)

                MockBuilder.assert_called_once_with(app, "default")
                mock_builder_instance.register_all.assert_called_once_with(
                    mock_grpc_server, {_Handler: _add_fn}
                )

    @pytest.mark.asyncio
    async def test_calls_scanner_validate_with_packages(self, mock_app, mock_grpc_server):
        grpc_service_registry.register(["api.grpc"], {})

        with patch("grpc.aio.server", return_value=mock_grpc_server):
            with patch("xime.adapters.grpc._adapter.GrpcServiceScanner") as MockScanner:
                mock_scanner_instance = MagicMock()
                MockScanner.return_value = mock_scanner_instance

                adapter = GrpcAdapter()
                await adapter.start(mock_app)

                mock_scanner_instance.validate_packages.assert_called_once_with("api.grpc")


# ---------------------------------------------------------------------------
# stop()
# ---------------------------------------------------------------------------

class TestGrpcAdapterStop:
    @pytest.mark.asyncio
    async def test_calls_server_stop_with_grace(self, mock_app, mock_grpc_server):
        with patch("grpc.aio.server", return_value=mock_grpc_server):
            adapter = GrpcAdapter()
            await adapter.start(mock_app)
            await adapter.stop()

            mock_grpc_server.stop.assert_called_once_with(grace=5)

    @pytest.mark.asyncio
    async def test_sets_server_to_none_after_stop(self, mock_app, mock_grpc_server):
        with patch("grpc.aio.server", return_value=mock_grpc_server):
            adapter = GrpcAdapter()
            await adapter.start(mock_app)
            await adapter.stop()

            assert adapter._server is None

    @pytest.mark.asyncio
    async def test_stop_is_noop_when_not_started(self):
        adapter = GrpcAdapter()
        await adapter.stop()   # không raise


# ---------------------------------------------------------------------------
# F6 - chế độ không an toàn phải nói ra, không được im lặng
# ---------------------------------------------------------------------------

class TestInsecureModeWarning:
    """Mặc định dễ dãi (TLS tắt) là có chủ đích; mặc định IM LẶNG mới là vấn đề:
    service production mất khối TLS trông y hệt service khoẻ mạnh trong log."""

    _LOGGER = "xime.adapters.grpc._adapter"

    @pytest.mark.asyncio
    async def test_plaintext_start_warns(self, mock_grpc_server, caplog):
        app = _make_app(_make_runtime({"port": 50051}))
        with patch("grpc.aio.server", return_value=mock_grpc_server), \
             caplog.at_level("WARNING", logger=self._LOGGER):
            await GrpcAdapter().start(app)
        assert "PLAINTEXT" in caplog.text

    def test_tls_without_mutual_warns(self, caplog):
        config = GrpcServerConfig.model_validate(
            {"port": 50051, "tls": {"enabled": True, "mutual": False}}
        )
        with caplog.at_level("WARNING", logger=self._LOGGER):
            GrpcAdapter()._warn_insecure_mode(config, secure=True)
        assert "not mTLS" in caplog.text

    def test_mtls_says_nothing(self, caplog):
        config = GrpcServerConfig.model_validate(
            {"port": 50051, "tls": {"enabled": True, "mutual": True}}
        )
        with caplog.at_level("WARNING", logger=self._LOGGER):
            GrpcAdapter()._warn_insecure_mode(config, secure=True)
        assert caplog.text == ""


# ---------------------------------------------------------------------------
# Keepalive phía server
# ---------------------------------------------------------------------------

class TestServerKeepalive:
    @pytest.mark.asyncio
    async def test_no_keepalive_block_means_no_options(self, mock_grpc_server):
        app = _make_app(_make_runtime({"port": 50051}))
        with patch("grpc.aio.server", return_value=mock_grpc_server) as server_fn:
            await GrpcAdapter().start(app)
        assert server_fn.call_args[1]["options"] == []

    @pytest.mark.asyncio
    async def test_ping_policy_forwarded(self, mock_grpc_server):
        # Không nới min_ping_interval thì server trả GOAWAY "too_many_pings" cho
        # client bật keepalive - giết đúng luồng dài mà keepalive bảo vệ.
        app = _make_app(
            _make_runtime(
                {"port": 50051, "keepalive": {"min_ping_interval_without_data_ms": 30000}}
            )
        )
        with patch("grpc.aio.server", return_value=mock_grpc_server) as server_fn:
            await GrpcAdapter().start(app)
        assert (
            "grpc.http2.min_ping_interval_without_data_ms", 30000
        ) in server_fn.call_args[1]["options"]
