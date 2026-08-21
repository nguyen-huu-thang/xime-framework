"""Read a POSIX file mode out of YAML, where ``0600`` is a trap.

Đọc quyền tệp POSIX từ YAML, chỗ mà ``0600`` là một cái bẫy.

YAML has no octal literal in the shape people expect. ``file_mode: 0600``
parses as the **decimal** integer 600, which as a mode means ``0o1130`` - a
nonsense the operator never intended, and one that no error message would ever
mention because 600 is a perfectly valid integer.
YAML không có literal bát phân như người ta tưởng. ``file_mode: 0600`` ra số
600 **hệ mười**, mà đọc như quyền tệp thì là ``0o1130`` - một thứ vô nghĩa mà
người vận hành không bao giờ định viết, và không thông báo lỗi nào nhắc tới vì
600 là một số nguyên hoàn toàn hợp lệ.

Nên quy ước ở đây: **chuỗi đọc theo bát phân, số nguyên giữ nguyên**. Nhờ vậy
``"0600"`` trong YAML và ``0o600`` trong file cấu hình Python cùng ra một giá
trị, còn ``0600`` không dấu nháy thì ra một con số sai một cách nhìn thấy được
thay vì sai âm thầm.

⭐ Vì sao nằm ở ``core/config/`` chứ không nằm trong một starter: hai starter
(``localfs`` và ``lmdb``) đều cần nó, và **hai chỗ cùng quyết định một thứ thì
sớm muộn lệch nhau**. Đó đúng là gốc của lỗi C4 mà 0.8 vừa vá ở tầng ngữ cảnh
tiến trình; không có lý do gì dựng lại nó ở tầng quyền tệp.
"""

from __future__ import annotations

__all__ = ["parse_mode"]


def parse_mode(value: object, default: int, where: str) -> int:
    """Return a POSIX mode. ``where`` names the config key, for the error text."""
    if value is None:
        return default
    if isinstance(value, bool):  # bool là subclass của int - từ chối tường minh
        raise ValueError(f"{where} must be a string or int, got {value!r}")
    if isinstance(value, str):
        return int(value, 8)
    if isinstance(value, int):
        return value
    raise ValueError(f"{where} must be a string or int, got {value!r}")
