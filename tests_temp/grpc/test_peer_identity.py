"""
Test peer mTLS identity extraction (0.4 - Cross-cutting):

  _read_peer_cn():
    - context None → None
    - auth_context() raises → None (fail-soft)
    - auth_context() empty → None
    - no x509_common_name key → None
    - CN present as list[bytes] → decoded str
    - CN key as bytes → decoded str
    - CN value non-utf8 bytes → None

  RequestContextInterceptor (mTLS):
    - sets peer_cn when client cert CN present
    - does NOT set peer_cn when no mTLS (request still works)
    - clears peer_cn after the handler completes
    - current_caller() reflects request_context["peer_cn"]
    - streaming handler also sets/clears peer_cn
"""
import grpc
import pytest
from unittest.mock import MagicMock

from xime.adapters.grpc.interceptors._context import (
    RequestContextInterceptor,
    _read_peer_cn,
)
from xime.core.context import request_context
from xime.core.security import current_caller
from xime.core.security.peer import PEER_CN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _context_with_auth(auth):
    """Build a fake ServicerContext whose auth_context() returns `auth`."""
    ctx = MagicMock()
    ctx.auth_context.return_value = auth
    return ctx


def _raising_context():
    ctx = MagicMock()
    ctx.auth_context.side_effect = RuntimeError("no auth context")
    return ctx


# ---------------------------------------------------------------------------
# _read_peer_cn
# ---------------------------------------------------------------------------

class TestReadPeerCn:
    def test_none_context_returns_none(self):
        assert _read_peer_cn(None) is None

    def test_auth_context_raises_returns_none(self):
        assert _read_peer_cn(_raising_context()) is None

    def test_empty_auth_context_returns_none(self):
        assert _read_peer_cn(_context_with_auth({})) is None

    def test_missing_cn_key_returns_none(self):
        auth = {"x509_subject_alternative_name": [b"san"]}
        assert _read_peer_cn(_context_with_auth(auth)) is None

    def test_cn_as_list_of_bytes_is_decoded(self):
        auth = {"x509_common_name": [b"data-service"]}
        assert _read_peer_cn(_context_with_auth(auth)) == "data-service"

    def test_cn_key_as_bytes_is_decoded(self):
        auth = {b"x509_common_name": [b"notification-service"]}
        assert _read_peer_cn(_context_with_auth(auth)) == "notification-service"

    def test_non_utf8_cn_returns_none(self):
        auth = {"x509_common_name": [b"\xff\xfe"]}
        assert _read_peer_cn(_context_with_auth(auth)) is None


# ---------------------------------------------------------------------------
# RequestContextInterceptor — peer CN behaviour
# ---------------------------------------------------------------------------

class TestRequestContextInterceptorPeerCn:
    @pytest.mark.asyncio
    async def test_sets_peer_cn_when_cert_present(self):
        captured_cn = None
        captured_caller = None

        async def handler_fn(request, context):
            nonlocal captured_cn, captured_caller
            captured_cn = request_context.get(PEER_CN)
            captured_caller = current_caller()
            return None

        real_handler = grpc.unary_unary_rpc_method_handler(handler_fn)

        async def continuation(details):
            return real_handler

        interceptor = RequestContextInterceptor()
        wrapped = await interceptor.intercept_service(continuation, MagicMock())

        ctx = _context_with_auth({"x509_common_name": [b"data-service"]})
        await wrapped.unary_unary("req", ctx)

        assert captured_cn == "data-service"
        assert captured_caller == "data-service"

    @pytest.mark.asyncio
    async def test_does_not_set_peer_cn_without_mtls(self):
        captured_cn = "sentinel"

        async def handler_fn(request, context):
            nonlocal captured_cn
            captured_cn = request_context.get(PEER_CN)
            return None

        real_handler = grpc.unary_unary_rpc_method_handler(handler_fn)

        async def continuation(details):
            return real_handler

        interceptor = RequestContextInterceptor()
        wrapped = await interceptor.intercept_service(continuation, MagicMock())

        # No mTLS: auth_context empty → handler still runs, peer_cn absent.
        ctx = _context_with_auth({})
        await wrapped.unary_unary("req", ctx)

        assert captured_cn is None

    @pytest.mark.asyncio
    async def test_clears_peer_cn_after_handler(self):
        async def handler_fn(request, context):
            return None

        real_handler = grpc.unary_unary_rpc_method_handler(handler_fn)

        async def continuation(details):
            return real_handler

        interceptor = RequestContextInterceptor()
        wrapped = await interceptor.intercept_service(continuation, MagicMock())

        ctx = _context_with_auth({"x509_common_name": [b"data-service"]})
        await wrapped.unary_unary("req", ctx)

        assert request_context.get(PEER_CN) is None
        assert current_caller() is None

    @pytest.mark.asyncio
    async def test_streaming_handler_sets_and_clears_peer_cn(self):
        captured_cn = None

        async def handler_fn(request, context):
            nonlocal captured_cn
            captured_cn = request_context.get(PEER_CN)
            yield "a"
            yield "b"

        real_handler = grpc.unary_stream_rpc_method_handler(handler_fn)

        async def continuation(details):
            return real_handler

        interceptor = RequestContextInterceptor()
        wrapped = await interceptor.intercept_service(continuation, MagicMock())

        ctx = _context_with_auth({"x509_common_name": [b"agent-service"]})
        items = [item async for item in wrapped.unary_stream("req", ctx)]

        assert items == ["a", "b"]
        assert captured_cn == "agent-service"
        assert request_context.get(PEER_CN) is None
