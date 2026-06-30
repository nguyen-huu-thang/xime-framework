from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from google.protobuf import descriptor_pb2

"""Client SDK generator - `xime grpc client --proto <dir> --out <dir>`.

Input : a directory of .proto files copied from the target service's repo,
        plus the contract.json sidecar when the target is a Xime service.
Output: a self-contained Python package (the SDK):

    <out>/
    |- __init__.py          # exports client classes + models
    |- _models.py           # Pydantic models + IntEnums mirrored from messages
    |- _clients.py          # one client class per service (methods per rpc)
    |- _descriptors.binpb   # FileDescriptorSet - loaded by SdkRuntime at import

With a sidecar the SDK mirrors the original Python contract 1:1 (method names,
Decimal/UUID/date fidelity, streaming). Without one (foreign/Java services)
only unary methods are generated and types follow plain proto mapping.
Có sidecar thì SDK lật gương contract Python gốc 1:1 (tên method, fidelity
Decimal/UUID/date, streaming). Không có (service Java) thì chỉ sinh method
unary và kiểu theo map proto thuần.
"""

_F = descriptor_pb2.FieldDescriptorProto

# Proto scalar type → Python annotation source text.
# Kiểu scalar proto → text annotation Python.
_SCALAR_PY: dict[int, str] = {
    _F.TYPE_DOUBLE: "float",
    _F.TYPE_FLOAT: "float",
    _F.TYPE_INT64: "int",
    _F.TYPE_UINT64: "int",
    _F.TYPE_INT32: "int",
    _F.TYPE_FIXED64: "int",
    _F.TYPE_FIXED32: "int",
    _F.TYPE_BOOL: "bool",
    _F.TYPE_STRING: "str",
    _F.TYPE_BYTES: "bytes",
    _F.TYPE_UINT32: "int",
    _F.TYPE_SFIXED32: "int",
    _F.TYPE_SFIXED64: "int",
    _F.TYPE_SINT32: "int",
    _F.TYPE_SINT64: "int",
}

_HINT_PY = {"decimal": "Decimal", "uuid": "UUID", "date": "datetime.date"}


@dataclass
class ClientGenResult:
    written: list[str] = field(default_factory=list)
    skipped_methods: list[str] = field(default_factory=list)  # streaming without sidecar


def _framework_xime_version() -> str:
    """Version of the running xime framework, used as the generated SDK's
    dependency floor. The SDK imports SdkRuntime from this framework, so it must
    require at least the version that produced it. Falls back when uninstalled.
    Version framework đang chạy - làm floor dependency cho SDK sinh ra.

    Delegates to xime.__version__ so there is a single source of truth (and a
    single fallback literal to keep in sync with pyproject.toml on each bump).
    Ủy quyền cho xime.__version__ để chỉ có MỘT nguồn version (và một literal
    fallback duy nhất cần đồng bộ với pyproject.toml mỗi lần bump).
    """
    from xime import __version__

    return __version__


