"""Process shutdown belongs to the whole Application, not an individual server."""
from __future__ import annotations

import asyncio
import signal
import threading
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from types import FrameType
from typing import Any

_OWNED: ContextVar[bool] = ContextVar('xime_worker_signals_owned', default=False)


def worker_signals_owned() -> bool:
    return _OWNED.get()


async def run_with_signals(main: Callable[[], Awaitable[None]]) -> None:
    """Cancel once, let all adapters/hooks unwind, then restore prior handlers.

    Embedding start()/stop() does not install process-global handlers. Only the
    synchronous run() worker entry calls this wrapper, and only on the main
    thread. Repeated signals cannot cancel cleanup a second time; supervisors
    retain their existing timeout/kill fallback.
    """
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    previous: dict[int, Any] = {}
    stopping = False

    def request_stop(signum: int, frame: FrameType | None) -> None:
        nonlocal stopping
        if not stopping and task is not None:
            stopping = True
            loop.call_soon_threadsafe(task.cancel)

    try:
        if threading.current_thread() is threading.main_thread():
            for name in ('SIGINT', 'SIGTERM', 'SIGBREAK'):
                signum = getattr(signal, name, None)
                if signum is None:
                    continue
                try:
                    previous[signum] = signal.signal(signum, request_stop)
                except (ValueError, OSError):
                    continue
        token = _OWNED.set(bool(previous))
        try:
            await main()
        finally:
            _OWNED.reset(token)
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
