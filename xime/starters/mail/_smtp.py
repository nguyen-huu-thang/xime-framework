from __future__ import annotations

from email.message import EmailMessage as MimeMessage

from xime.core.config.runtime import RuntimeConfig
from xime.starters.mail._exceptions import MailSendError
from xime.starters.mail._message import EmailMessage

# Implicit-TLS SMTP port. On 465 the connection is wrapped in TLS from the start
# (use_tls); every other port (587, 25) negotiates STARTTLS after connecting.
# Cổng SMTP TLS ngầm. 465 bọc TLS ngay từ đầu; cổng khác dùng STARTTLS.
_IMPLICIT_TLS_PORT = 465

# Defaults when the corresponding key is absent from application.yml.
# Mặc định khi thiếu khóa tương ứng trong application.yml.
_DEFAULT_PORT = 587
_DEFAULT_TIMEOUT = 10


class SmtpMailService:
    """MailService backend that sends email over SMTP via aiosmtplib.

    Reads its settings from RuntimeConfig (application.yml):

        mail:
          from: "Shop Demo <you@gmail.com>"   # default From header
          smtp:
            host: smtp.gmail.com              # required
            port: 587                         # default 587
            username: you@gmail.com           # optional
            password: ""                      # optional (app password - inject at runtime)
            use_tls: true                     # STARTTLS (587) or implicit TLS (465)
            timeout: 10                        # seconds, per send()

    Opens a fresh SMTP connection per send() and closes it afterwards. This is
    simpler and more robust than a long-lived pooled connection (idle SMTP
    sessions are routinely dropped by the server) - the right trade-off for the
    transactional/OTP volume this starter targets.
    Mỗi send() mở một kết nối SMTP mới rồi đóng - đơn giản và bền hơn pool (phiên
    SMTP idle thường bị server đóng), hợp với lượng email giao dịch/OTP.

    Does not inherit the MailService Protocol (structural typing) - the framework
    validates conformance at startup when the binding is resolved.
    Không kế thừa Protocol MailService - framework validate lúc startup.

    aiosmtplib is imported lazily so the module stays importable when the extra is
    absent - only services that scan this package need `pip install xime[mail]`.
    Import aiosmtplib lười để module vẫn import được khi chưa cài extra.

    Register and bind in config/dependency.py:
        dependency.scan("xime.starters.mail")
        dependency.bind({ MailService: SmtpMailService })
    RuntimeConfig is injected automatically.
    """

    def __init__(self, config: RuntimeConfig) -> None:
        host: str = config.get("mail.smtp.host") or ""
        if not host:
            raise ValueError(
                "mail.smtp.host is not configured. "
                "Add 'mail.smtp.host' to resources/application.yml."
            )
        self._host = host
        self._port: int = config.get("mail.smtp.port", _DEFAULT_PORT)
        self._username: str | None = config.get("mail.smtp.username")
        self._password: str | None = config.get("mail.smtp.password")
        # use_tls=true means "use TLS"; how depends on the port (see _send_kwargs).
        # use_tls=true nghĩa là "dùng TLS"; cách dùng tùy cổng (xem _send_kwargs).
        self._use_tls: bool = bool(config.get("mail.smtp.use_tls", True))
        self._timeout: int = config.get("mail.smtp.timeout", _DEFAULT_TIMEOUT)
        self._default_from: str | None = config.get("mail.from")

        # Lazy import: fail-fast with a clear message if the extra is missing.
        # Import lười: báo lỗi rõ nếu chưa cài extra.
        try:
            import aiosmtplib  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "The mail starter requires the 'aiosmtplib' package. "
                "Install it with: pip install xime[mail]"
            ) from exc

    async def send(self, message: EmailMessage) -> None:
        mime = self._build_mime(message)

        import aiosmtplib

        try:
            await aiosmtplib.send(mime, **self._send_kwargs())
        except (aiosmtplib.SMTPException, TimeoutError, OSError) as exc:
            # Wrap every transport-level failure in one typed error, keeping the
            # original as __cause__ for the application to log/inspect.
            # Bọc mọi lỗi tầng truyền tải thành một lỗi typed, giữ lỗi gốc ở
            # __cause__ để app log/kiểm tra.
            raise MailSendError(f"failed to send email: {exc}") from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_mime(self, message: EmailMessage) -> MimeMessage:
        """Render an EmailMessage into a stdlib MIME message.

        text-only / html-only -> a single body; both present -> a
        multipart/alternative where the html part is preferred by clients.
        Chỉ text/chỉ html -> một thân; có cả hai -> multipart/alternative, client
        ưu tiên phần html.
        """
        mime = MimeMessage()
        sender = message.sender or self._default_from
        if not sender:
            raise MailSendError(
                "no sender: set 'mail.from' in application.yml or EmailMessage.sender"
            )
        mime["From"] = sender
        mime["To"] = ", ".join(message.to)
        if message.cc:
            mime["Cc"] = ", ".join(message.cc)
        if message.reply_to:
            mime["Reply-To"] = message.reply_to
        mime["Subject"] = message.subject

        # __post_init__ guarantees at least one of text/html is present.
        # __post_init__ đảm bảo có ít nhất một trong text/html.
        if message.text is not None and message.html is not None:
            mime.set_content(message.text)
            mime.add_alternative(message.html, subtype="html")
        elif message.html is not None:
            mime.set_content(message.html, subtype="html")
        else:
            mime.set_content(message.text)
        return mime

    def _send_kwargs(self) -> dict:
        """Build aiosmtplib.send() keyword args, choosing the TLS mode by port."""
        kwargs: dict = {
            "hostname": self._host,
            "port": self._port,
            "timeout": self._timeout,
        }
        # `is not None` (not truthiness) so an explicitly configured empty string
        # is still passed to the SMTP server, and only a genuinely absent value
        # (null / missing key) skips authentication.
        # Dùng `is not None` (không phải falsy) để chuỗi rỗng cấu hình tường minh
        # vẫn được truyền; chỉ giá trị thật sự vắng (null / thiếu key) mới bỏ qua.
        if self._username is not None:
            kwargs["username"] = self._username
        if self._password is not None:
            kwargs["password"] = self._password
        if self._use_tls:
            if self._port == _IMPLICIT_TLS_PORT:
                kwargs["use_tls"] = True  # implicit TLS from connect (465)
            else:
                kwargs["start_tls"] = True  # STARTTLS upgrade (587, 25)
        return kwargs
