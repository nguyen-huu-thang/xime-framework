from __future__ import annotations

import asyncio
import enum
import struct
from dataclasses import dataclass

from xime.core.exception.framework import ProtocolError

# ---------------------------------------------------------------------------
# Wire frame
# ---------------------------------------------------------------------------
#
# Every message on the socket is a fixed 16-byte header + variable payload:
# Mỗi message trên socket = header cố định 16 byte + payload thay đổi:
#
#   ┌────────┬─────────┬──────────┬──────────────┬─────────────┬──────────┐
#   │ MAGIC  │ VERSION │ MSG_TYPE │  SESSION_ID   │ PAYLOAD_LEN │ PAYLOAD  │
#   │ 2 byte │  1 byte │  1 byte  │   8 byte u64  │  4 byte u32 │   ...    │
#   └────────┴─────────┴──────────┴──────────────┴─────────────┴──────────┘
#       "XM"     0x01                 big-endian      big-endian

MAGIC = b"XM"
VERSION = 1

# struct format: magic(2s) version(B) msg_type(B) session_id(Q) payload_len(I)
HEADER_FORMAT = ">2sBBQI"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # = 16

# Hard ceiling on a single frame payload (defense-in-depth). payload_len is a
# u32 (up to 4 GiB); without a bound a malformed/hostile header could make the
# reader allocate/wait for an enormous read. 64 MiB is far above any legitimate
# command or chunk (per-stream chunks are additionally capped by max_chunk_size).
# Trần cứng cho payload một frame: u32 tới 4 GiB, không chặn thì header độc hại
# bắt reader chờ/cấp phát khổng lồ. 64 MiB vượt xa mọi command/chunk hợp lệ.
MAX_PAYLOAD_SIZE = 64 * 1024 * 1024


class MessageType(enum.IntEnum):
    """Frame types exchanged between client and server.

    Payload interpretation depends on the type:
      COMMAND_REQUEST / STREAM_START : MessagePack envelope {endpoint, data}
      COMMAND_RESPONSE / STREAM_RESPONSE : MessagePack of response.model_dump()
      STREAM_CHUNK   : raw bytes (no msgpack — avoids copy/overhead)
      ERROR          : MessagePack {code, message}
      STREAM_END / CANCEL : empty payload
    """

    COMMAND_REQUEST = 1    # client → server: invoke a command
    COMMAND_RESPONSE = 2   # server → client: command result
    STREAM_START = 3       # client → server: open a stream (metadata = envelope)
    STREAM_CHUNK = 4       # either direction: one data chunk (raw bytes)
    STREAM_END = 5         # sender signals no more chunks
    STREAM_RESPONSE = 6    # server → client: final response after upload
    ERROR = 7              # error report {code, message}
    CANCEL = 8             # cancel a session


@dataclass
class Frame:
    """A decoded wire frame."""

    msg_type: int
    session_id: int
    payload: bytes


def encode_frame(msg_type: int, session_id: int, payload: bytes = b"") -> bytes:
    """Serialize a frame to bytes ready to write on the socket."""
    return (
        struct.pack(HEADER_FORMAT, MAGIC, VERSION, msg_type, session_id, len(payload))
        + payload
    )


async def read_frame(reader: asyncio.StreamReader) -> Frame:
    """Read exactly one frame from the stream.

    Raises asyncio.IncompleteReadError when the peer closes the connection
    (EOF mid-header) — callers treat that as "connection closed".
    Ném IncompleteReadError khi peer đóng connection — coi như đóng kết nối.

    Raises ProtocolError on a malformed header (bad magic / version).
    """
    header = await reader.readexactly(HEADER_SIZE)
    magic, version, msg_type, session_id, length = struct.unpack(HEADER_FORMAT, header)

    if magic != MAGIC:
        raise ProtocolError(f"bad frame magic: {magic!r} (expected {MAGIC!r})")
    if version != VERSION:
        raise ProtocolError(f"unsupported protocol version: {version} (expected {VERSION})")
    if length > MAX_PAYLOAD_SIZE:
        raise ProtocolError(
            f"frame payload too large: {length} bytes (max {MAX_PAYLOAD_SIZE})"
        )

    payload = await reader.readexactly(length) if length else b""
    return Frame(msg_type=msg_type, session_id=session_id, payload=payload)
