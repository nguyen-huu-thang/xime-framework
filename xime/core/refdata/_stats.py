"""Kiểu dữ liệu quan sát của kho tham chiếu.

Ba trường trong bố cục byte sinh ra **chỉ vì** kiểu này: `ghi_luc`, `so_doan` và
`nguoi_ghi`. Hàm `stats()` viết lúc nào cũng được, nhưng **dữ liệu nó đọc thì
phải được ghi từ trước** - thêm sau là đổi khuôn vùng nhớ, tức đổi cách mọi
tiến trình đọc.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RefDataStats:
    """Ảnh chụp **gần đúng** tình trạng một bảng tham chiếu.

    ⚠ Gần đúng là một phần của hợp đồng, không phải lời xin lỗi: nó đọc bộ nhớ
    chung trong lúc người khác có thể đang ghi. Đừng dùng nó làm chốt chặn
    logic - dùng `read()` cho việc đó.

    Attributes:
        name: tên bảng, cũng là tên vùng nhớ chung.
        generation: số đời **trong bộ nhớ chung** - bản mới nhất cả cụm có.
            **0 nghĩa là chưa ai publish lần nào.**
        served_generation: số đời mà **tiến trình này** đang phục vụ, tức số đời
            của object đang nằm trong cache L1. ⭐ Nó tách khỏi `generation` vì
            hai con số trả lời hai câu khác nhau, và chênh nhau là **tín hiệu
            duy nhất** cho thấy một tiến trình đang phục vụ bản cũ. 0 nghĩa là
            tiến trình này chưa đọc lần nào.
        written_at_ms: bao lâu rồi kể từ lần publish cuối, tính bằng mili giây.
            `None` khi chưa có bản nào.
        used_bytes: cỡ bản đang dùng.
        limit_bytes: trần đã khai (`max_bytes`).
        segments: số đoạn của bản đang dùng. v1 luôn là 1.
        writer: chỉ số tiến trình đã publish bản đang dùng, `None` nếu chưa ai.
        stale: ⭐ **lần publish gần nhất THẤT BẠI vì vượt trần.** Một publish
            hỏng mà không ai biết là chỗ tệ nhất của cả cơ chế này - cụm vẫn
            chạy êm bằng bản cũ, và không request nào lỗi cho tới khi có thứ
            phụ thuộc vào bản mới xuất hiện.
    """

    name: str
    generation: int
    served_generation: int
    written_at_ms: int | None
    used_bytes: int
    limit_bytes: int
    segments: int
    writer: int | None
    stale: bool

    @property
    def ready(self) -> bool:
        """Đã có ít nhất một bản để đọc chưa."""
        return self.generation > 0

    @property
    def fill_ratio(self) -> float:
        """Phần trăm trần đang dùng, dạng 0..1. Cảnh báo tự động ở 0,8."""
        return self.used_bytes / self.limit_bytes if self.limit_bytes else 0.0
