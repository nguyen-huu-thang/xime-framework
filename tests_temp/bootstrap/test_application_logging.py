"""Legacy logging behavior, checked on an isolated root without spying on calls."""

import logging

import pytest

from xime.core.config import LoggingConfig, RuntimeConfig
from xime.core.logging._runtime import LoggingRuntime


@pytest.mark.parametrize(
    "name,expected", [("DEBUG", 10), ("INFO", 20), ("NONSENSE", 20), ("warning", 30)]
)
def test_legacy_levels(name, expected):
    root = logging.RootLogger(logging.WARNING)
    runtime = LoggingRuntime(LoggingConfig(level=name), service="test", root=root)
    try:
        assert root.level == expected
        assert len(root.handlers) == 1
        assert root.handlers[0].level == expected
    finally:
        runtime.close()
    assert not root.handlers
    assert root.level == logging.WARNING


@pytest.mark.parametrize("enabled", [False, True])
def test_existing_app_root_keeps_formatter_and_levels(enabled):
    root = logging.RootLogger(logging.ERROR)
    handler = logging.NullHandler()
    root.addHandler(handler)
    runtime = LoggingRuntime(
        LoggingConfig(enabled=enabled, level="DEBUG"), service="test", root=root
    )
    assert root.handlers == [handler]
    assert root.level == logging.ERROR
    runtime.close()


def test_legacy_format_and_yaml_defaults():
    cfg = RuntimeConfig.from_dict({"logging": {"format": "%(message)s", "datefmt": "%Y"}})
    root = logging.RootLogger(logging.WARNING)
    runtime = LoggingRuntime(cfg.logging, service="test", root=root)
    try:
        formatter = root.handlers[0].formatter
        assert formatter._fmt == "%(message)s"
        assert formatter.datefmt == "%Y"
        assert cfg.logging.enabled
        assert not cfg.logging.file.enabled
    finally:
        runtime.close()
