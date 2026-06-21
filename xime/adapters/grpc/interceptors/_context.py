from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import grpc
import grpc.aio

from xime.core.context import request_context
from xime.core.security import clear_security
from xime.core.security.peer import PEER_CN


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

    # grpc exposes property names as str keys mapping to list[bytes]; tolerate a
    # bytes key as well across grpc versions.
    # grpc trả key str -> list[bytes]; chấp nhận cả key bytes cho chắc.
    values = auth.get("x509_common_name") or auth.get(b"x509_common_name")
    if not values:
        return None

    value = values[0]
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    return str(value)


def _set_peer_cn(handler_args: tuple[Any, ...]) -> None:
    """Store the peer CN in request_context if present.

    gRPC handlers are invoked as (request, context) / (request_iterator, context),
    so the ServicerContext is the second positional argument. Stored under the
    neutral key PEER_CN - the CN may be a service id OR an application identity,
    callers interpret it themselves.
    Handler được gọi dạng (request, context) nên context là tham số thứ hai.
    Lưu dưới key trung tính PEER_CN - app tự diễn giải.
    """
    context = handler_args[1] if len(handler_args) > 1 else None
    cn = _read_peer_cn(context)
    if cn is not None:
        request_context.set(PEER_CN, cn)


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
            _set_peer_cn(args)
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
            _set_peer_cn(args)
            try:
                async for item in fn(*args, **kwargs):
                    yield item
            finally:
                request_context.clear()
                clear_security()

        return wrapper
