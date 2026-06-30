from __future__ import annotations

from typing import Protocol, runtime_checkable

from xime.starters.mail._message import EmailMessage


@runtime_checkable
class MailService(Protocol):
    """
    Backend-neutral contract for sending email.

    Define this once; bind a concrete backend in config/dependency.py, e.g.

        dependency.bind({ MailService: SmtpMailService })

    and inject MailService wherever email is sent:

        class OtpService:
            def __init__(self, mail: MailService) -> None:
                self._mail = mail

    The framework only provides the mechanism (deliver one message, await the
    result). It imposes no policy on templating, retry, queueing or attachments -
    that is the application's job. This keeps the contract small and every backend
    (SMTP today, SendGrid/SES later) interchangeable with a one-line bind change.
    Framework chỉ cấp cơ chế (gửi một message, await kết quả). Không áp đặt
    template/retry/hàng đợi/đính kèm - đó là việc của app.
    """

    async def send(self, message: EmailMessage) -> None:
        """Send `message`, awaiting until delivery to the SMTP server completes.

        Logically synchronous: returns on success, raises MailSendError on
        failure (SMTP refused, timeout, lost connection). Has an internal
        timeout so a hung server cannot stall the caller indefinitely. This is
        the call to use for security email (OTP, password reset) where the user
        is waiting and must be told whether it was sent.

        Background sending is the application's job, NOT the starter's: wrap
        send() in asyncio.create_task(...) / FastAPI BackgroundTasks / the
        scheduler when the user should not wait (e.g. order-confirmation email).
        Await tới khi gửi xong: thành công -> return; thất bại -> raise
        MailSendError; có timeout nội bộ. Gửi nền do app tự bọc create_task(...).
        """
        ...
