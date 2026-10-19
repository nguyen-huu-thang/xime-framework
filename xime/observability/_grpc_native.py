"""Native stderr is a PROCESS resource. It is never restored after grpc import."""

from __future__ import annotations

import atexit
import contextvars
import logging
import os
import queue
import socket
import sys
import threading
import time
from dataclasses import asdict, dataclass
from typing import TextIO

from xime.core.exception.framework import StartupException
from xime.core.logging._fallback import set_process_stderr

from ._config import GrpcHandshakeLoggingConfig, GrpcHandshakeLoggingStats
from ._grpc_parser import (
    NativeFailure,
    NativeFramer,
    canonical_ip,
    handshaker_payload,
    parse_failure,
)

_LOG = logging.getLogger("xime.grpc.handshake")


def _windows_stderr() -> None:
    if sys.platform == "win32":
        import ctypes
        import msvcrt
        from ctypes import wintypes

        setter = ctypes.WinDLL("kernel32", use_last_error=True).SetStdHandle
        setter.argtypes = (wintypes.DWORD, wintypes.HANDLE)
        setter.restype = wintypes.BOOL
        if not setter(wintypes.DWORD(-12), msvcrt.get_osfhandle(2)):
            raise ctypes.WinError(ctypes.get_last_error())


@dataclass(frozen=True)
class _Listener:
    generation: int
    server_id: str
    ips: frozenset[str]
    port: int


@dataclass(frozen=True)
class _Event:
    generation: int
    server_id: str | None
    failure: NativeFailure
    observed: float


class NativeLoggingLease:
    def __init__(self, collector: NativeCollector, generation: int) -> None:
        self.collector, self.generation = collector, generation

    def register_listener(self, server_id: str, host: str, port: int) -> int:
        return self.collector.register(self.generation, server_id, host, port)

    def unregister_listener(self, token: int) -> None:
        self.collector.unregister(token)

    def close(self) -> None:
        self.collector.detach(self.generation)


