from __future__ import annotations

import inspect
import typing
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from xime.core.exception.framework import StartupException

from .._decorators import MQTT_ATTR, MqttHandlerInfo, MqttKind
from .._topic import is_valid_filter

if TYPE_CHECKING:
    from xime.core.bootstrap.application import Application

# Parameter names a @subscribe handler may declare; the adapter fills whichever
# are present. Matching by name keeps the contract explicit and predictable.
# Tên tham số mà handler @subscribe có thể khai báo; adapter điền cái nào có.
_SUBSCRIBE_PARAMS = ("payload", "topic", "message")


@dataclass
class ResolvedMqttRoute:
    """A fully-resolved MQTT route ready for dispatch.

    Built once at startup from a controller method + its DI-resolved instance.
    """

    info: MqttHandlerInfo
    bound: Any                              # method already bound to the DI instance
    # MQTT v5 Subscription Identifier assigned by the adapter at start; lets the
    # broker tell us exactly which route matched (avoids double-dispatch on
    # overlapping filters). None until assigned.
    # Subscription Identifier (MQTT v5) do adapter gán lúc start - broker báo đúng
    # route nào khớp, tránh double-dispatch khi filter chồng lấn.
    subscription_id: int | None = None
    # SUBSCRIBE: subset of _SUBSCRIBE_PARAMS present in the signature.
    subscribe_params: tuple[str, ...] = ()
    # RPC: inferred request/response models.
    request_type: type[BaseModel] | None = None
    response_type: type[BaseModel] | None = None
    # RPC: whether the handler also wants the topic injected.
    wants_topic: bool = False
    request_param: str = "request"


