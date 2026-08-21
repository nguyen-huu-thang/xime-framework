from xime.starters.mail._exceptions import MailError as MailError
from xime.starters.mail._exceptions import MailSendError as MailSendError
from xime.starters.mail._message import EmailMessage as EmailMessage
from xime.starters.mail._service import MailService as MailService
from xime.starters.mail._smtp import SmtpMailService as SmtpMailService

# The `X as X` form is PEP 484's explicit re-export marker - see the note in
# xime/starters/jwt/__init__.py for why __all__ cannot serve that role here.
#
# __all__ controls which classes the DI scanner registers when a service calls
# dependency.scan("xime.starters.mail"):
#
#   SmtpMailService : implements MailService, RuntimeConfig injected
#                     automatically. Bind it as the MailService backend:
#                         dependency.bind({ MailService: SmtpMailService })
#
#   MailService : a Protocol - the scanner skips all Protocols; it has no
#                 implementation to instantiate, so it is excluded here.
#
# The names below are still importable directly for bindings and type hints:
#   from xime.starters.mail import (
#       MailService, SmtpMailService, EmailMessage, MailError, MailSendError,
#   )
__all__ = ["SmtpMailService"]
