"""Ngoại lệ của bus liên tiến trình.

⚠ Module lá: chỉ import `XimeException`. Nhờ vậy `_layout.py` (không import gì
của bus) và `_link.py` (import `_layout`) cùng lấy được lớp nền mà không tạo
vòng import.
"""

from __future__ import annotations

from xime.core.exception.framework import XimeException


class LinkError(XimeException):
    """Lỗi dùng sai bus - kênh không tồn tại, payload quá cỡ, gửi khi đã đóng."""


class LinkLayoutMismatch(LinkError):
    """Vùng nhớ chung không mang đúng khuôn bảng tiến trình này chờ đợi.

    ⚠⚠ **Tên có tiền tố `Link` là cố ý, đừng rút gọn lại thành `LayoutMismatch`.**
    Kho tham chiếu có một lỗi cùng bản chất và trước 0.8.0 **cả hai cùng tên**,
    cùng là lớp con trực tiếp của `Exception`, ở hai package công khai:

        from xime.core.link import LayoutMismatch
        from xime.core.refdata import LayoutMismatch   # che mất cái trên, im lặng

    Sau hai dòng đó, `except LayoutMismatch:` bắt đúng **một** trong hai, và
    cái còn lại đi xuyên qua. Không cảnh báo, không lỗi lúc import. Đây là
    luật 03 ở tầng **từ vựng**: một tên mang hai nghĩa.

    Kèm một chỗ hỏng thứ hai đã sửa cùng lúc: bản cũ kế thừa thẳng `Exception`,
    nên `except LinkError:` - lớp nền của chính package này - **không bắt được
    nó**, và `except XimeException:` cũng không.
    """