def generate_client_sdk(
    proto_dir: str,
    out_dir: str,
    package: str | None = None,
    package_version: str = "0.1.0",
) -> ClientGenResult:
    """Generate a typed client SDK package from .proto (+ optional sidecar).

    Without `package`, out_dir IS the importable package (committed in the
    consumer repo, e.g. clients/trust/).
    Không có `package`, out_dir CHÍNH LÀ package import được (commit ở repo
    consumer, vd clients/trust/).

    With `package` (a distribution name, e.g. "trust-client"), the layout is
    pip-installable - ready for `pip install -e`, a git URL dependency, or a
    package index later:
    Có `package` (tên distribution, vd "trust-client"), layout cài được bằng
    pip - sẵn sàng cho `pip install -e`, dependency git URL, hoặc registry sau này:

        <out_dir>/
        |- pyproject.toml
        |- trust_client/        # module = tên package, '-' thành '_'
           |- __init__.py ...
    """
    if not os.path.isdir(proto_dir):
        raise FileNotFoundError(
            f"Proto directory not found: {proto_dir}\n"
            "Pass the directory holding the target service's .proto files "
            "(e.g. contracts/trust)."
        )
    proto_names = sorted(
        f for f in os.listdir(proto_dir) if f.endswith(".proto")
    )
    if not proto_names:
        raise FileNotFoundError(f"No .proto files found in: {proto_dir}")

    module_name: str | None = None
    pkg_dir = out_dir
    if package is not None:
        module_name = package.replace("-", "_")
        if not module_name.isidentifier():
            raise ValueError(
                f"Invalid package name '{package}': it must map to a valid "
                f"Python module name (got '{module_name}')."
            )
        pkg_dir = os.path.join(out_dir, module_name)

    sidecar = _load_sidecar(proto_dir)
    os.makedirs(pkg_dir, exist_ok=True)

    result = ClientGenResult()
    descriptor_path = os.path.join(pkg_dir, "_descriptors.binpb")
    _run_protoc_descriptor(proto_dir, proto_names, descriptor_path)
    result.written.append(descriptor_path)

    with open(descriptor_path, "rb") as fh:
        fds = descriptor_pb2.FileDescriptorSet.FromString(fh.read())
    own_files = [f for f in fds.file if not f.name.startswith("google/protobuf/")]

    wrappers: set[str] = set(sidecar.get("wrappers", [])) if sidecar else set()
    field_types: dict[str, str] = sidecar.get("field_types", {}) if sidecar else {}

    models_src, model_names = _emit_models(own_files, wrappers, field_types)
    clients_src, client_names = _emit_clients(own_files, sidecar, result)
    init_src = _emit_init(client_names, model_names)

    for fname, src in (
        ("_models.py", models_src),
        ("_clients.py", clients_src),
        ("__init__.py", init_src),
    ):
        path = os.path.join(pkg_dir, fname)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(src)
        result.written.append(path)

    if package is not None and module_name is not None:
        pyproject_path = os.path.join(out_dir, "pyproject.toml")
        with open(pyproject_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(_emit_pyproject(package, module_name, package_version))
        result.written.append(pyproject_path)
    return result


# ---------------------------------------------------------------------------
# protoc → FileDescriptorSet
# ---------------------------------------------------------------------------

def _run_protoc_descriptor(proto_dir: str, proto_names: list[str], out_path: str) -> None:
    import grpc_tools
    from grpc_tools import protoc

    # grpc_tools bundles the well-known types (google/protobuf/*.proto).
    # grpc_tools kèm sẵn các well-known types.
    well_known = os.path.join(os.path.dirname(grpc_tools.__file__), "_proto")
    args = [
        "protoc",
        f"-I{proto_dir}",
        f"-I{well_known}",
        f"--descriptor_set_out={out_path}",
        "--include_imports",
        *proto_names,
    ]
    code = protoc.main(args)
    if code != 0:
        raise RuntimeError(f"protoc failed (exit {code}) for {proto_dir}: {proto_names}")


def _load_sidecar(proto_dir: str) -> dict | None:
    path = os.path.join(proto_dir, "contract.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# _models.py
# ---------------------------------------------------------------------------

def _emit_models(
    own_files: list,
    wrappers: set[str],
    field_types: dict[str, str],
) -> tuple[str, list[str]]:
    enums: list[str] = []
    models: list[str] = []
    names: list[str] = []
    uses = {"datetime": False, "decimal": False, "uuid": False, "field": False}

    for fd in own_files:
        for enum_proto in fd.enum_type:
            enums.append(_emit_enum(enum_proto))
            names.append(enum_proto.name)
        for msg in fd.message_type:
            if msg.name in wrappers:
                continue  # chunk-wrapper là chi tiết transport, không phải DTO
            models.append(_emit_message(msg, field_types, uses))
            names.append(msg.name)

    header = ['"""Generated by `xime grpc client`. DO NOT EDIT."""']
    header.append("from __future__ import annotations")
    header.append("")
    if uses["datetime"]:
        header.append("import datetime")
    if uses["decimal"]:
        header.append("from decimal import Decimal")
    if enums:
        header.append("from enum import IntEnum")
    if uses["uuid"]:
        header.append("from uuid import UUID")
    header.append("")
    header.append("from pydantic import BaseModel" + (", Field" if uses["field"] else ""))

    body = "\n".join(header) + "\n\n\n" + "\n\n\n".join(enums + models)

    # Resolve forward references (messages may reference each other).
    # Phân giải forward reference (message có thể tham chiếu lẫn nhau).
    model_names = [n for n in names if any(m.startswith(f"class {n}(BaseModel)") for m in models)]
    if model_names:
        rebuild = "\n".join(f"{n}.model_rebuild()" for n in model_names)
        body += "\n\n\n" + rebuild
    return body + "\n", names


def _emit_enum(enum_proto) -> str:
    lines = [f"class {enum_proto.name}(IntEnum):"]
    for value in enum_proto.value:
        lines.append(f"    {value.name} = {value.number}")
    return "\n".join(lines)


def _emit_message(msg, field_types: dict[str, str], uses: dict[str, bool]) -> str:
    # Map entries are synthesized nested types: index them for dict rendering.
    # Map entry là nested type tự sinh: index lại để render dict.
    map_entries = {
        nested.name: nested for nested in msg.nested_type
        if nested.options.map_entry
    }

    lines = [f"class {msg.name}(BaseModel):"]
    if not msg.field:
        lines.append("    pass")
    for f in msg.field:
        annotation, default = _render_field(msg.name, f, map_entries, field_types, uses)
        suffix = f" = {default}" if default is not None else ""
        lines.append(f"    {f.name}: {annotation}{suffix}")
    return "\n".join(lines)


def _render_field(
    message_name: str,
    f,
    map_entries: dict,
    field_types: dict[str, str],
    uses: dict[str, bool],
) -> tuple[str, str | None]:
    # map<K, V> — proto encodes it as repeated MapEntry nested type.
    # map<K, V> — proto mã hóa thành repeated MapEntry.
    if f.type == _F.TYPE_MESSAGE:
        entry = map_entries.get(_short_name(f.type_name))
        if entry is not None:
            key_t = _base_type(message_name, entry.field[0], field_types, uses)
            val_t = _base_type(message_name, entry.field[1], field_types, uses)
            uses["field"] = True
            return f"dict[{key_t}, {val_t}]", "Field(default_factory=dict)"

    base = _base_type(message_name, f, field_types, uses)

    if f.label == _F.LABEL_REPEATED:
        uses["field"] = True
        return f"list[{base}]", "Field(default_factory=list)"

    # proto3 presence: explicit `optional` and message-typed fields are nullable.
    # proto3 presence: field `optional` và field kiểu message là nullable.
    if f.proto3_optional or f.type == _F.TYPE_MESSAGE:
        return f"{base} | None", "None"
    return base, None


def _base_type(message_name: str, f, field_types: dict[str, str], uses: dict[str, bool]) -> str:
    if f.type == _F.TYPE_MESSAGE:
        if f.type_name == ".google.protobuf.Timestamp":
            uses["datetime"] = True
            return "datetime.datetime"
        return _short_name(f.type_name)
    if f.type == _F.TYPE_ENUM:
        return _short_name(f.type_name)
    if f.type == _F.TYPE_STRING:
        hint = field_types.get(f"{message_name}.{f.name}")
        if hint in _HINT_PY:
            uses[hint if hint != "date" else "datetime"] = True
            if hint == "decimal":
                uses["decimal"] = True
            if hint == "uuid":
                uses["uuid"] = True
            return _HINT_PY[hint]
        return "str"
    return _SCALAR_PY[f.type]


def _short_name(type_name: str) -> str:
    # ".xime.e2e.HashRequest" → "HashRequest"
    return type_name.rsplit(".", 1)[-1]


# ---------------------------------------------------------------------------
# _clients.py
# ---------------------------------------------------------------------------

def _emit_clients(
    own_files: list,
    sidecar: dict | None,
    result: ClientGenResult,
) -> tuple[str, list[str]]:
    classes: list[str] = []
    class_names: list[str] = []
    model_imports: set[str] = set()
    has_streaming = False

    sidecar_services = (sidecar or {}).get("services", {})

    for fd in own_files:
        for service in fd.service:
            methods_meta = sidecar_services.get(service.name, {}).get("methods", {})
            src, used_models, streaming = _emit_client_class(
                fd.package, service, methods_meta, result
            )
            classes.append(src)
            class_names.append(_client_class_name(service.name))
            model_imports.update(used_models)
            has_streaming = has_streaming or streaming

    header = ['"""Generated by `xime grpc client`. DO NOT EDIT."""']
    header.append("from __future__ import annotations")
    header.append("")
    if has_streaming:
        header.append("from collections.abc import AsyncIterator")
    header.append("from pathlib import Path")
    header.append("")
    header.append("import grpc.aio")
    header.append("")
    header.append("from xime.adapters.grpc.client import SdkRuntime")
    if model_imports:
        names = ", ".join(sorted(model_imports))
        header.append(f"from ._models import {names}")
    header.append("")
    header.append('_runtime = SdkRuntime(Path(__file__).with_name("_descriptors.binpb"))')

    return "\n".join(header) + "\n\n\n" + "\n\n\n".join(classes) + "\n", class_names


def _emit_client_class(
    package: str,
    service,
    methods_meta: dict,
    result: ClientGenResult,
) -> tuple[str, set[str], bool]:
    class_name = _client_class_name(service.name)
    used_models: set[str] = set()
    has_streaming = False

    lines = [
        f"class {class_name}:",
        f'    """Generated client for gRPC service {package}.{service.name}."""',
        "",
        "    def __init__(self, channel: grpc.aio.Channel) -> None:",
        "        self._channel = channel",
    ]

    for method in service.method:
        path = f"/{package}.{service.name}/{method.name}"
        meta = methods_meta.get(method.name)

        if meta is None:
            # No sidecar entry: proto-only fallback supports unary methods.
            # Không có sidecar: fallback proto-only chỉ hỗ trợ unary.
            if method.client_streaming or method.server_streaming:
                result.skipped_methods.append(path)
                continue
            meta = {
                "name": _snake(method.name),
                "kind": "unary",
                "request": _short_name(method.input_type),
                "response": _short_name(method.output_type),
            }

        kind = meta["kind"]
        py_name = meta["name"]
        request = meta["request"]
        used_models.add(request)
        lines.append("")

        if kind == "unary":
            response = meta["response"]
            used_models.add(response)
            lines += [
                f"    async def {py_name}(self, request: {request}) -> {response}:",
                "        return await _runtime.unary(",
                "            self._channel,",
                f'            "{path}",',
                "            request,",
                f'            "{request}",',
                f"            {response},",
                f'            "{response}",',
                "        )",
            ]
        elif kind == "client_stream":
            has_streaming = True
            response = meta["response"]
            wrapper = meta["wrapper"]
            used_models.add(response)
            lines += [
                f"    async def {py_name}(",
                f"        self, request: {request}, chunks: AsyncIterator[bytes]",
                f"    ) -> {response}:",
                "        return await _runtime.client_stream(",
                "            self._channel,",
                f'            "{path}",',
                "            request,",
                f'            "{wrapper}",',
                f"            {response},",
                f'            "{response}",',
                "            chunks,",
                "        )",
            ]
        else:  # server_stream
            has_streaming = True
            wrapper = meta["wrapper"]
            lines += [
                f"    def {py_name}(self, request: {request}) -> AsyncIterator[bytes]:",
                "        return _runtime.server_stream(",
                "            self._channel,",
                f'            "{path}",',
                "            request,",
                f'            "{request}",',
                f'            "{wrapper}",',
                "        )",
            ]

    return "\n".join(lines), used_models, has_streaming


def _client_class_name(service_name: str) -> str:
    stem = service_name
    if stem.endswith("Controller"):
        stem = stem[: -len("Controller")]
    return f"{stem}Client"


def _snake(name: str) -> str:
    out: list[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0 and not name[i - 1].isupper():
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


# ---------------------------------------------------------------------------
# pyproject.toml (package mode)
# ---------------------------------------------------------------------------

def _emit_pyproject(package: str, module_name: str, version: str) -> str:
    # The SDK runtime needs xime (SdkRuntime/marshal) + grpcio/protobuf, which
    # the xime[grpc] extra provides. The floor tracks the framework version that
    # generated this SDK so it never runs against an older, incompatible runtime.
    # SDK lúc chạy cần xime (SdkRuntime/marshal) + grpcio/protobuf - extra
    # xime[grpc] cung cấp đủ. Floor bám version framework đã sinh ra SDK này.
    xime_floor = _framework_xime_version()
    return f'''# Generated by `xime grpc client`. DO NOT EDIT.
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "{package}"
version = "{version}"
description = "Generated gRPC client SDK ({package}) - do not edit by hand"
requires-python = ">=3.12"
dependencies = [
    "xime[grpc]>={xime_floor}",
]

[tool.setuptools.packages.find]
include = ["{module_name}*"]

[tool.setuptools.package-data]
{module_name} = ["*.binpb"]
'''


# ---------------------------------------------------------------------------
# __init__.py
# ---------------------------------------------------------------------------

def _emit_init(client_names: list[str], model_names: list[str]) -> str:
    lines = ['"""Generated by `xime grpc client`. DO NOT EDIT."""']
    if client_names:
        lines.append(f"from ._clients import {', '.join(sorted(client_names))}")
    if model_names:
        lines.append(f"from ._models import {', '.join(sorted(model_names))}")
    exported = sorted(client_names) + sorted(model_names)
    quoted = ", ".join(f'"{n}"' for n in exported)
    lines.append("")
    lines.append(f"__all__ = [{quoted}]")
    return "\n".join(lines) + "\n"
