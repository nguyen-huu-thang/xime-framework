from ._config import CronJob as CronJob
from ._config import IntervalJob as IntervalJob
from ._config import SchedulerConfig as SchedulerConfig
from ._config import configure_scheduler as configure_scheduler
from ._job import ScheduledJob as ScheduledJob

# The `X as X` form is PEP 484's explicit re-export marker - see the note in
# xime/starters/jwt/__init__.py for why __all__ cannot serve that role here.
#
# __all__ controls which classes DI scanner registers from dependency.scan("xime.starters.scheduler").
# Empty list → scanner finds nothing to register - correct, because:
#
#   SchedulerRunner   : framework-internal, created by StartupOrchestrator with a resolver
#                       callback after DI is built. NOT imported here - it has a top-level
#                       apscheduler import that would fail if apscheduler is not installed.
#   ScheduledJob      : Protocol - scanner skips all Protocols automatically.
#   CronJob / IntervalJob / SchedulerConfig : dataclasses / config objects, not services.
#   configure_scheduler : function, not a class.
#
# All public types are still importable directly:
#   from xime.starters.scheduler import configure_scheduler, SchedulerConfig, CronJob, ScheduledJob
__all__: list[str] = []
