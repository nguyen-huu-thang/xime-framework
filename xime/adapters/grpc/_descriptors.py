from __future__ import annotations

from pathlib import Path

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

"""Shared FileDescriptorSet loading - used by both the code-first server
(_pb2_loader) and generated client SDKs (SdkRuntime).

Message classes are built inside a PRIVATE DescriptorPool per descriptor set,
so multiple servers/SDKs in one process never collide on proto module names
(the historical `common_pb2` weakness of import-based loading) and sys.path
stays untouched.
Nạp FileDescriptorSet dùng chung cho server code-first lẫn SDK client. Message
class được dựng trong DescriptorPool RIÊNG theo từng descriptor set, nên nhiều
server/SDK trong một process không bao giờ đụng tên module pb2 (điểm yếu
`common_pb2` của cách import cũ) và không đụng sys.path.
"""

# protoc --descriptor_set_out filename, written per server_id dir at generate
# time and read back by the loaders.
# Tên file --descriptor_set_out của protoc, ghi mỗi thư mục server_id lúc
# generate và được loader đọc lại.
DESCRIPTOR_SET_NAME = "_descriptors.binpb"


def load_messages_from_descriptor_set(path: str | Path) -> dict[str, type]:
    """Read a FileDescriptorSet and return {message short name → class}."""
    data = Path(path).read_bytes()
    fds = descriptor_pb2.FileDescriptorSet.FromString(data)

    pool = descriptor_pool.DescriptorPool()
    # protoc --include_imports writes dependencies before dependents, so a
    # single pass is enough; duplicates (well-known types) are tolerated.
    # protoc --include_imports ghi dependency trước nên một lượt là đủ;
    # trùng lặp (well-known types) được bỏ qua.
    classes: dict[str, type] = {}
    for fd_proto in fds.file:
        try:
            pool.Add(fd_proto)
        except Exception:
            continue
        if fd_proto.name.startswith("google/protobuf/"):
            continue
        file_desc = pool.FindFileByName(fd_proto.name)
        for name, msg_desc in file_desc.message_types_by_name.items():
            classes[name] = message_factory.GetMessageClass(msg_desc)
    return classes
