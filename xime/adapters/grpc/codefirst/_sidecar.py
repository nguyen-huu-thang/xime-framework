from __future__ import annotations

import json
import re

from ._model import ContractModel, MethodContract, StreamKind

"""contract.json sidecar - metadata that .proto cannot carry.

Emitted next to the generated .proto files (one per server_id directory) so a
client SDK generator can mirror the original Python contract 1:1:
  - original endpoint names (snake_case, before PascalCase rpc names)
  - stream kinds + which messages are chunk-wrappers (not real DTOs)
  - field fidelity hints where proto flattens Python types (decimal/uuid/date)
Sidecar contract.json - metadata mà .proto không chứa được, phát cạnh .proto
(mỗi server_id một file) để generator client lật gương contract Python 1:1:
tên endpoint gốc, loại stream + message nào là chunk-wrapper, hint fidelity
cho field bị proto làm phẳng (decimal/uuid/date).

Foreign services (e.g. Java) have no sidecar - the client generator falls back
to proto-only mode (unary methods, plain types).
Service ngoài (Java) không có sidecar - generator fallback chế độ proto-only.
"""

SCHEMA_VERSION = 1


def sidecar_filename() -> str:
    return "contract.json"


def emit_sidecar(model: ContractModel) -> str:
    """Render the contract.json text for one server_id (stable output for check())."""
    services: dict[str, dict] = {}
    wrappers: set[str] = set()

    for service in model.services:
        methods: dict[str, dict] = {}
        for method in service.methods:
            methods[method.rpc_name] = _method_entry(method, wrappers)
        services[service.name] = {
            "proto_file": service.proto_file,
            "methods": methods,
        }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "server_id": model.server_id,
        "package": _package(model.server_id),
        "services": services,
        "wrappers": sorted(wrappers),
        "field_types": dict(sorted(model.field_hints.items())),
    }
    # sort_keys + fixed indent → byte-stable across runs, diffable in review.
    # sort_keys + indent cố định → output ổn định từng byte, diff được khi review.
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _method_entry(method: MethodContract, wrappers: set[str]) -> dict:
    entry: dict = {
        "name": method.endpoint_name or _snake(method.rpc_name),
        "kind": method.kind.value,
    }
    if method.kind in (StreamKind.UNARY, StreamKind.SERVER_STREAM_TYPED):
        # Typed stream: both sides are ordinary DTOs, no wrapper. Only `kind`
        # tells the SDK generator to emit an iterator instead of an await.
        # Stream có kiểu: hai đầu đều là DTO thường, không wrapper.
        entry["request"] = method.request_message
        entry["response"] = method.response_message
    elif method.kind is StreamKind.CLIENT_STREAM:
        # request_message is the oneof chunk-wrapper; the real request DTO is
        # the metadata type recorded at build time.
        # request_message là chunk-wrapper; DTO request thật là metadata type.
        entry["request"] = method.request_py.__name__
        entry["response"] = method.response_message
        entry["wrapper"] = method.request_message
        wrappers.add(method.request_message)
    else:  # SERVER_STREAM (byte download)
        entry["request"] = method.request_message
        entry["wrapper"] = method.response_message
        wrappers.add(method.response_message)
    return entry


def _package(server_id: str) -> str:
    # Mirrors CodeFirstGrpcBuilder._package so client paths match the server.
    # Trùng với CodeFirstGrpcBuilder._package để path phía client khớp server.
    return f"xime.{re.sub(r'[^0-9a-zA-Z_]', '_', server_id)}"


def _snake(name: str) -> str:
    out: list[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0 and not name[i - 1].isupper():
            out.append("_")
        out.append(ch.lower())
    return "".join(out)
