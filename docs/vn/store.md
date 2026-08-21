# Kho liên tiến trình (Store)

[English](../en/store.md) | **Tiếng Việt**

[← Starters](starters.md) · **Store** · [RefData →](refdata.md)

---

Khi một ứng dụng chạy nhiều tiến trình, mọi trạng thái nằm trong bộ nhớ của một
tiến trình đều trở thành sai: bộ đếm hãm nhịp bị nhân lên theo số tiến trình,
còn thử thách passkey thì `begin` rơi vào tiến trình A và `finish` rơi vào tiến
trình B nên tính năng gãy theo kiểu ngắt quãng.

`Store` là chỗ để những trạng thái đó ra khỏi bộ nhớ tiến trình. Nó là một kho
khoá-giá trị trên LMDB, dùng chung giữa mọi tiến trình của **một máy**.

```bash
pip install 'xime[lmdb]'
```

---

## Câu tự kiểm trước khi đặt bất cứ gì vào đây

Kho nằm trên bộ nhớ chia sẻ (`/dev/shm` trên Linux), nên nó **mất sạch khi máy
khởi động lại**.

> **Máy restart, bảng này rỗng trơn - ứng dụng có còn chạy đúng không?**

Không thì dữ liệu đó thuộc **database**, không thuộc kho này.

| | Có nguồn bền vững | Không có nguồn |
|---|---|---|
| **Mất được** | cache đọc lại từ nguồn | ✅ **`Store`** |
| **Không mất được** | - | ⛔ **database** |

⚠ Chữ *"database"* trong tên LMDB là lý do phổ biến nhất khiến người ta nhầm chỗ
này. Kho vẫn sống qua lần **restart ứng dụng** (cache còn ấm sau mỗi lần deploy),
nhưng không sống qua lần **khởi động lại máy**.

⛔ **Phạm vi là MỘT máy, luôn luôn.** Nhiều máy được giải bằng chia shard: mọi
request của cùng một chủ thể đi về cùng một shard, tức cùng một máy, nên trạng
thái mà các request đó phụ thuộc vào nhau chỉ cần chia sẻ trong máy ấy.

---

## Khai một bảng

Cấu hình đi bằng **tham số class**, không phải thuộc tính trong thân class - nhờ
vậy nó không bao giờ nằm chung không gian tên với thứ ứng dụng viết thêm, và
`mypy` bắt được lỗi gõ sai tên tham số.

```python
# app/infrastructure/store/LoginRateLimit.py
from xime.starters.lmdb import CounterStore


class LoginRateLimit(
    CounterStore,
    name="login-rate-limit",   # bắt buộc - cũng là tên thư mục trong kho
    ttl=900,                   # tuỳ chọn, mặc định 3600 giây
    parts=4,                   # tuỳ chọn, mặc định 1
):
    """Đếm số lần đăng nhập sai theo (tài khoản, IP)."""
```

Ba lớp nền:

| Lớp nền | Kiểu giá trị | Có gì thêm |
|---|---|---|
| `Store` | `bytes` | - |
| `CounterStore` | `int` | **`incr()`** nguyên tử |
| `Store[T]` | kiểu của bạn | bạn viết `encode()` / `decode()` |

```python
class WebhookDedup(Store, name="webhook-dedup", ttl=86400):
    """bytes vào, bytes ra - mặc định."""


class PasskeyChallenge(Store[Challenge], name="passkey-challenge", ttl=300):
    def encode(self, value: Challenge) -> bytes:
        return value.to_bytes()

    def decode(self, raw: memoryview) -> Challenge:
        return Challenge.from_bytes(bytes(raw))
```

⚠ `raw` trong `decode()` là view vào vùng nhớ của kho, **chỉ hợp lệ trong lời gọi
đó**. Dùng ngay, đừng giữ lại.

### Đưa vào DI

```python
# config/dependency.py
dependency.scan(
    "xime.starters.lmdb",              # LmdbEnvironment + StoreCleanupJob
    "app.infrastructure.store",        # các bảng của bạn
)
```

