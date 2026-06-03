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
  - pre-built instances (register_instance) cũng được gọi lifecycle hooks
"""
import pytest

from bootstrap_sample.service.tracker import GreeterService, TrackerService
from xime.core.bootstrap import StartupOrchestrator
from xime.core.config import BindingConfig, RuntimeConfig


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
    from xime.core.lifecycle import LifecycleManager
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
    tracker = orch.get(TrackerService)   # lấy reference trước khi stop
    await orch.stop()

    # container đã reset sau stop() → dùng reference đã lưu
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

    from xime.core.lifecycle import LifecycleManager
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


# ---------------------------------------------------------------------------
# Double start guard (Issue #4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_while_already_running_raises():
    orch = StartupOrchestrator(_binding_with_sample(), RuntimeConfig())
    await orch.start()
    try:
        with pytest.raises(RuntimeError, match="already running"):
            await orch.start()
    finally:
        await orch.stop()


# ---------------------------------------------------------------------------
# Restart sau stop (Issue #4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_restart_after_stop_works():
    orch = StartupOrchestrator(_binding_with_sample(), RuntimeConfig())

    # Lần 1
    await orch.start()
    tracker_1 = orch.get(TrackerService)
    assert tracker_1.started is True
    await orch.stop()

    # get() sau stop → RuntimeError (container đã reset về None)
    with pytest.raises(RuntimeError):
        orch.get(TrackerService)

    # Lần 2 — start lại được
    await orch.start()
    tracker_2 = orch.get(TrackerService)
    assert tracker_2.started is True
    await orch.stop()


@pytest.mark.asyncio
async def test_stop_resets_internal_state():
    """Sau stop(), _container và _lifecycle phải là None."""
    orch = StartupOrchestrator(_binding_with_sample(), RuntimeConfig())
    await orch.start()
    await orch.stop()
    assert orch._container is None
    assert orch._lifecycle is None


# ---------------------------------------------------------------------------
# Pre-built instances lifecycle (Bug 2 regression guard)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pre_built_instance_post_construct_is_called():
    """
    Instances đăng ký qua register_instance() phải được LifecycleManager
    gọi post_construct() nếu chúng implement PostConstruct.
    """
    log: list[str] = []

    class ExternalService:
        """Pre-built object có lifecycle hook."""
        async def post_construct(self) -> None:
            log.append("post_construct")

    class AppService:
        def __init__(self, ext: ExternalService) -> None:
            self.ext = ext

    from xime.core.container import XimeContainer
    from xime.core.lifecycle import LifecycleManager

    ext = ExternalService()
    container = (
        XimeContainer()
        .register_instance(ExternalService, ext)
        .build()
    )
    instances = container.get_all_in_order()
    await LifecycleManager(instances).start()

    assert "post_construct" in log


@pytest.mark.asyncio
async def test_pre_built_instance_pre_destroy_is_called():
    """
    Instances đăng ký qua register_instance() phải được LifecycleManager
    gọi pre_destroy() nếu chúng implement PreDestroy.
    """
    log: list[str] = []

    class ExternalService:
        async def pre_destroy(self) -> None:
            log.append("pre_destroy")

    from xime.core.container import XimeContainer
    from xime.core.lifecycle import LifecycleManager

    ext = ExternalService()
    container = (
        XimeContainer()
        .register_instance(ExternalService, ext)
        .build()
    )
    instances = container.get_all_in_order()
    await LifecycleManager(instances).stop()

    assert "pre_destroy" in log


@pytest.mark.asyncio
async def test_pre_built_instance_lifecycle_order():
    """
    Pre-built instance là dependency → post_construct chạy TRƯỚC scanned singleton,
    pre_destroy chạy SAU (vì LifecycleManager reverse list khi stop).
    """
    call_order: list[str] = []

    class PreBuiltDep:
        async def post_construct(self) -> None:
            call_order.append("pre_built:start")

        async def pre_destroy(self) -> None:
            call_order.append("pre_built:stop")

    class ScannedService:
        def __init__(self, dep: PreBuiltDep) -> None:
            self.dep = dep

        async def post_construct(self) -> None:
            call_order.append("scanned:start")

        async def pre_destroy(self) -> None:
            call_order.append("scanned:stop")

    import sys, types
    mod_name = "test_lifecycle_order_mod_9921"
    mod = types.ModuleType(mod_name)
    mod.__path__ = []
    mod.PreBuiltDep = PreBuiltDep  # type: ignore[attr-defined]
    mod.ScannedService = ScannedService  # type: ignore[attr-defined]
    ScannedService.__module__ = mod_name
    sys.modules[mod_name] = mod

    from xime.core.container import XimeContainer
    from xime.core.lifecycle import LifecycleManager

    dep = PreBuiltDep()
    container = (
        XimeContainer()
        .register_instance(PreBuiltDep, dep)
        .scan(mod_name)
        .build()
    )
    instances = container.get_all_in_order()
    manager = LifecycleManager(instances)

    await manager.start()
    assert call_order == ["pre_built:start", "scanned:start"]

    await manager.stop()
    assert call_order == ["pre_built:start", "scanned:start", "scanned:stop", "pre_built:stop"]
