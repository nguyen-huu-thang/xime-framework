"""Test Socket Adapter.

Chia làm hai nhóm:

1. Logic thuần (chạy mọi nền tảng):
   - Protocol: encode/read frame round-trip, ProtocolError khi magic sai
   - Session: UploadStream qua queue, SessionManager reap timeout
   - Builder: phân giải command/upload/download, lọc server_id, validation fail-fast
   - Config: SocketServerConfig.resolve (path auto, permission parse)

2. End-to-end (chỉ Linux + msgpack):
   - command round-trip
   - upload stream nhiều chunk → response
   - download stream → nhiều chunk
   - multiplex 2 session đồng thời trên 1 connection
   - error mapping
   Tự skip khi thiếu asyncio.start_unix_server (Windows) hoặc msgpack.
"""
from __future__ import annotations

import asyncio
import importlib.util

import pytest
from pydantic import BaseModel

from xime.adapters.socket import (
    DownloadStream,
    UploadStream,
    command,
    stream,
)
# Concrete socket implementations (the public UploadStream/DownloadStream are the
# shared abstract bases). Tests of the queue-backed behaviour use the concrete one.
from xime.adapters.socket._session import UploadStream as QueueUploadStream
from xime.adapters.socket._config import SocketServerConfig
from xime.adapters.socket._protocol import (
    HEADER_SIZE,
    MessageType,
    encode_frame,
    read_frame,
)
from xime.adapters.socket._session import (
    SessionManager,
    _END,
)
from xime.adapters.socket.routing._builder import SocketEndpointBuilder
from xime.core.config.runtime import RuntimeConfig
from xime.core.exception import ProtocolError, SessionTimeout, StartupException

HAS_UNIX = hasattr(asyncio, "start_unix_server")
HAS_MSGPACK = importlib.util.find_spec("msgpack") is not None
e2e = pytest.mark.skipif(
    not (HAS_UNIX and HAS_MSGPACK),
    reason="end-to-end socket test requires Linux Unix sockets + msgpack",
)


# ---------------------------------------------------------------------------
# DTOs & controller dùng chung
# ---------------------------------------------------------------------------

class HashRequest(BaseModel):
    file_id: str


class HashResponse(BaseModel):
    digest: str


class EncryptRequest(BaseModel):
    name: str


class EncryptResponse(BaseModel):
    total: int


class DownloadRequest(BaseModel):
    parts: int


class FakeApp:
    """Application giả — chỉ cần get(cls) trả instance."""

    def __init__(self, instances: dict | None = None) -> None:
        self._instances = instances or {}

    def get(self, cls):
        return self._instances.get(cls, cls())


# ===========================================================================
# 1. Protocol
# ===========================================================================

@pytest.mark.asyncio
async def test_frame_round_trip():
    payload = b"x" * 5000
    raw = encode_frame(MessageType.STREAM_CHUNK, 999, payload)
    reader = asyncio.StreamReader()
    reader.feed_data(raw)
    reader.feed_eof()

    frame = await read_frame(reader)
    assert frame.msg_type == MessageType.STREAM_CHUNK
    assert frame.session_id == 999
    assert frame.payload == payload


@pytest.mark.asyncio
async def test_frame_empty_payload():
    reader = asyncio.StreamReader()
    reader.feed_data(encode_frame(MessageType.STREAM_END, 42))
    reader.feed_eof()

    frame = await read_frame(reader)
    assert frame.payload == b""
    assert frame.session_id == 42


@pytest.mark.asyncio
async def test_frame_bad_magic_raises():
    reader = asyncio.StreamReader()
    reader.feed_data(b"ZZ" + bytes(HEADER_SIZE - 2))
    reader.feed_eof()

    with pytest.raises(ProtocolError):
        await read_frame(reader)


@pytest.mark.asyncio
async def test_read_frame_eof_raises_incomplete():
    reader = asyncio.StreamReader()
    reader.feed_eof()
    with pytest.raises(asyncio.IncompleteReadError):
        await read_frame(reader)


