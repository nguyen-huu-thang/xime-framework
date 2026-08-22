"""Có thư viện WebSocket nào cho uvicorn dùng không.

## Vì sao cần một module cho một câu hỏi nhỏ như vậy

`uvicorn/protocols/websockets/auto.py` đặt `AutoWebSocketsProtocol = None` khi
**không có cả** `websockets` lẫn `wsproto`. Lúc đó mọi route `@ws` của Xime
**chết lặng**: bắt tay không thành, và không một dòng log nào của Xime giải thích
vì sao - người viết app chỉ thấy trình duyệt báo kết nối hỏng.

`xime[web]` kéo `uvicorn[standard]` nên đường cài chuẩn được phủ. Đường **không**
phủ được, và là lý do module này tồn tại: ai cài `uvicorn` trần rồi cài `xime`
không kèm extra.

⭐ Cùng khuôn với cảnh báo `@rpc` của 0.7.2 và với cảnh báo *"có route WebSocket
mà chưa gọi `configure_jwt()`"* ngay cạnh đây: **chỉ kêu khi app thật sự có thứ
đó**. Kêu ở mọi app là một cảnh báo giả cho đa số, mà *phép dò kêu oan là phép dò
sẽ bị tắt*.

⛔ **Cảnh báo, KHÔNG nổ.** Nổ lúc khởi động là biến một app đang chạy thành một
app từ chối chạy, vì một thư viện mà đường cài chuẩn vốn đã kéo về. Người dùng
cần biết, không cần bị chặn.
"""

from __future__ import annotations

import logging

_log = logging.getLogger("xime.web.ws")

_HUONG_DAN = (
    'pip install "xime[web]"   (hoặc: pip install "uvicorn[standard]")'
)


def websocket_library_missing() -> bool:
    """``True`` khi uvicorn không tìm được thư viện WebSocket nào.

    Hỏi thẳng `AutoWebSocketsProtocol` thay vì thử `import websockets`: đó là
    **thứ uvicorn thật sự dùng**, và nó chấp cả `websockets` lẫn `wsproto`. Tự
    liệt kê tên gói ở đây là dựng một danh sách thứ hai phải bảo trì, và nó sẽ
    lệch với danh sách của uvicorn vào một ngày không ai để ý.
    """
    try:
        from uvicorn.protocols.websockets.auto import AutoWebSocketsProtocol
    except ImportError:
        # uvicorn quá cũ hoặc bị cắt xén tới mức không còn module đó - không kết
        # luận được là "có", nên xử lý như thiếu.
        return True
    return AutoWebSocketsProtocol is None


def warn_if_websocket_library_missing(route_count: int) -> bool:
    """Kêu khi app có route `@ws` mà không có thư viện nào chạy được chúng.

    Args:
        route_count: số route `@ws` đã đăng ký. Người gọi phải bảo đảm nó > 0 -
            đó chính là điều kiện *"chỉ kêu khi thật sự có `@ws`"*.

    Returns:
        ``True`` nếu đã cảnh báo. Trả về giá trị thay vì `None` để test khẳng
        định được **cả hai** nhánh: thiếu thì kêu, đủ thì im.
    """
    if not websocket_library_missing():
        return False
    _log.warning(
        "%d WebSocket route(s) registered but uvicorn has no WebSocket "
        "implementation available (neither 'websockets' nor 'wsproto'), so "
        "every handshake on them will fail with nothing else logged. Install "
        "one with:  %s",
        route_count,
        _HUONG_DAN,
    )
    return True
