"""Serving OPC UA: Xime as the server other systems connect to.

    class TankEmulator:
        @serve_nodes(Tank)
        async def provide(self) -> Tank:
            return Tank(level=self._level, setpoint=self._setpoint)

        @on_node_write(Tank.setpoint)
        async def setpoint_written(self, value: float) -> None:
            self._setpoint = value

Same split as the Modbus server: values are PUSHED on a timer, writes arrive
through a callback. Serving on demand would mean running business code inside
the library's request path, where a slow handler delays the protocol reply.
Giá trị ĐẨY theo nhịp, còn lệnh ghi tới qua callback - lý do giống server Modbus.

The nodes a model declares are created under the model's namespace. NodeIds are
taken verbatim from the model, so a client using the same model class addresses
exactly the nodes this server publishes.
NodeId lấy nguyên từ model, nên client dùng chung class model sẽ trỏ đúng node.
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

from ._config import OpcuaServerConfig, opcua_registry
from ._decorators import OpcuaKind
from ._model import NodeModelInfo, OpcuaNode, get_node_model_info
from ._scanner import OpcuaControllerScanner
from ._security import server_policies

if TYPE_CHECKING:
    from xime.core.bootstrap.application import Application

logger = logging.getLogger("xime.opcua.server")

DEFAULT_NAMESPACE = "http://xime.dev/opcua"


@dataclass
class ServedNodeModel:
    """One model this process publishes, plus the handlers around it."""

    info: NodeModelInfo
    provider: Any = None
    provider_name: str = ""
    writers: dict[str, Any] = dataclass_field(default_factory=dict)
    writer_names: dict[str, str] = dataclass_field(default_factory=dict)


class OpcuaServerAdapter:
    """Publish node models over OPC UA.

        app.use(OpcuaServerAdapter())

    Reads the endpoint from the `opcua.server` block; handler classes come from
    configure_opcua_server() unless `controllers` names them.
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
                f"call every @serve_nodes handler in a tight loop with no pause."
            )
        if max_concurrency < 1:
            raise ValueError(f"max_concurrency must be >= 1 (got {max_concurrency}).")
        self._controllers = controllers
        self._refresh = refresh
        # Upper bound on write handlers running at once — same reasoning as
        # ModbusServerAdapter: a client can write faster than a handler finishes.
        self._max_concurrency = max_concurrency
        self._sem: asyncio.Semaphore | None = None
        # One `opcua.server` block, so a second instance would bind the same
        # endpoint. See ModbusServerAdapter.
        self._server_id = "default"
        self._config: OpcuaServerConfig | None = None
        self._models: list[ServedNodeModel] = []
        self._server: Any = None
        self._variables: dict[str, Any] = {}   # node_id -> asyncua variable node
        self._watched_writes: dict[str, tuple[Any, str]] = {}
        self._initialised: dict[str, bool] = {}
        self._subscription: Any = None
        self._stopping = False
        self._tasks: set[asyncio.Task] = set()

    # ------------------------------------------------------------------
    # Adapter protocol
    # ------------------------------------------------------------------

    async def start(self, app: Application) -> None:
        try:
            from asyncua import Server
        except ImportError:
            raise RuntimeError(
                "OpcuaServerAdapter requires asyncua. Run: pip install 'xime[opcua]'"
            ) from None

        from xime.core.config.runtime import RuntimeConfig

        runtime: RuntimeConfig = app.get(RuntimeConfig)  # type: ignore[assignment]
        self._config = OpcuaServerConfig.resolve(runtime)

        controllers = self._controllers
        if controllers is None:
            controllers = OpcuaControllerScanner().find_controllers(
                *opcua_registry.get_server_packages()
            )
        self._models = self._collect(app, controllers)
        if not self._models:
            raise StartupException(
                "\nOPC UA server has nothing to serve\n"
                "  Detail: no @serve_nodes or @on_node_write handler was found.\n"
                "  Fix   : register the package with configure_opcua_server(), "
                "or pass controllers=[...] to OpcuaServerAdapter."
            )

        self._server = Server()
        await self._server.init()
        self._server.set_endpoint(self._config.endpoint)
        self._server.set_server_name(self._config.name)
        if self._config.application_uri:
            await self._server.set_application_uri(self._config.application_uri)
        self._server.set_security_policy(server_policies(self._config.security))
        if self._config.certificate and self._config.private_key:
            await self._server.load_certificate(self._config.certificate)
            await self._server.load_private_key(self._config.private_key)

        await self._create_nodes()
        await self._server.start()
        # Subscribing has to wait until the server is running: there is no
        # subscription service before that.
        await self._watch_writes()
        logger.info(
            "OPC UA server listening on %s (security=%s) — %d node(s)",
            self._config.endpoint, self._config.security, len(self._variables),
        )

        await self._refresh_forever()

    async def stop(self) -> None:
        self._stopping = True
        for task in list(self._tasks):
            task.cancel()
        self._tasks.clear()
        if self._subscription is not None:
            try:
                await self._subscription.delete()
            except Exception:
                logger.debug("Error deleting server subscription", exc_info=True)
            self._subscription = None
        if self._server is not None:
            try:
                await self._server.stop()
            except Exception:  # pragma: no cover - teardown diagnostics only
                logger.debug("Error stopping OPC UA server", exc_info=True)
            self._server = None

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def _collect(self, app: Any, controllers: list[type]) -> list[ServedNodeModel]:
        by_model: dict[type, ServedNodeModel] = {}

        for cls in controllers:
            try:
                instance = app.get(cls)
            except KeyError:
                raise StartupException(
                    f"\nOPC UA controller not in the DI container\n"
                    f"  Controller: {cls.__name__}\n"
                    f"  Fix       : add its package to dependency.scan()."
                ) from None

            from ._adapter import _iter_handlers

            for attr_name, info in _iter_handlers(
                cls, OpcuaKind.SERVE, OpcuaKind.ON_WRITE
            ):
                bound = getattr(instance, attr_name)
                if info.kind is OpcuaKind.SERVE:
                    model_info = self._require_model(cls, attr_name, info.model)
                    served = by_model.setdefault(
                        model_info.cls, ServedNodeModel(model_info)
                    )
                    if served.provider is not None:
                        raise StartupException(
                            f"\nDuplicate @serve_nodes for one model\n"
                            f"  Model   : {model_info.cls.__name__}\n"
                            f"  Handlers: {served.provider_name}, "
                            f"{cls.__name__}.{attr_name}\n"
                            f"  Why     : two providers would overwrite each\n"
                            f"            other on every refresh.\n"
                            f"  Fix     : keep one @serve_nodes per model."
                        )
                    served.provider = bound
                    served.provider_name = f"{cls.__name__}.{attr_name}"
                else:
                    node = info.node
                    if not isinstance(node, OpcuaNode):
                        raise StartupException(
                            f"\nInvalid @on_node_write target\n"
                            f"  Handler: {cls.__name__}.{attr_name}\n"
                            f"  Fix    : pass a model node, e.g. "
                            f"@on_node_write(Tank.setpoint)."
                        )
                    owner = node._owner_info
                    if owner is None:
                        raise StartupException(
                            f"\nInvalid @on_node_write target\n"
                            f"  Handler: {cls.__name__}.{attr_name}\n"
                            f"  Detail : node '{node.name}' does not belong to "
                            f"a @node_model class."
                        )
                    served = by_model.setdefault(owner.cls, ServedNodeModel(owner))
                    served.writers[node.name] = bound
                    served.writer_names[node.name] = f"{cls.__name__}.{attr_name}"

        return list(by_model.values())

    @staticmethod
    def _require_model(cls: type, attr_name: str, model: Any) -> NodeModelInfo:
        info = get_node_model_info(model) if isinstance(model, type) else None
        if info is None:
            name = getattr(model, "__name__", repr(model))
            raise StartupException(
                f"\nInvalid @serve_nodes target\n"
                f"  Handler: {cls.__name__}.{attr_name}\n"
                f"  Detail : '{name}' is not a node model.\n"
                f"  Fix    : decorate it with @node_model."
            )
        return info

    # ------------------------------------------------------------------
    # Address space
    # ------------------------------------------------------------------

    async def _create_nodes(self) -> None:
        """Create every declared node, honouring the NodeIds in the model."""
        from asyncua import ua

        for served in self._models:
            namespace = served.info.namespace or DEFAULT_NAMESPACE
            await self._server.register_namespace(namespace)
            folder = await self._server.nodes.objects.add_folder(
                ua.NodeId(served.info.cls.__name__, 0, ua.NodeIdType.String),
                served.info.cls.__name__,
            )
            for name, node in served.info.nodes.items():
                variable = await folder.add_variable(
                    ua.NodeId.from_string(node.node_id),
                    name,
                    _initial_value(served.info, node),
                )
                if name in served.writers or node.writable:
                    await variable.set_writable()
                self._variables[node.node_id] = variable

    async def _watch_writes(self) -> None:
        """Route client writes to @on_node_write handlers.

        The server subscribes to its OWN nodes through the public API rather
        than wrapping anything inside asyncua. That keeps the adapter off
        library internals, which change between releases and would break
        silently.
        Server tự subscribe node của CHÍNH NÓ qua API công khai thay vì bọc
        internals của asyncua - internals đổi giữa các bản và sẽ hỏng âm thầm.

        Because a written node is one the CLIENT owns, the refresh loop never
        overwrites it (see refresh_once), so every notification here really is
        somebody writing to us.
        Node có handler ghi thì vòng refresh không đụng vào, nên mọi thông báo ở
        đây đúng là có người ghi vào ta.
        """
        watched: dict[str, tuple[Any, str]] = {}
        for served in self._models:
            for name, bound in served.writers.items():
                node = served.info.nodes[name]
                watched[node.node_id] = (bound, served.writer_names.get(name, name))
        if not watched:
            return

        self._watched_writes = watched
        subscription = await self._server.create_subscription(
            100, _WriteHandler(self)
        )
        for node_id in watched:
            await subscription.subscribe_data_change(
                self._variables[node_id]
            )
        self._subscription = subscription

    def on_local_change(self, node_id: str, value: Any) -> None:
        """Called from asyncua's synchronous callback; never blocks it."""
        entry = self._watched_writes.get(node_id)
        if entry is None:
            return
        if self._initialised.get(node_id) is not True:
            # The subscription reports the current value immediately; that is
            # our own default, not a client write.
            # Thông báo đầu là giá trị mặc định của chính ta, không phải client ghi.
            self._initialised[node_id] = True
            return
        bound, label = entry
        self._schedule(bound, value, label)

    def _schedule(self, bound: Any, value: Any, label: str) -> None:
        if self._sem is None:
            self._sem = asyncio.Semaphore(self._max_concurrency)
        task = asyncio.create_task(self._invoke(self._sem, bound, value, label))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @staticmethod
    async def _invoke(
        sem: asyncio.Semaphore, bound: Any, value: Any, label: str
    ) -> None:
        # Acquired inside the task because the caller is asyncua's SYNCHRONOUS
        # notification callback and cannot await.
        # Lấy semaphore bên trong task vì chỗ gọi là callback ĐỒNG BỘ của asyncua.
        async with sem:
            request_context.set("request_id", str(uuid.uuid4()))
            try:
                await bound(value)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("OPC UA write handler %s failed", label)
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
                logger.exception("OPC UA server refresh failed")
            elapsed = loop.time() - started
            await asyncio.sleep(max(0.0, self._refresh - elapsed))

    async def refresh_once(self) -> None:
        """Ask every @serve_nodes handler for values and publish them.

        Public so an application can push an update immediately instead of
        waiting for the next tick.
        """
        if self._server is None:
            return
        for served in self._models:
            if served.provider is None:
                continue
            request_context.set("request_id", str(uuid.uuid4()))
            try:
                try:
                    instance = await served.provider()
                except Exception:
                    logger.exception(
                        "OPC UA @serve_nodes handler %s failed", served.provider_name
                    )
                    continue
                if instance is None:
                    continue
                for name, node in served.info.nodes.items():
                    if name in served.writers:
                        # A node with an @on_node_write handler is owned by the
                        # CLIENT. Republishing our own idea of its value would
                        # fight whoever just set it, and would make every write
                        # notification ambiguous.
                        # Node có @on_node_write do CLIENT làm chủ - ghi đè sẽ
                        # đá nhau với người vừa đặt giá trị.
                        continue
                    value = getattr(instance, name, None)
                    if value is None:
                        continue
                    variable = self._variables.get(node.node_id)
                    if variable is None:
                        continue
                    # One node per try: a single rejected write (wrong type,
                    # node deleted by an admin) must not stop the model's other
                    # nodes from being published. With one try around the whole
                    # loop, the first bad node froze every node after it at its
                    # initial value, and the log named the handler rather than
                    # the node at fault.
                    # Mỗi node một try: một lệnh ghi bị từ chối không được chặn
                    # các node còn lại - trước đây node hỏng đầu tiên làm mọi
                    # node sau nó đứng im ở giá trị khởi tạo.
                    try:
                        await variable.write_value(value)
                    except Exception:
                        logger.exception(
                            "OPC UA server could not publish node '%s' (%s) of %s",
                            name, node.node_id, served.info.cls.__name__,
                        )
            finally:
                request_context.clear()
                clear_security()


