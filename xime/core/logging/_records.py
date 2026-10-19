"""Capture task context and sanitize/limit file records BEFORE queueing them."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from itertools import islice
from typing import Any

from xime.core.context import request_context

_RESERVED = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}
_SECRET = re.compile(
    r"password|passwd|secret|token|credential|authorization|cookie|api.?key|private.?key|^key$",
    re.I,
)
_PEM = re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----.*?(?:-----END [^-]*PRIVATE KEY-----|$)", re.S)
_AUTH = re.compile(r"\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+", re.I)
_URL = re.compile(r"(\b[a-z][a-z0-9+.-]*://[^\s/:@]+:)[^\s@]+(@)", re.I)
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_PAIR = re.compile(
    r"""((?:password|passwd|secret|token|credential|authorization|cookie|api[_-]?key|private[_-]?key)["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;}&]+)""",
    re.I,
)


def redact(text: str) -> str:
    text = _PEM.sub("[REDACTED PRIVATE KEY]", text)
    text = _AUTH.sub(r"\1 [REDACTED]", text)
    text = _URL.sub(r"\1***\2", text)
    text = _JWT.sub("[REDACTED JWT]", text)
    return _PAIR.sub(r"\1***", text)


def _text(value: Any, limit: int) -> str:
    try:
        text = redact(str(value))
    except Exception:
        text = "[unformattable]"
    return text.encode("utf-8", errors="replace")[:limit].decode("utf-8", errors="ignore")


def _safe(value: Any, limit: int, depth: int = 0) -> Any:
    if depth > 4:
        return "[depth limit]"
    if isinstance(value, dict):
        return {
            _text(k, 120): "***" if _SECRET.search(str(k)) else _safe(v, limit, depth + 1)
            for k, v in islice(value.items(), 32)
        }
    if isinstance(value, (list, tuple)):
        return [_safe(v, limit, depth + 1) for v in value[:32]]
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        # NaN/Infinity are not JSON numbers.
        import math

        return value if math.isfinite(value) else str(value)
    return _text(value, limit)


def render(record: logging.LogRecord, service: str, style: str, limit: int) -> str:
    """Return one bounded line. A malformed app argument must not kill a writer."""
    try:
        message = record.getMessage()
    except Exception:
        message = "[log message formatting failed]"
    payload: dict[str, Any] = {
        "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
        "service": _text(service, 120),
        "pid": record.process,
        "process": _text(record.processName, 120),
        "logger": _text(record.name, 160),
        "level": _text(record.levelname, 20),
        "message": _text(message, limit),
    }
    for key in ("request_id", "correlation_id"):
        value = getattr(record, key, None) or request_context.get(key)
        if value is not None:
            payload[key] = _text(value, 160)
    extras = {
        k: v
        for k, v in record.__dict__.items()
        if k not in _RESERVED and k not in payload and not k.startswith("_")
    }
    if extras:
        payload["fields"] = _safe(extras, min(limit, 2048))
    if record.exc_info:
        try:
            payload["exception"] = _text(
                logging.Formatter().formatException(record.exc_info), limit
            )
        except Exception:
            payload["exception"] = "[exception formatting failed]"
    elif record.exc_text:
        payload["exception"] = _text(record.exc_text, limit)
    if record.stack_info:
        payload["stack"] = _text(record.stack_info, limit)

    def encode() -> str:
        if style == "json":
            return json.dumps(payload, ensure_ascii=False, allow_nan=False)
        # JSON-escape embedded newlines/controls even in text files.
        return " | ".join(
            f"{key}={json.dumps(value, ensure_ascii=False)}" for key, value in payload.items()
        )

    line = encode()
    if len(line.encode("utf-8")) > limit:
        payload.pop("fields", None)
        payload.pop("stack", None)
        payload["truncated"] = True
        budget = max(32, (limit - 800) // 2)
        payload["message"] = _text(payload["message"], budget)
        if "exception" in payload:
            payload["exception"] = _text(payload["exception"], budget)
        line = encode()
        while len(line.encode("utf-8")) > limit:
            # Escaping and long optional labels can exhaust even a small budget.
            for key in (
                "message",
                "exception",
                "service",
                "process",
                "logger",
                "request_id",
                "correlation_id",
            ):
                if key in payload:
                    payload[key] = payload[key][: len(payload[key]) // 2]
            line = encode()
    return line
