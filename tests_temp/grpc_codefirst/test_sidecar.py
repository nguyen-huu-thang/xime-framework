"""
Test contract.json sidecar:

  emit_sidecar():
    - schema_version / server_id / package đúng
    - unary: name gốc, kind, request/response
    - client_stream: wrapper được ghi nhận + request là metadata DTO
    - server_stream: wrapper được ghi nhận
    - field_types chứa hint decimal/uuid/date (kể cả trong Optional/list)
    - output ổn định (gọi 2 lần ra cùng text)

  build_proto_files():
    - có thêm <server_id>/contract.json bên cạnh .proto
"""
from __future__ import annotations

import datetime
import json
import uuid
from decimal import Decimal

from pydantic import BaseModel

from xime.adapters.grpc.codefirst._builder import ContractBuilder
from xime.adapters.grpc.codefirst._generator import build_proto_files
from xime.adapters.grpc.codefirst._lock import LockFile
from xime.adapters.grpc.codefirst._sidecar import emit_sidecar
from xime.adapters.grpc.codefirst._type_map import python_hint
from xime.core.contract import DownloadStream, UploadStream, command, stream


class PriceQuery(BaseModel):
    order_id: uuid.UUID


class PriceReply(BaseModel):
    amount: Decimal
    discounts: list[Decimal]
    valid_until: datetime.date | None


class UploadMeta(BaseModel):
    name: str


class UploadDone(BaseModel):
    total: int


class FetchQuery(BaseModel):
    parts: int


class SidecarPricingController:
    server_id = "sidecar"

    @command("get_price")
    async def get_price(self, request: PriceQuery) -> PriceReply: ...

    @stream("upload_doc")
    async def upload_doc(self, request: UploadMeta, upload: UploadStream) -> UploadDone: ...

    @stream("fetch_doc")
    async def fetch_doc(self, request: FetchQuery, download: DownloadStream) -> None: ...


def _build_sidecar() -> dict:
    model = ContractBuilder("sidecar", LockFile()).build([SidecarPricingController])
    return json.loads(emit_sidecar(model))


class TestEmitSidecar:
    def test_header_fields(self):
        data = _build_sidecar()
        assert data["schema_version"] == 1
        assert data["server_id"] == "sidecar"
        assert data["package"] == "xime.sidecar"

    def test_unary_method_entry(self):
        methods = _build_sidecar()["services"]["SidecarPricingController"]["methods"]
        assert methods["GetPrice"] == {
            "name": "get_price",
            "kind": "unary",
            "request": "PriceQuery",
            "response": "PriceReply",
        }

    def test_client_stream_records_wrapper_and_metadata_request(self):
        data = _build_sidecar()
        entry = data["services"]["SidecarPricingController"]["methods"]["UploadDoc"]
        assert entry["kind"] == "client_stream"
        assert entry["request"] == "UploadMeta"      # DTO thật, không phải wrapper
        assert entry["response"] == "UploadDone"
        assert entry["wrapper"] == "UploadDocChunk"
        assert "UploadDocChunk" in data["wrappers"]

    def test_server_stream_records_wrapper(self):
        data = _build_sidecar()
        entry = data["services"]["SidecarPricingController"]["methods"]["FetchDoc"]
        assert entry["kind"] == "server_stream"
        assert entry["request"] == "FetchQuery"
        assert entry["wrapper"] == "FetchDocChunk"
        assert "response" not in entry

    def test_field_types_fidelity_hints(self):
        hints = _build_sidecar()["field_types"]
        assert hints["PriceQuery.order_id"] == "uuid"
        assert hints["PriceReply.amount"] == "decimal"
        assert hints["PriceReply.discounts"] == "decimal"     # xuyên qua list
        assert hints["PriceReply.valid_until"] == "date"      # xuyên qua Optional

    def test_output_is_stable(self):
        model_a = ContractBuilder("sidecar", LockFile()).build([SidecarPricingController])
        model_b = ContractBuilder("sidecar", LockFile()).build([SidecarPricingController])
        assert emit_sidecar(model_a) == emit_sidecar(model_b)


class TestPythonHint:
    def test_plain_scalars_have_no_hint(self):
        assert python_hint(str) is None
        assert python_hint(int) is None
        assert python_hint(datetime.datetime) is None   # Timestamp là lossless

    def test_decimal_uuid_date(self):
        assert python_hint(Decimal) == "decimal"
        assert python_hint(uuid.UUID) == "uuid"
        assert python_hint(datetime.date) == "date"

    def test_unwraps_containers(self):
        assert python_hint(Decimal | None) == "decimal"
        assert python_hint(list[uuid.UUID]) == "uuid"
        assert python_hint(dict[str, Decimal]) == "decimal"


class TestGeneratorIncludesSidecar:
    def test_build_proto_files_contains_contract_json(self, monkeypatch):
        # tests_temp không phải package import được - stub scanner để trả
        # thẳng controller mẫu.
        class StubScanner:
            def find_controllers(self, *packages):
                return [SidecarPricingController]

        monkeypatch.setattr(
            "xime.adapters.grpc.codefirst._generator.ControllerScanner", StubScanner
        )
        files = build_proto_files(["ignored"], LockFile())
        assert "sidecar/contract.json" in files
        data = json.loads(files["sidecar/contract.json"])
        assert data["server_id"] == "sidecar"
        # các file .proto vẫn được sinh như trước
        assert any(path.endswith(".proto") for path in files)
