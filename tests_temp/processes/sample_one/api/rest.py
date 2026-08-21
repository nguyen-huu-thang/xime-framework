"""Controller tối thiểu: nói ra ai đang trả lời, và biết tự chết theo yêu cầu."""

from __future__ import annotations

import os

from xime.adapters.web import get


class PidController:
    prefix = ""

    @get("/pid")
    async def pid(self) -> dict[str, int]:
        """Hai tiến trình phục vụ chung một cổng thì hai pid khác nhau trả lời."""
        return {"pid": os.getpid()}

    @get("/die")
    async def die(self) -> dict[str, int]:
        """Chết ngay lập tức, không dọn dẹp - để đo việc cha dựng lại con.

        `os._exit` chứ không phải `sys.exit`: cần một cái chết đột ngột giống
        crash thật, không chạy `finally` nào.
        """
        os._exit(9)
