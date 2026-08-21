# Dữ liệu tham chiếu dùng chung (RefData)

[English](../en/refdata.md) | **Tiếng Việt**

[← Store](store.md) · **RefData** · [ProcessLink →](process-link.md)

---

Khi một ứng dụng chạy nhiều tiến trình, những thứ **mọi tiến trình đều cần đọc**
- khoá verify JWT, danh bạ app, cấu hình đã phân giải - hoá ra bị nạp lại một
lần cho mỗi tiến trình. Bốn tiến trình là bốn lần gọi Trust lúc khởi động, bốn
bản trong RAM, và bốn thời điểm xoay khoá khác nhau.

`RefData` là chỗ để một bản duy nhất nằm trong bộ nhớ chung: **primary nạp và
publish, mọi tiến trình đọc.**

Không cần cài thêm gì - nó nằm trong `xime.core`.

---

## RefData hay Store: chọn theo **nguồn bền vững**

Xime có hai kho liên tiến trình, và ranh giới giữa chúng không phải kích thước
hay tần suất, mà là **dữ liệu này mất đi thì có nạp lại được không**.

| | **`RefData`** (trang này) | [`Store`](store.md) (LMDB) |
|---|---|---|
| Ví dụ | khoá JWT · danh bạ app · cấu hình | hãm nhịp · thử thách passkey · chống lặp |
| Mất thì | **nạp lại được từ nguồn** | **mất hẳn** |
| Ghi | hiếm, và **thay trọn gói** | thường xuyên, sửa từng khoá |
| Ai ghi | **chỉ primary** | mọi tiến trình |
| Phép nguyên tử (`incr`) | không có, không cần | **có** |

> **Câu tự kiểm:** *dữ liệu này còn ở chỗ khác không?* Còn (Trust, database,
> file cấu hình) thì nó thuộc `RefData`. Không thì nó thuộc `Store`.

⛔ Phạm vi của cả hai là **một máy, luôn luôn**. Nhiều máy đã giải bằng chia
shard, không phải bằng một kho dùng chung.

---

## Khai một bảng

```python
# app/refdata/jwt_keys.py
import msgpack

from xime.core.refdata import RefData

from app.domain.keys import JwtKeySet


class JwtKeyRefData(RefData[JwtKeySet], name="jwt-keys", max_bytes=64 * 1024):
    """Tập khoá verify lấy từ Trust."""

    def encode(self, value: JwtKeySet) -> bytes:
        return msgpack.packb(value.to_dict())

    def decode(self, raw: memoryview) -> JwtKeySet:
        return JwtKeySet.from_dict(msgpack.unpackb(raw))
```

Cấu hình đi bằng **tham số class**, không phải thuộc tính trong thân class - nhờ
vậy cấu hình không bao giờ nằm chung không gian tên với thứ ứng dụng thêm vào,
và quên khai `name` thì class vẫn abstract nên **không vào DI được**. Cùng quy
ước với `Store`.

| Tham số | |
|---|---|
| `name` | **bắt buộc**. Cũng là tên vùng nhớ chung |
| `max_bytes` | trần cỡ một bản. Mặc định 64 KB |

⚠ **Vùng nhớ tốn `2 × max_bytes`**, vì luôn giữ hai bản để người đọc không bao
giờ thấy một bản đang ghi dở. Trên Windows nó bị cấp phát **thật** ngay lúc khởi
động, nên đừng cho dư cho chắc.

---

## Khai với framework

Bảng phải được khai ở `config/`, vì **tiến trình gốc cấp vùng nhớ trước khi dựng
DI** - lúc đó nó chỉ có class trong tay.

```python
# config/refdata.py
from xime.core.refdata import configure_refdata

from app.refdata.app_registry import AppRegistryRefData
from app.refdata.jwt_keys import JwtKeyRefData

configure_refdata([JwtKeyRefData, AppRegistryRefData])
```

Rồi nhớ import nó trong `config/__init__.py` như mọi module cấu hình khác.

---

## Đọc: `read()` và `read_or_fail()`

```python
class TrustKeyProvider:
    def __init__(self, keys: JwtKeyRefData) -> None:
        self._keys = keys

    def resolve(self, kid: str | None) -> Sequence[KeyContext]:
        return self._keys.read_or_fail().resolve(kid)
```

Bảng được inject **thẳng, có kiểu**, nên IDE và `mypy` biết `read()` trả gì.

| | |
|---|---|
| `read()` | giá trị, hoặc `None` khi **chưa ai publish lần nào** |
| `read_or_fail()` | như trên, nhưng chưa sẵn sàng thì ném `RefDataNotReadyError` |

### ⚠ `None` nghĩa là CHƯA SẴN SÀNG, không phải "rỗng"

Đây là chỗ dễ hỏng nhất, và nó hỏng **im lặng**:

```python
keys = self._keys.read()
if not keys:                      # ⛔ SAI
    return True                   # "không có khoá nào để kiểm" -> cho qua tất
```

Một bảng đã publish một **tập rỗng** trả về object rỗng, không phải `None`. Gộp
hai thứ đó lại là mở một cửa sổ lúc khởi động mà request xác thực bị **từ chối
oan, hoặc tệ hơn là được cho qua**.

```python
keys = self._keys.read()
if keys is None:                  # ✅ ĐÚNG - phân biệt rõ
    raise ServiceNotReady(...)
```

### ⚠ Object trả về là DÙNG CHUNG, không được sửa

`read()` trả **chính object** trong bộ nhớ tiến trình, không phải bản chép. Sửa
nó là sửa bản của mọi người trong tiến trình này. Framework **không chặn** -
chặn được thì phải trả phí runtime cho mọi lời đọc, cùng ranh giới đã chốt cho
`read_only()`.