Bảng được inject như một repository:

```python
class LoginUseCase:
    def __init__(self, rate_limit: LoginRateLimit, users: UserRepository) -> None:
        self._rate_limit = rate_limit
        self._users = users
```

> **Quên khai `name` thì class không vào DI.** Lớp nền là abstract vì `name` là
> abstract property; subclass khai `name` mới thành concrete. Nên lỗi đó nổ lúc
> khởi động chứ không âm thầm chạy với một bảng không tên.

---

## Năm phép

```python
await store.get(key)                          # -> T | None
await store.set(key, value, ttl=None)         # -> None
await store.delete(key)                       # -> None
await store.set_if_absent(key, value, ttl=None)   # -> bool, NGUYÊN TỬ
await counter.incr(key, by=1, ttl=None)       # -> int,  NGUYÊN TỬ, chỉ CounterStore
```

Khoá là chuỗi do ứng dụng tự ghép - framework không áp quy ước nào:

```python
key = f"{username}|{ip}"        # hãm nhịp theo tài khoản và IP
key = f"org:{org_id}"           # hạn mức theo tổ chức
```

`set_if_absent` là chỗ phép nguyên tử **thật sự cần**: hai tiến trình cùng nhận
một webhook thì đúng một bên nhận `True`.

```python
lan_dau = await self._dedup.set_if_absent(su_kien_id, b"1")
if not lan_dau:
    return                      # đã xử lý rồi
await self._xu_ly(su_kien)
```

⛔ **Không có `exists()` và không có `keys()`.** `get() is None` làm được việc thứ
nhất; việc thứ hai là lời mời quét toàn bảng trên đường request.

---

## Hạn dùng

Hạn được lưu là một **mốc tuyệt đối**, nên mọi lần **ghi** đặt lại hạn, còn
**đọc** thì không đụng tới.

| Thao tác | Ảnh hưởng tới hạn |
|---|---|
| `set()` | **đặt hạn mới** |
| `incr()` | **đặt hạn mới** |
| `set_if_absent()` | đặt hạn mới (khi chiếm được) |
| `get()` | **không đụng tới** |
| `delete()` | xoá luôn |

Bản ghi còn 10 giây mà `set(..., ttl=300)` thì nó hết hạn sau **300 giây kể từ
lúc gọi**, không phải 310. Redis hành xử y hệt.

> ⭐ Vì sao đọc không gia hạn: nếu đọc mà gia hạn thì **mọi lần đọc thành một lần
> ghi**, và một bảng đọc nhiều sẽ xếp hàng sau một khoá ghi duy nhất. Cùng lý do
> đó, kho này **không đuổi theo LRU**.

### `ttl=None` khác `ttl=NEVER`

| Giá trị | Ở lớp | Ở lời gọi |
|---|---|---|
| không khai | 3600 giây | - |
| `ttl=None` | - | dùng mặc định của bảng |
| `ttl=NEVER` | không bao giờ tự hết hạn | bản ghi này không hết hạn |
| `ttl=300` | mặc định của bảng là 300 | bản ghi này 300 giây |

```python
from xime.starters.lmdb import NEVER

class FeatureFlags(Store, name="feature-flags", ttl=NEVER):
    """Cố ý sống tới khi bị xoá, hoặc tới khi máy khởi động lại."""
```

⚠ `NEVER` **không làm nó bền** - xem câu tự kiểm ở đầu trang.

### ⚠ Cạm bẫy: đừng `incr` khi người dùng đang bị khoá

Vì ghi là đặt lại hạn, nếu vẫn đếm trong lúc người dùng đang bị chặn thì mỗi lần
họ bấm lại sẽ đẩy hạn ra xa, và **khoá kéo dài vô hạn**. Người thật gõ sai vài
lần rồi thử lại là tự khoá mình mãi mãi, không gì báo.

