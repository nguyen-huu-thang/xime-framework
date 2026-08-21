"""Controller đủ để đo thăng cấp và watchdog từ bên ngoài."""

from __future__ import annotations

import os
import time
from pathlib import Path

from xime.adapters.web import get


class ProbeController:
    prefix = ""

    @get("/pid")
    async def pid(self) -> dict[str, int]:
        return {"pid": os.getpid()}

    @get("/die")
    async def die(self, pid: int = 0) -> dict[str, object]:
        """Chết đột ngột, không `finally` nào chạy - giống crash thật.

        ⚠ `pid=` là để phép đo **chọn đúng tiến trình trong một lời gọi**. Hỏi
        *"ai là primary"* rồi gọi `/die` ở lời gọi thứ hai là một cuộc đua: kernel
        chia request nên lời gọi thứ hai rơi vào con khác, và phép đo giết nhầm
        người - rồi vẫn xanh, vì nó chỉ kiểm rằng *có ai đó* đã chết.
        """
        if pid and pid != os.getpid():
            return {"pid": os.getpid(), "died": False}
        os._exit(9)

    @get("/block")
    async def block(self) -> dict[str, int]:
        """CHẶN event loop.

        Đây là cách hỏng mà `waitpid` và health check đều mù: tiến trình vẫn sống
        theo kernel, còn hỏi qua HTTP thì *chậm* không phân biệt được với *mạng
        chậm*. Watchdog trên loop thì im bặt ngay.
        """
        time.sleep(600)
        return {"pid": os.getpid()}

    @get("/break")
    async def break_adapter(self) -> dict[str, bool]:
        """Bật công tắc để một adapter hạng nhân bản ném lỗi trong `serve()`.

        Đây là ca F10 thứ ba: đã phục vụ rồi mới hỏng. Adapter đó phải bị **cô
        lập**, anh em phải sống tiếp, tiến trình phải sống tiếp, và cha phải
        **biết** - qua bus, không qua nhịp watchdog.
        """
        Path("break_me").write_text("1", encoding="utf-8")
        return {"armed": True}

    @get("/trap")
    async def trap(self) -> dict[str, bool]:
        """Cài bẫy: lần thăng cấp kế tiếp sẽ hỏng ở `start()`.

        Dựng lại ca thật của thiết kế - con B được thăng cấp, `start()` của
        `CertRotationJob` ném lỗi vì cert hỏng. Nó phải **từ chối vai**, không
        sập, và vẫn phục vụ HTTP bình thường.
        """
        Path("promote_must_fail").write_text("1", encoding="utf-8")
        return {"armed": True}
