from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import grpc
import grpc.aio

from xime.core.context import request_context
from xime.core.security import clear_security


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
            try:
                async for item in fn(*args, **kwargs):
                    yield item
            finally:
                request_context.clear()
                clear_security()

        return wrapper
