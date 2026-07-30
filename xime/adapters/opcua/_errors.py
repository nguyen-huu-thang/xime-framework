"""Exception hierarchy for the OPC UA adapter.

Mirrors the Modbus split, for the same reason: the useful question after a
failure is "is the link down, or is my model wrong?", and one generic error
answers neither.
"""

from __future__ import annotations

from xime.core.exception.framework import XimeException


class OpcuaError(XimeException):
    """Base class for every OPC UA adapter failure."""


class OpcuaConnectionError(OpcuaError):
    """The server is unreachable, or the session dropped. Retrying may help."""


class OpcuaNodeError(OpcuaError):
    """The server answered and refused: unknown NodeId, wrong attribute, or
    an unreadable/unwritable node. Retrying the same request will fail again."""
