from __future__ import annotations

import base64
import datetime
import decimal
import enum
import uuid
from typing import Any

from google.protobuf import json_format
from google.protobuf.descriptor import Descriptor, FieldDescriptor
from pydantic import BaseModel

"""Pydantic ↔ protobuf message marshalling at the transport boundary.

Business code only ever sees Pydantic models; these helpers translate to/from
the generated protobuf classes so the wire stays standard gRPC/protobuf and
remains interoperable with Java/Go/Rust/C++ clients.
Business code chỉ thấy Pydantic; helper này dịch sang/từ protobuf để giữ wire chuẩn.

Implementation note: we lean on google.protobuf.json_format, which handles
nested messages, repeated, map, enums, optional and Timestamp. Field names match
because the generator emits proto field names identical to the Pydantic ones.
Dùng json_format để xử lý nested/repeated/map/enum/optional/Timestamp; tên field khớp.

bytes fields need special care on BOTH directions (proto JSON encodes bytes as
base64 text, while Pydantic treats a str for a bytes field as utf-8):
- model → pb2: model_dump(mode="python") + an explicit sanitizer that base64-
  encodes bytes (mode="json" would utf-8-decode and crash/corrupt binary data).
- pb2 → model: walk the message descriptor and base64-decode every bytes field
  back to real bytes before Pydantic validation.
Field bytes phải xử lý riêng cả HAI chiều (proto JSON mã hóa bytes thành base64,
còn Pydantic coi str cho field bytes là utf-8): chiều đi dùng mode="python" +
sanitizer tự base64; chiều về duyệt descriptor decode base64 thành bytes thật.
"""


def pydantic_to_pb2(model: BaseModel, pb2_class: type) -> Any:
    """Build a protobuf message instance from a Pydantic model."""
    data = _sanitize(model.model_dump(mode="python"))
    message = pb2_class()
    json_format.ParseDict(data, message, ignore_unknown_fields=True)
    return message


def pb2_to_pydantic(message: Any, model_class: type[BaseModel]) -> BaseModel:
    """Build a Pydantic model from a protobuf message instance."""
    data = _message_to_dict(message)
    _decode_bytes_fields(data, message.DESCRIPTOR)
    return model_class.model_validate(data)


# ---------------------------------------------------------------------------
# model → ParseDict-compatible primitives
# ---------------------------------------------------------------------------

def _sanitize(value: Any) -> Any:
    """Convert python-mode dump values into proto-JSON compatible primitives.

    Mirrors what Pydantic's JSON mode produces for every type the code-first
    type map supports, except bytes are base64 (proto JSON convention) instead
    of utf-8.
    Chuyển giá trị model_dump(mode="python") về primitive hợp lệ cho ParseDict;
    giống JSON mode của Pydantic, riêng bytes là base64 theo quy ước proto JSON.
    """
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    if isinstance(value, enum.Enum):
        return _sanitize(value.value)
    if isinstance(value, datetime.datetime):
        # proto Timestamp requires an RFC3339 string with a timezone offset.
        # A naive datetime has none, so ParseDict would crash — assume UTC.
        # Timestamp proto cần offset timezone; datetime naive không có nên coi
        # như UTC để ParseDict không lỗi.
        if value.tzinfo is None:
            value = value.replace(tzinfo=datetime.UTC)
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, (decimal.Decimal, uuid.UUID)):
        return str(value)
    return value


# ---------------------------------------------------------------------------
# pb2 dict → real bytes
# ---------------------------------------------------------------------------

def _decode_bytes_fields(data: dict, descriptor: Descriptor) -> None:
    """Recursively replace base64 strings with real bytes per the descriptor."""
    for field in descriptor.fields:
        value = data.get(field.name)
        if value is None:
            continue

        if field.type == FieldDescriptor.TYPE_BYTES:
            if _is_repeated(field):
                data[field.name] = [base64.b64decode(item) for item in value]
            else:
                data[field.name] = base64.b64decode(value)
            continue

        if field.type != FieldDescriptor.TYPE_MESSAGE:
            continue

        # map<K, V>: the entry is a synthesized message with key/value fields.
        # map<K, V>: entry là message tự sinh với hai field key/value.
        if field.message_type.GetOptions().map_entry:
            entry_value = field.message_type.fields_by_name["value"]
            if entry_value.type == FieldDescriptor.TYPE_BYTES:
                data[field.name] = {
                    key: base64.b64decode(item) for key, item in value.items()
                }
            elif entry_value.type == FieldDescriptor.TYPE_MESSAGE:
                for item in value.values():
                    _decode_bytes_fields(item, entry_value.message_type)
            continue

        if field.message_type.full_name.startswith("google.protobuf."):
            continue  # well-known types (Timestamp...) giữ nguyên dạng JSON
        if _is_repeated(field):
            for item in value:
                _decode_bytes_fields(item, field.message_type)
        else:
            _decode_bytes_fields(value, field.message_type)


def _is_repeated(field: FieldDescriptor) -> bool:
    # protobuf >= 6.30 deprecates .label in favor of .is_repeated; support both.
    # protobuf >= 6.30 bỏ .label, thay bằng .is_repeated; hỗ trợ cả hai.
    flag = getattr(field, "is_repeated", None)
    if flag is not None:
        return flag() if callable(flag) else bool(flag)
    return field.label == FieldDescriptor.LABEL_REPEATED


def _message_to_dict(message: Any) -> dict:
    """MessageToDict with proto field names, robust across protobuf versions.

    Newer protobuf renamed `including_default_value_fields` to
    `always_print_fields_with_no_presence`; try the modern kwarg first.
    Protobuf mới đổi tên kwarg — thử kwarg mới trước, fallback kwarg cũ.
    """
    # use_integers_for_enums: Pydantic IntEnum fields validate against the
    # numeric value, not the proto enum NAME string that MessageToDict emits
    # by default.
    # use_integers_for_enums: field IntEnum của Pydantic nhận giá trị số,
    # không nhận chuỗi TÊN enum mà MessageToDict trả về mặc định.
    try:
        return json_format.MessageToDict(
            message,
            preserving_proto_field_name=True,
            always_print_fields_with_no_presence=True,
            use_integers_for_enums=True,
        )
    except TypeError:
        return json_format.MessageToDict(
            message,
            preserving_proto_field_name=True,
            including_default_value_fields=True,
            use_integers_for_enums=True,
        )
