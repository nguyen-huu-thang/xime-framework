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

import asyncio
import logging
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
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
from ._stall_report import StallReporter
from ._watchdog import Heartbeats, Watchdog

if TYPE_CHECKING:
    from ._shared import SharedHandle

_log = logging.getLogger("xime.bootstrap")

#: Cha gọi con làm primary; con trả lời bằng `PROMOTED` hoặc `PROMOTE_FAILED`.
PromoteHandler = Callable[[bool], Awaitable[None]]
AdapterCommandHandler = Callable[[bytes], Awaitable[bytes]]


async def _unhandled_adapter_command(_payload: bytes) -> bytes:
    return b"unhandled"


@dataclass
class _CommandWaiter:
    expected: frozenset[int]
    acknowledgements: dict[int, bytes] = field(default_factory=dict)
    changed: asyncio.Event = field(default_factory=asyncio.Event)


class ClusterMember:
    """Một tiến trình nhìn từ phía cụm: nó nghe gì, nó báo gì, nó vỗ ra sao."""

    def __init__(self, handle: SharedHandle | None, *, share_load: bool) -> None:
        self._handle = handle
        self._share_load = share_load
        self._link: ProcessLink | None = None
        self._beats: Heartbeats | None = None
        self._stall: StallReporter | None = None
        self._watchdog: Watchdog | None = None
        self._orphan: OrphanGuard | None = None
        self._index = handle.index if handle is not None else 0
        self._slots = handle.slots if handle is not None else 1
        self._on_promote: PromoteHandler | None = None
        self._on_adapter_command: AdapterCommandHandler | None = None
        self._command_waiters: dict[bytes, _CommandWaiter] = {}
        self._adapter_tasks: set[asyncio.Task[None]] = set()

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
        self,
        handlers: dict[str, BoundHandler],
        on_promote: PromoteHandler,
        on_adapter_command: AdapterCommandHandler | None = None,
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
        self._on_adapter_command = on_adapter_command or _unhandled_adapter_command
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
            # ⭐ Bộ khoanh vùng đọc lại CHÍNH ô nhịp mà `Watchdog` vừa vỗ, từ
            # một thread riêng - vì khi loop kẹt thì mọi task trên loop cũng
            # kẹt, chỉ người đứng ngoài mới kể lại được chỗ kẹt. Chi phí đo
            # được là -0,22% (nhiễu), nên nó bật mặc định. Xem `_stall_report`.
            self._stall = StallReporter(self._beats, self._index)
            self._stall.start()

    async def quiesce(self) -> None:
        """Dừng vòng đọc và nhịp vỗ. Gọi trước khi dọn DI."""
        # Thôi canh TRƯỚC khi dừng những thứ còn lại: từ đây trở đi cha biến
        # mất là chuyện bình thường của một lần tắt, không phải mồ côi.
        if self._orphan is not None:
            self._orphan.stop()
            self._orphan = None
        if self._stall is not None:
            self._stall.stop()
            self._stall = None
        if self._watchdog is not None:
            await self._watchdog.stop()
            self._watchdog = None
        if self._link is not None:
            await self._link.stop()
        for task in tuple(self._adapter_tasks):
            task.cancel()
        for task in tuple(self._adapter_tasks):
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._adapter_tasks.clear()
        for waiter in self._command_waiters.values():
            waiter.changed.set()

    async def _on_control(self, key: str, payload: bytes) -> None:
        """Handler của kênh nội bộ. Lọc bằng chỉ số, **không bằng tên**."""
        if key == _control.ADAPTER_COMMAND_BROADCAST:
            command = _control.unpack_adapter_command(payload)
            if command is None:
                return
            request_id, targets, _opaque = command
            if self._index not in targets or self._on_adapter_command is None:
                return
            task = asyncio.create_task(
                self._execute_adapter_command(request_id, payload),
                name="xime-adapter-command",
            )
            self._adapter_tasks.add(task)
            task.add_done_callback(self._adapter_tasks.discard)
            return
        if key == _control.ADAPTER_COMMAND_ACK:
            ack = _control.unpack_adapter_ack(payload)
            if ack is not None:
                self._record_adapter_ack(*ack)
            return
        if key != _control.PROMOTE:
            return
        target, flag, _ = _control.unpack(payload)
        if target != self._index:
            return
        if self._on_promote is None:
            return
        await self._on_promote(bool(flag))

    async def request_adapter_command(
        self,
        command: bytes,
        *,
        targets: tuple[int, ...],
        timeout: float = 20.0,
    ) -> tuple[dict[int, bytes], tuple[int, ...]]:
        """Ask the supervisor to relay a command and await each target ACK."""
        if self._link is None or not self.clustered:
            raise RuntimeError("adapter commands require a clustered ProcessLink")
        expected = frozenset(targets)
        if not expected:
            raise ValueError("adapter command needs at least one target worker")

        request_id = secrets.token_bytes(16)
        waiter = _CommandWaiter(expected=expected)
        self._command_waiters[request_id] = waiter
        try:
            payload = _control.pack_adapter_command(
                request_id, tuple(sorted(expected)), command
            )
            self._link.announce_sync(
                INTERNAL_CHANNEL,
                payload,
                key=_control.ADAPTER_COMMAND_REQUEST,
            )

            async def wait_for_all() -> None:
                while not expected.issubset(waiter.acknowledgements):
                    waiter.changed.clear()
                    if expected.issubset(waiter.acknowledgements):
                        return
                    await waiter.changed.wait()

            try:
                await asyncio.wait_for(wait_for_all(), timeout=timeout)
            except TimeoutError:
                pass
            acknowledged = dict(waiter.acknowledgements)
            missing = tuple(sorted(expected.difference(acknowledged)))
            return acknowledged, missing
        finally:
            self._command_waiters.pop(request_id, None)

    async def _execute_adapter_command(self, request_id: bytes, envelope: bytes) -> None:
        parsed = _control.unpack_adapter_command(envelope)
        if parsed is None or self._on_adapter_command is None:
            return
        _request_id, _targets, command = parsed
        try:
            result = await self._on_adapter_command(command)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - return a per-worker failure
            _log.warning("link: internal adapter command failed", exc_info=True)
            result = f"failed:{type(exc).__name__}".encode("ascii", errors="replace")
        ack = _control.pack_adapter_ack(request_id, self._index, result)
        self._record_adapter_ack(request_id, self._index, result)
        if self._link is not None:
            try:
                self._link.announce_sync(
                    INTERNAL_CHANNEL,
                    ack,
                    key=_control.ADAPTER_COMMAND_ACK,
                )
            except Exception:  # noqa: BLE001 - ACK loss becomes a caller timeout
                _log.warning("link: could not acknowledge internal adapter command", exc_info=True)

    def _record_adapter_ack(self, request_id: bytes, index: int, result: bytes) -> None:
        waiter = self._command_waiters.get(request_id)
        if waiter is None or index not in waiter.expected:
            return
        waiter.acknowledgements.setdefault(index, result)
        waiter.changed.set()

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
