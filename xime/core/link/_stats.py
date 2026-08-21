"""Kiểu dữ liệu quan sát của bus.

Ba trường trong bố cục byte sinh ra **chỉ vì** những kiểu này: `missed[]` trong
header kênh, `ghi_luc` và `nguoi_gui` trên mỗi dòng. Hàm `stats()` viết lúc nào
cũng được, nhưng **dữ liệu nó đọc thì phải được ghi từ trước** - thêm sau là đổi
khuôn bảng, tức đổi cách mọi tiến trình đọc.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReaderStats:
    """Tình trạng một tiến trình đọc, nhìn từ bất kỳ tiến trình nào.

    ⚠ `missed` là **tổng tích luỹ, không bao giờ reset**. Muốn biết *"năm phút
    qua mất bao nhiêu"* thì tự lấy hiệu hai lần đọc - có hàm reset thì hai chỗ
    cùng gọi sẽ ăn mất số của nhau.
    """

    process_index: int
    unread: int
    missed: int


@dataclass(frozen=True)
class ChannelStats:
    """Tình trạng một kênh.

    `oldest_unread_age_ms` là lý do `ghi_luc` tốn 8 byte mỗi dòng, và nó đáng:
    `unread = 47` không nói gì nếu không biết nhịp tin, còn *"47 tin, cũ nhất 8
    phút trước"* thì ai cũng hiểu là **tắc**.
    """

    name: str
    rows_total: int
    rows_used: int
    oldest_unread_age_ms: int | None
    readers: tuple[ReaderStats, ...]


@dataclass(frozen=True)
class LinkStats:
    """Ảnh chụp gần đúng của cả cụm."""

    link_id: str
    channels: tuple[ChannelStats, ...]


@dataclass(frozen=True)
class RawRow:
    """Một dòng thô. Chỉ dùng để gỡ lỗi - `payload` là bytes framework không hiểu."""

    row: int
    kind: str
    key: str
    sender: int
    taker: int | None
    unread_by: tuple[int, ...]
    payload: bytes
    age_ms: int


@dataclass(frozen=True)
class LinkMessage:
    """Một dòng đã đọc, chưa qua handler nào.

    `drain_sync()` trả về kiểu này cho tiến trình gốc - nơi không có DI, nên
    không có handler nào để tra và người gọi tự phân nhánh.
    """

    channel: str
    key: str
    payload: bytes
    sender: int
