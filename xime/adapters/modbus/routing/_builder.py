from __future__ import annotations

import inspect
import typing
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import TYPE_CHECKING, Any

from xime.core.exception.framework import StartupException

from .._decorators import MODBUS_ATTR, ModbusHandlerInfo, ModbusKind
from .._model import DeviceInfo, ModbusField, get_device_info

if TYPE_CHECKING:
    from xime.core.bootstrap.application import Application

# Interval used when a model is only watched via @on_change and nobody said how
# often to read it. One second is the usual dashboard cadence and is slow enough
# not to hammer a PLC by accident.
# Nhịp mặc định khi model chỉ có @on_change mà không ai nói đọc bao lâu một lần.
DEFAULT_POLL_INTERVAL = 1.0

# Tên tham số handler khai để nhận tên THỰC THỂ đang được xử lý. Khớp theo tên,
# đúng quy ước `topic` của `@subscribe` - một hằng chứ không phải chuỗi rải rác,
# vì nó là một phần hợp đồng công khai.
DEVICE_PARAM = "device"


@dataclass
class ResolvedPoll:
    """A @poll handler bound to its DI instance."""

    bound: Any
    controller: str
    handler: str
    wants_device: bool = False


@dataclass
class ResolvedChangeWatch:
    """An @on_change handler plus the field it watches."""

    field: ModbusField
    bound: Any
    controller: str
    handler: str
    deadband: float | None = None
    wants_device: bool = False


@dataclass
class PollGroup:
    """One read loop: a model, a cadence, and everyone interested in it.

    Grouping is what stops two handlers on the same model and interval from
    causing two reads of the same device.
    Gom nhóm để hai handler cùng model, cùng nhịp không gây hai lần đọc.
    """

    model: type
    device_info: DeviceInfo
    interval: float
    polls: list[ResolvedPoll] = dataclass_field(default_factory=list)
    watches: list[ResolvedChangeWatch] = dataclass_field(default_factory=list)

    @property
    def key(self) -> tuple[Any, float]:
        return (self.model, self.interval)

    def __repr__(self) -> str:
        return (
            f"PollGroup({self.model.__name__}, every {self.interval}s, "
            f"{len(self.polls)} poll(s), {len(self.watches)} watch(es))"
        )


