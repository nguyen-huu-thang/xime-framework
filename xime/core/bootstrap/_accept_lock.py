"""Khoá `accept()` cho Windows: chỉ một tiến trình được nằm trong `accept()`.

## Vì sao có file này

Trên Windows, khi nhiều tiến trình cùng `accept()` trên một socket lắng nghe dùng
chung, tiến trình **thua cuộc đua** bị nhân giữ lại **bên trong `accept()`** cho
tới khi chính client kia bỏ cuộc - dù socket đã đặt non-blocking đúng chuẩn và
`select()` vừa báo sẵn sàng. Vì `accept()` chạy ngay trong callback của event
loop, cả event loop của tiến trình đó đứng im suốt thời gian ấy.

Đã đo: thời gian kẹt **bám đúng theo timeout của client** (client chờ 5 giây thì
kẹt 5,4 giây; chờ 40 giây thì kẹt 40,5 giây), và **kết nối mới không cứu được
nó**. Toàn bộ phép đo, thang mười bậc thu hẹp nguyên nhân, và phép so với Node:
`.claude/docs/ghi-chep/windows-shared-listener-accept-treo.md`.

⛔ **Không có mẹo vá ở tầng Python.** Cờ non-blocking đặt đúng và có hiệu lực (đã
đo riêng). Đường IOCP - thứ Node dùng và không dính - thì CPython **không nhận
nổi socket kế thừa**, nó chết ở `CreateIoCompletionPort` với `WinError 87`. Nên
trên Windows Python bị dồn vào đúng một đường, và đường đó có lỗi.

## Lời giải: thundering herd, và cách chữa kinh điển

Cho **đúng một tiến trình được gọi `accept()` tại một thời điểm**. Đây là
`accept_mutex` của nginx và `AcceptMutex` của Apache, chỉ khác chỗ đặt.

Đo được trên cụm ba tiến trình: **7 lần treo xuống 0**, chia tải vẫn đều
(109.622 / 112.089 / 111.149 lần accept), giá phải trả về thông lượng là
**2,5%**.

⭐ **Khoá không đụng gì tới cổng mạng.** Cổng vẫn `LISTEN`, nhân vẫn bắt tay TCP
và vẫn xếp kết nối vào hàng đợi. Khoá chỉ quyết định *ai được gọi `accept()` ngay
lúc này*, và chỉ giữ đúng bằng một lời gọi `accept()`. Phần đọc request, chạy
nghiệp vụ, truy vấn database, ghi phản hồi **không giữ khoá** nên vẫn song song
hoàn toàn - tức phần song song mà Python cần để vượt GIL không bị đụng tới.

## ⛔ Vì sao là MUTEX CÓ TÊN chứ không phải `multiprocessing.Lock`

Trong Xime, watchdog **giết** worker. Nên câu phải hỏi là: *worker bị giết đúng
lúc đang giữ khoá thì sao?*

| Loại khoá | Chủ bị giết |
|---|---|
| `multiprocessing.Lock` | ⛔ **không thả.** Khoá chết vĩnh viễn, cả cụm ngừng nhận kết nối |
| Mutex có tên của Windows | ✅ `WAIT_ABANDONED` **sau 0,00 giây**, người đợi kế tiếp nhận luôn quyền |

Lý do: `multiprocessing.Lock` trên Windows hiện thực bằng **semaphore**, mà
semaphore không có khái niệm chủ sở hữu nên cũng không có cơ chế thu hồi. Mutex
thì có chủ, và Windows biết chủ đã chết.

📌 Đây đúng là mối nguy mà nginx viện dẫn để **tắt** `accept_mutex` trên Win32:

    /* disable accept mutex on win32 as it may cause deadlock if
     * grabbed by a process which can't accept connections */

Họ nói đúng **về chính họ**: `ngx_shmtx` của nginx là một phép so-và-đổi nguyên
tử trên bộ nhớ chung, không có ngữ nghĩa chủ sở hữu ở tầng hệ điều hành. Trên
Unix họ vá bằng cách cho tiến trình cha tự gỡ khi thu xác con, và nhánh cứu đó
không có ở bản Windows. Thứ họ sợ lại đúng là thứ **Windows giải sẵn**, và ta
dùng được vì ta không phải viết một khoá dùng chung cho mọi nền tảng.

## ⚠ Rủi ro CÒN LẠI mà `WAIT_ABANDONED` không giải

Thu hồi chỉ xảy ra khi chủ **CHẾT**, không xảy ra khi chủ **KẸT**. Một worker bị
treo vì lý do khác (mã ứng dụng gọi thứ gì đó đồng bộ) mà đang giữ khoá thì cả
cụm ngừng accept cho tới khi nó chết hẳn hoặc watchdog giết nó.

Vì vậy luật của file này: **giữ khoá quanh ĐÚNG lời gọi `accept()`, không giữ
quanh bất cứ thứ gì khác.** Cửa sổ vài micro giây thì rủi ro trên gần bằng 0;
nới cửa sổ ra là dựng lại đúng nỗi lo của nginx.

⛔ Đặc biệt **không** giữ khoá quanh cả vòng lặp `for _ in range(backlog + 1)`
của `asyncio._accept_connection`: làm vậy là một tiến trình có thể ôm khoá suốt
101 lần accept trong khi hai tiến trình kia đứng chờ.
"""

