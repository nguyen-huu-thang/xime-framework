from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ScheduledJob(Protocol):
    """
    Contract for all scheduled jobs managed by the Xime scheduler starter.

    Implement this Protocol to mark a class as a runnable scheduled job.
    The framework calls run() on each scheduled interval or cron tick.

    Constructor injection works normally — declare dependencies in __init__
    and the DI container resolves them before the scheduler starts.

    Example:
        class DailyReportJob:
            def __init__(self, report_service: ReportService) -> None:
                self._report_service = report_service

            async def run(self) -> None:
                await self._report_service.generate_daily()
    """

    async def run(self) -> None: ...
