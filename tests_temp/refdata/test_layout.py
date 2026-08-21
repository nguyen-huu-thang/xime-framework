"""Bố cục byte - thứ **mọi tiến trình phải đọc giống hệt nhau**.

Một byte lệch ở đây thì hai tiến trình nhìn cùng một vùng nhớ mà thấy hai bảng
khác nhau, và **không có lỗi nào phát ra**. Đó là lý do bố cục có test riêng
thay vì chỉ được đo gián tiếp qua `read()`/`publish()`.
"""

from __future__ import annotations

import pytest

from xime.core.refdata._layout import (
    HEADER_BYTES,
    MAGIC,
    NEVER_PUBLISHED,
    NO_WRITER,
    VERSION,
    RefDataLayoutMismatch,
    RefDataLayout,
)


def _fresh(max_bytes: int = 64) -> tuple[RefDataLayout, memoryview]:
    layout = RefDataLayout(max_bytes)
    buf = memoryview(bytearray(layout.total_bytes))
    layout.write_header(buf)
    return layout, buf


class TestShape:
    def test_the_block_is_header_plus_TWO_slots(self) -> None:
        layout = RefDataLayout(1000)
        assert layout.total_bytes == HEADER_BYTES + 2000

    def test_both_slots_start_on_an_8_byte_boundary(self) -> None:
        # Không phải chuyện thẩm mỹ: dữ liệu bắt đầu lệch căn chỉnh làm chậm
        # mọi lần copy, và với một bảng đọc trên đường nóng thì đó là phí trả
        # mãi mãi cho một thứ chỉ phải tính đúng một lần.
        layout = RefDataLayout(64)
        assert layout.slot_a_offset % 8 == 0
        assert layout.slot_b_offset % 8 == 0

    def test_max_bytes_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="max_bytes"):
            RefDataLayout(0)


class TestFreshHeader:
    def test_a_new_block_says_NOBODY_HAS_PUBLISHED(self) -> None:
        layout, buf = _fresh()
        assert layout.read_generation(buf) == NEVER_PUBLISHED

    def test_a_new_block_has_no_writer(self) -> None:
        # 255 nghĩa "chưa ai giữ quyền ghi" - cùng quy ước NO_TAKER của bus.
        layout, buf = _fresh()
        assert layout.read_writer(buf) == NO_WRITER

    def test_a_new_block_verifies_against_itself(self) -> None:
        layout, buf = _fresh()
        layout.verify_header(buf, "x")  # không ném


class TestVerifyHeader:
    """Ba cách một vùng nhớ có thể **không phải** thứ ta đang chờ đợi.

    Ca thật mà chúng chặn: hai ứng dụng Xime chạy cùng máy, cùng đặt tên một
    bảng là `jwt-keys`. Không có phép kiểm này thì chúng attach vào nhau và đọc
    rác của nhau, mà triệu chứng chỉ là *"thỉnh thoảng decode hỏng"*.
    """

    def test_foreign_memory_is_rejected(self) -> None:
        layout = RefDataLayout(64)
        buf = memoryview(bytearray(layout.total_bytes))
        with pytest.raises(RefDataLayoutMismatch, match="does not carry a Xime"):
            layout.verify_header(buf, "jwt-keys")

    def test_a_different_layout_version_is_rejected(self) -> None:
        layout, buf = _fresh()
        buf[4:6] = (VERSION + 1).to_bytes(2, "little")
        with pytest.raises(RefDataLayoutMismatch, match="layout version"):
            layout.verify_header(buf, "jwt-keys")

    def test_a_different_max_bytes_is_rejected(self) -> None:
        writer = RefDataLayout(64)
        buf = memoryview(bytearray(writer.total_bytes))
        writer.write_header(buf)
        with pytest.raises(RefDataLayoutMismatch, match="max_bytes=64"):
            RefDataLayout(128).verify_header(buf, "jwt-keys")

    def test_the_magic_is_not_the_one_the_bus_uses(self) -> None:
        # Hai họ vùng nhớ khác nhau trên cùng một máy. Nếu magic trùng thì một
        # kênh bus attach được vào một bảng tham chiếu và ngược lại, rồi đọc
        # rác của nhau mà mọi phép kiểm đều xanh.
        from xime.core.link._layout import MAGIC as LINK_MAGIC

        assert MAGIC != LINK_MAGIC


class TestSlots:
    def test_writing_one_slot_does_not_touch_the_other(self) -> None:
        # Đây là toàn bộ lý do có hai ô: người ghi dựng trọn bản mới vào ô
        # KHÔNG ai đang đọc, rồi mới đổi con trỏ.
        layout, buf = _fresh()
        layout.write_slot(buf, 0, b"cu")
        layout.write_length(buf, 0, 2)
        layout.write_slot(buf, 1, b"moi hon")
        layout.write_length(buf, 1, 7)
        assert bytes(layout.slot_view(buf, 0)) == b"cu"
        assert bytes(layout.slot_view(buf, 1)) == b"moi hon"

    def test_lengths_are_tracked_per_slot(self) -> None:
        layout, buf = _fresh()
        layout.write_length(buf, 0, 5)
        layout.write_length(buf, 1, 9)
        assert layout.read_length(buf, 0) == 5
        assert layout.read_length(buf, 1) == 9

    def test_the_pointer_is_exactly_one_byte(self) -> None:
        # Ghi một byte là nguyên tử trên mọi kiến trúc thực tế, nên người đọc
        # không bao giờ thấy một giá trị nửa vời. Đừng đổi nó thành int nhiều
        # byte cho gọn.
        from xime.core.refdata._layout import POINTER_OFFSET, WRITER_OFFSET

        assert WRITER_OFFSET - POINTER_OFFSET == 1
