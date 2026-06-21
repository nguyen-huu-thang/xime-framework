from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from xime.core.contract import DownloadStream as BaseDownloadStream
from xime.core.contract import UploadStream as BaseUploadStream
from xime.core.exception.framework import SessionTimeout

from ._protocol import MessageType, encode_frame


# ---------------------------------------------------------------------------
# Queue sentinels
# ---------------------------------------------------------------------------
#
# Pushed into a session's chunk queue to signal end-of-stream or to inject an
# error so the awaiting handler unwinds instead of hanging forever.
# Đẩy vào queue của session để báo hết stream hoặc tiêm lỗi cho handler thoát.

class _EndSentinel:
    """Singleton marker: no more chunks for this session."""


_END = _EndSentinel()


class _ErrorSignal:
    """Wraps an exception so UploadStream re-raises it to the handler."""

    def __init__(self, exc: BaseException) -> None:
        self.exc = exc


# ---------------------------------------------------------------------------
# ConnectionWriter
# ---------------------------------------------------------------------------

class ConnectionWriter:
    """Serializes frame writes on a single connection.

    Multiple concurrent sessions share one underlying StreamWriter, so writes
    must be serialized — otherwise frames from different sessions could interleave.
    Nhiều session dùng chung một writer → phải tuần tự hoá để frame không chèn lẫn.

    drain() inside send() gives natural backpressure to whoever is writing
    (e.g. a DownloadStream producing faster than the peer consumes).
    drain() cho backpressure tự nhiên cho bên đang ghi.
    """

    def __init__(self, writer: asyncio.StreamWriter) -> None:
        self._writer = writer
        self._lock = asyncio.Lock()

    async def send(self, msg_type: int, session_id: int, payload: bytes = b"") -> None:
        frame = encode_frame(msg_type, session_id, payload)
        async with self._lock:
            self._writer.write(frame)
            await self._writer.drain()

    def close(self) -> None:
        try:
            self._writer.close()
        except Exception:
            # Closing an already-broken transport must never mask the real error.
            # Đóng transport đã hỏng không được che lỗi thật.
            pass


# ---------------------------------------------------------------------------
# Streams seen by developer
# ---------------------------------------------------------------------------

class UploadStream(BaseUploadStream):
    """Socket implementation of the shared UploadStream (client → server).

    Backed by the session's asyncio.Queue, which the connection read loop fills.
    Được cấp dữ liệu bởi queue của session, do read loop của connection bơm vào.
    """

    def __init__(self, queue: "asyncio.Queue") -> None:
        self._queue = queue

    def __aiter__(self) -> "UploadStream":
        return self

    async def __anext__(self) -> bytes:
        item = await self._queue.get()
        if item is _END:
            raise StopAsyncIteration
        if isinstance(item, _ErrorSignal):
            raise item.exc
        return item

    async def read(self) -> bytes | None:
        """Return the next chunk, or None when the stream is exhausted."""
        item = await self._queue.get()
        if item is _END:
            return None
        if isinstance(item, _ErrorSignal):
            raise item.exc
        return item


class DownloadStream(BaseDownloadStream):
    """Socket implementation of the shared DownloadStream (server → client).

    Each write is sent as one STREAM_CHUNK frame; the adapter sends STREAM_END
    automatically when the handler returns.
    Mỗi write gửi một STREAM_CHUNK; adapter tự gửi STREAM_END khi handler kết thúc.
    """

    def __init__(
        self,
        conn: ConnectionWriter,
        session_id: int,
        session: "Session | None" = None,
    ) -> None:
        self._conn = conn
        self._session_id = session_id
        # Download streams receive no inbound frames, so without this the idle
        # reaper (which only refreshes last_active on inbound traffic) would
        # cancel a healthy long download once it exceeds session_timeout. Each
        # write keeps the session alive.
        # Download không có frame inbound nên reaper (chỉ làm tươi last_active khi
        # có traffic vào) sẽ huỷ nhầm download dài. Mỗi write giữ session sống.
        self._session = session

    async def write(self, chunk: bytes) -> None:
        if self._session is not None:
            self._session.last_active = time.monotonic()
        await self._conn.send(MessageType.STREAM_CHUNK, self._session_id, chunk)


# ---------------------------------------------------------------------------
# Session & SessionManager
# ---------------------------------------------------------------------------

@dataclass
class Session:
    """A single in-flight stream on a connection."""

    session_id: int
    queue: "asyncio.Queue"
    task: asyncio.Task | None = None
    last_active: float = field(default_factory=time.monotonic)


class SessionManager:
    """Manages live sessions on ONE connection.

    The connection's read loop demultiplexes incoming frames by session_id into
    each session's queue; handler coroutines await that queue. This is the core
    multiplexing mechanism — analogous to HTTP/2 stream_id, but far simpler
    because everything is same-machine and trusted.
    Read loop demux frame theo session_id vào queue từng session — cơ chế multiplex
    cốt lõi, giống stream_id của HTTP/2 nhưng đơn giản hơn nhiều (cùng máy, tin cậy).
    """

    def __init__(self, timeout: float, queue_size: int) -> None:
        self._sessions: dict[int, Session] = {}
        self._timeout = timeout
        self._queue_size = queue_size

    def create(self, session_id: int) -> Session:
        session = Session(session_id, asyncio.Queue(maxsize=self._queue_size))
        self._sessions[session_id] = session
        return session

    def get(self, session_id: int) -> Session | None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.last_active = time.monotonic()
        return session

    def destroy(self, session_id: int) -> None:
        session = self._sessions.pop(session_id, None)
        if session and session.task and not session.task.done():
            session.task.cancel()

    def destroy_all(self) -> None:
        for session_id in list(self._sessions):
            self.destroy(session_id)

    def reap_expired(self) -> None:
        """Cancel sessions idle longer than the timeout.

        Pushes an error signal first so a handler blocked on upload.read()
        unwinds cleanly, then cancels the task and frees the slot.
        Đẩy tín hiệu lỗi trước để handler thoát sạch, rồi huỷ task và giải phóng.
        """
        now = time.monotonic()
        for session_id, session in list(self._sessions.items()):
            if now - session.last_active > self._timeout:
                try:
                    session.queue.put_nowait(_ErrorSignal(SessionTimeout(session_id)))
                except asyncio.QueueFull:
                    pass  # handler is busy; cancellation below still frees it
                self.destroy(session_id)