### Nó nhanh vì đường thường lệ chỉ là một phép so

`read()` giữ một cache trong RAM riêng của tiến trình, khoá bằng **số đời**. Số
đời chưa đổi thì nó trả thẳng object trong cache: không đọc bộ nhớ chung, không
decode, không copy. `decode()` chạy **một lần cho mỗi lần publish**, không phải
một lần cho mỗi lời đọc.

---

## Ghi: `publish()`, và **chỉ primary**

```python
# Thường nằm ở tầng khởi động của primary
keyset = await self._trust.fetch_keys()
await self._keys.publish(keyset)
```

Tiến trình khác gọi `publish()` thì **nổ** (`RefDataNotWriterError`). Cơ chế hai
bản chỉ đúng với đúng một người ghi; hai người cùng dựng bản mới vào ô trống là
hỏng, và **hỏng im lặng**.

`publish()` **thay trọn gói**. Không có API sửa một phần - đó là một phần định
nghĩa của loại dữ liệu này, không phải một chỗ còn thiếu.

---

## Chờ bản đầu tiên: `wait_ready()`

Lúc khởi động, tiến trình phụ có thể lên trước khi primary kịp publish. Chờ ở
**tầng khởi động**, không chờ trên đường phục vụ:

```python
class WarmUp:
    def __init__(self, keys: JwtKeyRefData) -> None:
        self._keys = keys

    async def post_construct(self) -> None:
        await self._keys.wait_ready(timeout=10)
```

| | |
|---|---|
| ⛔ `read()` **không tự chờ** | Chờ trong `read()` là treo một request |
| ⚠ `timeout` **bắt buộc** | Primary có thể chết trước khi kịp publish, và chờ vô hạn là treo cả tiến trình mà không ai biết vì sao |

---

## Quan sát: `stats()`

```python
stats = self._keys.stats()
```

| Trường | |
|---|---|
| `generation` | số đời **trong bộ nhớ chung** - bản mới nhất cả cụm có. `0` = chưa ai publish |
| `served_generation` | số đời **tiến trình này** đang phục vụ. ⭐ Chênh với `generation` là **tín hiệu duy nhất** cho thấy một tiến trình đang phục vụ bản cũ |
| `written_at_ms` | bao lâu rồi kể từ lần publish cuối |
| `used_bytes` / `limit_bytes` / `fill_ratio` | cỡ bản đang dùng so với trần |
| `writer` | chỉ số tiến trình đã publish bản đang dùng |
| `stale` | ⭐ **lần publish gần nhất THẤT BẠI vì vượt trần** |

⚠ Ảnh chụp **gần đúng** - nó đọc trong lúc người khác có thể đang ghi. Đừng dùng
nó làm chốt chặn logic; dùng `read()` cho việc đó.

---

## Vượt trần: ba lớp, và lớp cứu được là lớp đầu

Vượt trần ở đây nguy hơn ở [bus](process-link.md): bus làm mất **một tin**, còn
ở đây primary không publish được nghĩa là **cả cụm dùng bản cũ mãi mãi** - khoá
đã xoay mà mọi tiến trình vẫn verify bằng khoá cũ, và **không request nào lỗi**
cho tới khi token ký bằng khoá mới xuất hiện.

| Lớp | |
|---|---|
| **Cảnh báo ở 80% trần** | ⭐ **Lớp thật sự cứu**, vì nó báo TRƯỚC |
| `publish()` ném `RefDataTooLargeError` | Bản **cũ giữ nguyên** - một bản cũ đúng còn hơn một bản mới rách |
| `stats().stale = True` | Một publish hỏng mà không ai biết là chỗ tệ nhất |

Nâng `max_bytes` là cách sửa, và nhớ rằng nó tốn gấp đôi trong bộ nhớ chung.

---

## Chạy một tiến trình thì sao

Chạy y hệt. Ứng dụng không gọi `share_load()` thì nó **tự là primary**, tự cấp
vùng nhớ của mình, và `publish()` cùng `read()` đều hoạt động. Không có nhánh
code nào phải viết hai lần.

⚠ Chạy tay **một** tiến trình con để gỡ lỗi (`XIME_PROCESS_ID=api-2 python -m
app.main`) thì nó không có cha, nên nó cấp vùng nhớ **riêng của nó** - không
chia sẻ với ai. Framework log một dòng cảnh báo ở ca đó, vì nếu không thì tiến
trình chạy được mà `read()` trả `None` mãi mãi và không có gì trông giống lỗi.

---

## Bảng lớn: chia đoạn

Hình dạng đã có sẵn từ bản đầu (`encode_segments` / `decode_segments`), nhưng
bản hiện tại **chỉ dùng một đoạn**. Ngày dữ liệu lớn tới mức cần chia, lớp con
override hai method đó và **đọc theo dòng** (`msgpack` có `unpacker.feed`) -
đừng nối các đoạn lại trước, vì nối thành một `bytes` liền là một lần copy toàn
bộ, tức vứt đi chính thứ việc chia đoạn đang cố giữ.

---

## Xem thêm

- [Starters](starters.md) - **bảng chọn ba chiều**: `RefData` / `Store` / `CacheService`
- [Store](store.md) - nửa còn lại: dữ liệu **không có nguồn bền vững**
- [ProcessLink](process-link.md) - gửi **tín hiệu và lệnh** giữa các tiến trình
- [Đa tiến trình](multi-process.md) - `share_load()`, khối `processes:`, primary

---

[← Store](store.md) · **RefData** · [ProcessLink →](process-link.md)