```python
TRAN_SO_LAN_SAI = 5

so_lan_sai = await self._rate_limit.get(khoa) or 0
if so_lan_sai >= TRAN_SO_LAN_SAI:
    raise QuaNhieuLanSai()        # <- thoát Ở ĐÂY, KHÔNG incr

nguoi_dung = await self._users.tim_theo_ten(ten)
if nguoi_dung is None or not nguoi_dung.khop_mat_khau(mat_khau):
    await self._rate_limit.incr(khoa)
    raise ThongTinDangNhapSai()

await self._rate_limit.delete(khoa)   # đăng nhập được thì xoá bộ đếm
```

---

## Chia bảng thành nhiều file

LMDB cho **một người ghi trên mỗi file** tại một thời điểm. `parts` chia khoá ghi
đó ra:

```text
runtime/store/login-rate-limit/
    .parts   0.mdb   1.mdb   2.mdb   3.mdb

"thang|1.2.3.4"  ->  crc32(...) % 4  ->  1.mdb
"hoa|5.6.7.8"    ->  crc32(...) % 4  ->  3.mdb
```

Ứng dụng không thấy gì cả - `store.incr("thang|1.2.3.4")` y nguyên.

- Mặc định **1**. Tăng khi bảng đó **ghi nhiều**, tức mỗi request một lần ghi
  (hãm nhịp là ca điển hình).
- ⛔ **Đừng suy `parts` từ số tiến trình.** Số file phải cố định suốt đời kho: đổi
  nó là mọi khoá nằm sai file. Framework phát hiện và **xoá bảng rồi tạo lại**,
  kèm một dòng log - mất cache một lần, đổi lấy việc không bao giờ chạy trên một
  kho lạc chỗ.

---

## Cấu hình vận hành

```yaml
# resources/application.yml
lmdb:
  path: /dev/shm/my-service-store   # Linux: thẳng trên RAM
  # path: runtime/store             # Windows (máy dev): thư mục thường
  map_size: 64MB                    # cỡ KHỞI ĐIỂM của MỖI file
  total_max: 1GB                    # trần cứng cho CẢ kho
```

| Khoá | Mặc định | |
|---|---|---|
| `path` | **không có** | Bắt buộc khai. Framework cố ý không đoán: nhiều service Xime chạy chung một máy, và một mặc định dùng chung sẽ âm thầm trộn bảng của chúng với nhau |
| `map_size` | 64MB | Mỗi file tự nới **gấp đôi** khi đầy, kèm log `WARNING` |
| `total_max` | 1GB | Chạm trần thì **báo lỗi**, không âm thầm vứt dữ liệu của ai đó |

⭐ **Xem mọi khoá kèm giải thích, không phải nhớ:** `xime config --print`.
Đối chiếu file của bạn: `xime check config`.

### ⚠ Đặt kho trên RAM (tmpfs) - được, và framework nói cho bạn biết

Trên Linux, `/dev/shm/...` hoặc `/run/<service>` (systemd `RuntimeDirectory=`)
là tmpfs, tức kho nằm thẳng trong RAM. Không cần quyền gì đặc biệt lúc chạy:

```ini
[Service]
RuntimeDirectory=my-service
RuntimeDirectoryMode=0700
RuntimeDirectorySize=256M
RuntimeDirectoryPreserve=restart   # sống qua restart, dọn khi stop hẳn
```

⚠ Dòng cuối dễ quên nhất: mặc định systemd **xoá thư mục khi service dừng**, tức
mỗi lần restart là mất sạch - đúng thứ phá `Store`, vì cả lý do nó tồn tại là
*"lời gọi sau phụ thuộc lời gọi trước"*.

⛔ **`/tmp` KHÔNG chắc là RAM.** Debian/Ubuntu để nó trên đĩa; Fedora/RHEL thì
tmpfs. Kiểm bằng `findmnt -no FSTYPE -T /tmp`, đừng đoán.

