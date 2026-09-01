from __future__ import annotations

import asyncio
import logging
import os
import secrets
import time
from multiprocessing import synchronize
from multiprocessing.shared_memory import SharedMemory

from xime.core.shared import MP_CONTEXT, view_of

from ._config import INTERNAL_CHANNEL, ChannelSpec, validate_process_count
from ._decorators import ANNOUNCE, REQUEST, BoundHandler
from ._errors import LinkError
from ._layout import (
    KEY_BYTES,
    KIND_ANNOUNCE,
    KIND_FAILURE,
    KIND_REPLY,
    KIND_REQUEST,
    NO_TAKER,
    ROW_COMPLETE,
    ROW_KIND,
    ROW_SENDER,
    ROW_SEQ,
    ROW_TAKER,
    ROW_WRITTEN_AT,
    ChannelLayout,
)
from ._outcome import Done, Failed, NoAnswer, NoOwner, Outcome
from ._stats import ChannelStats, LinkMessage, LinkStats, RawRow, ReaderStats

_log = logging.getLogger("xime.link")

# Ngưỡng cảnh báo khi bảng của một kênh sắp đầy.
_FULL_WARN_RATIO = 0.8

# Handler chạy quá ngần này thì kêu - nó chặn kênh của nó, và một kênh tắc mà im
# lặng thì người vận hành thấy "mọi thứ bình thường, chỉ là không có gì xảy ra".
_SLOW_HANDLER_SECONDS = 5.0

# Khuôn hãm nhịp chép từ EventBus (F15): kêu ở lần đầu, rồi mỗi 1000 lần một
# dòng. Một dòng log xuất hiện đúng một lần đọc như sự cố lẻ, không như mất mát
# đang diễn ra.
_RATE_LIMIT_EVERY = 1000

# Trần độ dài của `Failed.detail`.
_DETAIL_LIMIT = 200


