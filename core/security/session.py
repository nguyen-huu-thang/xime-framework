from __future__ import annotations

from enum import Enum
from typing import Any

from core.security.context import (
    credentials as _credentials,
    credential_type as _credential_type,
    identity as _identity,
    permissions as _permissions,
)


def authenticate(
    *,
    identity: Any = None,
    credentials: Any = None,
    credential_type: Enum | None = None,
    permissions: set[Enum] | None = None,
) -> None:
    """
    Set security fields for the current async task in one call.

    Called by authentication middleware after verifying the request.
    Only fields explicitly provided are written — omitted fields stay as-is.

    Usage:
        authenticate(
            identity="user_123",
            credential_type=CredentialType.TOKEN,
            permissions={Permission.READ, Permission.WRITE},
        )
    """
    if identity is not None:
        _identity.set(identity)
    if credentials is not None:
        _credentials.set(credentials)
    if credential_type is not None:
        _credential_type.set(credential_type)
    if permissions is not None:
        _permissions.set(permissions)


def clear_security() -> None:
    """
    Remove all security fields for the current async task.

    Called by middleware at the end of a request, or in tests to reset state.
    """
    _identity.clear()
    _credentials.clear()
    _credential_type.clear()
    _permissions.clear()