from __future__ import annotations

import errno
import logging
import socket
import sys
import time
from typing import Any

_log = logging.getLogger("xime.bootstrap")

#: Không gian tên phiên đăng nhập, không phải `Global\` - tránh đòi quyền quản trị.
_TIEN_TO = "Local" + chr(92) + "xime-accept-"

#: Mốc lúc tiến trình này giành được khoá, `None` khi không giữ.
#:
#: ⭐ Đây là **hai phép gán thuộc tính** mỗi lần accept, không phải một phép đo.
#: Nó tồn tại để `_stall_report.py` phân biệt được *"kẹt và đang giữ khoá"*
#: (hại cả cụm, hạn chót 10 giây) với *"kẹt chỗ khác"* (chỉ hại chính nó, hạn
#: chót 60 giây). Không có nó thì hai ca đó nhìn giống hệt nhau từ bên ngoài.
_giu_tu: float | None = None


def dang_giu_khoa_tu() -> float | None:
    """Mốc `monotonic` lúc giành được khoá, `None` khi không giữ."""
    return _giu_tu


_WAIT_OBJECT_0 = 0x00000000
_WAIT_ABANDONED = 0x00000080
_WAIT_TIMEOUT = 0x00000102


class _KhoaCoTen:
    """Bọc một mutex có tên của Windows, dùng qua `ctypes`.

    ⚠ Mutex của Win32 thuộc về **THREAD**, không phải tiến trình, và nó **đệ quy
    với chính chủ**: cùng một thread lấy hai lần thì cả hai lần đều thành công.

    Hai hệ quả:

    1. Chỉ thread nào lấy mới nhả được. Ở đây cả hai đều xảy ra trong callback
       của event loop, tức cùng thread chính, nên ràng buộc đó tự thoả. **Đừng
       chuyển việc nhả khoá sang một thread khác.**
    2. ⚠ Khoá này **không** tuần tự hoá hai event loop chạy trong **cùng một
       tiến trình** trên cùng một thread. Hôm nay Xime không có hình dạng đó -
       mỗi tiến trình một event loop, một thread chính - nhưng ngày ai đó chạy
       hai loop trong một tiến trình thì bản vá này không che được họ.

    📌 Tính chất đệ quy đó đã treo cả bộ test một lần: bản đầu của
    `TestNhuongKhiNguoiKhacGiu` giữ khoá ngay trên thread chạy test rồi mong
    `accept()` bị nhường. Nó không nhường.
    """

    __slots__ = ("_h", "_k32", "_ten", "_da_bao_bo_roi")

    def __init__(self, ten: str) -> None:
        import ctypes
        import ctypes.wintypes as w

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.argtypes = [w.LPVOID, w.BOOL, w.LPCWSTR]
        k32.CreateMutexW.restype = w.HANDLE
        k32.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
        k32.WaitForSingleObject.restype = w.DWORD
        k32.ReleaseMutex.argtypes = [w.HANDLE]
        k32.ReleaseMutex.restype = w.BOOL

        # CreateMutexW vừa tạo vừa mở: tiến trình đầu tiên tạo, những tiến trình
        # sau nhận đúng object đó. Mutex không mang trạng thái nào cần giữ, nên
        # cả cụm chết rồi dựng lại thì tạo mới cũng đúng.
        h = k32.CreateMutexW(None, False, ten)
        if not h:
            import ctypes as _c

            raise OSError(_c.get_last_error(), f"CreateMutexW({ten!r}) that bai")
        self._h = h
        self._k32 = k32
        self._ten = ten
        self._da_bao_bo_roi = False

    def thu_lay(self) -> bool:
        """Lấy khoá nếu rảnh, KHÔNG chờ. `False` nghĩa là người khác đang giữ."""
        ma = self._k32.WaitForSingleObject(self._h, 0)
        if ma == _WAIT_OBJECT_0:
            return True
        if ma == _WAIT_ABANDONED:
            # Chủ trước chết giữa chừng. Windows trao quyền cho ta. An toàn ở đây
            # vì vùng găng không giữ bất biến nào - nó chỉ chứa một lời gọi
            # accept(), không có dữ liệu chung nào có thể dở dang.
            if not self._da_bao_bo_roi:
                self._da_bao_bo_roi = True
                _log.warning(
                    "accept lock %s: nguoi giu truoc chet giua chung, "
                    "Windows da trao quyen lai (WAIT_ABANDONED). Cum van chay.",
                    self._ten,
                )
            return True
        return False

    def nha(self) -> None:
        self._k32.ReleaseMutex(self._h)


