"""Signal ownership/restoration without delivering signals to the pytest host."""
import asyncio
from types import SimpleNamespace

import pytest

from xime.core.bootstrap import _signals


def fake_signals(monkeypatch):
    handlers = {2: object(), 15: object(), 21: object()}
    original = handlers.copy()

    def install(signum, handler):
        previous = handlers[signum]
        handlers[signum] = handler
        return previous

    monkeypatch.setattr(_signals, 'signal', SimpleNamespace(
        SIGINT=2, SIGTERM=15, SIGBREAK=21, signal=install))
    return handlers, original


@pytest.mark.asyncio
@pytest.mark.parametrize('fail', [False, True])
async def test_worker_restores_handlers_and_context(monkeypatch, fail):
    handlers, original = fake_signals(monkeypatch)

    async def main():
        assert _signals.worker_signals_owned()
        if fail:
            raise ValueError('intentional startup failure')

    if fail:
        with pytest.raises(ValueError, match='intentional'):
            await _signals.run_with_signals(main)
    else:
        await _signals.run_with_signals(main)
    assert handlers == original
    assert not _signals.worker_signals_owned()


@pytest.mark.asyncio
async def test_non_main_thread_does_not_own_process_signals(monkeypatch):
    handlers, original = fake_signals(monkeypatch)
    monkeypatch.setattr(_signals, 'threading', SimpleNamespace(
        current_thread=lambda: 1, main_thread=lambda: 2))

    async def main():
        assert not _signals.worker_signals_owned()

    await _signals.run_with_signals(main)
    assert handlers == original


@pytest.mark.asyncio
async def test_repeated_signals_do_not_cancel_cleanup_twice(monkeypatch):
    handlers, original = fake_signals(monkeypatch)
    ready = asyncio.Event()
    cleaning = asyncio.Event()
    finished = []

    async def main():
        ready.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass
        finally:
            cleaning.set()
            await asyncio.sleep(0.02)
            finished.append('cleaned')

    task = asyncio.create_task(_signals.run_with_signals(main))
    await ready.wait()
    handlers[15](15, None)
    await cleaning.wait()
    handlers[2](2, None)
    await task
    assert finished == ['cleaned']
    assert task.cancelling() == 1
    assert handlers == original
