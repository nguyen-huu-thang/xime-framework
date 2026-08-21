"""Controller tối thiểu: nói ra ai đang trả lời, và biết tự chết theo yêu cầu."""

from __future__ import annotations

import os

from xime.adapters.web import get
from xime.core.refdata import RefDataArena

from sample_app.refdata.keys import KeyTable


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


class RefDataController:
    """Đo phần nối `RefData` vào mô hình đa tiến trình.

    Nó trả lời được câu mà mọi test khác của `RefData` **không** trả lời được:
    cha có thật sự cấp vùng nhớ trước khi sinh con không, và con có attach vào
    ĐÚNG vùng đó không. Mọi test kia hoặc chạy một tiến trình, hoặc tự dựng
    arena bằng tay - cả hai đều đi vòng qua chính đoạn nối đang cần đo.
    """

    prefix = ""

    def __init__(self, keys: KeyTable, arena: RefDataArena) -> None:
        self._keys = keys
        self._arena = arena

    @get("/refdata")
    async def read(self) -> dict:
        return {
            "pid": os.getpid(),
            "primary": self._arena.primary,
            "index": self._arena.index,
            "value": self._keys.read(),
            "generation": self._keys.generation,
        }

    @get("/publish")
    async def publish(self) -> dict:
        """Chỉ primary publish được; con khác trả về nguyên trạng, không nổ.

        Kernel chia request nên bên gọi phải hỏi vài lần mới trúng primary -
        đó chính là thứ đang được đo.
        """
        if not self._arena.primary:
            return {"pid": os.getpid(), "primary": False, "published": False}
        generation = await self._keys.publish({"kid": "k1", "pem": "pem-1"})
        return {"pid": os.getpid(), "primary": True, "published": True,
                "generation": generation}
