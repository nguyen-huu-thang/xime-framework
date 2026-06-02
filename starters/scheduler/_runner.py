from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any, Callable

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
    singletons — no web-adapter involvement needed.

    Startup order guaranteed by StartupOrchestrator:
        all user singletons → SchedulerRunner.post_construct()

    Shutdown order (reverse):
        SchedulerRunner.pre_destroy() → all user singletons
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
        self._task: asyncio.Task[None] | None = None

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
                        " — add 'async def run(self) -> None' to the class."
                    )

                trigger = self._build_trigger(job_def)
                job_id = job_def.id or job_def.job_class.__name__
                await self._scheduler.add_schedule(instance.run, trigger, id=job_id)

            # Run the scheduler event loop in a background task so it does not
            # block the main event loop. run_until_stopped() exits when stop() is called.
            self._task = asyncio.create_task(
                self._scheduler.run_until_stopped(),
                name="xime-scheduler",
            )
        except Exception:
            await self._scheduler.__aexit__(None, None, None)
            self._scheduler = None
            raise

    async def pre_destroy(self) -> None:
        """
        Stop APScheduler gracefully, waiting for any in-flight job to finish.

        Called before user singletons are torn down, so services used by
        jobs are still available during the final run of any active job.

        stop() signals run_until_stopped() to exit its loop. We then await
        the task to let APScheduler finish its internal shutdown sequence
        rather than interrupting it with cancel().
        """
        if self._scheduler is not None:
            await self._scheduler.stop()
            await self._scheduler.__aexit__(None, None, None)
            self._scheduler = None

        if self._task is not None:
            # Do NOT cancel — stop() already signalled run_until_stopped() to exit.
            # Awaiting here lets APScheduler complete its internal cleanup before
            # control returns to LifecycleManager to tear down user singletons.
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_trigger(self, job_def: CronJob | IntervalJob) -> CronTrigger | IntervalTrigger:
        if isinstance(job_def, CronJob):
            return CronTrigger.from_crontab(job_def.cron, timezone=self._config.timezone)

        # IntervalJob — APScheduler v4 IntervalTrigger accepts keyword args directly
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
