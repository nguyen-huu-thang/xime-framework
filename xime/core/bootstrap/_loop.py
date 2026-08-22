"""Chọn hiện thực event loop cho tiến trình đang chạy.

Tách khỏi `_supervisor.py` có chủ đích: quyết định *"dùng loop nào"* áp cho
**mọi** tiến trình Xime, kể cả app không bao giờ gọi `share_load()`. Đặt nó cạnh
supervisor là buộc một nhánh không cần `multiprocessing` phải import nó.

## Vì sao module này tồn tại

`pip install xime[web]` kéo `uvicorn[standard]`, mà extra đó khai sẵn `uvloop`
với marker nền tảng. Nên trên **mọi cài đặt Linux chuẩn, uvloop đã nằm trên
đĩa** - và trước 0.8.1 nó **chưa bao giờ chạy**:

```text
uvicorn/server.py
├─ run()    → asyncio_run(self.serve(), loop_factory=config.get_loop_factory())
└─ serve()  → không đụng get_loop_factory()          ← đường Xime đi
```

Xime tự sở hữu event loop (`Application.run()` gọi `asyncio.run`) nên nó gọi
thẳng `Server.serve()`. Đường cài uvloop của uvicorn không nằm trên đường đi,
trong khi `httptools` và `websockets` thì lại chạy thật vì chúng được chọn bên
trong `config.load()`.

⭐ Ba cơ chế đó **trông giống hệt nhau từ ngoài** - cùng khuôn `auto.py`, cùng
kiểu `try: import X except ImportError`. Nhìn `pip list` thấy đủ bốn gói tăng
tốc rồi kết luận *"đã bật"* là sai, và **không có gì báo**. Đó là lý do
`Application._log_running_loop()` log thứ **đang chạy thật** thay vì log ý định.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def uvloop_factory() -> Callable[[], Any] | None:
    """Return uvloop's loop factory when it is importable, otherwise ``None``.

    ``None`` means "let ``asyncio.run`` decide", which is exactly what every
    release before 0.8.1 did. uvloop ships no Windows wheel and never will, so
    on Windows this returns ``None`` by construction rather than by policy.

    Trả ``None`` nghĩa là *"để `asyncio.run` tự quyết"*, tức đúng hành vi của mọi
    bản trước 0.8.1. uvloop không có wheel Windows và sẽ không bao giờ có, nên ở
    đó hàm này trả ``None`` **do bản chất**, không do một luật nào của Xime.

    ⛔ Cố ý **không** dùng `uvloop.install()`: đó là API cũ, nó sửa chính sách
    toàn cục của asyncio thay vì cấp một factory cho đúng một lời gọi
    `asyncio.run`. `loop_factory` là đường uvloop khuyến nghị và là đường duy
    nhất ghép được với cách Xime sở hữu loop.

    ⛔ Cũng cố ý **không có công tắc bật/tắt**. Có uvloop thì dùng, không có thì
    thôi; muốn tắt thì `pip uninstall uvloop`. Một khoá cấu hình cho việc này là
    thêm bề mặt API cho một nhánh code chưa ai cần, và người vận hành không có
    đủ thông tin để chọn giá trị (xem `rules/config-discovery.md`).
    """
    try:
        import uvloop
    except ImportError:
        return None
    return uvloop.new_event_loop
