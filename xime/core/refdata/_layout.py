"""Bố cục byte của một vùng `RefData`.

Tách khỏi phần cơ chế vì đây là thứ **mọi tiến trình phải đọc giống hệt nhau**:
một byte lệch ở đây thì hai tiến trình nhìn cùng một vùng nhớ mà thấy hai bảng
khác nhau, và không có lỗi nào phát ra.

```text
┌──────────────────────────────────────────────────────────┐
│ HEADER                                                   │
│   magic · version · co (2B)                              │
│   so_doi        8B   0 = CHƯA AI PUBLISH LẦN NÀO         │
│   ghi_luc       8B   monotonic_ns, CHỈ để quan sát       │
│   do_dai_A      4B                                       │
│   do_dai_B      4B                                       │
│   tran_bytes    4B   khai lúc tạo, kiểm lại lúc attach   │
│   so_doan       2B   số đoạn dữ liệu của bản đang dùng   │
│   con_tro       1B   0 hoặc 1 - bản nào đang dùng        │
│   nguoi_ghi     1B   tiến trình đang giữ quyền ghi       │
├──────────────────────────────────────────────────────────┤
│ bản A            max_bytes                               │
│ bản B            max_bytes                               │
└──────────────────────────────────────────────────────────┘
```

⚠ **Tổng = 2 × max_bytes + header.** Khai `max_bytes = 64 KB` là mất **128 KB**,
và trên Windows là mất **thật** ngay lúc khởi động (không thưa như Linux).

### `con_tro` là 1 byte, và đó không phải chuyện tiết kiệm

Ghi một byte là **nguyên tử trên mọi kiến trúc thực tế**, nên người đọc không
bao giờ thấy một giá trị nửa vời. Đừng đổi nó thành `int` nhiều byte cho gọn.

### Vì sao `so_doan` có mặt từ v1 dù v1 chỉ dùng một đoạn

Thiết kế chốt *"khai hình dạng ngay từ v1"*: nếu v1 làm một vùng liền không có
trường này thì ngày cần nhiều đoạn là **đổi khuôn vùng nhớ**, tức đổi cách mọi
tiến trình đọc. Hai byte bây giờ rẻ hơn một lần đổi khuôn về sau.
"""

from __future__ import annotations

import struct
from typing import Final

from xime.core.shared import ghi_o

from ._errors import RefDataLayoutMismatch

MAGIC: Final[bytes] = b"XREF"
VERSION: Final[int] = 1

# Sắp theo CĂN CHỈNH giảm dần chứ không theo thứ tự tài liệu liệt kê: hai
# trường 8 byte nằm ngay sau magic để chúng luôn căn 8, phần 1 byte gom về
# cuối. Header vì vậy đúng 40 byte, và ô dữ liệu bắt đầu ở bội số của 8.
#
#   0  magic       4B
#   4  version     2B
#   6  (đệm)       2B
#   8  so_doi      8B
#  16  ghi_luc     8B
#  24  do_dai_A    4B
#  28  do_dai_B    4B
#  32  tran_bytes  4B
#  36  so_doan     2B
#  38  con_tro     1B
#  39  nguoi_ghi   1B
#  40  bản A ...
_HEADER = struct.Struct("<4sHHQQIIIHBB")
HEADER_BYTES: Final[int] = _HEADER.size

_GENERATION = struct.Struct("<Q")
_WRITTEN_AT = struct.Struct("<Q")
_LENGTH = struct.Struct("<I")
_SEGMENTS = struct.Struct("<H")
_FLAGS = struct.Struct("<H")

GENERATION_OFFSET: Final[int] = 8
WRITTEN_AT_OFFSET: Final[int] = 16
LENGTH_A_OFFSET: Final[int] = 24
LENGTH_B_OFFSET: Final[int] = 28
LIMIT_OFFSET: Final[int] = 32
SEGMENTS_OFFSET: Final[int] = 36
POINTER_OFFSET: Final[int] = 38
WRITER_OFFSET: Final[int] = 39

