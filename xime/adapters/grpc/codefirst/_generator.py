from __future__ import annotations

import os
from dataclasses import dataclass, field

from xime.core.contract import ControllerScanner

from .._descriptors import DESCRIPTOR_SET_NAME
from ._builder import ContractBuilder
from ._lock import LockFile
from ._proto_emitter import ProtoEmitter
from ._sidecar import emit_sidecar, sidecar_filename


@dataclass
class GenerateResult:
    written: list[str] = field(default_factory=list)        # proto files written
    protoc_outputs: list[str] = field(default_factory=list)  # *_pb2 files written


@dataclass
class CheckResult:
    up_to_date: bool
    stale: list[str] = field(default_factory=list)    # files that differ
    missing: list[str] = field(default_factory=list)  # files not on disk

    @property
    def ok(self) -> bool:
        return self.up_to_date


# ---------------------------------------------------------------------------
# Core orchestration (testable without the CLI)
# ---------------------------------------------------------------------------

def build_proto_files(packages: list[str], lock: LockFile) -> dict[str, str]:
    """Scan controllers, build one ContractModel per server_id, render all outputs.

    Returns {relative_path: text} - the .proto files plus one contract.json
    sidecar per server_id (metadata proto cannot carry; see _sidecar.py).
    Mutates `lock` with field numbers.
    Trả {đường dẫn tương đối: text} - các .proto kèm một sidecar contract.json
    mỗi server_id. Cập nhật field number vào `lock`.
    """
    controllers = ControllerScanner().find_controllers(*packages)
    server_ids = sorted({getattr(c, "server_id", "default") for c in controllers})

    emitter = ProtoEmitter()
    files: dict[str, str] = {}
    for server_id in server_ids:
        model = ContractBuilder(server_id, lock).build(controllers)
        if not model.services:
            continue
        files.update(emitter.emit(model))
        files[f"{server_id}/{sidecar_filename()}"] = emit_sidecar(model)
    return files


def generate(
    packages: list[str],
    output_dir: str = "generated",
    lock_file: str = "proto.lock.json",
    run_protoc: bool = True,
) -> GenerateResult:
    """Generate .proto files (+ optional Python stubs) and persist the lock."""
    lock = LockFile.load(lock_file)
    files = build_proto_files(packages, lock)

    result = GenerateResult()
    for rel_path, text in files.items():
        # rel_path uses POSIX separators (proto paths); split so the OS path is consistent.
        # rel_path dùng dấu '/' (proto path); tách ra để path theo OS nhất quán.
        abs_path = os.path.join(output_dir, *rel_path.split("/"))
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        result.written.append(abs_path)

    lock.save(lock_file)

    if run_protoc:
        result.protoc_outputs = _run_protoc(output_dir, files)

    return result


def check(
    packages: list[str],
    output_dir: str = "generated",
    lock_file: str = "proto.lock.json",
) -> CheckResult:
    """Compare freshly-rendered protos against what is on disk (no mutation).

    Used by CI: a non-up-to-date result means someone changed a DTO/controller
    without running `xime grpc generate`.
    Dùng cho CI: kết quả không up-to-date nghĩa là ai đó sửa DTO/controller mà chưa generate.
    """
    lock = LockFile.load(lock_file)
    files = build_proto_files(packages, lock)

    stale: list[str] = []
    missing: list[str] = []
    for rel_path, expected in files.items():
        abs_path = os.path.join(output_dir, *rel_path.split("/"))
        if not os.path.exists(abs_path):
            missing.append(abs_path)
            continue
        with open(abs_path, encoding="utf-8") as fh:
            actual = fh.read()
        if actual != expected:
            stale.append(abs_path)

    return CheckResult(up_to_date=not (stale or missing), stale=stale, missing=missing)


# ---------------------------------------------------------------------------
# protoc invocation (per server_id dir so common.proto imports resolve)
# ---------------------------------------------------------------------------

def _run_protoc(output_dir: str, files: dict[str, str]) -> list[str]:
    import grpc_tools
    from grpc_tools import protoc

    # grpc_tools bundles the well-known types (google/protobuf/*.proto) so
    # --include_imports can resolve Timestamp etc. for the descriptor set.
    # grpc_tools kèm sẵn well-known types để --include_imports resolve được.
    well_known = os.path.join(os.path.dirname(grpc_tools.__file__), "_proto")

    # Group proto files by their server_id directory (skip non-proto outputs
    # such as the contract.json sidecar).
    # Nhóm file proto theo thư mục server_id (bỏ qua output không phải .proto
    # như sidecar contract.json).
    by_dir: dict[str, list[str]] = {}
    for rel_path in files:
        if not rel_path.endswith(".proto"):
            continue
        server_dir = os.path.dirname(rel_path)          # e.g. "public"
        abs_dir = os.path.join(output_dir, server_dir)
        by_dir.setdefault(abs_dir, []).append(os.path.basename(rel_path))

    outputs: list[str] = []
    for abs_dir, proto_names in by_dir.items():
        descriptor_out = os.path.join(abs_dir, DESCRIPTOR_SET_NAME)
        args = [
            "protoc",
            f"-I{abs_dir}",
            f"-I{well_known}",
            f"--python_out={abs_dir}",
            f"--grpc_python_out={abs_dir}",
            # Emit a FileDescriptorSet the server loads via a private
            # DescriptorPool — no pb2 module imports, so no cross-server_id
            # module name collisions.
            # Phát FileDescriptorSet để server nạp qua DescriptorPool riêng —
            # không import module pb2, nên không đụng tên giữa các server_id.
            f"--descriptor_set_out={descriptor_out}",
            "--include_imports",
            *proto_names,
        ]
        code = protoc.main(args)
        if code != 0:
            raise RuntimeError(f"protoc failed (exit {code}) for {abs_dir}: {proto_names}")
        outputs.append(descriptor_out)
        for name in proto_names:
            stem = name[:-len(".proto")]
            outputs.append(os.path.join(abs_dir, f"{stem}_pb2.py"))
            outputs.append(os.path.join(abs_dir, f"{stem}_pb2_grpc.py"))
    return outputs
