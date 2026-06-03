from __future__ import annotations

from typing import Any, Protocol


class AuthenticationManager(Protocol):
    """
    Contract for verifying credentials and returning an authenticated identity.

    Implement this Protocol to plug custom authentication logic (JWT, OAuth2,
    API key, username+password, etc.) into the framework.

    The implementation is registered via DI binding:
        dependency.bind({AuthenticationManager: JwtAuthenticationManager})

    Middleware or route handlers call authenticate(), then populate the security
    context via xime.core.security.authenticate().

    Raises:
        AuthenticationException: if credentials are missing, invalid, or expired.
    """

    async def authenticate(self, credentials: Any) -> Any:
        """
        Verify credentials and return the authenticated identity.

        Args:
            credentials: Raw credential material — token string, dict with
                         username/password, API key, certificate, etc.

        Returns:
            The authenticated identity in whatever shape the application uses:
            user_id, user object, claims dict, etc.

        Raises:
            AuthenticationException: if authentication fails.
        """
        ...
