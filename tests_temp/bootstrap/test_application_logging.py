"""Framework cấu hình root logging mặc định từ khối logging: trong application.yml.

Trước khi thêm, app chạy im lặng (root logger mức WARNING, không handler) ->
mọi log INFO bị nuốt. Application._configure_logging() áp dụng default an toàn:
chỉ khi enabled VÀ root chưa có handler (app/pytest tự cấu hình luôn thắng).

Test truyền root giả (seam `root=`) + spy logging.basicConfig, nên không đụng
root logger thật (pytest gắn handler riêng lên root suốt thân test).
"""
import logging

import pytest

from xime.core.bootstrap import Application
from xime.core.config import LoggingConfig, RuntimeConfig


class _FakeRoot:
    """Root logger giả với hasHandlers() điều khiển được."""

    def __init__(self, has_handlers: bool) -> None:
        self._has_handlers = has_handlers

    def hasHandlers(self) -> bool:  # noqa: N802 - khớp API logging
        return self._has_handlers


@pytest.fixture
def spy_basicconfig(monkeypatch):
    """Ghi lại tham số của logging.basicConfig (None nếu không được gọi)."""
    recorded: dict = {"kwargs": None}
    monkeypatch.setattr(
        logging, "basicConfig", lambda **kw: recorded.__setitem__("kwargs", kw)
    )
    return recorded


def _apply(spy_basicconfig, cfg: LoggingConfig, has_handlers: bool) -> dict:
    Application._configure_logging(
        RuntimeConfig(logging=cfg), root=_FakeRoot(has_handlers)
    )
    return spy_basicconfig


def test_configures_root_when_no_handler(spy_basicconfig):
    recorded = _apply(spy_basicconfig, LoggingConfig(level="DEBUG"), has_handlers=False)
    assert recorded["kwargs"] is not None
    assert recorded["kwargs"]["level"] == logging.DEBUG


def test_default_level_is_info(spy_basicconfig):
    recorded = _apply(spy_basicconfig, LoggingConfig(), has_handlers=False)
    assert recorded["kwargs"]["level"] == logging.INFO


def test_disabled_does_not_call_basicconfig(spy_basicconfig):
    recorded = _apply(spy_basicconfig, LoggingConfig(enabled=False), has_handlers=False)
    assert recorded["kwargs"] is None


def test_does_not_override_existing_handler(spy_basicconfig):
    """App tự cấu hình logging (root đã có handler) -> framework không gọi basicConfig."""
    recorded = _apply(spy_basicconfig, LoggingConfig(level="DEBUG"), has_handlers=True)
    assert recorded["kwargs"] is None


def test_unknown_level_falls_back_to_info(spy_basicconfig):
    recorded = _apply(spy_basicconfig, LoggingConfig(level="NONSENSE"), has_handlers=False)
    assert recorded["kwargs"]["level"] == logging.INFO


def test_level_name_is_case_insensitive(spy_basicconfig):
    recorded = _apply(spy_basicconfig, LoggingConfig(level="warning"), has_handlers=False)
    assert recorded["kwargs"]["level"] == logging.WARNING


def test_passes_format_and_datefmt(spy_basicconfig):
    cfg = LoggingConfig(format="%(message)s", datefmt="%Y")
    recorded = _apply(spy_basicconfig, cfg, has_handlers=False)
    assert recorded["kwargs"]["format"] == "%(message)s"
    assert recorded["kwargs"]["datefmt"] == "%Y"


def test_logging_config_parsed_from_yaml():
    """Khối logging: trong YAML được parse vào RuntimeConfig.logging."""
    runtime = RuntimeConfig.from_dict(
        {"logging": {"enabled": False, "level": "DEBUG", "format": "%(message)s"}}
    )
    assert runtime.logging.enabled is False
    assert runtime.logging.level == "DEBUG"
    assert runtime.logging.format == "%(message)s"


def test_logging_config_defaults_when_absent():
    """Không khai báo logging: -> default enabled INFO."""
    runtime = RuntimeConfig()
    assert runtime.logging.enabled is True
    assert runtime.logging.level == "INFO"
