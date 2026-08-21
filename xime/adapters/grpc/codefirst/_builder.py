from __future__ import annotations

import collections.abc
import enum
import inspect
import typing
from typing import Annotated, Any

from pydantic import BaseModel

from xime.core.contract import (
    ENDPOINT_ATTR,
    DownloadStream,
    EndpointInfo,
    EndpointKind,
    UploadStream,
)
from xime.core.exception.framework import StartupException

from ._lock import LockFile
from ._model import (
    ContractModel,
    EnumContract,
    EnumValueContract,
    FieldContract,
    MessageContract,
    MethodContract,
    ServiceContract,
    StreamKind,
)
from ._stream_convention import (
    DOWNLOAD_CHUNK_FIELD,
    UPLOAD_CHUNK_FIELD,
    UPLOAD_METADATA_FIELD,
    download_wrapper_name,
    upload_wrapper_name,
)
from ._type_map import map_type, python_hint

# Return annotations accepted on a typed-stream handler. typing.AsyncIterator[X]
# and collections.abc.AsyncIterator[X] both report the abc as their origin.
# Annotation return chấp nhận cho handler stream có kiểu.
_ASYNC_ITER_ORIGINS = (
    collections.abc.AsyncIterator,
    collections.abc.AsyncIterable,
    collections.abc.AsyncGenerator,
)


def _unresolved_hint(cls: type) -> str:
    """Actionable explanation for a NameError raised by get_type_hints.

    The common cause is a controller (or its request/response models) defined
    inside a function: with ``from __future__ import annotations`` every hint is
    a string resolved later against the module globals only - the enclosing
    function's locals are gone, so the name cannot be found. There is no way to
    recover that scope, so we tell the developer to lift it to module level.
    Nguyên nhân thường gặp: controller định nghĩa trong local scope của hàm.
    """
    if "<locals>" in getattr(cls, "__qualname__", ""):
        return (
            f"controller '{cls.__qualname__}' is defined inside a function - "
            f"define it and its request/response models at module level; "
            f"annotations referencing a function's local scope cannot be "
            f"resolved at startup."
        )
    return (
        f"the annotation refers to a name not importable from module "
        f"'{cls.__module__}' - define or import the referenced type at module level."
    )


