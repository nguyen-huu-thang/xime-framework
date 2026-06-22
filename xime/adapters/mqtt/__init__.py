"""MQTT Adapter — message-driven (pub/sub + RPC) transport for IoT / embedded.

Lets a Xime service subscribe to MQTT topics with constructor injection and
controller scanning, publish via an injectable MqttPublisher, and serve
request/reply over MQTT v5 (@rpc). The framework imposes no payload format for
pub/sub (raw bytes); @rpc uses JSON-encoded Pydantic models.

Public API:
    from xime.adapters.mqtt import (
        MqttAdapter, MqttPublisher,
        subscribe, rpc,
        configure_mqtt_controllers, configure_mqtt_error_mappings,
    )

Usage:
    # api/mqtt/sensor_controller.py
    from xime.adapters.mqtt import subscribe, rpc

    class SensorController:
        def __init__(self, ingest: IngestService) -> None:
            self._ingest = ingest

        @subscribe("sensors/+/temperature", qos=1)
        async def on_temp(self, payload: bytes, topic: str) -> None:
            await self._ingest.record(topic, payload)

        @rpc("sensors/calibrate")
        async def calibrate(self, request: CalibrateRequest) -> CalibrateResponse:
            return await self._ingest.calibrate(request)

    # config/mqtt.py
    from xime.adapters.mqtt import configure_mqtt_controllers
    configure_mqtt_controllers("api.mqtt")

    # config/dependency.py
    dependency.scan("api.mqtt")
    dependency.register(MqttPublisher)
"""

from ._adapter import MqttAdapter
from ._config import (
    MqttConfig,
    configure_mqtt_controllers,
    configure_mqtt_error_mappings,
    mqtt_registry,
)
from ._decorators import rpc, subscribe
from ._publisher import MqttPublisher
from ._runtime import MqttConnection

__all__ = [
    # Adapter & publisher
    "MqttAdapter",
    "MqttPublisher",
    "MqttConnection",
    # Decorators
    "subscribe",
    "rpc",
    # Config
    "MqttConfig",
    "configure_mqtt_controllers",
    "configure_mqtt_error_mappings",
    "mqtt_registry",
]
