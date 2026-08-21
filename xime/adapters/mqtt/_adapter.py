from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from xime.core.bootstrap.adapter import SCALING_SHARDED, Adapter

from ._config import MqttConfig, mqtt_registry
from ._decorators import MqttKind
from ._dispatcher import MqttDispatcher
from .routing._builder import MqttRouteBuilder
from .routing._scanner import MqttControllerScanner

if TYPE_CHECKING:
    from xime.core.bootstrap.application import Application

logger = logging.getLogger("xime.mqtt")


class MqttAdapter(
    Adapter,
    scaling=SCALING_SHARDED,
    unique_per_process=("client_id",),
    disjoint_per_process=("topics",),
):
    """MQTT adapter - message-driven (pub/sub) transport for IoT / embedded peers.

    Register via app.use() and start via app.run():

        app = Application()
        app.use(MqttAdapter())
        app.run()

    Unlike web/grpc/socket (request/response), MQTT is pub/sub: the adapter
    subscribes to the topic filters declared by @subscribe/@rpc controllers and
    dispatches each incoming message. @rpc additionally publishes a reply to the
    request's ResponseTopic (MQTT v5).
    Khác web/grpc/socket (request/response), MQTT là pub/sub.

    Lifecycle (driven by Application._run_async):
        1. Application.start() - DI container fully built
        2. MqttAdapter.start(app) - connect, subscribe, dispatch until stopped
        3. MqttAdapter.stop() - cancel handlers, disconnect cleanly

    Resilience: on connection loss the adapter reconnects and re-subscribes all
    topics. Message handlers run in bounded-concurrency tasks (max_concurrency),
    applying backpressure to the receive loop when saturated.

    Ordering: with max_concurrency > 1 messages are dispatched CONCURRENTLY, so
    per-topic delivery order is NOT preserved. Set max_concurrency=1 for strict
    sequential, in-order processing (lower throughput).
    Thứ tự: max_concurrency > 1 -> xử lý đồng thời, KHÔNG giữ thứ tự per-topic;
    đặt =1 để xử lý tuần tự đúng thứ tự.

    The publisher (MqttPublisher) binds to the connection of the default
    client_id; run the adapter with the default id for the publisher to work.
    Publisher bám vào connection của client_id mặc định.
    """

    # Khoá tầng hai trong khối `processes:` (`processes.<p>.mqtt.<id>`).
    adapter_kind = "mqtt"

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

    def __init__(self, target_id: str = "default", path: str | None = None) -> None:
        # ⚠ `target_id`, không phải `client_id`. Chữ `client_id` đã mang HAI
        # nghĩa NGƯỢC NHAU trong cùng framework: ở gRPC client SDK
        # (`grpc.clients.<client_id>`) nó là tên **service đích**, ở đây nó là
        # định danh **phiên của chính ta** trên broker. Một cái là tên người
        # kia, một cái là tên của mình.
        self._target_id = target_id
        # Identity used by Application.use() to reject a duplicate registration.
        # MQTT makes this worse than a wasted connection: a broker only allows
        # one session per client id and kicks the older one off, so two adapters
        # on the same id fight each other in a reconnect loop.
        # MQTT chỉ cho MỘT phiên trên mỗi client id và đá phiên cũ ra, nên hai
        # adapter cùng id sẽ đánh nhau trong vòng lặp reconnect.
        self.adapter_id = target_id
        self._slot: object | None = None
        self._config: MqttConfig | None = None
        self._connection = mqtt_registry.connection(target_id)
        # Claim the client_id at construction (app.use time), well before any
        # publish, so MqttPublisher bound to this id won't fail fast or hang.
        # Nhận client_id ngay lúc app.use, trước mọi publish.
        self._connection.mark_served()
        self._dispatcher: MqttDispatcher | None = None
        # (topic_filter, qos, subscription_id) per route.
        self._subscriptions: list[tuple[str, int, int]] = []
        self._stopping = False
        self._tasks: set[asyncio.Task] = set()
        self._sem: asyncio.Semaphore | None = None

    # ------------------------------------------------------------------
    # Adapter protocol
    # ------------------------------------------------------------------

    async def start(self, app: Application) -> None:
        """Build the route table, then connect/subscribe/dispatch with reconnect."""
        try:
            import aiomqtt  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "MqttAdapter requires aiomqtt. Run: pip install 'xime[mqtt]'"
            ) from None

        from xime.core.config.runtime import RuntimeConfig
        runtime: RuntimeConfig = app.get(RuntimeConfig)
        self._config = MqttConfig.resolve(runtime, self._target_id)
        self._sem = asyncio.Semaphore(self._config.max_concurrency)

        # Build the dispatch table from scanned controllers (DI is ready).
        controllers = MqttControllerScanner().find_controllers(*mqtt_registry.get_packages())
        routes = MqttRouteBuilder(app).build(controllers)
        # Assign a unique MQTT v5 Subscription Identifier per route so the broker
        # reports exactly which subscription matched -> the dispatcher routes by
        # that id and overlapping filters never double-fire.
        # Gán Subscription Identifier (MQTT v5) cho mỗi route -> broker báo đúng
        # subscription khớp, dispatcher route theo id, filter chồng lấn không
        # double-fire.
        for i, route in enumerate(routes):
            route.subscription_id = i + 1
        self._dispatcher = MqttDispatcher(
            routes,
            self._connection,
            mqtt_registry.get_error_mappings(),
            allowed_reply_topics=self._config.rpc.reply_topics,
        )
        # (filter, qos, subscription_id) to (re-)issue on every (re)connect.
        self._subscriptions = [
            (r.info.topic, r.info.qos, route_id)
            for r in routes
            if (route_id := r.subscription_id) is not None
        ]

        self._warn_insecure_mode()
        self._warn_unrestricted_rpc_replies(routes)

    async def serve(self) -> None:
        """Vòng kết nối lại chạy suốt vòng đời.

        ⚠ Kết nối tới broker nằm ở đây chứ không ở `start()`: adapter này
        vốn thiết kế để **chịu được broker chưa lên**, nên *"chưa nối được"*
        không phải lỗi khởi động.
        """
        await self._run_forever()

    def _warn_insecure_mode(self) -> None:
        """Say out loud, once, that this connection is not protected.

        MQTT without TLS is a defensible default for a lab broker on localhost,
        but sending a username and password over it is not: they travel in the
        clear in the CONNECT packet, and so does every payload afterwards.
        MQTT không TLS là mặc định chấp nhận được với broker trong phòng lab,
        nhưng gửi kèm tài khoản/mật khẩu thì không: chúng đi trên dây dạng rõ
        ngay trong gói CONNECT, và mọi payload sau đó cũng vậy.
        """
        cfg = self._config
        if cfg is None or cfg.tls is not None:
            return
        if cfg.username is not None or cfg.password is not None:
            logger.warning(
                "MQTT client '%s' sends credentials to %s:%d over a PLAINTEXT "
                "connection - username and password travel in the clear. "
                "Configure mqtt.tls.",
                cfg.client_id, cfg.host, cfg.port,
            )
        else:
            logger.warning(
                "MQTT client '%s' is connected to %s:%d without TLS: payloads "
                "are unencrypted and the broker's identity is not verified.",
                cfg.client_id, cfg.host, cfg.port,
            )

    def _warn_unrestricted_rpc_replies(self, routes: list) -> None:
        """Say once that RPC replies go wherever the caller asks (F17).

        Only fires when this client actually serves `@rpc`, and only when no
        `mqtt.rpc.reply_topics` is declared - otherwise the dispatcher reports
        per message. One line at startup beats one line per message: a check
        that cries wolf is a check somebody switches off.
        Chỉ kêu khi client này thực sự phục vụ `@rpc` và chưa khai
        `mqtt.rpc.reply_topics`; có khai rồi thì dispatcher báo theo từng
        message. Một dòng lúc khởi động hơn một dòng mỗi message - phép dò kêu
        oan là phép dò sẽ bị tắt.
        """
        cfg = self._config
        if cfg is None or cfg.rpc.reply_topics:
            return
        if not any(r.info.kind is MqttKind.RPC for r in routes):
            return
        logger.warning(
            "MQTT client '%s' serves RPC handlers and publishes each reply to the "
            "topic the CALLER names, using this client's broker credentials. On a "
            "broker with per-client ACLs a caller can therefore reach topics its "
            "own ACL forbids. Declare mqtt.rpc.reply_topics to have replies "
            "outside the expected topics reported.",
            cfg.client_id,
        )

    async def stop(self) -> None:
        """Stop reconnecting, cancel in-flight handlers, drop the connection."""
        self._stopping = True
        for task in list(self._tasks):
            task.cancel()
        self._tasks.clear()
        self._connection.detach()

    # ------------------------------------------------------------------
    # Connection loop
    # ------------------------------------------------------------------

    async def _run_forever(self) -> None:
        import aiomqtt

        assert self._config is not None
        cfg = self._config
        while not self._stopping:
            try:
                async with self._build_client(aiomqtt) as client:
                    self._connection.attach(client)
                    await self._subscribe_all(client)
                    async for message in client.messages:
                        await self._handle_message(message)
            except aiomqtt.MqttError as exc:
                if self._stopping:
                    break
                logger.warning(
                    "MQTT connection lost (%s); reconnecting in %.1fs",
                    exc, cfg.reconnect_delay,
                )
            finally:
                self._connection.detach()
            if self._stopping:
                break
            await asyncio.sleep(cfg.reconnect_delay)

    def _build_client(self, aiomqtt):
        cfg = self._config
        assert cfg is not None
        kwargs: dict = {
            "hostname": cfg.host,
            "port": cfg.port,
            "identifier": cfg.client_id,
            "keepalive": cfg.keepalive,
            # MQTT v5 is required for RPC ResponseTopic/CorrelationData.
            "protocol": aiomqtt.ProtocolVersion.V5,
        }
        if cfg.username is not None:
            kwargs["username"] = cfg.username
        if cfg.password is not None:
            kwargs["password"] = cfg.password
        if cfg.tls is not None:
            kwargs["tls_params"] = aiomqtt.TLSParameters(
                ca_certs=cfg.tls.ca_certs,
                certfile=cfg.tls.certfile,
                keyfile=cfg.tls.keyfile,
            )
        if cfg.lwt is not None:
            kwargs["will"] = aiomqtt.Will(
                topic=cfg.lwt.topic,
                payload=cfg.lwt.payload,
                qos=cfg.lwt.qos,
                retain=cfg.lwt.retain,
            )
        return aiomqtt.Client(**kwargs)

    async def _subscribe_all(self, client) -> None:
        for topic, qos, sub_id in self._subscriptions:
            await client.subscribe(
                topic, qos=qos, properties=_subscribe_properties(sub_id)
            )

    async def _handle_message(self, message) -> None:
        """Spawn a bounded-concurrency task to dispatch one message.

        Acquiring the semaphore before scheduling applies backpressure: when
        max_concurrency handlers are in flight, the receive loop blocks here.
        Acquire semaphore trước khi schedule -> backpressure khi đầy.
        """
        assert self._sem is not None and self._dispatcher is not None
        await self._sem.acquire()
        task = asyncio.create_task(self._dispatch_one(message))
        self._tasks.add(task)

        def _done(t: asyncio.Task) -> None:
            self._tasks.discard(t)
            self._sem.release()  # type: ignore[union-attr]

        task.add_done_callback(_done)

    async def _dispatch_one(self, message) -> None:
        topic = getattr(message.topic, "value", str(message.topic))
        payload = message.payload
        if isinstance(payload, str):
            payload = payload.encode()
        elif payload is None:
            payload = b""
        properties = getattr(message, "properties", None)
        # MQTT v5: broker echoes the matching Subscription Identifier(s) so the
        # dispatcher routes to exactly the right handler(s). None on a v3 broker
        # or QoS path without the property -> dispatcher falls back to topic match.
        # MQTT v5: broker trả Subscription Identifier khớp -> dispatcher route đúng
        # handler. None (broker v3) -> dispatcher fallback khớp topic.
        sub_ids = getattr(properties, "SubscriptionIdentifier", None)
        await self._dispatcher.dispatch(  # type: ignore[union-attr]
            topic, payload, properties, message, subscription_ids=sub_ids
        )


def _subscribe_properties(subscription_id: int):
    """Build MQTT v5 SUBSCRIBE properties carrying the Subscription Identifier.

    Imported lazily so the module stays importable without paho installed.
    Import paho lười để module vẫn import được khi chưa cài paho.
    """
    from paho.mqtt.packettypes import PacketTypes
    from paho.mqtt.properties import Properties

    props = Properties(PacketTypes.SUBSCRIBE)
    props.SubscriptionIdentifier = subscription_id
    return props
