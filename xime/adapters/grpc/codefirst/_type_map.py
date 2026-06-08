from __future__ import annotations

import datetime
import decimal
import enum
import typing
import uuid
from typing import Any

from pydantic import BaseModel


class UnsupportedTypeError(Exception):
    """Raised at generate time when a Python type cannot be mapped to proto."""

    def __init__(self, py_type: Any, context: str = "") -> None:
        self.py_type = py_type
        suffix = f" ({context})" if context else ""
        super().__init__(f"Cannot map Python type {py_type!r} to a proto type{suffix}")


# ---------------------------------------------------------------------------
# Annotated overrides for integer width / signedness
# ---------------------------------------------------------------------------
#
# Default int → int64. Override per field with typing.Annotated:
#     size: Annotated[int, ProtoInt32]
#     id:   Annotated[int, ProtoUInt64]
# Mặc định int → int64; override từng field bằng Annotated.

class _ProtoIntMarker:
    """Base marker carrying the proto scalar name an int field should use."""

    proto_type = "int64"


class ProtoInt32(_ProtoIntMarker):
    proto_type = "int32"


class ProtoInt64(_ProtoIntMarker):
    proto_type = "int64"


class ProtoUInt32(_ProtoIntMarker):
    proto_type = "uint32"


class ProtoUInt64(_ProtoIntMarker):
    proto_type = "uint64"


class ProtoSInt32(_ProtoIntMarker):
    proto_type = "sint32"


class ProtoSInt64(_ProtoIntMarker):
    proto_type = "sint64"


# Scalar Python types with a fixed proto mapping.
# Kiểu scalar Python ánh xạ cố định sang proto.
_SCALARS: dict[Any, str] = {
    str: "string",
    bytes: "bytes",
    bool: "bool",      # NOTE: check bool before int — bool is a subclass of int
    int: "int64",
    float: "double",
    uuid.UUID: "string",
    decimal.Decimal: "string",
    datetime.datetime: "google.protobuf.Timestamp",
    datetime.date: "string",
}


def map_type(py_type: Any, registry: Any) -> tuple[str, bool]:
    """Map a Python annotation to (proto_type, optional).

    `registry` must expose register_message(model)->name and
    register_enum(enum_cls)->name so nested models/enums are pulled in.
    `registry` cần có register_message/register_enum để kéo theo model/enum lồng nhau.

    Returns the proto type string (e.g. "repeated string", "UserDto") and whether
    the field uses proto3 explicit presence (the `optional` keyword).
    Trả chuỗi proto type và cờ optional (proto3 explicit presence).
    """
    # 1) Annotated[...] — pull out integer-width override / underlying type.
    if hasattr(py_type, "__metadata__"):
        base = py_type.__origin__
        for meta in py_type.__metadata__:
            marker = meta if isinstance(meta, type) else type(meta)
            if isinstance(marker, type) and issubclass(marker, _ProtoIntMarker):
                return marker.proto_type, False
        return map_type(base, registry)

    origin = typing.get_origin(py_type)

    # 2) Optional[T] / T | None → optional <T>
    if origin is typing.Union or _is_uniontype(py_type):
        args = [a for a in typing.get_args(py_type) if a is not type(None)]
        if len(args) != 1:
            raise UnsupportedTypeError(py_type, "only Optional[X] unions are supported")
        proto, _ = map_type(args[0], registry)
        return proto, True

    # 3) list[T] → repeated <T>
    if origin in (list, typing.List):  # noqa: UP006
        (elem,) = typing.get_args(py_type) or (Any,)
        proto, _ = map_type(elem, registry)
        return f"repeated {proto}", False

    # 4) dict[K, V] → map<K, V>
    if origin in (dict, typing.Dict):  # noqa: UP006
        key_t, val_t = typing.get_args(py_type) or (str, Any)
        key_proto = _scalar_or_error(key_t, "map key")
        val_proto, _ = map_type(val_t, registry)
        if val_proto.startswith("repeated ") or val_proto.startswith("map<"):
            raise UnsupportedTypeError(py_type, "map values cannot be repeated/map")
        return f"map<{key_proto}, {val_proto}>", False

    # 5) Nested Pydantic model → message
    if isinstance(py_type, type) and issubclass(py_type, BaseModel):
        return registry.register_message(py_type), False

    # 6) Enum
    if isinstance(py_type, type) and issubclass(py_type, enum.Enum):
        if issubclass(py_type, int):
            return registry.register_enum(py_type), False
        if issubclass(py_type, str):
            return "string", False
        raise UnsupportedTypeError(py_type, "only IntEnum / str-Enum are supported")

    # 7) Scalars (bool before int via dict ordering handled in _lookup_scalar)
    scalar = _lookup_scalar(py_type)
    if scalar is not None:
        return scalar, False

    raise UnsupportedTypeError(py_type)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _lookup_scalar(py_type: Any) -> str | None:
    # bool is a subclass of int — match exact types, and check bool first.
    # bool là subclass của int — khớp đúng type, kiểm tra bool trước.
    if py_type is bool:
        return "bool"
    return _SCALARS.get(py_type)


def _scalar_or_error(py_type: Any, context: str) -> str:
    scalar = _lookup_scalar(py_type)
    if scalar is None or scalar.startswith(("repeated", "map<")):
        raise UnsupportedTypeError(py_type, context)
    return scalar


def _is_uniontype(py_type: Any) -> bool:
    # Python 3.10+ `X | None` produces types.UnionType, distinct from typing.Union.
    import types as _types
    return isinstance(py_type, getattr(_types, "UnionType", ()))
