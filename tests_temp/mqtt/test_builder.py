"""MqttRouteBuilder resolution + fail-fast validation (0.5)."""
import pytest
from pydantic import BaseModel

from xime.adapters.mqtt import rpc, subscribe
from xime.adapters.mqtt._decorators import MqttKind
from xime.adapters.mqtt.routing import MqttRouteBuilder
from xime.core.exception.framework import StartupException


class _FakeApp:
    """Minimal Application stand-in: resolves controller types to instances."""

    def __init__(self, *instances) -> None:
        self._by_type = {type(i): i for i in instances}

    def get(self, cls):
        if cls not in self._by_type:
            raise KeyError(cls)
        return self._by_type[cls]


class Req(BaseModel):
    x: int


class Resp(BaseModel):
    y: int


def _build(*instances):
    builder = MqttRouteBuilder(_FakeApp(*instances))
    return builder.build([type(i) for i in instances])


class TestResolution:
    def test_subscribe_params_detected(self):
        class C:
            @subscribe("a/+/b", qos=1)
            async def on(self, payload: bytes, topic: str) -> None: ...

        routes = _build(C())
        assert len(routes) == 1
        r = routes[0]
        assert r.info.kind is MqttKind.SUBSCRIBE
        assert r.info.qos == 1
        assert r.subscribe_params == ("payload", "topic")

    def test_subscribe_no_params(self):
        class C:
            @subscribe("a")
            async def on(self) -> None: ...

        routes = _build(C())
        assert routes[0].subscribe_params == ()

    def test_rpc_models_inferred(self):
        class C:
            @rpc("svc/echo")
            async def echo(self, request: Req) -> Resp: ...

        routes = _build(C())
        r = routes[0]
        assert r.info.kind is MqttKind.RPC
        assert r.request_type is Req and r.response_type is Resp
        assert r.wants_topic is False

    def test_rpc_wants_topic(self):
        class C:
            @rpc("svc/echo")
            async def echo(self, request: Req, topic: str) -> Resp: ...

        assert _build(C())[0].wants_topic is True


class TestFailFast:
    def test_non_async_handler(self):
        class C:
            @subscribe("a")
            def on(self, payload: bytes) -> None: ...

        with pytest.raises(StartupException, match="async def"):
            _build(C())

    def test_invalid_filter(self):
        class C:
            @subscribe("a/#/b")
            async def on(self, payload: bytes) -> None: ...

        with pytest.raises(StartupException, match="invalid MQTT topic filter"):
            _build(C())

    def test_bad_qos(self):
        class C:
            @subscribe("a", qos=5)
            async def on(self, payload: bytes) -> None: ...

        with pytest.raises(StartupException, match="qos must be"):
            _build(C())

    def test_subscribe_unexpected_param(self):
        class C:
            @subscribe("a")
            async def on(self, payload: bytes, bogus: str) -> None: ...

        with pytest.raises(StartupException, match="unexpected parameter"):
            _build(C())

    def test_rpc_missing_request(self):
        class C:
            @rpc("svc")
            async def h(self) -> Resp: ...

        with pytest.raises(StartupException, match="request"):
            _build(C())

    def test_rpc_bad_return(self):
        class C:
            @rpc("svc")
            async def h(self, request: Req) -> dict: ...

        with pytest.raises(StartupException, match="return type"):
            _build(C())

    def test_duplicate_filter(self):
        class C:
            @subscribe("dup")
            async def a(self, payload: bytes) -> None: ...

            @subscribe("dup")
            async def b(self, payload: bytes) -> None: ...

        with pytest.raises(StartupException, match="Duplicate MQTT Topic Filter"):
            _build(C())

    def test_controller_not_in_di(self):
        class C:
            @subscribe("a")
            async def on(self, payload: bytes) -> None: ...

        builder = MqttRouteBuilder(_FakeApp())  # empty app
        with pytest.raises(RuntimeError, match="not registered in the DI container"):
            builder.build([C])
