"""Khai kênh và handler - `configure_link()`.

Đúng khuôn `configure_*` của repo: framework **không tự quét** config, lập trình
viên gọi một hàm. Xem `rules/config-discovery.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from xime.core.exception.framework import StartupException

from ._layout import MAX_PROCESSES

# Kênh điều khiển của chính framework. Cha dùng nó để nói với con (*"bạn là
# primary từ giờ"*) và con báo lại (*"tôi đã sẵn sàng"*).
#
# ⚠ Framework LUÔN tạo kênh này, không phụ thuộc ứng dụng khai kênh nào. Để nó
# phụ thuộc app là đặt một chốt chặn của framework lên một thành phần TUỲ CHỌN -
# đúng thứ đã bị bác khi loại phương án khoá trong LMDB: nó sẽ vắng mặt đúng lúc
# cần nhất.
INTERNAL_CHANNEL: Final[str] = "__xime__"

# Kênh nội bộ chở tín hiệu điều khiển: thưa, nhỏ, và không được phép mất.
_INTERNAL_ROWS: Final[int] = 64
_INTERNAL_PAYLOAD: Final[int] = 512


@dataclass(frozen=True)
class ChannelSpec:
    """Kích thước một kênh, khai bằng Python chứ không bằng YAML.

    Chọn số dòng và cỡ payload đòi biết **handler chạy bao lâu** và **tin của
    ứng dụng to cỡ nào** - hai thứ người vận hành không biết và không quyết
    được. Cùng phép phân loại đã dùng cho `configure_event_bus`:
    *người vận hành có ĐỦ THÔNG TIN để chọn giá trị này không?*

    ⚠ Trên Windows, bộ nhớ chung bị **cấp phát thật** ngay lúc tạo, nên tổng RAM
    mất đi bằng tổng mọi kênh, mất ngay lúc khởi động. Khai `rows` và
    `payload_bytes` có ý thức, đừng cho dư cho chắc:

        4 kênh × 256 dòng × 4 KB    =    4 MB     ổn
        4 kênh × 4096 dòng × 64 KB  =    1 GB     mất trắng lúc khởi động

    Attributes:
        rows: số dòng MỖI TIẾN TRÌNH được ghi. Tổng số dòng của kênh là
            `rows × số tiến trình`, vì mỗi tiến trình có vùng ghi riêng.
        payload_bytes: trần cỡ payload. Gửi quá là **nổ ngay lúc gửi**, không
            trả về một kết cục - đó là bug của người viết app, không phải trạng
            thái lúc chạy, và trả về một kết cục là mời người ta `except` rồi
            bỏ qua.
    """

    rows: int = 256
    payload_bytes: int = 512

    def __post_init__(self) -> None:
        if self.rows < 1:
            raise ValueError(f"ChannelSpec.rows must be >= 1, got {self.rows}")
        if self.payload_bytes < 1:
            raise ValueError(
                f"ChannelSpec.payload_bytes must be >= 1, got {self.payload_bytes}"
            )


class _LinkRegistry:
    """Nơi `configure_link()` ghi vào, đọc lúc khởi động.

    Cùng khuôn gọi tường minh với `configure_socket_controllers()` và các anh em.
    """

    def __init__(self) -> None:
        self._channels: dict[str, ChannelSpec] = {}
        self._handlers: tuple[type, ...] = ()

    def set(
        self, channels: dict[str, ChannelSpec], handlers: tuple[type, ...]
    ) -> None:
        self._channels = dict(channels)
        self._handlers = handlers

    def channels(self) -> dict[str, ChannelSpec]:
        """Kênh của ứng dụng, CỘNG kênh nội bộ framework luôn tạo."""
        merged = {INTERNAL_CHANNEL: ChannelSpec(_INTERNAL_ROWS, _INTERNAL_PAYLOAD)}
        merged.update(self._channels)
        return merged

    def app_channels(self) -> dict[str, ChannelSpec]:
        """Chỉ những kênh ứng dụng khai - dùng cho phép kiểm lúc khởi động."""
        return dict(self._channels)

    def handlers(self) -> tuple[type, ...]:
        return self._handlers

    def reset(self) -> None:
        """Về mặc định. Cho test - code sản xuất không bao giờ gọi."""
        self._channels = {}
        self._handlers = ()


link_registry = _LinkRegistry()


def configure_link(
    *,
    channels: dict[str, ChannelSpec] | None = None,
    handlers: list[type] | tuple[type, ...] = (),
) -> None:
    """Khai các kênh của ứng dụng và những class chứa handler.

    ```python
    # config/link.py
    from xime.core.link import ChannelSpec, configure_link

    from app.link.fieldbus import FieldbusHandler

    configure_link(
        channels={
            "fieldbus": ChannelSpec(rows=256, payload_bytes=512),
            "cauhinh":  ChannelSpec(rows=64,  payload_bytes=4096),
        },
        handlers=[FieldbusHandler],
    )
    ```

    Bốn chi tiết cố ý:

    1. **`handlers=` nhận CLASS, không nhận instance.** Framework lấy nó từ DI
       nên handler được inject bình thường. Cùng khuôn
       `configure_jwt(key_provider=...)` và `configure_grpc_tls(provider=...)`.
    2. **Khai kênh và khai handler tách nhau**: một handler phục vụ nhiều kênh
       được, và một kênh có thể chỉ để **gửi**.
    3. **`channels` phải giống nhau ở mọi tiến trình**, vì vùng nhớ là chung.
       Tự đúng nhờ `config/` được import y hệt ở mọi tiến trình, nhưng vẫn được
       kiểm lại lúc attach - "tự đúng nhờ quy ước" là thứ hỏng im lặng khi quy
       ước bị phá.
    4. Tên kênh bắt đầu bằng `__` **dành riêng cho framework**.
    """
    specs = dict(channels or {})
    for name in specs:
        if name.startswith("__"):
            raise StartupException(
                f"\nReserved Link Channel Name\n"
                f"  Channel: {name!r}\n"
                f"  Detail : names starting with '__' belong to the framework "
                f"(it always creates {INTERNAL_CHANNEL!r} for its own control "
                f"traffic). Pick another name."
            )
        if not name or len(name.encode("utf-8")) > 64:
            raise StartupException(
                f"\nInvalid Link Channel Name\n"
                f"  Channel: {name!r}\n"
                f"  Detail : must be non-empty and at most 64 bytes - it becomes "
                f"part of the shared-memory name."
            )
    link_registry.set(specs, tuple(handlers))


def validate_process_count(count: int) -> int:
    if count < 1 or count > MAX_PROCESSES:
        raise StartupException(
            f"\nInvalid Link Process Count\n"
            f"  Value   : {count}\n"
            f"  Expected: between 1 and {MAX_PROCESSES}.\n"
            f"  Detail  : one byte on every row records which process took it, "
            f"and {MAX_PROCESSES} is reserved to mean 'nobody took it yet'."
        )
    return count
