from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass

# Attribute name used to mark endpoint methods — internal to the framework.
# Tên attribute đánh dấu method là endpoint — nội bộ framework.
#
# Shared by every transport that speaks the Xime contract (Socket, Code-First
# gRPC, ...). A single decorator set means one Controller can serve multiple
# transports without declaring the contract twice.
# Dùng chung cho mọi transport nói "contract" của Xime (Socket, Code-First gRPC).
# Một bộ decorator → một Controller phục vụ nhiều transport, không khai báo hai lần.
ENDPOINT_ATTR = "_xime_endpoint"


class EndpointKind(enum.Enum):
    """High-level shape of an endpoint, as declared by its decorator.

    The transport adapter refines STREAM into upload/download by inspecting
    the method signature (UploadStream vs DownloadStream parameter).
    Adapter sẽ tinh chỉnh STREAM thành upload/download dựa trên chữ ký method.
    """

    COMMAND = "command"   # request → response (unary)
    STREAM = "stream"     # metadata + stream (upload hoặc download)


@dataclass
class EndpointInfo:
    """Metadata attached to a controller method by an endpoint decorator."""

    name: str             # wire name of the endpoint ("hash", "encrypt")
    kind: EndpointKind


def command(name: str) -> Callable:
    """Mark a controller method as a command endpoint (request → response).

    Example:
        @command("hash")
        async def hash(self, request: HashRequest) -> HashResponse:
            ...
    """
    def decorator(func: Callable) -> Callable:
        setattr(func, ENDPOINT_ATTR, EndpointInfo(name, EndpointKind.COMMAND))
        return func

    return decorator


def stream(name: str) -> Callable:
    """Mark a controller method as a stream endpoint.

    Whether it is an upload (client → server) or download (server → client)
    is inferred later from the parameter types (UploadStream / DownloadStream).
    Upload hay download được suy ra sau từ kiểu tham số.

    Example:
        @stream("encrypt")
        async def encrypt(self, request: EncryptRequest, upload: UploadStream) -> EncryptResponse:
            ...
    """
    def decorator(func: Callable) -> Callable:
        setattr(func, ENDPOINT_ATTR, EndpointInfo(name, EndpointKind.STREAM))
        return func

    return decorator
