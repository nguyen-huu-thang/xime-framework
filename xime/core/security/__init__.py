from xime.core.security.authentication import AuthenticationManager
from xime.core.security.authorization import AuthorizationManager
from xime.core.security.context import credentials, credential_type, identity, permissions
from xime.core.security.enums import CredentialType
from xime.core.security.peer import (
    PEER_APP_ID,
    PEER_CN,
    current_app_id,
    current_caller,
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
    "current_app_id",
    "PEER_CN",
    "PEER_APP_ID",
    # Enums
    "CredentialType",
    # Protocols — implement to plug custom logic
    "AuthenticationManager",
    "AuthorizationManager",
]
