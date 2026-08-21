from __future__ import annotations

from typing import Any

from xime.core.security.context import (
    credential_type as _credential_type,
)
from xime.core.security.context import (
    credentials as _credentials,
)
from xime.core.security.context import (
    identity as _identity,
)
from xime.core.security.context import (
    permissions as _permissions,
)

# Sentinel to distinguish "caller did not pass this argument" from "caller
# explicitly passed None" (which clears the field).
_UNSET: Any = object()


def authenticate(
    *,
    identity: Any = _UNSET,
    credentials: Any = _UNSET,
    credential_type: Any = _UNSET,
    permissions: Any = _UNSET,
) -> None:
    """
    Set security fields for the current async task in one call.

    Called by authentication middleware after verifying the request.
    Only fields explicitly provided are written - omitted fields stay as-is.
    Passing None explicitly clears that field (sets it to None).

    Usage:
        authenticate(
            identity="user_123",
            credential_type=CredentialType.TOKEN,
            permissions={Permission.READ, Permission.WRITE},
        )
    """
    if identity is not _UNSET:
        _identity.set(identity)
    if credentials is not _UNSET:
        _credentials.set(credentials)
    if credential_type is not _UNSET:
        _credential_type.set(credential_type)
    if permissions is not _UNSET:
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
