"""Hai decorator khai handler, và phép gom chúng lúc khởi động.

Hai decorator chứ không một, vì đó là hai **hợp đồng** khác nhau: chúng khác ở
**kiểu trả về**, nên viết sai là lỗi kiểu chứ không phải lỗi lúc chạy.

📌 Chủ dự án ghi nhận không thích dạng `@` (framework đã bỏ `@service`,
`@component` từ đầu). Chấp nhận ở đây với lý do: decorator này **chỉ ghi vào một
thuộc tính của hàm**, không phải proxy hay AOP, nên đổi sang cách khác về sau là
đổi đúng một chỗ.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from xime.core.exception.framework import StartupException

_MARK: Final[str] = "__xime_link__"

ANNOUNCE: Final[str] = "announce"
REQUEST: Final[str] = "request"


def on_announce(channel: str) -> Callable[[Any], Any]:
    """Nhận tin broadcast trên `channel`. Không ai chờ trả lời.

    ```python
    @on_announce("cauhinh")
    async def cau_hinh_doi(self, key: str, payload: bytes) -> None: ...
    ```

    Handler ném lỗi thì framework **log rồi đi tiếp** - không có ai chờ, và bit
    đã hạ nên tin không quay lại.
    """
    return _mark(ANNOUNCE, channel)


def on_request(channel: str) -> Callable[[Any], Any]:
    """Nhận lệnh trên `channel`, và trả lời.

    ```python
    @on_request("fieldbus")
    async def dieu_khien(self, key: str, payload: bytes) -> bytes | None:
        if key not in self.thiet_bi_cua_toi:
            return None                 # chưa hề chạm vào payload
        ...
        return b"ok"
    ```

    **Trả `None` chính là cách nói "không phải của tôi"** - framework chỉ hạ bit
    và không ghi người nhận. Không ai trả khác `None` cho tới lúc người hỏi hết
    giờ thì kết cục là `NoOwner`, tức *lỗi cấu hình, đừng thử lại*. Cơ chế bốn
    kết cục chạy mà không cần thêm khái niệm nào.

    ⚠ **Handler phải nhanh.** Việc lâu thì nhét vào hàng đợi của app rồi trả về
    ngay. Handler treo **sau khi đã hạ bit nhưng trước khi ghi người nhận** làm
    người hỏi thấy `NoOwner` - tức *"sửa cấu hình"* - trong khi sự thật là *"tiến
    trình kia đang treo"*.
    """
    return _mark(REQUEST, channel)


def _mark(kind: str, channel: str) -> Callable[[Any], Any]:
    if not channel:
        raise ValueError("link handler channel must be a non-empty name")

    def decorate(fn: Any) -> Any:
        if not inspect.iscoroutinefunction(fn):
            raise StartupException(
                f"\nLink Handler Must Be Async\n"
                f"  Handler: {getattr(fn, '__qualname__', fn)!r}\n"
                f"  Channel: {channel!r}\n"
                f"  Detail : the channel loop awaits it, so it has to be "
                f"'async def'. A blocking handler would stall the whole channel."
            )
        setattr(fn, _MARK, (kind, channel))
        return fn

    return decorate


@dataclass(frozen=True)
class BoundHandler:
    """Một method đã gắn với instance lấy từ DI, sẵn sàng chạy."""

    channel: str
    kind: str
    call: Callable[[str, bytes], Any]
    owner: str


def collect(instances: list[object]) -> dict[str, BoundHandler]:
    """Gom handler từ các instance, một kênh đúng một handler.

    Vì sao một kênh một handler: nhiều handler thì phải trả lời *"ai được nhận"*,
    mà câu đó lại phụ thuộc thứ chỉ biết lúc chạy - đúng cái vòng vừa thoát ra
    khi bỏ định tuyến theo tên tiến trình. Muốn nhiều nhánh thì handler tự phân
    nhánh.
    """
    found: dict[str, BoundHandler] = {}
    for instance in instances:
        for _, member in inspect.getmembers(instance, inspect.ismethod):
            mark = getattr(member, _MARK, None)
            if mark is None:
                continue
            kind, channel = mark
            owner = f"{type(instance).__name__}.{member.__name__}"
            existing = found.get(channel)
            if existing is not None:
                raise StartupException(
                    f"\nTwo Handlers On One Link Channel\n"
                    f"  Channel : {channel!r}\n"
                    f"  Handlers: {existing.owner}, {owner}\n"
                    f"  Detail  : one channel takes exactly one handler. With two, "
                    f"the framework would have to answer 'which one gets it', and "
                    f"that answer depends on things only known at runtime.\n"
                    f"  Fix     : branch inside a single handler, or split the "
                    f"channel in two."
                )
            found[channel] = BoundHandler(
                channel=channel, kind=kind, call=member, owner=owner
            )
    return found
