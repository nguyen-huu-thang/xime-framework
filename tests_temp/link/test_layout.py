"""Bố cục byte của một kênh.

Đây là thứ **mọi tiến trình phải đọc giống hệt nhau**: một byte lệch thì hai
tiến trình nhìn cùng một vùng nhớ mà thấy hai bảng khác nhau, và **không có lỗi
nào phát ra**. Nên nó có bộ test riêng, tách khỏi phần cơ chế.
"""

from __future__ import annotations

import pytest

from xime.core.link._layout import (
    ROW_HEADER_BYTES,
    ChannelLayout,
    LinkLayoutMismatch,
)


def _buffer(layout: ChannelLayout) -> memoryview:
    return memoryview(bytearray(layout.total_bytes))


class TestGeometry:
    def test_total_rows_is_rows_times_processes(self):
        """Mỗi tiến trình có VÙNG GHI riêng, nên tổng dòng là tích chứ không phải `rows`."""
        layout = ChannelLayout(rows_per_writer=256, payload_bytes=512, process_count=4)
        assert layout.total_rows == 1024

    def test_row_header_is_72_bytes_and_payload_is_aligned(self):
        """Header dòng căn 8 để hai trường 8 byte đọc được không lệch.

        Nó cũng khiến payload bắt đầu ở bội số của 8 - đổi con số này là đổi
        cách mọi tiến trình đọc, nên nó được chốt bằng test chứ không bằng trí
        nhớ.
        """
        assert ROW_HEADER_BYTES == 72
        assert ROW_HEADER_BYTES % 8 == 0

    def test_each_writer_owns_a_contiguous_range_of_rows(self):
        layout = ChannelLayout(4, 32, 3)
        assert list(layout.rows_of(0)) == [0, 1, 2, 3]
        assert list(layout.rows_of(1)) == [4, 5, 6, 7]
        assert list(layout.rows_of(2)) == [8, 9, 10, 11]

    def test_writer_ranges_never_overlap(self):
        layout = ChannelLayout(7, 32, 5)
        seen: set[int] = set()
        for writer in range(5):
            rows = set(layout.rows_of(writer))
            assert not (rows & seen), "hai người ghi không được chung dòng nào"
            seen |= rows
        assert len(seen) == layout.total_rows

    def test_regions_and_bitmap_do_not_overlap(self):
        layout = ChannelLayout(8, 64, 4)
        assert layout.bitmap_offset < layout.rows_offset
        bitmap_end = layout.bitmap_offset + layout.bitmap_stride * 4
        assert bitmap_end <= layout.rows_offset
        assert layout.row_offset(layout.total_rows - 1) + layout.row_bytes <= layout.total_bytes


class TestBitmap:
    def test_a_bit_belongs_to_exactly_one_reader_and_row(self):
        layout = ChannelLayout(8, 32, 4)
        buf = _buffer(layout)
        layout.set_bit(buf, reader=2, row=17)

        assert layout.test_bit(buf, 2, 17)
        assert not layout.test_bit(buf, 1, 17)
        assert not layout.test_bit(buf, 2, 18)

    def test_clearing_leaves_the_neighbours_alone(self):
        layout = ChannelLayout(8, 32, 4)
        buf = _buffer(layout)
        for row in (16, 17, 18):
            layout.set_bit(buf, 1, row)

        layout.clear_bit(buf, 1, 17)

        assert layout.test_bit(buf, 1, 16)
        assert not layout.test_bit(buf, 1, 17)
        assert layout.test_bit(buf, 1, 18)

    def test_unread_rows_is_empty_when_nothing_is_pending(self):
        """Ca THƯỜNG LỆ phải rẻ: một tiến trình bị đánh thức giả hỏi câu này liên tục."""
        layout = ChannelLayout(128, 32, 4)
        assert layout.unread_rows(_buffer(layout), reader=0) == []

    def test_unread_rows_returns_them_in_ascending_order(self):
        layout = ChannelLayout(128, 32, 4)
        buf = _buffer(layout)
        for row in (5, 200, 3, 511):
            layout.set_bit(buf, 3, row)

        assert layout.unread_rows(buf, 3) == [3, 5, 200, 511]

    def test_bands_are_independent_across_readers(self):
        """Bitmap xếp thành DÃY LIỀN NHAU, mỗi tiến trình một dãy.

        Nhờ vậy một tiến trình thức dậy chỉ đọc dãy của riêng nó rồi so với 0 -
        một phép so, không phải quét cả bảng.
        """
        layout = ChannelLayout(64, 32, 4)
        buf = _buffer(layout)
        layout.set_bit(buf, 0, 10)

        assert layout.unread_rows(buf, 0) == [10]
        assert layout.unread_rows(buf, 1) == []
        assert layout.unread_rows(buf, 2) == []
        assert layout.unread_rows(buf, 3) == []

    def test_any_unread_lists_every_reader_still_holding_the_row(self):
        layout = ChannelLayout(8, 32, 4)
        buf = _buffer(layout)
        layout.set_bit(buf, 1, 5)
        layout.set_bit(buf, 3, 5)

        assert layout.any_unread(buf, 5) == [1, 3]


