from __future__ import annotations

from typing import Any

from google.protobuf import json_format
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
"""


def pydantic_to_pb2(model: BaseModel, pb2_class: type) -> Any:
    """Build a protobuf message instance from a Pydantic model."""
    data = model.model_dump(mode="json")
    message = pb2_class()
    json_format.ParseDict(data, message, ignore_unknown_fields=True)
    return message


def pb2_to_pydantic(message: Any, model_class: type[BaseModel]) -> BaseModel:
    """Build a Pydantic model from a protobuf message instance."""
    data = _message_to_dict(message)
    return model_class(**data)


def _message_to_dict(message: Any) -> dict:
    """MessageToDict with proto field names, robust across protobuf versions.

    Newer protobuf renamed `including_default_value_fields` to
    `always_print_fields_with_no_presence`; try the modern kwarg first.
    Protobuf mới đổi tên kwarg — thử kwarg mới trước, fallback kwarg cũ.
    """
    try:
        return json_format.MessageToDict(
            message,
            preserving_proto_field_name=True,
            always_print_fields_with_no_presence=True,
        )
    except TypeError:
        return json_format.MessageToDict(
            message,
            preserving_proto_field_name=True,
            including_default_value_fields=True,
        )
