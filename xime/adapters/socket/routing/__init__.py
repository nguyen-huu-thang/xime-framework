"""Socket routing layer.

Re-exports the shared contract decorators (@command / @stream) and the
configure helper so socket controllers import everything from one place,
mirroring xime.adapters.web.routing.
Tái export decorator dùng chung + helper config để controller import từ một chỗ.
"""

from xime.core.contract import command, stream

from .._config import configure_socket_controllers
from ._builder import ResolvedEndpoint, SocketEndpointBuilder

__all__ = [
    "command",
    "stream",
    "configure_socket_controllers",
    "ResolvedEndpoint",
    "SocketEndpointBuilder",
]
