from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from xime.core.context import request_context
from xime.core.exception.framework import EndpointNotFound
from xime.core.security import clear_security

from ._config import SocketServerConfig, socket_registry
from ._peercred import authorize_peer, secure_socket_file
from ._protocol import Frame, MessageType, read_frame
from ._session import (
    ConnectionWriter,
    DownloadStream,
    SessionManager,
    UploadStream,
    _END,
)
from .routing._builder import ResolvedEndpoint, SocketEndpointBuilder

if TYPE_CHECKING:
    from xime.core.bootstrap.application import Application

# How often the reaper scans for idle sessions (seconds).
# Tần suất reaper quét session idle (giây).
_REAP_INTERVAL = 5.0


class SocketAdapter:
    """Unix Domain Socket adapter — Local IPC for native engines.

    Register via app.use() and start via app.run():

        app = Application()
        app.use(SocketAdapter("crypto"))
        app.run()

    Hỗ trợ nhiều socket server, mỗi server một server_id và một file socket:

        app.use(SocketAdapter("crypto"))      # /run/xime/crypto.sock
        app.use(SocketAdapter("thumbnail"))   # /run/xime/thumbnail.sock

    Controller thuộc server nào khai báo qua class variable server_id (mặc định
    "default"). Path mặc định sinh từ server_id; có thể override qua constructor
    hoặc application.yml (block `socket:`).

    Bảo mật dựa trên kernel Linux: file permission (chmod/chown) + SO_PEERCRED.
    Không cần TLS/token vì đây là IPC cùng máy giữa các process tin cậy.

    Lifecycle (driven by Application._run_async):
        1. Application.start()      — DI container fully built
        2. SocketAdapter.start(app) — build endpoint table, bind socket, serve
        3. SocketAdapter.stop()     — close server, remove socket file
    """

    def __init__(self, server_id: str = "default", path: str | None = None) -> None:
        self._server_id = server_id
        self._path_override = path
        self._server: asyncio.AbstractServer | None = None
        self._reaper: asyncio.Task | None = None
        self._config: SocketServerConfig | None = None
        self._table: dict[str, ResolvedEndpoint] = {}
        self._actual_path: str | None = None
        # Live session managers (one per connection) for the reaper to scan.
        # Các session manager đang sống (mỗi connection một cái) cho reaper quét.
        self._managers: set[SessionManager] = set()
        # Strong references to fire-and-forget command tasks so the event loop
        # does not garbage-collect them mid-flight.
        # Giữ reference cho command task để event loop không thu gom giữa chừng.
        self._command_tasks: set[asyncio.Task] = set()

    # ------------------------------------------------------------------
    # Adapter protocol
    # ------------------------------------------------------------------

    async def start(self, app: "Application") -> None:
        """Build the endpoint table, bind the socket, and serve until stopped."""
        try:
            import msgpack  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "SocketAdapter requires msgpack. Run: pip install 'xime[socket]'"
            ) from None

        from xime.core.config.runtime import RuntimeConfig
        runtime: RuntimeConfig = app.get(RuntimeConfig)  # type: ignore[assignment]

        self._config = SocketServerConfig.resolve(
            runtime, self._server_id, self._path_override
        )
        self._actual_path = self._config.path

        # 1) Create the directory holding the socket (idempotent).
        Path(self._actual_path).parent.mkdir(parents=True, exist_ok=True)

        # 2) Remove a stale socket left by a previous crash before binding.
        if os.path.exists(self._actual_path):
            os.remove(self._actual_path)

        # 3) Build the endpoint dispatch table (DI is ready).
        from xime.core.contract import ControllerScanner
        scanner = ControllerScanner()
        controllers = scanner.find_controllers(*socket_registry.get_packages())
        self._table = SocketEndpointBuilder(app, self._server_id).build(controllers)

        # 4) Bind the Unix server, tighten file permissions, run the reaper.
        self._server = await asyncio.start_unix_server(
            self._handle_connection, path=self._actual_path
        )
        secure_socket_file(
            self._actual_path,
            self._config.permission,
            self._config.owner,
            self._config.group,
        )
        self._reaper = asyncio.create_task(self._reap_loop())

        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        """Stop serving and remove the socket file. Idempotent."""
        if self._reaper is not None:
            self._reaper.cancel()
            self._reaper = None
        if self._server is not None:
            self._server.close()
            try:
                await self._server.wait_closed()
            except Exception:
                pass
            self._server = None
        for task in list(self._command_tasks):
            task.cancel()
        self._command_tasks.clear()
        if self._actual_path and os.path.exists(self._actual_path):
            try:
                os.remove(self._actual_path)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        conn = ConnectionWriter(writer)

        # Reject the connection immediately if the peer UID is not allowed.
        # Từ chối ngay nếu UID của peer không được phép.
        if not authorize_peer(writer, self._config.allowed_uids):  # type: ignore[union-attr]
            conn.close()
            return

        sessions = SessionManager(
            self._config.session_timeout,    # type: ignore[union-attr]
            self._config.recv_queue_size,    # type: ignore[union-attr]
        )
        self._managers.add(sessions)
        try:
            while True:
                try:
                    frame = await read_frame(reader)
                except (asyncio.IncompleteReadError, ConnectionResetError):
                    break  # peer closed the connection
                await self._dispatch(frame, conn, sessions)
        finally:
            sessions.destroy_all()
            self._managers.discard(sessions)
            conn.close()

    async def _dispatch(
        self, frame: Frame, conn: ConnectionWriter, sessions: SessionManager
    ) -> None:
        mt = frame.msg_type

        if mt == MessageType.COMMAND_REQUEST:
            # Commands are independent — run in their own task. Keep a strong
            # reference until done so the loop does not collect it mid-flight.
            # Command độc lập — chạy task riêng; giữ reference tới khi xong.
            task = asyncio.create_task(self._run_command(frame, conn))
            self._command_tasks.add(task)
            task.add_done_callback(self._command_tasks.discard)

        elif mt == MessageType.STREAM_START:
            await self._start_stream(frame, conn, sessions)

        elif mt == MessageType.STREAM_CHUNK:
            session = sessions.get(frame.session_id)
            if session is None:
                return
            if len(frame.payload) > self._config.max_chunk_size:  # type: ignore[union-attr]
                await self._send_error(conn, frame.session_id, "TOO_LARGE", "chunk too large")
                sessions.destroy(frame.session_id)
                return
            # NOTE: bounded queue → if full, this await blocks the read loop,
            # applying connection-wide backpressure (see design doc §9.7).
            # Queue có giới hạn → đầy thì chặn read loop (backpressure toàn connection).
            await session.queue.put(frame.payload)

        elif mt == MessageType.STREAM_END:
            session = sessions.get(frame.session_id)
            if session is not None:
                await session.queue.put(_END)

        elif mt == MessageType.CANCEL:
            sessions.destroy(frame.session_id)

    async def _start_stream(
        self, frame: Frame, conn: ConnectionWriter, sessions: SessionManager
    ) -> None:
        import msgpack

        envelope = msgpack.unpackb(frame.payload, raw=False)
        endpoint = self._table.get(envelope.get("endpoint"))
        if endpoint is None:
            await self._send_error(
                conn, frame.session_id, "NOT_FOUND",
                f"endpoint '{envelope.get('endpoint')}' not found",
            )
            return

        session = sessions.create(frame.session_id)
        data = envelope.get("data", {})

        if endpoint.shape == "upload":
            upload = UploadStream(session.queue)
            session.task = asyncio.create_task(
                self._run_upload(endpoint, data, upload, frame.session_id, conn, sessions)
            )
        elif endpoint.shape == "download":
            download = DownloadStream(conn, frame.session_id)
            session.task = asyncio.create_task(
                self._run_download(endpoint, data, download, frame.session_id, conn, sessions)
            )
        else:
            # A command was invoked via STREAM_START — protocol misuse.
            # Command bị gọi qua STREAM_START — dùng sai protocol.
            sessions.destroy(frame.session_id)
            await self._send_error(
                conn, frame.session_id, "INVALID_ARGUMENT",
                f"endpoint '{endpoint.info.name}' is a command, not a stream",
            )

    # ------------------------------------------------------------------
    # Handler runners
    # ------------------------------------------------------------------

    async def _run_command(self, frame: Frame, conn: ConnectionWriter) -> None:
        import msgpack

        request_context.set("request_id", str(uuid.uuid4()))
        try:
            envelope = msgpack.unpackb(frame.payload, raw=False)
            endpoint = self._table.get(envelope.get("endpoint"))
            if endpoint is None:
                raise EndpointNotFound(envelope.get("endpoint"))
            request = endpoint.request_type(**envelope.get("data", {}))
            response = await endpoint.bound(request=request)
            payload = msgpack.packb(response.model_dump())
            await conn.send(MessageType.COMMAND_RESPONSE, frame.session_id, payload)
        except Exception as exc:
            await self._send_error(conn, frame.session_id, *self._map_error(exc))
        finally:
            request_context.clear()
            clear_security()

    async def _run_upload(
        self,
        endpoint: ResolvedEndpoint,
        data: dict,
        upload: UploadStream,
        session_id: int,
        conn: ConnectionWriter,
        sessions: SessionManager,
    ) -> None:
        import msgpack

        request_context.set("request_id", str(uuid.uuid4()))
        try:
            request = endpoint.request_type(**data)
            kwargs = {"request": request, endpoint.stream_param: upload}
            response = await endpoint.bound(**kwargs)
            await conn.send(
                MessageType.STREAM_RESPONSE, session_id, msgpack.packb(response.model_dump())
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._send_error(conn, session_id, *self._map_error(exc))
        finally:
            request_context.clear()
            clear_security()
            sessions.destroy(session_id)

    async def _run_download(
        self,
        endpoint: ResolvedEndpoint,
        data: dict,
        download: DownloadStream,
        session_id: int,
        conn: ConnectionWriter,
        sessions: SessionManager,
    ) -> None:
        request_context.set("request_id", str(uuid.uuid4()))
        try:
            request = endpoint.request_type(**data)
            kwargs = {"request": request, endpoint.stream_param: download}
            await endpoint.bound(**kwargs)
            # Signal the client there are no more chunks.
            # Báo client đã hết chunk.
            await conn.send(MessageType.STREAM_END, session_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._send_error(conn, session_id, *self._map_error(exc))
        finally:
            request_context.clear()
            clear_security()
            sessions.destroy(session_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _send_error(
        self, conn: ConnectionWriter, session_id: int, code: str, message: str
    ) -> None:
        import msgpack

        try:
            payload = msgpack.packb({"code": code, "message": message})
            await conn.send(MessageType.ERROR, session_id, payload)
        except (ConnectionResetError, BrokenPipeError):
            pass  # peer already gone — nothing to report to

    def _map_error(self, exc: Exception) -> tuple[str, str]:
        """Resolve an exception to (code, message) using the configured mappings."""
        mappings = socket_registry.get_error_mappings()
        for exc_type, code in mappings.items():
            if isinstance(exc, exc_type):
                return code, str(exc)
        return "INTERNAL", str(exc)

    async def _reap_loop(self) -> None:
        """Periodically reap idle sessions across all live connections."""
        try:
            while True:
                await asyncio.sleep(_REAP_INTERVAL)
                for manager in list(self._managers):
                    manager.reap_expired()
        except asyncio.CancelledError:
            pass
