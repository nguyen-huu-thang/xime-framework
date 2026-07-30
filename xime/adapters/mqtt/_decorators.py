from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

# Attribute name used to mark MQTT handler methods — internal to the framework.
# Mirrors ROUTE_ATTR (web) / ENDPOINT_ATTR (contract).
MQTT_ATTR = "_xime_mqtt_info"


class MqttKind(Enum):
    """Whether a handler is fire-and-forget (SUBSCRIBE) or request/reply (RPC)."""

    SUBSCRIBE = "subscribe"
    RPC = "rpc"


@dataclass
class MqttHandlerInfo:
    """Metadata attached to a controller method by @subscribe / @rpc.

    `topic` is an MQTT subscription filter (wildcards + / # allowed). `qos` is
    the subscription QoS (0/1/2). For RPC, `qos` also applies to the reply
    publish unless overridden by the request's response properties.
    """

    kind: MqttKind
    topic: str
    qos: int = 0


def subscribe(topic: str, *, qos: int = 0) -> Callable:
    """Mark a controller method as an MQTT subscription (fire-and-forget).

    The handler receives the raw message; the framework does NOT deserialize the
    payload (consistent with StorageService/CacheService: mechanism, not policy).
    Expected signature (parameters matched by type hint, all optional):

        @subscribe("sensors/+/temperature", qos=1)
        async def on_temp(self, payload: bytes, topic: str) -> None: ...

    Handler nhận message thô; framework KHÔNG tự deserialize payload.
    """
    def decorator(func: Callable) -> Callable:
        setattr(func, MQTT_ATTR, MqttHandlerInfo(MqttKind.SUBSCRIBE, topic, qos))
        return func

    return decorator


def rpc(topic: str, *, qos: int = 0) -> Callable:
    """Mark a controller method as an MQTT RPC handler (request/reply).

    The handler takes a Pydantic request model and returns a Pydantic response
    model; the adapter decodes the request payload as JSON, calls the handler,
    and publishes the JSON-encoded response to the request's ResponseTopic with
    the same CorrelationData (MQTT v5).

        @rpc("service/echo")
        async def echo(self, request: EchoRequest) -> EchoResponse: ...

    Handler nhận/return Pydantic model; adapter trả về ResponseTopic kèm
    CorrelationData (MQTT v5).
    """
    def decorator(func: Callable) -> Callable:
        setattr(func, MQTT_ATTR, MqttHandlerInfo(MqttKind.RPC, topic, qos))
        return func

    return decorator


def get_mqtt_info(func: Any) -> MqttHandlerInfo | None:
    """Return the MqttHandlerInfo attached to a method, or None."""
    return getattr(func, MQTT_ATTR, None)
