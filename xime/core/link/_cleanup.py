"""Dọn vùng nhớ mồ côi của những lần chạy trước.

Ba lớp, và mỗi lớp che một cách tắt khác nhau:

| Lớp | Che gì |
|---|---|
| `unlink()` trong `finally` (ở `ProcessLink.close`) | tắt êm, `Ctrl+C`, `SIGTERM`, mọi exception - **99% số lần** |
| Hàm ở file này, chạy lúc khởi động | `kill -9`, mất điện |
| `resource_tracker` của Python | có sẵn, không phải làm gì |

⚠ **Chỉ Linux mới có chuyện này.** Trên Windows vùng nhớ biến mất khi handle
cuối đóng; trên Linux nó là một file thật trong `/dev/shm`, mà `/dev/shm` là
RAM - rác ở đó là RAM không ai đòi lại.

⚠ Đừng tắt cảnh báo `leaked shared_memory objects` của `resource_tracker`: nó
đang làm đúng việc của nó.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_log = logging.getLogger("xime.link")

# Cả BA họ vùng nhớ chung của framework, không chỉ bus.
#
# `refdata/_arena.py` từng ghi chú thích *"cùng khuôn với bus để một lần dọn
# rác nhìn thấy cả hai họ"* - câu đó mô tả một ý định chưa bao giờ thành mã:
# hàm này chỉ lọc `xime-link-`, nên `xime-ref-` và `xime-beat-` **không bao giờ
# được dọn**. Phát hiện T4 của kiểm toán 0.8.
_PREFIXES = ("xime-link-", "xime-ref-", "xime-beat-")
_PREFIX = _PREFIXES[0]  # giữ tên cũ cho test hiện có
_SHM_DIR = Path("/dev/shm")


def sweep_orphans() -> int:
    """Xoá vùng nhớ của những tiến trình gốc đã chết. Trả về số vùng đã xoá.

    Tên vùng mang pid của tiến trình đã tạo nó, nên câu hỏi *"còn ai giữ cái này
    không"* trả lời được bằng `os.kill(pid, 0)` - gửi tín hiệu số 0 không gửi gì
    cả, nó chỉ HỎI tiến trình còn sống không.

    ⚠ Hệ điều hành **tái dùng pid**, nên thỉnh thoảng một vùng rác sẽ sống thêm
    một vòng vì pid của nó tình cờ trùng một tiến trình đang chạy. Đừng cố giải
    chính xác chuyện đó - giá không xứng với một file vài megabyte trong RAM.
    """
    if sys.platform == "win32" or not _SHM_DIR.is_dir():
        return 0

    removed = 0
    for entry in _SHM_DIR.iterdir():
        if not entry.name.startswith(_PREFIXES):
            continue
        pid = _owner_pid(entry.name)
        if pid is None or _alive(pid):
            continue
        try:
            entry.unlink()
            removed += 1
        except OSError:
            # Người khác vừa xoá, hoặc ta không có quyền - cả hai đều không phải
            # việc phải chữa ở đây.
            continue
    if removed:
        _log.info("link: removed %d orphaned shared-memory block(s)", removed)
    return removed


def _owner_pid(name: str) -> int | None:
    """`xime-<ho>-<pid>-<random>[-<duoi>]` -> pid. Cả ba họ cùng khuôn này."""
    for tien_to in _PREFIXES:
        if name.startswith(tien_to):
            break
    else:
        return None
    parts = name[len(tien_to) :].split("-", 1)
    if not parts or not parts[0].isdigit():
        return None
    return int(parts[0])


def _alive(pid: int) -> bool:
    """Tiến trình `pid` còn sống không. Tín hiệu 0 không gửi gì cả, nó chỉ HỎI.

    ⚠ Bắt `OSError` chứ không chỉ `ProcessLookupError`, và đó là kết quả của một
    phép đo chứ không phải phòng xa: trên POSIX một pid đã chết cho
    `ProcessLookupError`, nhưng trên **Windows** nó cho `OSError [WinError 87]
    The parameter is incorrect` - không phải lớp con nào của `ProcessLookupError`.
    Bắt hẹp thì hàm này ném lỗi thay vì trả lời, và bước dọn rác chết theo.

    ✅ Đo cùng lúc, vì nó là thứ đáng sợ hơn: `os.kill(pid, 0)` trên Windows
    **KHÔNG giết tiến trình đích** - một tiến trình con vẫn sống nguyên sau lời
    gọi. (Với tín hiệu khác 0 thì CPython ánh xạ `os.kill` thành
    `TerminateProcess`, nên chỗ này chỉ an toàn nhờ đúng con số 0.)
    """
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True  # tồn tại, chỉ là của người dùng khác
    except OSError:
        return False
    return True
