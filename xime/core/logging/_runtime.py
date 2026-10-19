"""Logging ownership per Application; root handlers supplied by apps are explicit."""

from __future__ import annotations

import logging
from typing import TextIO

from xime.core.config import LoggingConfig
from xime.core.exception.framework import StartupException

from ._file import FileProducer, FileWriter, LoggingTransport, close_queue


def level_number(value: str) -> int:
    number = logging.getLevelName(value.upper())
    return number if isinstance(number, int) else logging.INFO


class LoggingRuntime:
    def __init__(
        self,
        cfg: LoggingConfig,
        *,
        service: str,
        root: logging.Logger | None = None,
        console_handler: logging.Handler | None = None,
        transport: LoggingTransport | None = None,
        multiprocess: bool = False,
        stderr_stream: TextIO | None = None,
    ) -> None:
        self._cfg = cfg
        self._root = root if root is not None else logging.getLogger()
        self._previous_level = self._root.level
        self._previous_handlers = list(self._root.handlers)
        self._custom = console_handler
        self._custom_level = console_handler.level if console_handler else logging.NOTSET
        self._owned: list[logging.Handler] = []
        self._writer: FileWriter | None = None
        self.transport: LoggingTransport | None = None
        self._closed = False
        self._managed = False
        self._custom_stream: TextIO | None = None
        if not cfg.enabled:
            return
        # Old apps/pytest keep full ownership until an explicit handover.
        if self._root.handlers and console_handler is None:
            if cfg.file.enabled:
                raise StartupException(
                    "Root logging is application-owned; register its console with Application.use_logging_console(handler) before enabling logging.file"
                )
            return
        if console_handler is not None and any(
            h is not console_handler for h in self._root.handlers
        ):
            raise StartupException(
                "Application.use_logging_console requires a single console owner on root"
            )
        self._managed = True
        try:
            levels: list[int] = []
            if cfg.console.enabled:
                handler = console_handler or logging.StreamHandler(stderr_stream)
                if console_handler is not None and stderr_stream is not None and isinstance(handler, logging.StreamHandler):
                    try:
                        uses_fd2 = handler.stream.fileno() == 2
                    except (AttributeError, OSError, ValueError):
                        uses_fd2 = False
                    if uses_fd2:
                        self._custom_stream = handler.setStream(stderr_stream)
                if console_handler is None:
                    handler.setFormatter(logging.Formatter(cfg.format, cfg.datefmt))
                console_level = level_number(cfg.console.level or cfg.level)
                if (
                    console_handler is not None
                    and cfg.console.level is None
                    and "level" not in cfg.model_fields_set
                ):
                    console_level = handler.level or self._previous_level
                handler.setLevel(console_level)
                levels.append(handler.level)
                if handler not in self._root.handlers:
                    self._root.addHandler(handler)
                if console_handler is None:
                    self._owned.append(handler)
            elif console_handler is not None:
                self._root.removeHandler(console_handler)
            if cfg.file.enabled:
                if transport is None:
                    self._writer = FileWriter(cfg.file, multiprocess=multiprocess)
                    transport = self._writer.transport
                self.transport = transport
                producer = FileProducer(transport, cfg.file, cfg.service_name or service)
                producer.setLevel(level_number(cfg.file.level or cfg.level))
                self._root.addHandler(producer)
                self._owned.append(producer)
                levels.append(producer.level)
            # Empty sinks must stay silent (avoid logging.lastResort).
            if not levels:
                handler = logging.NullHandler()
                self._root.addHandler(handler)
                self._owned.append(handler)
            self._root.setLevel(min(levels) if levels else logging.CRITICAL + 1)
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if not self._managed:
            return
        for handler in self._owned:
            self._root.removeHandler(handler)
            handler.close()
        if self._custom is not None:
            if self._custom_stream is not None and isinstance(self._custom, logging.StreamHandler):
                self._custom.setStream(self._custom_stream)
            self._custom.setLevel(self._custom_level)
            if self._custom in self._previous_handlers and self._custom not in self._root.handlers:
                self._root.addHandler(self._custom)
            elif self._custom not in self._previous_handlers:
                self._root.removeHandler(self._custom)
        if self._writer is not None:
            self._writer.close()
        elif self.transport is not None:
            close_queue(self.transport, self._cfg.file.shutdown_timeout)
        self._root.setLevel(self._previous_level)
