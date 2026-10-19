"""One locked append/rotation writer, with bounded queue and bounded shutdown."""

from __future__ import annotations

import logging
import logging.handlers
import queue
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from xime.core.config import FileLoggingConfig
from xime.core.exception.framework import StartupException

from ._fallback import process_stderr
from ._records import render


class EmergencyReporter:
    """Bypass logging entirely: no recursion and no failing record/secret echoed."""

    def __init__(self) -> None:
        self._last = float("-inf")
        self.dropped = 0

    def report(self, reason: str) -> None:
        now = time.monotonic()
        if now - self._last < 5.0:
            return
        self._last = now
        try:
            stream = process_stderr()
            stream.write(f"Xime file logging: {reason}; dropped={self.dropped}\n")
            stream.flush()
        except Exception:
            pass


@dataclass(frozen=True)
class LoggingTransport:
    """Only the spawn-context queue crosses a process boundary, never handlers."""

    queue: Any


class FileProducer(logging.handlers.QueueHandler):
    def __init__(self, transport: LoggingTransport, cfg: FileLoggingConfig, service: str) -> None:
        super().__init__(transport.queue)
        self._cfg = cfg
        self._service = service
        self.reporter = EmergencyReporter()

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        line = render(record, self._service, self._cfg.format, self._cfg.max_record_bytes)
        # Drop every original object/traceback, including unpickleable extras.
        return logging.LogRecord("xime.file", record.levelno, "", 0, line, (), None)

    def emit(self, record: logging.LogRecord) -> None:
        # multiprocessing.Queue emits DEBUG while starting its own feeder. Never
        # send those internals back through that same queue (recursive deadlock).
        if record.name == "multiprocessing" or record.name.startswith("multiprocessing."):
            return
        try:
            self.enqueue(self.prepare(record))
        except queue.Full:
            self.reporter.dropped += 1
            self.reporter.report("queue full (records discarded)")
        except Exception:
            self.reporter.dropped += 1
            self.reporter.report("record could not be queued")


class _RotationHandler(logging.handlers.RotatingFileHandler):
    def __init__(self, path: Path, cfg: FileLoggingConfig, reporter: EmergencyReporter) -> None:
        self._reporter = reporter
        super().__init__(
            path,
            mode="a",
            maxBytes=cfg.max_bytes,
            backupCount=cfg.backup_count,
            encoding="utf-8",
            errors="replace",
        )
        self.setFormatter(logging.Formatter("%(message)s"))

    def handleError(self, record: logging.LogRecord) -> None:  # noqa: N802
        self._reporter.dropped += 1
        self._reporter.report("write/rotation failed; check disk and permissions")


class _FileLock:
    def __init__(self, path: Path) -> None:
        self._stream = path.open("a+b")
        try:
            if sys.platform == "win32":
                import msvcrt

                self._stream.seek(0, 2)
                if not self._stream.tell():
                    self._stream.write(b"\0")
                    self._stream.flush()
                self._stream.seek(0)
                msvcrt.locking(self._stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self._stream.close()
            raise

    def close(self) -> None:
        self._stream.close()  # OS releases the lock; retain sidecar to avoid unlink races.


class _Listener(logging.handlers.QueueListener):
    _sentinel = None

    def __init__(
        self, transport: LoggingTransport, handler: _RotationHandler, lock: _FileLock
    ) -> None:
        super().__init__(transport.queue, handler)
        self._source: Any = transport.queue
        self._handler = handler
        self._lock = lock
        self._stopping = threading.Event()

    def _monitor(self) -> None:
        try:
            while True:
                try:
                    record = self._source.get(timeout=0.2)
                except queue.Empty:
                    if self._stopping.is_set():
                        return
                    continue
                except (EOFError, OSError, ValueError):
                    self._handler._reporter.report("log queue unavailable")
                    return
                if record is self._sentinel:
                    return
                try:
                    self.handle(record)
                except Exception:
                    self._handler._reporter.dropped += 1
                    self._handler._reporter.report("writer could not handle record")
        finally:
            # If disk I/O stalls, ownership stays held until this thread exits.
            try:
                self._handler.close()
            except Exception:
                self._handler._reporter.report("file close failed")
            finally:
                self._lock.close()

    def stop_bounded(self, timeout: float) -> None:
        started = time.monotonic()
        try:
            self._source.put(self._sentinel, timeout=min(timeout, 0.2))
        except (queue.Full, OSError, ValueError):
            self._stopping.set()
        thread = self._thread
        if thread is not None:
            thread.join(max(0.0, timeout - (time.monotonic() - started)))
            if thread.is_alive():
                self._handler._reporter.report("flush timed out; final records may be lost")
            else:
                self._thread = None


def close_queue(transport: LoggingTransport, timeout: float) -> None:
    """Drain a process's feeder with a deadline; stdlib Queue has no feeder."""
    q = transport.queue
    if not hasattr(q, "close"):
        return
    reporter = EmergencyReporter()
    try:
        q.close()
    except (OSError, ValueError):
        reporter.report("producer queue close failed")
        return

    def join_feeder() -> None:
        try:
            q.join_thread()
        except (OSError, ValueError):
            reporter.report("producer queue flush failed")

    waiter = threading.Thread(target=join_feeder, name="xime-log-flush", daemon=True)
    waiter.start()
    waiter.join(timeout)
    if waiter.is_alive():
        q.cancel_join_thread()
        EmergencyReporter().report("producer flush timed out; final records may be lost")


class FileWriter:
    def __init__(self, cfg: FileLoggingConfig, *, multiprocess: bool) -> None:
        self.reporter = EmergencyReporter()
        lock: _FileLock | None = None
        handler: _RotationHandler | None = None
        transport: LoggingTransport | None = None
        try:
            path = Path(cfg.path).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            lock = _FileLock(path.with_name(path.name + ".lock"))
            handler = _RotationHandler(path, cfg, self.reporter)
            q: Any
            if multiprocess:
                from xime.core.shared import MP_CONTEXT

                q = MP_CONTEXT.Queue(maxsize=cfg.queue_capacity)
            else:
                q = queue.Queue(maxsize=cfg.queue_capacity)
            self.transport = LoggingTransport(q)
            transport = self.transport
            self._listener = _Listener(self.transport, handler, lock)
            self._listener.start()
        except Exception as exc:
            if handler is not None:
                handler.close()
            if lock is not None:
                lock.close()
            if transport is not None:
                close_queue(transport, cfg.shutdown_timeout)
            raise StartupException(
                f"Cannot open logging.file.path ({type(exc).__name__}); check directory permissions and exclusive file ownership"
            ) from None
        self._cfg = cfg

    def close(self) -> None:
        self._listener.stop_bounded(self._cfg.shutdown_timeout)
        close_queue(self.transport, self._cfg.shutdown_timeout)
