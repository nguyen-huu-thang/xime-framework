"""MQTT routing layer.

Re-exports the MQTT handler decorators and the configure helper so MQTT
controllers import everything from one place, mirroring
xime.adapters.web.routing / xime.adapters.socket.routing.
"""

from .._config import configure_mqtt_controllers
from .._decorators import rpc, subscribe
from ._builder import MqttRouteBuilder, ResolvedMqttRoute
from ._scanner import MqttControllerScanner

__all__ = [
    "subscribe",
    "rpc",
    "configure_mqtt_controllers",
    "MqttRouteBuilder",
    "ResolvedMqttRoute",
    "MqttControllerScanner",
]