# Zero value per declared Python type. An OPC UA variable takes its data type
# from the value it is created with, and a client can never write a value of a
# different type afterwards — so getting this wrong is not cosmetic.
# bool must come before int in intent: dict lookup is exact, so `bool` never
# falls through to the `int` entry.
# Biến OPC UA lấy kiểu từ giá trị lúc tạo và về sau KHÔNG nhận giá trị khác kiểu.
_ZERO_BY_TYPE: dict[Any, Any] = {
    bool: False,
    int: 0,
    float: 0.0,
    str: "",
    bytes: b"",
}


def _initial_value(info: NodeModelInfo, node: OpcuaNode) -> Any:
    """The value the variable is created with, which fixes its OPC UA type.

    Order: an explicit `default=` wins, otherwise the type annotated in the
    model. Neither available is a start-up error rather than a guess: creating
    the node as a Double and letting the first refresh fail with
    BadTypeMismatch — inside a caught-and-logged handler, so the node just
    silently keeps its initial value — is exactly the kind of failure this
    framework is supposed to catch at start-up.
    Thứ tự: `default=` tường minh thắng, sau đó tới annotation trong model.
    Không có cái nào thì báo lỗi lúc khởi động chứ không đoán - đoán sai là node
    im lặng giữ giá trị đầu suốt đời.
    """
    if node.default is not None:
        return node.default
    zero = _ZERO_BY_TYPE.get(node.declared_type)
    if zero is not None or node.declared_type in _ZERO_BY_TYPE:
        return zero
    raise StartupException(
        f"\nCannot determine the OPC UA type of a served node\n"
        f"  Model : {info.cls.__name__}\n"
        f"  Node  : {node.name} ({node.node_id})\n"
        f"  Detail: an OPC UA variable takes its data type from the value it\n"
        f"          is created with, and this node declares neither a usable\n"
        f"          Python annotation nor default=.\n"
        f"  Fix   : annotate it ({node.name}: float = Node(...)) using one of\n"
        f"          bool/int/float/str/bytes, or pass default=<initial value>."
    )


class _WriteHandler:
    """asyncua subscription handler for the server's own nodes."""

    def __init__(self, adapter: OpcuaServerAdapter) -> None:
        self._adapter = adapter

    def datachange_notification(self, node: Any, value: Any, data: Any) -> None:
        try:
            node_id = node.nodeid.to_string()
        except Exception:  # pragma: no cover - defensive
            return
        self._adapter.on_local_change(node_id, value)

    def status_change_notification(self, status: Any) -> None:
        logger.debug("OPC UA server status change: %s", status)

    def event_notification(self, event: Any) -> None:
        logger.debug("OPC UA server event: %s", event)
