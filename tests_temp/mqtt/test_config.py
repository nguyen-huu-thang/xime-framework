"""MqttConfig.resolve + registry behaviour (0.5)."""
import pytest

from xime.adapters.mqtt._config import (
    MqttConfig,
    configure_mqtt_controllers,
    configure_mqtt_error_mappings,
    mqtt_registry,
)
from xime.core.config.runtime import RuntimeConfig


def _runtime(mqtt: dict | None) -> RuntimeConfig:
    return RuntimeConfig.from_dict({"mqtt": mqtt} if mqtt is not None else {})


class TestResolve:
    def test_missing_host_fails_fast(self):
        with pytest.raises(ValueError, match="mqtt.host"):
            MqttConfig.resolve(_runtime({"port": 1883}), "default")

    def test_defaults(self):
        cfg = MqttConfig.resolve(_runtime({"host": "broker"}), "data")
        assert cfg.host == "broker"
        assert cfg.port == 1883
        assert cfg.keepalive == 60
        assert cfg.default_qos == 0
        assert cfg.max_concurrency == 16
        # client_id falls back to the adapter's id when unset.
        assert cfg.client_id == "data"
        assert cfg.tls is None and cfg.lwt is None

    def test_explicit_client_id_wins(self):
        cfg = MqttConfig.resolve(_runtime({"host": "b", "client_id": "explicit"}), "data")
        assert cfg.client_id == "explicit"

    def test_tls_and_lwt_parsed(self):
        cfg = MqttConfig.resolve(
            _runtime(
                {
                    "host": "b",
                    "tls": {"ca_certs": "/ca.pem", "certfile": "/c.pem", "keyfile": "/k.key"},
                    "lwt": {"topic": "status", "payload": "offline", "qos": 1, "retain": True},
                }
            ),
            "default",
        )
        assert cfg.tls is not None and cfg.tls.ca_certs == "/ca.pem"
        assert cfg.lwt is not None and cfg.lwt.topic == "status"
        assert cfg.lwt.qos == 1 and cfg.lwt.retain is True


class TestRegistry:
    def test_packages_and_error_mappings(self):
        configure_mqtt_controllers("api.mqtt", "api.more")
        assert mqtt_registry.get_packages() == ["api.mqtt", "api.more"]

        class Boom(Exception):
            pass

        configure_mqtt_error_mappings({Boom: "BOOM"})
        assert mqtt_registry.get_error_mappings()[Boom] == "BOOM"

    def test_connection_is_shared_per_client_id(self):
        c1 = mqtt_registry.connection("default")
        c2 = mqtt_registry.connection("default")
        c3 = mqtt_registry.connection("other")
        assert c1 is c2
        assert c1 is not c3


class TestRpcReplyTopics:
    """F17: mqtt.rpc.reply_topics - the reply-topic policy for @rpc handlers."""

    def test_absent_block_means_no_policy(self):
        cfg = MqttConfig.resolve(_runtime({"host": "b"}), "data")
        assert cfg.rpc.reply_topics == []

    def test_filters_are_read(self):
        cfg = MqttConfig.resolve(
            _runtime({"host": "b", "rpc": {"reply_topics": ["a/#", "b/+/c"]}}), "data"
        )
        assert cfg.rpc.reply_topics == ["a/#", "b/+/c"]

    def test_single_string_is_accepted_as_one_filter(self):
        cfg = MqttConfig.resolve(
            _runtime({"host": "b", "rpc": {"reply_topics": "a/#"}}), "data"
        )
        assert cfg.rpc.reply_topics == ["a/#"]

    def test_malformed_filter_fails_fast(self):
        """A filter that can never match would turn EVERY reply into a warning.

        That is the shape of a check which cries wolf, so it must be caught at
        startup rather than lived with.
        Filter không bao giờ khớp sẽ biến MỌI reply thành cảnh báo - đúng hình
        dạng phép dò kêu oan, nên phải chết ngay lúc khởi động.
        """
        with pytest.raises(ValueError, match="invalid topic filter"):
            MqttConfig.resolve(
                _runtime({"host": "b", "rpc": {"reply_topics": ["a/#/b"]}}), "data"
            )

    def test_wrong_type_fails_fast(self):
        with pytest.raises(ValueError, match="must be a list"):
            MqttConfig.resolve(
                _runtime({"host": "b", "rpc": {"reply_topics": 5}}), "data"
            )
