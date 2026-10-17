from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

_logger = logging.getLogger(__name__)


def _report_cleanup_failure(
    primary: BaseException, failure: BaseException, operation: str,
) -> None:
    # Preserve the original exception and its cause, but make cleanup visible.
    # Giữ lỗi gốc và cause; lỗi dọn dẹp vẫn có note và traceback trong log.
    primary.add_note(f"SQLAlchemy session {operation} also failed ({type(failure).__name__})")
    _logger.error(
        "SQLAlchemy session %s failed during cleanup", operation,
        exc_info=(type(failure), failure, failure.__traceback__),
    )


async def _close_session(session: AsyncSession, primary: BaseException | None) -> None:
    try:
        await session.close()
    except BaseException as failure:
        if primary is None or not isinstance(failure, Exception):
            raise
        _report_cleanup_failure(primary, failure, "close")
