from __future__ import annotations

import os

from .._descriptors import DESCRIPTOR_SET_NAME, load_messages_from_descriptor_set


def load_message_classes(output_dir: str, server_id: str) -> dict[str, type]:
    """Load the generated message classes for a server, mapping name → class.

    Reads the FileDescriptorSet that `xime grpc generate` writes at
    <output_dir>/<server_id>/_descriptors.binpb and builds message classes in a
    PRIVATE DescriptorPool. Unlike the old import-based loader, this never adds
    to sys.path nor registers pb2 modules in sys.modules, so two server_ids that
    each define a `common.proto` no longer collide on the `common_pb2` module
    name.
    Đọc FileDescriptorSet do `xime grpc generate` ghi tại
    <output_dir>/<server_id>/_descriptors.binpb, dựng message class trong
    DescriptorPool RIÊNG. Khác loader import cũ, hàm này không đụng sys.path,
    không đăng ký module pb2 vào sys.modules, nên hai server_id cùng có
    `common.proto` không còn đụng tên module `common_pb2`.

    Raises FileNotFoundError if the descriptor set is missing (run generate first).
    """
    directory = os.path.join(output_dir, server_id)
    descriptor_path = os.path.join(directory, DESCRIPTOR_SET_NAME)
    if not os.path.isfile(descriptor_path):
        raise FileNotFoundError(
            f"Generated descriptor set not found: {descriptor_path}\n"
            f"Run `xime grpc generate` before serving code-first gRPC."
        )
    return load_messages_from_descriptor_set(descriptor_path)
