from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from xime.adapters.grpc._descriptors import load_messages_from_descriptor_set
from xime.adapters.grpc.codefirst._marshal import pb2_to_pydantic, pydantic_to_pb2

"""Runtime support imported by generated client SDKs.

A generated SDK ships a FileDescriptorSet (_descriptors.binpb) instead of
*_pb2.py modules: message classes are built at import time inside a PRIVATE
DescriptorPool, so two SDKs in the same process never collide on module names
(the historical _pb2_loader weakness) and sys.path stays untouched. The same
loader now backs the code-first server too (see grpc/_descriptors.py).
SDK sinh ra mang theo FileDescriptorSet (_descriptors.binpb) thay vì *_pb2.py:
message class được dựng lúc import trong DescriptorPool RIÊNG, nên hai SDK
trong cùng process không bao giờ đụng tên module và không đụng sys.path.

Streaming follows the xime chunk-wrapper convention (see _stream_convention.py):
upload sends wrapper(metadata=...) first then wrapper(chunk=...); download
yields wrapper.chunk per message.
Streaming theo quy ước chunk-wrapper của xime: upload gửi wrapper(metadata=...)
trước rồi wrapper(chunk=...); download yield wrapper.chunk mỗi message.
"""


class SdkRuntime:
    """Loads the SDK's descriptor set and performs marshalling gRPC calls."""

    def __init__(self, descriptor_file: str | Path) -> None:
        self._messages = load_messages_from_descriptor_set(descriptor_file)

    def message_class(self, name: str) -> type:
        try:
            return self._messages[name]
        except KeyError:
            raise KeyError(
                f"Message '{name}' not found in the SDK descriptor set. "
                "Regenerate the client SDK (xime grpc client)."
            ) from None

    # ------------------------------------------------------------------
    # Call helpers — one per StreamKind
    # ------------------------------------------------------------------

    async def unary(
        self,
        channel: Any,
        path: str,
        request: BaseModel,
        request_message: str,
        response_model: type[BaseModel],
        response_message: str,
    ) -> BaseModel:
        req_cls = self.message_class(request_message)
        resp_cls = self.message_class(response_message)
        call = channel.unary_unary(
            path,
            request_serializer=_serialize,
            response_deserializer=resp_cls.FromString,
        )
        reply = await call(pydantic_to_pb2(request, req_cls))
        return pb2_to_pydantic(reply, response_model)

    async def client_stream(
        self,
        channel: Any,
        path: str,
        request: BaseModel,
        wrapper_message: str,
        response_model: type[BaseModel],
        response_message: str,
        chunks: AsyncIterator[bytes],
    ) -> BaseModel:
        wrapper_cls = self.message_class(wrapper_message)
        resp_cls = self.message_class(response_message)
        # The wrapper's `metadata` field is the real request DTO message; look
        # its class up by name in the same pool the wrapper came from.
        # Field `metadata` của wrapper là message DTO request thật; tra class
        # theo tên trong cùng pool với wrapper.
        meta_cls = self.message_class(
            wrapper_cls.DESCRIPTOR.fields_by_name["metadata"].message_type.name
        )

        async def stream() -> AsyncIterator[Any]:
            # First message carries the request metadata, the rest raw chunks.
            # Message đầu mang metadata request, các message sau là chunk thô.
            yield wrapper_cls(metadata=pydantic_to_pb2(request, meta_cls))
            async for chunk in chunks:
                yield wrapper_cls(chunk=chunk)

        call = channel.stream_unary(
            path,
            request_serializer=_serialize,
            response_deserializer=resp_cls.FromString,
        )
        reply = await call(stream())
        return pb2_to_pydantic(reply, response_model)

    async def server_stream(
        self,
        channel: Any,
        path: str,
        request: BaseModel,
        request_message: str,
        wrapper_message: str,
    ) -> AsyncIterator[bytes]:
        req_cls = self.message_class(request_message)
        wrapper_cls = self.message_class(wrapper_message)
        call = channel.unary_stream(
            path,
            request_serializer=_serialize,
            response_deserializer=wrapper_cls.FromString,
        )
        async for item in call(pydantic_to_pb2(request, req_cls)):
            yield item.chunk


def _serialize(message: Any) -> bytes:
    return message.SerializeToString()
