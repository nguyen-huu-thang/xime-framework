"""Cha báo cho `systemd`. Vài chục dòng, không thư viện.

> **Cha canh con vì cha sinh ra con. Cha thì do thứ sinh ra cha canh.**

Nguyên tắc mượn nguyên từ phần cứng: **watchdog không nằm trên con CPU nó canh**.
Đó là điều làm nó đáng tin - nó không cùng số phận với thứ nó canh. Nên framework
**không tự viết** tiến trình canh cha (và ai canh nó?); nó nói với tầng dưới.

```ini
# /etc/systemd/system/app.service
[Service]
Type=notify
WatchdogSec=30
ExecStart=/usr/bin/python -m app.main
```

Không có `NOTIFY_SOCKET` (chạy tay, máy dev, Windows) thì **bỏ qua im lặng** - đó
là ca thường lệ lúc phát triển, và một cảnh báo ở đó là cảnh báo sẽ bị học cách
lờ đi.

⭐ Chọn systemd nhất quán với nguyên tắc đã chốt *"đừng viết bộ cân bằng tải"*:
**đừng viết lại thứ tầng dưới đã làm tốt hơn**.

⚠ Và cha treo **không nguy như nghe**: cha không `accept()`, nên con vẫn phục vụ
bình thường. Thứ mất là khả năng **tự phục hồi** - con chết không ai dựng lại.
Tức đây là **hỏng chậm**: không ai thấy gì cho tới lần đầu có con chết. Nguy hiểm
nằm ở chỗ **im lặng**, không ở chỗ tức thì, và đó chính là lý do giao cho systemd
là đủ.
"""

from __future__ import annotations

import logging
import os
import socket

_log = logging.getLogger("xime.bootstrap")

_ENV = "NOTIFY_SOCKET"


class SystemdNotifier:
    """Gửi `READY=1` và `WATCHDOG=1`. Không có socket thì mọi lời gọi là no-op."""

    __slots__ = ("_socket", "_address")

    def __init__(self) -> None:
        self._socket: socket.socket | None = None
        self._address: str | bytes | None = None
        raw = os.environ.get(_ENV)
        if not raw:
            return
        if not hasattr(socket, "AF_UNIX"):
            return  # Windows: systemd không tồn tại, và biến này thì có thể sót lại
        # "@abstract" của Linux: ký tự đầu là NUL trong không gian tên trừu tượng.
        address: str | bytes = ("\0" + raw[1:]) if raw[0] == "@" else raw
        try:
            self._socket = socket.socket(
                socket.AF_UNIX, socket.SOCK_DGRAM | socket.SOCK_CLOEXEC
            )
        except OSError:
            _log.debug("sd_notify: could not open the notify socket", exc_info=True)
            return
        self._address = address

    @property
    def enabled(self) -> bool:
        return self._socket is not None

    def ready(self) -> None:
        self._send(b"READY=1")

    def watchdog(self) -> None:
        self._send(b"WATCHDOG=1")

    def stopping(self) -> None:
        self._send(b"STOPPING=1")

    def close(self) -> None:
        sock, self._socket = self._socket, None
        if sock is not None:
            sock.close()

    def _send(self, message: bytes) -> None:
        if self._socket is None or self._address is None:
            return
        try:
            self._socket.sendto(message, self._address)
        except OSError:
            # ⚠ Nuốt chứ không ném: mất một nhịp báo cho systemd không đáng để
            # giết một tiến trình cha đang trông cả cụm. systemd tự xử lý bằng
            # cách restart khi hết `WatchdogSec` - đúng việc của nó.
            _log.debug("sd_notify: %r was not delivered", message, exc_info=True)
