"""Phía CON của một cụm: bus, nhịp watchdog, và kênh điều khiển với cha.

Tách khỏi `Application` vì đây là một mối quan tâm trọn vẹn - *"tôi là một tiến
trình trong một cụm"* - và `Application` vốn đã gánh cấu hình, DI và vòng đời
adapter. Gộp thêm vào đó là một file không ai đọc hết được.

```text
Application.start()
  ├─ open()        attach bus + bảng nhịp        (TRƯỚC DI: chúng là hạ tầng)
  ├─ ... dựng DI, post_construct ...
  ├─ listen()      gắn handler, chạy vòng đọc, bắt đầu vỗ
  ├─ ... run_once() nếu là primary ...
  └─ report_*()    báo cha từng cột mốc
```

### ⭐ Bus dựng TRƯỚC DI

Nó là hạ tầng của framework, không phải một component của ứng dụng, nên nó không
đi qua `post_construct` nào cả. Nhờ vậy kênh điều khiển có mặt kể cả khi DI của
ứng dụng hỏng - và đó đúng là lúc cha cần nghe nhất.

### Vì sao một tiến trình đơn vẫn CÓ bus nhưng không CHẠY vòng đọc

`ProcessLink` luôn được dựng để nó luôn inject được - một app khai `ProcessLink`
trong constructor không nên hỏng chỉ vì hôm nay nó chạy một tiến trình. Nhưng
**vòng đọc chỉ chạy khi cụm có từ hai ô trở lên**: một tiến trình không có ai để
nghe, và một vòng đọc ở đó là một thread đỗ vĩnh viễn để chờ thứ không bao giờ
đến.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from xime.core.link import (
    INTERNAL_CHANNEL,
    BoundHandler,
    ChannelSpec,
    ProcessLink,
    link_registry,
)
from xime.core.link._decorators import ANNOUNCE

from . import _control
from ._orphan import OrphanGuard
from ._watchdog import Heartbeats, Watchdog

if TYPE_CHECKING:
    from ._shared import SharedHandle

_log = logging.getLogger("xime.bootstrap")

#: Cha gọi con làm primary; con trả lời bằng `PROMOTED` hoặc `PROMOTE_FAILED`.
PromoteHandler = Callable[[bool], Awaitable[None]]


class ClusterMember:
    """Một tiến trình nhìn từ phía cụm: nó nghe gì, nó báo gì, nó vỗ ra sao."""

    def __init__(self, handle: SharedHandle | None, *, share_load: bool) -> None:
        self._handle = handle
        self._share_load = share_load
        self._link: ProcessLink | None = None
        self._beats: Heartbeats | None = None
        self._watchdog: Watchdog | None = None
        self._orphan: OrphanGuard | None = None
        self._index = handle.index if handle is not None else 0
        self._slots = handle.slots if handle is not None else 1
        self._on_promote: PromoteHandler | None = None

    # ------------------------------------------------------------------
    # Thuộc tính
    # ------------------------------------------------------------------

    @property
    def link(self) -> ProcessLink | None:
        return self._link

    @property
    def index(self) -> int:
        return self._index

    @property
    def clustered(self) -> bool:
        """Có ai khác trong cụm không. Một tiến trình đơn thì không."""
        return self._slots > 1

    # ------------------------------------------------------------------
    # Mở và đóng
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Gắn vào bus và bảng nhịp. Gọi **trước** khi dựng DI."""
        channels = self._channels()
        handle = self._handle
        if handle is not None and handle.link_id is not None:
            self._link = ProcessLink.attach(
                handle.link_id,
                channels,
                self._slots,
                self._index,
                handle.link_bells,
            )
        else:
            if self._share_load and link_registry.app_channels():
                _log.warning(
                    "link: this process was started without a parent, so its "
                    "channels are private - nothing reaches any other process."
                )
            self._link = ProcessLink.create(channels, self._slots)
        if handle is not None and handle.beat_run_id is not None:
            self._beats = Heartbeats.attach(handle.beat_run_id, self._slots)

        if link_registry.app_channels() and not self.clustered:
            # Không tự chạy bus trong tiến trình để làm ra vẻ ổn, nhưng cũng
            # không im lặng: `ask()` sẽ luôn trả `NoOwner`, và đó trông y hệt
            # một lỗi cấu hình.
            _log.warning(
                "link: %d channel(s) are configured but this application runs a "
                "single process, so announce/send reach nobody and ask() always "
                "returns NoOwner.",
                len(link_registry.app_channels()),
            )

    def close(self) -> None:
        if self._beats is not None:
            self._beats.close()
            self._beats = None
        if self._link is not None:
            self._link.close()
            self._link = None

    def _channels(self) -> dict[str, ChannelSpec]:
        """Bố cục kênh phải giống hệt ở mọi tiến trình.

        Cha trao xuống bản của nó thay vì để con tự đọc registry: hai bên đọc
        **một** nguồn thì không có cửa cho lệch, còn *"tự đúng nhờ cùng import
        một file"* là thứ hỏng im lặng khi quy ước bị phá. Con vẫn kiểm lại một
        lần nữa lúc attach (header mang ba con số).
        """
        handle = self._handle
        if handle is not None and handle.channels:
            return dict(handle.channels)
        return link_registry.channels()

    # ------------------------------------------------------------------
    # Chạy
    # ------------------------------------------------------------------

    async def listen(
        self, handlers: dict[str, BoundHandler], on_promote: PromoteHandler
    ) -> None:
        """Gắn handler của ứng dụng, cắm handler nội bộ, rồi chạy.

        Gọi **sau** khi DI dựng xong: handler của ứng dụng là instance lấy từ
        container.
        """
        # TRƯỚC lối ra sớm bên dưới: con mồ côi giữ cổng là chuyện của quan hệ
        # cha-con, không phải của việc ứng dụng có khai kênh bus nào không. Đặt
        # sau `return` là mất phép canh ở đúng những ứng dụng đơn giản nhất.
        # `start()` tự im khi không có cha (chạy tay, chạy trong test).
        self._orphan = OrphanGuard()
        self._orphan.start()
        if self._link is None:
            return
        self._on_promote = on_promote
        merged = dict(handlers)
        merged[INTERNAL_CHANNEL] = BoundHandler(
            channel=INTERNAL_CHANNEL,
            kind=ANNOUNCE,
            call=self._on_control,
            owner="xime.bootstrap",
        )
        self._link.bind(merged)
        if self.clustered:
            await self._link.start()
        if self._beats is not None:
            self._watchdog = Watchdog(self._beats, self._index)
            await self._watchdog.start()

    async def quiesce(self) -> None:
        """Dừng vòng đọc và nhịp vỗ. Gọi trước khi dọn DI."""
        # Thôi canh TRƯỚC khi dừng những thứ còn lại: từ đây trở đi cha biến
        # mất là chuyện bình thường của một lần tắt, không phải mồ côi.
        if self._orphan is not None:
            self._orphan.stop()
            self._orphan = None
        if self._watchdog is not None:
            await self._watchdog.stop()
            self._watchdog = None
        if self._link is not None:
            await self._link.stop()

    async def _on_control(self, key: str, payload: bytes) -> None:
        """Handler của kênh nội bộ. Lọc bằng chỉ số, **không bằng tên**."""
        if key != _control.PROMOTE:
            return
        target, flag, _ = _control.unpack(payload)
        if target != self._index:
            return
        if self._on_promote is None:
            return
        await self._on_promote(bool(flag))

    # ------------------------------------------------------------------
    # Báo cho cha
    # ------------------------------------------------------------------

    def report_ready(self) -> None:
        self._tell(_control.READY)

    def report_run_once_done(self) -> None:
        self._tell(_control.RUN_ONCE_DONE)

    def report_promoted(self) -> None:
        self._tell(_control.PROMOTED)

    def report_promote_failed(self, reason: str) -> None:
        self._tell(_control.PROMOTE_FAILED, reason)

    def report_adapter_isolated(self, label: str) -> None:
        self._tell(_control.ADAPTER_ISOLATED, label)

    def _tell(self, key: str, detail: str = "") -> None:
        """Nói với cha, và **không bao giờ ném**.

        ⚠ Đây là đường báo tin, không phải đường nghiệp vụ. Một lỗi ở đây không
        được phép làm hỏng thứ nó đang đi báo - nhất là ở `report_promote_failed`,
        nơi cả lời gọi tồn tại vì có chuyện vừa hỏng.
        """
        if self._link is None or not self.clustered:
            return
        try:
            self._link.announce_sync(
                INTERNAL_CHANNEL,
                _control.pack(self._index, detail.encode("utf-8")[:400]),
                key=key,
            )
        except Exception:  # noqa: BLE001 - đường báo tin không được kéo ai theo
            _log.warning("link: could not report %r to the supervisor", key, exc_info=True)
