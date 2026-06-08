from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from typing import Any


def load_message_classes(output_dir: str, server_id: str) -> dict[str, type]:
    """Import the generated *_pb2 modules for a server and map message name → class.

    Expects `xime grpc generate` to have produced <output_dir>/<server_id>/*_pb2.py
    (protoc output). The directory is put on sys.path so the generated modules'
    sibling imports (e.g. `import common_pb2`) resolve.
    Cần `xime grpc generate` đã sinh *_pb2.py; thêm thư mục vào sys.path để import chéo.

    Raises FileNotFoundError if the directory does not exist (run generate first).
    """
    directory = os.path.join(output_dir, server_id)
    if not os.path.isdir(directory):
        raise FileNotFoundError(
            f"Generated proto directory not found: {directory}\n"
            f"Run `xime grpc generate` before serving code-first gRPC."
        )

    abs_dir = os.path.abspath(directory)
    if abs_dir not in sys.path:
        sys.path.insert(0, abs_dir)

    classes: dict[str, type] = {}
    for fname in sorted(os.listdir(directory)):
        if not fname.endswith("_pb2.py"):
            continue
        module = _import_from_path(os.path.join(directory, fname))
        descriptor = getattr(module, "DESCRIPTOR", None)
        if descriptor is None:
            continue
        for message_name in descriptor.message_types_by_name:
            classes[message_name] = getattr(module, message_name)
    return classes


def _import_from_path(path: str) -> Any:
    module_name = os.path.splitext(os.path.basename(path))[0]
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[module_name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module
