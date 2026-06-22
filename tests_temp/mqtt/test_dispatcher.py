"""MqttDispatcher: subscribe invocation, RPC reply, error handling, context (0.5)."""
import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from xime.adapters.mqtt import rpc, subscribe
from xime.adapters.mqtt._dispatcher import MqttDispatcher
from xime.adapters.mqtt.routing import MqttRouteBuilder
from xime.core.context import request_context


class _FakeApp:
    def __init__(self, *instances) -> None:
        self._by_type = {type(i): i for i in instances}

    def get(self, cls):
        return self._by_type[cls]


class _FakeConnection:
    """Records publish() calls; stands in for MqttConnection in RPC replies."""

    def __init__(self) -> None:
        self.published: list[dict] = []

    async def publish(self, topic, payload, *, qos=0, retain=False, properties=None, timeout=None):
        self.published.append(
            {"topic": topic, "payload": payload, "qos": qos, "properties": properties}
        )


# Reply properties factory that avoids paho: echoes the correlation data.
def _fake_props(correlation):
    return {"CorrelationData": correlation}


def _dispatcher(*instances, error_mappings=None):
    routes = MqttRouteBuilder(_FakeApp(*instances)).build([type(i) for i in instances])
    conn = _FakeConnection()
    disp = MqttDispatcher(
        routes, conn, error_mappings, reply_properties_factory=_fake_props
    )
    return disp, conn


class Req(BaseModel):
    n: int


class Resp(BaseModel):
    doubled: int


class TestSubscribe:
    @pytest.mark.asyncio
    async def test_handler_receives_payload_and_topic(self):
        seen = {}

        class C:
            @subscribe("sensors/+/temp")
            async def on(self, payload: bytes, topic: str) -> None:
                seen["payload"] = payload
                seen["topic"] = topic
                seen["request_id"] = request_context.get("request_id")

        disp, _ = _dispatcher(C())
        await disp.dispatch("sensors/a/temp", b"21.5")
        assert seen["payload"] == b"21.5"
        assert seen["topic"] == "sensors/a/temp"
        assert seen["request_id"]  # a request_id was set during handling

    @pytest.mark.asyncio
    async def test_context_cleared_after_dispatch(self):
        class C:
            @subscribe("a")
            async def on(self, payload: bytes) -> None: ...

        disp, _ = _dispatcher(C())
        await disp.dispatch("a", b"x")
        assert request_context.get("request_id") is None

    @pytest.mark.asyncio
    async def test_no_match_is_noop(self):
        called = []

        class C:
            @subscribe("a/b")
            async def on(self, payload: bytes) -> None:
                called.append(1)

        disp, _ = _dispatcher(C())
        await disp.dispatch("x/y", b"p")
        assert called == []

    @pytest.mark.asyncio
    async def test_multiple_matches_all_called(self):
        hits = []

        class C:
            @subscribe("sensors/#")
            async def wide(self, topic: str) -> None:
                hits.append("wide")

            @subscribe("sensors/+/temp")
            async def narrow(self, topic: str) -> None:
                hits.append("narrow")

        disp, _ = _dispatcher(C())
        await disp.dispatch("sensors/a/temp", b"1")
        assert sorted(hits) == ["narrow", "wide"]

    @pytest.mark.asyncio
    async def test_handler_error_does_not_break_loop(self):
        hits = []

        class C:
            @subscribe("a/#")
            async def boom(self, topic: str) -> None:
                raise RuntimeError("nope")

            @subscribe("a/b")
            async def ok(self, topic: str) -> None:
                hits.append("ok")

        disp, _ = _dispatcher(C())
        await disp.dispatch("a/b", b"x")  # must not raise
        assert hits == ["ok"]


