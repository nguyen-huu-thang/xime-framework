"""
Test Application:
  - direct binding bỏ qua auto-discovery
  - auto-discovery module không tồn tại → dùng empty config
  - async context manager: start() khi vào, stop() khi ra
  - get() hoạt động sau start()
  - get() trước start() → RuntimeError
  - stop() trước start() → no-op
  - runtime config được load từ YAML (nonexistent → defaults)
"""
import pytest

from bootstrap_sample.service.tracker import TrackerService
from core.bootstrap import Application
from core.config import BindingConfig, RuntimeConfig


def _sample_binding() -> BindingConfig:
    cfg = BindingConfig()
    cfg.scan("bootstrap_sample.service")
    return cfg


# ---------------------------------------------------------------------------
# Async context manager
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_context_manager_starts_application():
    async with Application(binding=_sample_binding(), resources_dir="nonexistent") as app:
        tracker = app.get(TrackerService)
        assert tracker.started is True


@pytest.mark.asyncio
async def test_context_manager_stops_on_exit():
    async with Application(binding=_sample_binding(), resources_dir="nonexistent") as app:
        tracker = app.get(TrackerService)

    assert tracker.stopped is True


@pytest.mark.asyncio
async def test_context_manager_stop_called_even_on_exception():
    tracker_ref: TrackerService | None = None

    with pytest.raises(RuntimeError, match="test error"):
        async with Application(binding=_sample_binding(), resources_dir="nonexistent") as app:
            tracker_ref = app.get(TrackerService)
            raise RuntimeError("test error")

    assert tracker_ref is not None
    assert tracker_ref.stopped is True


# ---------------------------------------------------------------------------
# Manual start / stop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manual_start_stop():
    app = Application(binding=_sample_binding(), resources_dir="nonexistent")
    await app.start()
    tracker = app.get(TrackerService)
    assert tracker.started is True
    await app.stop()
    assert tracker.stopped is True


@pytest.mark.asyncio
async def test_stop_without_start_is_noop():
    app = Application(resources_dir="nonexistent")
    await app.stop()  # không raise


@pytest.mark.asyncio
async def test_get_before_start_raises():
    app = Application(resources_dir="nonexistent")
    with pytest.raises(RuntimeError, match="not started"):
        app.get(TrackerService)


# ---------------------------------------------------------------------------
# Auto-discovery
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_discovery_missing_module_falls_back_to_empty_config():
    app = Application(
        config_module="absolutely.does.not.exist",
        resources_dir="nonexistent",
    )
    await app.start()
    await app.stop()   # không raise — empty config, không có gì để scan


@pytest.mark.asyncio
async def test_direct_binding_bypasses_auto_discovery():
    """Khi binding= được truyền, config_module không được import."""
    binding = _sample_binding()
    app = Application(
        binding=binding,
        config_module="this.should.not.be.imported",
        resources_dir="nonexistent",
    )
    await app.start()
    tracker = app.get(TrackerService)
    assert isinstance(tracker, TrackerService)
    await app.stop()


# ---------------------------------------------------------------------------
# Runtime config
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_runtime_config_defaults_when_no_yaml(tmp_path):
    """Khi resources/ trống, RuntimeConfig dùng giá trị mặc định."""
    app = Application(binding=BindingConfig(), resources_dir=str(tmp_path))
    await app.start()
    runtime = app._orchestrator.runtime
    assert runtime.env == "development"
    assert runtime.server.port == 8080
    await app.stop()


@pytest.mark.asyncio
async def test_runtime_config_loaded_from_yaml(tmp_path):
    (tmp_path / "application.yml").write_text("env: production\nserver:\n  port: 9000\n")
    app = Application(binding=BindingConfig(), resources_dir=str(tmp_path))
    await app.start()
    runtime = app._orchestrator.runtime
    assert runtime.env == "production"
    assert runtime.server.port == 9000
    await app.stop()
