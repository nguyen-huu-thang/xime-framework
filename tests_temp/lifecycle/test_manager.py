"""
Test LifecycleManager:
  - start() gọi post_construct() đúng thứ tự
  - stop() gọi pre_destroy() đúng thứ tự ngược
  - start() fail fast khi post_construct() raise
  - stop() thu thập tất cả lỗi pre_destroy() vào ExceptionGroup
  - start() / stop() bỏ qua instance không implement hook
  - danh sách rỗng không gây lỗi
"""
import pytest

from xime.core.lifecycle import LifecycleManager


# ---------------------------------------------------------------------------
# Helpers - ghi lại thứ tự gọi
# ---------------------------------------------------------------------------

class CallTracker:
    def __init__(self):
        self.log: list[str] = []


class ServiceA:
    def __init__(self, tracker: CallTracker):
        self.tracker = tracker

    async def post_construct(self) -> None:
        self.tracker.log.append("A.start")

    async def pre_destroy(self) -> None:
        self.tracker.log.append("A.stop")


class ServiceB:
    def __init__(self, tracker: CallTracker):
        self.tracker = tracker

    async def post_construct(self) -> None:
        self.tracker.log.append("B.start")

    async def pre_destroy(self) -> None:
        self.tracker.log.append("B.stop")


class ServiceC:
    """Không có lifecycle hook."""
    pass


# ---------------------------------------------------------------------------
# start() - thứ tự và bỏ qua
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_calls_post_construct_in_order():
    tracker = CallTracker()
    a = ServiceA(tracker)
    b = ServiceB(tracker)
    manager = LifecycleManager([a, b])

    await manager.start()

    assert tracker.log == ["A.start", "B.start"]


@pytest.mark.asyncio
async def test_start_skips_instances_without_hook():
    tracker = CallTracker()
    a = ServiceA(tracker)
    c = ServiceC()          # không có post_construct
    b = ServiceB(tracker)
    manager = LifecycleManager([a, c, b])

    await manager.start()

    assert tracker.log == ["A.start", "B.start"]


@pytest.mark.asyncio
async def test_start_empty_list_is_noop():
    manager = LifecycleManager([])
    await manager.start()   # không raise


# ---------------------------------------------------------------------------
# stop() - thứ tự ngược và bỏ qua
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_calls_pre_destroy_in_reverse_order():
    tracker = CallTracker()
    a = ServiceA(tracker)
    b = ServiceB(tracker)
    manager = LifecycleManager([a, b])

    await manager.stop()

    # Ngược lại so với thứ tự khởi tạo
    assert tracker.log == ["B.stop", "A.stop"]


@pytest.mark.asyncio
async def test_stop_skips_instances_without_hook():
    tracker = CallTracker()
    a = ServiceA(tracker)
    c = ServiceC()
    b = ServiceB(tracker)
    manager = LifecycleManager([a, c, b])

    await manager.stop()

    assert tracker.log == ["B.stop", "A.stop"]


@pytest.mark.asyncio
async def test_stop_empty_list_is_noop():
    manager = LifecycleManager([])
    await manager.stop()    # không raise


# ---------------------------------------------------------------------------
# start() - fail fast
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_fails_fast_on_post_construct_error():
    tracker = CallTracker()

    class FailingService:
        async def post_construct(self) -> None:
            raise RuntimeError("init failed")

    a = ServiceA(tracker)
    failing = FailingService()
    b = ServiceB(tracker)
    manager = LifecycleManager([a, failing, b])

    with pytest.raises(RuntimeError, match="init failed"):
        await manager.start()

    # B.start không được gọi vì fail fast sau FailingService
    assert tracker.log == ["A.start"]


# ---------------------------------------------------------------------------
# stop() - thu thập lỗi
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_collects_all_pre_destroy_errors():
    tracker = CallTracker()

    class FailingA:
        async def pre_destroy(self) -> None:
            tracker.log.append("FailingA.stop")
            raise ValueError("A cleanup failed")

    class FailingB:
        async def pre_destroy(self) -> None:
            tracker.log.append("FailingB.stop")
            raise RuntimeError("B cleanup failed")

    manager = LifecycleManager([FailingA(), FailingB()])

    with pytest.raises(ExceptionGroup) as exc_info:
        await manager.stop()

    group = exc_info.value
    assert len(group.exceptions) == 2
    # Gọi theo thứ tự ngược: B trước, A sau
    assert tracker.log == ["FailingB.stop", "FailingA.stop"]


@pytest.mark.asyncio
async def test_stop_continues_after_one_failure():
    """pre_destroy() vẫn được gọi trên tất cả instance dù có lỗi."""
    tracker = CallTracker()

    class GoodService:
        async def pre_destroy(self) -> None:
            tracker.log.append("good.stop")

    class FailingService:
        async def pre_destroy(self) -> None:
            tracker.log.append("failing.stop")
            raise RuntimeError("cleanup failed")

    # Thứ tự: good, failing - stop sẽ gọi ngược: failing trước, good sau
    manager = LifecycleManager([GoodService(), FailingService()])

    with pytest.raises(ExceptionGroup):
        await manager.stop()

    # Cả hai đều được gọi dù failing raise
    assert "good.stop" in tracker.log
    assert "failing.stop" in tracker.log


@pytest.mark.asyncio
async def test_stop_raises_nothing_when_all_succeed():
    tracker = CallTracker()
    a = ServiceA(tracker)
    b = ServiceB(tracker)
    manager = LifecycleManager([a, b])

    await manager.stop()   # không raise

    assert tracker.log == ["B.stop", "A.stop"]


# ---------------------------------------------------------------------------
# Kết hợp start → stop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_then_stop_full_cycle():
    tracker = CallTracker()
    a = ServiceA(tracker)
    b = ServiceB(tracker)
    manager = LifecycleManager([a, b])

    await manager.start()
    await manager.stop()

    assert tracker.log == ["A.start", "B.start", "B.stop", "A.stop"]
