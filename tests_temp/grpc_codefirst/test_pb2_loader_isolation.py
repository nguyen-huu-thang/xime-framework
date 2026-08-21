"""Regression: two server_ids each with a `common.proto`-like shared message no
longer collide when loaded in the same process (backlog #2 - pb2 module name
collision in the old import-based loader).

Trước fix: loader cũ import module pb2 theo tên file trần → server_id thứ hai
nhận nhầm class của server_id thứ nhất. Sau fix: load qua DescriptorPool riêng.
"""
from __future__ import annotations

import pytest

pytest.importorskip("grpc")
pytest.importorskip("grpc_tools")

from pydantic import BaseModel  # noqa: E402

from xime.adapters.grpc.codefirst._builder import ContractBuilder  # noqa: E402
from xime.adapters.grpc.codefirst._generator import _run_protoc  # noqa: E402
from xime.adapters.grpc.codefirst._lock import LockFile  # noqa: E402
from xime.adapters.grpc.codefirst._pb2_loader import load_message_classes  # noqa: E402
from xime.adapters.grpc.codefirst._proto_emitter import ProtoEmitter  # noqa: E402
from xime.core.contract import command  # noqa: E402


# Two controllers on different server_ids whose request DTOs share the name
# `SharedRecord` but have DIFFERENT shapes. The old loader cached the first
# `*_pb2` module under its bare name, so the second server got the wrong class.
# Hai controller khác server_id, DTO trùng tên `SharedRecord` nhưng KHÁC cấu trúc.

class SharedRecord(BaseModel):
    public_field: str


class PublicController:
    server_id = "iso_public"

    @command("get")
    async def get(self, request: SharedRecord) -> SharedRecord: ...


class _InternalSharedRecord(BaseModel):
    # different field set, but emitted as message name "SharedRecord"
    internal_id: int
    secret: str


# Force the emitted message name to collide with the public one.
_InternalSharedRecord.__name__ = "SharedRecord"


class InternalController:
    server_id = "iso_internal"

    @command("get")
    async def get(self, request: _InternalSharedRecord) -> _InternalSharedRecord: ...


def _emit(controller, server_id, out):
    model = ContractBuilder(server_id, LockFile()).build([controller])
    files = ProtoEmitter().emit(model)
    for rel, text in files.items():
        path = out.joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _run_protoc(str(out), files)


def test_two_server_ids_with_same_message_name_do_not_collide(tmp_path):
    out = tmp_path / "generated"
    _emit(PublicController, "iso_public", out)
    _emit(InternalController, "iso_internal", out)

    # Load both in the same process - order matters for the old bug.
    public_messages = load_message_classes(str(out), "iso_public")
    internal_messages = load_message_classes(str(out), "iso_internal")

    public_record = public_messages["SharedRecord"]
    internal_record = internal_messages["SharedRecord"]

    # Each server's SharedRecord keeps its OWN fields - no cross-contamination.
    public_fields = set(public_record.DESCRIPTOR.fields_by_name)
    internal_fields = set(internal_record.DESCRIPTOR.fields_by_name)

    assert public_fields == {"public_field"}
    assert internal_fields == {"internal_id", "secret"}
    assert public_record is not internal_record
