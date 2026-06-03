from enum import Enum


class CredentialType(Enum):
    """
    Framework-provided credential types for convenience.
    Developers can pass their own Enum to SecurityContext.credential_type
    instead of using this one.
    """

    PASSWORD    = "password"
    TOKEN       = "token"
    API_KEY     = "api_key"
    OAUTH2      = "oauth2"
    CERTIFICATE = "certificate"
