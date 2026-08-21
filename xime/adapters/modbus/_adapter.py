"""The polling adapter: Xime as an active Modbus master.

Registered like any other adapter and started by app.run():

    app = Application()
    app.use(WebAdapter()).use(ModbusAdapter("inverter_1"))
    app.run()

It owns the connection to ONE named device, and runs one loop per poll group so
two handlers on the same model and cadence never cause two reads. Handlers run
in bounded-concurrency tasks reusing the pattern proven by the MQTT adapter.
Sở hữu kết nối tới MỘT thiết bị theo tên, chạy một vòng cho mỗi poll group.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING, Any

from xime.core.bootstrap.adapter import SCALING_SHARDED, Adapter
from xime.core.context import request_context
from xime.core.security import clear_security

from ._client import ModbusClient, register_resolved_config
from ._config import DEFAULT_DEVICE, ModbusConfig, modbus_registry
from .routing._builder import ModbusRouteBuilder, PollGroup
from .routing._scanner import ModbusControllerScanner

if TYPE_CHECKING:
    from xime.core.bootstrap.application import Application

logger = logging.getLogger("xime.modbus")

# Sentinel for "no reading yet", distinct from a genuine None value.
_UNSEEN = object()


class ModbusAdapter(
    Adapter,
    scaling=SCALING_SHARDED,
    disjoint_per_process=("devices",),
):
    """Connects to one device and drives its poll loops."""

    # Khoá tầng hai trong khối `processes:` (`processes.<p>.modbus.<id>`).
    adapter_kind = "modbus"

    def assign_slot(self, slot: object) -> None:
        """Nhận ô cấu hình, và **hiện chưa dùng tới nó**.

        Adapter hạng phân mảnh đọc khối YAML của riêng mình như cũ; việc chia
        tập thiết bị / tập topic theo tiến trình thi công ở **0.8.1**.

        ⚠ Không ném ở đây. Từ 0.8 **mọi** adapter luôn nhận một ô, kể cả ở nhánh
        một tiến trình - nơi adapter này chạy hoàn toàn bình thường. Thứ phải
        chặn là *chia tải*, không phải *nhận cấu hình*, nên phép chặn nằm ở
        framework (`_reject_sharded_under_share_load`).
        """
        self._slot = slot

    def __init__(
        self,
        target_id: str = DEFAULT_DEVICE,
        *,
        controllers: list[type] | None = None,
    ) -> None:
        """Serve one named device.

        `controllers` names the handler classes explicitly instead of scanning
        the packages given to configure_modbus_devices(). Useful for a small
        application that would rather list them, and for tests.
        `controllers` khai tường minh thay cho việc quét package.
        """
        self._device = target_id
        # Application.use() rejects two adapters of the same type carrying the
        # same adapter_id. Two ModbusAdapters on one device would run two poll
        # loops against the same PLC and attach two clients to the one shared
        # ModbusConnection, where the second silently replaces the first.
        # Application.use() từ chối hai adapter cùng loại cùng adapter_id. Hai
        # ModbusAdapter trên một thiết bị sẽ chạy hai vòng poll vào cùng một PLC
        # và gắn hai client vào một ModbusConnection dùng chung.
        self.adapter_id = target_id
        self._slot = None
        self._controllers = controllers
        self._config: ModbusConfig | None = None
        self._connection = modbus_registry.connection(target_id)
        # Claim the name at construction (app.use time) so a ModbusClient bound
        # to it fails fast instead of waiting for a connection that is coming.
        # Nhận tên ngay lúc app.use để client bám vào không chờ vô ích.
        self._connection.mark_served()
        self._groups: list[PollGroup] = []
        self._client = ModbusClient(target_id)
        self._stopping = False
        self._tasks: set[asyncio.Task] = set()
        self._sem: asyncio.Semaphore | None = None

    # ------------------------------------------------------------------
    # Adapter protocol
    # ------------------------------------------------------------------

    async def start(self, app: Application) -> None:
        try:
            import pymodbus  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "ModbusAdapter requires pymodbus. Run: pip install 'xime[modbus]'"
            ) from None

        from xime.core.config.runtime import RuntimeConfig

        runtime: RuntimeConfig = app.get(RuntimeConfig)
        self._config = ModbusConfig.resolve(runtime, self._device)
        register_resolved_config(self._config)
        self._sem = asyncio.Semaphore(self._config.max_concurrency)

        controllers = self._controllers
        if controllers is None:
            controllers = ModbusControllerScanner().find_controllers(
                *modbus_registry.get_packages()
            )
        # 0.8: một adapter phục vụ MỘT LOẠI thiết bị, nên MỌI nhóm của mọi
        # controller nó cầm đều chạy - không còn trục `device` để lọc. Việc chọn
        # controller nào thuộc loại nào là việc của `controllers=` ở `app.use()`.
        self._groups = ModbusRouteBuilder(app).build(controllers)
        logger.info(
            "Modbus device '%s' at %s:%s - %d poll group(s)",
            self._device, self._config.host, self._config.port, len(self._groups),
        )


    async def serve(self) -> None:
        """Vòng poll chạy suốt vòng đời.

        ⚠ Kết nối tới thiết bị nằm ở đây chứ không ở `start()`: adapter này
        vốn thiết kế để **chịu được PLC chưa lên** và tự thử lại.
        """
        await self._run_forever()

    async def stop(self) -> None:
        self._stopping = True
        for task in list(self._tasks):
            task.cancel()
        self._tasks.clear()
        client = getattr(self._connection, "_client", None)
        self._connection.detach()
        if client is not None:
            try:
                client.close()
            except Exception:  # pragma: no cover - teardown must not mask errors
                logger.debug("Error closing Modbus client", exc_info=True)

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def _run_forever(self) -> None:
        assert self._config is not None
        config = self._config
        while not self._stopping:
            client = None
            try:
                client = await self._connect(config)
                self._connection.attach(client)
                await self._serve_groups()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._stopping:
                    break
                logger.warning(
                    "Modbus device '%s' unavailable (%s); retrying in %.1fs",
                    self._device, exc, config.reconnect_delay,
                )
            finally:
                self._connection.detach()
                if client is not None:
                    try:
                        client.close()
                    except Exception:
                        logger.debug("Error closing Modbus client", exc_info=True)
            if self._stopping:
                break
            await asyncio.sleep(config.reconnect_delay)

    async def _connect(self, config: ModbusConfig) -> Any:
        from pymodbus.client import AsyncModbusTcpClient

        client = AsyncModbusTcpClient(
            config.host,
            port=config.port,
            timeout=config.timeout,
            reconnect_delay=config.reconnect_delay,
        )
        await client.connect()
        if not client.connected:
            raise ConnectionError(
                f"could not connect to {config.host}:{config.port}"
            )
        logger.info("Modbus device '%s' connected", self._device)
        return client

    async def _serve_groups(self) -> None:
        """Run every poll loop until one fails fatally or the adapter stops.

        With no groups the adapter still holds the connection open, which is
        what an application that only reads on demand needs.
        Không có group nào thì adapter vẫn giữ kết nối - đủ cho app chỉ đọc
        theo yêu cầu.
        """
        if not self._groups:
            while not self._stopping:
                await asyncio.sleep(3600)
            return

        async with asyncio.TaskGroup() as tg:
            for group in self._groups:
                tg.create_task(self._run_group(group))

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    async def _run_group(self, group: PollGroup) -> None:
        """Read one model on its cadence and dispatch to everyone waiting.

        A failed cycle is logged and the loop continues: devices on a plant
        floor drop off the network routinely, and one bad reading must not kill
        the monitoring for the rest of the shift.
        Một chu kỳ lỗi thì log rồi chạy tiếp - thiết bị nhà máy rớt mạng là
        chuyện thường.
        """
        loop = asyncio.get_running_loop()
        previous: dict[str, Any] = {}

        while not self._stopping:
            started = loop.time()
            request_context.set("request_id", str(uuid.uuid4()))
            try:
                instance: Any = await self._client.read(
                    group.model, device=self._device
                )
                for poll in group.polls:
                    await self._dispatch(
                        poll.bound, instance, poll.controller, poll.handler,
                        poll.wants_device,
                    )
                await self._fire_changes(group, instance, previous)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Modbus poll failed for %s on device '%s'",
                    group.model.__name__, self._device,
                )
            finally:
                request_context.clear()
                clear_security()

            # Subtract the time the cycle took so the cadence stays honest
            # instead of drifting by however long the device took to answer.
            # Trừ thời gian chu kỳ để nhịp không trôi theo độ trễ thiết bị.
            elapsed = loop.time() - started
            await asyncio.sleep(max(0.0, group.interval - elapsed))

    async def _fire_changes(
        self, group: PollGroup, instance: Any, previous: dict[str, Any]
    ) -> None:
        for watch in group.watches:
            name = watch.field.name
            current = getattr(instance, name, None)
            before = previous.get(name, _UNSEEN)
            previous[name] = current
            if before is _UNSEEN:
                # First reading establishes the baseline. Firing here would
                # report a "change" on every startup, which is noise, not news.
                # Lần đọc đầu chỉ lấy mốc - bắn ở đây là báo động giả lúc khởi động.
                continue
            if _has_changed(before, current, watch.deadband):
                await self._dispatch(
                    watch.bound, current, watch.controller, watch.handler,
                    watch.wants_device,
                )

    async def _dispatch(
        self,
        bound: Any,
        argument: Any,
        controller: str,
        handler: str,
        wants_device: bool = False,
    ) -> None:
        """Schedule one handler under the concurrency limit.

        Acquiring the semaphore before creating the task applies backpressure:
        when max_concurrency handlers are in flight, the poll loop waits here
        rather than piling up work the device cannot keep up with.
        """
        assert self._sem is not None
        await self._sem.acquire()
        device = self._device if wants_device else None
        task = asyncio.create_task(
            self._invoke(bound, argument, controller, handler, device)
        )
        self._tasks.add(task)

        def _done(finished: asyncio.Task) -> None:
            self._tasks.discard(finished)
            self._sem.release()  # type: ignore[union-attr]

        task.add_done_callback(_done)

    @staticmethod
    async def _invoke(
        bound: Any,
        argument: Any,
        controller: str,
        handler: str,
        device: str | None = None,
    ) -> None:
        try:
            if device is None:
                await bound(argument)
            else:
                await bound(argument, device=device)
        except asyncio.CancelledError:
            raise
        except Exception:
            # One failing handler must not stop the others, mirroring the MQTT
            # dispatcher's policy.
            logger.exception("Modbus handler %s.%s failed", controller, handler)


def _has_changed(before: Any, current: Any, deadband: float | None) -> bool:
    """Whether a new reading counts as a change worth reporting.

    Without a deadband this is plain inequality. With one, numeric readings must
    move by MORE than the deadband - the point is to ignore the last-digit noise
    every analogue sensor produces, which would otherwise fire the handler on
    almost every cycle.
    """
    if deadband is None or deadband <= 0:
        return before != current
    if isinstance(before, (int, float)) and isinstance(current, (int, float)):
        if isinstance(before, bool) or isinstance(current, bool):
            return before != current
        return abs(current - before) > deadband
    return before != current


def describe_groups(groups: list[PollGroup]) -> str:
    """One line per poll group - for startup logging and debugging."""
    if not groups:
        return "(no poll groups)"
    return "\n".join(f"  {group!r}" for group in groups)
