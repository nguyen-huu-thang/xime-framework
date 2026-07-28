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

Peer APPLICATION identity from the certificate SAN (0.6.3):

  _read_peer_app_id():
    - context None / auth_context() raises / empty → None (fail-soft)
    - no x509_subject_alternative_name key → None
    - SAN without any xime-app:// entry (platform cert) → None
    - xime-app:// entry among other SANs → identity without the scheme
    - SAN type prefix ("URI:...") tolerated
    - SAN key as bytes → decoded
    - several xime-app:// entries → the first one
    - identity of unexpected length → None
    - non-utf8 entry skipped, a valid later entry still found

  RequestContextInterceptor (application identity):
    - sets peer_app_id alongside peer_cn
    - platform cert (CN only) → peer_cn set, peer_app_id absent
    - clears peer_app_id after the handler completes
    - streaming handler also sets/clears peer_app_id
"""
import grpc
import pytest
from unittest.mock import MagicMock

from xime.adapters.grpc.interceptors._context import (
    RequestContextInterceptor,
    _read_peer_app_id,
    _read_peer_cn,
)
from xime.core.context import request_context
from xime.core.security import current_app_id, current_caller
from xime.core.security.peer import PEER_APP_ID, PEER_CN

# A real 33-character Base62 application identity, taken from a certificate
# issued by Trust on the dev machine.
# Định danh app Base62 33 ký tự thật, lấy từ cert do Trust cấp trên máy dev.
APP_ID = "0FM4Roe2BT16XvEB7Y65VMv2xAZ68sdoZ"


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


# ---------------------------------------------------------------------------
# _read_peer_app_id
# ---------------------------------------------------------------------------

def _app_cert_auth(*extra_sans):
    """auth_context() of a certificate issued to a process of an application."""
    sans = [
        b"spiffe://localhost/gym",
        b"localhost",
        b"127.0.0.1",
        f"xime-app://{APP_ID}".encode(),
        *extra_sans,
    ]
    return {
        "x509_common_name": [b"gym-backend"],
        "x509_subject_alternative_name": sans,
    }


def _platform_cert_auth():
    """auth_context() of a platform service certificate — no application SAN."""
    return {
        "x509_common_name": [b"data-service"],
        "x509_subject_alternative_name": [
            b"spiffe://localhost/data",
            b"localhost",
            b"127.0.0.1",
        ],
    }


class TestReadPeerAppId:
    def test_none_context_returns_none(self):
        assert _read_peer_app_id(None) is None

    def test_auth_context_raises_returns_none(self):
        assert _read_peer_app_id(_raising_context()) is None

    def test_empty_auth_context_returns_none(self):
        assert _read_peer_app_id(_context_with_auth({})) is None

    def test_missing_san_key_returns_none(self):
        auth = {"x509_common_name": [b"data-service"]}
        assert _read_peer_app_id(_context_with_auth(auth)) is None

    def test_platform_cert_without_app_san_returns_none(self):
        assert _read_peer_app_id(_context_with_auth(_platform_cert_auth())) is None

    def test_app_san_among_other_sans_is_extracted_without_scheme(self):
        result = _read_peer_app_id(_context_with_auth(_app_cert_auth()))
        assert result == APP_ID
        assert "xime-app" not in result

    def test_san_type_prefix_is_tolerated(self):
        auth = {
            "x509_subject_alternative_name": [
                b"DNS:localhost",
                f"URI:xime-app://{APP_ID}".encode(),
            ]
        }
        assert _read_peer_app_id(_context_with_auth(auth)) == APP_ID

    def test_san_key_as_bytes_is_read(self):
        auth = {b"x509_subject_alternative_name": [f"xime-app://{APP_ID}".encode()]}
        assert _read_peer_app_id(_context_with_auth(auth)) == APP_ID

    def test_str_san_values_are_accepted(self):
        auth = {"x509_subject_alternative_name": [f"xime-app://{APP_ID}"]}
        assert _read_peer_app_id(_context_with_auth(auth)) == APP_ID

    def test_first_app_san_wins_when_several_present(self):
        other = "1" * 33
        auth = _app_cert_auth(f"xime-app://{other}".encode())
        assert _read_peer_app_id(_context_with_auth(auth)) == APP_ID

    def test_identity_of_wrong_length_returns_none(self):
        auth = {"x509_subject_alternative_name": [b"xime-app://too-short"]}
        assert _read_peer_app_id(_context_with_auth(auth)) is None

    def test_empty_identity_returns_none(self):
        auth = {"x509_subject_alternative_name": [b"xime-app://"]}
        assert _read_peer_app_id(_context_with_auth(auth)) is None

    def test_non_utf8_entry_is_skipped_not_raised(self):
        auth = {"x509_subject_alternative_name": [b"\xff\xfe"]}
        assert _read_peer_app_id(_context_with_auth(auth)) is None

    def test_non_utf8_entry_does_not_hide_a_later_valid_entry(self):
        auth = {
            "x509_subject_alternative_name": [
                b"\xff\xfe",
                f"xime-app://{APP_ID}".encode(),
            ]
        }
        assert _read_peer_app_id(_context_with_auth(auth)) == APP_ID


# ---------------------------------------------------------------------------
# RequestContextInterceptor — peer application identity
# ---------------------------------------------------------------------------

def _intercepted(handler):
    """Run a handler through RequestContextInterceptor and return the wrapper."""

    async def continuation(details):
        return handler

    return RequestContextInterceptor().intercept_service(continuation, MagicMock())


class TestRequestContextInterceptorPeerAppId:
    @pytest.mark.asyncio
    async def test_sets_app_id_alongside_cn(self):
        captured = {}

        async def handler_fn(request, context):
            captured["cn"] = current_caller()
            captured["app_id"] = current_app_id()
            captured["raw"] = request_context.get(PEER_APP_ID)
            return None

        wrapped = await _intercepted(grpc.unary_unary_rpc_method_handler(handler_fn))
        await wrapped.unary_unary("req", _context_with_auth(_app_cert_auth()))

        # Both identities coexist: the process (CN) and the application (SAN).
        assert captured["cn"] == "gym-backend"
        assert captured["app_id"] == APP_ID
        assert captured["raw"] == APP_ID

    @pytest.mark.asyncio
    async def test_platform_cert_sets_cn_only(self):
        captured = {}

        async def handler_fn(request, context):
            captured["cn"] = current_caller()
            captured["app_id"] = current_app_id()
            return None

        wrapped = await _intercepted(grpc.unary_unary_rpc_method_handler(handler_fn))
        await wrapped.unary_unary("req", _context_with_auth(_platform_cert_auth()))

        assert captured["cn"] == "data-service"
        assert captured["app_id"] is None

    @pytest.mark.asyncio
    async def test_clears_app_id_after_handler(self):
        async def handler_fn(request, context):
            return None

        wrapped = await _intercepted(grpc.unary_unary_rpc_method_handler(handler_fn))
        await wrapped.unary_unary("req", _context_with_auth(_app_cert_auth()))

        assert request_context.get(PEER_APP_ID) is None
        assert current_app_id() is None

    @pytest.mark.asyncio
    async def test_streaming_handler_sets_and_clears_app_id(self):
        captured_app_id = None

        async def handler_fn(request, context):
            nonlocal captured_app_id
            captured_app_id = current_app_id()
            yield "a"

        wrapped = await _intercepted(grpc.unary_stream_rpc_method_handler(handler_fn))
        ctx = _context_with_auth(_app_cert_auth())
        items = [item async for item in wrapped.unary_stream("req", ctx)]

        assert items == ["a"]
        assert captured_app_id == APP_ID
        assert request_context.get(PEER_APP_ID) is None
