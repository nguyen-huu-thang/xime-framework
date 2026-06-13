"""
Test XimeGrpcChannel (Phase 2):

  Deadline:
    - call không truyền timeout → dùng deadline_ms từ config (giây)
    - call truyền timeout → override
    - deadline_ms=0 → không deadline (None)

  Dịch lỗi (_translate):
    - DEADLINE_EXCEEDED → RemoteCallTimeout
    - UNAVAILABLE → RemoteServiceUnavailable
    - status khác → RemoteCallError
    - trailing metadata xime-error → .code; không có → .code rỗng
    - exception mang status/path/message

  TLS tĩnh:
    - tls.enabled=False → insecure_channel
    - tls.enabled=True → secure_channel với credentials từ file
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import grpc
import pytest

from xime.adapters.grpc.client._channel import XimeGrpcChannel
from xime.adapters.grpc.client._config import GrpcClientConfig
from xime.core.exception.framework import (
    RemoteCallError,
    RemoteCallTimeout,
    RemoteServiceUnavailable,
)


def _channel(deadline_ms: int = 5000, **config_extra) -> XimeGrpcChannel:
    config = GrpcClientConfig(port=9090, deadline_ms=deadline_ms, **config_extra)
    return XimeGrpcChannel("trust", config)


class _FakeRpcError:
    """Đối tượng giả đủ giao diện AioRpcError mà _translate cần."""

    def __init__(self, status, details="boom", trailing=()):
        self._status = status
        self._details = details
        self._trailing = trailing

    def code(self):
        return self._status

    def details(self):
        return self._details

    def trailing_metadata(self):
        return self._trailing


# ---------------------------------------------------------------------------
# Deadline
# ---------------------------------------------------------------------------

class TestDeadline:
    @pytest.mark.asyncio
    async def test_default_deadline_applied(self):
        channel = _channel(deadline_ms=3000)
        captured = {}

        async def inner(request, timeout=None):
            captured["timeout"] = timeout
            return "reply"

        fake_grpc_channel = MagicMock()
        fake_grpc_channel.unary_unary.return_value = inner
        with patch.object(channel, "_create_static_channel", return_value=fake_grpc_channel):
            call = channel.unary_unary("/svc/Method", None, None)
            assert await call("req") == "reply"
        assert captured["timeout"] == 3.0

    @pytest.mark.asyncio
    async def test_per_call_override(self):
        channel = _channel(deadline_ms=3000)
        captured = {}

        async def inner(request, timeout=None):
            captured["timeout"] = timeout
            return "reply"

        fake_grpc_channel = MagicMock()
        fake_grpc_channel.unary_unary.return_value = inner
        with patch.object(channel, "_create_static_channel", return_value=fake_grpc_channel):
            call = channel.unary_unary("/svc/Method", None, None)
            await call("req", timeout=0.5)
        assert captured["timeout"] == 0.5

    def test_zero_deadline_means_none(self):
        assert _channel(deadline_ms=0)._timeout(None) is None

    def test_timeout_helper_converts_ms_to_seconds(self):
        assert _channel(deadline_ms=250)._timeout(None) == 0.25


# ---------------------------------------------------------------------------
# Dịch lỗi
# ---------------------------------------------------------------------------

class TestTranslateErrors:
    def test_deadline_exceeded_maps_to_timeout(self):
        exc = _channel()._translate(
            _FakeRpcError(grpc.StatusCode.DEADLINE_EXCEEDED), "/svc/M"
        )
        assert isinstance(exc, RemoteCallTimeout)
        assert exc.status == "DEADLINE_EXCEEDED"

    def test_unavailable_maps_to_service_unavailable(self):
        exc = _channel()._translate(
            _FakeRpcError(grpc.StatusCode.UNAVAILABLE), "/svc/M"
        )
        assert isinstance(exc, RemoteServiceUnavailable)

    def test_other_status_maps_to_remote_call_error(self):
        exc = _channel()._translate(
            _FakeRpcError(grpc.StatusCode.NOT_FOUND), "/svc/M"
        )
        assert type(exc) is RemoteCallError
        assert exc.status == "NOT_FOUND"

    def test_xime_error_metadata_becomes_code(self):
        exc = _channel()._translate(
            _FakeRpcError(
                grpc.StatusCode.INTERNAL,
                trailing=(("xime-error", "ObjectNotFoundException"),),
            ),
            "/svc/M",
        )
        assert exc.code == "ObjectNotFoundException"

    def test_no_metadata_gives_empty_code(self):
        exc = _channel()._translate(_FakeRpcError(grpc.StatusCode.INTERNAL), "/svc/M")
        assert exc.code == ""

    def test_carries_path_and_message(self):
        exc = _channel()._translate(
            _FakeRpcError(grpc.StatusCode.INTERNAL, details="kaboom"),
            "/xime.internal.KeyController/GetKeys",
        )
        assert exc.path == "/xime.internal.KeyController/GetKeys"
        assert exc.error_message == "kaboom"
        assert "kaboom" in str(exc)


# ---------------------------------------------------------------------------
# TLS tĩnh
# ---------------------------------------------------------------------------

class TestChannelCreation:
    def test_insecure_when_tls_disabled(self):
        channel = _channel()
        with patch("grpc.aio.insecure_channel") as mock_insecure:
            channel._create_static_channel()
            mock_insecure.assert_called_once_with("localhost:9090")

    def test_secure_when_tls_enabled(self, tmp_path):
        ca = tmp_path / "ca.pem"
        ca.write_bytes(b"FAKE_CA")
        channel = _channel(tls={"enabled": True, "ca_file": str(ca)})
        with patch("grpc.aio.secure_channel") as mock_secure, \
             patch("grpc.ssl_channel_credentials") as mock_creds:
            channel._create_static_channel()
            mock_creds.assert_called_once_with(
                root_certificates=b"FAKE_CA",
                private_key=None,
                certificate_chain=None,
            )
            mock_secure.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_is_safe_when_never_opened(self):
        await _channel().close()   # không raise
