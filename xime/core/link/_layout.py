"""Bố cục byte của một kênh trong bộ nhớ chung.

Tách khỏi phần cơ chế vì đây là thứ **mọi tiến trình phải đọc giống hệt nhau**:
một byte lệch ở đây thì hai tiến trình nhìn cùng một vùng nhớ mà thấy hai bảng
khác nhau, và không có lỗi nào phát ra. Nên nó được tính ở một chỗ, bằng những
hằng số có tên, chứ không rải số học con trỏ khắp nơi.

```text
┌──────────────────────────────────────────────────────────────┐
│ HEADER KÊNH                                                  │
│   magic · version · so_tien_trinh · so_dong_moi_vung          │
│   co_payload · so_thu_tu_ke_tiep                              │
│   missed[0..N-1]   <- đếm tin bị đè khi người đó chưa kịp đọc  │
├──────────────────────────────────────────────────────────────┤
│ BITMAP - N dãy LIỀN NHAU, mỗi dãy 1 bit cho MỖI DÒNG toàn kênh │
│   dãy chưa-đọc của tiến trình 0                               │
│   dãy chưa-đọc của tiến trình 1                               │
│   ...                                                         │
├──────────────────────────────────────────────────────────────┤
│ VÙNG GHI của tiến trình 0   <- CHỈ tiến trình 0 ghi vào đây   │
│ VÙNG GHI của tiến trình 1                                     │
│   ...                                                         │
└──────────────────────────────────────────────────────────────┘
```

⭐ Bitmap xếp thành **dãy liền nhau**, không rải trong từng dòng: nhờ vậy một
tiến trình thức dậy chỉ đọc **dãy của riêng nó** (1024 dòng = 128 byte) rồi
`int.from_bytes(...) != 0` là biết ngay có tin hay không - **một phép so**. Rải
trong dòng thì phải quét cả bảng.
"""

from __future__ import annotations

import struct
from typing import Final

from xime.core.shared import ghi_o

from ._errors import LinkLayoutMismatch

# ---------------------------------------------------------------------------
# Header của kênh
# ---------------------------------------------------------------------------

MAGIC: Final[bytes] = b"XLNK"
VERSION: Final[int] = 1

# magic 4B · version 2B · so_tien_trinh 2B · so_dong_moi_vung 4B · co_payload 4B
_HEADER = struct.Struct("<4sHHII")
_HEADER_FIXED: Final[int] = _HEADER.size  # 16

# Bộ đếm số thứ tự dùng chung, đặt ngay sau phần cố định và căn 8 byte.
# Nó phải nằm trong bộ nhớ CHUNG chứ không phải trong RAM của từng tiến trình:
# số thứ tự dùng để sắp đúng thứ tự các dòng khi bảng vòng lại, mà các dòng đó
# đến từ nhiều người ghi khác nhau.
# Nó KHÔNG cần nguyên tử tuyệt đối - hai người ghi cùng lúc có thể lấy trùng một
# số, và hậu quả là hai dòng cùng số thứ tự, tức thứ tự giữa đúng HAI dòng đó
# không xác định. Với một bus chở tín hiệu thưa thì đó là cái giá rẻ hơn nhiều
# so với một khoá trên đường ghi nóng.
SEQ_OFFSET: Final[int] = 16
_SEQ = struct.Struct("<Q")

MISSED_OFFSET: Final[int] = SEQ_OFFSET + _SEQ.size  # 24
_MISSED = struct.Struct("<Q")


# ---------------------------------------------------------------------------
# Một dòng
# ---------------------------------------------------------------------------

KEY_BYTES: Final[int] = 32
CORRELATION_BYTES: Final[int] = 16

