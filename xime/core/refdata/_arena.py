"""Vùng nhớ của mọi `RefData` trong một lần chạy, và ai được ghi.

```text
CHA:  1. đọc danh sách class đã khai (configure_refdata)
      2. TẠO một vùng nhớ RIÊNG cho từng bảng            <- RefDataArena.create
      3. sinh con, truyền `run_id` xuống

CON:  1. nhận `run_id`
      2. ATTACH từng vùng nhớ                            <- RefDataArena.attach
      3. import config, dựng DI                          <- RefData vào DI ở đây
```

⭐ **Arena dựng TRƯỚC DI**, không qua `post_construct`: nó là hạ tầng của
framework chứ không phải component của ứng dụng. Cùng lập luận và cùng bước với
bus.

### Mỗi bảng một vùng nhớ RIÊNG (chủ dự án chốt 2026-08-19)

Nguyên văn: *"các bảng nên không liên quan gì đến nhau, kể cả bộ nhớ"*. Được ba
thứ, và tổng RAM thì **bằng nhau** ở cả hai cách nên không mất gì:

| | |
|---|---|
| Kích thước độc lập | khoá JWT 64 KB, danh bạ app 1 MB |
| Thêm hoặc bớt một bảng | **không đổi bố cục** của bảng khác |
| `publish()` một bảng | không chạm một byte nào của bảng kia |

Cùng lý do đã chốt *"một bảng một file LMDB"* ở kho nhóm 2.
"""

from __future__ import annotations

import logging
import os
import secrets
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from multiprocessing.shared_memory import SharedMemory
from typing import TYPE_CHECKING, Any

from xime.core._mp import view_of

from ._layout import RefDataLayout

if TYPE_CHECKING:
    from ._refdata import RefData

_log = logging.getLogger("xime.refdata")

# Tiền tố tên vùng nhớ. Cùng khuôn với bus (`xime-link-...`) để một lần dọn rác
# nhìn thấy cả hai họ.
_PREFIX = "xime-ref"


def block_name(run_id: str, table: str) -> str:
    return f"{_PREFIX}-{run_id}-{table}"


def new_run_id() -> str:
    """Mã một lần chạy: pid cộng phần ngẫu nhiên.

    `pid` nằm trong tên để bước dọn rác lúc khởi động biết chủ của một vùng nhớ
    mồ côi còn sống hay không; phần ngẫu nhiên để hai ứng dụng Xime chạy cùng
    máy, cùng đặt tên một bảng là `jwt-keys`, không attach vào nhau.
    """
    return f"{os.getpid()}-{secrets.token_hex(8)}"


@dataclass(frozen=True)
class TableSpec:
    """Một bảng, rút từ tham số class - đọc được **trước khi** DI tồn tại."""

    name: str
    max_bytes: int

    @property
    def total_bytes(self) -> int:
        return RefDataLayout(self.max_bytes).total_bytes


def specs_of(classes: tuple[type[RefData], ...]) -> tuple[TableSpec, ...]:
    """Rút `(name, max_bytes)` từ các class đã khai.

    Đọc thuộc tính class chứ không dựng instance: cha **không dựng DI**, nên nó
    chỉ có class trong tay. Đó cũng là lý do hai giá trị này phải là **tham số
    class** chứ không phải thứ tính ra trong `__init__`.
    """
    seen: dict[str, TableSpec] = {}
    for cls in classes:
        spec = TableSpec(name=cls.name, max_bytes=cls.max_bytes)  # type: ignore[arg-type]
        previous = seen.get(spec.name)
        if previous is not None and previous != spec:
            raise ValueError(
                f"two RefData classes declare the table {spec.name!r} with "
                f"different sizes ({previous.max_bytes} and {spec.max_bytes}). "
                f"One table, one size - every process must agree."
            )
        seen[spec.name] = spec
    return tuple(seen.values())


