"""
xime.starters.scheduler — Task scheduling via APScheduler.

Usage:
    from xime.starters.scheduler import configure_scheduler, SchedulerConfig
    from xime.starters.scheduler import CronJob, IntervalJob, ScheduledJob

Example:
    configure_scheduler(SchedulerConfig(
        jobs=[
            CronJob(job_class=ReportJob, cron="0 8 * * *"),
            IntervalJob(job_class=SyncJob, seconds=60),
        ]
    ))
"""

from starters.scheduler import (
    CronJob,
    IntervalJob,
    ScheduledJob,
    SchedulerConfig,
    configure_scheduler,
)

__all__ = [
    "configure_scheduler",
    "SchedulerConfig",
    "CronJob",
    "IntervalJob",
    "ScheduledJob",
]