# Hai byte ở offset 6 vốn là đệm (`_HEADER` luôn pack 0 vào đó và không ai đọc).
# Nay chúng chở CỜ TRẠNG THÁI, và đó là chỗ duy nhất đúng cho chúng.
#
# `stale` nghĩa là: primary đã thử publish một bản mới và **không vừa trần**,
# nên cả cụm đang phục vụ bản CŨ. Trước bản vá cờ này là thuộc tính instance,
# sống trong RAM của **đúng cái tiến trình đã hỏng** - nên `stats().stale` chỉ
# nhìn thấy được từ nơi không ai nhìn, và một primary MỚI được thăng cấp bắt
# đầu với `stale=False` trong khi dữ liệu vẫn cũ. Phát hiện T5 của kiểm toán 0.8.
#
# ⭐ Làm bây giờ tốn 0 byte vì đệm có sẵn; làm sau là **đổi khuôn vùng nhớ**,
# tức đổi cách mọi tiến trình đọc. Đúng lập luận đã dùng để đưa `so_doan` vào
# từ v1.
FLAGS_OFFSET: Final[int] = 6
FLAG_STALE: Final[int] = 0x0001

# 255 nghĩa là "chưa ai giữ quyền ghi" - cùng quy ước NO_TAKER của bus, và cùng
# lý do một cụm không phục vụ quá 255 tiến trình.
NO_WRITER: Final[int] = 255

# `so_doi` bắt đầu từ 0 và 0 mang **đúng một** nghĩa: chưa ai publish lần nào.
# Không cần thêm một bit cờ - thêm là tạo hai nguồn sự thật cho cùng một câu
# hỏi, và hai nguồn thì có ngày lệch nhau.
NEVER_PUBLISHED: Final[int] = 0


