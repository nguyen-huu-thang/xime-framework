"""Bus liên tiến trình - `ProcessLink`.

⚠⚠ **KHÔNG phải `EventBus`.** Hai thứ khác nhau hoàn toàn, không dùng chung một
dòng code nào, và gọi nhầm thì **không có triệu chứng**: tin không bao giờ ra
khỏi tiến trình, không lỗi, không log. Tên cố ý không chung gốc từ.

| | `EventBus` (`core/event/`) | **`ProcessLink`** |
|---|---|---|
| Phạm vi | trong MỘT tiến trình | **GIỮA các tiến trình** |
| Chở gì | object Python | **bytes** |
| Chở loại gì | **event** - đã xảy ra rồi, ai quan tâm thì nghe | **lệnh và câu hỏi** - có đích, có thể chờ trả lời |
| Phản hồi | không có | **có** (`ask`) |
| Handler chạy | song song | **tuần tự theo kênh** |

Ranh giới thực dụng: **thứ 4 KB không đủ chứa thì đó là dữ liệu, không phải tín
hiệu** - dữ liệu đi qua kho (`xime.starters.lmdb`) hoặc vùng nhớ tham chiếu.

```python
# config/link.py
from xime.core.link import ChannelSpec, configure_link
from app.link.fieldbus import FieldbusHandler

configure_link(
    channels={"fieldbus": ChannelSpec(rows=256, payload_bytes=512)},
    handlers=[FieldbusHandler],
)

# app/link/fieldbus.py
from xime.core.link import on_request

class FieldbusHandler:
    def __init__(self, modbus: ModbusClient, cfg: RuntimeConfig) -> None:
        self._devices = cfg.get("...")        # khoá đến từ CẤU HÌNH

    @on_request("fieldbus")
    async def control(self, key: str, payload: bytes) -> bytes | None:
        if key not in self._devices:
            return None                       # chưa hề chạm vào payload
        ...
        return b"ok"

# nơi gửi
match await link.ask("fieldbus", key="BT-01", payload=b"stop"):
    case Done(value):    ...
    case NoOwner():      ...   # lỗi CẤU HÌNH, đừng thử lại
    case NoAnswer():     ...   # xem tiến trình kia còn sống không
    case Failed(detail): ...   # lỗi nghiệp vụ
```
"""

from ._cleanup import sweep_orphans
from ._config import INTERNAL_CHANNEL, ChannelSpec, configure_link, link_registry
from ._decorators import BoundHandler, collect, on_announce, on_request
from ._errors import LinkError, LinkLayoutMismatch
from ._link import ProcessLink
from ._outcome import Done, Failed, NoAnswer, NoOwner, Outcome
from ._stats import ChannelStats, LinkMessage, LinkStats, RawRow, ReaderStats

# ⚠ `__all__` ở đây KHÔNG phục vụ DI scanner (không ai `dependency.scan` vào
# core), nên nó thuần tuý là danh sách export. Khác hẳn `__all__` của một package
# starter - xem ghi chú trong `xime/starters/lmdb/__init__.py`.
__all__ = [
    "ProcessLink",
    "LinkError",
    "LinkLayoutMismatch",
    "ChannelSpec",
    "configure_link",
    "link_registry",
    "INTERNAL_CHANNEL",
    "on_announce",
    "on_request",
    "BoundHandler",
    "collect",
    "Done",
    "NoOwner",
    "NoAnswer",
    "Failed",
    "Outcome",
    "LinkMessage",
    "LinkStats",
    "ChannelStats",
    "ReaderStats",
    "RawRow",
    "sweep_orphans",
]
