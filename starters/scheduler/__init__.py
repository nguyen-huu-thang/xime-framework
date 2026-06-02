from ._config import CronJob, IntervalJob, SchedulerConfig, configure_scheduler
from ._job import ScheduledJob

# __all__ controls which classes DI scanner registers from dependency.scan("starters.scheduler").
# Empty list → scanner finds nothing to register — correct, because:
#
#   SchedulerRunner   : framework-internal, created by StartupOrchestrator with a resolver
#                       callback after DI is built. NOT imported here — it has a top-level
#                       apscheduler import that would fail if apscheduler is not installed.
#   ScheduledJob      : Protocol — scanner skips all Protocols automatically.
#   CronJob / IntervalJob / SchedulerConfig : dataclasses / config objects, not services.
#   configure_scheduler : function, not a class.
#
# All public types are still importable directly:
#   from starters.scheduler import configure_scheduler, SchedulerConfig, CronJob, ScheduledJob
__all__: list[str] = []