class MqttRouteBuilder:
    """Builds the MQTT dispatch table for one client from scanned controllers.

    Mirrors SocketEndpointBuilder: read @subscribe/@rpc metadata, resolve the
    signature, fail-fast on misuse, and return the list of routes.
    """

    def __init__(self, app: Application) -> None:
        self._app = app

    def build(self, controllers: list[type]) -> list[ResolvedMqttRoute]:
        routes: list[ResolvedMqttRoute] = []
        seen_filters: set[str] = set()

        for cls in controllers:
            try:
                instance = self._app.get(cls)
            except KeyError:
                raise RuntimeError(
                    f"MQTT controller '{cls.__name__}' is not registered in the "
                    f"DI container. Add its package to dependency.scan() in "
                    f"config/dependency.py."
                ) from None

            for attr_name, info in self._iter_handlers(cls):
                bound = getattr(instance, attr_name)
                route = self._resolve(cls, attr_name, info, bound)
                if info.topic in seen_filters:
                    raise StartupException(
                        f"\nDuplicate MQTT Topic Filter\n"
                        f"  Filter: {info.topic}\n"
                        f"  Why   : each route gets its own MQTT v5 Subscription\n"
                        f"          Identifier, but subscribing the SAME filter\n"
                        f"          twice makes the broker REPLACE the earlier\n"
                        f"          subscription (only the last id survives), so two\n"
                        f"          handlers on an identical filter cannot both fire.\n"
                        f"  Fix   : use distinct/overlapping filters (e.g. add a '+'\n"
                        f"          level) - the dispatcher fans out to all matching\n"
                        f"          routes - or merge the two handlers into one."
                    )
                seen_filters.add(info.topic)
                routes.append(route)

        return routes

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _iter_handlers(self, cls: type) -> list[tuple[str, MqttHandlerInfo]]:
        seen: set[str] = set()
        result: list[tuple[str, MqttHandlerInfo]] = []
        for klass in reversed(cls.__mro__):
            for attr_name, val in vars(klass).items():
                if attr_name in seen or not inspect.isfunction(val):
                    continue
                seen.add(attr_name)
                info: MqttHandlerInfo | None = getattr(
                    getattr(cls, attr_name, None), MQTT_ATTR, None
                )
                if info is not None:
                    result.append((attr_name, info))
        return result

    def _resolve(
        self, cls: type, attr_name: str, info: MqttHandlerInfo, bound: Any
    ) -> ResolvedMqttRoute:
        if not inspect.iscoroutinefunction(bound):
            raise StartupException(
                self._err(cls, attr_name, "handler must be an `async def` coroutine function")
            )
        if not is_valid_filter(info.topic):
            raise StartupException(
                self._err(cls, attr_name, f"invalid MQTT topic filter: {info.topic!r}")
            )
        if info.qos not in (0, 1, 2):
            raise StartupException(
                self._err(cls, attr_name, f"qos must be 0, 1 or 2 (got {info.qos})")
            )

        hints = self._type_hints(cls, attr_name, bound)
        sig = inspect.signature(bound)
        param_names = list(sig.parameters)

        if info.kind is MqttKind.SUBSCRIBE:
            return self._resolve_subscribe(cls, attr_name, info, bound, param_names)
        return self._resolve_rpc(cls, attr_name, info, bound, sig, hints)

    def _resolve_subscribe(
        self, cls, attr_name, info, bound, param_names
    ) -> ResolvedMqttRoute:
        unknown = [p for p in param_names if p not in _SUBSCRIBE_PARAMS]
        if unknown:
            raise StartupException(
                self._err(
                    cls, attr_name,
                    f"@subscribe handler may only declare {list(_SUBSCRIBE_PARAMS)}; "
                    f"got unexpected parameter(s) {unknown}",
                )
            )
        present = tuple(p for p in _SUBSCRIBE_PARAMS if p in param_names)
        return ResolvedMqttRoute(info=info, bound=bound, subscribe_params=present)

    def _resolve_rpc(self, cls, attr_name, info, bound, sig, hints) -> ResolvedMqttRoute:
        request_type: type[BaseModel] | None = None
        request_param = "request"
        wants_topic = False

        for param_name in sig.parameters:
            if param_name == "topic":
                wants_topic = True
                continue
            annotation = hints.get(param_name)
            if annotation is None:
                raise StartupException(
                    self._err(cls, attr_name, f"parameter '{param_name}' has no type hint")
                )
            if self._is_basemodel(annotation):
                if request_type is not None:
                    raise StartupException(
                        self._err(cls, attr_name, "@rpc handler must take exactly one request model")
                    )
                request_type = annotation
                request_param = param_name
            else:
                raise StartupException(
                    self._err(
                        cls, attr_name,
                        f"parameter '{param_name}' must be a Pydantic BaseModel "
                        f"(got {annotation!r})",
                    )
                )

        if request_type is None:
            raise StartupException(
                self._err(cls, attr_name, "@rpc handler must have a `request: <BaseModel>` parameter")
            )

        return_type = hints.get("return")
        if not self._is_basemodel(return_type):
            raise StartupException(
                self._err(
                    cls, attr_name,
                    f"@rpc return type must be a Pydantic BaseModel (got {return_type!r})",
                )
            )

        return ResolvedMqttRoute(
            info=info,
            bound=bound,
            request_type=request_type,
            response_type=return_type,
            wants_topic=wants_topic,
            request_param=request_param,
        )

    @staticmethod
    def _type_hints(cls: type, attr_name: str, bound: Any) -> dict[str, Any]:
        try:
            return typing.get_type_hints(bound)
        except Exception as exc:
            raise StartupException(
                f"\nUnresolvable Type Annotation\n"
                f"  Controller: {cls.__name__}\n"
                f"  Handler   : {attr_name}\n"
                f"  Detail    : {exc}"
            ) from exc

    @staticmethod
    def _is_basemodel(annotation: Any) -> bool:
        return isinstance(annotation, type) and issubclass(annotation, BaseModel)

    @staticmethod
    def _err(cls: type, attr_name: str, detail: str) -> str:
        return (
            f"\nInvalid MQTT Handler\n"
            f"  Controller: {cls.__name__}\n"
            f"  Handler   : {attr_name}\n"
            f"  Detail    : {detail}"
        )
