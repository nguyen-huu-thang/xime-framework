"""
Test StartupOrchestrator:
  - empty config: pipeline chạy bình thường (no-op lifecycle)
  - scan package thật: singletons được tạo đúng
  - post_construct được gọi sau start()
  - pre_destroy được gọi sau stop()
  - singletons được chia sẻ (dependency injection đúng)
  - thứ tự: dependency start trước, stop sau
  - get() trước start() → RuntimeError
  - stop() trước start() → no-op
  - runtime config có thể đọc qua orchestrator.runtime
"""
import pytest

from bootstrap_sample.service.tracker import GreeterService, TrackerService
from core.bootstrap import StartupOrchestrator
from core.config import BindingConfig, RuntimeConfig


def _binding_with_sample() -> BindingConfig:
    cfg = BindingConfig()
    cfg.scan("bootstrap_sample.service")
    return cfg


# ---------------------------------------------------------------------------
# Empty config
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_config_starts_and_stops():
    orch = StartupOrchestrator(BindingConfig(), RuntimeConfig())
    await orch.start()
    await orch.stop()  # không raise


@pytest.mark.asyncio
async def test_stop_without_start_is_noop():
    orch = StartupOrchestrator(BindingConfig(), RuntimeConfig())
    await orch.stop()  # không raise


# ---------------------------------------------------------------------------
# DI pipeline — singletons được tạo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_singleton_after_start():
    orch = StartupOrchestrator(_binding_with_sample(), RuntimeConfig())
    await orch.start()

    tracker = orch.get(TrackerService)
    assert isinstance(tracker, TrackerService)


@pytest.mark.asyncio
async def test_get_before_start_raises():
    orch = StartupOrchestrator(_binding_with_sample(), RuntimeConfig())
    with pytest.raises(RuntimeError, match="not started"):
        orch.get(TrackerService)


@pytest.mark.asyncio
async def test_dependency_injected_correctly():
    orch = StartupOrchestrator(_binding_with_sample(), RuntimeConfig())
    await orch.start()

    greeter = orch.get(GreeterService)
    tracker = orch.get(TrackerService)
    assert greeter.tracker is tracker   # singleton chia sẻ


@pytest.mark.asyncio
async def test_singletons_are_the_same_instance():
    orch = StartupOrchestrator(_binding_with_sample(), RuntimeConfig())
    await orch.start()

    t1 = orch.get(TrackerService)
    t2 = orch.get(TrackerService)
    assert t1 is t2


# ---------------------------------------------------------------------------
# Lifecycle — PostConstruct
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_construct_called_after_start():
    orch = StartupOrchestrator(_binding_with_sample(), RuntimeConfig())
    await orch.start()

    tracker = orch.get(TrackerService)
    assert tracker.started is True


@pytest.mark.asyncio
async def test_all_post_construct_called():
    orch = StartupOrchestrator(_binding_with_sample(), RuntimeConfig())
    await orch.start()

    assert orch.get(TrackerService).started is True
    assert orch.get(GreeterService).started is True


@pytest.mark.asyncio
async def test_dependency_post_construct_runs_before_dependent():
    """
    TrackerService (dependency) phải được start() trước GreeterService (dependent).
    Nếu TopologicalOrder đúng, tracker.started=True khi greeter.post_construct chạy.
    """
    call_order: list[str] = []

    class OrderTrackingTracker:
        def __init__(self) -> None:
            pass

        async def post_construct(self) -> None:
            call_order.append("tracker")

    class OrderTrackingGreeter:
        def __init__(self, tracker: OrderTrackingTracker) -> None:
            self.tracker = tracker

        async def post_construct(self) -> None:
            call_order.append("greeter")

    # Test trực tiếp trên LifecycleManager với thứ tự [tracker, greeter]
    from core.lifecycle import LifecycleManager
    t = OrderTrackingTracker()
    g = OrderTrackingGreeter(tracker=t)
    manager = LifecycleManager([t, g])
    await manager.start()

    assert call_order == ["tracker", "greeter"]


# ---------------------------------------------------------------------------
# Lifecycle — PreDestroy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pre_destroy_called_after_stop():
    orch = StartupOrchestrator(_binding_with_sample(), RuntimeConfig())
    await orch.start()
    await orch.stop()

    tracker = orch.get(TrackerService)
    assert tracker.stopped is True


@pytest.mark.asyncio
async def test_pre_destroy_runs_in_reverse_order():
    call_order: list[str] = []

    class ServiceA:
        def __init__(self) -> None:
            pass

        async def pre_destroy(self) -> None:
            call_order.append("A")

    class ServiceB:
        def __init__(self, a: ServiceA) -> None:
            self.a = a

        async def pre_destroy(self) -> None:
            call_order.append("B")

    from core.lifecycle import LifecycleManager
    a = ServiceA()
    b = ServiceB(a=a)
    manager = LifecycleManager([a, b])   # topological order: a trước b
    await manager.stop()

    assert call_order == ["B", "A"]  # ngược lại


# ---------------------------------------------------------------------------
# Runtime config
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_runtime_config_accessible():
    runtime = RuntimeConfig.from_dict({"env": "testing", "server": {"port": 9999}})
    orch = StartupOrchestrator(BindingConfig(), runtime)
    assert orch.runtime.env == "testing"
    assert orch.runtime.server.port == 9999


@pytest.mark.asyncio
async def test_runtime_config_accessible_before_start():
    runtime = RuntimeConfig.from_dict({"env": "staging"})
    orch = StartupOrchestrator(BindingConfig(), runtime)
    # runtime phải có thể đọc cả trước khi start()
    assert orch.runtime.env == "staging"
