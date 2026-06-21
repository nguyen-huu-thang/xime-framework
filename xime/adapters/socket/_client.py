from __future__ import annotations

import asyncio
import itertools
from typing import Any

from pydantic import BaseModel

from xime.core.exception.framework import SocketCommandError

from ._protocol import MessageType, read_frame
from ._session import ConnectionWriter, _END, _ErrorSignal


class SocketClient:
    """Python-side client for a Xime Socket server.

    Native engines in C++/Rust/Go implement the same wire protocol (see
    _protocol.py); this class is the convenience client for Python ↔ Python.
    Engine C++/Rust/Go tự implement cùng protocol; class này tiện cho Python↔Python.

        client = SocketClient("/run/xime/crypto.sock")
        await client.connect()
        resp = await client.command("hash", HashRequest(file_id="f1"))

        async with client.upload("encrypt", EncryptRequest(...)) as up:
            while chunk := await file.read(65536):
                await up.write(chunk)
            result = await up.finish()

        async for chunk in client.download("download", DownloadRequest(...)):
            ...

        await client.close()
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._conn: ConnectionWriter | None = None
        self._read_task: asyncio.Task | None = None
        self._next_session = itertools.count(1)
        # session_id → Future resolving to a response dict (command / upload finish)
        self._pending: dict[int, asyncio.Future] = {}
        # session_id → inbound chunk queue (download streams)
        self._inbound: dict[int, asyncio.Queue] = {}

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        reader, writer = await asyncio.open_unix_connection(self._path)
        self._conn = ConnectionWriter(writer)
        self._read_task = asyncio.create_task(self._read_loop(reader))

    async def close(self) -> None:
        if self._read_task is not None:
            self._read_task.cancel()
            self._read_task = None
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    async def __aenter__(self) -> "SocketClient":
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Calls
    # ------------------------------------------------------------------

    async def command(self, endpoint: str, request: BaseModel) -> dict:
        """Invoke a command endpoint and return the response dict."""
        import msgpack

        sid = next(self._next_session)
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[sid] = fut
        payload = msgpack.packb({"endpoint": endpoint, "data": request.model_dump()})
        await self._send(MessageType.COMMAND_REQUEST, sid, payload)
        return await fut

    def upload(self, endpoint: str, request: BaseModel) -> "ClientUpload":
        """Open an upload stream as an async context manager."""
        sid = next(self._next_session)
        return ClientUpload(self, sid, endpoint, request)

    async def download(self, endpoint: str, request: BaseModel):
        """Open a download stream and async-iterate its chunks.

        Yields raw bytes until the server signals end-of-stream.
        Trả về raw bytes cho tới khi server báo hết stream.
        """
        import msgpack

        sid = next(self._next_session)
        queue: asyncio.Queue = asyncio.Queue()
        self._inbound[sid] = queue
        payload = msgpack.packb({"endpoint": endpoint, "data": request.model_dump()})
        await self._send(MessageType.STREAM_START, sid, payload)
        try:
            while True:
                item = await queue.get()
                if item is _END:
                    return
                if isinstance(item, _ErrorSignal):
                    raise item.exc
                yield item
        finally:
            self._inbound.pop(sid, None)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _send(self, msg_type: int, session_id: int, payload: bytes = b"") -> None:
        if self._conn is None:
            raise RuntimeError("SocketClient is not connected. Call connect() first.")
        await self._conn.send(msg_type, session_id, payload)

    async def _read_loop(self, reader: asyncio.StreamReader) -> None:
        import msgpack

        try:
            while True:
                try:
                    frame = await read_frame(reader)
                except (asyncio.IncompleteReadError, ConnectionResetError):
                    break

                mt = frame.msg_type
                sid = frame.session_id

                if mt in (MessageType.COMMAND_RESPONSE, MessageType.STREAM_RESPONSE):
                    fut = self._pending.pop(sid, None)
                    if fut is not None and not fut.done():
                        fut.set_result(msgpack.unpackb(frame.payload, raw=False))

                elif mt == MessageType.STREAM_CHUNK:
                    queue = self._inbound.get(sid)
                    if queue is not None:
                        await queue.put(frame.payload)

                elif mt == MessageType.STREAM_END:
                    queue = self._inbound.get(sid)
                    if queue is not None:
                        await queue.put(_END)

                elif mt == MessageType.ERROR:
                    err = msgpack.unpackb(frame.payload, raw=False)
                    exc = SocketCommandError(err.get("code", "INTERNAL"), err.get("message", ""))
                    self._fail(sid, exc)
        finally:
            # Connection dropped — fail anything still waiting.
            # Connection rớt — báo lỗi mọi thứ còn đang chờ.
            self._fail_all()

    def _fail(self, session_id: int, exc: Exception) -> None:
        fut = self._pending.pop(session_id, None)
        if fut is not None and not fut.done():
            fut.set_exception(exc)
            return
        queue = self._inbound.get(session_id)
        if queue is not None:
            queue.put_nowait(_ErrorSignal(exc))

    def _fail_all(self) -> None:
        exc = ConnectionError("socket connection closed")
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()
        for queue in self._inbound.values():
            queue.put_nowait(_ErrorSignal(exc))


class ClientUpload:
    """Async context manager for a client → server upload stream.

        async with client.upload("encrypt", req) as up:
            await up.write(chunk)
            result = await up.finish()
    """

    def __init__(self, client: SocketClient, session_id: int, endpoint: str, request: BaseModel) -> None:
        self._client = client
        self._sid = session_id
        self._endpoint = endpoint
        self._request = request
        self._fut: asyncio.Future | None = None

    async def __aenter__(self) -> "ClientUpload":
        import msgpack

        self._fut = asyncio.get_running_loop().create_future()
        self._client._pending[self._sid] = self._fut
        payload = msgpack.packb({"endpoint": self._endpoint, "data": self._request.model_dump()})
        await self._client._send(MessageType.STREAM_START, self._sid, payload)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        # If the body raised before finish(), cancel the server-side session.
        # Nếu thân lỗi trước finish(), huỷ session phía server.
        if exc_type is not None:
            await self._client._send(MessageType.CANCEL, self._sid)
            self._client._pending.pop(self._sid, None)

    async def write(self, chunk: bytes) -> None:
        await self._client._send(MessageType.STREAM_CHUNK, self._sid, chunk)

    async def finish(self) -> dict:
        """Signal end-of-stream and await the server's final response."""
        await self._client._send(MessageType.STREAM_END, self._sid)
        assert self._fut is not None
        return await self._fut
