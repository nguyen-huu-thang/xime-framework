from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from typing import Any

from xime.core.context import request_context
from xime.core.security import clear_security

from ._decorators import MqttKind
from ._runtime import MqttConnection
from ._topic import topic_matches
from .routing._builder import ResolvedMqttRoute

logger = logging.getLogger("xime.mqtt")

# Cap on how many DISTINCT offending reply topics get their own warning line.
# Số topic reply vi phạm KHÁC NHAU được cấp một dòng cảnh báo riêng.
_MAX_WARNED_REPLY_TOPICS = 64


class MqttDispatcher:
    """Routes one incoming MQTT message to every matching handler.

    Pure of transport I/O: it takes the already-decoded (topic, payload,
    properties) of a message plus the live connection (for RPC replies), so it
    can be unit-tested with a fake connection. The adapter feeds it messages.
    Tách khỏi I/O: nhận (topic, payload, properties) + connection để test bằng
    fake; adapter bơm message vào.

    Per-message lifecycle mirrors every other adapter: a fresh request_id is set
    in request_context, and request_context.clear() + clear_security() run in a
    finally block so context never leaks between messages.
    """

    def __init__(
        self,
        routes: list[ResolvedMqttRoute],
        connection: MqttConnection,
        error_mappings: dict[type[Exception], str] | None = None,
        *,
        reply_properties_factory: Callable[[bytes | None], Any] | None = None,
        allowed_reply_topics: list[str] | None = None,
    ) -> None:
        self._routes = routes
        self._connection = connection
        self._error_mappings = error_mappings or {}
        self._reply_props = reply_properties_factory or _default_reply_properties
        # F17: topic filters an RPC reply is expected to land on. Empty = no
        # policy declared, so nothing is reported per message (the adapter warns
        # once at startup instead). Non-empty = advisory: a reply outside the
        # list is still published, but named in a WARNING.
        # F17: filter mà reply RPC được phép rơi vào. Rỗng = chưa khai chính
        # sách nên không cảnh báo theo từng message (adapter cảnh báo một lần
        # lúc khởi động). Có khai = chỉ cảnh báo, reply vẫn được gửi.
        self._allowed_reply_topics = list(allowed_reply_topics or [])
        # Bounded dedupe so a caller cannot turn one warning into a log flood by
        # varying the topic. Past the cap we say so once and stop listing.
        # Chặn theo số topic KHÁC NHAU để bên gọi không biến cảnh báo thành lũ
        # log bằng cách đổi topic. Quá ngưỡng thì nói một câu rồi thôi liệt kê.
        self._warned_reply_topics: set[str] = set()
        self._reply_warn_capped = False
        # Subscription Identifier -> route, for exact dispatch when the broker
        # reports which subscription(s) matched (MQTT v5). Avoids re-matching by
        # topic and the double-dispatch overlapping filters can cause.
        # Map Subscription Identifier -> route để dispatch chính xác theo broker.
        self._by_sub_id = {
            r.subscription_id: r for r in routes if r.subscription_id is not None
        }

    async def dispatch(
        self,
        topic: str,
        payload: bytes,
        properties: Any = None,
        message: Any = None,
        subscription_ids: Any = None,
    ) -> None:
        """Dispatch a message to the matching route(s).

        When the broker reports Subscription Identifier(s) (MQTT v5), dispatch
        to exactly those route(s) - each broker delivery hits one route, so
        overlapping filters cannot double-fire. Otherwise fall back to matching
        every route by topic filter.
        Có Subscription Identifier (MQTT v5) -> dispatch đúng route đó (không
        double-fire khi filter chồng lấn); không có -> khớp theo topic filter.

        Each matching handler runs under its own request_id; handler errors are
        logged (and, for RPC, reported on the reply topic) but never abort the
        loop, so one failing handler does not stop the others.
        """
        matched = self._match(topic, subscription_ids)
        for route in matched:
            request_context.set("request_id", str(uuid.uuid4()))
            try:
                if route.info.kind is MqttKind.SUBSCRIBE:
                    await self._invoke_subscribe(route, topic, payload, message)
                else:
                    await self._invoke_rpc(route, topic, payload, properties)
            except Exception:
                logger.exception(
                    "MQTT handler failed for topic %r (filter %r)",
                    topic, route.info.topic,
                )
            finally:
                request_context.clear()
                clear_security()

    def _match(self, topic: str, subscription_ids: Any) -> list[ResolvedMqttRoute]:
        """Pick routes by Subscription Identifier when present, else by topic."""
        if subscription_ids:
            ids = (
                subscription_ids
                if isinstance(subscription_ids, (list, tuple))
                else [subscription_ids]
            )
            # dict.fromkeys: dedupe ids while preserving order.
            return [
                self._by_sub_id[sid]
                for sid in dict.fromkeys(ids)
                if sid in self._by_sub_id
            ]
        return [r for r in self._routes if topic_matches(r.info.topic, topic)]

    # ------------------------------------------------------------------
    # Handler invocation
    # ------------------------------------------------------------------

    async def _invoke_subscribe(
        self, route: ResolvedMqttRoute, topic: str, payload: bytes, message: Any
    ) -> None:
        available = {"payload": payload, "topic": topic, "message": message}
        kwargs = {name: available[name] for name in route.subscribe_params}
        await route.bound(**kwargs)

    async def _invoke_rpc(
        self, route: ResolvedMqttRoute, topic: str, payload: bytes, properties: Any
    ) -> None:
        response_topic = getattr(properties, "ResponseTopic", None)
        correlation = getattr(properties, "CorrelationData", None)
        # Checked BEFORE the handler runs so the warning is emitted even when the
        # handler raises - the failing case is exactly the one worth seeing.
        # Kiểm TRƯỚC khi chạy handler để dòng cảnh báo vẫn xuất hiện kể cả khi
        # handler ném lỗi - đó đúng là ca đáng nhìn nhất.
        if response_topic:
            self._check_reply_topic(response_topic, route)
        try:
            request = route.request_type.model_validate_json(payload or b"{}")
            kwargs: dict[str, Any] = {route.request_param: request}
            if route.wants_topic:
                kwargs["topic"] = topic
            response = await route.bound(**kwargs)
            if response_topic:
                await self._reply(response_topic, response.model_dump_json().encode(), correlation)
        except Exception as exc:
            # RPC errors are reported to the caller on the reply topic (if any),
            # never leaking internal detail for unmapped exceptions.
            # Lỗi RPC báo về reply topic (nếu có), không lộ chi tiết nội bộ.
            if response_topic:
                code, msg = self._map_error(exc)
                body = json.dumps({"error": {"code": code, "message": msg}}).encode()
                # Publishing the error reply is best-effort: a failure here must
                # NOT replace the original exception (which dispatch() logs).
                # Gửi reply lỗi là best-effort: lỗi ở đây KHÔNG được thay thế lỗi gốc.
                try:
                    await self._reply(response_topic, body, correlation)
                except Exception:
                    logger.exception(
                        "MQTT: failed to publish RPC error reply to %r", response_topic
                    )
            raise

    def _check_reply_topic(self, response_topic: str, route: ResolvedMqttRoute) -> None:
        """Warn when an RPC reply is about to leave the declared topic list (F17).

        Advisory by design: the reply is still published. The chosen trade-off is
        that breaking the SILENCE is what matters - an operator who has declared
        `reply_topics` gets told when reality disagrees, and one who has not is
        told once at startup rather than once per message.
        Cố ý chỉ cảnh báo, reply vẫn được gửi. Thứ đáng giá ở đây là phá vỡ SỰ IM
        LẶNG: ai đã khai `reply_topics` thì được báo khi thực tế lệch khỏi lời
        khai, ai chưa khai thì được báo một lần lúc khởi động.
        """
        if not self._allowed_reply_topics:
            return
        if any(topic_matches(f, response_topic) for f in self._allowed_reply_topics):
            return
        if response_topic in self._warned_reply_topics:
            return
        if len(self._warned_reply_topics) >= _MAX_WARNED_REPLY_TOPICS:
            if not self._reply_warn_capped:
                self._reply_warn_capped = True
                logger.warning(
                    "MQTT RPC: more than %d distinct reply topics fell outside "
                    "mqtt.rpc.reply_topics; further ones are no longer listed "
                    "individually.",
                    _MAX_WARNED_REPLY_TOPICS,
                )
            return
        self._warned_reply_topics.add(response_topic)
        logger.warning(
            "MQTT RPC: reply for %r goes to caller-chosen topic %r, which matches "
            "no filter in mqtt.rpc.reply_topics %r. The reply is still sent. The "
            "caller picks this topic while WE publish it, so on a broker with "
            "per-client ACLs it reaches topics the caller may not write to.",
            route.info.topic, response_topic, self._allowed_reply_topics,
        )

    async def _reply(self, response_topic: str, body: bytes, correlation: bytes | None) -> None:
        await self._connection.publish(
            response_topic, body, qos=1, properties=self._reply_props(correlation)
        )

    def _map_error(self, exc: Exception) -> tuple[str, str]:
        for exc_type, code in self._error_mappings.items():
            if isinstance(exc, exc_type):
                return code, str(exc)
        return "INTERNAL", "Internal server error"


def _default_reply_properties(correlation: bytes | None) -> Any:
    """Build MQTT v5 PUBLISH properties carrying CorrelationData (lazy paho).

    Imported lazily so the module stays importable without paho installed; only
    actually publishing an RPC reply needs it.
    Import paho lười: chỉ khi thực sự trả reply RPC mới cần.
    """
    if correlation is None:
        return None
    from paho.mqtt.packettypes import PacketTypes
    from paho.mqtt.properties import Properties

    props = Properties(PacketTypes.PUBLISH)
    props.CorrelationData = correlation
    return props