class ProcessLink:
    """Bus liên tiến trình trên bộ nhớ chung.

    ⚠⚠ **KHÁC HẲN `EventBus`** trong `core/event/`, và không dùng chung một dòng
    code nào. Gọi nhầm thì **không có triệu chứng**: tin không bao giờ ra khỏi
    tiến trình, không lỗi, không log. Tên cố ý không chung gốc từ - `link.ask()`
    với `event_bus.publish()` không thể gõ nhầm thành nhau.

    | | `EventBus` | `ProcessLink` |
    |---|---|---|
    | Phạm vi | trong MỘT tiến trình | GIỮA các tiến trình |
    | Chở gì | object Python | **bytes** |
    | Chở loại gì | **event** - đã xảy ra rồi | **lệnh và câu hỏi** - có đích |
    | Phản hồi | không | **có** (`ask`) |
    | Handler chạy | song song | **tuần tự theo kênh** |

    Cơ chế: mỗi kênh một vùng nhớ chung, chia N **vùng ghi riêng** nên không có
    tranh chấp ghi và thứ tự trong một người gửi được giữ nguyên. Semaphore chỉ
    là **chuông**; **bitmap "ai chưa đọc" mới là sự thật**.

    ⚠ Thiết kế cho `N = 1` luồng mỗi tiến trình. `N > 1` không đòi đổi cấu trúc
    chia sẻ, chỉ thêm một tầng phân phối bên trong tiến trình - và tầng đó
    **không được dùng `asyncio.Queue`** (primitive asyncio gắn chặt một event
    loop).
    """

    def __init__(
        self,
        *,
        link_id: str,
        index: int,
        process_count: int,
        specs: dict[str, ChannelSpec],
        blocks: dict[str, SharedMemory],
        bells: tuple[synchronize.Semaphore, ...],
        owner: bool,
    ) -> None:
        self._link_id = link_id
        self._index = index
        self._process_count = process_count
        self._specs = specs
        self._blocks = blocks
        self._bells = bells
        self._owner = owner

        self._layouts = {
            name: ChannelLayout(spec.rows, spec.payload_bytes, process_count)
            for name, spec in specs.items()
        }
        self._views = {name: view_of(block) for name, block in blocks.items()}
        # Con trỏ ghi trong vùng của CHÍNH mình. Nằm trong RAM riêng vì không ai
        # khác ghi vào vùng đó, nên nó không cần chia sẻ.
        self._cursors = dict.fromkeys(specs, 0)

        self._handlers: dict[str, BoundHandler] = {}
        self._pending: dict[bytes, asyncio.Future[Outcome]] = {}
        self._tasks: list[asyncio.Task[None]] = []
        self._running = False
        self._closed = False
        self._warned_full: set[str] = set()
        self._missed_logs = 0
        self._slow_logs = 0

    # ------------------------------------------------------------------
    # Dựng và gỡ
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        specs: dict[str, ChannelSpec],
        process_count: int,
        *,
        link_id: str | None = None,
        index: int = 0,
    ) -> ProcessLink:
        """Tiến trình gốc gọi: cấp vùng nhớ và chuông cho cả cụm.

        ⚠ `index` là ô của **chính người cấp**, và nó không mặc định đúng cho
        supervisor: cha giữ ô **cuối** (`N`), không phải ô 0. Để nó ở 0 thì cha
        và con thứ nhất dùng chung một vùng ghi và một cái chuông - cha đọc tin
        của con và con không bao giờ thấy lệnh của cha, cả hai đều im lặng.

        Người gọi giữ `link_id` để truyền xuống con qua biến môi trường, và
        `bells` để truyền qua `Process(args=...)` - một semaphore không đi qua
        biến môi trường được.

        ⭐ Bus được dựng **TRƯỚC DI**: nó là hạ tầng của framework, không phải
        một component của ứng dụng, nên nó không đi qua `post_construct` nào cả.
        """
        validate_process_count(process_count)
        # ⛔ Kiểm `index` TRƯỚC khi cấp bất cứ tài nguyên nào. Bản trước kiểm sau
        # khi đã tạo vùng nhớ chung và semaphore, nên một `index` sai để lại rác
        # trong `/dev/shm`: Windows tự dọn khi tiến trình chết, **Linux thì
        # KHÔNG** - vùng nhớ nằm lại tới lần khởi động máy. Đo được 2026-08-21:
        # một lời gọi sai để lại `xime-link-<pid>-<rand>-ctl`. Phát hiện L2.
        if not 0 <= index < process_count:
            raise LinkError(
                f"link index {index} is outside 0..{process_count - 1}"
            )
        # pid nằm trong tên để bước dọn rác lúc khởi động biết chủ của một vùng
        # nhớ mồ côi còn sống hay không; phần ngẫu nhiên để hai ứng dụng Xime
        # chạy cùng máy, cùng đặt tên kênh "fieldbus", không attach vào nhau.
        run_id = link_id or f"{os.getpid()}-{secrets.token_hex(8)}"

        blocks: dict[str, SharedMemory] = {}
        try:
            for name, spec in specs.items():
                layout = ChannelLayout(spec.rows, spec.payload_bytes, process_count)
                block = SharedMemory(
                    name=_block_name(run_id, name), create=True, size=layout.total_bytes
                )
                layout.write_header(view_of(block))
                blocks[name] = block
        except BaseException:
            for block in blocks.values():
                block.close()
                block.unlink()
            raise

        # The bell MUST come from the framework's one context: a semaphore made
        # by the default context cannot cross into a spawn child on Linux.
        # Chuông BẮT BUỘC lấy từ ngữ cảnh duy nhất của framework: semaphore tạo
        # bằng ngữ cảnh mặc định không qua nổi ranh giới sang con spawn trên Linux.
        bells = tuple(MP_CONTEXT.Semaphore(0) for _ in range(process_count))
        return cls(
            link_id=run_id,
            index=index,
            process_count=process_count,
            specs=specs,
            blocks=blocks,
            bells=bells,
            owner=True,
        )

    @classmethod
    def attach(
        cls,
        link_id: str,
        specs: dict[str, ChannelSpec],
        process_count: int,
        index: int,
        bells: tuple[synchronize.Semaphore, ...],
    ) -> ProcessLink:
        """Tiến trình con gọi: gắn vào vùng nhớ cha đã cấp.

        Con **không tự đoán tên, nó nhận tên** - `link_id` đến từ biến môi
        trường, và biến môi trường có mặt từ trước mọi lệnh import.
        """
        validate_process_count(process_count)
        if not 0 <= index < process_count:
            raise LinkError(
                f"link index {index} is outside 0..{process_count - 1}"
            )

        blocks: dict[str, SharedMemory] = {}
        try:
            for name, spec in specs.items():
                layout = ChannelLayout(spec.rows, spec.payload_bytes, process_count)
                block = SharedMemory(name=_block_name(link_id, name))
                layout.verify_header(view_of(block), name)
                blocks[name] = block
        except BaseException:
            for block in blocks.values():
                block.close()
            raise

        return cls(
            link_id=link_id,
            index=index,
            process_count=process_count,
            specs=specs,
            blocks=blocks,
            bells=bells,
            owner=False,
        )

    @property
    def link_id(self) -> str:
        return self._link_id

    @property
    def index(self) -> int:
        return self._index

    @property
    def bells(self) -> tuple[synchronize.Semaphore, ...]:
        """Chuông của cả cụm, để tiến trình gốc truyền xuống con."""
        return self._bells

    def bind(self, handlers: dict[str, BoundHandler]) -> None:
        """Gắn handler đã lấy từ DI. Gọi sau khi container dựng xong."""
        for channel in handlers:
            if channel not in self._specs:
                raise LinkError(
                    f"handler declares channel {channel!r} which was never "
                    f"configured. Known channels: {sorted(self._specs)}"
                )
        self._handlers = handlers

    # ------------------------------------------------------------------
    # Vòng đời
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Khởi động vòng đọc: **một vòng cho mỗi kênh**.

        Mỗi kênh là một đơn vị thứ tự - tin trong một kênh chạy tuần tự, các kênh
        chạy song song với nhau. Đây là lý do tồn tại của cả phần vùng-ghi-riêng:
        `create_task` cho từng tin là **vứt bỏ thứ tự vừa xây**, vì `bật` và
        `tắt` chạy song song thì trạng thái cuối là *cái nào thắng cuộc đua*.

        Muốn song song thì **tách kênh**, không phải tách task.
        """
        if self._running:
            return
        self._running = True
        loop = asyncio.get_running_loop()
        self._tasks = [
            loop.create_task(self._pump(name), name=f"xime-link:{name}")
            for name in self._specs
        ]

    async def stop(self) -> None:
        """Dừng mọi vòng đọc. Idempotent."""
        if not self._running:
            return
        self._running = False
        # Đánh chuông của chính mình để đánh thức thread đang chờ acquire - nếu
        # không thì nó nằm trong `to_thread` cho tới khi có ai đó gửi tin.
        for _ in self._specs:
            self._bells[self._index].release()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks = []
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()

    def close(self) -> None:
        """Trả vùng nhớ. Chỉ tiến trình TẠO mới `unlink`.

        ⚠ Con gọi `unlink` thì các con khác **không attach được nữa**, nên nó
        chỉ `close`. Trên Linux, vùng nhớ là một file thật trong `/dev/shm` nên
        thiếu bước này là để lại rác trong RAM; trên Windows nó biến mất khi
        handle cuối đóng.
        """
        if self._closed:
            return
        self._closed = True
        self._views.clear()
        for name, block in self._blocks.items():
            try:
                block.close()
                if self._owner:
                    block.unlink()
            except Exception:  # noqa: BLE001 - dọn dẹp phải best-effort
                _log.warning("link: could not release channel %r", name, exc_info=True)
        self._blocks.clear()

    # ------------------------------------------------------------------
    # Gửi
    # ------------------------------------------------------------------

    async def announce(self, channel: str, payload: bytes, *, key: str = "") -> None:
        """Phát cho mọi tiến trình khác. Không ai trả lời."""
        self._publish(channel, KIND_ANNOUNCE, key, payload, b"")

    async def send(self, channel: str, key: str, payload: bytes) -> None:
        """Gửi một lệnh có đích. Không chờ trả lời."""
        self._publish(channel, KIND_REQUEST, key, payload, b"")

    async def ask(
        self, channel: str, key: str, payload: bytes, *, timeout: float = 2.0
    ) -> Outcome:
        """Gửi một lệnh và chờ trả lời, trả về **một trong bốn kết cục**.

        ```python
        match await link.ask("fieldbus", key="BT-01", payload=b"stop"):
            case Done(value):    ...   # handler đã nhận và trả lời
            case NoOwner():      ...   # KHÔNG ai nhận -> lỗi CẤU HÌNH
            case NoAnswer():     ...   # có đích nhưng quá hạn
            case Failed(detail): ...   # có người nhận và người đó HỎNG
        ```
        """
        correlation = secrets.token_bytes(16)
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Outcome] = loop.create_future()
        self._pending[correlation] = future
        try:
            row = self._publish(channel, KIND_REQUEST, key, payload, correlation)
            # Nhớ số thứ tự của ĐÚNG dòng vừa gửi. Xem nhánh hết giờ bên dưới.
            seq_luc_gui = self._layouts[channel].read_u64(
                self._views[channel], row, ROW_SEQ
            )
            return await asyncio.wait_for(asyncio.shield(future), timeout)
        except TimeoutError:
            # Hết giờ: phân biệt "không ai nhận" với "có người nhận mà chậm" bằng
            # đúng một byte trên dòng vừa gửi. Không có byte đó thì hai tình
            # huống bắt người gọi làm hai việc khác nhau lại trông giống hệt.
            layout = self._layouts[channel]
            view = self._views[channel]
            # ⛔ Chỉ tin byte đó khi dòng VẪN LÀ DÒNG CŨ. Con trỏ ghi vòng lại
            # sau `rows_per_writer` dòng (mặc định 256), nên với một timeout dài
            # hoặc một kênh bận, dòng ta gửi có thể đã bị một tin khác chiếm và
            # `ROW_TAKER` lúc này thuộc về tin đó. Phát hiện L4 của kiểm toán 0.8.
            #
            # Không phân biệt được thì trả `NoAnswer`, KHÔNG trả `NoOwner`:
            # `NoOwner` là một kết luận (*"không ai đăng ký xử lý việc này"*)
            # và người gọi sẽ thôi thử lại; `NoAnswer` là một trạng thái tạm
            # thời. Đoán sai về phía kết luận thì đắt hơn nhiều.
            if layout.read_u64(view, row, ROW_SEQ) != seq_luc_gui:
                return NoAnswer()
            taker = layout.read_u8(view, row, ROW_TAKER)
            return NoAnswer() if taker != NO_TAKER else NoOwner()
        finally:
            self._pending.pop(correlation, None)

    # ------------------------------------------------------------------
    # Bề mặt ĐỒNG BỘ - dành cho tiến trình KHÔNG có event loop (tiến trình gốc)
    # ------------------------------------------------------------------

    def announce_sync(self, channel: str, payload: bytes, *, key: str = "") -> None:
        """`announce` cho người gọi không có event loop.

        Tiến trình gốc **không dựng DI và không chạy asyncio** - nó `waitpid`,
        đọc bộ nhớ, ngủ. Nhưng nó vẫn phải nói được với con (*"bạn là primary từ
        giờ"*), và ghi vào bus vốn **đã là một thao tác đồng bộ**: `announce()`
        không `await` một dòng nào, nó chỉ bọc `_publish` cho cân với `ask()`.

        ⚠ Không có bản đồng bộ của `ask()`, và đó là cố ý: chờ trả lời cần một
        chỗ để treo, mà cha thì không có. Cha **phát rồi đọc lại ở vòng sau** -
        đúng hình dạng vòng giám sát của nó.
        """
        self._publish(channel, KIND_ANNOUNCE, key, payload, b"")

    def drain_sync(self, channel: str) -> list[LinkMessage]:
        """Đọc và hạ bit mọi dòng đang chờ, **KHÔNG chạy handler nào**.

        Cùng lý do với `announce_sync`. Trả về dữ liệu thô để người gọi tự phân
        nhánh - cha không có DI nên không có handler nào để tra.
        """
        layout, view = self._channel(channel)
        rows = layout.unread_rows(view, self._index)
        out: list[LinkMessage] = []
        for row in sorted(rows, key=lambda r: layout.read_u64(view, r, ROW_SEQ)):
            if not layout.read_u8(view, row, ROW_COMPLETE):
                continue  # đang ghi dở - xem lại ở lần sau
            message = LinkMessage(
                channel=channel,
                key=layout.read_key(view, row),
                payload=layout.read_payload(view, row),
                sender=layout.read_u8(view, row, ROW_SENDER),
            )
            layout.clear_bit(view, self._index, row)
            out.append(message)
        return out

    def _publish(
        self, channel: str, kind: int, key: str, payload: bytes, correlation: bytes
    ) -> int:
        layout, view = self._channel(channel)
        if len(payload) > layout.payload_bytes:
            # Nổ ngay chứ không trả về một kết cục: đây là bug của người viết
            # app, không phải trạng thái lúc chạy, và trả về một kết cục là mời
            # người ta `except` rồi bỏ qua.
            raise LinkError(
                f"payload of {len(payload)} bytes exceeds the {layout.payload_bytes} "
                f"declared for channel {channel!r}. Raise ChannelSpec.payload_bytes, "
                f"or move the data to a store and send a reference."
            )
        if len(key.encode("utf-8")) > KEY_BYTES:
            raise LinkError(
                f"key {key!r} is longer than {KEY_BYTES} bytes on channel {channel!r}"
            )

        row = self._claim_row(layout, view, channel)
        sequence = layout.next_sequence(view)

        layout.write_u64(view, row, ROW_SEQ, sequence)
        layout.write_u64(view, row, ROW_WRITTEN_AT, time.monotonic_ns())
        layout.write_correlation(view, row, correlation)
        layout.write_key(view, row, key)
        layout.write_payload(view, row, payload)
        layout.write_length(view, row, len(payload))
        layout.write_u8(view, row, ROW_KIND, kind)
        layout.write_u8(view, row, ROW_TAKER, NO_TAKER)
        layout.write_u8(view, row, ROW_SENDER, self._index)

        # ⚠ THỨ TỰ Ở ĐÂY LÀ HỢP ĐỒNG, không phải chi tiết hiện thực.
        #
        # `da_ghi_xong` phải bật TRƯỚC khi bật bit chưa-đọc. Người đọc chỉ tìm
        # thấy một dòng QUA BIT của nó, nên đặt bit sau cùng bảo đảm hai điều
        # cùng lúc: không ai đọc được dòng nửa vời, VÀ người ghi chết giữa chừng
        # không để lại một bit không bao giờ hạ được.
        # Thứ tự ngược lại (bit trước, hoàn tất sau) cũng chặn được dòng nửa vời,
        # nhưng nó rò một bit vĩnh viễn mỗi lần người ghi chết đúng khoảng giữa -
        # và người đọc sẽ quay lại nhìn dòng đó mãi mãi.
        layout.write_u8(view, row, ROW_COMPLETE, 1)
        for reader in range(self._process_count):
            if reader != self._index:
                layout.set_bit(view, reader, row)

        # ⚠ LUÔN đánh chuông, không bao giờ "tối ưu" bỏ qua. Semaphore là bộ
        # đếm, không phải sự thật: lệch THỪA thì người đọc thức dậy không thấy
        # gì (bình thường), lệch THIẾU thì có tin mà không ai đánh chuông và
        # người đọc NGỦ QUÊN với tin còn trong bảng.
        # Nó còn đóng một cửa sổ đua: giữa lúc người đọc "quét thấy trống" và
        # lúc nó gọi acquire để ngủ, tin có thể đến - vì đã release nên bộ đếm
        # lên 1 và acquire trả về ngay.
        for reader in range(self._process_count):
            if reader != self._index:
                self._bells[reader].release()
        return row

    def _claim_row(self, layout: ChannelLayout, view: memoryview, channel: str) -> int:
        """Lấy dòng kế tiếp trong vùng của mình, vòng lại và đè khi hết chỗ.

        Không có hạn dùng theo đồng hồ trong dòng: *"vòng lại thì đè"* rẻ hơn -
        không cần đồng hồ, không cần ai đi dọn, và **tự giới hạn bộ nhớ** bởi
        kích thước vùng.

        ⭐ Hệ quả tốt: một tiến trình treo **tự chịu hậu quả** (nó mất tin), chứ
        không nghẽn ai. Nếu chọn *"chờ mọi người đọc xong mới xoá"* thì nó giữ
        bit mãi và cả nhà tắc.
        """
        rows = layout.rows_of(self._index)
        cursor = self._cursors[channel]
        row = rows.start + cursor
        self._cursors[channel] = (cursor + 1) % layout.rows_per_writer

        # Trước khi đè, đếm cho những người chưa kịp đọc. Bit bị đè là dấu vết
        # biến mất; không đếm ngay lúc đó thì tin mất trong im lặng tuyệt đối.
        stale = layout.any_unread(view, row)
        if stale:
            for reader in stale:
                layout.bump_missed(view, reader)
                layout.clear_bit(view, reader, row)
            self._warn_missed(channel, row, stale)

        layout.write_u8(view, row, ROW_COMPLETE, 0)
        self._maybe_warn_full(layout, view, channel)
        return row

    # ------------------------------------------------------------------
    # Đọc
    # ------------------------------------------------------------------

    async def _pump(self, channel: str) -> None:
        """Vòng xử lý của một kênh: chờ chuông, quét bitmap, chạy tuần tự."""
        bell = self._bells[self._index]
        while self._running:
            try:
                await asyncio.to_thread(bell.acquire)
            except asyncio.CancelledError:
                raise
            if not self._running:
                return
            try:
                await self._drain(channel)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - một kênh hỏng không được kéo cả app
                _log.exception("link: channel %r pump failed", channel)

    async def _drain(self, channel: str) -> None:
        """Xử lý mọi dòng đang có bit của mình, theo đúng thứ tự số thứ tự.

        ⚠ *"Thức dậy thì QUÉT. Quét không thấy gì thì ngủ tiếp, đó KHÔNG phải
        lỗi"* - thức dậy giả là chuyện bình thường của một cái chuông đếm.
        """
        layout, view = self._channel(channel)
        rows = layout.unread_rows(view, self._index)
        if not rows:
            return
        for row in sorted(rows, key=lambda r: layout.read_u64(view, r, ROW_SEQ)):
            if not layout.read_u8(view, row, ROW_COMPLETE):
                continue  # đang ghi dở - xem lại ở lần thức sau
            await self._consume(channel, layout, view, row)

    async def _consume(
        self, channel: str, layout: ChannelLayout, view: memoryview, row: int
    ) -> None:
        kind = layout.read_u8(view, row, ROW_KIND)
        key = layout.read_key(view, row)
        correlation = layout.read_correlation(view, row)
        payload = layout.read_payload(view, row)
        sender = layout.read_u8(view, row, ROW_SENDER)

        # ⚠ HẠ BIT TRƯỚC KHI LÀM BẤT CỨ GÌ - quyết định có ý thức, không phải
        # tiện tay. Chết giữa chừng thì tin MẤT (at-most-once) thay vì được làm
        # lại lần nữa (at-least-once). Chọn vế đầu để nhất quán với "không làm
        # đảm bảo giao tuyệt đối"; ứng dụng nào cần chắc thì tự thêm một hàng
        # đợi bền vững ở phía mình.
        layout.clear_bit(view, self._index, row)

        if kind in (KIND_REPLY, KIND_FAILURE):
            self._settle(correlation, kind, payload)
            return

        handler = self._handlers.get(channel)
        if handler is None:
            return  # kênh này ta chỉ dùng để gửi

        verdict, answer = await self._invoke(handler, channel, key, payload)
        if verdict is _FAILED:
            if kind == KIND_REQUEST and correlation != _EMPTY_CORRELATION:
                layout.write_u8(view, row, ROW_TAKER, self._index)
                self._publish(channel, KIND_FAILURE, key, answer, correlation)
            return
        if verdict is _SKIPPED:
            return  # "không phải của tôi" - không ghi người nhận
        if kind != KIND_REQUEST:
            return

        # ⚠ Ngoại lệ DUY NHẤT của luật "mỗi tiến trình chỉ ghi vùng của mình":
        # một byte `nguoi_nhan` trên dòng của NGƯỜI GỬI. Nó phải nằm đó vì chỉ
        # người gửi mới đọc nó, và nó là thứ tách `NoOwner` khỏi `NoAnswer` khi
        # hết giờ. Một byte, một người ghi trong ca dùng thật (một kênh một
        # handler, và chỉ tiến trình giữ khoá đó mới trả khác None).
        layout.write_u8(view, row, ROW_TAKER, self._index)
        if correlation != _EMPTY_CORRELATION:
            self._publish(channel, KIND_REPLY, key, answer, correlation)
        _ = sender

    async def _invoke(
        self, handler: BoundHandler, channel: str, key: str, payload: bytes
    ) -> tuple[object, bytes]:
        """Chạy handler, trả về (kết cục, dữ liệu) - không dùng biến dùng chung.

        Ba kết cục: `_ANSWERED` kèm bytes trả lời · `_SKIPPED` (*"không phải của
        tôi"*) · `_FAILED` kèm mô tả lỗi đã cắt độ dài.
        """
        started = time.monotonic()
        try:
            result = await handler.call(key, payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - biến thành Failed cho người hỏi
            # Traceback đầy đủ được log TẠI ĐÂY, nơi có đủ ngữ cảnh và biến;
            # người hỏi ở tiến trình khác chỉ nhận tên lỗi cộng thông điệp, vì
            # traceback của tiến trình này không giúp họ debug được gì.
            _log.exception(
                "link: handler %s failed on channel %r key %r",
                handler.owner,
                channel,
                key,
            )
            return _FAILED, _describe(exc)
        finally:
            elapsed = time.monotonic() - started
            if elapsed > _SLOW_HANDLER_SECONDS:
                self._warn_slow(handler, channel, key, elapsed)

        if handler.kind == ANNOUNCE or result is None:
            return _SKIPPED, b""
        if handler.kind == REQUEST and not isinstance(result, bytes):
            raise LinkError(
                f"handler {handler.owner} on channel {channel!r} returned "
                f"{type(result).__name__}; an @on_request handler returns bytes "
                f"(it answered) or None (not mine)."
            )
        return _ANSWERED, result

    def _settle(self, correlation: bytes, kind: int, payload: bytes) -> None:
        future = self._pending.get(correlation)
        if future is None or future.done():
            return  # người hỏi đã bỏ cuộc, hoặc đây là reply lạc
        if kind == KIND_FAILURE:
            future.set_result(Failed(payload.decode("utf-8", errors="replace")))
        else:
            future.set_result(Done(payload))

    # ------------------------------------------------------------------
    # Quan sát
    # ------------------------------------------------------------------

    def stats(self) -> LinkStats:
        """Ảnh chụp GẦN ĐÚNG tình trạng của **cả cụm**, không giữ khoá nào.

        ⚠ Gần đúng là một phần của hợp đồng, không phải lời xin lỗi: nó đọc bộ
        nhớ chung trong lúc người khác đang ghi. Đừng dùng nó làm chốt chặn
        logic - `if stats.rows_used == 0:` sẽ sai đúng một lần trong một nghìn
        lần, và đó là loại sai không ai tìm ra.

        ⭐ Nó trả về số liệu của **mọi** tiến trình vì bitmap nằm trong bộ nhớ
        chung: một endpoint sức khoẻ ở tiến trình web trả lời được tình trạng
        của cả đàn, kể cả tiến trình không mở cổng nào.
        """
        now = time.monotonic_ns()
        channels = []
        for name, layout in self._layouts.items():
            view = self._views[name]
            readers = tuple(
                ReaderStats(
                    process_index=index,
                    unread=len(layout.unread_rows(view, index)),
                    missed=layout.read_missed(view, index),
                )
                for index in range(self._process_count)
            )
            used = 0
            oldest: int | None = None
            for row in range(layout.total_rows):
                if not layout.read_u8(view, row, ROW_COMPLETE):
                    continue
                unread = layout.any_unread(view, row)
                if not unread:
                    continue
                used += 1
                age = (now - layout.read_u64(view, row, ROW_WRITTEN_AT)) // 1_000_000
                oldest = age if oldest is None else max(oldest, age)
            channels.append(
                ChannelStats(
                    name=name,
                    rows_total=layout.total_rows,
                    rows_used=used,
                    oldest_unread_age_ms=oldest,
                    readers=readers,
                )
            )
        return LinkStats(link_id=self._link_id, channels=tuple(channels))

    def dump(self, channel: str) -> tuple[RawRow, ...]:
        """Đọc thô mọi dòng của một kênh. **CHỈ để gỡ lỗi.**

        Tách hẳn khỏi `stats()` và tên nói rõ là công cụ gỡ lỗi: trộn chung thì
        sẽ có người gọi nó mỗi mười giây trong một endpoint sức khoẻ và chở
        toàn bộ payload ra ngoài.
        """
        layout, view = self._channel(channel)
        now = time.monotonic_ns()
        rows = []
        for row in range(layout.total_rows):
            if not layout.read_u8(view, row, ROW_COMPLETE):
                continue
            taker = layout.read_u8(view, row, ROW_TAKER)
            rows.append(
                RawRow(
                    row=row,
                    kind=_KIND_NAMES.get(layout.read_u8(view, row, ROW_KIND), "?"),
                    key=layout.read_key(view, row),
                    sender=layout.read_u8(view, row, ROW_SENDER),
                    taker=None if taker == NO_TAKER else taker,
                    unread_by=tuple(layout.any_unread(view, row)),
                    payload=layout.read_payload(view, row),
                    age_ms=(now - layout.read_u64(view, row, ROW_WRITTEN_AT)) // 1_000_000,
                )
            )
        return tuple(rows)

    # ------------------------------------------------------------------
    # Nội bộ
    # ------------------------------------------------------------------

    def _channel(self, channel: str) -> tuple[ChannelLayout, memoryview]:
        try:
            return self._layouts[channel], self._views[channel]
        except KeyError:
            raise LinkError(
                f"unknown link channel {channel!r}. Configured: "
                f"{sorted(self._specs)}. Channels are declared in "
                f"configure_link(channels={{...}})."
            ) from None

    def _warn_missed(self, channel: str, row: int, readers: list[int]) -> None:
        if self._missed_logs % _RATE_LIMIT_EVERY == 0:
            _log.warning(
                "link: channel %r overwrote row %d before process(es) %s read it "
                "(%d such events so far). The table wrapped around, which on a "
                "signal bus almost always means one process has stalled.",
                channel,
                row,
                readers,
                self._missed_logs + 1,
            )
        self._missed_logs += 1

    def _warn_slow(
        self, handler: BoundHandler, channel: str, key: str, elapsed: float
    ) -> None:
        # Bộ đếm hãm nhịp RIÊNG cho từng loại cảnh báo. Dùng chung một bộ đếm
        # thì một loại ồn ào sẽ nuốt mất loại kia - lỗi đã vấp ở F15.
        if self._slow_logs % _RATE_LIMIT_EVERY == 0:
            _log.warning(
                "link: handler %s on channel %r took %.1fs for key %r - it blocks "
                "its channel while it runs. Queue the work and return.",
                handler.owner,
                channel,
                elapsed,
                key,
            )
        self._slow_logs += 1

    def _maybe_warn_full(
        self, layout: ChannelLayout, view: memoryview, channel: str
    ) -> None:
        # ⛔ Đo VÙNG GHI CỦA CHÍNH MÌNH, không đo hộp thư đến.
        #
        # Bản trước đếm `unread_rows(view, self._index)` - những dòng CHƯA ĐỌC
        # GỬI TỚI TÔI - rồi chia cho `total_rows` của cả kênh, và in một câu về
        # *"bảng ghi sắp đầy"*. Hai đại lượng khác hẳn nhau, và nó sai theo cả
        # hai chiều: đo được 2026-08-21 rằng vùng ghi **8/8 đầy** trong khi phép
        # đo đọc ra **0/16** nên không kêu; ngược lại một người chỉ nhận mà xử
        # lý chậm sẽ bị tố là "bảng ghi sắp đầy" dù nó chưa ghi dòng nào.
        #
        # Thứ sắp đầy và gây mất tin là **vùng ghi của người gửi**: con trỏ vòng
        # lại sau `rows_per_writer` dòng và đè lên dòng chưa ai đọc. Phát hiện
        # T2 của kiểm toán 0.8 - và không một test nào chạm tới hàm này.
        cua_toi = layout.rows_of(self._index)
        chua_doc = sum(1 for r in cua_toi if layout.any_unread(view, r))
        ratio = chua_doc / len(cua_toi) if cua_toi else 0.0
        if ratio >= _FULL_WARN_RATIO and channel not in self._warned_full:
            self._warned_full.add(channel)
            _log.warning(
                "link: channel %r is %.0f%% full of unread rows. On a signal bus "
                "that is a symptom, not a size problem - look for a stalled reader "
                "before raising ChannelSpec.rows.",
                channel,
                ratio * 100,
            )
        elif ratio < _FULL_WARN_RATIO:
            self._warned_full.discard(channel)


def _block_name(link_id: str, channel: str) -> str:
    return f"xime-link-{link_id}-{channel}"


def _describe(exc: BaseException) -> bytes:
    text = f"{type(exc).__name__}: {exc}"[:_DETAIL_LIMIT]
    return text.encode("utf-8", errors="replace")


# Ba kết cục của một lần chạy handler. Sentinel object chứ không phải chuỗi để
# không ai so nhầm bằng `==` với một giá trị dữ liệu.
_ANSWERED: object = object()
_SKIPPED: object = object()
_FAILED: object = object()

_EMPTY_CORRELATION = b"\x00" * 16

_KIND_NAMES = {
    KIND_ANNOUNCE: "announce",
    KIND_REQUEST: "request",
    KIND_REPLY: "reply",
    KIND_FAILURE: "failure",
}

__all__ = ["INTERNAL_CHANNEL", "LinkError", "ProcessLink"]
