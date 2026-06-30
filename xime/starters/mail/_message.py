from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from xime.starters.mail._exceptions import MailError


@dataclass(frozen=True, slots=True)
class EmailMessage:
    """A single email to send through a MailService.

    Immutable value object (matches StorageStat's shape). At least one of `html`
    or `text` must be provided, and `to` must be non-empty - both checked in
    __post_init__ so a malformed message fails fast at construction, not deep in
    the SMTP backend.
    Value object bất biến. Phải có ít nhất một trong html/text và `to` không rỗng
    - kiểm tra trong __post_init__ để lỗi nổ ngay lúc tạo, không lọt vào backend.

    `sender` overrides the default `mail.from` from config for this one message
    (named `sender`, not `from`, because `from` is a Python keyword).
    `sender` ghi đè `mail.from` mặc định trong config cho riêng email này (đặt tên
    `sender` vì `from` là từ khóa Python).
    """

    to: Sequence[str]
    subject: str
    html: str | None = None
    text: str | None = None
    cc: Sequence[str] | None = None
    reply_to: str | None = None
    sender: str | None = None

    def __post_init__(self) -> None:
        # Snapshot the recipient sequences into tuples so a frozen EmailMessage is
        # truly immutable: frozen=True blocks reassignment but not mutation of a
        # shared list the caller still holds (msg.to.append(...)).
        # Sao chép danh sách người nhận thành tuple để EmailMessage frozen thật sự
        # bất biến: frozen chặn gán lại nhưng không chặn mutate list mà caller còn
        # giữ tham chiếu.
        object.__setattr__(self, "to", tuple(self.to))
        if self.cc is not None:
            object.__setattr__(self, "cc", tuple(self.cc))
        if not self.to:
            raise MailError("EmailMessage.to must contain at least one recipient")
        if self.html is None and self.text is None:
            raise MailError("EmailMessage must have at least one of `html` or `text`")
