from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import grpc
import grpc.aio

from xime.core.context import request_context
from xime.core.security import clear_security
from xime.core.security.peer import PEER_APP_ID, PEER_CN

# URI scheme a peer certificate uses to carry the identity of the application
# owning the process. Certificates of processes that belong to no application
# simply do not have such an entry.
# Scheme URI cert peer dùng để mang định danh app sở hữu tiến trình. Cert của
# tiến trình không thuộc app nào thì đơn giản là không có entry này.
_APP_ID_SCHEME = "xime-app://"

# Expected length of the identity that follows the scheme. Used only as a cheap
# shape check so a malformed SAN is dropped instead of propagating downstream;
# the framework never decodes or validates the identity itself.
# Độ dài định danh đứng sau scheme. Chỉ dùng để kiểm hình dạng cho rẻ, SAN dị
# dạng bị bỏ thay vì lọt xuống dưới; framework không giải mã hay kiểm nội dung.
_APP_ID_LENGTH = 33


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


def _read_peer_app_id(context: Any) -> str | None:
    """Return the application identity carried by the client certificate, or None.

    Reads the Subject Alternative Names of a verified client certificate and
    returns the identity behind the `xime-app://` URI entry, with the scheme
    stripped so consumers get the identity in the same form the platform uses
    everywhere else. Unlike the CN, SANs are a multi-valued property (a
    certificate typically also carries DNS, IP and spiffe entries), so every
    entry is examined and unrelated ones are skipped.
    Đọc SAN của client cert đã verify và trả định danh nằm sau entry URI
    `xime-app://`, đã cắt scheme để consumer nhận đúng dạng platform vẫn dùng.
    Khác CN, SAN là property nhiều giá trị (cert thường còn mang DNS, IP,
    spiffe), nên phải duyệt mọi entry và bỏ qua entry không liên quan.

    Fail-soft by design, exactly like _read_peer_cn: no mTLS, no such entry, an
    undecodable value or an identity of unexpected length all yield None instead
    of raising. A strange certificate must never be able to break a request.
    Cố ý fail-soft y như _read_peer_cn: không mTLS, không có entry, giá trị không
    decode được hay định danh sai độ dài đều trả None chứ không ném. Một cert lạ
    không bao giờ được phép làm hỏng request.
    """
    if context is None:
        return None
    try:
        auth = context.auth_context()
    except Exception:
        return None
    if not auth:
        return None

    for value in _auth_values(auth, "x509_subject_alternative_name"):
        if isinstance(value, bytes):
            try:
                entry = value.decode("utf-8")
            except UnicodeDecodeError:
                continue
        else:
            entry = str(value)

        # Search for the scheme rather than matching the start of the entry:
        # grpc may hand the URI over bare or prefixed with its SAN type (the
        # "URI:" form openssl prints), and both must work.
        # Tìm scheme thay vì so đầu chuỗi: grpc có thể trả URI trần hoặc kèm
        # tiền tố loại SAN (dạng "URI:" như openssl in), cả hai đều phải chạy.
        position = entry.find(_APP_ID_SCHEME)
        if position < 0:
            continue

        app_id = entry[position + len(_APP_ID_SCHEME):]
        if len(app_id) != _APP_ID_LENGTH:
            continue
        return app_id

    return None


def _set_peer_identity(handler_args: tuple[Any, ...]) -> None:
    """Store the verified peer identity in request_context, as far as available.

    gRPC handlers are invoked as (request, context) / (request_iterator, context),
    so the ServicerContext is the second positional argument. Two neutral keys are
    written when the certificate supplies them: PEER_CN identifies the calling
    process, PEER_APP_ID the application owning it. Both stay raw - the CN may be
    a service id OR an application identity, and callers interpret them
    themselves.
    Handler được gọi dạng (request, context) nên context là tham số thứ hai. Ghi
    hai key trung tính khi cert có: PEER_CN định danh tiến trình gọi, PEER_APP_ID
    định danh app sở hữu nó. Cả hai giữ nguyên dạng thô - app tự diễn giải.
    """
    context = handler_args[1] if len(handler_args) > 1 else None
    cn = _read_peer_cn(context)
    if cn is not None:
        request_context.set(PEER_CN, cn)
    app_id = _read_peer_app_id(context)
    if app_id is not None:
        request_context.set(PEER_APP_ID, app_id)


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
    — the actual RPC invocation happens later.  Wrapping at the handler level
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
        not `await` — awaiting an async_generator raises TypeError and breaks
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
