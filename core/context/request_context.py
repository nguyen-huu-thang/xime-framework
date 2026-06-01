from __future__ import annotations

from contextvars import ContextVar
from typing import Any


class _RequestContext:
    """
    A key-value store for the current async context (one dict per request).

    Unlike SecurityContext fields which have fixed semantics, this context
    accepts arbitrary data — trace IDs, locale, correlation IDs, feature flags,
    or anything else middleware and business code needs to share.

    The backing dict is created lazily on first set() call.
    """

    def __init__(self) -> None:
        self._var: ContextVar[dict[str, Any] | None] = ContextVar(
            "xime_request_context", default=None
        )

    def set(self, key: str, value: Any) -> None:
        """Insert or overwrite a value for the given key."""
        ctx = self._var.get()
        if ctx is None:
            ctx = {}
            self._var.set(ctx)
        ctx[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for key, or default if not set."""
        ctx = self._var.get()
        if ctx is None:
            return default
        return ctx.get(key, default)

    def delete(self, key: str) -> None:
        """Remove a key. No-op if the key does not exist."""
        ctx = self._var.get()
        if ctx is not None:
            ctx.pop(key, None)

    def clear(self) -> None:
        """Remove all keys for the current async task."""
        self._var.set(None)

    def all(self) -> dict[str, Any]:
        """Return a shallow copy of the entire context dict."""
        ctx = self._var.get()
        return dict(ctx) if ctx else {}

    def __contains__(self, key: str) -> bool:
        ctx = self._var.get()
        return key in ctx if ctx else False


# Module-level singleton — import this directly
#
#   from core.context import request_context
#   from core.context.request_context import request_context
request_context = _RequestContext()
