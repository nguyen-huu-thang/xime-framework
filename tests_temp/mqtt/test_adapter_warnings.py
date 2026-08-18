"""MqttAdapter startup warnings (F17): unrestricted RPC reply topics.

Same shape as GrpcAdapter._warn_insecure_mode - call the method directly with a
built config instead of standing up a broker.
Cùng khuôn `GrpcAdapter._warn_insecure_mode`: gọi thẳng method với config dựng
sẵn, không cần broker thật.
"""
import pytest
from pydantic import BaseModel

from xime.adapters.mqtt import rpc, subscribe
from xime.adapters.mqtt._adapter import MqttAdapter
from xime.adapters.mqtt._config import MqttConfig
from xime.adapters.mqtt.routing import MqttRouteBuilder
from xime.core.config.runtime import RuntimeConfig

_LOGGER = "xime.mqtt"


class Req(BaseModel):
    n: int


class Resp(BaseModel):
    n: int


class _FakeApp:
    def __init__(self, *instances) -> None:
        self._by_type = {type(i): i for i in instances}

    def get(self, cls):
        return self._by_type[cls]


def _routes(*instances):
    return MqttRouteBuilder(_FakeApp(*instances)).build([type(i) for i in instances])


def _adapter(mqtt_block: dict):
    adapter = MqttAdapter()
    adapter._config = MqttConfig.resolve(
        RuntimeConfig.from_dict({"mqtt": {"host": "b", **mqtt_block}}), "svc"
    )
    return adapter


class _RpcController:
    @rpc("svc/x")
    async def h(self, request: Req) -> Resp:
        return Resp(n=request.n)


class _SubOnlyController:
    @subscribe("sensors/#")
    async def h(self, payload: bytes) -> None:
        return None


class TestUnrestrictedRpcReplyWarning:
    """Paired tests: it must fire exactly when it is useful, and be silent otherwise.

    Kiểm theo CẶP: phải kêu đúng lúc có ích, và im ở mọi lúc khác. Chỉ kiểm vế
    kêu thì bản hiện thực "luôn kêu" cũng qua, mà bản đó dạy người ta bỏ qua log.
    """

    def test_rpc_without_policy_warns(self, caplog):
        adapter = _adapter({})
        with caplog.at_level("WARNING", logger=_LOGGER):
            adapter._warn_unrestricted_rpc_replies(_routes(_RpcController()))
        assert "mqtt.rpc.reply_topics" in caplog.text

    def test_rpc_with_policy_is_silent(self, caplog):
        """Policy declared -> the dispatcher reports per message instead."""
        adapter = _adapter({"rpc": {"reply_topics": ["ok/#"]}})
        with caplog.at_level("WARNING", logger=_LOGGER):
            adapter._warn_unrestricted_rpc_replies(_routes(_RpcController()))
        assert caplog.text == ""

    def test_no_rpc_route_is_silent(self, caplog):
        """A pub/sub-only client never publishes to a caller-chosen topic.

        Client chỉ pub/sub thì không bao giờ publish vào topic do bên gọi đặt,
        nên cảnh báo ở đây là cảnh báo sai chỗ.
        """
        adapter = _adapter({})
        with caplog.at_level("WARNING", logger=_LOGGER):
            adapter._warn_unrestricted_rpc_replies(_routes(_SubOnlyController()))
        assert caplog.text == ""
