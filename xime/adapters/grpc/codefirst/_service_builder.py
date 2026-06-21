from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any

import grpc
import grpc.aio

from xime.core.contract import DownloadStream, UploadStream

from ._marshal import pb2_to_pydantic, pydantic_to_pb2
from ._model import ContractModel, MethodContract, ServiceContract, StreamKind

if TYPE_CHECKING:
    from xime.core.bootstrap.application import Application

# Sentinel pushed onto the download queue when the handler finishes.
# Sentinel đẩy vào queue download khi handler kết thúc.
_DONE = object()


class CodeFirstGrpcBuilder:
    """Serves code-first controllers on a grpc.aio.Server.

    For each controller it registers a generic RPC handler whose behaviors
    marshal protobuf ↔ Pydantic at the boundary, so business code only ever
    deals with Pydantic models.
    Đăng ký generic handler cho mỗi controller; marshalling protobuf↔Pydantic tại
    biên để business code chỉ thấy Pydantic.

    Requires the generated *_pb2 message classes (run `xime grpc generate` first);
    the adapter passes them in via `messages`.
    Cần *_pb2 đã generate; adapter truyền vào qua `messages`.
    """

    def __init__(
        self,
        app: "Application",
        model: ContractModel,
        messages: dict[str, type],
    ) -> None:
        self._app = app
        self._model = model
        self._messages = messages

    def register_all(self, server: grpc.aio.Server) -> None:
        for service in self._model.services:
            instance = self._app.get(service.controller)
            handlers = self._build_handlers(service, instance)
            full_name = f"{self._package()}.{service.name}"
            generic = grpc.method_handlers_generic_handler(full_name, handlers)
            server.add_generic_rpc_handlers((generic,))

    # ------------------------------------------------------------------
    # Per-method handler construction
    # ------------------------------------------------------------------

    def _build_handlers(
        self, service: ServiceContract, instance: object
    ) -> dict[str, grpc.RpcMethodHandler]:
        handlers: dict[str, grpc.RpcMethodHandler] = {}
        for method in service.methods:
            bound = getattr(instance, method.handler_attr)
            if method.kind is StreamKind.UNARY:
                handlers[method.rpc_name] = self._unary_handler(method, bound)
            elif method.kind is StreamKind.CLIENT_STREAM:
                handlers[method.rpc_name] = self._client_stream_handler(method, bound)
            else:  # SERVER_STREAM
                handlers[method.rpc_name] = self._server_stream_handler(method, bound)
        return handlers

    def _unary_handler(self, method: MethodContract, bound: Any) -> grpc.RpcMethodHandler:
        req_pb2 = self._messages[method.request_message]
        resp_pb2 = self._messages[method.response_message]

        async def behavior(request: Any, context: grpc.aio.ServicerContext) -> Any:
            req_model = pb2_to_pydantic(request, method.request_py)
            resp_model = await bound(request=req_model)
            return pydantic_to_pb2(resp_model, resp_pb2)

        return grpc.unary_unary_rpc_method_handler(
            behavior,
            request_deserializer=req_pb2.FromString,
            response_serializer=_serialize,
        )

    def _client_stream_handler(self, method: MethodContract, bound: Any) -> grpc.RpcMethodHandler:
        wrapper_pb2 = self._messages[method.request_message]   # the *Chunk wrapper
        resp_pb2 = self._messages[method.response_message]

        async def behavior(request_iterator: Any, context: grpc.aio.ServicerContext) -> Any:
            upload = _GrpcUploadStream(request_iterator, method.request_py)
            req_model = await upload.prime()
            kwargs = {"request": req_model, method.stream_param: upload}
            resp_model = await bound(**kwargs)
            return pydantic_to_pb2(resp_model, resp_pb2)

        return grpc.stream_unary_rpc_method_handler(
            behavior,
            request_deserializer=wrapper_pb2.FromString,
            response_serializer=_serialize,
        )

    def _server_stream_handler(self, method: MethodContract, bound: Any) -> grpc.RpcMethodHandler:
        req_pb2 = self._messages[method.request_message]
        wrapper_pb2 = self._messages[method.response_message]  # the *Chunk wrapper

        async def behavior(request: Any, context: grpc.aio.ServicerContext):
            req_model = pb2_to_pydantic(request, method.request_py)
            download = _GrpcDownloadStream(wrapper_pb2)

            async def run() -> None:
                try:
                    kwargs = {"request": req_model, method.stream_param: download}
                    await bound(**kwargs)
                finally:
                    await download._queue.put(_DONE)

            task = asyncio.create_task(run())
            try:
                while True:
                    item = await download._queue.get()
                    if item is _DONE:
                        break
                    yield item
                await task  # re-raise handler exceptions → ErrorMappingInterceptor maps them
            finally:
                # On client cancellation the generator is closed (GeneratorExit
                # at `yield`) and `await task` is never reached — cancel the
                # handler task so it does not run on detached, writing to a queue
                # nobody reads.
                # Khi client cancel, generator bị đóng và `await task` không tới —
                # huỷ task handler để nó không chạy mồ côi.
                if not task.done():
                    task.cancel()

        return grpc.unary_stream_rpc_method_handler(
            behavior,
            request_deserializer=req_pb2.FromString,
            response_serializer=_serialize,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _package(self) -> str:
        return f"xime.{re.sub(r'[^0-9a-zA-Z_]', '_', self._model.server_id)}"


def _serialize(message: Any) -> bytes:
    return message.SerializeToString()


# ---------------------------------------------------------------------------
# Stream adapters — bridge gRPC streaming to the shared Upload/DownloadStream
# ---------------------------------------------------------------------------

class _GrpcUploadStream(UploadStream):
    """Wraps a gRPC client-streaming request iterator as an UploadStream.

    The first wrapper message carries the request metadata; the rest carry
    raw chunk bytes (per the upload chunk-wrapper convention).
    Message wrapper đầu mang metadata; các message sau mang chunk bytes.
    """

    def __init__(self, request_iterator: Any, request_py: type) -> None:
        self._it = request_iterator.__aiter__()
        self._request_py = request_py

    async def prime(self) -> Any:
        """Read the first message and return the decoded request metadata."""
        first = await self._it.__anext__()
        return pb2_to_pydantic(first.metadata, self._request_py)

    def __aiter__(self) -> "_GrpcUploadStream":
        return self

    async def __anext__(self) -> bytes:
        chunk = await self.read()
        if chunk is None:
            raise StopAsyncIteration
        return chunk

    async def read(self) -> bytes | None:
        try:
            message = await self._it.__anext__()
        except StopAsyncIteration:
            return None
        return message.chunk


class _GrpcDownloadStream(DownloadStream):
    """Collects handler writes into wrapper messages yielded by the server stream."""

    def __init__(self, wrapper_pb2: type) -> None:
        self._wrapper_pb2 = wrapper_pb2
        self._queue: asyncio.Queue = asyncio.Queue()

    async def write(self, chunk: bytes) -> None:
        await self._queue.put(self._wrapper_pb2(chunk=chunk))
