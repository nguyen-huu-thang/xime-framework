from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any


class _SecurityField:
    """
    A single typed slot in the security context, backed by its own ContextVar.
    Each field is independent — set/get/clear without touching the others.
    """

    def __init__(self, var_name: str) -> None:
        self._var: ContextVar[Any] = ContextVar(f"xime_security_{var_name}", default=None)

    def get(self) -> Any:
        """Return the current value, or None if not set."""
        return self._var.get()

    def set(self, value: Any) -> Token:
        """
        Set the value for the current async task.
        Returns a Token to restore the previous value via reset().
        """
        return self._var.set(value)

    def reset(self, token: Token) -> None:
        """Restore the value to what it was before the matching set() call."""
        self._var.reset(token)

    def clear(self) -> None:
        """Remove the value for the current async task."""
        self._var.set(None)


# ---------------------------------------------------------------------------
# Module-level singletons — import these directly
#
#   from core.security.context import identity, permissions
#   from core.security import identity, permissions
# ---------------------------------------------------------------------------

identity = _SecurityField("identity")
"""Who is making the request: user_id, username, subject, UUID, etc."""

credentials = _SecurityField("credentials")
"""Raw auth material: password, token string, api_key, certificate.
Clear after authentication completes if not needed further."""

credential_type = _SecurityField("credential_type")
"""What kind of credential was used.
Use the framework's CredentialType or your own Enum."""

permissions = _SecurityField("permissions")
"""What the identity is allowed to do.
Pass a set of your own Permission Enum values."""
