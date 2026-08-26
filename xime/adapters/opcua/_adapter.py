"""The OPC UA client adapter: connect, subscribe, dispatch.

    app.use(OpcuaAdapter())

Owns the session to one named server, keeps it alive across drops, and turns
the server's data-change notifications into calls on your @on_node_change
handlers.

Where the Modbus adapter has to poll, this one subscribes: OPC UA pushes. That
removes the interval question entirely but adds one of its own - asyncua
delivers notifications through a SYNCHRONOUS callback, so handlers are
scheduled as tasks rather than awaited inline. Awaiting there would block the
library's receive loop and stall every other subscription.
asyncua giao thông báo qua callback ĐỒNG BỘ, nên handler được schedule thành
task; await thẳng trong đó sẽ chặn vòng nhận của thư viện.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from xime.core.bootstrap.adapter import SCALING_SHARDED, Adapter
from xime.core.context import request_context
from xime.core.exception.framework import StartupException
from xime.core.security import clear_security

from ._client import OpcuaClient, register_resolved_config
from ._config import DEFAULT_SERVER, OpcuaConfig, opcua_registry
from ._decorators import OPCUA_ATTR, OpcuaKind
from ._model import OpcuaNode
from ._scanner import OpcuaControllerScanner
from ._security import build_security_string

if TYPE_CHECKING:
    from xime.core.bootstrap.application import Application

logger = logging.getLogger("xime.opcua")

_UNSEEN = object()

# Tên tham số handler khai để nhận tên THỰC THỂ đang được xử lý - đối xứng với
# `DEVICE_PARAM` của Modbus. Một hằng chứ không phải chuỗi rải rác, vì nó là một
# phần hợp đồng công khai.
SERVER_PARAM = "server"


@dataclass
class NodeWatch:
    """One @on_node_change handler bound to its DI instance."""

    node: OpcuaNode
    bound: Any
    controller: str
    handler: str
    deadband: float | None = None
    initial: bool = False
    wants_server: bool = False


class OpcuaAdapter(
    Adapter,
    scaling=SCALING_SHARDED,
    disjoint_per_process=("servers",),
):
    """Maintain a session to one OPC UA server and dispatch data changes."""

    # Khoá tầng hai trong khối `processes:` (`processes.<p>.opcua.<id>`).
    adapter_kind = "opcua"

    def assign_slot(self, slot: object) -> None:
        """Nhận ô cấu hình, và **hiện chưa dùng tới nó**.

        Adapter hạng phân mảnh đọc khối YAML của riêng mình như cũ; việc chia
        tập thiết bị / tập topic theo tiến trình thi công ở **một bản 0.8.x**,
        chưa chốt bản nào.

        ⚠ Không ném ở đây. Từ 0.8 **mọi** adapter luôn nhận một ô, kể cả ở nhánh
        một tiến trình - nơi adapter này chạy hoàn toàn bình thường. Thứ phải
        chặn là *chia tải*, không phải *nhận cấu hình*, nên phép chặn nằm ở
        framework (`_reject_sharded_under_share_load`).
        """
        self._slot = slot

    def __init__(
        self,
        target_id: str = DEFAULT_SERVER,
        *,
        controllers: list[type] | None = None,
    ) -> None:
        self._server = target_id
        # Identity used by Application.use() to reject a duplicate registration
        # - two adapters on one server would hold two sessions and attach two
        # clients to the one shared OpcuaConnection. See ModbusAdapter.
        self.adapter_id = target_id
        self._slot = None
        self._controllers = controllers
        self._config: OpcuaConfig | None = None
        self._connection = opcua_registry.connection(target_id)
        self._connection.mark_served()
        self._client = OpcuaClient(target_id)
        self._watches: list[NodeWatch] = []
        self._by_node_id: dict[str, list[NodeWatch]] = {}
        self._last: dict[str, Any] = {}
        self._stopping = False
        self._tasks: set[asyncio.Task] = set()
        self._sem: asyncio.Semaphore | None = None

    # ------------------------------------------------------------------
    # Adapter protocol
    # ------------------------------------------------------------------

    async def start(self, app: Application) -> None:
        try:
            import asyncua  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "OpcuaAdapter requires asyncua. Run: pip install 'xime[opcua]'"
            ) from None

        from xime.core.config.runtime import RuntimeConfig

        runtime: RuntimeConfig = app.get(RuntimeConfig)
        self._config = OpcuaConfig.resolve(runtime, self._server)
        register_resolved_config(self._config)
        self._sem = asyncio.Semaphore(self._config.max_concurrency)

        controllers = self._controllers
        if controllers is None:
            controllers = OpcuaControllerScanner().find_controllers(
                *opcua_registry.get_packages()
            )
        self._watches = self._collect(app, controllers)
        self._by_node_id = {}
        for watch in self._watches:
            self._by_node_id.setdefault(watch.node.node_id, []).append(watch)

        logger.info(
            "OPC UA server '%s' at %s (security=%s) - %d watched node(s)",
            self._server, self._config.endpoint, self._config.security,
            len(self._watches),
        )
        if str(self._config.security).lower() == "none":
            logger.warning(
                "OPC UA client '%s' connects to %s with security=None: the "
                "session is neither signed nor encrypted, and neither side "
                "proves who it is. Use Sign or SignAndEncrypt outside a lab.",
                self._server, self._config.endpoint,
            )

    async def serve(self) -> None:
        """Vòng kết nối lại chạy suốt vòng đời - xem `ModbusAdapter.serve`."""
        await self._run_forever()

    async def stop(self) -> None:
        self._stopping = True
        for task in list(self._tasks):
            task.cancel()
        self._tasks.clear()
        self._connection.detach()

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def _collect(self, app: Any, controllers: list[type]) -> list[NodeWatch]:
        watches: list[NodeWatch] = []
        for cls in controllers:
            try:
                instance = app.get(cls)
            except KeyError:
                raise StartupException(
                    f"\nOPC UA controller not in the DI container\n"
                    f"  Controller: {cls.__name__}\n"
                    f"  Fix       : add its package to dependency.scan()."
                ) from None

            for attr_name, info in _iter_handlers(cls, OpcuaKind.ON_CHANGE):
                bound = getattr(instance, attr_name)
                if not inspect.iscoroutinefunction(bound):
                    raise StartupException(
                        _err(cls, attr_name, "handler must be an `async def` "
                                             "coroutine function")
                    )
                node = info.node
                if not isinstance(node, OpcuaNode):
                    raise StartupException(
                        _err(
                            cls, attr_name,
                            "@on_node_change needs a model node, e.g. "
                            "@on_node_change(Tank.level)",
                        )
                    )
                if info.deadband is not None and info.deadband < 0:
                    raise StartupException(
                        _err(cls, attr_name,
                             f"deadband must be >= 0 (got {info.deadband})")
                    )
                watches.append(
                    NodeWatch(
                        node, bound, cls.__name__, attr_name,
                        info.deadband, info.initial,
                        _wants_server(cls, attr_name, bound),
                    )
                )
        return watches

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------

    async def _run_forever(self) -> None:
        assert self._config is not None
        config = self._config
        while not self._stopping:
            client = None
            try:
                client = await self._connect(config)
                self._connection.attach(client)
                await self._subscribe_and_wait(config)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._stopping:
                    break
                logger.warning(
                    "OPC UA server '%s' unavailable (%s); retrying in %.1fs",
                    self._server, exc, config.reconnect_delay,
                )
            finally:
                self._connection.detach()
                if client is not None:
                    try:
                        await client.disconnect()
                    except Exception:
                        logger.debug("Error disconnecting OPC UA client", exc_info=True)
            if self._stopping:
                break
            await asyncio.sleep(config.reconnect_delay)

    async def _connect(self, config: OpcuaConfig) -> Any:
        from asyncua import Client

        client = Client(config.endpoint, timeout=config.timeout)
        # Set before set_security_string(): the URI travels in the session
        # request the server validates against our certificate.
        # Đặt TRƯỚC set_security_string(): URI đi trong request tạo session mà
        # server dùng để đối chiếu với cert của ta.
        if config.application_uri:
            client.application_uri = config.application_uri
        security = build_security_string(
            config.security, config.certificate, config.private_key
        )
        if security is not None:
            await client.set_security_string(security)
        if config.username:
            client.set_user(config.username)
            if config.password:
                client.set_password(config.password)
        await client.connect()
        logger.info("OPC UA server '%s' connected", self._server)
        return client

    async def _subscribe_and_wait(self, config: OpcuaConfig) -> None:
        """Subscribe to every watched node, then idle until stopped.

        With nothing to watch the adapter still holds the session open, which
        is what an application that only reads on demand needs.
        """
        if not self._watches:
            while not self._stopping:
                await asyncio.sleep(3600)
            return

        subscription = await self._connection.create_subscription(
            config.subscription_period, _Handler(self)
        )
        client = self._connection._client
        for node_id in self._by_node_id:
            await subscription.subscribe_data_change(client.get_node(node_id))

        try:
            while not self._stopping:
                await asyncio.sleep(1)
        finally:
            try:
                await subscription.delete()
            except Exception:
                logger.debug("Error deleting OPC UA subscription", exc_info=True)

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def on_data_change(self, node_id: str, value: Any) -> None:
        """Called from asyncua's synchronous callback; never blocks it."""
        watches = self._by_node_id.get(node_id)
        if not watches:
            return
        for watch in watches:
            before = self._last.get(node_id, _UNSEEN)
            if before is _UNSEEN and not watch.initial:
                # OPC UA delivers the current value the moment you subscribe.
                # Reporting it as a "change" would fire every handler on every
                # startup, so by default it is only a baseline - same rule as
                # the Modbus @on_change.
                continue
            if before is not _UNSEEN and not _has_changed(
                before, value, watch.deadband
            ):
                continue
            task = asyncio.create_task(
                self._invoke(watch, value)
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        self._last[node_id] = value

    async def _invoke(self, watch: NodeWatch, value: Any) -> None:
        assert self._sem is not None
        async with self._sem:
            request_context.set("request_id", str(uuid.uuid4()))
            try:
                if watch.wants_server:
                    await watch.bound(value, server=self._server)
                else:
                    await watch.bound(value)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "OPC UA handler %s.%s failed", watch.controller, watch.handler
                )
            finally:
                request_context.clear()
                clear_security()


