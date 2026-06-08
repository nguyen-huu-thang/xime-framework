from __future__ import annotations

import os
from dataclasses import dataclass, field

from xime.core.contract import ControllerScanner

from ._builder import ContractBuilder
from ._lock import LockFile
from ._proto_emitter import ProtoEmitter


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
    """Scan controllers, build one ContractModel per server_id, render all protos.

    Returns {relative_path: proto_text}. Mutates `lock` with field numbers.
    Trả {đường dẫn tương đối: text proto}. Cập nhật field number vào `lock`.
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
    from grpc_tools import protoc

    # Group proto files by their server_id directory.
    # Nhóm file proto theo thư mục server_id.
    by_dir: dict[str, list[str]] = {}
    for rel_path in files:
        server_dir = os.path.dirname(rel_path)          # e.g. "public"
        abs_dir = os.path.join(output_dir, server_dir)
        by_dir.setdefault(abs_dir, []).append(os.path.basename(rel_path))

    outputs: list[str] = []
    for abs_dir, proto_names in by_dir.items():
        args = [
            "protoc",
            f"-I{abs_dir}",
            f"--python_out={abs_dir}",
            f"--grpc_python_out={abs_dir}",
            *proto_names,
        ]
        code = protoc.main(args)
        if code != 0:
            raise RuntimeError(f"protoc failed (exit {code}) for {abs_dir}: {proto_names}")
        for name in proto_names:
            stem = name[:-len(".proto")]
            outputs.append(os.path.join(abs_dir, f"{stem}_pb2.py"))
            outputs.append(os.path.join(abs_dir, f"{stem}_pb2_grpc.py"))
    return outputs
