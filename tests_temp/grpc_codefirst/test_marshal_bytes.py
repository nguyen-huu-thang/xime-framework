"""Test marshal field `bytes` (fix bug backlog #3): binary thật đi hai chiều.

Trước fix: model_dump(mode="json") utf-8 hóa bytes (crash/sai với binary),
MessageToDict trả base64 string mà Pydantic lại utf-8 encode → dữ liệu hỏng.
Sau fix: chiều đi base64 qua _sanitize, chiều về decode theo descriptor.

  - unit: _sanitize giữ nguyên scalar, base64 bytes, đệ quy list/dict/enum
  - e2e: controller echo blob binary (kể cả byte không phải utf-8),
    list[bytes], dict[str, bytes], nested message chứa bytes
"""
from __future__ import annotations

import base64
import datetime
import enum
import uuid
from decimal import Decimal

import pytest

pytest.importorskip("grpc")
pytest.importorskip("grpc_tools")

import grpc.aio  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from xime.adapters.grpc.codefirst._builder import ContractBuilder  # noqa: E402
from xime.adapters.grpc.codefirst._generator import _run_protoc  # noqa: E402
from xime.adapters.grpc.codefirst._lock import LockFile  # noqa: E402
from xime.adapters.grpc.codefirst._marshal import _sanitize  # noqa: E402
from xime.adapters.grpc.codefirst._pb2_loader import load_message_classes  # noqa: E402
from xime.adapters.grpc.codefirst._proto_emitter import ProtoEmitter  # noqa: E402
from xime.adapters.grpc.codefirst._service_builder import CodeFirstGrpcBuilder  # noqa: E402
from xime.core.contract import command  # noqa: E402

BINARY = b"\x00\xff\xfe\x01PNG\x89"   # cố tình không phải utf-8 hợp lệ


# ---------------------------------------------------------------------------
# Unit - _sanitize
# ---------------------------------------------------------------------------

class Color(enum.IntEnum):
    RED = 1


class TestSanitize:
    def test_bytes_become_base64(self):
        assert _sanitize(BINARY) == base64.b64encode(BINARY).decode("ascii")

    def test_scalars_unchanged(self):
        assert _sanitize("text") == "text"
        assert _sanitize(42) == 42
        assert _sanitize(1.5) == 1.5
        assert _sanitize(True) is True
        assert _sanitize(None) is None

    def test_json_like_types_match_pydantic_json_mode(self):
        assert _sanitize(Decimal("9.99")) == "9.99"
        uid = uuid.uuid4()
        assert _sanitize(uid) == str(uid)
        # Aware datetime keeps its offset; naive is assumed UTC so the proto
        # Timestamp parser always receives a valid RFC3339 string.
        aware = datetime.datetime(2026, 6, 13, 8, 30, tzinfo=datetime.timezone.utc)
        assert _sanitize(aware) == aware.isoformat()
        naive = datetime.datetime(2026, 6, 13, 8, 30)
        assert _sanitize(naive) == naive.replace(tzinfo=datetime.timezone.utc).isoformat()
        assert _sanitize(datetime.date(2026, 6, 13)) == "2026-06-13"
        assert _sanitize(Color.RED) == 1

    def test_recurses_into_containers(self):
        data = {"items": [BINARY, "x"], "map": {"k": BINARY}}
        out = _sanitize(data)
        encoded = base64.b64encode(BINARY).decode("ascii")
        assert out == {"items": [encoded, "x"], "map": {"k": encoded}}


# ---------------------------------------------------------------------------
# E2E - binary roundtrip qua wire thật
# ---------------------------------------------------------------------------

class Attachment(BaseModel):
    name: str
    payload: bytes


class BlobRequest(BaseModel):
    blob: bytes
    parts: list[bytes]
    by_key: dict[str, bytes]
    nested: Attachment


class BlobReply(BaseModel):
    blob: bytes
    total_len: int
    nested_payload: bytes


class BytesEchoController:
    server_id = "bytese2e"

    @command("echo_blob")
    async def echo_blob(self, request: BlobRequest) -> BlobReply:
        # Server phải nhận được bytes THẬT (không phải base64 utf-8 hóa)
        assert isinstance(request.blob, bytes)
        assert request.blob == BINARY
        assert request.parts == [b"a1", BINARY]
        assert request.by_key == {"k": BINARY}
        assert request.nested.payload == BINARY
        return BlobReply(
            blob=request.blob,
            total_len=sum(len(p) for p in request.parts),
            nested_payload=request.nested.payload,
        )


class FakeApp:
    def __init__(self, instances: dict) -> None:
        self._instances = instances

    def get(self, cls):
        return self._instances[cls]


@pytest.mark.asyncio
async def test_binary_bytes_roundtrip_over_wire(tmp_path):
    model = ContractBuilder("bytese2e", LockFile()).build([BytesEchoController])
    files = ProtoEmitter().emit(model)
    out = tmp_path / "generated"
    for rel, text in files.items():
        path = out.joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _run_protoc(str(out), files)

    messages = load_message_classes(str(out), "bytese2e")
    server = grpc.aio.server()
    CodeFirstGrpcBuilder(
        FakeApp({BytesEchoController: BytesEchoController()}), model, messages
    ).register_all(server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()

    try:
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            req_cls = messages["BlobRequest"]
            resp_cls = messages["BlobReply"]
            call = channel.unary_unary(
                "/xime.bytese2e.BytesEchoController/EchoBlob",
                request_serializer=lambda m: m.SerializeToString(),
                response_deserializer=resp_cls.FromString,
            )
            # Gửi pb2 thô từ client để chắc chắn wire chứa binary chuẩn
            request = req_cls(
                blob=BINARY,
                parts=[b"a1", BINARY],
                by_key={"k": BINARY},
                nested=messages["Attachment"](name="img", payload=BINARY),
            )
            reply = await call(request)
            # Chiều về: server marshal BlobReply (Pydantic → pb2) đúng binary
            assert reply.blob == BINARY
            assert reply.total_len == 2 + len(BINARY)
            assert reply.nested_payload == BINARY
    finally:
        await server.stop(None)
