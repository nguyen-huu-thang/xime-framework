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

Subject Alternative Names of the peer certificate (0.7.1):

  _read_peer_sans():
    - context None / auth_context() raises / empty → () (fail-soft)
    - no x509_subject_alternative_name key → ()
    - EVERY entry is returned, in the order the transport supplied
    - entries of any scheme, DNS names and IP addresses are all kept - the
      framework interprets nothing and filters nothing
    - SAN key as bytes → decoded; str values accepted as-is
    - non-utf8 entry skipped, a valid later entry still returned

  RequestContextInterceptor (SANs):
    - sets peer_sans alongside peer_cn
    - cert with a CN but no SANs → peer_cn set, peer_sans ABSENT (not empty)
    - clears peer_sans after the handler completes
    - streaming handler also sets/clears peer_sans

⚠ Test data here is deliberately NEUTRAL (spiffe:// plus an invented scheme).
The framework must not know any particular deployment's URI scheme, so its tests
must not encode one either.
⚠ Dữ liệu mẫu ở đây CỐ Ý trung tính (spiffe:// và một scheme tự đặt). Framework
không được biết scheme URI của bất kỳ nơi triển khai nào, nên test của nó cũng
không được nhúng một scheme cụ thể vào.
"""
import grpc
import pytest
from unittest.mock import MagicMock

from xime.adapters.grpc.interceptors._context import (
    RequestContextInterceptor,
    _read_peer_cn,
    _read_peer_sans,
)
from xime.core.context import request_context
from xime.core.security import current_caller, current_peer_sans
from xime.core.security.peer import PEER_CN, PEER_SANS

# A SPIFFE ID, the industry-standard way of carrying workload identity in a SAN.
# Một SPIFFE ID - cách chuẩn công nghiệp để chở định danh workload trong SAN.
SPIFFE_ID = "spiffe://cluster.local/ns/default/sa/api"

# An invented scheme, standing in for whatever a deployment chooses to use.
# Its shape is deliberately unlike SPIFFE's so the tests prove the framework
# keeps entries it knows nothing about.
# Một scheme tự đặt, đại diện cho thứ mà một nơi triển khai tự chọn dùng. Hình
# dạng cố ý khác SPIFFE để test chứng minh framework giữ cả entry nó không biết.
CUSTOM_URI = "acme-workload://team-7/checkout"


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
# _read_peer_sans
# ---------------------------------------------------------------------------

def _cert_auth_with_sans():
    """auth_context() of a certificate carrying a realistic mix of SAN entries.

    Four entries of three different kinds, and gRPC reports them FLAT with no
    tag saying which is which - that is exactly why the framework cannot filter.
    Bốn entry thuộc ba loại khác nhau, và gRPC trả PHẲNG không nhãn - đó chính là
    lý do framework không thể lọc.
    """
    return {
        "x509_common_name": [b"api-backend"],
        "x509_subject_alternative_name": [
            SPIFFE_ID.encode(),
            b"localhost",
            b"127.0.0.1",
            CUSTOM_URI.encode(),
        ],
    }


def _cert_auth_cn_only():
    """auth_context() of a certificate with a CN but no SAN entries at all."""
    return {"x509_common_name": [b"legacy-client"]}


class TestReadPeerSans:
    def test_none_context_returns_empty(self):
        assert _read_peer_sans(None) == ()

    def test_auth_context_raises_returns_empty(self):
        assert _read_peer_sans(_raising_context()) == ()

    def test_empty_auth_context_returns_empty(self):
        assert _read_peer_sans(_context_with_auth({})) == ()

    def test_missing_san_key_returns_empty(self):
        auth = {"x509_common_name": [b"data-service"]}
        assert _read_peer_sans(_context_with_auth(auth)) == ()

    def test_returns_every_entry_in_transport_order(self):
        result = _read_peer_sans(_context_with_auth(_cert_auth_with_sans()))
        assert result == (SPIFFE_ID, "localhost", "127.0.0.1", CUSTOM_URI)

    def test_keeps_entries_of_schemes_it_knows_nothing_about(self):
        # The framework must not have an opinion about which scheme is "the"
        # identity scheme. Both URI entries survive, untouched and unstripped.
        # Framework không được có ý kiến scheme nào là scheme định danh "chính".
        result = _read_peer_sans(_context_with_auth(_cert_auth_with_sans()))
        assert SPIFFE_ID in result
        assert CUSTOM_URI in result

    def test_keeps_entries_of_any_length(self):
        # Guards the 0.7.1 removal of a hard-coded identity-length check: a
        # length rule belongs to whoever owns the identity format, never here.
        # Canh việc 0.7.1 gỡ phép kiểm độ dài đóng cứng: luật độ dài thuộc về bên
        # sở hữu định dạng định danh, không bao giờ thuộc về đây.
        auth = {"x509_subject_alternative_name": [b"x://a", b"x://" + b"z" * 200]}
        assert _read_peer_sans(_context_with_auth(auth)) == (
            "x://a",
            "x://" + "z" * 200,
        )

    def test_does_not_strip_any_prefix(self):
        # Entries are handed back verbatim, including a SAN type label if the
        # transport happens to add one. Stripping is interpretation.
        # Trả nguyên văn, kể cả nhãn loại SAN nếu transport có thêm. Cắt bỏ là
        # diễn giải.
        auth = {"x509_subject_alternative_name": [b"URI:" + CUSTOM_URI.encode()]}
        assert _read_peer_sans(_context_with_auth(auth)) == ("URI:" + CUSTOM_URI,)

    def test_san_key_as_bytes_is_read(self):
        auth = {b"x509_subject_alternative_name": [SPIFFE_ID.encode()]}
        assert _read_peer_sans(_context_with_auth(auth)) == (SPIFFE_ID,)

    def test_str_san_values_are_accepted(self):
        auth = {"x509_subject_alternative_name": [SPIFFE_ID]}
        assert _read_peer_sans(_context_with_auth(auth)) == (SPIFFE_ID,)

    def test_non_utf8_entry_is_skipped_not_raised(self):
        auth = {"x509_subject_alternative_name": [b"\xff\xfe"]}
        assert _read_peer_sans(_context_with_auth(auth)) == ()

    def test_non_utf8_entry_does_not_hide_a_later_valid_entry(self):
        auth = {
            "x509_subject_alternative_name": [b"\xff\xfe", SPIFFE_ID.encode()],
        }
        assert _read_peer_sans(_context_with_auth(auth)) == (SPIFFE_ID,)


# ---------------------------------------------------------------------------
# RequestContextInterceptor — peer SANs
# ---------------------------------------------------------------------------

def _intercepted(handler):
    """Run a handler through RequestContextInterceptor and return the wrapper."""

    async def continuation(details):
        return handler

    return RequestContextInterceptor().intercept_service(continuation, MagicMock())


class TestRequestContextInterceptorPeerSans:
    @pytest.mark.asyncio
    async def test_sets_sans_alongside_cn(self):
        captured = {}

        async def handler_fn(request, context):
            captured["cn"] = current_caller()
            captured["sans"] = current_peer_sans()
            captured["raw"] = request_context.get(PEER_SANS)
            return None

        wrapped = await _intercepted(grpc.unary_unary_rpc_method_handler(handler_fn))
        await wrapped.unary_unary("req", _context_with_auth(_cert_auth_with_sans()))

        # Both facts coexist: the CN and the full SAN list, neither interpreted.
        assert captured["cn"] == "api-backend"
        assert captured["sans"] == (SPIFFE_ID, "localhost", "127.0.0.1", CUSTOM_URI)
        assert captured["raw"] == captured["sans"]

    @pytest.mark.asyncio
    async def test_cert_without_sans_leaves_the_key_ABSENT(self):
        # Half of a deliberate pair with the test above. The key is absent, not
        # an empty tuple: absent means "the certificate did not supply this".
        # Whether mTLS happened at all is answered by PEER_CN, so PEER_SANS must
        # not carry that second meaning as well.
        # Một nửa của cặp test cố ý. Khoá VẮNG MẶT, không phải tuple rỗng: vắng
        # nghĩa là "cert không cấp thứ này". Câu có mTLS hay không đã do PEER_CN
        # trả lời, nên PEER_SANS không được chở thêm nghĩa thứ hai đó.
        captured = {}

        async def handler_fn(request, context):
            captured["cn"] = current_caller()
            captured["sans"] = current_peer_sans()
            captured["contains"] = PEER_SANS in request_context
            return None

        wrapped = await _intercepted(grpc.unary_unary_rpc_method_handler(handler_fn))
        await wrapped.unary_unary("req", _context_with_auth(_cert_auth_cn_only()))

        assert captured["cn"] == "legacy-client"
        assert captured["sans"] is None
        assert captured["contains"] is False

    @pytest.mark.asyncio
    async def test_clears_sans_after_handler(self):
        async def handler_fn(request, context):
            return None

        wrapped = await _intercepted(grpc.unary_unary_rpc_method_handler(handler_fn))
        await wrapped.unary_unary("req", _context_with_auth(_cert_auth_with_sans()))

        assert request_context.get(PEER_SANS) is None
        assert current_peer_sans() is None

    @pytest.mark.asyncio
    async def test_streaming_handler_sets_and_clears_sans(self):
        captured_sans = None

        async def handler_fn(request, context):
            nonlocal captured_sans
            captured_sans = current_peer_sans()
            yield "a"

        wrapped = await _intercepted(grpc.unary_stream_rpc_method_handler(handler_fn))
        ctx = _context_with_auth(_cert_auth_with_sans())
        items = [item async for item in wrapped.unary_stream("req", ctx)]

        assert items == ["a"]
        assert captured_sans == (SPIFFE_ID, "localhost", "127.0.0.1", CUSTOM_URI)
        assert request_context.get(PEER_SANS) is None
