"""Hai controller, mỗi cái gắn vào một server web của cùng một tiến trình."""

from __future__ import annotations

import os

from xime.adapters.web import get


class PublicController:
    prefix = ""
    server_id = "public"

    @get("/pid")
    async def pid(self) -> dict[str, int]:
        return {"pid": os.getpid()}


class AdminController:
    prefix = ""
    server_id = "admin"

    @get("/pid")
    async def pid(self) -> dict[str, int]:
        """Cổng khác, cùng tiến trình - nên cùng pid."""
        return {"pid": os.getpid()}
