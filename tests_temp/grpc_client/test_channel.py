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

from unittest.mock import AsyncMock, MagicMock, patch

import grpc
import grpc.aio
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


class _FakeAioRpcError(grpc.aio.AioRpcError):
    """Raised by the fake inner call so `except AioRpcError` catches it."""

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


# ---------------------------------------------------------------------------
# Retry policy (unary)
# ---------------------------------------------------------------------------

class TestRetry:
    def _with_inner(self, inner, **retry):
        channel = _channel(retry={"enabled": True, "max_attempts": 3,
                                  "initial_backoff_ms": 1, **retry})
        fake = MagicMock()
        fake.unary_unary.return_value = inner
        return channel, fake

    @pytest.mark.asyncio
    async def test_retries_unavailable_then_succeeds(self):
        calls = {"n": 0}

        async def inner(request, timeout=None):
            calls["n"] += 1
            if calls["n"] < 3:
                raise _FakeAioRpcError(grpc.StatusCode.UNAVAILABLE)
            return "ok"

        channel, fake = self._with_inner(inner)
        with patch.object(channel, "_create_static_channel", return_value=fake), \
             patch("asyncio.sleep", new=AsyncMock()):
            call = channel.unary_unary("/svc/M", None, None)
            assert await call("req") == "ok"
        assert calls["n"] == 3   # two failures + one success

    @pytest.mark.asyncio
    async def test_retries_exhausted_raises_typed(self):
        calls = {"n": 0}

        async def inner(request, timeout=None):
            calls["n"] += 1
            raise _FakeAioRpcError(grpc.StatusCode.UNAVAILABLE)

        channel, fake = self._with_inner(inner)
        with patch.object(channel, "_create_static_channel", return_value=fake), \
             patch("asyncio.sleep", new=AsyncMock()):
            call = channel.unary_unary("/svc/M", None, None)
            with pytest.raises(RemoteServiceUnavailable):
                await call("req")
        assert calls["n"] == 3   # exactly max_attempts

    @pytest.mark.asyncio
    async def test_disabled_does_not_retry(self):
        calls = {"n": 0}

        async def inner(request, timeout=None):
            calls["n"] += 1
            raise _FakeAioRpcError(grpc.StatusCode.UNAVAILABLE)

        channel = _channel()   # retry off by default
        fake = MagicMock()
        fake.unary_unary.return_value = inner
        with patch.object(channel, "_create_static_channel", return_value=fake):
            call = channel.unary_unary("/svc/M", None, None)
            with pytest.raises(RemoteServiceUnavailable):
                await call("req")
        assert calls["n"] == 1

    @pytest.mark.asyncio
    async def test_non_retryable_status_not_retried(self):
        calls = {"n": 0}

        async def inner(request, timeout=None):
            calls["n"] += 1
            raise _FakeAioRpcError(grpc.StatusCode.NOT_FOUND)

        channel, fake = self._with_inner(inner)
        with patch.object(channel, "_create_static_channel", return_value=fake), \
             patch("asyncio.sleep", new=AsyncMock()):
            call = channel.unary_unary("/svc/M", None, None)
            with pytest.raises(RemoteCallError):
                await call("req")
        assert calls["n"] == 1   # NOT_FOUND is not retryable

    def test_backoff_grows_and_caps(self):
        channel = _channel(retry={"enabled": True, "initial_backoff_ms": 100,
                                  "backoff_multiplier": 2.0, "max_backoff_ms": 300})
        assert channel._backoff_delay(1) == 0.1
        assert channel._backoff_delay(2) == 0.2
        assert channel._backoff_delay(3) == 0.3   # would be 0.4, capped at 0.3
        assert channel._backoff_delay(4) == 0.3