class _MessageRegistry:
    """Collects Pydantic models / enums referenced by a contract and turns them
    into MessageContract / EnumContract, assigning stable field numbers via the lock.

    map_type() calls register_message / register_enum on this object as it walks
    nested types, so the whole reachable graph is pulled in automatically.
    map_type gọi register_* khi duyệt type lồng nhau → kéo toàn bộ đồ thị.
    """

    def __init__(self, lock: LockFile) -> None:
        self._lock = lock
        self.messages: dict[str, MessageContract] = {}
        self.enums: dict[str, EnumContract] = {}
        self._pending: list[type] = []
        self._seen_models: set[type] = set()
        self._seen_enums: set[type] = set()
        # name → set of child message/enum names (for transitive shared detection)
        self.children: dict[str, set[str]] = {}
        self._current: str | None = None
        # "Message.field" → sidecar fidelity hint ("decimal" / "uuid" / "date")
        # "Message.field" → hint fidelity cho sidecar
        self.field_hints: dict[str, str] = {}

    # -- called by map_type -------------------------------------------------

    def register_message(self, model: type[BaseModel]) -> str:
        name = model.__name__
        if model not in self._seen_models:
            self._seen_models.add(model)
            self._pending.append(model)
        if self._current is not None:
            self.children.setdefault(self._current, set()).add(name)
        return name

    def register_enum(self, enum_cls: type[enum.Enum]) -> str:
        name = enum_cls.__name__
        if enum_cls not in self._seen_enums:
            self._seen_enums.add(enum_cls)
            self.enums[name] = self._build_enum(enum_cls)
        if self._current is not None:
            self.children.setdefault(self._current, set()).add(name)
        return name

    # -- driving ------------------------------------------------------------

    def process_pending(self) -> None:
        """Build MessageContract for every queued model (which may queue more)."""
        while self._pending:
            model = self._pending.pop(0)
            self.messages[model.__name__] = self._build_message(model)

    def add_message(self, message: MessageContract, children: set[str]) -> None:
        """Add a manually-built message (e.g. a stream chunk wrapper)."""
        self.messages[message.name] = message
        if children:
            self.children.setdefault(message.name, set()).update(children)

    # -- internals ----------------------------------------------------------

    def _build_message(self, model: type[BaseModel]) -> MessageContract:
        self._current = model.__name__
        try:
            field_specs: dict[str, tuple[str, bool]] = {}
            py_fields: list[str] = []
            for fname, finfo in model.model_fields.items():
                # Pydantic v2 strips Annotated, moving extras to finfo.metadata.
                # Re-wrap so map_type sees ProtoInt32 etc. again.
                # Pydantic v2 tách Annotated, đẩy extras vào finfo.metadata - dựng lại.
                annotation = finfo.annotation
                if finfo.metadata:
                    annotation = Annotated[(annotation, *finfo.metadata)]
                proto_type, optional = map_type(annotation, self)
                field_specs[fname] = (proto_type, optional)
                py_fields.append(fname)
                hint = python_hint(annotation)
                if hint is not None:
                    self.field_hints[f"{model.__name__}.{fname}"] = hint
        finally:
            self._current = None

        numbers = self._lock.assign_numbers(model.__name__, py_fields)
        record = self._lock.messages[model.__name__]
        fields = [
            FieldContract(
                name=f,
                proto_type=field_specs[f][0],
                number=numbers[f],
                optional=field_specs[f][1],
            )
            for f in py_fields
        ]
        return MessageContract(
            name=model.__name__,
            fields=fields,
            reserved_numbers=list(record.reserved_numbers),
            reserved_names=list(record.reserved_names),
        )

    def _build_enum(self, enum_cls: type[enum.Enum]) -> EnumContract:
        members = [(m.name, int(m.value)) for m in enum_cls]
        # proto3 requires a 0-value member (the default / "unspecified"). We
        # require the developer's own enum to define it rather than silently
        # injecting one: otherwise a cross-language peer that leaves the field
        # unset sends 0 on the wire, which deserializes back to a value the
        # Python enum has no member for and fails Pydantic validation. Failing
        # at generate time keeps the source enum, the .proto and every generated
        # SDK in agreement.
        # proto3 cần member giá trị 0. Bắt enum của developer tự khai báo thay vì
        # tự chèn ngầm: nếu không, peer khác ngôn ngữ để field trống sẽ gửi 0,
        # giải mã về giá trị enum Python không có → Pydantic validate lỗi. Báo lỗi
        # lúc generate để enum gốc, .proto và mọi SDK sinh ra luôn khớp nhau.
        if not any(v == 0 for _, v in members):
            raise StartupException(
                f"\nInvalid Enum for proto mapping\n"
                f"  Enum  : {enum_cls.__name__}\n"
                f"  Detail: proto3 requires a member with value 0 (the default / "
                f"\"unspecified\" value).\n"
                f"          Without it, a peer that leaves the field unset sends 0 "
                f"on the wire, which\n"
                f"          deserializes back to an invalid value and fails "
                f"validation.\n"
                f"  Fix   : add a zero member, e.g. "
                f"`{enum_cls.__name__.upper()}_UNSPECIFIED = 0`."
            )
        # Keep the zero member first (proto3 convention), preserve the rest.
        # Đưa member 0 lên đầu (quy ước proto3), giữ nguyên phần còn lại.
        ordered = [m for m in members if m[1] == 0] + [m for m in members if m[1] != 0]
        return EnumContract(
            name=enum_cls.__name__,
            values=[EnumValueContract(name=n, number=v) for n, v in ordered],
        )


