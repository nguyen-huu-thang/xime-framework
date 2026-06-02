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
        """
        Insert or overwrite a value for the given key.

        Always creates a new dict and calls _var.set() so the ContextVar
        binding is updated in the current async context only. This prevents
        child tasks (created via asyncio.create_task) from sharing the same
        dict object and accidentally mutating the parent's context.
        """
        ctx = dict(self._var.get() or {})
        ctx[key] = value
        self._var.set(ctx)

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for key, or default if not set."""
        ctx = self._var.get()
        if ctx is None:
            return default
        return ctx.get(key, default)

    def delete(self, key: str) -> None:
        """
        Remove a key. No-op if the key does not exist.

        Creates a new dict (same isolation reason as set()).
        """
        ctx = self._var.get()
        if ctx is None or key not in ctx:
            return
        new_ctx = dict(ctx)
        del new_ctx[key]
        self._var.set(new_ctx)

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

    def __len__(self) -> int:
        ctx = self._var.get()
        return len(ctx) if ctx else 0

    def __repr__(self) -> str:
        return f"RequestContext({self.all()!r})"


# Module-level singleton — import this directly
#
#   from core.context import request_context
#   from core.context.request_context import request_context
request_context = _RequestContext()
