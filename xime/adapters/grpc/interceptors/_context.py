from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import grpc
import grpc.aio

from xime.core.context import request_context
from xime.core.security import clear_security
from xime.core.security.peer import PEER_CN, PEER_SANS


def _auth_values(auth: Any, property_name: str) -> list[Any]:
    """Return the values of a gRPC auth-context property, or an empty list.

    grpc exposes property names as str keys mapping to list[bytes]; tolerate a
    bytes key as well across grpc versions.
    grpc trả key str -> list[bytes]; chấp nhận cả key bytes cho chắc.
    """
    values = auth.get(property_name) or auth.get(property_name.encode("ascii"))
    return list(values) if values else []


def _read_peer_cn(context: Any) -> str | None:
    """Return the verified client-certificate Common Name, or None.

    Reads the CN from the gRPC ServicerContext's auth_context(), which is only
    populated when the call arrived over verified mTLS. Returns None for every
    other case (plaintext, server-only TLS, missing CN) so it degrades cleanly.
    Đọc CN từ auth_context() - chỉ có khi call đến qua mTLS đã verify. Trả None
    cho mọi trường hợp còn lại để fail-soft.

    Fail-soft by design: any exception (e.g. context is a test double without
    auth_context) is swallowed and treated as "no peer identity" so it can never
    break a request.
    Cố ý fail-soft: mọi exception bị nuốt và coi như "không có danh tính peer".
    """
    if context is None:
        return None
    try:
        auth = context.auth_context()
    except Exception:
        return None
    if not auth:
        return None

    values = _auth_values(auth, "x509_common_name")
    if not values:
        return None

    value = values[0]
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    return str(value)


def _read_peer_sans(context: Any) -> tuple[str, ...]:
    """Return every Subject Alternative Name of the client certificate.

    Unlike the CN, SANs are a multi-valued property, and gRPC hands them over as
    a FLAT, UNTAGGED list: DNS names, IP addresses and URIs arrive mixed together
    with nothing marking which is which. So this returns all of them, decoded and
    in the order gRPC supplied, and interprets nothing - picking out a particular
    entry is the caller's job, because only the caller knows what it is looking
    for.
    Khác CN, SAN là property nhiều giá trị, và gRPC trả về một danh sách PHẲNG,
    KHÔNG GẮN NHÃN: tên DNS, địa chỉ IP và URI lẫn vào nhau, không có gì phân
    biệt. Nên hàm này trả HẾT, đã decode, giữ nguyên thứ tự gRPC đưa, và không
    diễn giải gì - chọn ra entry nào là việc của bên gọi, vì chỉ bên gọi biết
    mình đang tìm cái gì.

    Fail-soft by design, exactly like _read_peer_cn: no mTLS, no such property or
    an unreadable context all yield an empty tuple instead of raising. Individual
    entries that do not decode as UTF-8 are skipped, so one bad entry can never
    hide a good one behind it. A strange certificate must never be able to break
    a request.
    Cố ý fail-soft y như _read_peer_cn: không mTLS, không có property, context
    không đọc được đều trả tuple rỗng chứ không ném. Entry nào không decode được
    UTF-8 thì bỏ qua, nên một entry rác không bao giờ che được entry hợp lệ đứng
    sau nó.
    """
    if context is None:
        return ()
    try:
        auth = context.auth_context()
    except Exception:
        return ()
    if not auth:
        return ()

    entries: list[str] = []
    for value in _auth_values(auth, "x509_subject_alternative_name"):
        if isinstance(value, bytes):
            try:
                entries.append(value.decode("utf-8"))
            except UnicodeDecodeError:
                continue
        else:
            entries.append(str(value))
    return tuple(entries)


