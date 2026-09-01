"""Nền đa tiến trình dùng chung: ngữ cảnh sinh con, và vùng nhớ chung.

Ba thứ mà `core/link`, `core/refdata` và `core/bootstrap` đều cần - cách sinh
tiến trình (`MP_CONTEXT`), cách mở một vùng nhớ chung (`view_of`), cách **ghi**
vào nó (`ghi_o`) - và **không cái nào trong ba nên phải import cái kia để có**.
Module này chỉ phụ thuộc thư viện chuẩn, nên nó là chỗ duy nhất cả ba đi tới
được mà không tạo cạnh mới giữa các hệ thống con.

📌 Luật của gói chứa nó (ai được vào đây, ai không) nằm ở `__init__.py`.

📌 `view_of` từng nằm ở `core/link/_cleanup.py` trong vài giờ ngày 2026-08-21,
và đó là một sai lầm bị chính lượt rà cuối bắt được: nó buộc `core/refdata`
import một module **riêng tư** của `core/link` - một cạnh phụ thuộc chưa từng
tồn tại giữa hai hệ thống con cố ý độc lập, dựng lên chỉ để dùng một hàm ba
dòng.

⛔ Every ``multiprocessing`` primitive that has to cross a process boundary MUST
be created from ``MP_CONTEXT``. Never from the bare ``multiprocessing.Semaphore``
/ ``Lock`` / ``Event`` helpers.
⛔ Mọi nguyên thủy ``multiprocessing`` phải đi qua ranh giới tiến trình đều BẮT
BUỘC tạo từ ``MP_CONTEXT``. Đừng bao giờ dùng thẳng ``multiprocessing.Semaphore``
/ ``Lock`` / ``Event``.

Vì sao đây là luật chứ không phải lời khuyên, và vì sao Windows không thể phát
hiện việc vi phạm nó:

``multiprocessing`` trộn hai ngữ cảnh khác nhau thì **ném ``RuntimeError``**::

    RuntimeError: A SemLock created in a fork context is being shared with a
    process in a spawn context. This is not supported.

Mà ngữ cảnh mặc định **khác nhau theo hệ điều hành**:

===============  =========================  =====================================
Hệ điều hành     Ngữ cảnh mặc định          Trùng với ``spawn`` của framework?
===============  =========================  =====================================
Windows          ``spawn`` (duy nhất)       **có** - trùng một cách tình cờ
Linux, Python    ``fork``                   không
3.13 trở xuống
Linux, Python    ``forkserver``             không
3.14 trở lên
macOS            ``spawn``                  có
===============  =========================  =====================================

Nghĩa là một dòng ``Semaphore(0)`` viết bằng ngữ cảnh mặc định **chạy hoàn hảo
trên máy phát triển Windows và chết trên máy chạy thật Linux**, và không phép đo
nào trên Windows có thể thấy điều đó - điều kiện gây lỗi không tồn tại ở đó.

📌 Đây không phải giả thuyết. Ngày 2026-08-21, phiên kiểm toán Linux đo được
**26 test đỏ** ở đúng vùng đa tiến trình, trong khi cùng bộ test cho **0 đỏ**
trên Windows. Nguyên nhân là đúng một dòng ``from multiprocessing import
Semaphore`` trong ``core/link/_link.py`` - chuông tạo bằng ngữ cảnh mặc định,
còn ``Supervisor`` sinh con bằng ``spawn``. Xem ``.claude/docs/kiem-toan/
0.8-kiem-toan-toan-dien.md`` mục **C4**.

⭐ Gốc của lỗi không phải chọn sai ngữ cảnh, mà là **HAI CHỖ CÙNG QUYẾT ĐỊNH MỘT
THỨ mà không biết nhau**. Module này tồn tại để chỉ còn một chỗ quyết định. Thêm
một lời gọi ``get_context`` thứ hai ở bất kỳ đâu là dựng lại đúng cái lỗi vừa vá
- và có test canh ``tests_temp/processes/test_mp_context.py`` bắt việc đó.

Vì sao là ``spawn`` chứ không phải ``fork``: con phải nạp lại ``main.py`` để
``import config`` và ``app.use(...)`` chạy tự nhiên trong nó. ``fork`` sao chép
bộ nhớ của cha, mà cha thì **không dựng DI**, nên con sẽ thừa hưởng một trạng
thái dở dang. Lý do đầy đủ ở ``core/bootstrap/_supervisor.py`` và
``.claude/docs/thiet-ke/10-da-tien-trinh.md``.
"""

