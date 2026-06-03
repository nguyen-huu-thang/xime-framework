from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CronJob:
    """
    Schedule a job class using a standard 5-field cron expression.

    Args:
        job_class:  Class that implements ScheduledJob (async def run).
        cron:       Standard 5-field cron string, e.g. "0 9 * * 1-5"
                    (every weekday at 09:00).
        id:         Unique schedule ID. Defaults to the class name.

    Example:
        CronJob(job_class=DailyReportJob, cron="0 0 * * *")
    """

    job_class: type
    cron: str
    id: str | None = None


@dataclass
class IntervalJob:
    """
    Schedule a job class to run at a fixed time interval.

    At least one of hours / minutes / seconds must be greater than zero —
    a zero interval is rejected at startup (fail-fast).

    Args:
        job_class:  Class that implements ScheduledJob (async def run).
        hours:      Interval in hours (additive with minutes / seconds).
        minutes:    Interval in minutes.
        seconds:    Interval in seconds.
        id:         Unique schedule ID. Defaults to the class name.

    Example:
        IntervalJob(job_class=CleanupJob, minutes=30)
    """

    job_class: type
    hours: int = 0
    minutes: int = 0
    seconds: int = 0
    id: str | None = None


@dataclass
class SchedulerConfig:
    """
    Top-level configuration for the Xime scheduler starter.

    Pass an instance to configure_scheduler() in config/scheduler.py:

        configure_scheduler(SchedulerConfig(
            jobs=[
                CronJob(job_class=DailyReportJob, cron="0 0 * * *"),
                IntervalJob(job_class=CleanupJob, minutes=30),
            ],
            timezone="Asia/Ho_Chi_Minh",
        ))

    Args:
        jobs:       List of CronJob / IntervalJob descriptors to schedule.
        timezone:   Timezone name for cron evaluation (default "UTC").
                    Any IANA timezone string is accepted, e.g. "Asia/Ho_Chi_Minh".
    """

    jobs: list[CronJob | IntervalJob] = field(default_factory=list)
    timezone: str = "UTC"


class _SchedulerRegistry:
    """Module-level singleton that holds the SchedulerConfig set by the developer."""

    def __init__(self) -> None:
        self._config: SchedulerConfig | None = None

    def set(self, config: SchedulerConfig) -> None:
        self._config = config

    def get(self) -> SchedulerConfig | None:
        return self._config


# Module-level singleton — read by StartupOrchestrator after DI is built.
scheduler_registry = _SchedulerRegistry()


def configure_scheduler(config: SchedulerConfig) -> None:
    """
    Register the scheduler configuration.

    Call this once in config/scheduler.py (or any module imported before startup).
    Calling it a second time overwrites the previous config.

    Example:
        from xime.starters.scheduler import configure_scheduler, SchedulerConfig, CronJob

        configure_scheduler(SchedulerConfig(
            jobs=[CronJob(job_class=DailyReportJob, cron="0 0 * * *")],
        ))
    """
    scheduler_registry.set(config)
