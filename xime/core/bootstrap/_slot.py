"""Ô cấu hình mà framework ĐẨY vào adapter, và cách nhận diện một adapter.

> **Lời giải không phải thống nhất TÊN KHOÁ, mà là adapter THÔI BIẾT về khoá.**

```text
Hôm nay:         adapter  ->  runtime.get("mqtt")  ->  tự parse
Từ share_load(): framework đọc processes.<p>.<loại>.<id>  ->  ĐẨY ô vào adapter
```

Sau đó chỉ còn **một chỗ duy nhất** biết cách ánh xạ `(tiến trình, loại, id)` ra
cấu hình - và đó chính là điều kiện để khối `processes:` có nghĩa.

⚠ **Đây là phần nền của giai đoạn 3, chưa phải bản đầy đủ.** Giai đoạn 4 sẽ đưa
`adapter_id` lên Protocol, gỡ `host`/`port`/`ssl` khỏi constructor, và bắt mọi
adapter nhận ô này. Ở giai đoạn 3, `assign_slot()` là **tuỳ chọn**: adapter nào
chưa có thì framework nổ ngay khi thấy nó trong một khối `processes:`, thay vì
im lặng để nó tự đọc YAML và bind nhầm cổng.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Any, Final, Protocol, runtime_checkable

from xime.core.bootstrap._processes import EndpointSpec, topology_error

# Ba cách một điểm phục vụ dùng chung được một địa chỉ. Adapter tự khai, vì chỉ
# nó biết thư viện bên dưới nhận socket từ ngoài hay không.
SHARE_INHERIT: Final[str] = "inherit"
"""Cha `bind()` + `listen()` rồi truyền socket xuống con (web, unix socket)."""

SHARE_REUSEPORT: Final[str] = "reuseport"
"""Mỗi con tự bind, kernel chia tải (`SO_REUSEPORT`). Linux thôi - gRPC."""

SHARE_NONE: Final[str] = "none"
"""Không dùng chung được. Mặc định: khai `shared: true` cho nó là lỗi khởi động."""


@dataclass(frozen=True)
class AdapterSlot:
    """Ô của một adapter trong một tiến trình cụ thể.

    Attributes:
        process_id: id tiến trình đang chạy. ⚠ **Không phơi ra cho code nghiệp
            vụ** - có `current_process_id()` công khai thì sớm muộn sẽ có người
            viết `if process_id == "main"` trong use case, và N tiến trình chạy
            N nhánh code khác nhau. Adapter được biết vì nó cần để log.
        primary: tiến trình này có phải primary không.
        spec: ô YAML đã phân giải (host, port, path, shared, và nguyên văn).
        sock: socket **cha đã bind sẵn**, hoặc `None` khi adapter tự bind.
            `None` xảy ra ở hai ca rất khác nhau - không dùng chung địa chỉ, và
            chạy tay một con để gỡ lỗi (`XIME_PROCESS_ID=api-2 python -m
            app.main`) - nhưng adapter làm **cùng một việc** ở cả hai, nên gộp
            là đúng chứ không phải một giá trị hai nghĩa.
    """

    process_id: str
    primary: bool
    spec: EndpointSpec
    sock: socket.socket | None = None
    single: bool = False

    @property
    def where(self) -> str:
        """Vị trí trong file cấu hình, dùng cho thông báo lỗi.

        Một chỗ duy nhất sinh chuỗi này, vì hai nhánh có hai tiền tố khác
        nhau (`process.` và `processes.<id>.`) và một thông báo chỉ sai
        tiền tố là một thông báo dẫn người đọc tới nhầm khoá.
        """
        head = "process" if self.single else f"processes.{self.process_id}"
        return f"{head}.{self.spec.kind}.{self.spec.adapter_id}"


@runtime_checkable
class SlotAware(Protocol):
    """Adapter nhận được ô cấu hình do framework đẩy vào.

    Framework gọi `assign_slot()` **trước** `start()`, và chỉ ở nhánh
    `share_load()`. App không gọi `share_load()` thì không adapter nào nhận ô
    nào, và đường chạy y hệt hôm nay - đó là thứ giữ cho 31 codebase hiện tại
    không phải sửa một dòng.
    """

    adapter_kind: str
    share_port_by: str

    def assign_slot(self, slot: AdapterSlot) -> None:
        """Nhận ô cấu hình. Adapter nào thấy mình bị truyền cổng trong code thì
        **nổ ở đây** - hai nguồn cho một giá trị là chỗ để lệch, và *người vận
        hành sửa YAML mà cổng không đổi* là loại lỗi tốn cả buổi."""
        ...


def adapter_kind_of(adapter: object) -> str:
    """Loại của một adapter - khoá tầng hai trong khối `processes:`.

    Khai bằng thuộc tính class chứ không suy từ tên class. Suy từ tên thì đúng
    cho cả sáu adapter hiện có (`WebAdapter` -> `web`), nhưng nó khoá tên khoá
    YAML vào tên class, nên đổi tên class là đổi cấu hình của mọi người dùng -
    một ràng buộc không ai khai và không gì canh.

    ⛔ Bản đầu của docstring này ghi lý do là *"adapter người dùng tự viết thì
    không suy được"*. **Câu đó sai kể từ 2026-09-01**: chủ dự án chốt viết adapter
    KHÔNG phải điểm mở rộng công khai - sáu adapter đi kèm framework là sáu cái
    có, và thêm cái mới là việc của framework. Tài liệu ở `docs/` đã sửa theo.
    """
    kind = getattr(adapter, "adapter_kind", None)
    if isinstance(kind, str) and kind:
        return kind
    raise topology_error(
        "Adapter Without adapter_kind",
        f"Adapter: {type(adapter).__name__}",
        "Detail : share_load() maps every adapter onto a "
        "processes.<process>.<kind>.<id> block, so each adapter class must "
        "declare a class attribute `adapter_kind` (for example \"web\").",
    )


def adapter_id_of(adapter: object) -> str:
    """Id của một adapter - khoá tầng ba trong khối `processes:`.

    `adapter_id` là thành viên Protocol từ 0.8, và `Application.use()` đã kiểm
    nó trước khi adapter vào danh sách - nên tới đây nó chắc chắn hợp lệ. Giữ
    phép kiểm phòng hờ cho đường gọi trực tiếp trong test.
    """
    value = getattr(adapter, "adapter_id", None)
    if isinstance(value, str) and value:
        return value
    raise topology_error(
        "Adapter Without An Id",
        f"Adapter: {type(adapter).__name__}",
        "Detail : share_load() needs an id to look up "
        "processes.<process>.<kind>.<id>.",
    )


def share_strategy_of(adapter: object) -> str:
    """Cách adapter này dùng chung được một địa chỉ với tiến trình khác."""
    value = getattr(adapter, "share_port_by", SHARE_NONE)
    if value in (SHARE_INHERIT, SHARE_REUSEPORT, SHARE_NONE):
        return str(value)
    raise topology_error(
        "Invalid share_port_by",
        f"Adapter: {type(adapter).__name__}",
        f"Value  : {value!r}",
        f"Expected: one of {SHARE_INHERIT!r}, {SHARE_REUSEPORT!r}, "
        f"{SHARE_NONE!r}.",
    )


def describe(adapter: object) -> str:
    """Nhãn ngắn dùng trong log và thông báo lỗi."""
    try:
        return f"{adapter_kind_of(adapter)}.{adapter_id_of(adapter)}"
    except Exception:  # noqa: BLE001 - nhãn cho thông báo lỗi, không được tự nổ
        return type(adapter).__name__


def slot_options(slot: AdapterSlot) -> dict[str, Any]:
    """Nguyên văn ô YAML, dạng dict chép ra để adapter tự do đọc."""
    return dict(slot.spec.options)