class _Handler:
    """asyncua subscription handler: a plain object with sync callbacks."""

    def __init__(self, adapter: OpcuaAdapter) -> None:
        self._adapter = adapter

    def datachange_notification(self, node: Any, value: Any, data: Any) -> None:
        try:
            node_id = node.nodeid.to_string()
        except Exception:  # pragma: no cover - defensive; asyncua always sets it
            return
        self._adapter.on_data_change(node_id, value)

    def status_change_notification(self, status: Any) -> None:
        logger.debug("OPC UA status change: %s", status)

    def event_notification(self, event: Any) -> None:
        logger.debug("OPC UA event: %s", event)


def _has_changed(before: Any, current: Any, deadband: float | None) -> bool:
    """Same rule as the Modbus adapter, so both behave alike."""
    if deadband is None or deadband <= 0:
        return before != current
    if isinstance(before, (int, float)) and isinstance(current, (int, float)):
        if isinstance(before, bool) or isinstance(current, bool):
            return before != current
        return abs(current - before) > deadband
    return before != current


def _iter_handlers(cls: type, *kinds: OpcuaKind) -> list[tuple[str, Any]]:
    seen: set[str] = set()
    result: list[tuple[str, Any]] = []
    for klass in reversed(cls.__mro__):
        for attr_name in vars(klass):
            if attr_name in seen:
                continue
            seen.add(attr_name)
            info = getattr(getattr(cls, attr_name, None), OPCUA_ATTR, None)
            if info is not None and (not kinds or info.kind in kinds):
                result.append((attr_name, info))
    return result