class ContractBuilder:
    """Scans controllers for one server_id and builds the ContractModel IR.

    Mirrors the socket SocketEndpointBuilder for signature resolution, but emits
    a transport-neutral IR consumed by the proto emitter and serving glue.
    Giống SocketEndpointBuilder về phân giải chữ ký, nhưng sinh IR trung lập.
    """

    def __init__(self, server_id: str, lock: LockFile) -> None:
        self._server_id = server_id
        self._lock = lock

    def build(self, controllers: list[type]) -> ContractModel:
        registry = _MessageRegistry(self._lock)
        services: list[ServiceContract] = []

        for cls in controllers:
            if getattr(cls, "server_id", "default") != self._server_id:
                continue
            services.append(self._build_service(cls, registry))

        registry.process_pending()

        references = self._compute_references(services, registry)

        return ContractModel(
            server_id=self._server_id,
            services=services,
            messages=registry.messages,
            enums=registry.enums,
            references=references,
            field_hints=registry.field_hints,
        )

    # ------------------------------------------------------------------
    # Service / method
    # ------------------------------------------------------------------

    def _build_service(self, cls: type, registry: _MessageRegistry) -> ServiceContract:
        methods: list[MethodContract] = []
        for attr_name, info in self._iter_endpoints(cls):
            func = getattr(cls, attr_name)
            methods.append(self._build_method(cls, attr_name, info, func, registry))

        return ServiceContract(
            name=cls.__name__,
            server_id=self._server_id,
            proto_file=self._proto_file(cls.__name__),
            methods=methods,
            controller=cls,
        )

    def _build_method(
        self,
        cls: type,
        attr_name: str,
        info: EndpointInfo,
        func: Any,
        registry: _MessageRegistry,
    ) -> MethodContract:
        request_type, response_type, stream_kind, stream_param = self._resolve(
            cls, attr_name, info, func
        )
        rpc_name = self._rpc_name(info.name)

        request_msg = registry.register_message(request_type)

        if stream_kind is StreamKind.UNARY:
            response_msg = registry.register_message(response_type)  # type: ignore[arg-type]
            return MethodContract(
                rpc_name, request_msg, response_msg, stream_kind,
                handler_attr=attr_name, request_py=request_type, response_py=response_type,
                endpoint_name=info.name,
            )

        if stream_kind is StreamKind.CLIENT_STREAM:
            response_msg = registry.register_message(response_type)  # type: ignore[arg-type]
            wrapper = upload_wrapper_name(rpc_name)
            registry.add_message(
                MessageContract(
                    name=wrapper,
                    fields=[
                        FieldContract("metadata", request_msg, UPLOAD_METADATA_FIELD, oneof="payload"),
                        FieldContract("chunk", "bytes", UPLOAD_CHUNK_FIELD, oneof="payload"),
                    ],
                ),
                children={request_msg},
            )
            # Streamed request = wrapper; response stays unary.
            # Request stream là wrapper; response vẫn unary.
            return MethodContract(
                rpc_name, wrapper, response_msg, StreamKind.CLIENT_STREAM,
                handler_attr=attr_name, stream_param=stream_param,
                request_py=request_type, response_py=response_type,
                endpoint_name=info.name,
            )

        if stream_kind is StreamKind.SERVER_STREAM_TYPED:
            # No wrapper: the yielded model IS the streamed message, so the
            # response side of the rpc is an ordinary DTO. That is what makes
            # `rpc Watch(Req) returns (stream Resp)` readable to a Java peer.
            # Không wrapper: model yield ra CHÍNH LÀ message của stream.
            response_msg = registry.register_message(response_type)  # type: ignore[arg-type]
            return MethodContract(
                rpc_name, request_msg, response_msg, StreamKind.SERVER_STREAM_TYPED,
                handler_attr=attr_name, request_py=request_type, response_py=response_type,
                endpoint_name=info.name,
            )

        # SERVER_STREAM (byte download)
        wrapper = download_wrapper_name(rpc_name)
        registry.add_message(
            MessageContract(
                name=wrapper,
                fields=[FieldContract("chunk", "bytes", DOWNLOAD_CHUNK_FIELD)],
            ),
            children=set(),
        )
        return MethodContract(
            rpc_name, request_msg, wrapper, StreamKind.SERVER_STREAM,
            handler_attr=attr_name, stream_param=stream_param,
            request_py=request_type, response_py=None,
            endpoint_name=info.name,
        )

    # ------------------------------------------------------------------
    # Signature resolution (no DI - works on the class)
    # ------------------------------------------------------------------

    def _iter_endpoints(self, cls: type) -> list[tuple[str, EndpointInfo]]:
        seen: set[str] = set()
        result: list[tuple[str, EndpointInfo]] = []
        for klass in reversed(cls.__mro__):
            for attr_name, val in vars(klass).items():
                if attr_name in seen or not inspect.isfunction(val):
                    continue
                seen.add(attr_name)
                # Resolve metadata from the most-derived definition so an
                # overriding subclass controls its own @command/@stream info.
                # Lấy metadata từ định nghĩa dẫn xuất nhất để subclass override quyết.
                info: EndpointInfo | None = getattr(
                    getattr(cls, attr_name, None), ENDPOINT_ATTR, None
                )
                if info is not None:
                    result.append((attr_name, info))
        return result

    def _resolve(
        self, cls: type, attr_name: str, info: EndpointInfo, func: Any
    ) -> tuple[type[BaseModel], type | None, StreamKind, str]:
        # Handlers come in two shapes and the serving glue calls them
        # differently: a coroutine function is awaited once, an async generator
        # is iterated (typed server stream). Anything else - a plain `def` -
        # would start fine but crash at the first RPC with "object NoneType
        # can't be used in 'await' expression". Fail fast.
        # Handler có hai dạng, glue gọi khác nhau: coroutine thì `await` một
        # lần, async generator thì lặp (stream có kiểu). Dạng khác - `def`
        # thường - qua được startup nhưng crash ở RPC đầu tiên.
        is_async_gen = inspect.isasyncgenfunction(func)
        if not inspect.iscoroutinefunction(func) and not is_async_gen:
            raise StartupException(
                self._err(
                    cls,
                    attr_name,
                    "endpoint handler must be an `async def` coroutine function "
                    "(or, for a typed server stream, an `async def` with `yield` "
                    "returning AsyncIterator[<BaseModel>]); a plain `def` would "
                    "crash at the first RPC when the server awaits it",
                )
            )
        try:
            hints = typing.get_type_hints(func)
        except NameError as exc:
            raise StartupException(
                self._err(cls, attr_name, f"unresolvable annotation: {exc}. {_unresolved_hint(cls)}")
            ) from exc
        except Exception as exc:
            raise StartupException(self._err(cls, attr_name, f"unresolvable annotation: {exc}")) from exc
        return_type = hints.pop("return", None)

        sig = inspect.signature(func)
        request_type: type[BaseModel] | None = None
        stream_param_type: type | None = None
        stream_param_name: str = ""

        for param_name in sig.parameters:
            if param_name == "self":
                continue
            annotation = hints.get(param_name)
            if annotation is None:
                raise StartupException(self._err(cls, attr_name, f"parameter '{param_name}' has no type hint"))
            if annotation is UploadStream or annotation is DownloadStream:
                stream_param_type = annotation
                stream_param_name = param_name
            elif self._is_basemodel(annotation):
                request_type = annotation
            else:
                raise StartupException(
                    self._err(cls, attr_name, f"parameter '{param_name}' must be a BaseModel (got {annotation!r})")
                )

        if request_type is None:
            raise StartupException(self._err(cls, attr_name, "endpoint must have a `request: <BaseModel>` parameter"))

        if info.kind is EndpointKind.COMMAND:
            if stream_param_type is not None:
                raise StartupException(self._err(cls, attr_name, "@command must not take an Upload/DownloadStream"))
            if is_async_gen:
                raise StartupException(
                    self._err(
                        cls, attr_name,
                        "@command must return one response, so it cannot be an async "
                        "generator - use @stream for a typed server stream",
                    )
                )
            self._require_response(cls, attr_name, return_type)
            return request_type, return_type, StreamKind.UNARY, ""

        # @stream
        if stream_param_type is not None and is_async_gen:
            raise StartupException(
                self._err(
                    cls, attr_name,
                    f"@stream takes either an {stream_param_type.__name__} parameter or "
                    "`yield` (typed stream), not both",
                )
            )
        if stream_param_type is UploadStream:
            self._require_response(cls, attr_name, return_type)
            return request_type, return_type, StreamKind.CLIENT_STREAM, stream_param_name
        if stream_param_type is DownloadStream:
            return request_type, None, StreamKind.SERVER_STREAM, stream_param_name
        if is_async_gen:
            # Typed server stream: the yielded model comes from the return
            # annotation, the only place it is written down.
            # Stream có kiểu: model lấy từ annotation return - chỗ duy nhất khai.
            yielded = self._yielded_model(cls, attr_name, return_type)
            return request_type, yielded, StreamKind.SERVER_STREAM_TYPED, ""
        raise StartupException(
            self._err(
                cls, attr_name,
                "@stream must take exactly one UploadStream or DownloadStream parameter, "
                "or `yield` models (typed server stream: `async def ... -> "
                "AsyncIterator[<BaseModel>]` with `yield`)",
            )
        )

    def _yielded_model(self, cls: type, attr_name: str, return_type: Any) -> type[BaseModel]:
        """Extract Resp from AsyncIterator[Resp] on a typed-stream handler."""
        origin = typing.get_origin(return_type)
        args = typing.get_args(return_type)
        if origin in _ASYNC_ITER_ORIGINS and args and self._is_basemodel(args[0]):
            return args[0]  # type: ignore[no-any-return]
        raise StartupException(
            self._err(
                cls, attr_name,
                f"a typed server stream must be annotated `-> AsyncIterator[<BaseModel>]` "
                f"(got {return_type!r}). The yielded model is the streamed message, so "
                f"the generator cannot be built without it.",
            )
        )

    # ------------------------------------------------------------------
    # Shared-message detection
    # ------------------------------------------------------------------

    def _compute_references(
        self, services: list[ServiceContract], registry: _MessageRegistry
    ) -> dict[str, set[str]]:
        """For each message/enum name, the set of proto file stems that reach it.

        Reachability is transitive through message fields, so a nested message
        used by two services lands in common.proto.
        Tính khả đạt bắc cầu qua field → message lồng dùng bởi 2 service vào common.
        """
        references: dict[str, set[str]] = {}
        for service in services:
            stem = self._stem(service.proto_file)
            roots: set[str] = set()
            for method in service.methods:
                roots.add(method.request_message)
                roots.add(method.response_message)
            for name in self._reachable(roots, registry):
                references.setdefault(name, set()).add(stem)
        return references

    @staticmethod
    def _reachable(roots: set[str], registry: _MessageRegistry) -> set[str]:
        seen: set[str] = set()
        stack = list(roots)
        while stack:
            name = stack.pop()
            if name in seen:
                continue
            seen.add(name)
            stack.extend(registry.children.get(name, set()))
        return seen

    # ------------------------------------------------------------------
    # Naming helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _proto_file(controller_name: str) -> str:
        stem = controller_name
        if stem.endswith("Controller"):
            stem = stem[: -len("Controller")]
        return f"{ContractBuilder._snake(stem)}.proto"

    @staticmethod
    def _stem(proto_file: str) -> str:
        return proto_file[:-len(".proto")] if proto_file.endswith(".proto") else proto_file

    @staticmethod
    def _snake(name: str) -> str:
        out: list[str] = []
        for i, ch in enumerate(name):
            if ch.isupper() and i > 0 and not name[i - 1].isupper():
                out.append("_")
            out.append(ch.lower())
        return "".join(out)

    @staticmethod
    def _rpc_name(endpoint_name: str) -> str:
        return "".join(part[:1].upper() + part[1:] for part in endpoint_name.split("_") if part)

    @staticmethod
    def _is_basemodel(annotation: Any) -> bool:
        return isinstance(annotation, type) and issubclass(annotation, BaseModel)

    def _require_response(self, cls: type, attr_name: str, return_type: Any) -> None:
        if not self._is_basemodel(return_type):
            raise StartupException(
                self._err(cls, attr_name, f"return type must be a BaseModel (got {return_type!r})")
            )

    @staticmethod
    def _err(cls: type, attr_name: str, detail: str) -> str:
        return (
            f"\nInvalid gRPC Endpoint\n"
            f"  Controller: {cls.__name__}\n"
            f"  Endpoint  : {attr_name}\n"
            f"  Detail    : {detail}"
        )
