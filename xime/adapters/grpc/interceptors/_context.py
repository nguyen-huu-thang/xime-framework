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
    """

    async def intercept_service(
        self,
        continuation: Callable[..., Coroutine[Any, Any, Any]],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler:
        request_context.set("request_id", str(uuid.uuid4()))
        try:
            return await continuation(handler_call_details)
        finally:
            request_context.clear()
            clear_security()