class RefDataLayout:
    """Tính mọi offset của một vùng `RefData` từ đúng một con số: `max_bytes`."""

    __slots__ = ("max_bytes", "slot_a_offset", "slot_b_offset", "total_bytes")

    def __init__(self, max_bytes: int) -> None:
        if max_bytes < 1:
            raise ValueError(f"max_bytes must be >= 1, got {max_bytes}")
        self.max_bytes = max_bytes
        self.slot_a_offset = HEADER_BYTES
        self.slot_b_offset = HEADER_BYTES + max_bytes
        self.total_bytes = HEADER_BYTES + max_bytes * 2

    # -- header ------------------------------------------------------------

    def write_header(self, buf: memoryview) -> None:
        _HEADER.pack_into(
            buf, 0, MAGIC, VERSION, 0, NEVER_PUBLISHED, 0, 0, 0,
            self.max_bytes, 0, 0, NO_WRITER,
        )

    def verify_header(self, buf: memoryview, name: str) -> None:
        """Fail fast khi vùng nhớ không mang đúng khuôn ta đang chờ đợi.

        Ca thật mà nó chặn: hai ứng dụng Xime chạy cùng máy, cùng đặt tên một
        bảng là `jwt-keys` nhưng khai `max_bytes` khác nhau. Không có phép kiểm
        này thì chúng attach vào nhau và đọc rác của nhau, mà triệu chứng chỉ
        là "thỉnh thoảng decode hỏng".
        """
        unpacked = _HEADER.unpack_from(buf, 0)
        magic, version, limit = unpacked[0], unpacked[1], unpacked[7]
        if magic != MAGIC:
            raise RefDataLayoutMismatch(
                f"refdata {name!r}: shared memory does not carry a Xime refdata "
                f"header (found {magic!r}). Another program may own this name."
            )
        if version != VERSION:
            raise RefDataLayoutMismatch(
                f"refdata {name!r}: layout version {version} but this process "
                f"speaks version {VERSION}."
            )
        if limit != self.max_bytes:
            raise RefDataLayoutMismatch(
                f"refdata {name!r}: shared memory was created with "
                f"max_bytes={limit} but this process expects {self.max_bytes}. "
                f"Every process must import the same config module."
            )

    # -- các trường đơn ----------------------------------------------------

    def read_generation(self, buf: memoryview) -> int:
        return int(_GENERATION.unpack_from(buf, GENERATION_OFFSET)[0])

    def write_generation(self, buf: memoryview, value: int) -> None:
        # ⛔ `ghi_o`, KHÔNG phải `pack_into` - xem docstring của `ghi_o`.
        # `pack_into` xoá vùng về 0 trước khi ghi, mà `NEVER_PUBLISHED` cũng là
        # `0`. Người đọc rơi vào cửa sổ đó nhận `None` = *"bảng chưa ai
        # publish"*, và với bảng `jwt-keys` thì đó là một request hợp lệ bị 401.
        ghi_o(buf, GENERATION_OFFSET, _GENERATION, value)

    def read_written_at(self, buf: memoryview) -> int:
        return int(_WRITTEN_AT.unpack_from(buf, WRITTEN_AT_OFFSET)[0])

    def write_written_at(self, buf: memoryview, value: int) -> None:
        ghi_o(buf, WRITTEN_AT_OFFSET, _WRITTEN_AT, value)

    def read_pointer(self, buf: memoryview) -> int:
        return buf[POINTER_OFFSET]

    def write_pointer(self, buf: memoryview, slot: int) -> None:
        buf[POINTER_OFFSET] = slot

    def read_segments(self, buf: memoryview) -> int:
        return int(_SEGMENTS.unpack_from(buf, SEGMENTS_OFFSET)[0])

    def write_segments(self, buf: memoryview, value: int) -> None:
        # ⛔ `ghi_o`: cửa sổ số 0 ở đây không im lặng như `generation` - người
        # đọc thấy `segments == 0` sẽ **ném `RefDataTornError`**. Đó chính là
        # "một exception msgpack ngẫu nhiên vài tháng một lần" mà `_refdata.py`
        # đã lo trong chú thích của nó.
        ghi_o(buf, SEGMENTS_OFFSET, _SEGMENTS, value)

    def read_writer(self, buf: memoryview) -> int:
        return buf[WRITER_OFFSET]

    def write_writer(self, buf: memoryview, value: int) -> None:
        buf[WRITER_OFFSET] = value

    # -- hai ô dữ liệu -----------------------------------------------------

    def _length_offset(self, slot: int) -> int:
        return LENGTH_A_OFFSET if slot == 0 else LENGTH_B_OFFSET

    def read_length(self, buf: memoryview, slot: int) -> int:
        return int(_LENGTH.unpack_from(buf, self._length_offset(slot))[0])

    def write_length(self, buf: memoryview, slot: int, value: int) -> None:
        ghi_o(buf, self._length_offset(slot), _LENGTH, value)

    def read_flags(self, buf: memoryview) -> int:
        return int(_FLAGS.unpack_from(buf, FLAGS_OFFSET)[0])

    def set_flag(self, buf: memoryview, flag: int, value: bool) -> None:
        """Bật hoặc tắt một cờ. Ghi 2 byte thẳng, không đọc-sửa-ghi trên bit.

        ⚠ Chỉ **primary** gọi hàm này, và mỗi lần chạy chỉ có một primary - đó
        là điều kiện khiến đọc-sửa-ghi ở đây an toàn. Ngày có cờ thứ hai do một
        tiến trình KHÁC ghi thì điều kiện đó mất, và phải nghĩ lại.
        """
        hien = self.read_flags(buf)
        moi = (hien | flag) if value else (hien & ~flag)
        if moi != hien:
            ghi_o(buf, FLAGS_OFFSET, _FLAGS, moi)

    def slot_offset(self, slot: int) -> int:
        return self.slot_a_offset if slot == 0 else self.slot_b_offset

    def slot_view(self, buf: memoryview, slot: int) -> memoryview:
        """View vào một ô - **không copy**.

        ⚠ Người gọi phải dùng ngay trong lượt đọc rồi thả ra: nó trỏ thẳng vào
        bộ nhớ chung, nên giữ lại là giữ một view có thể bị người ghi đè lên
        bất cứ lúc nào, và `SharedMemory.close()` sẽ ném vì còn view chưa thả.
        """
        start = self.slot_offset(slot)
        return buf[start : start + self.read_length(buf, slot)]

    def write_slot(self, buf: memoryview, slot: int, payload: bytes) -> None:
        start = self.slot_offset(slot)
        buf[start : start + len(payload)] = payload