class TestFields:
    def test_key_round_trips_and_is_padded(self):
        layout = ChannelLayout(4, 32, 2)
        buf = _buffer(layout)
        layout.write_key(buf, 1, "BT-01")
        assert layout.read_key(buf, 1) == "BT-01"

    def test_key_may_be_empty(self):
        layout = ChannelLayout(4, 32, 2)
        buf = _buffer(layout)
        layout.write_key(buf, 0, "")
        assert layout.read_key(buf, 0) == ""

    def test_payload_round_trips_at_its_declared_length(self):
        layout = ChannelLayout(4, 32, 2)
        buf = _buffer(layout)
        layout.write_payload(buf, 2, b"xin chao")
        layout.write_length(buf, 2, len(b"xin chao"))
        assert layout.read_payload(buf, 2) == b"xin chao"

    def test_a_shorter_payload_does_not_leak_the_previous_one(self):
        """Dòng bị đè: đọc phải theo `do_dai` mới, không theo nội dung còn sót."""
        layout = ChannelLayout(4, 32, 2)
        buf = _buffer(layout)
        layout.write_payload(buf, 0, b"cai nay dai hon nhieu")
        layout.write_length(buf, 0, 21)

        layout.write_payload(buf, 0, b"ngan")
        layout.write_length(buf, 0, 4)

        assert layout.read_payload(buf, 0) == b"ngan"

    def test_writing_one_row_never_touches_its_neighbours(self):
        layout = ChannelLayout(4, 32, 2)
        buf = _buffer(layout)
        layout.write_payload(buf, 1, b"A" * 32)
        layout.write_length(buf, 1, 32)
        layout.write_key(buf, 1, "row-one")

        layout.write_payload(buf, 2, b"B" * 32)
        layout.write_length(buf, 2, 32)

        assert layout.read_payload(buf, 1) == b"A" * 32
        assert layout.read_key(buf, 1) == "row-one"


class TestHeader:
    def test_a_fresh_block_verifies_against_its_own_layout(self):
        layout = ChannelLayout(8, 64, 3)
        buf = _buffer(layout)
        layout.write_header(buf, )
        layout.verify_header(buf, "fieldbus")

    def test_attaching_with_a_different_shape_is_refused(self):
        """Ca thật: hai ứng dụng Xime cùng máy, cùng đặt tên kênh "fieldbus".

        Không có phép kiểm này thì chúng attach vào nhau và đọc rác của nhau, mà
        triệu chứng chỉ là "thỉnh thoảng nhận được tin lạ".
        """
        written = ChannelLayout(8, 64, 3)
        buf = _buffer(written)
        written.write_header(buf)

        expected = ChannelLayout(8, 128, 3)  # cùng tên kênh, khác cỡ payload
        with pytest.raises(LinkLayoutMismatch, match="payload=64"):
            expected.verify_header(buf, "fieldbus")

    def test_a_block_that_is_not_ours_is_refused(self):
        layout = ChannelLayout(8, 64, 3)
        buf = _buffer(layout)
        buf[0:4] = b"JUNK"
        with pytest.raises(LinkLayoutMismatch, match="does not carry a Xime link"):
            layout.verify_header(buf, "fieldbus")

    def test_missed_counters_start_at_zero_and_accumulate(self):
        layout = ChannelLayout(8, 64, 3)
        buf = _buffer(layout)
        layout.write_header(buf)

        assert layout.read_missed(buf, 1) == 0
        layout.bump_missed(buf, 1)
        layout.bump_missed(buf, 1)
        assert layout.read_missed(buf, 1) == 2
        assert layout.read_missed(buf, 0) == 0

    def test_sequence_numbers_increase(self):
        layout = ChannelLayout(8, 64, 2)
        buf = _buffer(layout)
        layout.write_header(buf)

        first = layout.next_sequence(buf)
        second = layout.next_sequence(buf)
        assert second > first