class ModbusRouteBuilder:
    """Builds the poll table from scanned controllers.

    Mirrors MqttRouteBuilder: read the decorator metadata, resolve each method
    against its DI singleton, fail fast on misuse, and return the groups the
    adapter will run.
    """

    def __init__(self, app: Application) -> None:
        self._app = app

    def build(self, controllers: list[type]) -> list[PollGroup]:
        groups: dict[tuple[Any, float], PollGroup] = {}
        pending_watches: list[tuple[type, ResolvedChangeWatch]] = []

        for cls in controllers:
            instance = self._instance_of(cls)
            for attr_name, info in self._iter_handlers(cls):
                bound = getattr(instance, attr_name)
                self._check_coroutine(cls, attr_name, bound)

                if info.kind is ModbusKind.POLL:
                    self._add_poll(groups, cls, attr_name, info, bound)
                elif info.kind is ModbusKind.ON_CHANGE:
                    watch = self._resolve_watch(cls, attr_name, info, bound)
                    pending_watches.append((cls, watch))
                # SERVE / ON_WRITE belong to slave mode; the server builder
                # picks those up from the same metadata.

        # Watches are attached after every @poll is known, so each one can join
        # the FASTEST existing loop for its model instead of forcing an extra
        # read at a cadence nobody asked for.
        # Gắn watch sau khi biết hết @poll để chọn vòng NHANH NHẤT của model.
        for cls, watch in pending_watches:
            self._attach_watch(groups, cls, watch)

        return list(groups.values())

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _add_poll(
        self,
        groups: dict,
        cls: type,
        attr_name: str,
        info: ModbusHandlerInfo,
        bound: Any,
    ) -> None:
        model = info.model
        device_info = self._require_model(cls, attr_name, model)
        interval = info.interval if info.interval is not None else DEFAULT_POLL_INTERVAL
        if interval <= 0:
            raise StartupException(
                self._err(cls, attr_name, f"interval must be > 0 (got {interval})")
            )
        wants_device = self._check_signature(cls, attr_name, bound, expected=model)

        key = (model, interval)
        group = groups.get(key)
        if group is None:
            group = PollGroup(model, device_info, interval)  # type: ignore[arg-type]
            groups[key] = group
        group.polls.append(
            ResolvedPoll(bound, cls.__name__, attr_name, wants_device)
        )

    def _resolve_watch(
        self, cls: type, attr_name: str, info: ModbusHandlerInfo, bound: Any
    ) -> ResolvedChangeWatch:
        field = info.field
        if not isinstance(field, ModbusField):
            raise StartupException(
                self._err(
                    cls, attr_name,
                    "@on_change needs a device model field, e.g. "
                    "@on_change(Inverter.fault_code)",
                )
            )
        if info.deadband is not None and info.deadband < 0:
            raise StartupException(
                self._err(cls, attr_name, f"deadband must be >= 0 (got {info.deadband})")
            )
        wants_device = self._check_signature(cls, attr_name, bound, expected=None)
        return ResolvedChangeWatch(
            field, bound, cls.__name__, attr_name, info.deadband, wants_device
        )

    def _attach_watch(
        self, groups: dict, cls: type, watch: ResolvedChangeWatch
    ) -> None:
        owner = watch.field._owner_info
        if owner is None:
            raise StartupException(
                self._err(
                    cls, watch.handler,
                    f"field '{watch.field.name}' does not belong to a @device model",
                )
            )

        candidates = [
            group for group in groups.values() if group.model is owner.cls
        ]
        if candidates:
            target = min(candidates, key=lambda g: g.interval)
        else:
            # Nobody polls this model, so the watch becomes its own loop.
            key = (owner.cls, DEFAULT_POLL_INTERVAL)
            target = groups.get(key)
            if target is None:
                target = PollGroup(owner.cls, owner, DEFAULT_POLL_INTERVAL)
                groups[key] = target
        target.watches.append(watch)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _instance_of(self, cls: type) -> Any:
        try:
            return self._app.get(cls)
        except KeyError:
            raise StartupException(
                f"\nModbus controller not in the DI container\n"
                f"  Controller: {cls.__name__}\n"
                f"  Fix       : add its package to dependency.scan() in "
                f"config/dependency.py."
            ) from None

    @staticmethod
    def _iter_handlers(cls: type) -> list[tuple[str, ModbusHandlerInfo]]:
        seen: set[str] = set()
        result: list[tuple[str, ModbusHandlerInfo]] = []
        for klass in reversed(cls.__mro__):
            for attr_name, val in vars(klass).items():
                if attr_name in seen or not inspect.isfunction(val):
                    continue
                seen.add(attr_name)
                info = getattr(getattr(cls, attr_name, None), MODBUS_ATTR, None)
                if info is not None:
                    result.append((attr_name, info))
        return result

    def _check_coroutine(self, cls: type, attr_name: str, bound: Any) -> None:
        if not inspect.iscoroutinefunction(bound):
            raise StartupException(
                self._err(cls, attr_name, "handler must be an `async def` coroutine function")
            )

    def _require_model(self, cls: type, attr_name: str, model: Any) -> DeviceInfo:
        info = get_device_info(model) if isinstance(model, type) else None
        if info is None:
            name = getattr(model, "__name__", repr(model))
            raise StartupException(
                self._err(
                    cls, attr_name,
                    f"'{name}' is not a device model. Decorate it with "
                    f"@device(unit=...) from xime.adapters.modbus.",
                )
            )
        return info

    def _check_signature(
        self, cls: type, attr_name: str, bound: Any, *, expected: type | None
    ) -> bool:
        """Check the handler signature; say whether it asked for `device`.

        A handler takes the model (or the new value), and MAY take a second
        parameter named exactly `device` to learn which entity of its kind this
        call is about - matched BY NAME, the same convention `@subscribe` uses
        for `topic`.
        Handler nhận model (hoặc giá trị mới), và **được phép** nhận thêm một
        tham số tên đúng `device` để biết lời gọi này thuộc thực thể nào - khớp
        theo TÊN, đúng quy ước `topic` của `@subscribe`.

        ⚠ Tên phải khớp chính xác. Một tham số thứ hai mang tên khác là **lỗi
        khởi động**, không phải một tham số bị bỏ qua im lặng: người viết đang
        chờ framework truyền một thứ mà framework không biết là gì.
        """
        params = [
            p for p in inspect.signature(bound).parameters.values()
            if p.kind
            in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        ]
        wants_device = len(params) == 2 and params[1].name == DEVICE_PARAM
        if len(params) != 1 and not wants_device:
            what = "the polled model" if expected else "the new value"
            raise StartupException(
                self._err(
                    cls, attr_name,
                    f"handler takes {what}, plus an optional parameter named "
                    f"'{DEVICE_PARAM}'; got {[p.name for p in params]}",
                )
            )
        if expected is None:
            return wants_device

        # If the parameter is annotated, it has to be the model being polled -
        # a mismatch here means the handler will get an object it does not
        # expect, and that is much cheaper to catch now than at 3 a.m.
        # Annotation lệch model = handler nhận nhầm object, bắt ngay lúc startup.
        try:
            hints = typing.get_type_hints(bound)
        except Exception:
            # unresolvable annotation: not worth failing startup over
            return wants_device
        annotation = hints.get(params[0].name)
        if annotation is not None and annotation is not expected:
            raise StartupException(
                self._err(
                    cls, attr_name,
                    f"parameter '{params[0].name}' is annotated "
                    f"{getattr(annotation, '__name__', annotation)!r} but the "
                    f"handler polls {expected.__name__}",
                )
            )
        return wants_device

    @staticmethod
    def _err(cls: type, attr_name: str, detail: str) -> str:
        return (
            f"\nInvalid Modbus Handler\n"
            f"  Controller: {cls.__name__}\n"
            f"  Handler   : {attr_name}\n"
            f"  Detail    : {detail}"
        )
