"""Socket Adapter - Unix Domain Socket transport for Local IPC.

Lets a Xime service talk to native engines (C++/Rust/Go) on the same machine
with constructor injection, controller scanning, and the same @command/@stream
contract used by Code-First gRPC.
Cho phép service Xime giao tiếp với native engine cùng máy qua UDS, dùng chung
contract @command/@stream với Code-First gRPC.

Public API:
    from xime.adapters.socket import (
        SocketAdapter, SocketClient,
        command, stream, UploadStream, DownloadStream,
        configure_socket_controllers, configure_socket_error_mappings,
    )
"""

from xime.core.contract import DownloadStream, UploadStream, command, stream

from ._adapter import SocketAdapter
from ._client import ClientUpload, SocketClient
from ._config import (
    SocketServerConfig,
    configure_socket_controllers,
    configure_socket_error_mappings,
)

__all__ = [
    # Adapter & client
    "SocketAdapter",
    "SocketClient",
    "ClientUpload",
    # Contract decorators (shared)
    "command",
    "stream",
    # Developer-facing streams
    "UploadStream",
    "DownloadStream",
    # Config
    "SocketServerConfig",
    "configure_socket_controllers",
    "configure_socket_error_mappings",
]