Framework in **một dòng lúc khởi động** nói kho nằm trên cái gì, vì câu *"kho ở
`/dev/shm/x`"* mang hai nghĩa mà không gì tách ra:

```text
store: /dev/shm/my-service-store (tmpfs, RAM-backed - contents are lost on
reboot) - 1.9GiB free, total_max=1.0GiB
```

⚠⚠ **Và `total_max` vượt dung lượng trống của hệ tệp thì CHẶN KHỞI ĐỘNG.** Trên
tmpfs, trang nhớ **không đuổi ra được** - chỉ có đường swap, mà VPS thường không
có swap. Nên lời hứa đó không vỡ bằng *chậm đi*, nó vỡ bằng **OOM kill cả tiến
trình**. Ca hay gặp nhất: Docker cấp `/dev/shm` mặc định **64 MB**, cần
`--shm-size`.

⚠ Trên tmpfs dữ liệu **mất khi máy khởi động lại**. Với hãm nhịp và thử thách
passkey thì vô hại; với **chống lặp** thì cân nhắc - xoá sổ nonce nghĩa là token
cũ dùng lại được.

⚠ **Kho này không tự nhường chỗ.** Đầy thì nới; chạm `total_max` thì ném
`StoreFullError` và log `CRITICAL`. Đừng đọc chữ "cache" rồi tưởng nó hành xử như
Redis - Redis đuổi key cũ, kho này thì không.

Chấp nhận được vì **mọi bảng đều có hạn** nên dữ liệu tự chết đều đặn. Kho chỉ
thật sự đầy khi tốc độ ghi vượt tốc độ hết hạn, và đó là **tải thật** - cần nới
trần chứ không cần đuổi.

⚠ Trên Windows, một file LMDB bị **cấp phát thật** ngay lúc mở, nên đừng khai
`map_size` rộng tay trên máy dev.

---

## Dọn bản ghi hết hạn

Bản ghi hết hạn đã vô hình với `get()` và đã được tính là trống với
`set_if_absent()`, nên job dọn chỉ **thu hồi chỗ**. Nó không bắt buộc.

```python
# config/scheduler.py
from xime.starters.lmdb import StoreCleanupJob

configure_scheduler(SchedulerConfig(jobs=[
    IntervalJob(job_class=StoreCleanupJob, minutes=10),
]))
```

Chạy hai lần chỉ **thừa**, không sai, nên nó không cần khoá phân tán. Nhưng ghi
LMDB là độc quyền theo file, nên với nhiều tiến trình thì chỉ nên xếp lịch nó ở
**một** tiến trình.

---

## Lỗi

Kho báo sự cố bằng **ngoại lệ**, không phải bằng một kết cục thứ ba trong kiểu
trả về:

| Ngoại lệ | Nghĩa |
|---|---|
| `StoreUnavailableError` | Không đọc/ghi được. Bọc lỗi của lmdb nên bạn không phải import lmdb |
| `StoreFullError` | Cần nới nhưng kho đã chạm `total_max`. Người vận hành phải nâng trần |
| `StoreError` | Lớp nền của cả hai |

> ⭐ Vì sao ngoại lệ: với `incr` và `set_if_absent` thì ngoại lệ là **fail-closed
> tự nhiên** - quên bắt thì request lỗi, không ai chiếm được khoá. Còn quên một
> nhánh của kiểu trả về là **fail-open im lặng**: hãm nhịp hoá ra cho qua tất.

Muốn fail-soft thì **tự bắt** - đó là quyết định của ứng dụng, không phải mặc
định của framework.

---

## Liên quan

- [Starters](starters.md) - Cache/Redis, và ranh giới với kho này
- [RefData](refdata.md) - nửa còn lại: dữ liệu **có** nguồn bền vững
- [Cấu hình](configuration.md) - hai tầng cấu hình
- [Testing](testing.md) - test với DI override

---

[← Starters](starters.md) · **Store** · [RefData →](refdata.md)