# ===========================================================================
# 2. Session / streams
# ===========================================================================

@pytest.mark.asyncio
async def test_upload_stream_iterates_until_end():
    sm = SessionManager(timeout=30.0, queue_size=8)
    session = sm.create(1)
    up = QueueUploadStream(session.queue)

    await session.queue.put(b"a")
    await session.queue.put(b"b")
    await session.queue.put(_END)

    assert [c async for c in up] == [b"a", b"b"]


@pytest.mark.asyncio
async def test_upload_stream_read_returns_none_at_end():
    sm = SessionManager(timeout=30.0, queue_size=8)
    session = sm.create(1)
    up = QueueUploadStream(session.queue)
    await session.queue.put(_END)
    assert await up.read() is None


@pytest.mark.asyncio
async def test_session_reap_injects_timeout():
    sm = SessionManager(timeout=-1.0, queue_size=8)  # mọi session coi như đã quá hạn
    session = sm.create(1)
    up = QueueUploadStream(session.queue)
    sm.reap_expired()
    with pytest.raises(SessionTimeout):
        await up.read()


def test_session_destroy_cancels_task():
    sm = SessionManager(timeout=30.0, queue_size=8)
    session = sm.create(1)

    async def runner():
        sm2 = SessionManager(timeout=30.0, queue_size=8)
        s = sm2.create(5)
        s.task = asyncio.ensure_future(asyncio.sleep(100))
        sm2.destroy(5)
        await asyncio.sleep(0)
        assert s.task.cancelled()

    asyncio.run(runner())


# ===========================================================================
# 3. Builder
# ===========================================================================

class CryptoController:
    server_id = "crypto"

    def __init__(self) -> None:
        self.uploaded = b""

    @command("hash")
    async def hash(self, request: HashRequest) -> HashResponse:
        return HashResponse(digest=f"h:{request.file_id}")

    @stream("encrypt")
    async def encrypt(self, request: EncryptRequest, upload: UploadStream) -> EncryptResponse:
        total = 0
        async for chunk in upload:
            total += len(chunk)
        return EncryptResponse(total=total)

    @stream("download")
    async def download(self, request: DownloadRequest, download: DownloadStream) -> None:
        for i in range(request.parts):
            await download.write(f"part{i}".encode())


def test_builder_resolves_all_shapes():
    table = SocketEndpointBuilder(FakeApp(), "crypto").build([CryptoController])
    assert table["hash"].shape == "command"
    assert table["encrypt"].shape == "upload"
    assert table["encrypt"].stream_param == "upload"
    assert table["download"].shape == "download"
    assert table["download"].response_type is None


def test_builder_filters_by_server_id():
    assert SocketEndpointBuilder(FakeApp(), "other").build([CryptoController]) == {}


def test_builder_rejects_command_with_stream():
    class Bad:
        server_id = "crypto"

        def __init__(self) -> None: ...

        @command("x")
        async def x(self, request: HashRequest, upload: UploadStream) -> HashResponse: ...

    with pytest.raises(StartupException):
        SocketEndpointBuilder(FakeApp(), "crypto").build([Bad])


def test_builder_rejects_missing_request():
    class Bad:
        server_id = "crypto"

        def __init__(self) -> None: ...

        @command("x")
        async def x(self) -> HashResponse: ...

    with pytest.raises(StartupException):
        SocketEndpointBuilder(FakeApp(), "crypto").build([Bad])


def test_builder_rejects_duplicate_endpoint():
    class Dup:
        server_id = "crypto"

        def __init__(self) -> None: ...

        @command("same")
        async def a(self, request: HashRequest) -> HashResponse: ...

        @command("same")
        async def b(self, request: HashRequest) -> HashResponse: ...

    with pytest.raises(StartupException):
        SocketEndpointBuilder(FakeApp(), "crypto").build([Dup])