class NativeCollector:
    def __init__(self, config: GrpcHandshakeLoggingConfig, *, version: str, quiet: bool) -> None:
        self.config, self.version = config, version
        self.pid = os.getpid()
        self._lock = threading.RLock()
        self._counts = asdict(GrpcHandshakeLoggingStats())
        self._listeners: dict[int, _Listener] = {}
        self._next_token = 0
        self._generation = 0
        self._active: int | None = None
        self._events: queue.Queue[_Event | threading.Event] = queue.Queue(config.queue_capacity)
        self._exiting = False
        self._drained = threading.Event()
        self._drain_lock = threading.Lock()
        self._drain_pending = False
        self._drain_marker = (
            b"\x00XIME_NATIVE_DRAIN_" + os.urandom(16).hex().encode("ascii") + b"\n"
        )
        self._rate_start = time.monotonic()
        self._rate_count = 0
        self._summary_at = time.monotonic()
        self._last_losses = (0, 0, 0, 0, 0, 0, 0)
        self._original = os.dup(2)
        self.console_stream: TextIO = os.fdopen(
            os.dup(self._original), "w", encoding="utf-8", errors="backslashreplace", buffering=1
        )
        read_fd, write_fd = os.pipe()
        self._read = read_fd
        self._framer = NativeFramer(
            limit=config.max_record_bytes,
            quiet=quiet,
            forward=self._forward,
            record=self._record,
            count=self._increment,
            drain_marker=self._drain_marker,
            drained=self._drained.set,
        )
        try:
            os.dup2(write_fd, 2)
            os.close(write_fd)
            _windows_stderr()
            self._reader = threading.Thread(
                target=self._read_forever, name="xime-grpc-native-reader", daemon=True
            )
            self._worker = threading.Thread(
                target=self._dispatch_forever, name="xime-grpc-native-events", daemon=True
            )
            self._reader.start()
            self._worker.start()
        except BaseException:
            # grpc has not been imported yet: rollback is safe ONLY here.
            os.dup2(self._original, 2)
            _windows_stderr()
            self.console_stream.close()
            os.close(self._original)
            os.close(read_fd)
            raise
        set_process_stderr(self.console_stream)
        atexit.register(self._at_exit)

    def _forward(self, data: bytes) -> None:
        view = memoryview(data)
        try:
            while view:
                written = os.write(self._original, view)
                if written <= 0:
                    return
                view = view[written:]
        except OSError:
            # The original stderr can disappear (e.g. a closed supervisor pipe).
            # Keep draining native input so gRPC cannot fill our pipe forever.
            self._increment("passthrough_errors")

    def _increment(self, name: str) -> None:
        with self._lock:
            self._counts[name] += 1

    def stats(self) -> GrpcHandshakeLoggingStats:
        with self._lock:
            return GrpcHandshakeLoggingStats(**self._counts)

    def attach(self) -> NativeLoggingLease:
        node: logging.Logger | None = _LOG
        handlers: list[logging.Handler] = []
        while node is not None:
            handlers.extend(node.handlers)
            if not node.propagate:
                break
            node = node.parent
        if not handlers and logging.lastResort is not None:
            handlers.append(logging.lastResort)
        for handler in handlers:
            if not isinstance(handler, logging.StreamHandler):
                continue
            try:
                uses_pipe = handler.stream.fileno() == 2
            except (AttributeError, OSError, ValueError):
                uses_pipe = False
            if uses_pipe:
                raise StartupException(
                    "Native gRPC logging console must bypass FD 2; use logging.enabled=true and Application.use_logging_console(handler) for an app-owned stderr console"
                )
        with self._lock:
            if os.getpid() != self.pid:
                raise StartupException(
                    "Native gRPC logging requires spawn; an inherited fork collector cannot be reused"
                )
            if self._active is not None:
                raise StartupException(
                    "Native gRPC logging already belongs to a running Application"
                )
            self._generation += 1
            self._active = self._generation
            return NativeLoggingLease(self, self._generation)

    def register(self, generation: int, server_id: str, host: str, port: int) -> int:
        host = host.strip("[]")
        if host in ("0.0.0.0", "::"):
            ips = frozenset({"*"})
        else:
            ips = frozenset(
                canonical_ip(str(row[4][0]))
                for row in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            )
        with self._lock:
            if self._active != generation:
                raise StartupException(
                    "Native gRPC listener registered outside its Application lifecycle"
                )
            self._next_token += 1
            self._listeners[self._next_token] = _Listener(generation, server_id, ips, port)
            return self._next_token

    def unregister(self, token: int) -> None:
        self._drain_input()
        with self._lock:
            self._listeners.pop(token, None)

    def _barrier(self, timeout: float = 2.0) -> None:
        marker = threading.Event()
        started = time.monotonic()
        try:
            self._events.put(marker, timeout=min(timeout, 0.1))
        except queue.Full:
            self._increment("queue_dropped")
            return
        if not marker.wait(max(0.0, timeout - (time.monotonic() - started))):
            self._increment("flush_timeouts")

    def detach(self, generation: int) -> None:
        self._drain_input()
        with self._lock:
            self._listeners = {
                k: v for k, v in self._listeners.items() if v.generation != generation
            }
        self._barrier()
        with self._lock:
            if self._active == generation:
                self._active = None

    def _drain_input(self, timeout: float = 2.0) -> None:
        with self._drain_lock:
            if self._drain_pending and not self._drained.is_set():
                if not self._drained.wait(timeout):
                    self._increment("flush_timeouts")
                return
            self._drained.clear()
            self._drain_pending = True

            def signal_reader() -> None:
                try:
                    os.write(2, self._drain_marker)
                except OSError:
                    self._drained.set()

            threading.Thread(
                target=signal_reader, name="xime-grpc-native-flush", daemon=True
            ).start()
            if not self._drained.wait(timeout):
                self._increment("flush_timeouts")

    def _record(self, data: bytes) -> None:
        failure = parse_failure(data)
        if failure is None:
            payload = handshaker_payload(data)
            succeeded = payload is not None and (payload.startswith(b"OK ") or payload == b"OK")
            if not succeeded and b"grpc.internal.server_credentials=" in data:
                self._increment("unparsed")
            return
        with self._lock:
            listeners = tuple(self._listeners.values())
            generation = self._active
        # In particular, the supervisor has no inbound listeners. It must never
        # re-attribute inherited worker stderr to its own PID.
        if generation is None or self._exiting:
            self._increment("inactive")
            return
        own = [item for item in listeners if item.generation == generation]
        if not own:
            self._increment("unregistered")
            return
        matched = [
            item
            for item in own
            if failure.local is not None
            and item.port == failure.local[1]
            and ("*" in item.ips or failure.local[0] in item.ips)
        ]
        if failure.local is not None and not matched:
            self._increment("unregistered")
            return
        server_id = matched[0].server_id if len(matched) == 1 else None
        self._increment("received")
        event = _Event(generation, server_id, failure, time.time())
        try:
            self._events.put_nowait(event)
        except queue.Full:
            self._increment("queue_dropped")

    def _read_forever(self) -> None:
        while True:
            try:
                data = os.read(self._read, 8192)
                if not data:
                    if not self._exiting:
                        self._increment("read_errors")
                    return
                self._framer.feed(data)
            except OSError:
                self._increment("read_errors")
                try:
                    os.close(self._read)
                except OSError:
                    pass
                return
            except Exception:
                self._increment("unparsed")
                self._forward(data)

    def _emit(self, event: _Event) -> None:
        now = time.monotonic()
        if now - self._rate_start >= 1.0:
            self._rate_start, self._rate_count = now, 0
        if self._rate_count >= self.config.rate_limit_per_second:
            self._increment("rate_limited")
            return
        self._rate_count += 1
        level = logging.getLevelName(self.config.level)
        if not _LOG.isEnabledFor(level):
            self._increment("logger_filtered")
            return
        failure = event.failure
        fields = {
            "event": "grpc_tls_handshake_failed",
            "server_id": event.server_id,
            "remote_ip": failure.remote[0] if failure.remote else None,
            "remote_port": failure.remote[1] if failure.remote else None,
            "local_ip": failure.local[0] if failure.local else None,
            "local_port": failure.local[1] if failure.local else None,
            "cause": failure.cause,
            "grpcio_version": self.version,
            "address_status": "complete" if failure.remote and failure.local else "unavailable",
        }
        record = _LOG.makeRecord(
            _LOG.name,
            level,
            __file__,
            0,
            "gRPC TLS handshake failed: server=%s peer=%s:%s local=%s:%s cause=%s",
            (
                event.server_id,
                fields["remote_ip"],
                fields["remote_port"],
                fields["local_ip"],
                fields["local_port"],
                failure.cause,
            ),
            None,
            extra=fields,
        )
        record.relativeCreated += (event.observed - record.created) * 1000
        record.created = event.observed
        record.msecs = (event.observed - int(event.observed)) * 1000
        _LOG.handle(record)
        self._increment("emitted")

    def _summary(self, force: bool = False) -> None:
        if not force and time.monotonic() - self._summary_at < 5.0:
            return
        self._summary_at = time.monotonic()
        stats = self.stats()
        losses = (
            stats.rate_limited,
            stats.queue_dropped,
            stats.truncated,
            stats.unparsed,
            stats.passthrough_errors,
            stats.read_errors,
            stats.flush_timeouts,
        )
        if losses == self._last_losses:
            return
        self._last_losses = losses
        if self._active is not None and not self._exiting:
            _LOG.warning(
                "gRPC native logging discarded or could not parse records",
                extra={
                    "event": "grpc_handshake_logging_summary",
                    "rate_limited": losses[0],
                    "queue_dropped": losses[1],
                    "truncated": losses[2],
                    "unparsed": losses[3],
                    "passthrough_errors": losses[4],
                    "read_errors": losses[5],
                    "flush_timeouts": losses[6],
                },
            )

    def _dispatch_forever(self) -> None:
        while True:
            try:
                item = self._events.get(timeout=1.0)
            except queue.Empty:
                try:
                    self._summary()
                except Exception:
                    self._increment("queue_dropped")
                continue
            try:
                if isinstance(item, threading.Event):
                    try:
                        self._summary(force=True)
                    finally:
                        item.set()
                elif item.generation == self._active and not self._exiting:
                    contextvars.Context().run(self._emit, item)
                else:
                    self._increment("inactive")
            except Exception:
                self._increment("queue_dropped")
            finally:
                self._events.task_done()

    def _at_exit(self) -> None:
        self._drain_input()
        self._barrier()
        self._exiting = True
        self._active = None
        # Deliberately keep FD 2, reader and original destination alive for late
        # native destructors. The OS releases them at process exit. No restore.