# Sắp theo thứ tự CĂN CHỈNH giảm dần chứ không theo thứ tự tài liệu liệt kê:
# hai trường 8 byte nằm đầu để chúng luôn căn 8, phần 1 byte gom về cuối. Header
# dòng vì vậy đúng 72 byte, và payload cũng bắt đầu ở bội số của 8.
#
#   0  so_thu_tu     8B
#   8  ghi_luc       8B   monotonic_ns, CHỈ để quan sát
#  16  correlation  16B   ghép ask với reply
#  32  key          32B   bên nhận lọc bằng cái này, KHÔNG chạm payload
#  64  do_dai        4B
#  68  da_ghi_xong   1B   0 = đang ghi dở -> người đọc BỎ QUA
#  69  loai          1B
#  70  nguoi_nhan    1B   255 = chưa ai nhận
#  71  nguoi_gui     1B
#  72  payload...
ROW_SEQ: Final[int] = 0
ROW_WRITTEN_AT: Final[int] = 8
ROW_CORRELATION: Final[int] = 16
ROW_KEY: Final[int] = 32
ROW_LENGTH: Final[int] = 64
ROW_COMPLETE: Final[int] = 68
ROW_KIND: Final[int] = 69
ROW_TAKER: Final[int] = 70
ROW_SENDER: Final[int] = 71
ROW_HEADER_BYTES: Final[int] = 72

_U64 = struct.Struct("<Q")
_U32 = struct.Struct("<I")

# 255 nghĩa là "chưa ai nhận dòng này". Cũng là lý do một kênh không phục vụ quá
# 255 tiến trình - một trần cao hơn mọi con số hợp lý, được kiểm lúc tạo kênh.
NO_TAKER: Final[int] = 255
MAX_PROCESSES: Final[int] = 255

KIND_ANNOUNCE: Final[int] = 0
KIND_REQUEST: Final[int] = 1
KIND_REPLY: Final[int] = 2
KIND_FAILURE: Final[int] = 3


