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
    Exceptions that are already grpc.RpcError are re-raised untouched - they
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
                # grpc.RpcError carries a status already; grpc.aio.AbortError is
                # raised by an inner interceptor/handler that already called
                # context.abort() - it is NOT a subclass of grpc.RpcError, so
                # without this it would be aborted a second time here. Re-raise
                # both as terminal.
                # grpc.RpcError đã có status; grpc.aio.AbortError nghĩa là một
                # interceptor/handler bên trong đã abort rồi (nó KHÔNG kế thừa
                # grpc.RpcError) - thiếu nhánh này sẽ abort lần hai. Re-raise cả hai.
                if isinstance(exc, (grpc.RpcError, grpc.aio.AbortError)):
                    raise
                await context.abort(
                    interceptor._resolve_status_code(exc),
                    interceptor._safe_details(exc),
                    trailing_metadata=_error_metadata(exc, interceptor._is_mapped(exc)),
                )

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
                # grpc.RpcError carries a status already; grpc.aio.AbortError is
                # raised by an inner interceptor/handler that already called
                # context.abort() - it is NOT a subclass of grpc.RpcError, so
                # without this it would be aborted a second time here. Re-raise
                # both as terminal.
                # grpc.RpcError đã có status; grpc.aio.AbortError nghĩa là một
                # interceptor/handler bên trong đã abort rồi (nó KHÔNG kế thừa
                # grpc.RpcError) - thiếu nhánh này sẽ abort lần hai. Re-raise cả hai.
                if isinstance(exc, (grpc.RpcError, grpc.aio.AbortError)):
                    raise
                await context.abort(
                    interceptor._resolve_status_code(exc),
                    interceptor._safe_details(exc),
                    trailing_metadata=_error_metadata(exc, interceptor._is_mapped(exc)),
                )

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

    def _safe_details(self, exc: Exception) -> str:
        """Message sent to the client.

        Mapped (business) exceptions expose their own message intentionally -
        the developer chose to surface them. Unmapped exceptions fall back to a
        generic string so internal details (str(exc)) never leak to the caller.
        Lỗi đã map: phơi message có chủ đích. Lỗi chưa map: trả message chung,
        không để chi tiết nội bộ lọt ra client.
        """
        if self._is_mapped(exc):
            return str(exc)
        return _GENERIC_INTERNAL_DETAILS

    def _is_mapped(self, exc: Exception) -> bool:
        """True when the developer deliberately exposed this exception type."""
        return any(isinstance(exc, exc_type) for exc_type in self._mappings)


# Trailing metadata key carrying the server-side exception class name so a
# Xime client SDK can expose a typed error code (RemoteCallError.code).
# Key trailing metadata mang tên exception phía server để client SDK
# phơi ra code lỗi typed (RemoteCallError.code).
XIME_ERROR_METADATA_KEY = "xime-error"

# Generic message for unmapped exceptions so str(exc) (internal detail) never
# reaches the client. Visibility-aware redaction (Private/System/Public) is a
# separate, larger design tracked for a later version (#1b).
# Message chung cho lỗi chưa map để str(exc) không lọt ra client.
_GENERIC_INTERNAL_DETAILS = "Internal server error"


# Name reported for an exception the developer never mapped. The class name of
# an internal exception is a small but real disclosure (it names libraries, ORM
# internals and file layers), and _safe_details() already hides str(exc) for the
# same reason - reporting the real name here undid half of that.
# Tên báo ra cho exception chưa map. Tên class nội bộ vẫn là rò rỉ (nó khai ra
# thư viện, nội bộ ORM, tầng file), và _safe_details() vốn đã che str(exc) vì
# đúng lý do đó.
_GENERIC_INTERNAL_NAME = "InternalError"


def _error_metadata(exc: Exception, mapped: bool = True) -> tuple[tuple[str, str], ...]:
    name = type(exc).__name__ if mapped else _GENERIC_INTERNAL_NAME
    return ((XIME_ERROR_METADATA_KEY, name),)