def _set_peer_identity(handler_args: tuple[Any, ...]) -> None:
    """Store the verified peer identity in request_context, as far as available.

    gRPC handlers are invoked as (request, context) / (request_iterator, context),
    so the ServicerContext is the second positional argument. Two neutral keys are
    written when the certificate supplies them: PEER_CN identifies the calling
    process, PEER_SANS carries every Subject Alternative Name. Both stay raw and
    uninterpreted - the framework reports what the certificate said, nothing more.
    Handler được gọi dạng (request, context) nên context là tham số thứ hai. Ghi
    hai key trung tính khi cert có: PEER_CN định danh tiến trình gọi, PEER_SANS
    chở mọi SAN. Cả hai giữ nguyên dạng thô - framework thuật lại đúng thứ cert
    khai, không hơn.

    Neither key is written when there is nothing to report, so an absent key means
    "the certificate did not supply this" rather than "supplied and empty". The
    question of whether the call arrived over mTLS at all is already answered by
    PEER_CN, so PEER_SANS does not have to carry it too.
    Không key nào được ghi khi không có gì để thuật, nên key VẮNG MẶT nghĩa là
    "cert không cấp thứ này" chứ không phải "có mà rỗng". Câu "lời gọi có qua mTLS
    hay không" đã do PEER_CN trả lời, nên PEER_SANS không phải chở thêm nghĩa đó.
    """
    context = handler_args[1] if len(handler_args) > 1 else None
    cn = _read_peer_cn(context)
    if cn is not None:
        request_context.set(PEER_CN, cn)
    sans = _read_peer_sans(context)
    if sans:
        request_context.set(PEER_SANS, sans)


class RequestContextInterceptor(grpc.aio.ServerInterceptor):
    """Set up and tear down request-scoped context for each gRPC call.

    Mirrors RequestContextMiddleware for HTTP:
      Startup : assign a UUID request_id to request_context
      Teardown: clear request_context and security context to prevent
                data bleeding between concurrent calls on the same worker.

    Always runs as the outermost interceptor so that every other interceptor
    and handler downstream can read request_context safely.

    Implementation note: intercept_service() wraps the *handler function*
    returned by continuation(), not the continuation() call itself.
    With grpc.aio, continuation() only returns an RpcMethodHandler descriptor
 - the actual RPC invocation happens later.  Wrapping at the handler level
    ensures the context is set and cleared around each real invocation.
    """

    async def intercept_service(
        self,
        continuation: Callable[..., Coroutine[Any, Any, Any]],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler:
        handler = await continuation(handler_call_details)
        if handler is None:
            return handler
        return self._wrap_handler(handler)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _wrap_handler(self, handler: grpc.RpcMethodHandler) -> grpc.RpcMethodHandler:
        """Return a new RpcMethodHandler whose invocation function sets/clears context.

        Response-streaming handlers (unary_stream / stream_stream) are async
        generator functions, so they must be wrapped with `async for ... yield`,
        not `await` - awaiting an async_generator raises TypeError and breaks
        every server-streaming RPC. Mirrors ErrorMappingInterceptor.
        Handler có response-streaming là async generator nên phải bọc bằng
        `async for ... yield`, không được `await` (sẽ TypeError, hỏng mọi RPC
        server-streaming). Giống ErrorMappingInterceptor.
        """
        if handler.request_streaming and handler.response_streaming:
            return handler._replace(
                stream_stream=self._wrap_streaming(handler.stream_stream)
            )
        elif handler.request_streaming:
            return handler._replace(
                stream_unary=self._wrap_unary(handler.stream_unary)
            )
        elif handler.response_streaming:
            return handler._replace(
                unary_stream=self._wrap_streaming(handler.unary_stream)
            )
        else:
            return handler._replace(
                unary_unary=self._wrap_unary(handler.unary_unary)
            )

    @staticmethod
    def _wrap_unary(fn: Callable[..., Any] | None) -> Callable[..., Any] | None:
        """Wrap a unary (or client-streaming) handler coroutine."""
        if fn is None:
            return fn

        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request_context.set("request_id", str(uuid.uuid4()))
            _set_peer_identity(args)
            try:
                return await fn(*args, **kwargs)
            finally:
                request_context.clear()
                clear_security()

        return wrapper

    @staticmethod
    def _wrap_streaming(fn: Callable[..., Any] | None) -> Callable[..., Any] | None:
        """Wrap a server-streaming (or bidirectional) async-generator handler."""
        if fn is None:
            return fn

        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request_context.set("request_id", str(uuid.uuid4()))
            _set_peer_identity(args)
            try:
                async for item in fn(*args, **kwargs):
                    yield item
            finally:
                request_context.clear()
                clear_security()

        return wrapper
