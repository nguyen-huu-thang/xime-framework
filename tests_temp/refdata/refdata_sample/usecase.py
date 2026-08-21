"""Use case mẫu: inject bảng THẲNG, có kiểu - đúng như tài liệu hướng dẫn."""

from __future__ import annotations

from .tables import JwtKeyRefData, KeySet


class KeyLookupFailed(Exception):
    """Khoá chưa sẵn sàng - khác hẳn 'không có khoá nào'."""


class VerifyTokenUseCase:
    def __init__(self, keys: JwtKeyRefData) -> None:
        self._keys = keys

    def public_key(self, kid: str) -> str:
        keyset = self._keys.read()
        if keyset is None:
            # ⭐ Nhánh này là lý do `None` phải khác *tập rỗng*: nếu hai thứ đó
            # trả về giống nhau thì ở đây ta hoặc từ chối oan mọi token, hoặc
            # tệ hơn là cho qua vì tưởng "không có khoá nào để kiểm".
            raise KeyLookupFailed("key set is not ready yet")
        found = keyset.resolve(kid)
        if found is None:
            raise LookupError(f"unknown kid {kid!r}")
        return found

    async def rotate(self, keyset: KeySet) -> int:
        return await self._keys.publish(keyset)
