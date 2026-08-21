from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ._config import CronJob, IntervalJob, SchedulerConfig
from ._job import ScheduledJob


class SchedulerRunner:
    """
    Bridges the Xime DI container with APScheduler v4.

    Lifecycle-aware: implements post_construct / pre_destroy so that
    StartupOrchestrator can add it to LifecycleManager alongside user
    singletons - no web-adapter involvement needed.

    Startup order guaranteed by StartupOrchestrator:
        all user singletons → SchedulerRunner.post_construct()

    Shutdown order (reverse):
        SchedulerRunner.pre_destroy() → all user singletons

    The scheduler loop runs inside APScheduler's own supervised task group via
    start_in_background(), which returns only once the loop reports started.
    That ordering matters: AsyncScheduler.stop() is a no-op while the state is
    still "stopped", so a runner that returned before the loop began would let
    a fast shutdown dismantle the data store under a task that had not yet run
 - surfacing as "The scheduler has not been initialized yet". Any Application
    that starts and stops quickly hits it; long-running processes hide it.

    Vòng lặp chạy trong task group của chính APScheduler qua start_in_background(),
    hàm này chỉ trả về khi vòng lặp đã báo started. Thứ tự đó quan trọng: stop()
    không làm gì khi trạng thái còn là "stopped", nên nếu trả về trước lúc vòng
    lặp kịp chạy thì việc tắt nhanh sẽ dọn kho dữ liệu dưới chân một task chưa
    khởi động - lộ ra thành "The scheduler has not been initialized yet".
    """

    def __init__(
        self,
        config: SchedulerConfig,
        resolver: Callable[[type], Any],
    ) -> None:
        """
        Args:
            config:   SchedulerConfig populated by configure_scheduler().
            resolver: callable(cls) → singleton instance from the DI container.
                      Provided by StartupOrchestrator as container.get.
        """
        self._config = config
        self._resolver = resolver
        self._scheduler: AsyncScheduler | None = None

    # ------------------------------------------------------------------
    # Lifecycle hooks (called by LifecycleManager)
    # ------------------------------------------------------------------

    async def post_construct(self) -> None:
        """
        Start APScheduler and register all configured jobs.

        Called after all user singletons are created, so resolver() is
        guaranteed to return fully-injected instances.

        Raises RuntimeError on the first invalid job (fail-fast).
        If setup fails after __aenter__, __aexit__ is called to release
        APScheduler's internal resources before re-raising.
        """
        self._scheduler = AsyncScheduler()
        await self._scheduler.__aenter__()

        try:
            for job_def in self._config.jobs:
                self._validate(job_def)

                instance = self._resolver(job_def.job_class)
                if not isinstance(instance, ScheduledJob):
                    raise RuntimeError(
                        f"{job_def.job_class.__name__} does not implement ScheduledJob"
                        " - add 'async def run(self) -> None' to the class."
                    )

                trigger = self._build_trigger(job_def)
                job_id = job_def.id or job_def.job_class.__name__
                await self._scheduler.add_schedule(instance.run, trigger, id=job_id)

            # Hand the scheduler loop to APScheduler's own supervised task group
            # and WAIT until it reports started. Do NOT replace this with
            # asyncio.create_task(run_until_stopped()): that returns before the
            # loop has run, and a fast shutdown then tears the services down
            # underneath a task that never started - stop() is a silent no-op
            # while the state is still "stopped". See the class docstring.
            # Giao vòng lặp cho task group của chính APScheduler và ĐỢI tới khi
            # nó báo đã chạy. Đừng thay bằng asyncio.create_task(): hàm đó trả
            # về trước khi vòng lặp kịp chạy, và nếu tắt nhanh thì dịch vụ bị
            # dọn dưới chân một task chưa khởi động - lúc đó stop() im lặng
            # không làm gì vì trạng thái vẫn là "stopped".
            await self._scheduler.start_in_background()
        except BaseException:
            await self._scheduler.__aexit__(None, None, None)
            self._scheduler = None
            raise

    async def pre_destroy(self) -> None:
        """
        Stop APScheduler gracefully, waiting for any in-flight job to finish.

        Called before user singletons are torn down, so services used by
        jobs are still available during the final run of any active job.

        stop() signals the scheduler loop to exit; __aexit__ then unwinds
        APScheduler's own task group, which waits for that loop to finish its
        internal shutdown. Because post_construct waited for the started state,
        stop() is guaranteed to act rather than silently do nothing.

        stop() ra hiệu cho vòng lặp thoát; __aexit__ gỡ task group của chính
        APScheduler và đợi vòng lặp dọn xong. Vì post_construct đã đợi tới
        trạng thái started nên stop() chắc chắn có tác dụng, không im lặng bỏ qua.
        """
        if self._scheduler is not None:
            await self._scheduler.stop()
            with suppress(asyncio.CancelledError):
                await self._scheduler.__aexit__(None, None, None)
            self._scheduler = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_trigger(self, job_def: CronJob | IntervalJob) -> CronTrigger | IntervalTrigger:
        if isinstance(job_def, CronJob):
            return CronTrigger.from_crontab(job_def.cron, timezone=self._config.timezone)

        # IntervalJob - APScheduler v4 IntervalTrigger accepts keyword args directly
        return IntervalTrigger(
            hours=job_def.hours,
            minutes=job_def.minutes,
            seconds=job_def.seconds,
        )

    @staticmethod
    def _validate(job_def: CronJob | IntervalJob) -> None:
        """Fail fast for obviously incorrect job definitions."""
        if isinstance(job_def, IntervalJob):
            total_seconds = (
                job_def.hours * 3600
                + job_def.minutes * 60
                + job_def.seconds
            )
            if total_seconds <= 0:
                raise RuntimeError(
                    f"IntervalJob for {job_def.job_class.__name__} has a zero interval. "
                    "Set at least one of hours, minutes, or seconds to a positive value."
                )
