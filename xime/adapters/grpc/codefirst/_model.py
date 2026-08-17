from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class StreamKind(enum.Enum):
    """How a method maps onto a gRPC RPC signature.

    Derived from the decorator + parameter types by ContractBuilder:
      @command                        → UNARY
      @stream + UploadStream param    → CLIENT_STREAM  (client → server)
      @stream + DownloadStream param  → SERVER_STREAM  (server → client, bytes)
      @stream + async generator       → SERVER_STREAM_TYPED (server → client, models)
    BIDI để dành cho v2.

    SERVER_STREAM carries raw bytes through a generated *Chunk wrapper message
    (file download); SERVER_STREAM_TYPED carries the handler's own Pydantic
    model, one message per yield, with no wrapper.
    SERVER_STREAM truyền byte thô qua wrapper *Chunk (tải file);
    SERVER_STREAM_TYPED truyền chính model Pydantic của handler, mỗi `yield`
    một message, không wrapper.
    """

    UNARY = "unary"               # Req → Resp
    CLIENT_STREAM = "client_stream"  # stream Req → Resp
    SERVER_STREAM = "server_stream"  # Req → stream Chunk (bytes)
    SERVER_STREAM_TYPED = "server_stream_typed"  # Req → stream Resp (model)


@dataclass
class FieldContract:
    """One field of a message, with a stable proto field number."""

    name: str
    proto_type: str        # "string", "int64", "repeated string", "MessageX", ...
    number: int            # field number — kept stable across regen via the lock
    optional: bool = False  # proto3 explicit presence (optional keyword)
    oneof: str | None = None  # fields sharing a name are emitted inside oneof <name>{}


@dataclass
class EnumValueContract:
    name: str
    number: int


@dataclass
class EnumContract:
    """A proto enum generated from a Python IntEnum."""

    name: str
    values: list[EnumValueContract]


@dataclass
class MessageContract:
    """A proto message generated from a Pydantic model."""

    name: str
    fields: list[FieldContract]
    reserved_numbers: list[int] = field(default_factory=list)  # numbers of deleted fields
    reserved_names: list[str] = field(default_factory=list)


@dataclass
class MethodContract:
    """One RPC: maps a controller endpoint to a proto rpc.

    The trailing fields are runtime-only (used by the serving glue); the proto
    emitter ignores them.
    Các field cuối chỉ dùng lúc serving; emitter bỏ qua.
    """

    rpc_name: str          # PascalCase, e.g. "Hash"
    request_message: str   # message name on the request side (wrapper for upload)
    response_message: str  # message name on the response side (wrapper for download)
    kind: StreamKind
    # serving-only
    handler_attr: str = ""        # controller method name to invoke
    stream_param: str = ""        # name of the Upload/DownloadStream parameter
    request_py: Any = None        # Pydantic request type (the metadata for streams)
    response_py: Any = None       # Pydantic response type (None for byte download)
    # contract metadata (sidecar) — original endpoint name, e.g. "hash"
    # metadata contract (sidecar) — tên endpoint gốc, vd "hash"
    endpoint_name: str = ""


@dataclass
class ServiceContract:
    """One gRPC service, generated from a controller class."""

    name: str              # service name = controller class name
    server_id: str
    proto_file: str        # "crypto.proto" (derived from controller name)
    methods: list[MethodContract]
    controller: Any = None  # the controller type (used by the service builder)


@dataclass
class ContractModel:
    """The full intermediate representation for one server_id.

    Single source consumed by every emitter (proto text, Python serving glue,
    and — later — client SDKs / docs).
    Nguồn duy nhất cho mọi emitter (text proto, glue serving, sau này SDK/docs).
    """

    server_id: str
    services: list[ServiceContract]
    messages: dict[str, MessageContract]
    enums: dict[str, EnumContract] = field(default_factory=dict)
    # message/enum name → set of proto file stems that reference it (shared detection)
    # tên message/enum → tập file proto tham chiếu (phát hiện shared)
    references: dict[str, set[str]] = field(default_factory=dict)
    # "Message.field" → fidelity hint where proto flattens the Python type
    # ("decimal" / "uuid" / "date") — consumed by the contract.json sidecar.
    # "Message.field" → hint giữ fidelity khi proto làm phẳng kiểu Python.
    field_hints: dict[str, str] = field(default_factory=dict)
