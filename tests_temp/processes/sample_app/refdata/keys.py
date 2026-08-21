"""Một bảng tham chiếu tối thiểu, khai đúng như tài liệu hướng dẫn."""

from __future__ import annotations

import json

from xime.core.refdata import RefData


class KeyTable(RefData[dict], name="keys", max_bytes=4096):
    """Đứng thay chỗ tập khoá verify JWT trong đời thật."""

    def encode(self, value: dict) -> bytes:
        return json.dumps(value).encode("utf-8")

    def decode(self, raw: memoryview) -> dict:
        return json.loads(bytes(raw).decode("utf-8"))
