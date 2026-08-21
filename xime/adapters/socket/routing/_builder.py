from __future__ import annotations

import inspect
import typing
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from xime.core.contract import (
    ENDPOINT_ATTR,
    DownloadStream,
    EndpointInfo,
    EndpointKind,
    UploadStream,
)
from xime.core.exception.framework import StartupException

if typing.TYPE_CHECKING:
    from xime.core.bootstrap.application import Application

EndpointShape = Literal["command", "upload", "download"]


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
            f"controller '{cls.__qualname__}' is defined inside a function. "
            f"Define the controller and its request/response models at module "
            f"level - annotations referencing names from a function's local "
            f"scope cannot be resolved at startup."
        )
    return (
        f"the annotation refers to a name that is not importable from module "
        f"'{cls.__module__}'. Define or import the referenced type at module level."
    )


@dataclass
class ResolvedEndpoint:
    """A fully-resolved endpoint ready for dispatch.

    Built once at startup from a controller method + its DI-resolved instance.
    Dựng một lần lúc startup từ method controller + instance DI.
    """

    info: EndpointInfo
    shape: EndpointShape
    bound: Any                      # method already bound to the DI instance
    request_type: type[BaseModel]   # inferred from the `request` parameter
    response_type: type | None      # inferred from return annotation (None for download)
    stream_param: str | None        # name of the UploadStream/DownloadStream param


