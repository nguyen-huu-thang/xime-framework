"""Code-First gRPC - generate .proto from Python controllers + DTOs.

Public API:
    from xime.adapters.grpc.codefirst import (
        configure_grpc_codefirst,
        generate, check,
        ProtoInt32, ProtoUInt64, ...,   # Annotated int-width overrides
    )

The serving glue (CodeFirstGrpcBuilder) and marshalling import grpc/protobuf, so
they are imported lazily where used (GrpcAdapter) - keeping plain generation
usable even where the grpc runtime is absent.
Glue serving import grpc/protobuf nên được import lười tại nơi dùng (GrpcAdapter).
"""

from ._config import (
    CodeFirstConfig,
    codefirst_registry,
    configure_grpc_codefirst,
)
from ._generator import (
    CheckResult,
    GenerateResult,
    build_proto_files,
    check,
    generate,
)
from ._type_map import (
    ProtoInt32,
    ProtoInt64,
    ProtoSInt32,
    ProtoSInt64,
    ProtoUInt32,
    ProtoUInt64,
    UnsupportedTypeError,
)

__all__ = [
    # Config
    "configure_grpc_codefirst",
    "CodeFirstConfig",
    "codefirst_registry",
    # Generation
    "generate",
    "check",
    "build_proto_files",
    "GenerateResult",
    "CheckResult",
    # Type overrides
    "ProtoInt32",
    "ProtoInt64",
    "ProtoUInt32",
    "ProtoUInt64",
    "ProtoSInt32",
    "ProtoSInt64",
    "UnsupportedTypeError",
]