class _SocketCoKhoa(socket.socket):
    """Socket lắng nghe mà `accept()` phải qua khoá.

    Không giành được khoá thì ném `BlockingIOError` - đúng ngoại lệ mà
    `asyncio._accept_connection` đã chuẩn bị sẵn đường thoát cho, nên nó trở về
    êm và vòng lặp đi làm việc khác.
    """

    _khoa: _KhoaCoTen

    def accept(self) -> Any:
        global _giu_tu
        if not self._khoa.thu_lay():
            raise BlockingIOError(
                errno.EWOULDBLOCK, "nguoi khac dang giu khoa accept"
            )
        _giu_tu = time.monotonic()
        try:
            return super().accept()
        finally:
            _giu_tu = None
            self._khoa.nha()


def boc_khoa_accept(sock: socket.socket | None) -> socket.socket | None:
    """Trả về socket đã bọc khoá, hoặc chính nó khi không cần bọc.

    Chỉ bọc khi **cả hai** điều kiện đúng: đang chạy Windows, và có socket kế
    thừa từ supervisor (tức nhiều tiến trình dùng chung một listener). Socket
    tiến trình tự bind thì không có ai để tranh, bọc chỉ tốn thêm.

    Không bọc được vì bất cứ lý do gì thì **trả lại socket gốc và ghi cảnh báo** -
    mất bản vá còn hơn không khởi động được.
    """
    if sock is None or sys.platform != "win32":
        return sock
    try:
        gia_dinh, kieu, giao_thuc = sock.family, sock.type, sock.proto
        try:
            dia_chi = sock.getsockname()
            nhan = "-".join(str(x) for x in dia_chi[:2])
        except OSError:
            nhan = f"fd{sock.fileno()}"
        khoa = _KhoaCoTen(_TIEN_TO + nhan)
        # detach() nhường quyền sở hữu fd cho object mới, không đóng fd.
        moi = _SocketCoKhoa(gia_dinh, kieu, giao_thuc, fileno=sock.detach())
        moi._khoa = khoa
        _log.info(
            "accept lock: bat cho listener %s - tren Windows nhieu tien trinh "
            "cung accept mot socket dung chung se treo event loop",
            nhan,
        )
        return moi
    except Exception:  # noqa: BLE001 - mat ban va con hon khong khoi dong duoc
        _log.warning(
            "accept lock: khong bat duoc, chay khong khoa. Tren Windows co the "
            "gap worker treo trong accept()",
            exc_info=True,
        )
        return sock
