"""Shared fixtures for the MQTT adapter suite.

The MQTT registry is a module-level singleton (packages, error mappings, shared
connections). Reset it around every test so registrations and connection holders
do not bleed between tests.
"""
import pytest

from xime.adapters.mqtt._config import mqtt_registry


@pytest.fixture(autouse=True)
def reset_mqtt_registry():
    mqtt_registry.reset()
    yield
    mqtt_registry.reset()