class RefDataArena:
    """Mọi vùng nhớ `RefData` của một lần chạy, cộng quyền ghi của tiến trình này.

    Đưa vào DI như một singleton dựng sẵn, và `RefData.__init__` nhận nó -
    đúng khuôn `Store(env: LmdbEnvironment)`.
    """

    def __init__(
        self,
        *,
        run_id: str,
        index: int,
        primary: bool | Callable[[], bool],
        blocks: dict[str, SharedMemory],
        owner: bool,
    ) -> None:
        self._run_id = run_id
        self._index = index
        # bool HOẶC một hàm trả bool. Xem property `primary` bên dưới.
        self._primary: bool | Callable[[], bool] = primary
        self._blocks = blocks
        self._owner = owner
        self._closed = False
        # Instance đã gắn vào arena này. Tham chiếu YẾU có chủ đích: RefData là
        # singleton DI sống suốt đời tiến trình nên arena không cần giữ nó
        # sống, và một test dựng chục bảng tạm thì không được rò.
        self._tracked: weakref.WeakSet[RefData[Any]] = weakref.WeakSet()

    # ------------------------------------------------------------------
    # Dựng
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        specs: tuple[TableSpec, ...],
        *,
        run_id: str | None = None,
        index: int = 0,
        primary: bool | Callable[[], bool] = True,
    ) -> RefDataArena:
        """Cấp vùng nhớ cho cả cụm. Tiến trình gốc gọi, và **chỉ nó**."""
        identifier = run_id or new_run_id()
        blocks: dict[str, SharedMemory] = {}
        try:
            for spec in specs:
                layout = RefDataLayout(spec.max_bytes)
                block = SharedMemory(
                    name=block_name(identifier, spec.name),
                    create=True,
                    size=layout.total_bytes,
                )
                layout.write_header(view_of(block))
                blocks[spec.name] = block
        except BaseException:
            for block in blocks.values():
                block.close()
                block.unlink()
            raise
        return cls(
            run_id=identifier,
            index=index,
            primary=primary,
            blocks=blocks,
            owner=True,
        )

    @classmethod
    def attach(
        cls,
        run_id: str,
        specs: tuple[TableSpec, ...],
        *,
        index: int,
        primary: bool | Callable[[], bool],
    ) -> RefDataArena:
        """Gắn vào vùng nhớ cha đã cấp. Con **không tự đoán tên, nó nhận tên**."""
        blocks: dict[str, SharedMemory] = {}
        try:
            for spec in specs:
                layout = RefDataLayout(spec.max_bytes)
                block = SharedMemory(name=block_name(run_id, spec.name))
                layout.verify_header(view_of(block), spec.name)
                blocks[spec.name] = block
        except BaseException:
            for block in blocks.values():
                block.close()
            raise
        return cls(
            run_id=run_id,
            index=index,
            primary=primary,
            blocks=blocks,
            owner=False,
        )

    # ------------------------------------------------------------------
    # Truy cập
    # ------------------------------------------------------------------

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def index(self) -> int:
        """Chỉ số tiến trình này, ghi vào `nguoi_ghi` khi nó publish."""
        return self._index

    @property
    def primary(self) -> bool:
        """Tiến trình này có được `publish()` không.

        ⭐ Nhận được một **hàm** thì hỏi hàm đó mỗi lần, không chụp lại một
        bản sao. Vai primary **đổi lúc chạy**: cha thăng cấp một con sống sót
        khi primary cũ chết, và con đó có thể **từ chối vai** rồi quay lại
        standby. Một bản sao chụp lúc dựng arena sẽ đứng yên qua cả hai lần
        đổi đó.

        📌 Đây là phát hiện **C3** của kiểm toán 0.8, và nó là mục nặng nhất
        trong ba mục CAO ban đầu: cờ *"tôi có phải primary"* nằm ở hai chỗ,
        `Application._is_primary` được cập nhật còn `RefDataArena._primary`
        thì **không có setter nào tồn tại**. Mà `RefData.publish()` hỏi đúng
        cái cờ không được cập nhật. Hậu quả: primary MỚI không bao giờ cập
        nhật được khoá JWT nữa - ca dùng số một của `RefData` - trong khi cha
        log *"took the primary role"* và `/healthz` trả `primary: true`.

        Sửa bằng cách bỏ hẳn bản sao thứ hai, không phải bằng cách thêm một
        setter và nhớ gọi nó ở hai nhánh. Cùng lập luận đã dùng cho **C4**:
        hai chỗ cùng quyết định một thứ thì sớm muộn lệch nhau.
        """
        p = self._primary
        return p() if callable(p) else p

    @property
    def tables(self) -> tuple[str, ...]:
        return tuple(self._blocks)

    def track(self, instance: RefData[Any]) -> None:
        """Ghi nhận một instance để `close()` bảo nó buông view trước.

        Cần vì `SharedMemory.close()` ném `BufferError` khi còn một lát cắt
        chưa thả. Arena là bên đóng vùng nhớ, nên nó phải là bên biết ai đang
        cầm gì - để nghĩa vụ đó cho từng lớp con tự nhớ là một nghĩa vụ sẽ bị
        quên, và quên thì tắt máy ném một lỗi không ai đọc ra nguyên nhân.
        """
        self._tracked.add(instance)

    def block(self, table: str) -> SharedMemory:
        try:
            return self._blocks[table]
        except KeyError:
            raise KeyError(
                f"refdata table {table!r} was never allocated. Declared: "
                f"{sorted(self._blocks)}. Tables are declared in "
                f"configure_refdata([...]) and the parent allocates them "
                f"before it builds DI."
            ) from None

    # ------------------------------------------------------------------
    # Dọn
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Trả vùng nhớ. Chỉ tiến trình **TẠO** mới `unlink`.

        ⚠ Con gọi `unlink` thì các con khác **không attach được nữa**, nên nó
        chỉ `close`. Trên Linux, vùng nhớ là một file thật trong `/dev/shm` nên
        thiếu bước này là để lại rác trong RAM; trên Windows nó biến mất khi
        handle cuối cùng đóng.
        """
        if self._closed:
            return
        self._closed = True
        for instance in list(self._tracked):
            instance.release()
        self._tracked.clear()
        for name, block in self._blocks.items():
            try:
                block.close()
                if self._owner:
                    block.unlink()
            except Exception:  # noqa: BLE001 - dọn dẹp phải best-effort
                _log.warning(
                    "refdata: could not release table %r", name, exc_info=True
                )
        self._blocks.clear()
