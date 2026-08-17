"""
Test SchedulerRunner (yêu cầu apscheduler>=4.0.0a6 - API v4):

  _validate():
    - IntervalJob với tất cả field = 0 → RuntimeError "zero interval"
    - IntervalJob với seconds > 0 → không raise
    - IntervalJob với minutes > 0 → không raise
    - IntervalJob với hours > 0 → không raise
    - CronJob → không raise (không có validation riêng)

  _build_trigger():
    - CronJob → trả về CronTrigger
    - IntervalJob → trả về IntervalTrigger
    - IntervalTrigger giữ đúng timedelta tương ứng với hours/minutes/seconds

  post_construct():
    - Happy path: __aenter__ được gọi, add_schedule được gọi, vòng lặp chạy nền
    - KHÔNG tự create_task(run_until_stopped()) - phải qua start_in_background()
    - Không có job → scheduler vẫn start, add_schedule không được gọi
    - resolver được gọi đúng với job_class
    - Dùng tên class làm id khi id=None
    - Dùng id tuỳ chỉnh khi id được set
    - Job class thiếu run() → RuntimeError
    - Khi raise sau __aenter__ → __aexit__ được gọi (dọn resource)
    - Khi raise sau __aenter__ → self._scheduler bị reset về None
    - Nhiều jobs → add_schedule được gọi đúng số lần

  pre_destroy():
    - stop() được gọi trên scheduler
    - self._scheduler là None sau khi gọi
    - __aexit__ được gọi để đóng task group nội bộ của APScheduler
    - An toàn khi gọi lúc chưa start (scheduler=None)
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

apscheduler = pytest.importorskip("apscheduler", reason="pip install 'apscheduler>=4.0.0a6'")

from apscheduler.triggers.cron import CronTrigger       # noqa: E402
from apscheduler.triggers.interval import IntervalTrigger  # noqa: E402

from xime.starters.scheduler._config import CronJob, IntervalJob, SchedulerConfig  # noqa: E402
from xime.starters.scheduler._job import ScheduledJob        # noqa: E402
from xime.starters.scheduler._runner import SchedulerRunner  # noqa: E402


# ---------------------------------------------------------------------------
# Job stubs
# ---------------------------------------------------------------------------

class _GoodJob:
    async def run(self) -> None:
        pass


class _NoRunJob:
    pass  # thiếu run() → không thoả ScheduledJob


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_apscheduler():
    """Mock AsyncScheduler instance với async interface đầy đủ."""
    m = AsyncMock()
    m.__aenter__ = AsyncMock(return_value=None)
    m.__aexit__ = AsyncMock(return_value=None)
    m.add_schedule = AsyncMock()
    m.run_until_stopped = AsyncMock()  # trả về ngay để không block test
    m.stop = AsyncMock()
    return m


@pytest.fixture
def patch_async_scheduler(mock_apscheduler):
    """Patch AsyncScheduler trong _runner module bằng mock_apscheduler."""
    with patch("xime.starters.scheduler._runner.AsyncScheduler", return_value=mock_apscheduler):
        yield mock_apscheduler


# ---------------------------------------------------------------------------
# _validate
# ---------------------------------------------------------------------------

class TestSchedulerRunnerValidate:
    def test_interval_job_all_zeros_raises_runtime_error(self):
        job = IntervalJob(job_class=_GoodJob)  # hours=0, minutes=0, seconds=0
        with pytest.raises(RuntimeError, match="zero interval"):
            SchedulerRunner._validate(job)

    def test_interval_job_with_positive_seconds_passes(self):
        job = IntervalJob(job_class=_GoodJob, seconds=1)
        SchedulerRunner._validate(job)  # không raise

    def test_interval_job_with_positive_minutes_passes(self):
        job = IntervalJob(job_class=_GoodJob, minutes=5)
        SchedulerRunner._validate(job)

    def test_interval_job_with_positive_hours_passes(self):
        job = IntervalJob(job_class=_GoodJob, hours=1)
        SchedulerRunner._validate(job)

    def test_interval_job_combined_fields_passes(self):
        job = IntervalJob(job_class=_GoodJob, hours=1, minutes=30, seconds=15)
        SchedulerRunner._validate(job)

    def test_cron_job_always_passes(self):
        job = CronJob(job_class=_GoodJob, cron="0 0 * * *")
        SchedulerRunner._validate(job)  # không raise

    def test_error_message_contains_class_name(self):
        job = IntervalJob(job_class=_GoodJob)
        with pytest.raises(RuntimeError, match="_GoodJob"):
            SchedulerRunner._validate(job)


# ---------------------------------------------------------------------------
# _build_trigger
# ---------------------------------------------------------------------------

class TestSchedulerRunnerBuildTrigger:
    def _make_runner(self, timezone: str = "UTC") -> SchedulerRunner:
        return SchedulerRunner(
            SchedulerConfig(timezone=timezone),
            resolver=MagicMock(),
        )

    def test_cron_job_returns_cron_trigger_instance(self):
        runner = self._make_runner()
        job = CronJob(job_class=_GoodJob, cron="0 0 * * *")
        trigger = runner._build_trigger(job)
        assert isinstance(trigger, CronTrigger)

    def test_interval_job_returns_interval_trigger_instance(self):
        runner = self._make_runner()
        job = IntervalJob(job_class=_GoodJob, seconds=60)
        trigger = runner._build_trigger(job)
        assert isinstance(trigger, IntervalTrigger)

    def test_interval_trigger_carries_correct_hours_and_minutes(self):
        runner = self._make_runner()
        job = IntervalJob(job_class=_GoodJob, hours=1, minutes=30, seconds=0)
        trigger = runner._build_trigger(job)
        # APScheduler v4: IntervalTrigger lưu từng field riêng lẻ
        assert trigger.hours == 1
        assert trigger.minutes == 30

    def test_interval_trigger_seconds_only(self):
        runner = self._make_runner()
        job = IntervalJob(job_class=_GoodJob, seconds=45)
        trigger = runner._build_trigger(job)
        assert trigger.seconds == 45

    def test_cron_trigger_different_expressions_produce_different_triggers(self):
        runner = self._make_runner()
        t1 = runner._build_trigger(CronJob(job_class=_GoodJob, cron="0 0 * * *"))
        t2 = runner._build_trigger(CronJob(job_class=_GoodJob, cron="0 9 * * 1"))
        assert t1 != t2


# ---------------------------------------------------------------------------
# post_construct
# ---------------------------------------------------------------------------

class TestSchedulerRunnerPostConstruct:
    @pytest.mark.asyncio
    async def test_happy_path_calls_aenter(self, patch_async_scheduler):
        config = SchedulerConfig(jobs=[CronJob(job_class=_GoodJob, cron="0 0 * * *")])
        runner = SchedulerRunner(config, MagicMock(return_value=_GoodJob()))

        await runner.post_construct()

        patch_async_scheduler.__aenter__.assert_called_once()

    @pytest.mark.asyncio
    async def test_happy_path_calls_add_schedule(self, patch_async_scheduler):
        config = SchedulerConfig(jobs=[CronJob(job_class=_GoodJob, cron="0 0 * * *")])
        runner = SchedulerRunner(config, MagicMock(return_value=_GoodJob()))

        await runner.post_construct()

        patch_async_scheduler.add_schedule.assert_called_once()

    @pytest.mark.asyncio
    async def test_happy_path_starts_loop_in_background(self, patch_async_scheduler):
        config = SchedulerConfig(jobs=[CronJob(job_class=_GoodJob, cron="0 0 * * *")])
        runner = SchedulerRunner(config, MagicMock(return_value=_GoodJob()))

        await runner.post_construct()

        patch_async_scheduler.start_in_background.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_does_not_spawn_its_own_task(self, patch_async_scheduler):
        """post_construct KHÔNG được tự create_task(run_until_stopped()).

        Hàm đó trả về trước khi vòng lặp kịp chạy, nên tắt nhanh sẽ dọn dịch vụ
        dưới chân một task chưa khởi động. Canh bằng cách chặn chính run_until_stopped.
        """
        config = SchedulerConfig(jobs=[CronJob(job_class=_GoodJob, cron="0 0 * * *")])
        runner = SchedulerRunner(config, MagicMock(return_value=_GoodJob()))

        await runner.post_construct()

        patch_async_scheduler.run_until_stopped.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_jobs_starts_scheduler_without_add_schedule(self, patch_async_scheduler):
        config = SchedulerConfig(jobs=[])
        runner = SchedulerRunner(config, MagicMock())

        await runner.post_construct()

        patch_async_scheduler.__aenter__.assert_called_once()
        patch_async_scheduler.add_schedule.assert_not_called()
        patch_async_scheduler.start_in_background.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_resolver_called_with_correct_job_class(self, patch_async_scheduler):
        config = SchedulerConfig(jobs=[CronJob(job_class=_GoodJob, cron="0 0 * * *")])
        resolver = MagicMock(return_value=_GoodJob())
        runner = SchedulerRunner(config, resolver)

        await runner.post_construct()

        resolver.assert_called_once_with(_GoodJob)

    @pytest.mark.asyncio
    async def test_uses_class_name_as_default_id(self, patch_async_scheduler):
        config = SchedulerConfig(jobs=[CronJob(job_class=_GoodJob, cron="0 0 * * *")])
        runner = SchedulerRunner(config, MagicMock(return_value=_GoodJob()))

        await runner.post_construct()

        _, kwargs = patch_async_scheduler.add_schedule.call_args
        assert kwargs["id"] == "_GoodJob"

    @pytest.mark.asyncio
    async def test_uses_custom_id_when_provided(self, patch_async_scheduler):
        config = SchedulerConfig(jobs=[
            CronJob(job_class=_GoodJob, cron="0 0 * * *", id="my-daily-job")
        ])
        runner = SchedulerRunner(config, MagicMock(return_value=_GoodJob()))

        await runner.post_construct()

        _, kwargs = patch_async_scheduler.add_schedule.call_args
        assert kwargs["id"] == "my-daily-job"

    @pytest.mark.asyncio
    async def test_multiple_jobs_calls_add_schedule_for_each(self, patch_async_scheduler):
        config = SchedulerConfig(jobs=[
            CronJob(job_class=_GoodJob, cron="0 0 * * *"),
            IntervalJob(job_class=_GoodJob, minutes=30),
        ])
        runner = SchedulerRunner(config, MagicMock(return_value=_GoodJob()))

        await runner.post_construct()

        assert patch_async_scheduler.add_schedule.call_count == 2

    @pytest.mark.asyncio
    async def test_job_without_run_raises_runtime_error(self, patch_async_scheduler):
        config = SchedulerConfig(jobs=[CronJob(job_class=_NoRunJob, cron="0 0 * * *")])
        runner = SchedulerRunner(config, MagicMock(return_value=_NoRunJob()))

        with pytest.raises(RuntimeError, match="does not implement ScheduledJob"):
            await runner.post_construct()

    @pytest.mark.asyncio
    async def test_failure_after_aenter_calls_aexit_cleanup(self, patch_async_scheduler):
        """__aexit__ phải được gọi khi setup thất bại để tránh resource leak."""
        config = SchedulerConfig(jobs=[CronJob(job_class=_NoRunJob, cron="0 0 * * *")])
        runner = SchedulerRunner(config, MagicMock(return_value=_NoRunJob()))

        with pytest.raises(RuntimeError):
            await runner.post_construct()

        patch_async_scheduler.__aexit__.assert_called_once_with(None, None, None)

    @pytest.mark.asyncio
    async def test_failure_resets_scheduler_to_none(self, patch_async_scheduler):
        config = SchedulerConfig(jobs=[CronJob(job_class=_NoRunJob, cron="0 0 * * *")])
        runner = SchedulerRunner(config, MagicMock(return_value=_NoRunJob()))

        with pytest.raises(RuntimeError):
            await runner.post_construct()

        assert runner._scheduler is None

    @pytest.mark.asyncio
    async def test_interval_job_zero_interval_raises_on_validate(self, patch_async_scheduler):
        config = SchedulerConfig(jobs=[
            IntervalJob(job_class=_GoodJob)  # hours=0, minutes=0, seconds=0
        ])
        runner = SchedulerRunner(config, MagicMock(return_value=_GoodJob()))

        with pytest.raises(RuntimeError, match="zero interval"):
            await runner.post_construct()


# ---------------------------------------------------------------------------
# pre_destroy
# ---------------------------------------------------------------------------

class TestSchedulerRunnerPreDestroy:
    @pytest.mark.asyncio
    async def test_calls_stop_on_scheduler(self, patch_async_scheduler):
        config = SchedulerConfig(jobs=[CronJob(job_class=_GoodJob, cron="0 0 * * *")])
        runner = SchedulerRunner(config, MagicMock(return_value=_GoodJob()))
        await runner.post_construct()

        await runner.pre_destroy()

        patch_async_scheduler.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_scheduler_is_none_after_pre_destroy(self, patch_async_scheduler):
        config = SchedulerConfig(jobs=[CronJob(job_class=_GoodJob, cron="0 0 * * *")])
        runner = SchedulerRunner(config, MagicMock(return_value=_GoodJob()))
        await runner.post_construct()

        await runner.pre_destroy()

        assert runner._scheduler is None

    @pytest.mark.asyncio
    async def test_exits_scheduler_context_after_stop(self, patch_async_scheduler):
        """Thoát context của APScheduler để task group nội bộ được đóng đúng cách."""
        config = SchedulerConfig(jobs=[CronJob(job_class=_GoodJob, cron="0 0 * * *")])
        runner = SchedulerRunner(config, MagicMock(return_value=_GoodJob()))
        await runner.post_construct()

        await runner.pre_destroy()

        patch_async_scheduler.stop.assert_awaited_once()
        patch_async_scheduler.__aexit__.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pre_destroy_safe_when_never_started(self):
        """pre_destroy không được raise khi post_construct chưa được gọi."""
        runner = SchedulerRunner(SchedulerConfig(), MagicMock())

        await runner.pre_destroy()  # không raise

        assert runner._scheduler is None
