"""Scheduler là một **adapter hạng đơn nhất**, không phải một singleton DI.

⚠⚠ Trước 0.8, `SchedulerRunner` khởi động vòng lặp lịch trong `post_construct`,
tức nó chạy ở **mọi tiến trình**. Với một tiến trình thì đúng; với bốn thì job
nhắc email gửi bốn lần và con trỏ đồng bộ bị tiến bốn lần - đúng hạng *"chạy hai
lần thì SAI"* của luật 01.

Chỗ sai nằm ở **bảng bốn ô** chốt 2026-08-18: việc *"chạy mãi, một lần cho cả
cụm"* đang ở nhà của việc *"chạy một lần, ở mọi tiến trình"*.

| | Mọi tiến trình | Một lần cho cả cụm |
|---|---|---|
| **Chạy một lần rồi thôi** | `post_construct()` | `run_once()` |
| **Chạy mãi** | `Adapter.start()` | **`scaling="singleton"`** ← đây |

⭐ Nhờ ô cuối mà **không cần cờ nào trong object**: framework chỉ `start()` nó ở
primary, và một object không được gọi thì không chạy. Khác hẳn phương án cờ, nơi
**mỗi object phải nhớ tự kiểm** và quên một chỗ là chạy nhầm ở bốn tiến trình,
im lặng.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from xime.core.bootstrap.adapter import SCALING_SINGLETON, Adapter

if TYPE_CHECKING:
    from xime.core.bootstrap.application import Application

    from ._runner import SchedulerRunner


class SchedulerAdapter(Adapter, scaling=SCALING_SINGLETON):
    """Bọc `SchedulerRunner` vào vòng đời adapter.

    Framework tự đăng ký nó khi ứng dụng đã gọi `configure_scheduler()`, nên
    không app nào phải thêm một dòng `app.use(...)`. Đây là chỗ **giữ nguyên**
    hành vi cũ: trước 0.8 scheduler cũng tự có mặt khi được cấu hình.
    """

    adapter_kind = "scheduler"

    def __init__(self, runner: SchedulerRunner) -> None:
        self.adapter_id = "default"
        self._runner = runner
        self._stopped = asyncio.Event()

    async def start(self, app: Application) -> None:
        """Dựng scheduler và đăng ký job. Lỗi ở đây thì **sập** - đúng ý muốn:
        một job khai sai là lỗi cấu hình, không phải sự cố lúc chạy."""
        await self._runner.post_construct()

    async def serve(self) -> None:
        """Chờ tới khi bị dừng.

        ⚠ Vòng lặp lịch **không chạy ở đây**: `start_in_background()` đã giao nó
        cho task group của chính APScheduler. Cố kéo nó về đây là dựng lại đúng
        lỗi đua đã vá ở 0.7.1 - xem docstring `SchedulerRunner`.
        """
        await self._stopped.wait()

    async def stop(self) -> None:
        self._stopped.set()
        await self._runner.pre_destroy()