class ChannelLayout:
    """Tính mọi offset của một kênh từ ba con số khai trong `ChannelSpec`.

    Bất biến quan trọng nhất: **mọi tiến trình phải dựng cùng một layout**. Điều
    đó tự đúng vì cả ba con số đến từ `config/link.py`, thứ được import y hệt ở
    mọi tiến trình - nhưng lớp này vẫn ghi ba con số ấy vào header và kiểm lại
    lúc attach, vì "tự đúng nhờ quy ước" là thứ hỏng im lặng khi quy ước bị phá.
    """

    __slots__ = (
        "rows_per_writer",
        "payload_bytes",
        "process_count",
        "total_rows",
        "row_bytes",
        "bitmap_offset",
        "bitmap_stride",
        "rows_offset",
        "region_bytes",
        "total_bytes",
    )

    def __init__(self, rows_per_writer: int, payload_bytes: int, process_count: int) -> None:
        self.rows_per_writer = rows_per_writer
        self.payload_bytes = payload_bytes
        self.process_count = process_count

        self.total_rows = rows_per_writer * process_count
        self.row_bytes = ROW_HEADER_BYTES + payload_bytes

        header_bytes = MISSED_OFFSET + _MISSED.size * process_count
        self.bitmap_offset = _align8(header_bytes)
        # Một dãy bit cho mỗi tiến trình, mỗi dãy phủ MỌI dòng của kênh. Căn 8
        # để mỗi dãy bắt đầu ở bội số của 8 - đọc cả dãy bằng một lần int.from_bytes.
        self.bitmap_stride = _align8((self.total_rows + 7) // 8)
        self.rows_offset = self.bitmap_offset + self.bitmap_stride * process_count
        self.region_bytes = self.row_bytes * rows_per_writer
        self.total_bytes = self.rows_offset + self.region_bytes * process_count

    # -- header ------------------------------------------------------------

    def write_header(self, buf: memoryview) -> None:
        _HEADER.pack_into(
            buf,
            0,
            MAGIC,
            VERSION,
            self.process_count,
            self.rows_per_writer,
            self.payload_bytes,
        )
        _SEQ.pack_into(buf, SEQ_OFFSET, 0)
        for index in range(self.process_count):
            _MISSED.pack_into(buf, self.missed_offset(index), 0)

    def verify_header(self, buf: memoryview, channel: str) -> None:
        """Fail fast khi vùng nhớ không mang đúng khuôn bảng ta đang chờ đợi.

        Ca thật mà nó chặn: hai ứng dụng Xime chạy cùng máy, cùng đặt tên một
        kênh là "fieldbus" nhưng khai kích thước khác nhau. Không có phép kiểm
        này thì chúng attach vào nhau và đọc rác của nhau, mà triệu chứng chỉ là
        "thỉnh thoảng nhận được tin lạ".
        """
        magic, version, process_count, rows, payload = _HEADER.unpack_from(buf, 0)
        if magic != MAGIC:
            raise LinkLayoutMismatch(
                f"channel {channel!r}: shared memory does not carry a Xime link "
                f"header (found {magic!r}). Another program may own this name."
            )
        if version != VERSION:
            raise LinkLayoutMismatch(
                f"channel {channel!r}: link layout version {version} but this "
                f"process speaks version {VERSION}."
            )
        actual = (process_count, rows, payload)
        expected = (self.process_count, self.rows_per_writer, self.payload_bytes)
        if actual != expected:
            raise LinkLayoutMismatch(
                f"channel {channel!r}: shared memory was created with "
                f"(processes={actual[0]}, rows={actual[1]}, payload={actual[2]}) "
                f"but this process expects "
                f"(processes={expected[0]}, rows={expected[1]}, payload={expected[2]}). "
                f"Every process must import the same config/link.py."
            )

    def missed_offset(self, index: int) -> int:
        return MISSED_OFFSET + _MISSED.size * index

    def read_missed(self, buf: memoryview, index: int) -> int:
        return int(_MISSED.unpack_from(buf, self.missed_offset(index))[0])

    def bump_missed(self, buf: memoryview, index: int) -> None:
        """Tăng bộ đếm `missed` của một tiến trình.

        ⚠ **Đọc-sửa-ghi, KHÔNG nguyên tử.** Hai tiến trình cùng tăng một ô
        trong cùng khoảnh khắc thì một lần tăng biến mất. Chấp nhận được, và
        khai ra đây thay vì để người sau tự phát hiện: `missed` là **chỉ số
        chẩn đoán**, dùng để trả lời *"có đang mất tin không"* chứ không phải
        *"mất đúng bao nhiêu"*. Một con số thấp hơn thực tế vẫn khác 0, và khác
        0 là toàn bộ tín hiệu.

        `next_sequence` ngay dưới cũng đọc-sửa-ghi nhưng ở đó **chỉ có một
        người ghi mỗi vùng**, nên nó không có cùng vấn đề - lý do đầy đủ ở chú
        thích của hàm đó. Phát hiện L5 của kiểm toán 0.8.
        """
        offset = self.missed_offset(index)
        current = _MISSED.unpack_from(buf, offset)[0]
        ghi_o(buf, offset, _MISSED, current + 1)

    def next_sequence(self, buf: memoryview) -> int:
        current = _SEQ.unpack_from(buf, SEQ_OFFSET)[0] + 1
        ghi_o(buf, SEQ_OFFSET, _SEQ, current)
        return int(current)

    # -- bitmap ------------------------------------------------------------

    def bit_offset(self, reader: int, row: int) -> tuple[int, int]:
        """Trả (vị trí byte, mặt nạ bit) của ô "reader chưa đọc row"."""
        return self.bitmap_offset + self.bitmap_stride * reader + row // 8, 1 << (row % 8)

    def set_bit(self, buf: memoryview, reader: int, row: int) -> None:
        pos, mask = self.bit_offset(reader, row)
        buf[pos] |= mask

    def clear_bit(self, buf: memoryview, reader: int, row: int) -> None:
        pos, mask = self.bit_offset(reader, row)
        buf[pos] &= 0xFF ^ mask

    def test_bit(self, buf: memoryview, reader: int, row: int) -> bool:
        pos, mask = self.bit_offset(reader, row)
        return bool(buf[pos] & mask)

    def band(self, buf: memoryview, reader: int) -> memoryview:
        start = self.bitmap_offset + self.bitmap_stride * reader
        return buf[start : start + self.bitmap_stride]

    def unread_rows(self, buf: memoryview, reader: int) -> list[int]:
        """Danh sách dòng mà `reader` chưa đọc, rẻ nhất có thể ở ca thường lệ.

        Ca thường lệ là **không có gì** - một tiến trình bị đánh thức giả (xem
        luật "semaphore là chuông") phải trả lời câu đó bằng một phép so, không
        phải bằng một vòng lặp qua cả nghìn dòng.
        """
        raw = self.band(buf, reader)
        value = int.from_bytes(raw, "little")
        if value == 0:
            return []
        rows: list[int] = []
        while value:
            low = value & -value
            row = low.bit_length() - 1
            if row < self.total_rows:
                rows.append(row)
            value ^= low
        return rows

    def any_unread(self, buf: memoryview, row: int) -> list[int]:
        """Những tiến trình còn bit chưa đọc trên `row`."""
        return [r for r in range(self.process_count) if self.test_bit(buf, r, row)]

    # -- dòng --------------------------------------------------------------

    def row_offset(self, row: int) -> int:
        return self.rows_offset + self.row_bytes * row

    def rows_of(self, writer: int) -> range:
        start = writer * self.rows_per_writer
        return range(start, start + self.rows_per_writer)

    def read_u64(self, buf: memoryview, row: int, field: int) -> int:
        return int(_U64.unpack_from(buf, self.row_offset(row) + field)[0])

    def write_u64(self, buf: memoryview, row: int, field: int, value: int) -> None:
        ghi_o(buf, self.row_offset(row) + field, _U64, value)

    def read_u8(self, buf: memoryview, row: int, field: int) -> int:
        return buf[self.row_offset(row) + field]

    def write_u8(self, buf: memoryview, row: int, field: int, value: int) -> None:
        buf[self.row_offset(row) + field] = value

    def read_length(self, buf: memoryview, row: int) -> int:
        return int(_U32.unpack_from(buf, self.row_offset(row) + ROW_LENGTH)[0])

    def write_length(self, buf: memoryview, row: int, value: int) -> None:
        ghi_o(buf, self.row_offset(row) + ROW_LENGTH, _U32, value)

    def read_key(self, buf: memoryview, row: int) -> str:
        start = self.row_offset(row) + ROW_KEY
        raw = bytes(buf[start : start + KEY_BYTES])
        return raw.rstrip(b"\x00").decode("utf-8", errors="replace")

    def write_key(self, buf: memoryview, row: int, key: str) -> None:
        raw = key.encode("utf-8")
        start = self.row_offset(row) + ROW_KEY
        buf[start : start + KEY_BYTES] = raw.ljust(KEY_BYTES, b"\x00")

    def read_correlation(self, buf: memoryview, row: int) -> bytes:
        start = self.row_offset(row) + ROW_CORRELATION
        return bytes(buf[start : start + CORRELATION_BYTES])

    def write_correlation(self, buf: memoryview, row: int, value: bytes) -> None:
        start = self.row_offset(row) + ROW_CORRELATION
        buf[start : start + CORRELATION_BYTES] = value.ljust(CORRELATION_BYTES, b"\x00")

    def read_payload(self, buf: memoryview, row: int) -> bytes:
        start = self.row_offset(row) + ROW_HEADER_BYTES
        # ⛔ Ép trần. Trường độ dài nằm TRONG vùng nhớ chung, tức một tiến trình
        # ghi bậy (hoặc một lỗi ghi) đặt được vào đó một con số lớn hơn dòng.
        # Đo được 2026-08-21: kênh khai `payload_bytes=64`, bóp méo trường độ
        # dài rồi đọc ra **2.104 byte** - lan sang vùng ghi của tiến trình khác,
        # rồi chảy tiếp vào `stats()` và `dump()`. Phát hiện L1 của kiểm toán 0.8.
        dai = min(self.read_length(buf, row), self.payload_bytes)
        return bytes(buf[start : start + dai])

    def write_payload(self, buf: memoryview, row: int, payload: bytes) -> None:
        start = self.row_offset(row) + ROW_HEADER_BYTES
        buf[start : start + len(payload)] = payload


def _align8(value: int) -> int:
    return (value + 7) & ~7
