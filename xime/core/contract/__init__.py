"""Shared contract layer.

Decorators and scanning logic used by every Xime transport that maps a
controller method to a remote endpoint (Socket Adapter, Code-First gRPC, ...).
Keeping these here means a single Controller can serve multiple transports
without re-declaring its contract.
Lớp contract dùng chung cho mọi transport — một Controller phục vụ nhiều transport
mà không khai báo lại contract.
"""

from xime.core.contract._decorators import (
    ENDPOINT_ATTR,
    EndpointInfo,
    EndpointKind,
    command,
    stream,
)
from xime.core.contract._scanner import ControllerScanner
from xime.core.contract._streams import DownloadStream, UploadStream

__all__ = [
    "ENDPOINT_ATTR",
    "EndpointInfo",
    "EndpointKind",
    "command",
    "stream",
    "ControllerScanner",
    "UploadStream",
    "DownloadStream",
]
