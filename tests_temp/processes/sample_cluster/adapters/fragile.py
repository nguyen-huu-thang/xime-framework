"""Một adapter hạng đơn nhất **do ứng dụng khai** - và nó biết cách hỏng.

Nó dựng lại ca thật của thiết kế mục 4.4: con B được thăng cấp, `start()` ném lỗi
vì cert hỏng. Nó phải **từ chối vai, không sập**, và vẫn phục vụ HTTP bình thường.
Áp nguyên luật *"lỗi trong start() thì sập"* thì B sập, cha thăng cấp C, C sập -
đúng domino, và mất ba tiến trình đang phục vụ người dùng thật vì một cái cert.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING

from xime.core.bootstrap.adapter import SCALING_SINGLETON, Adapter

if TYPE_CHECKING:
    from xime.core.bootstrap.application import Application

TRAP = Path("promote_must_fail")
STARTED_LOG = Path("singleton_started.log")


class FragileAdapter(Adapter, scaling=SCALING_SINGLETON):
    adapter_kind = "fragile"

    def __init__(self) -> None:
        self.adapter_id = "default"
        self._stopped = asyncio.Event()
        self._slot: object | None = None

    def assign_slot(self, slot: object) -> None:
        """Nhận ô cấu hình. Adapter này không mở cổng nào nên nó không dùng tới,
        nhưng **mọi** adapter đều phải nhận được một ô từ 0.8."""
        self._slot = slot

    async def start(self, app: Application) -> None:
        if TRAP.exists():
            TRAP.unlink()
            raise RuntimeError("cert hỏng - không nhận vai được")
        STARTED_LOG.open("a").write(f"{os.getpid()}\n")

    async def serve(self) -> None:
        await self._stopped.wait()

    async def stop(self) -> None:
        self._stopped.set()