class SocketEndpointBuilder:
    """Builds the endpoint dispatch table for one socket server.

    Mirrors the web RouteBuilder: read decorator metadata from each controller
    method, resolve its signature, and produce a lookup table keyed by endpoint
    name. Only controllers whose server_id matches this builder are included.
    Giống RouteBuilder của web: đọc metadata, phân giải chữ ký, dựng bảng tra cứu
    theo tên endpoint. Chỉ gồm controller khớp server_id.
    """

    def __init__(self, app: Application, server_id: str) -> None:
        self._app = app
        self._server_id = server_id

    def build(self, controllers: list[type]) -> dict[str, ResolvedEndpoint]:
        table: dict[str, ResolvedEndpoint] = {}

        for cls in controllers:
            if getattr(cls, "server_id", "default") != self._server_id:
                continue

            try:
                instance = self._app.get(cls)
            except KeyError:
                raise RuntimeError(
                    f"Socket controller '{cls.__name__}' is not registered in the "
                    f"DI container. Add its package to dependency.scan() in "
                    f"config/dependency.py."
                ) from None

            for attr_name, info in self._iter_endpoints(cls):
                bound = getattr(instance, attr_name)
                resolved = self._resolve(cls, attr_name, info, bound)
                if resolved.info.name in table:
                    raise StartupException(
                        f"\nDuplicate Socket Endpoint\n"
                        f"  Name  : {resolved.info.name}\n"
                        f"  Server: {self._server_id}\n"
                        f"  Hint  : each @command/@stream name must be unique per server."
                    )
                table[resolved.info.name] = resolved

        return table

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _iter_endpoints(self, cls: type) -> list[tuple[str, EndpointInfo]]:
        """Yield (method_name, EndpointInfo) in declaration order.

        Uses vars() + MRO traversal (reversed) to preserve declaration order,
        the same approach RouteBuilder uses.
        Dùng vars() + MRO (đảo) để giữ thứ tự khai báo, giống RouteBuilder.
        """
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
        self,
        cls: type,
        attr_name: str,
        info: EndpointInfo,
        bound: Any,
    ) -> ResolvedEndpoint:
        # The adapter invokes every handler with `await bound(...)`, so it must
        # be an `async def` coroutine function. A plain `def` - or an
        # `async def` with `yield` (async generator) - passes startup but crashes
        # at the first call. Fail fast, mirroring the code-first gRPC builder.
        # Adapter gọi handler bằng `await bound(...)` nên phải là async def. Viết
        # `def` (hoặc async generator) sẽ qua startup nhưng hỏng ở call đầu -
        # chặn sớm, giống builder gRPC code-first.
        if not inspect.iscoroutinefunction(bound):
            raise StartupException(
                self._err(
                    cls,
                    attr_name,
                    "endpoint handler must be an `async def` coroutine function "
                    "(a plain `def` or an `async def` with `yield` would crash at "
                    "the first call when the adapter awaits it)",
                )
            )
        hints = self._type_hints(cls, attr_name, bound)
        sig = inspect.signature(bound)   # 'self' already bound out

        request_type: type[BaseModel] | None = None
        stream_param: str | None = None
        shape: EndpointShape

        for param_name in sig.parameters:
            annotation = hints.get(param_name)
            if annotation is None:
                raise StartupException(
                    self._err(cls, attr_name, f"parameter '{param_name}' has no type hint")
                )
            if annotation is UploadStream:
                stream_param = param_name
            elif annotation is DownloadStream:
                stream_param = param_name
            else:
                if not self._is_basemodel(annotation):
                    raise StartupException(
                        self._err(
                            cls, attr_name,
                            f"parameter '{param_name}' must be a Pydantic BaseModel "
                            f"(got {annotation!r})",
                        )
                    )
                request_type = annotation

        if request_type is None:
            raise StartupException(
                self._err(cls, attr_name, "endpoint must have a `request: <BaseModel>` parameter")
            )

        return_type = hints.get("return")

        # Decide the concrete shape and validate it matches the decorator.
        # Quyết định shape cụ thể và kiểm tra khớp với decorator.
        if info.kind is EndpointKind.COMMAND:
            if stream_param is not None:
                raise StartupException(
                    self._err(cls, attr_name, "@command must not take an Upload/DownloadStream")
                )
            self._require_response(cls, attr_name, return_type)
            shape = "command"
        else:  # STREAM
            stream_annotation = hints.get(stream_param) if stream_param else None
            if stream_annotation is UploadStream:
                self._require_response(cls, attr_name, return_type)
                shape = "upload"
            elif stream_annotation is DownloadStream:
                shape = "download"
                return_type = None  # download streams return nothing meaningful
            else:
                raise StartupException(
                    self._err(
                        cls, attr_name,
                        "@stream must take exactly one UploadStream or DownloadStream parameter",
                    )
                )

        return ResolvedEndpoint(
            info=info,
            shape=shape,
            bound=bound,
            request_type=request_type,
            response_type=return_type,
            stream_param=stream_param,
        )

    @staticmethod
    def _type_hints(cls: type, attr_name: str, bound: Any) -> dict[str, Any]:
        try:
            return typing.get_type_hints(bound)
        except NameError as exc:
            raise StartupException(
                f"\nUnresolvable Type Annotation\n"
                f"  Controller: {cls.__name__}\n"
                f"  Endpoint  : {attr_name}\n"
                f"  Detail    : {exc}\n"
                f"  Hint      : {_unresolved_hint(cls)}"
            ) from exc
        except Exception as exc:
            raise StartupException(
                f"\nUnresolvable Type Annotation\n"
                f"  Controller: {cls.__name__}\n"
                f"  Endpoint  : {attr_name}\n"
                f"  Detail    : {exc}"
            ) from exc

    @staticmethod
    def _is_basemodel(annotation: Any) -> bool:
        return isinstance(annotation, type) and issubclass(annotation, BaseModel)

    def _require_response(self, cls: type, attr_name: str, return_type: Any) -> None:
        if not self._is_basemodel(return_type):
            raise StartupException(
                self._err(
                    cls, attr_name,
                    f"return type must be a Pydantic BaseModel (got {return_type!r})",
                )
            )

    @staticmethod
    def _err(cls: type, attr_name: str, detail: str) -> str:
        return (
            f"\nInvalid Socket Endpoint\n"
            f"  Controller: {cls.__name__}\n"
            f"  Endpoint  : {attr_name}\n"
            f"  Detail    : {detail}"
        )
