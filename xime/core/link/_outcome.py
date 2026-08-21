"""Bốn kết cục của `ask`.

Bốn tình huống khiến người gọi làm **bốn việc khác nhau**, nên chúng phải là bốn
giá trị khác nhau trong hợp đồng - xem luật 03 của workspace. Gộp `Failed` vào
`NoAnswer` là nói *"không ai trả lời"* về một ca **đã có người trả lời**, và bên
gọi sẽ đi sửa cấu hình trong khi thứ hỏng nằm ở nghiệp vụ.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Done:
    """Handler đã nhận và đã trả lời.

    ⚠ `Done` nghĩa là *"handler đã nhận và trả lời"*, **KHÔNG** nhất thiết là
    *"việc đã làm xong"*. Một handler nhét lệnh vào hàng đợi rồi trả `b"da nhan"`
    thì `Done` mang nghĩa *đã nhận*. Ngữ nghĩa đó do ứng dụng định nghĩa;
    framework không hứa hộ.
    """

    value: bytes


@dataclass(frozen=True)
class NoOwner:
    """KHÔNG tiến trình nào nhận - đây là lỗi CẤU HÌNH, đừng thử lại.

    Không ai giữ khoá đó: hoặc khối cấu hình phân việc còn thiếu, hoặc khoá bị
    gõ sai. Thử lại sẽ cho đúng kết quả này mãi mãi.
    """


@dataclass(frozen=True)
class NoAnswer:
    """Có đích nhưng quá hạn - xem tiến trình kia còn sống không.

    Khác `NoOwner` ở chỗ có người đã nhận dòng này. Nó chậm, hoặc nó treo.
    """


@dataclass(frozen=True)
class Failed:
    """Có người nhận, và người đó HỎNG - lỗi nghiệp vụ.

    `detail` mang tên lớp lỗi cộng `str(exc)`, cắt cứng độ dài. Cố ý **không**
    chở traceback: người hỏi ở tiến trình khác không debug được bằng traceback
    của tiến trình kia - họ không có ngữ cảnh, không có biến. Traceback đầy đủ
    được log **tại tiến trình bị lỗi**, nơi có đủ mọi thứ.
    """

    detail: str


Outcome = Done | NoOwner | NoAnswer | Failed
