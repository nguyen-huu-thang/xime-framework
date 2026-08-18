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


# ---------------------------------------------------------------------------
# F17 - reply topic do BEN GOI chi dinh, canh bao chu khong chan
# ---------------------------------------------------------------------------

def _rpc_dispatcher(allowed=None):
    """Build a dispatcher serving one @rpc route, with an optional reply policy."""
    class C:
        @rpc("svc/double")
        async def double(self, request: Req) -> Resp:
            return Resp(doubled=request.n * 2)

    routes = MqttRouteBuilder(_FakeApp(C())).build([C])
    conn = _FakeConnection()
    disp = MqttDispatcher(
        routes, conn, None,
        reply_properties_factory=_fake_props,
        allowed_reply_topics=allowed,
    )
    return disp, conn


async def _call(disp, reply_to):
    props = SimpleNamespace(ResponseTopic=reply_to, CorrelationData=b"c")
    await disp.dispatch("svc/double", json.dumps({"n": 1}).encode(), props)


class TestRpcReplyTopicPolicy:
    """F17: the caller names the reply topic, WE publish it with our credentials.

    Chosen behaviour (chủ dự án chốt 2026-08-18): warn, do not block. So the
    tests come in PAIRS - one that the warning fires, one that it does NOT.
    A test for only the first half would also pass an implementation that warns
    on every single reply, and that implementation is worse than none: a check
    which cries wolf is a check somebody switches off.
    Hành vi đã chốt: cảnh báo chứ không chặn. Nên test đi thành CẶP - một cái
    bắt cảnh báo phải kêu, một cái bắt nó phải IM. Chỉ có vế đầu thì bản hiện
    thực "kêu với mọi reply" cũng qua, mà bản đó còn tệ hơn không có gì.
    """

    @pytest.mark.asyncio
    async def test_reply_outside_policy_is_still_published(self, caplog):
        """Advisory, not enforcing: the message must still go out."""
        disp, conn = _rpc_dispatcher(allowed=["nhamay/reply/#"])
        with caplog.at_level("WARNING", logger="xime.mqtt"):
            await _call(disp, "nhamay/BT-99/lenh")

        assert len(conn.published) == 1
        assert conn.published[0]["topic"] == "nhamay/BT-99/lenh"
        assert "nhamay/BT-99/lenh" in caplog.text

    @pytest.mark.asyncio
    async def test_reply_inside_policy_is_silent(self, caplog):
        """Other half of the pair - no warning when reality matches the policy."""
        disp, conn = _rpc_dispatcher(allowed=["nhamay/reply/#"])
        with caplog.at_level("WARNING", logger="xime.mqtt"):
            await _call(disp, "nhamay/reply/abc")

        assert len(conn.published) == 1
        assert caplog.text == ""

    @pytest.mark.asyncio
    async def test_no_policy_declared_is_silent_per_message(self, caplog):
        """Nothing declared -> the adapter warns ONCE at startup, not per message.

        Warning here instead would put one line on every RPC of every app that
        has not opted in, which is how a warning becomes noise.
        Chưa khai gì thì adapter cảnh báo MỘT lần lúc khởi động; kêu ở đây là
        mỗi RPC một dòng, và đó là cách một cảnh báo trở thành tiếng ồn.
        """
        disp, conn = _rpc_dispatcher(allowed=None)
        with caplog.at_level("WARNING", logger="xime.mqtt"):
            await _call(disp, "bat/ky/dau")

        assert len(conn.published) == 1
        assert caplog.text == ""

    @pytest.mark.asyncio
    async def test_same_offending_topic_warns_once(self, caplog):
        disp, _ = _rpc_dispatcher(allowed=["ok/#"])
        with caplog.at_level("WARNING", logger="xime.mqtt"):
            for _ in range(5):
                await _call(disp, "xau/mot")

        assert caplog.text.count("xau/mot") == 1

    @pytest.mark.asyncio
    async def test_distinct_offending_topics_are_capped(self, caplog):
        """A caller must not turn one warning into a log flood by varying topics.

        Bên gọi không được biến một cảnh báo thành lũ log bằng cách đổi topic.
        """
        from xime.adapters.mqtt._dispatcher import _MAX_WARNED_REPLY_TOPICS as CAP

        disp, _ = _rpc_dispatcher(allowed=["ok/#"])
        with caplog.at_level("WARNING", logger="xime.mqtt"):
            for i in range(CAP + 10):
                await _call(disp, f"xau/{i}")

        lines = [r for r in caplog.records if r.levelname == "WARNING"]
        # CAP individual lines + exactly one "stopped listing" line.
        assert len(lines) == CAP + 1
        assert "no longer listed" in lines[-1].getMessage()

    @pytest.mark.asyncio
    async def test_warning_fires_even_when_the_handler_raises(self, caplog):
        """The check runs BEFORE the handler - the failing case is the one to see."""
        class Boom(Exception):
            pass

        class C:
            @rpc("svc/fail")
            async def h(self, request: Req) -> Resp:
                raise Boom("no")

        routes = MqttRouteBuilder(_FakeApp(C())).build([C])
        conn = _FakeConnection()
        disp = MqttDispatcher(
            routes, conn, None,
            reply_properties_factory=_fake_props,
            allowed_reply_topics=["ok/#"],
        )
        with caplog.at_level("WARNING", logger="xime.mqtt"):
            props = SimpleNamespace(ResponseTopic="xau/x", CorrelationData=b"c")
            await disp.dispatch("svc/fail", json.dumps({"n": 1}).encode(), props)

        assert "xau/x" in caplog.text
        # The error reply still went out on the caller's topic.
        assert conn.published[0]["topic"] == "xau/x"
