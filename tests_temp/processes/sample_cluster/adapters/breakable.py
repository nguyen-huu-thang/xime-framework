"""Adapter hạng nhân bản biết tự hỏng **sau khi đã phục vụ** - để đo F10.

Ranh giới mà P1 (tách `start()` khỏi `serve()`) biến từ mong muốn thành thứ cưỡng
chế được:

| Lỗi ném ra từ | Nghĩa | Xử lý |
|---|---|---|
| `start()` lúc khởi động | chưa phục vụ được | **SẬP** cả tiến trình |
| `start()` lúc thăng cấp | không nhận được vai | **từ chối vai**, không sập |
| `serve()` | đã phục vụ rồi mới hỏng | **CÔ LẬP** adapter đó |

Adapter này lo vế thứ ba: `serve()` chờ một cái công tắc, và khi công tắc bật thì
nó ném lỗi. Anh em phải sống tiếp, tiến trình phải sống tiếp, và cha phải **biết**.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from xime.core.bootstrap.adapter import SCALING_REPLICATED, Adapter

if TYPE_CHECKING:
    from xime.core.bootstrap.application import Application

TRIGGER = Path("break_me")


class BreakableAdapter(Adapter, scaling=SCALING_REPLICATED):
    adapter_kind = "breakable"

    def __init__(self) -> None:
        self.adapter_id = "default"
        self._slot: object | None = None
        self._stopped = asyncio.Event()

    def assign_slot(self, slot: object) -> None:
        self._slot = slot

    async def start(self, app: Application) -> None:
        pass

    async def serve(self) -> None:
        while not self._stopped.is_set():
            if TRIGGER.exists():
                raise RuntimeError("kênh nội bộ đứt")
            try:
                await asyncio.wait_for(self._stopped.wait(), 0.2)
            except TimeoutError:
                continue

    async def stop(self) -> None:
        self._stopped.set()
