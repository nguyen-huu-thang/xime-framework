"""Kho này đang nằm trên cái gì: RAM, đĩa, hay không biết.

Một câu *"kho ở `/dev/shm/app-store`"* mang **hai nghĩa** mà không gì tách ra:
dữ liệu **mất khi máy khởi động lại**, hay **sống qua**. Người vận hành đổi một
dòng `lmdb.path` trong YAML là đổi trọn ngữ nghĩa đó, và hôm nay không có dòng
log nào nói ra. Đúng [luật 03](../../../.claude/rules/03-mot-gia-tri-mot-nghia.md).

⭐ **BA kết cục, không phải hai.** Trên Linux đọc được `/proc/mounts` nên biết
chắc; trên Windows thì **không biết** - và trả `False` ở đó là nói dối, vì một ổ
đĩa RAM (ImDisk và tương tự) trông y hệt một ổ thật với mọi API Python. *"Chưa
kết luận được"* phải là một giá trị riêng.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

# tmpfs và ramfs là hai hệ tệp nằm trong RAM mà Linux thật sự dùng. `/run`,
# `/dev/shm` và thư mục do `RuntimeDirectory=` tạo đều là tmpfs.
RAM_FILESYSTEMS = frozenset({"tmpfs", "ramfs"})

_MOUNTS = "/proc/mounts"


@dataclass(frozen=True)
class StorageReport:
    """Kho nằm ở đâu, còn bao nhiêu chỗ, và có phải RAM không."""

    measured_at: str
    """Thư mục **tồn tại** gần nhất đã dùng để đo - `lmdb.path` có thể chưa được tạo."""

    free_bytes: int | None
    """`None` = không đo được. Không phải `0`: hai thứ đó bắt người gọi làm hai việc khác nhau."""

    fstype: str | None
    """`None` = không đọc được loại hệ tệp (không phải Linux, hoặc `/proc` bị che)."""

    ram_backed: bool | None
    """`True` RAM · `False` bền vững · **`None` chưa kết luận được**."""

    @property
    def label(self) -> str:
        """Chữ để in ra log, giữ nguyên ba kết cục."""
        if self.ram_backed is None:
            return f"{self.fstype or 'unknown filesystem'}, RAM-backed unknown"
        if self.ram_backed:
            return f"{self.fstype}, RAM-backed - contents are lost on reboot"
        return f"{self.fstype}, on durable storage - contents survive a reboot"


def nearest_existing(path: str | Path) -> Path | None:
    """Tổ tiên tồn tại gần nhất của `path`.

    `lmdb.path` thường **chưa được tạo** lúc ta muốn đo, nhưng hệ tệp thì đã
    quyết định rồi - nó là hệ tệp của thư mục cha. Đo ở đó cho cùng câu trả lời
    mà không phải tạo gì.
    """
    current = Path(path).expanduser()
    try:
        current = current.resolve()
    except OSError:  # pragma: no cover - đường dẫn dị dạng
        return None
    for candidate in (current, *current.parents):
        if candidate.is_dir():
            return candidate
    return None


def _linux_fstype(target: Path) -> str | None:
    """Loại hệ tệp của điểm gắn kết dài nhất phủ `target`, đọc từ `/proc/mounts`.

    ⚠ Phải khớp điểm gắn kết **DÀI NHẤT**, không phải điểm đầu tiên khớp: `/`
    là tiền tố của mọi đường dẫn, nên khớp đầu tiên luôn trả về hệ tệp gốc và
    `/dev/shm` sẽ bị báo là `ext4`.
    """
    try:
        with open(_MOUNTS, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return None

    best_point = ""
    best_type: str | None = None
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        point, fstype = parts[1], parts[2]
        # `/proc/mounts` thoát khoảng trắng thành `\040`.
        point = point.replace("\\040", " ")
        try:
            mount = Path(point)
        except ValueError:  # pragma: no cover
            continue
        if (target == mount or mount in target.parents) and len(point) >= len(best_point):
            best_point, best_type = point, fstype
    return best_type


def inspect_storage(path: str | Path) -> StorageReport:
    """Đo hệ tệp đang đỡ `path`. Không tạo gì, không mở gì."""
    anchor = nearest_existing(path)
    if anchor is None:
        return StorageReport(str(path), None, None, None)

    try:
        free_bytes: int | None = shutil.disk_usage(anchor).free
    except OSError:  # pragma: no cover - quyền, hoặc ổ vừa bị rút
        free_bytes = None

    fstype = _linux_fstype(anchor)
    ram_backed = None if fstype is None else fstype in RAM_FILESYSTEMS
    return StorageReport(str(anchor), free_bytes, fstype, ram_backed)


def human_size(size: int) -> str:
    """`1073741824` -> `1.0GiB`. Một con số byte trần không nói gì với người đọc log."""
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f}{unit}" if unit != "B" else f"{int(value)}B"
        value /= 1024
    raise AssertionError("unreachable")  # pragma: no cover
