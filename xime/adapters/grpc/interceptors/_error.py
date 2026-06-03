from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any

import grpc
import grpc.aio


class ErrorMappingInterceptor(grpc.aio.ServerInterceptor):
    """Map business exceptions to gRPC StatusCodes automatically.

    Wraps every handler method (unary/stream variants) so that when a handler
    raises a mapped exception, gRPC sends the corresponding status code to the
    client instead of a generic INTERNAL error.

    Unmapped exceptions become StatusCode.INTERNAL (grpc default behavior).
    Exceptions that are already grpc.RpcError are re-raised untouched — they
    carry a status code already set by the handler or a lower interceptor.

    Usage:
        ErrorMappingInterceptor({
            NotFoundException:   grpc.StatusCode.NOT_FOUND,
            ValidationException: grpc.StatusCode.INVALID_ARGUMENT,
        })
    """

    def __init__(
        self,
        mappings: dict[type[Exception], grpc.StatusCode],
    ) -> None:
        self._mappings = mappings

    async def intercept_service(
        self,
        continuation: Callable[..., Coroutine[Any, Any, grpc.RpcMethodHandler | None]],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler | None:
        handler = await continuation(handler_call_details)
        if handler is None:
            return None

        # Replace whichever handler variant is set; only one will be non-None.
        if handler.unary_unary is not None:
            return handler._replace(unary_unary=self._wrap_unary(handler.unary_unary))
        if handler.unary_stream is not None:
            return handler._replace(unary_stream=self._wrap_streaming(handler.unary_stream))
        if handler.stream_unary is not None:
            return handler._replace(stream_unary=self._wrap_unary(handler.stream_unary))
        if handler.stream_stream is not None:
            return handler._replace(stream_stream=self._wrap_streaming(handler.stream_stream))

        return handler

    # ------------------------------------------------------------------
    # Wrapper factories
    # ------------------------------------------------------------------

    def _wrap_unary(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap a unary (or client-streaming) handler coroutine."""
        interceptor = self

        async def wrapped(request_or_iterator: Any, context: grpc.aio.ServicerContext) -> Any:
            try:
                return await fn(request_or_iterator, context)
            except Exception as exc:
                if isinstance(exc, grpc.RpcError):
                    raise
                await context.abort(interceptor._resolve_status_code(exc), str(exc))

        return wrapped

    def _wrap_streaming(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap a server-streaming (or bidirectional) async-generator handler."""
        interceptor = self

        async def wrapped(
            request_or_iterator: Any,
            context: grpc.aio.ServicerContext,
        ) -> AsyncIterator[Any]:
            try:
                async for item in fn(request_or_iterator, context):
                    yield item
            except Exception as exc:
                if isinstance(exc, grpc.RpcError):
                    raise
                await context.abort(interceptor._resolve_status_code(exc), str(exc))

        return wrapped

    # ------------------------------------------------------------------
    # Status code resolution
    # ------------------------------------------------------------------

    def _resolve_status_code(self, exc: Exception) -> grpc.StatusCode:
        """Return the mapped StatusCode, or INTERNAL if no mapping found."""
        for exc_type, status_code in self._mappings.items():
            if isinstance(exc, exc_type):
                return status_code
        return grpc.StatusCode.INTERNAL