def _wants_server(cls: type, attr_name: str, bound: Any) -> bool:
    """Whether the handler asked to know which entity this call is about.

    Đối xứng với `device` của Modbus (thiết kế 5.7.3): một adapter phục vụ một
    **loại** và giữ **nhiều thực thể**, nên handler chạy một lần cho mỗi thực
    thể và muốn biết máy nào thì khai thêm một tham số tên `server` - khớp theo
    TÊN, đúng quy ước `topic` của `@subscribe`.

    ⭐ Mỗi adapter giữ từ vựng của miền nó: Modbus nói *device*, OPC UA nói
    *server*. Đây là chỗ **khác** với `adapter_id`/`target_id` ở phần 1 - ở đó
    một cái tên chung là đúng vì nó nói về **framework**; ở đây cái tên nói về
    **thứ thật ngoài kia**, và ép chung một chữ là dán sai nhãn.

    ⚠ Tên phải khớp chính xác: một tham số thứ hai mang tên khác là **lỗi khởi
    động**, không phải một tham số bị bỏ qua im lặng.
    """
    params = [
        p for p in inspect.signature(bound).parameters.values()
        if p.kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    ]
    if len(params) == 1:
        return False
    if len(params) == 2 and params[1].name == SERVER_PARAM:
        return True
    raise StartupException(
        _err(
            cls, attr_name,
            f"handler takes the new value, plus an optional parameter named "
            f"'{SERVER_PARAM}'; got {[p.name for p in params]}",
        )
    )


def _err(cls: type, attr_name: str, detail: str) -> str:
    return (
        f"\nInvalid OPC UA Handler\n"
        f"  Controller: {cls.__name__}\n"
        f"  Handler   : {attr_name}\n"
        f"  Detail    : {detail}"
    )