# ===========================================================================
# 4. Config
# ===========================================================================

def test_config_auto_path_from_dir():
    runtime = RuntimeConfig.from_dict({"socket": {"dir": "/run/myapp"}})
    cfg = SocketServerConfig.resolve(runtime, "crypto", None)
    assert cfg.path == "/run/myapp/crypto.sock"


def test_config_path_override_wins():
    runtime = RuntimeConfig.from_dict({"socket": {"dir": "/run/myapp"}})
    cfg = SocketServerConfig.resolve(runtime, "crypto", "/custom/x.sock")
    assert cfg.path == "/custom/x.sock"


def test_config_permission_parsed_as_octal():
    runtime = RuntimeConfig.from_dict({"socket": {"dir": "/run/x", "permission": "0640"}})
    cfg = SocketServerConfig.resolve(runtime, "s", None)
    assert cfg.permission == 0o640


def test_config_defaults_without_block():
    runtime = RuntimeConfig.from_dict({})
    cfg = SocketServerConfig.resolve(runtime, "crypto", "/x.sock")
    assert cfg.permission == 0o600
    assert cfg.session_timeout == 30.0
    assert cfg.allowed_uids == ()


# ===========================================================================
# 5. End-to-end (Linux + msgpack)
# ===========================================================================

@e2e
@pytest.mark.asyncio
async def test_e2e_command_and_streams(tmp_path):
    """Khởi động một SocketAdapter thật trên một file socket tạm, gọi qua SocketClient."""
    from xime.adapters.socket import SocketClient
    from xime.adapters.socket._adapter import SocketAdapter
    from xime.adapters.socket._config import socket_registry

    sock_path = str(tmp_path / "crypto.sock")
    controller = CryptoController()

    adapter = SocketAdapter("crypto", path=sock_path)
    adapter._config = SocketServerConfig(path=sock_path)
    adapter._table = SocketEndpointBuilder(
        FakeApp({CryptoController: controller}), "crypto"
    ).build([CryptoController])

    server = await asyncio.start_unix_server(adapter._handle_connection, path=sock_path)
    async with server:
        client = SocketClient(sock_path)
        await client.connect()
        try:
            # command
            resp = await client.command("hash", HashRequest(file_id="f1"))
            assert resp["digest"] == "h:f1"

            # upload
            async with client.upload("encrypt", EncryptRequest(name="a")) as up:
                await up.write(b"12345")
                await up.write(b"678")
                result = await up.finish()
            assert result["total"] == 8

            # download
            chunks = [c async for c in client.download("download", DownloadRequest(parts=3))]
            assert chunks == [b"part0", b"part1", b"part2"]
        finally:
            await client.close()


@e2e
@pytest.mark.asyncio
async def test_e2e_concurrent_sessions(tmp_path):
    """Hai upload đồng thời trên cùng một connection không lẫn dữ liệu."""
    from xime.adapters.socket import SocketClient
    from xime.adapters.socket._adapter import SocketAdapter

    sock_path = str(tmp_path / "crypto.sock")
    adapter = SocketAdapter("crypto", path=sock_path)
    adapter._config = SocketServerConfig(path=sock_path)
    adapter._table = SocketEndpointBuilder(FakeApp(), "crypto").build([CryptoController])

    server = await asyncio.start_unix_server(adapter._handle_connection, path=sock_path)
    async with server:
        client = SocketClient(sock_path)
        await client.connect()
        try:
            async def run_upload(payloads):
                async with client.upload("encrypt", EncryptRequest(name="x")) as up:
                    for p in payloads:
                        await up.write(p)
                    return await up.finish()

            r1, r2 = await asyncio.gather(
                run_upload([b"aaaa", b"bb"]),       # 6
                run_upload([b"c", b"dddddddd"]),    # 9
            )
            assert {r1["total"], r2["total"]} == {6, 9}
        finally:
            await client.close()
