"""Bảng tham chiếu của một app mẫu - khai đúng như tài liệu hướng dẫn."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from xime.core.refdata import RefData


@dataclass(frozen=True)
class KeySet:
    """Một tập khoá verify, giống thứ `TrustKeyProvider` giữ trong đời thật."""

    keys: dict[str, str] = field(default_factory=dict)

    def resolve(self, kid: str | None) -> str | None:
        return self.keys.get(kid) if kid is not None else None


class JwtKeyRefData(RefData[KeySet], name="jwt-keys", max_bytes=4096):
    """Khoá verify JWT - **có nguồn bền vững** (Trust), nên nó thuộc nhóm 1."""

    def encode(self, value: KeySet) -> bytes:
        return json.dumps(value.keys).encode("utf-8")

    def decode(self, raw: memoryview) -> KeySet:
        return KeySet(json.loads(bytes(raw).decode("utf-8")))


class AppRegistryRefData(RefData[list], name="app-registry", max_bytes=2048):
    """Danh bạ app - bảng thứ hai, để kiểm chuyện mỗi bảng một vùng nhớ riêng."""

    def encode(self, value: list) -> bytes:
        return json.dumps(value).encode("utf-8")

    def decode(self, raw: memoryview) -> list:
        return json.loads(bytes(raw).decode("utf-8"))


class RawRefData(RefData, name="raw", max_bytes=512):
    """Không khai kiểu - bytes vào, bytes ra, đúng như mặc định của lớp nền."""
