"""Khoanh vùng event loop bị kẹt: kêu tăng dần, và nói KẸT Ở ĐÂU.

## Vì sao có file này

`Watchdog` phát hiện được loop đứng, nhưng nó **không nói được đứng ở đâu** - vì
chính nó là một task trên loop đó, nên khi loop kẹt thì nó cũng kẹt. Cha chỉ
thấy một ô nhịp ôi và kết luận *"event loop is blocked"*, không hơn.

Đợt điều tra 2026-08-31 cho thấy chỗ thiếu đó tốn bao nhiêu: thứ duy nhất tách
được *"mã ứng dụng gọi hàm đồng bộ"* khỏi *"lỗi của hệ điều hành"* là **một dòng
stack**, và phải đi vay từ một bản dò tạm viết vội ở repo ngoài. Đây chính là đề
nghị số 3 của báo cáo gốc từ `Service ngang`, và là đề nghị duy nhất của họ trúng
đích.

## Chi phí: đo được, gần bằng không

Bộ này **không thêm một dòng nào vào đường xử lý request**. Nó là một thread đọc
lại **chính mốc nhịp mà `Watchdog` đã ghi sẵn**.

| | Đo được |
|---|---|
| Thông lượng khi rảnh, có thread canh so với không | **-0,22%**, nằm trong nhiễu |
| Một lần chụp stack | **0,11 ms**, và chỉ khi đã kẹt |

Vì vậy nó **bật mặc định**, không phải thứ chỉ có ở bản dev. Sự cố đáng biết nhất
xảy ra ở production, nơi không ai đang bật cờ debug; một tính năng chi phí 0 mà
chỉ chạy ở chỗ không có sự cố thì gần như vô dụng. `xime.dev` chỉnh **ngưỡng và
độ dài**, không chỉnh *có bật hay không*.

## Kêu tăng dần, không im rồi giết

Trước bản này, dòng log đầu tiên người ta nhìn thấy **cũng là dòng báo tử**:
`_reap_hung_children` ghi `CRITICAL` và giết trong cùng một nhịp. Nay:

| Kẹt được | Mức | Làm gì |
|---|---|---|
| 5 s | `WARNING` | báo, kèm stack |
| 15 s | `ERROR` | báo lại, kèm stack mới - nó đã đi tiếp hay đứng yên chỗ cũ? |
| 30 s | `CRITICAL` | loa to, khai rõ cha sắp giết |
| 60 s | - | cha giết (`SILENCE_SECONDS` bên `_watchdog.py`) |

Mỗi mức in **một lần cho mỗi đợt kẹt**, không in lặp. Đây không phải chuyện gọn
gàng: nếu thứ đang làm kẹt loop lại chính là ghi log ra console (trên Windows đó
là I/O đồng bộ), thì in mỗi vòng sẽ **làm nặng thêm đúng cái đang hỏng**.

## ⛔ Ngoại lệ: kẹt trong `accept()` thì hạn chót NGẮN hơn nhiều

Từ khi có khoá accept (`_accept_lock.py`), một worker kẹt **bên trong `accept()`**
là worker **đang giữ khoá**, và trong lúc đó **cả cụm không ai nhận được kết nối**.

Nên hai loại kẹt không cùng mức nguy hiểm:

| Kẹt ở đâu | Hại ai | Hạn chót |
|---|---|---|
| bất cứ chỗ nào khác | chỉ chính nó | **60 giây** |
| **trong `accept()`, đang giữ khoá** | **cả cụm** | **10 giây** |

Quá hạn ngắn thì tiến trình **tự kết thúc**. Đó là cách nhanh nhất trả khoá lại:
Windows thấy chủ mutex chết và trao quyền cho người đợi kế tiếp bằng
`WAIT_ABANDONED` - đã đo, **0,00 giây**. Chờ cha giết thì lâu hơn, mà mỗi giây
chờ là một giây cả cụm điếc.

⚠ Nó dùng đúng cặp lệnh mà `_orphan.py` đã chốt cho hai nền tảng, vì lý do y hệt:
`os.kill(SIGTERM)` trên POSIX (tín hiệu phải tới **tiến trình**, không phải thread
đang gọi), `signal.raise_signal` trên Windows (ở đó `os.kill` gọi thẳng
`TerminateProcess`, tức mất sạch phần dọn êm).
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
import traceback
from typing import TYPE_CHECKING

from ._watchdog import SILENCE_SECONDS

if TYPE_CHECKING:
    from ._watchdog import Heartbeats

_log = logging.getLogger("xime.bootstrap")

#: Nhịp lấy mẫu. Rẻ tới mức không cần chỉnh: một lần đọc 8 byte bộ nhớ chung.
NHIP_LAY_MAU: float = 0.5

#: Các mức kêu, theo giây kẹt. Phải tăng dần.
MUC_CANH_BAO: tuple[tuple[float, int], ...] = (
    (5.0, logging.WARNING),
    (15.0, logging.ERROR),
    (30.0, logging.CRITICAL),
)

#: Hạn chót riêng cho ca đang giữ khoá accept - xem docstring module.
HAN_CHOT_ACCEPT: float = 10.0

#: Số khung stack in ra. Đủ để thấy chỗ kẹt, không đủ để làm ngập log.
SO_KHUNG: int = 12

#: Biến môi trường cha đặt cho con, mang tên tiến trình (ví dụ `api-2`).
#: ⚠ Chép giá trị thay vì nhập `_processes.PROCESS_ID_ENV` để module này không
#: kéo theo cả bộ phân tích cấu hình - nó phải nhẹ và không có vòng import.
_TEN_ENV = "XIME_PROCESS_ID"


def _stack_cua_luong_chinh() -> list[str]:
    """Stack của thread chính, đọc từ MỘT THREAD KHÁC.

    Đây là toàn bộ lý do bộ này là một thread chứ không phải một task: khi loop
    kẹt, mọi task trên nó cũng kẹt, nên chỉ người đứng ngoài mới kể lại được.
    """
    ident = threading.main_thread().ident
    if ident is None:
        return ["  (khong doc duoc stack cua luong chinh)"]
    khung = sys._current_frames().get(ident)
    if khung is None:
        return ["  (khong doc duoc stack cua luong chinh)"]
    return [
        f"  {f.filename}:{f.lineno} trong {f.name}"
        for f in traceback.extract_stack(khung)[-SO_KHUNG:]
    ]


def _dang_ket_trong_accept(dong_stack: list[str]) -> bool:
    return any("in accept" in d or " trong accept" in d for d in dong_stack)


class StallReporter:
    """Thread canh nhịp của chính tiến trình này và kể lại chỗ kẹt."""

    def __init__(
        self,
        beats: Heartbeats,
        index: int,
        ten: str | None = None,
        *, chi_tiet: bool = False,
    ) -> None:
        self._beats = beats
        self._index = index
        self._ten = ten or os.environ.get(_TEN_ENV) or f"slot-{index}"
        self._chi_tiet = chi_tiet
        self._thread: threading.Thread | None = None
        self._dung = threading.Event()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._chay, name="xime-stall-report", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._dung.set()
        self._thread = None

    # ------------------------------------------------------------------

    def _chay(self) -> None:
        da_keu = 0                      # số mức đã kêu trong đợt kẹt hiện tại
        while not self._dung.wait(NHIP_LAY_MAU):
            try:
                ket = self._beats.silent_for(self._index)
            except Exception:  # noqa: BLE001 - bộ dò không được làm chết app
                return
            if ket is None or ket < MUC_CANH_BAO[0][0]:
                if da_keu:
                    _log.info(
                        "stall %s: event loop quay lai sau %.1fs",
                        self._ten, ket if ket is not None else 0.0,
                    )
                    da_keu = 0
                continue

            muc_can = sum(1 for nguong, _ in MUC_CANH_BAO if ket >= nguong)
            if muc_can > da_keu:
                da_keu = muc_can
                self._keu(ket, MUC_CANH_BAO[muc_can - 1][1])

            self._kiem_khoa_accept(ket)

    def _keu(self, ket: float, muc: int) -> None:
        dong = _stack_cua_luong_chinh()
        _log.log(
            muc,
            "%s\nstall %s: EVENT LOOP DUNG YEN %.1f giay (pid %s)\n"
            "Moi request, moi task nen, moi timer cua tien trinh nay deu dang "
            "dung. Cha se giet no o giay thu %.0f.\nNo dang ket o day:\n%s\n%s",
            "=" * 72 if muc >= logging.CRITICAL else "",
            self._ten, ket, os.getpid(),
            SILENCE_SECONDS,
            "\n".join(dong),
            "=" * 72 if muc >= logging.CRITICAL else "",
        )

    def _kiem_khoa_accept(self, ket: float) -> None:
        """Kẹt trong `accept()` khi đang giữ khoá thì tự kết thúc sớm."""
        if ket < HAN_CHOT_ACCEPT:
            return
        from ._accept_lock import dang_giu_khoa_tu

        tu = dang_giu_khoa_tu()
        if tu is None or (time.monotonic() - tu) < HAN_CHOT_ACCEPT:
            return
        _log.critical(
            "%s\nstall %s: KET TRONG accept() VA DANG GIU KHOA %.1f giay "
            "(pid %s).\nCa CUM khong ai nhan duoc ket noi trong luc nay, nen "
            "tien trinh nay TU KET THUC de tra khoa lai ngay.\n"
            "Windows se trao khoa cho nguoi doi ke tiep (WAIT_ABANDONED).\n%s",
            "=" * 72, self._ten, time.monotonic() - tu, os.getpid(), "=" * 72,
        )
        self._tu_ket_thuc()

    @staticmethod
    def _tu_ket_thuc() -> None:
        # ⛔ Hai nền tảng, hai lệnh - đổi chỗ thì hỏng IM LẶNG. Lý do đầy đủ ở
        # `_orphan.py`: `raise_signal` gửi cho THREAD đang gọi nên không ngắt
        # nổi `epoll_wait` của thread chính trên POSIX; còn `os.kill` trên
        # Windows gọi thẳng `TerminateProcess`, tức mất sạch phần dọn êm.
        try:
            if sys.platform == "win32":
                signal.raise_signal(signal.SIGTERM)
            else:
                os.kill(os.getpid(), signal.SIGTERM)
        except Exception:  # noqa: BLE001
            os._exit(1)
