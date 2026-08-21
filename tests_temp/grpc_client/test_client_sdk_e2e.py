"""End-to-end client SDK: generate proto+sidecar → protoc → sinh SDK → gọi server thật.

Chứng minh trọn vòng "code-first hai chiều":
  Controller Python (server)  →  .proto + contract.json
                              →  xime grpc client  →  SDK package
  SDK import được, client class gọi unary / upload / download qua TCP thật,
  DTO Pydantic lật gương 1:1 (kể cả Decimal/UUID fidelity).

Requires grpcio + grpcio-tools + protobuf.
"""
from __future__ import annotations

import importlib
import sys
import uuid
from decimal import Decimal

import pytest

pytest.importorskip("grpc")
pytest.importorskip("grpc_tools")

import grpc.aio  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from xime.adapters.grpc.client import generate_client_sdk  # noqa: E402
from xime.adapters.grpc.codefirst._builder import ContractBuilder  # noqa: E402
from xime.adapters.grpc.codefirst._generator import _run_protoc  # noqa: E402
from xime.adapters.grpc.codefirst._lock import LockFile  # noqa: E402
from xime.adapters.grpc.codefirst._pb2_loader import load_message_classes  # noqa: E402
from xime.adapters.grpc.codefirst._proto_emitter import ProtoEmitter  # noqa: E402
from xime.adapters.grpc.codefirst._service_builder import CodeFirstGrpcBuilder  # noqa: E402
from xime.adapters.grpc.codefirst._sidecar import emit_sidecar  # noqa: E402
from xime.core.contract import DownloadStream, UploadStream, command, stream  # noqa: E402


# ---------------------------------------------------------------------------
# DTOs + controller phía server (module-level để get_type_hints resolve)
# ---------------------------------------------------------------------------

class PriceQuery(BaseModel):
    order_id: uuid.UUID


class PriceReply(BaseModel):
    amount: Decimal
    note: str


class PushMeta(BaseModel):
    name: str


class PushDone(BaseModel):
    total: int


class PullQuery(BaseModel):
    parts: int


class SdkBillingController:
    server_id = "sdke2e"

    @command("get_price")
    async def get_price(self, request: PriceQuery) -> PriceReply:
        # Echo lại để kiểm chứng fidelity hai chiều
        return PriceReply(amount=Decimal("19.99"), note=str(request.order_id))

    @stream("push_doc")
    async def push_doc(self, request: PushMeta, upload: UploadStream) -> PushDone:
        total = 0
        async for chunk in upload:
            total += len(chunk)
        return PushDone(total=total)

    @stream("pull_doc")
    async def pull_doc(self, request: PullQuery, download: DownloadStream) -> None:
        for i in range(request.parts):
            await download.write(f"part{i}".encode())


class FakeApp:
    def __init__(self, instances: dict) -> None:
        self._instances = instances

    def get(self, cls):
        return self._instances[cls]


@pytest.mark.asyncio
async def test_generated_sdk_calls_codefirst_server(tmp_path):
    # 1) Server side: IR → proto + sidecar → protoc.
    model = ContractBuilder("sdke2e", LockFile()).build([SdkBillingController])
    files = ProtoEmitter().emit(model)
    files["sdke2e/contract.json"] = emit_sidecar(model)

    out = tmp_path / "generated"
    for rel, text in files.items():
        path = out.joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _run_protoc(str(out), files)

    # 2) Sinh client SDK từ thư mục proto của server.
    sdk_dir = tmp_path / "clients" / "billing_sdk"
    result = generate_client_sdk(str(out / "sdke2e"), str(sdk_dir))
    assert not result.skipped_methods  # có sidecar → không method nào bị bỏ

    # 3) Import SDK như một package thật.
    sys.path.insert(0, str(tmp_path / "clients"))
    try:
        sdk = importlib.import_module("billing_sdk")

        # DTO lật gương đúng kiểu Python gốc
        assert sdk.PriceQuery.model_fields["order_id"].annotation is uuid.UUID

        # 4) Server code-first thật.
        messages = load_message_classes(str(out), "sdke2e")
        controller = SdkBillingController()
        server = grpc.aio.server()
        CodeFirstGrpcBuilder(
            FakeApp({SdkBillingController: controller}), model, messages
        ).register_all(server)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()

        try:
            async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
                client = sdk.SdkBillingClient(channel)

                # unary - Decimal/UUID fidelity hai chiều
                order_id = uuid.uuid4()
                reply = await client.get_price(sdk.PriceQuery(order_id=order_id))
                assert isinstance(reply.amount, Decimal)
                assert reply.amount == Decimal("19.99")
                assert reply.note == str(order_id)

                # upload (client streaming)
                async def chunks():
                    yield b"12345"
                    yield b"678"

                done = await client.push_doc(sdk.PushMeta(name="doc"), chunks())
                assert done.total == 8

                # download (server streaming)
                got = [c async for c in client.pull_doc(sdk.PullQuery(parts=3))]
                assert got == [b"part0", b"part1", b"part2"]
        finally:
            await server.stop(None)
    finally:
        sys.path.remove(str(tmp_path / "clients"))
        sys.modules.pop("billing_sdk", None)
        sys.modules.pop("billing_sdk._clients", None)
        sys.modules.pop("billing_sdk._models", None)
