"""End-to-end Code-First gRPC: generate → protoc → serve → call over TCP.

Proves the full path works with real protobuf wire + a generated client stub:
  - command (unary)
  - upload (client streaming via the oneof chunk-wrapper)
  - download (server streaming)

Requires grpcio + grpcio-tools + protobuf (the `xime[grpc]` extra). gRPC runs
over TCP so this works on any OS (unlike the Unix-socket adapter).
"""
from __future__ import annotations

import importlib

import pytest

pytest.importorskip("grpc")
pytest.importorskip("grpc_tools")

import grpc  # noqa: E402
import grpc.aio  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from xime.adapters.grpc.codefirst._builder import ContractBuilder  # noqa: E402
from xime.adapters.grpc.codefirst._generator import _run_protoc  # noqa: E402
from xime.adapters.grpc.codefirst._lock import LockFile  # noqa: E402
from xime.adapters.grpc.codefirst._pb2_loader import load_message_classes  # noqa: E402
from xime.adapters.grpc.codefirst._proto_emitter import ProtoEmitter  # noqa: E402
from xime.adapters.grpc.codefirst._service_builder import CodeFirstGrpcBuilder  # noqa: E402
from xime.core.contract import DownloadStream, UploadStream, command, stream  # noqa: E402


# ---------------------------------------------------------------------------
# DTOs + controller (module-level so get_type_hints resolves)
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


class E2eCryptoController:
    server_id = "e2e"

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


class FakeApp:
    def __init__(self, instances: dict) -> None:
        self._instances = instances

    def get(self, cls):
        return self._instances[cls]


@pytest.mark.asyncio
async def test_codefirst_serves_over_grpc(tmp_path):
    # 1) Build IR + emit proto.
    model = ContractBuilder("e2e", LockFile()).build([E2eCryptoController])
    files = ProtoEmitter().emit(model)

    out = tmp_path / "generated"
    for rel, text in files.items():
        path = out.joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    # 2) protoc → *_pb2 / *_pb2_grpc.
    _run_protoc(str(out), files)

    # 3) Load generated message classes + the client stub module.
    messages = load_message_classes(str(out), "e2e")          # also puts dir on sys.path
    pb2 = importlib.import_module("e2e_crypto_pb2")
    pb2_grpc = importlib.import_module("e2e_crypto_pb2_grpc")

    # 4) Start a real grpc.aio server serving the code-first controller.
    controller = E2eCryptoController()
    server = grpc.aio.server()
    CodeFirstGrpcBuilder(
        FakeApp({E2eCryptoController: controller}), model, messages
    ).register_all(server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()

    try:
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            stub = pb2_grpc.E2eCryptoControllerStub(channel)

            # command (unary)
            resp = await stub.Hash(pb2.HashRequest(file_id="f1"))
            assert resp.digest == "h:f1"

            # upload (client streaming) — first message metadata, rest chunks
            async def chunks():
                yield pb2.EncryptChunk(metadata=pb2.EncryptRequest(name="a"))
                yield pb2.EncryptChunk(chunk=b"12345")
                yield pb2.EncryptChunk(chunk=b"678")

            enc = await stub.Encrypt(chunks())
            assert enc.total == 8

            # download (server streaming)
            got = [c.chunk async for c in stub.Download(pb2.DownloadRequest(parts=3))]
            assert got == [b"part0", b"part1", b"part2"]
    finally:
        await server.stop(None)