from __future__ import annotations

import multiprocessing
import struct
from typing import Any

# Not a function: resolving the context once, at import time, is what makes it a
# single source of truth instead of a convention people have to remember.
# Không phải hàm: phân giải một lần lúc import chính là thứ biến nó thành nguồn
# sự thật duy nhất, thay vì một quy ước mà ai cũng phải nhớ.
MP_CONTEXT = multiprocessing.get_context("spawn")


def view_of(block: Any) -> memoryview:
    """Vùng nhớ của `block`, đã thu hẹp kiểu.

    `SharedMemory.buf` được typeshed khai là `memoryview | None` vì nó thành
    `None` sau `close()`. Đúng, nhưng mọi chỗ dùng trong framework đều nằm giữa
    lúc mở và lúc đóng - nên thay vì rắc hai chục lời `assert` vào các đường
    nóng, thu hẹp MỘT LẦN ở chỗ nhận, đúng nơi câu "đã mở chưa" còn trả lời
    được.

    Ném `RuntimeError` thay vì `assert`: `python -O` bỏ `assert`, và một vùng
    nhớ đã đóng mà vẫn bị ghi vào là thứ phải nổ ở mọi chế độ.
    """
    buf = block.buf
    if buf is None:
        raise RuntimeError(
            f"shared memory block {getattr(block, 'name', '?')!r} is closed - "
            f"nothing may read or write it any more"
        )
    return buf


def ghi_o(
    view: memoryview, offset: int, mau: struct.Struct, *gia_tri: Any
) -> None:
    """Ghi một bản ghi vào bộ nhớ chung. **Dùng cái này, đừng dùng `pack_into`.**

    ⛔ `struct.pack_into` **xoá vùng đích về 0 trước khi ghi** - nó phải làm vậy
    để byte đệm luôn bằng 0. Trong một tiến trình thì GIL che mất cửa sổ ấy;
    giữa hai tiến trình thì **không có gì che**, và người đọc rơi vào đó sẽ thấy
    một bản ghi toàn số 0.

    Đo được 2026-09-01, hai tiến trình trên một vùng nhớ chung, 34,6 triệu lượt
    đọc::

        ghi bằng `pack_into`  ->  1.658.361 lượt đọc ra TOÀN SỐ 0  (4,79%)
        ghi bằng hàm này      ->  0

    Vì sao nó là lỗi chứ không phải chuyện lý thuyết: **số 0 hầu như luôn là một
    giá trị mang nghĩa riêng**, và nghĩa đó thường là *"chưa có gì"*::

        `_watchdog.NEVER = 0.0`            -> "con này chưa bao giờ vỗ nhịp"
        `_refdata.NEVER_PUBLISHED = 0`     -> "bảng này chưa ai publish"

    Cả hai đều dẫn tới một hành động **sai và không thể lấy lại**: cha giết một
    tiến trình đang khoẻ; một request hợp lệ nhận 401 vì bảng khoá JWT bỗng
    trông như rỗng. Không exception, không log, không test đỏ - đúng thứ
    [luật 03](../../../.claude/rules/03-mot-gia-tri-mot-nghia.md) gọi tên: một
    giá trị mang hai nghĩa, ở đây là *"chưa có gì"* và *"đang ghi dở"*.

    Hàm này chép đè mà **không xoá trước**, nên trạng thái trung gian tệ nhất là
    *nửa cũ nửa mới* - cả hai nửa đều là giá trị hợp lệ, và lượt đọc sau lấy lại
    được. Đó đúng là mức bảo đảm mà `core/link`, `core/refdata` và `_watchdog`
    vẫn luôn khai trong docstring của chúng.

    ⚠ Nó **không** làm phép ghi thành nguyên tử, và không định làm vậy. Nó chỉ
    bỏ đi một trạng thái trung gian **giả** mà `pack_into` tự sinh ra.

    ⛔ Chỗ duy nhất còn được dùng `pack_into` là lúc **dựng** một vùng nhớ mới,
    trước khi tiến trình nào kịp attach - ở đó không có ai để mà đọc dở. Có test
    canh đếm số lời gọi `pack_into` còn lại: `tests_temp/mp/test_ghi_o.py`.
    """
    view[offset:offset + mau.size] = mau.pack(*gia_tri)


__all__ = ["MP_CONTEXT", "ghi_o", "view_of"]
