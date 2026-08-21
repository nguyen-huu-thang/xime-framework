"""Hai loại việc nằm ở hai class, đúng bảng bốn ô."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

_RUN_ONCE_LOG = Path("run_once.log")


class TickJob:
    """Việc *"chạy mãi, một lần cho cả cụm"* - ô (4), nay là adapter đơn nhất."""

    async def run(self) -> None:
        pass


class Migration:
    """Việc *"chạy một lần cho cả cụm"* - ô (2), nay là `run_once()`.

    Ghi ra file chứ không ghi vào bộ nhớ: phép đo phải nhìn thấy được **từ ngoài
    cả cụm**, và một biến trong RAM của primary thì tiến trình chạy test không
    đọc nổi.
    """

    async def post_construct(self) -> None:
        # Ô (1): mọi tiến trình, nhẹ. Có mặt để chứng minh hai hook TÁCH nhau.
        Path("post_construct.log").open("a").write(f"{os.getpid()} {time.time()}\n")

    async def run_once(self) -> None:
        """⚠ CHẬM có chủ ý.

        `run_once` chạy tức thì thì phép đo *"cha đợi nó xong rồi mới sinh con
        tiếp"* **không đo được gì** - gỡ hẳn bước đợi ra thì kết quả vẫn y hệt,
        vì con thứ hai dù sao cũng mất vài trăm mili giây để import. Một giây ở
        đây là thứ biến một lời hứa về **thứ tự** thành một thứ quan sát được.
        """
        await asyncio.sleep(1.0)
        _RUN_ONCE_LOG.open("a").write(f"{os.getpid()} {time.time()}\n")
