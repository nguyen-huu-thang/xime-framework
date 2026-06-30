from __future__ import annotations


class MailError(Exception):
    """Base class for every error raised by a MailService backend.

    Backends raise subclasses of this; callers can catch MailError to handle any
    mail failure uniformly, or catch a specific subclass.
    Lớp gốc cho mọi lỗi của backend MailService. Caller bắt MailError để xử lý
    chung, hoặc bắt subclass cụ thể.
    """


class MailSendError(MailError):
    """Raised when sending an email fails (SMTP refused, timeout, lost connection).

    The original transport error is preserved as the exception cause (`from exc`)
    so the application can inspect it for logging/debugging. Map this to a clean
    AppException at the application boundary.
    Ném khi gửi email thất bại (SMTP từ chối, timeout, mất kết nối). Lỗi gốc giữ
    ở `__cause__` để app log/debug; app map sang AppException của mình.
    """
