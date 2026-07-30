"""Slave mode: Xime answering masters instead of asking devices.

Same device models, opposite direction. A controller declares what it serves
and what it accepts:

    class PlcEmulator:
        @serve(Inverter)
        async def provide(self) -> Inverter:
            return Inverter(voltage=self._voltage, run_state=self._running)

        @on_write(Inverter.run_state)
        async def handle_command(self, value: bool) -> None:
            self._running = value

Two mechanisms, chosen for different reasons:

* **Serving values is a push on a timer.** The framework calls @serve handlers
  every `refresh` seconds, encodes the returned model and stores it. Pulling on
  every master request would mean running business code inside pymodbus'
  register-access hook, where a slow handler stalls the protocol reply.
  Đẩy theo nhịp thay vì hỏi lúc master đọc: handler chậm sẽ làm nghẽn phản hồi.

* **Accepting writes is a hook.** There is no other moment to learn that a
  master wrote something, so @on_write runs from the access callback.

Units are kept apart: each @device(unit=N) becomes its own SimDevice, so one
Xime process can present itself as several devices behind one port, the way an
RTU gateway does.
Mỗi @device(unit=N) là một SimDevice riêng - một tiến trình Xime đóng vai nhiều
thiết bị sau một cổng, giống gateway RTU.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import TYPE_CHECKING, Any

from xime.core.context import request_context
from xime.core.exception.framework import StartupException
from xime.core.security import clear_security

from ._codec import decode_field, encode_field
from ._config import ModbusServerConfig, modbus_registry
from ._decorators import MODBUS_ATTR, ModbusHandlerInfo, ModbusKind
from ._model import Area, DeviceInfo, ModbusField, get_device_info
from .routing._scanner import ModbusControllerScanner

if TYPE_CHECKING:
    from xime.core.bootstrap.application import Application

logger = logging.getLogger("xime.modbus.server")

# Modbus function codes that write, grouped by the area they touch.
_WRITE_COIL_CODES = frozenset({5, 15})
_WRITE_REGISTER_CODES = frozenset({6, 16})

# Function code -> the area it addresses, for routing an access callback.
_CODE_AREAS: dict[int, Area] = {
    1: Area.COIL, 5: Area.COIL, 15: Area.COIL,
    2: Area.DISCRETE,
    3: Area.HOLDING, 6: Area.HOLDING, 16: Area.HOLDING,
    4: Area.INPUT,
}


@dataclass
class ServedModel:
    """One model this process exposes, plus the handlers around it."""

    info: DeviceInfo
    provider: Any = None                       # bound @serve method
    provider_name: str = ""
    writers: dict[str, Any] = dataclass_field(default_factory=dict)  # field name -> bound
    writer_names: dict[str, str] = dataclass_field(default_factory=dict)


class ModbusServerAdapter:
    """Serve device models over Modbus TCP (Xime as the slave/server).

    Register it like any other adapter:

        app.use(ModbusServerAdapter())

    Reads the listen address from the `modbus.server` block; handler classes
    come from configure_modbus_server() unless `controllers` names them.
    """

    def __init__(
        self,
        *,
        controllers: list[type] | None = None,
        refresh: float = 1.0,
        max_concurrency: int = 16,
    ) -> None:
        if refresh <= 0:
            raise ValueError(
                f"refresh must be > 0 seconds (got {refresh}). A value of 0 would "
                f"call every @serve handler in a tight loop with no pause."
            )
        if max_concurrency < 1:
            raise ValueError(
                f"max_concurrency must be >= 1 (got {max_concurrency})."
            )
        self._controllers = controllers
        self._refresh = refresh
        # Upper bound on write handlers running at once. A master can write far
        # faster than a handler that talks to a database can finish, and without
        # a cap every request spawned an unbounded task. The master side has had
        # this limit since 0.7 (modbus.max_concurrency); the slave side needs it
        # for the same reason.
        # Chặn trên số handler ghi chạy đồng thời. Master ghi nhanh hơn handler
        # nói chuyện với database rất nhiều; không có chặn trên thì mỗi request
        # sinh một task không giới hạn.
        self._max_concurrency = max_concurrency
        self._sem: asyncio.Semaphore | None = None
        # Settings come from the single `modbus.server` block, so a second
        # instance would bind the same port. Application.use() rejects it here
        # with a message, instead of leaving an OSError from deep inside the
        # listener at start-up.
        self._server_id = "default"
        self._config: ModbusServerConfig | None = None
        self._models: dict[int, list[ServedModel]] = {}   # unit -> models
        self._server: Any = None
        self._stopping = False
        self._tasks: set[asyncio.Task] = set()

    # ------------------------------------------------------------------
    # Adapter protocol
    # ------------------------------------------------------------------

    async def start(self, app: Application) -> None:
        try:
            import pymodbus  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "ModbusServerAdapter requires pymodbus. "
                "Run: pip install 'xime[modbus]'"
            ) from None

        from pymodbus.server import ModbusTcpServer

        from xime.core.config.runtime import RuntimeConfig

        runtime: RuntimeConfig = app.get(RuntimeConfig)  # type: ignore[assignment]
        self._config = ModbusServerConfig.resolve(runtime)

        controllers = self._controllers
        if controllers is None:
            controllers = ModbusControllerScanner().find_controllers(
                *modbus_registry.get_server_packages()
            )
        self._models = self._collect(app, controllers)
        if not self._models:
            raise StartupException(
                "\nModbus server has nothing to serve\n"
                "  Detail: no @serve or @on_write handler was found.\n"
                "  Fix   : register the package with configure_modbus_server(), "
                "or pass controllers=[...] to ModbusServerAdapter."
            )

        devices = [self._build_device(unit) for unit in sorted(self._models)]
        self._server = ModbusTcpServer(
            devices if len(devices) > 1 else devices[0],
            address=(self._config.host, self._config.port),
        )
        # background=True returns once the listener is accepting; without it
        # serve_forever() would only return at shutdown and the refresh loop
        # below would never start.
        # background=True trả về ngay khi đã lắng nghe.
        await self._server.serve_forever(background=True)
        logger.info(
            "Modbus server listening on %s:%s — unit(s) %s",
            self._config.host, self._config.port, sorted(self._models),
        )

        await self._refresh_forever()

    async def stop(self) -> None:
        self._stopping = True
        for task in list(self._tasks):
            task.cancel()
        self._tasks.clear()
        if self._server is not None:
            try:
                await self._server.shutdown()
            except Exception:  # pragma: no cover - teardown diagnostics only
                logger.debug("Error shutting down Modbus server", exc_info=True)
            self._server = None

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def _collect(self, app: Any, controllers: list[type]) -> dict[int, list[ServedModel]]:
        """Group @serve / @on_write handlers by unit id, then by model."""
        by_model: dict[type, ServedModel] = {}

        for cls in controllers:
            try:
                instance = app.get(cls)
            except KeyError:
                raise StartupException(
                    f"\nModbus controller not in the DI container\n"
                    f"  Controller: {cls.__name__}\n"
                    f"  Fix       : add its package to dependency.scan()."
                ) from None

            for attr_name, info in self._iter_handlers(cls):
                bound = getattr(instance, attr_name)
                if info.kind is ModbusKind.SERVE:
                    self._add_provider(by_model, cls, attr_name, info, bound)
                elif info.kind is ModbusKind.ON_WRITE:
                    self._add_writer(by_model, cls, attr_name, info, bound)

        by_unit: dict[int, list[ServedModel]] = {}
        for served in by_model.values():
            by_unit.setdefault(served.info.unit, []).append(served)
        return by_unit

    def _add_provider(self, by_model, cls, attr_name, info, bound) -> None:
        device_info = self._require_model(cls, attr_name, info.model)
        served = by_model.setdefault(device_info.cls, ServedModel(device_info))
        if served.provider is not None:
            raise StartupException(
                f"\nDuplicate @serve for one model\n"
                f"  Model   : {device_info.cls.__name__}\n"
                f"  Handlers: {served.provider_name}, {cls.__name__}.{attr_name}\n"
                f"  Why     : two providers would overwrite each other's values\n"
                f"            on every refresh, and which one wins would depend\n"
                f"            on scan order.\n"
                f"  Fix     : keep one @serve per model."
            )
        served.provider = bound
        served.provider_name = f"{cls.__name__}.{attr_name}"

    def _add_writer(self, by_model, cls, attr_name, info, bound) -> None:
        field = info.field
        if not isinstance(field, ModbusField):
            raise StartupException(
                f"\nInvalid @on_write target\n"
                f"  Handler: {cls.__name__}.{attr_name}\n"
                f"  Fix    : pass a model field, e.g. @on_write(Inverter.run_state)."
            )
        owner = field._owner_info
        if owner is None:
            raise StartupException(
                f"\nInvalid @on_write target\n"
                f"  Handler: {cls.__name__}.{attr_name}\n"
                f"  Detail : field '{field.name}' does not belong to a @device model."
            )
        if not field.area.writable:
            raise StartupException(
                f"\nUnwritable @on_write target\n"
                f"  Handler: {cls.__name__}.{attr_name}\n"
                f"  Field  : {field.name} ({field.area.label})\n"
                f"  Why    : masters cannot write to {field.area.label} on the\n"
                f"           Modbus protocol, so this handler could never fire.\n"
                f"  Fix    : use a coil or holding register field."
            )
        served = by_model.setdefault(owner.cls, ServedModel(owner))
        served.writers[field.name] = bound
        served.writer_names[field.name] = f"{cls.__name__}.{attr_name}"

    @staticmethod
    def _iter_handlers(cls: type) -> list[tuple[str, ModbusHandlerInfo]]:
        seen: set[str] = set()
        result: list[tuple[str, ModbusHandlerInfo]] = []
        for klass in reversed(cls.__mro__):
            for attr_name in vars(klass):
                if attr_name in seen:
                    continue
                seen.add(attr_name)
                info = getattr(getattr(cls, attr_name, None), MODBUS_ATTR, None)
                if info is not None and info.kind in (
                    ModbusKind.SERVE, ModbusKind.ON_WRITE
                ):
                    result.append((attr_name, info))
        return result

    @staticmethod
    def _require_model(cls: type, attr_name: str, model: Any) -> DeviceInfo:
        info = get_device_info(model) if isinstance(model, type) else None
        if info is None:
            name = getattr(model, "__name__", repr(model))
            raise StartupException(
                f"\nInvalid @serve target\n"
                f"  Handler: {cls.__name__}.{attr_name}\n"
                f"  Detail : '{name}' is not a device model.\n"
                f"  Fix    : decorate it with @device(unit=...)."
            )
        return info

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def _build_device(self, unit: int) -> Any:
        """Build the SimDevice holding every model served on one unit.

        Each area is sized to the highest address any model declares. Addresses
        outside that span stay undefined on purpose, so a master reading them
        gets ILLEGAL DATA ADDRESS instead of a plausible zero.
        Địa chỉ ngoài vùng khai báo cố ý để trống - master đọc sẽ nhận ILLEGAL
        DATA ADDRESS thay vì một số 0 trông có vẻ hợp lệ.
        """
        from pymodbus.simulator import DataType, SimData, SimDevice

        blocks = []
        for area in (Area.COIL, Area.DISCRETE, Area.HOLDING, Area.INPUT):
            size = self._area_size(unit, area)
            if size == 0:
                # SimData needs at least one cell; one undefined-but-present
                # entry keeps the block valid without exposing storage.
                size = 1
            if area.is_bit:
                blocks.append([SimData(0, values=[False] * size, datatype=DataType.BITS)])
            else:
                blocks.append([SimData(0, values=[0] * size, datatype=DataType.REGISTERS)])

        return SimDevice(unit, simdata=tuple(blocks), action=self._make_action(unit))

    def _area_size(self, unit: int, area: Area) -> int:
        highest = 0
        for served in self._models.get(unit, []):
            for field in served.info.fields.values():
                if field.area is area:
                    highest = max(highest, field.end_address)
        return highest

    def _make_action(self, unit: int):
        """Build the register-access callback pymodbus calls for this unit."""

        async def action(
            func_code: int,
            start_address: int,
            address: int,
            count: int,
            registers: list[int],
            values: Any,
        ) -> Any:
            if values is None:
                return None  # a read: values were refreshed by the timer
            await self._handle_write(unit, func_code, address, values)
            return None

        return action

    # ------------------------------------------------------------------
    # Write handling
    # ------------------------------------------------------------------

    async def _handle_write(
        self, unit: int, func_code: int, address: int, values: Any
    ) -> None:
        area = _CODE_AREAS.get(func_code)
        if area is None or func_code not in (_WRITE_COIL_CODES | _WRITE_REGISTER_CODES):
            return

        for served in self._models.get(unit, []):
            for name, bound in served.writers.items():
                field = served.info.fields[name]
                if field.area is not area:
                    continue
                payload = _slice_written(field, address, values)
                if payload is None:
                    continue
                try:
                    value = decode_field(field, served.info, payload)
                except Exception:
                    logger.exception(
                        "Modbus server could not decode a write to '%s'", name
                    )
                    continue
                await self._dispatch(
                    bound, value, served.writer_names.get(name, name)
                )

    async def _dispatch(self, bound: Any, value: Any, label: str) -> None:
        """Run a write handler outside the protocol path.

        Scheduling it rather than awaiting keeps pymodbus' reply prompt: a
        handler that talks to a database must not delay the Modbus response.
        Chạy nền để handler chậm không làm trễ phản hồi Modbus.
        """
        if self._sem is None:
            self._sem = asyncio.Semaphore(self._max_concurrency)
        task = asyncio.create_task(self._invoke(self._sem, bound, value, label))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @staticmethod
    async def _invoke(
        sem: asyncio.Semaphore, bound: Any, value: Any, label: str
    ) -> None:
        # The semaphore is acquired inside the task, not before creating it:
        # this runs from pymodbus' access callback, which is synchronous and
        # cannot await. Queueing here still bounds how many handlers execute at
        # once, which is what protects whatever they talk to.
        # Semaphore lấy BÊN TRONG task chứ không trước khi tạo: chỗ gọi là callback
        # ĐỒNG BỘ của pymodbus, không await được.
        async with sem:
            request_context.set("request_id", str(uuid.uuid4()))
            try:
                await bound(value)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Modbus write handler %s failed", label)
            finally:
                request_context.clear()
                clear_security()

    # ------------------------------------------------------------------
    # Refresh loop
    # ------------------------------------------------------------------

    async def _refresh_forever(self) -> None:
        loop = asyncio.get_running_loop()
        while not self._stopping:
            started = loop.time()
            try:
                await self.refresh_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Modbus server refresh failed")
            elapsed = loop.time() - started
            await asyncio.sleep(max(0.0, self._refresh - elapsed))

    async def refresh_once(self) -> None:
        """Ask every @serve handler for current values and store them.

        Public so an application can push an update immediately after something
        important changed, instead of waiting for the next tick.
        Công khai để app đẩy cập nhật ngay khi có thay đổi quan trọng.
        """
        if self._server is None:
            return
        for unit, served_models in self._models.items():
            for served in served_models:
                if served.provider is None:
                    continue
                request_context.set("request_id", str(uuid.uuid4()))
                try:
                    instance = await served.provider()
                    if instance is not None:
                        await self._store(unit, served.info, instance)
                except Exception:
                    logger.exception(
                        "Modbus @serve handler %s failed", served.provider_name
                    )
                finally:
                    request_context.clear()
                    clear_security()

    async def _store(self, unit: int, info: DeviceInfo, instance: Any) -> None:
        """Encode a model instance into the served registers."""
        for name, field in info.fields.items():
            value = getattr(instance, name, None)
            if value is None:
                continue
            try:
                payload = encode_field(field, info, value, allow_read_only=True)
            except Exception:
                logger.exception("Modbus server could not encode field '%s'", name)
                continue
            await self._server.async_setValues(
                unit, _read_code(field.area), field.address, payload
            )


def _read_code(area: Area) -> int:
    return {
        Area.COIL: 1, Area.DISCRETE: 2, Area.HOLDING: 3, Area.INPUT: 4,
    }[area]


def _slice_written(field: ModbusField, address: int, values: Any) -> list[Any] | None:
    """The part of a write request that lands on `field`, or None if it misses."""
    end = address + len(values)
    if field.address < address or field.end_address > end:
        return None
    begin = field.address - address
    return list(values)[begin:begin + field.word_count]
