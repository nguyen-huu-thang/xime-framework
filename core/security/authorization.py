from __future__ import annotations

from enum import Enum
from typing import Protocol


class AuthorizationManager(Protocol):
    """
    Contract for checking whether the current identity has a required permission.

    Implement this Protocol to plug custom authorization logic (RBAC, ABAC,
    permission list check, external policy engine, etc.) into the framework.

    The implementation is registered via DI binding:
        dependency.bind({AuthorizationManager: RbacAuthorizationManager})

    The implementation reads the current identity and permissions from the
    security context (core.security.identity, core.security.permissions) and
    decides whether to allow or deny the request.

    Raises:
        AuthorizationException: if the current identity lacks the permission.
    """

    async def authorize(self, permission: Enum) -> None:
        """
        Assert that the current identity holds the given permission.

        Args:
            permission: The permission required for the operation.
                        Pass a value from your application's Permission enum.

        Raises:
            AuthorizationException: if the identity is not authorized.
        """
        ...
