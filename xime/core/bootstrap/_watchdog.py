"""Watchdog kiểu phần cứng: con tự chứng minh, cha chỉ đọc.

```text
CON:  mỗi 1 giây, ghi time.time() vào ô của mình   (task trên EVENT LOOP CHÍNH)
CHA:  mỗi vòng giám sát, đọc ô của từng con
      im quá 10 giây  ->  GIẾT
                      ->  waitpid xác nhận đã exit
                      ->  BÂY GIỜ mới thăng cấp con khác
```

### Vì sao watchdog chứ không phải health check

| | Health check | **Watchdog** |
|---|---|---|
| Chiều | Cha **hỏi**, con **trả lời** | Con **tự chứng minh**, cha chỉ đọc |
| Cha phải dựng gì | Client, timeout, retry | **Không gì** - đọc 8 byte |
| Con bận | Không trả lời được **dù vẫn khoẻ** | Vẫn vỗ được nếu loop còn quay |

### ⭐⭐ Vỗ ở đâu quyết định nó ĐO CÁI GÌ

Đây là cái bẫy kinh điển của watchdog phần cứng, và nó dịch sang đây gần như
nguyên văn. Trong firmware, lỗi hay gặp nhất là đặt lệnh vỗ **trong ngắt timer**:
timer vẫn chạy khi vòng lặp chính đã treo, nên watchdog được vỗ đều đặn trong khi
thiết bị chết cứng. Watchdog hoạt động hoàn hảo - nó chỉ **đang canh sai thứ**.

| Vỗ ở đâu | Đo được gì |
|---|---|
| Thread riêng | ⛔ chỉ đo *"tiến trình còn tồn tại"* - `waitpid` đã trả lời rồi |
| **Task trên event loop chính** | ✅ đo *"**event loop chưa bị chặn**"* |

Vế thứ hai mới đáng canh, vì nó bắt đúng cách hỏng mà hai cơ chế kia mù: một
coroutine gọi I/O đồng bộ hoặc chạy vòng lặp CPU dài sẽ **chặn cả event loop**.
Tiến trình vẫn sống theo kernel (`waitpid` im), còn hỏi qua HTTP thì *chậm* không
phân biệt được với *mạng chậm*. Watchdog trên loop thì **im bặt ngay**.

⚠ **Chỗ đặt lệnh vỗ là một phần của HỢP ĐỒNG, không phải chi tiết hiện thực.** Ai
đó "dọn dẹp" bằng cách chuyển nó sang thread riêng thì watchdog xanh mãi mãi và
không gì báo. Có test canh: chặn loop thì nhịp phải **đứng**.

### ⛔ Watchdog là tín hiệu GIẾT, không phải tín hiệu THĂNG CẤP

Thăng cấp chỉ tin `waitpid` - sự thật của kernel. Nhờ vậy ca *"hai primary"* đóng
chặt: A treo, cha **giết** A, kernel xác nhận A chết, cha mới thăng cấp B. A không
thể tỉnh lại vì nó đã chết thật chứ không phải *bị coi là* chết.

### ⚠ Vì sao nhịp vỗ KHÔNG đi bằng `ProcessLink`

Thiết kế nói watchdog *"đi chung chuyến"* với bus, và ý đó đúng ở tầng khái niệm:
cả hai đều là **vùng ghi riêng cho từng tiến trình trong bộ nhớ chung**. Nhưng nhịp
vỗ **không được là một dòng tin của bus**, và lý do là số học:

| | |
|---|---|
| Nhịp 1 giây, cụm 4 tiến trình | 4 dòng/giây đổ vào một vòng 256 dòng - vòng lại sau **một phút** |
| Không ai đọc nhịp của người khác | Bit chưa-đọc của họ không bao giờ hạ, nên mỗi lần vòng lại **cộng vào `missed`** |

`missed` là **chỉ số chẩn đoán chính** của bus (*"tiến trình kia đọc không kịp"*).
Cho nhịp vỗ chảy qua đó là làm hỏng đúng thứ đồng hồ mình dựng lên để đo sức khoẻ.

> Nhịp vỗ là một **đại lượng bị ghi đè**, không phải một **sự kiện**. Bus chở sự
> kiện; đại lượng thì ở một ô riêng.

Nên đây là một vùng nhớ chung **riêng, rất nhỏ** (`16 + 8×N` byte cho cả cụm), và
nó độc lập với việc ứng dụng có khai kênh nào không.
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from multiprocessing.shared_memory import SharedMemory
from typing import Final

from xime.core.shared import ghi_o, view_of

_log = logging.getLogger("xime.bootstrap")

MAGIC: Final[bytes] = b"XBET"
VERSION: Final[int] = 2

# magic 4B · version 2B · so_o 2B  ->  căn 8 cho phần mốc phía sau
_HEADER = struct.Struct("<4sHH")
HEADER_BYTES: Final[int] = 8
# ⭐ MỖI Ô HAI GIÁ TRỊ, không phải một: mốc nhịp **và** số lần đã vỗ.
#
# Bản 1 chỉ có mốc, và `NEVER = 0.0` phải gánh **ba** nghĩa cùng lúc:
#   1. chưa bao giờ vỗ (tiến trình đang khởi động)
#   2. vừa bị `reset()` vì cha sắp sinh con mới
#   3. vùng nhớ vừa cấp phát, hoặc một lần ghi dở dang
#
# Ba tình huống đó bắt người đọc làm ba việc khác nhau, nên gộp vào một giá trị
# là vi phạm luật 03 ngay trong định dạng dữ liệu. Và nó đã trả giá thật: đợt
# 2026-08-31 có worker bị giết kèm *"never sent a heartbeat in 1323s"* trong khi
# log chứng minh nó **đã** vỗ nhịp bình thường - mà không ai phân biệt nổi, vì
# bằng chứng không tồn tại trong định dạng.
#
# Với bộ đếm: `so_nhip > 0` **chứng minh** tiến trình đã từng vỗ. Câu hỏi
# *"nó có bao giờ vỗ không"* từ chỗ không trả lời được thành trả lời được bằng
# một phép so sánh.
#
# ⭐ Bộ đếm chỉ tăng, không bao giờ reset trong đời một tiến trình - **và nó
# không tràn được**. `Q` là 64 bit không dấu, trần 1,8·10¹⁹:
#
#   nhịp thật (1 lần/giây)              ->  5,8·10¹¹ năm
#   chạy hết tốc lực (3,4 triệu/giây)   ->  1,7·10⁵ năm
#
# ⛔ Và nếu bằng cách nào đó vẫn tràn thì `struct.pack` **ném `struct.error`**,
# nó KHÔNG âm thầm quấn về 0. Đó là hành vi đúng ở đây, đừng "sửa" thành quấn
# vòng: `so_nhip == 0` nghĩa là *"chưa bao giờ vỗ"*, nên một bộ đếm quấn về 0 là
# dựng lại đúng lỗi đã cắn 7 lần ngày 30-31/8. Một tiếng nổ ồn ào sau 170 nghìn
# năm tốt hơn một lần giết nhầm im lặng.
_BEAT = struct.Struct("<dQ")
BEAT_BYTES: Final[int] = _BEAT.size

#: Con vỗ mỗi ngần này giây.
PAT_SECONDS: Final[float] = 1.0

#: Im quá ngần này giây thì cha giết.
#:
#: Chọn theo nguyên tắc phần cứng: **rộng hơn tác vụ dài nhất còn hợp lệ** (GC
#: pause tệ nhất cộng biên). Giết oan thì cha dựng lại, mất vài trăm mili giây;
#: không giết thì treo mãi. Hai hậu quả không cùng cỡ nên nghiêng về giết, nhưng
#: ngưỡng vẫn rộng rãi.
SILENCE_SECONDS: Final[float] = 60.0
#: ⚠ Nâng từ 10 lên 60 giây (2026-08-31, chủ dự án chốt). Mười giây là **hạn chót
#: giết mà không có một lời cảnh báo nào trước đó** - dòng log đầu tiên người vận
#: hành nhìn thấy cũng chính là dòng báo tử. Nay có thang cảnh báo tăng dần ở
#: `_supervisor._MUC_CANH_BAO` (10 → 25 → 45 giây) và tiến trình tự in stack của
#: chính nó (`_stall_report`), nên kéo dài hạn chót là để **giữ hiện trường**,
#: không phải để khoan dung với lỗi.
#:
#: ⛔ Ca kẹt trong `accept()` KHÔNG dùng ngưỡng này: nó giữ khoá accept nên hại
#: cả cụm, và có hạn chót riêng 10 giây ở `_stall_report.HAN_CHOT_ACCEPT`.

#: Con chưa vỗ lần nào thì cha chờ ngần này giây rồi mới coi là treo.
#:
#: ⚠ **Thiết kế không chốt con số này, nó được thêm lúc thi công.** Thiết kế nói
#: `NEVER` nghĩa là *"đang khởi động"*, và đúng - nhưng nó không nói **khi nào thì
#: đang-khởi-động thôi là một lời bào chữa**. Không có ngưỡng này thì một con treo
#: **trước nhịp vỗ đầu tiên** (kẹt trong `post_construct`, chờ một kết nối không
#: bao giờ mở) sống mãi mãi và cha không bao giờ biết - đúng cái lỗ mà watchdog
#: sinh ra để bịt, chỉ dịch sớm hơn mười giây.
#:
#: Rộng gấp sáu ngưỡng im lặng vì hai giai đoạn không cùng cỡ: một tiến trình
#: **đang phục vụ** không có lý do gì chặn loop mười giây, còn một tiến trình
#: **đang khởi động** thì dựng DI, mở pool, lấy cert - hàng chục giây là bình
#: thường trên một máy lạnh.
STARTUP_GRACE_SECONDS: Final[float] = 60.0

#: Ô chưa bao giờ được vỗ. Tách hẳn khỏi *"vỗ rất lâu rồi"* - một tiến trình đang
#: khởi động chưa kịp vỗ lần nào **không phải** một tiến trình treo, và đối xử với
#: nó như treo là giết mọi con ngay lúc chúng vừa sinh ra.
NEVER: Final[float] = 0.0


def block_name(run_id: str) -> str:
    return f"xime-beat-{run_id}"


def total_bytes(slots: int) -> int:
    return HEADER_BYTES + BEAT_BYTES * slots


class Heartbeats:
    """Bảng nhịp vỗ dùng chung: một ô 8 byte cho mỗi tiến trình.

    Không khoá, không nguyên tử: một `double` 8 byte căn 8 thì đọc và ghi không
    xé nhau trên mọi kiến trúc Xime chạy, và **kể cả có xé thì hậu quả cũng chỉ
    là một lần đọc lệch** - vòng sau đọc lại. Đây là chỗ chi phí của một khoá
    lớn hơn thứ nó bảo vệ.
    """

    __slots__ = ("_block", "_view", "_slots", "_owner", "_closed")

    def __init__(self, block: SharedMemory, slots: int, *, owner: bool) -> None:
        self._block = block
        self._view = view_of(block)
        self._slots = slots
        self._owner = owner
        self._closed = False

    # -- dựng và gỡ --------------------------------------------------------

    @classmethod
    def create(cls, run_id: str, slots: int) -> Heartbeats:
        block = SharedMemory(
            name=block_name(run_id), create=True, size=total_bytes(slots)
        )
        _HEADER.pack_into(view_of(block), 0, MAGIC, VERSION, slots)
        for index in range(slots):
            _BEAT.pack_into(
                view_of(block), HEADER_BYTES + BEAT_BYTES * index, NEVER, 0
            )
        return cls(block, slots, owner=True)

    @classmethod
    def attach(cls, run_id: str, slots: int) -> Heartbeats:
        block = SharedMemory(name=block_name(run_id))
        magic, version, found = _HEADER.unpack_from(view_of(block), 0)
        if magic != MAGIC or version != VERSION or found != slots:
            block.close()
            raise ValueError(
                f"heartbeat table {block_name(run_id)!r} carries "
                f"(magic={magic!r}, version={version}, slots={found}) but this "
                f"process expects (magic={MAGIC!r}, version={VERSION}, "
                f"slots={slots})."
            )
        return cls(block, slots, owner=False)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._view.release()
        try:
            self._block.close()
            if self._owner:
                self._block.unlink()
        except Exception:  # noqa: BLE001 - dọn dẹp phải best-effort
            _log.warning("watchdog: could not release the beat table", exc_info=True)

    # -- đọc và ghi --------------------------------------------------------

    def pat(self, index: int) -> None:
        # ⛔ `monotonic()`, KHÔNG phải `time()`. Đồng hồ tường có thể nhảy:
        # NTP kéo giờ, người vận hành sửa giờ, máy ảo khôi phục ảnh chụp. Một
        # cú nhảy TIẾN 30 giây làm `silent_for` của MỌI con đang khoẻ vọt lên
        # 30s > 10s, nên cha giết cả đàn cùng lúc; rồi chống domino đếm đủ ba
        # lần thăng cấp và **dừng cấp vai primary vĩnh viễn**. Phát hiện T1 của
        # kiểm toán 0.8.
        #
        # `monotonic()` so được giữa hai tiến trình trên cùng một máy (Linux:
        # CLOCK_MONOTONIC theo hệ thống, không theo tiến trình), và `core/link`
        # cùng `core/refdata` đã dùng `monotonic_ns` cho đúng lý do đó - hai
        # nhánh của cùng một hàm ở đây lại dùng hai đồng hồ khác nhau.
        # ⛔⭐ `ghi_o`, KHÔNG PHẢI `pack_into` - đây là bản vá của một lỗi thật,
        # không phải chuyện phong cách. `pack_into` xoá vùng về 0 trước khi ghi,
        # mà `NEVER` chính là `0.0`, nên cha đọc trúng cửa sổ đó kết luận *"con
        # này chưa bao giờ vỗ nhịp"* và **giết một tiến trình đang khoẻ** - đúng
        # lỗi đã cắn 7 lần trong hai ngày 30 và 31/8. Số đo và lý do đầy đủ ở
        # docstring của `ghi_o`; hồ sơ điều tra ở
        # `.claude/docs/ghi-chep/loi-nhip-tim-o-quay-ve-khong-2026-08-31.md`.
        _, so = self.read(index)
        ghi_o(
            self._view, HEADER_BYTES + BEAT_BYTES * index, _BEAT,
            time.monotonic(), so + 1,
        )

    def read(self, index: int) -> tuple[float, int]:
        """Trả về `(mốc nhịp, số lần đã vỗ)`.

        Số lần vỗ là thứ phân biệt *"chưa bao giờ vỗ"* với *"đã vỗ rồi mà ô lại
        về không"* - vế sau là hỏng, và trước bản này không ai thấy được nó.
        """
        moc, so = _BEAT.unpack_from(self._view, HEADER_BYTES + BEAT_BYTES * index)
        return float(moc), int(so)

    def so_nhip(self, index: int) -> int:
        """Số lần tiến trình ở ô này đã vỗ. `0` nghĩa là **chưa bao giờ**."""
        return self.read(index)[1]

    def reset(self, index: int) -> None:
        """Xoá ô về *chưa bao giờ vỗ*. Cha gọi khi sinh lại một con.

        Thiếu bước này thì con mới thừa hưởng mốc của con vừa chết, và nếu mốc đó
        đã cũ hơn ngưỡng thì cha **giết con mới ngay khi nó vừa sinh ra** - một
        vòng lặp sinh-giết không lý do, và triệu chứng duy nhất là log.
        """
        ghi_o(self._view, HEADER_BYTES + BEAT_BYTES * index, _BEAT, NEVER, 0)

    def silent_for(self, index: int, *, now: float | None = None) -> float | None:
        """Số giây kể từ nhịp cuối, hoặc `None` khi **chưa bao giờ vỗ**.

        Hai giá trị chứ không một, đúng [luật 03](../../../.claude/rules/03-mot-gia-tri-mot-nghia.md):
        *chưa vỗ lần nào* là **đang khởi động** (chờ tiếp), *vỗ lâu rồi* là
        **đang treo** (giết). Gộp chúng thành một con số lớn là giết mọi con
        trong mười giây đầu đời của cụm.
        """
        beat, so = self.read(index)
        if so == 0:
            # Chưa bao giờ vỗ. ⚠ Xét theo BỘ ĐẾM, không theo mốc: một ô có
            # `so > 0` mà mốc bằng 0 là ô **hỏng**, không phải ô đang khởi động,
            # và gọi nó là "đang khởi động" sẽ che đúng thứ cần thấy.
            return None
        if beat == NEVER:
            _log.error(
                "watchdog: o nhip %d co so_nhip=%d nhung moc=0. Day la trang "
                "thai KHONG THE xay ra hop le - o da tung duoc vo roi bi dua ve "
                "khong ma bo dem khong bi xoa theo. Coi nhu treo.",
                index, so,
            )
            return float("inf")
        return (now if now is not None else time.monotonic()) - beat


class Watchdog:
    """Task định kỳ **trên event loop chính** của tiến trình con.

    ⚠ `asyncio.sleep` chứ không phải `threading.Timer`, và đó là toàn bộ điểm:
    task này chỉ chạy được khi loop còn quay. Chuyển nó sang một thread là biến
    watchdog thành thứ luôn xanh - xem docstring module.
    """

    def __init__(
        self, beats: Heartbeats, index: int, *, interval: float = PAT_SECONDS
    ) -> None:
        self._beats = beats
        self._index = index
        self._interval = interval
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        # Vỗ một nhịp NGAY, đừng đợi hết chu kỳ đầu: ô đang mang `NEVER`, và một
        # ô `NEVER` là "đang khởi động" - trạng thái đó nên kết thúc ngay khi loop
        # thật sự bắt đầu quay, không phải một giây sau.
        self._beats.pat(self._index)
        self._task = asyncio.get_running_loop().create_task(
            self._loop(), name="xime-watchdog"
        )

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            self._beats.pat(self._index)
