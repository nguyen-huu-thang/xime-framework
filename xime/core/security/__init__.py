from xime.core.security.authentication import AuthenticationManager
from xime.core.security.authorization import AuthorizationManager
from xime.core.security.context import credential_type, credentials, identity, permissions
from xime.core.security.enums import CredentialType
from xime.core.security.peer import (
    PEER_CN,
    PEER_SANS,
    current_caller,
    current_peer_sans,
)
from xime.core.security.session import authenticate, clear_security

__all__ = [
    # Context fields
    "identity",
    "credentials",
    "credential_type",
    "permissions",
    # Helpers
    "authenticate",
    "clear_security",
    "current_caller",
    "current_peer_sans",
    "PEER_CN",
    "PEER_SANS",
    # Enums
    "CredentialType",
    # Protocols - implement to plug custom logic
    "AuthenticationManager",
    "AuthorizationManager",
]