class TestRpc:
    @pytest.mark.asyncio
    async def test_round_trip_publishes_reply(self):
        class C:
            @rpc("svc/double")
            async def double(self, request: Req) -> Resp:
                return Resp(doubled=request.n * 2)

        disp, conn = _dispatcher(C())
        props = SimpleNamespace(ResponseTopic="reply/1", CorrelationData=b"cid-1")
        await disp.dispatch("svc/double", json.dumps({"n": 21}).encode(), props)

        assert len(conn.published) == 1
        msg = conn.published[0]
        assert msg["topic"] == "reply/1"
        assert json.loads(msg["payload"]) == {"doubled": 42}
        assert msg["properties"] == {"CorrelationData": b"cid-1"}

    @pytest.mark.asyncio
    async def test_no_response_topic_skips_reply(self):
        ran = []

        class C:
            @rpc("svc/x")
            async def h(self, request: Req) -> Resp:
                ran.append(1)
                return Resp(doubled=request.n)

        disp, conn = _dispatcher(C())
        await disp.dispatch("svc/x", b'{"n": 1}', SimpleNamespace())
        assert ran == [1]
        assert conn.published == []

    @pytest.mark.asyncio
    async def test_error_reported_on_reply_topic_with_mapped_code(self):
        class Bad(Exception):
            pass

        class C:
            @rpc("svc/fail")
            async def h(self, request: Req) -> Resp:
                raise Bad("kaboom")

        disp, conn = _dispatcher(C(), error_mappings={Bad: "BAD_INPUT"})
        props = SimpleNamespace(ResponseTopic="reply/err", CorrelationData=b"c")
        await disp.dispatch("svc/fail", b'{"n": 1}', props)

        assert len(conn.published) == 1
        body = json.loads(conn.published[0]["payload"])
        assert body["error"]["code"] == "BAD_INPUT"
        assert body["error"]["message"] == "kaboom"

    @pytest.mark.asyncio
    async def test_unmapped_error_uses_generic_message(self):
        class C:
            @rpc("svc/fail")
            async def h(self, request: Req) -> Resp:
                raise RuntimeError("internal secret detail")

        disp, conn = _dispatcher(C())
        props = SimpleNamespace(ResponseTopic="reply/err", CorrelationData=b"c")
        await disp.dispatch("svc/fail", b'{"n": 1}', props)

        body = json.loads(conn.published[0]["payload"])
        assert body["error"]["code"] == "INTERNAL"
        assert "secret" not in body["error"]["message"]

    @pytest.mark.asyncio
    async def test_context_cleared_after_rpc_error(self):
        class C:
            @rpc("svc/fail")
            async def h(self, request: Req) -> Resp:
                raise RuntimeError("x")

        disp, _ = _dispatcher(C())
        await disp.dispatch("svc/fail", b'{"n": 1}', SimpleNamespace(ResponseTopic="r", CorrelationData=b"c"))
        assert request_context.get("request_id") is None


def _dispatcher_with_ids(*instances, error_mappings=None):
    """Build a dispatcher whose routes carry MQTT v5 Subscription Identifiers
    (1-based), like MqttAdapter.start assigns at runtime."""
    routes = MqttRouteBuilder(_FakeApp(*instances)).build([type(i) for i in instances])
    for i, route in enumerate(routes):
        route.subscription_id = i + 1
    conn = _FakeConnection()
    disp = MqttDispatcher(routes, conn, error_mappings, reply_properties_factory=_fake_props)
    return disp, conn, routes


class TestSubscriptionIdRouting:
    @pytest.mark.asyncio
    async def test_subscription_id_routes_to_exact_handler(self):
        hits = []

        class C:
            @subscribe("sensors/#")
            async def wide(self, topic: str) -> None:
                hits.append("wide")

            @subscribe("sensors/+/temp")
            async def narrow(self, topic: str) -> None:
                hits.append("narrow")

        disp, _, routes = _dispatcher_with_ids(C())
        narrow_id = next(r.subscription_id for r in routes if r.info.topic == "sensors/+/temp")

        # Broker reports only the narrow subscription matched -> only narrow runs,
        # even though the topic also matches "sensors/#".
        await disp.dispatch("sensors/a/temp", b"1", subscription_ids=[narrow_id])
        assert hits == ["narrow"]

    @pytest.mark.asyncio
    async def test_overlapping_delivery_fires_each_route_once(self):
        hits = []

        class C:
            @subscribe("a/#")
            async def wide(self, topic: str) -> None:
                hits.append("wide")

            @subscribe("a/b")
            async def exact(self, topic: str) -> None:
                hits.append("exact")

        disp, _, routes = _dispatcher_with_ids(C())
        ids = [r.subscription_id for r in routes]
        # Broker says both subscriptions matched in one delivery -> each route
        # fires exactly once (no duplication).
        await disp.dispatch("a/b", b"x", subscription_ids=ids)
        assert sorted(hits) == ["exact", "wide"]

    @pytest.mark.asyncio
    async def test_duplicate_ids_deduped(self):
        hits = []

        class C:
            @subscribe("a/#")
            async def h(self, topic: str) -> None:
                hits.append(1)

        disp, _, routes = _dispatcher_with_ids(C())
        sid = routes[0].subscription_id
        await disp.dispatch("a/b", b"x", subscription_ids=[sid, sid])
        assert hits == [1]  # handler runs once despite duplicate ids

    @pytest.mark.asyncio
    async def test_falls_back_to_topic_match_without_ids(self):
        hits = []

        class C:
            @subscribe("sensors/#")
            async def wide(self, topic: str) -> None:
                hits.append("wide")

            @subscribe("sensors/+/temp")
            async def narrow(self, topic: str) -> None:
                hits.append("narrow")

        disp, _, _ = _dispatcher_with_ids(C())
        # No subscription ids (e.g. v3 broker) -> match all routes by topic.
        await disp.dispatch("sensors/a/temp", b"1")
        assert sorted(hits) == ["narrow", "wide"]
