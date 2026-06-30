"""
Test the mail starter (0.6.2) - MailService Protocol + SmtpMailService backend.

  EmailMessage:
    - empty `to` or missing both html/text -> MailError (fail-fast at construction)
  Construction:
    - missing mail.smtp.host -> ValueError (fail-fast)
    - defaults: port 587, timeout 10, use_tls true
  Protocol:
    - SmtpMailService satisfies the MailService Protocol
  send() (aiosmtplib.send monkeypatched - no real SMTP server):
    - builds correct MIME headers (From default/override, To, Cc, Reply-To, Subject)
    - text-only / html-only / both (multipart/alternative)
    - chooses STARTTLS (587) vs implicit TLS (465) by port; passes credentials
    - transport failure -> MailSendError wrapping the original cause
"""
import aiosmtplib
import pytest

from xime.core.config.runtime import RuntimeConfig
from xime.starters.mail import (
    EmailMessage,
    MailError,
    MailSendError,
    MailService,
    SmtpMailService,
)


def _service(**smtp) -> SmtpMailService:
    smtp.setdefault("host", "smtp.example.com")
    cfg = {"mail": {"from": "Demo <demo@example.com>", "smtp": smtp}}
    return SmtpMailService(RuntimeConfig.from_dict(cfg))


class _Capture:
    """Replacement for aiosmtplib.send that records its arguments."""

    def __init__(self) -> None:
        self.message = None
        self.kwargs = None

    async def __call__(self, message, **kwargs):
        self.message = message
        self.kwargs = kwargs


class TestEmailMessage:
    def test_empty_to_raises(self):
        with pytest.raises(MailError, match="recipient"):
            EmailMessage(to=[], subject="x", text="body")

    def test_missing_body_raises(self):
        with pytest.raises(MailError, match="html.*text"):
            EmailMessage(to=["a@b.com"], subject="x")

    def test_minimal_ok(self):
        msg = EmailMessage(to=["a@b.com"], subject="x", text="hi")
        assert msg.to == ("a@b.com",)

    def test_recipients_snapshot_to_tuple(self):
        """to/cc are snapshotted to tuples so the frozen message is truly immutable."""
        recipients = ["a@b.com"]
        ccs = ["c@d.com"]
        msg = EmailMessage(to=recipients, subject="x", text="hi", cc=ccs)
        assert msg.to == ("a@b.com",)
        assert msg.cc == ("c@d.com",)
        # Mutating the original lists must not affect the message.
        recipients.append("evil@x.com")
        ccs.append("evil2@x.com")
        assert msg.to == ("a@b.com",)
        assert msg.cc == ("c@d.com",)


class TestConstruction:
    def test_missing_host_raises(self):
        with pytest.raises(ValueError, match="mail.smtp.host"):
            SmtpMailService(RuntimeConfig.from_dict({}))

    def test_defaults(self):
        svc = _service()
        assert svc._port == 587
        assert svc._timeout == 10
        assert svc._use_tls is True

    def test_satisfies_protocol(self):
        assert isinstance(_service(), MailService)


class TestSendKwargs:
    def test_starttls_for_587(self):
        svc = _service(port=587, username="u", password="p")
        kw = svc._send_kwargs()
        assert kw["start_tls"] is True
        assert "use_tls" not in kw
        assert kw["username"] == "u" and kw["password"] == "p"
        assert kw["hostname"] == "smtp.example.com" and kw["timeout"] == 10

    def test_implicit_tls_for_465(self):
        kw = _service(port=465)._send_kwargs()
        assert kw["use_tls"] is True
        assert "start_tls" not in kw

    def test_no_tls_when_disabled(self):
        kw = _service(use_tls=False)._send_kwargs()
        assert "start_tls" not in kw and "use_tls" not in kw

    def test_no_credentials_when_absent(self):
        kw = _service()._send_kwargs()
        assert "username" not in kw and "password" not in kw


class TestSend:
    @pytest.mark.asyncio
    async def test_builds_headers_and_text(self, monkeypatch):
        cap = _Capture()
        monkeypatch.setattr(aiosmtplib, "send", cap)
        svc = _service()
        await svc.send(
            EmailMessage(
                to=["a@b.com", "c@d.com"],
                cc=["e@f.com"],
                reply_to="reply@x.com",
                subject="Hello",
                text="plain body",
            )
        )
        mime = cap.message
        assert mime["From"] == "Demo <demo@example.com>"
        assert mime["To"] == "a@b.com, c@d.com"
        assert mime["Cc"] == "e@f.com"
        assert mime["Reply-To"] == "reply@x.com"
        assert mime["Subject"] == "Hello"
        assert mime.get_content_type() == "text/plain"
        assert "plain body" in mime.get_content()

    @pytest.mark.asyncio
    async def test_sender_override(self, monkeypatch):
        cap = _Capture()
        monkeypatch.setattr(aiosmtplib, "send", cap)
        await _service().send(
            EmailMessage(to=["a@b.com"], subject="x", text="hi", sender="other@x.com")
        )
        assert cap.message["From"] == "other@x.com"

    @pytest.mark.asyncio
    async def test_html_only(self, monkeypatch):
        cap = _Capture()
        monkeypatch.setattr(aiosmtplib, "send", cap)
        await _service().send(
            EmailMessage(to=["a@b.com"], subject="x", html="<b>hi</b>")
        )
        assert cap.message.get_content_type() == "text/html"

    @pytest.mark.asyncio
    async def test_multipart_alternative(self, monkeypatch):
        cap = _Capture()
        monkeypatch.setattr(aiosmtplib, "send", cap)
        await _service().send(
            EmailMessage(to=["a@b.com"], subject="x", text="plain", html="<b>hi</b>")
        )
        assert cap.message.get_content_type() == "multipart/alternative"
        subtypes = {part.get_content_subtype() for part in cap.message.iter_parts()}
        assert subtypes == {"plain", "html"}

    @pytest.mark.asyncio
    async def test_missing_sender_raises(self, monkeypatch):
        cap = _Capture()
        monkeypatch.setattr(aiosmtplib, "send", cap)
        # No mail.from and no message.sender.
        svc = SmtpMailService(RuntimeConfig.from_dict({"mail": {"smtp": {"host": "h"}}}))
        with pytest.raises(MailSendError, match="sender"):
            await svc.send(EmailMessage(to=["a@b.com"], subject="x", text="hi"))

    @pytest.mark.asyncio
    async def test_transport_failure_wrapped(self, monkeypatch):
        async def _boom(message, **kwargs):
            raise aiosmtplib.SMTPException("refused")

        monkeypatch.setattr(aiosmtplib, "send", _boom)
        with pytest.raises(MailSendError) as exc_info:
            await _service().send(EmailMessage(to=["a@b.com"], subject="x", text="hi"))
        assert isinstance(exc_info.value.__cause__, aiosmtplib.SMTPException)

    @pytest.mark.asyncio
    async def test_timeout_wrapped(self, monkeypatch):
        async def _slow(message, **kwargs):
            raise TimeoutError("timed out")

        monkeypatch.setattr(aiosmtplib, "send", _slow)
        with pytest.raises(MailSendError):
            await _service().send(EmailMessage(to=["a@b.com"], subject="x", text="hi"))
