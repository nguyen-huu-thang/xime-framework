"""Mốc thời gian của lần import đầu tiên, và **phép dò thứ nhất** của luật
*"code ở mức module phải nhẹ"*.

Mọi thứ nằm ngoài `if __name__ == "__main__":` chạy **`N+1`** lần khi ứng dụng
có `N` tiến trình - tiến trình cha cũng chạy lại chính `main.py` rồi mới rẽ
nhánh ở `share_load()`. Nên một kết nối mở ở mức module là `N+1` kết nối, và
**không gì báo**.

`share_load()` là điểm đầu tiên framework giành lại quyền điều khiển sau khi
code mức module chạy xong, nên nó là chỗ duy nhất đo được khoảng đó mà không
cần biết bên trong có gì.

⚠ **Phép dò này bắt cái ĐẮT, không bắt cái SAI.** Một kết nối tới `localhost`
mất vài mili giây, nằm dưới mọi ngưỡng hợp lý. Chỗ mù đó do phép dò thứ hai
(`xime check module-level`) bù, và **hai cái không thay thế nhau**: cái này đo
*hậu quả* mà không biết nguyên nhân, cái kia tìm *nguyên nhân* theo tên mà
không thấy hậu quả.

📌 `IMPORT_MARK` dưới đây là **một giá trị không tất định ở mức module** - đúng
thứ luật cấm ở mã ứng dụng. Nó hợp lệ ở đây vì đó chính là điều đang cần: mỗi
tiến trình đo **của chính nó**, và không ai đọc nó như một hằng số dùng chung.
"""

from __future__ import annotations

import logging
import time

# Thời điểm dòng mã Xime đầu tiên chạy trong tiến trình này. Module này được
# import ở dòng đầu của `xime/__init__.py`, mà mọi `import xime.X` đều kéo
# `xime/__init__.py` chạy trước - nên mốc này luôn là sớm nhất framework thấy được.
IMPORT_MARK = time.perf_counter()

# ⭐ Ngưỡng ĐO RA, không phải đoán. Kế hoạch thi công đề nghị 1 giây; đo ngày
# 2026-08-20 trên hai ứng dụng thật và **lành mạnh** (`linh-kien-dien-tu`
# 0,996s · `shop-hoa-qua-tang` 1,03-1,06s qua ba lần chạy) thì cả hai đều vượt
# ngưỡng đó. Riêng phần import của framework (`xime` + web + grpc + sqlalchemy)
# đã là ~0,75s trên máy dev này.
#
# Một phép dò kêu oan là một phép dò sẽ bị tắt, nên ngưỡng lấy ~3x số đo của
# ứng dụng lành mạnh: đủ chỗ cho một máy chậm hơn, mà vẫn bắt được thứ nó sinh
# ra để bắt.
MODULE_LEVEL_BUDGET_SECONDS = 3.0

_log = logging.getLogger("xime.bootstrap")


def module_level_seconds(now: float | None = None) -> float:
    """Số giây đã trôi từ dòng Xime đầu tiên tới lúc gọi hàm này."""
    return (time.perf_counter() if now is None else now) - IMPORT_MARK


def warn_if_module_level_is_heavy(
    seconds: float,
    process_count: int,
    *,
    budget: float = MODULE_LEVEL_BUDGET_SECONDS,
) -> bool:
    """Kêu khi code mức module tốn quá `budget` giây. Trả về *đã kêu hay chưa*.

    ⚠ Gọi hàm này **sau** khi logging đã được cấu hình và **sau** khi biết số
    tiến trình - nếu không thì hoặc cảnh báo rơi vào hư không, hoặc nó không
    nói được phần đắt giá nhất: con số này bị **nhân lên**.

    Chỉ tiến trình cha gọi, nên cả cụm chỉ có **một** dòng cảnh báo.
    """
    if seconds <= budget:
        return False

    total = seconds * (process_count + 1)
    _log.warning(
        "\nModule-Level Code Is Heavy\n"
        "  Measured: %.1fs from the first Xime import to share_load()\n"
        "  Cost    : x%d (parent + %d worker(s)) = %.1fs spent before serving\n"
        "  Detail  : module-level code runs once per process. Move connections,\n"
        "            file reads and network calls into post_construct(), run_once()\n"
        "            or an adapter - the module level is for DECLARING only.\n"
        "  See     : docs/multi-process.md",
        seconds,
        process_count + 1,
        process_count,
        total,
    )
    return True
