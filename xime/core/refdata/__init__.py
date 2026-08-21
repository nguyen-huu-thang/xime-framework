"""Kho tham chiếu liên tiến trình - `RefData`.

Dành cho dữ liệu **có nguồn bền vững**: khoá JWT lấy từ Trust, danh bạ app,
cấu hình đã phân giải. Đọc rất nhiều, ghi rất hiếm, và mỗi lần ghi là **thay
trọn gói**. Mất thì nạp lại được.

⚠⚠ **Không phải `Store`** (`xime.starters.lmdb`). Ranh giới là **dữ liệu có
nguồn bền vững hay không**, và chọn nhầm thì hỏng theo hai kiểu ngược nhau:

| | **`RefData`** (chỗ này) | `Store` (LMDB) |
|---|---|---|
| Ví dụ | khoá JWT · danh bạ app | hãm nhịp · thử thách passkey |
| Mất thì | **nạp lại được** | **mất hẳn** |
| Ghi | hiếm, **thay trọn gói** | thường xuyên, sửa từng khoá |
| Ai ghi | **chỉ primary** | mọi tiến trình |
| Phép nguyên tử (`incr`) | không có, không cần | **có** |

⛔ Phạm vi là **MỘT máy, luôn luôn**. Nhiều máy đã giải bằng chia shard.

```python
# app/refdata/jwt_keys.py
from xime.core.refdata import RefData

class JwtKeyRefData(RefData[JwtKeySet], name="jwt-keys", max_bytes=65536):
    def encode(self, value: JwtKeySet) -> bytes: ...
    def decode(self, raw: memoryview) -> JwtKeySet: ...

# config/refdata.py
from xime.core.refdata import configure_refdata

from app.refdata.jwt_keys import JwtKeyRefData

configure_refdata([JwtKeyRefData])

# nơi ghi - CHỈ primary, thường trong run_once()
await self._keys.publish(keyset_moi)

# nơi đọc - MỌI tiến trình
keys = self._keys.read()          # None = CHƯA SẴN SÀNG, khác tập rỗng
keys = self._keys.read_or_fail()  # chưa sẵn sàng thì ném
```

Tài liệu người dùng: `docs/{vn,en}/refdata.md`.
"""

from ._arena import RefDataArena, TableSpec, block_name, new_run_id, specs_of
from ._config import configure_refdata, refdata_registry
from ._errors import (
    RefDataClosedError,
    RefDataError,
    RefDataLayoutMismatch,
    RefDataNotReadyError,
    RefDataNotWriterError,
    RefDataTooLargeError,
    RefDataTornError,
)
from ._layout import RefDataLayout
from ._refdata import DEFAULT_MAX_BYTES, MAX_SPINS, RefData
from ._stats import RefDataStats

# ⚠ `__all__` ở đây KHÔNG phục vụ DI scanner (không ai `dependency.scan` vào
# core), nên nó thuần tuý là danh sách export. Khác hẳn `__all__` của một
# package starter - xem ghi chú trong `xime/starters/lmdb/__init__.py`.
__all__ = [
    "RefData",
    "RefDataArena",
    "RefDataLayout",
    "RefDataStats",
    "TableSpec",
    "configure_refdata",
    "refdata_registry",
    "specs_of",
    "block_name",
    "new_run_id",
    "DEFAULT_MAX_BYTES",
    "MAX_SPINS",
    "RefDataLayoutMismatch",
    "RefDataClosedError",
    "RefDataError",
    "RefDataNotReadyError",
    "RefDataNotWriterError",
    "RefDataTooLargeError",
    "RefDataTornError",
]
