# Kho nhóm 2: `Store` trên LMDB, chia file theo hash

> **Trạng thái 2026-08-19: hình dạng API và cơ chế chia file ĐÃ CHỐT.**
>
> ✅ **ĐÃ CODE 2026-08-20** (giai đoạn 1 của kế hoạch thi công): `xime/starters/lmdb/`,
> extra `xime[lmdb]`, **128 test**. Tài liệu người dùng: `docs/{vn,en}/store.md`.
> Mọi quyết định trong file này đã hiện thực đúng như viết; không mục nào phải đổi.
> ⚠ Dòng cũ *"chưa có một dòng code nào"* hết đúng từ ngày đó.
>
> Tách khỏi [`09-kho-lien-tien-trinh-boi-canh.md`](09-kho-lien-tien-trinh-boi-canh.md)
> theo cùng lý do đã tách nhóm 1 hôm 08-18: chia nhỏ bài toán thì dễ chốt hơn. File
> kia giữ phần bối cảnh, số đo và những thứ **chưa** quyết; file này giữ phần đã chốt
> của nhóm 2.
>
> ⚠ **Câu 2 và câu 7 trong bảng "chưa quyết" của file kia đã HẾT hiệu lực** - chủ dự
> án nói rõ chúng *"chỉ là phiên trước gợi ý tạm"*, và buổi này bàn lại từ nhu cầu
> thật rồi ra kết quả khác. Xem mục 1.3 và mục 4.

---

## 0. Đọc gì trong hai phút

| | |
|---|---|
| **Là gì** | Cache liên tiến trình trên LMDB, cho dữ liệu **không có nguồn bền vững** (hãm nhịp, thử thách passkey, chống lặp) |
| ⛔ **Phạm vi** | **MỘT máy, luôn luôn.** Nhiều máy đã giải bằng chia shard - xem mục 2.7 của tài liệu cache |
| **Khai thế nào** | Subclass, cấu hình đi bằng **tham số class** (PEP 487): `class HamNhip(CounterStore, name="...", ttl=900)` |
| **Ba lớp nền** | `Store` (bytes) · `CounterStore` (int, có `incr`) · `Store[T]` (kiểu riêng của app) |
| **Vào DI** | `dependency.scan("app.infrastructure.store")`, không cần `configure_*` |
| **Chia file** | Một bảng = **N file**, `crc32(key) % N`. Lập trình viên chọn N, mặc định **1** |
| **TTL** | Lưu **mốc tuyệt đối**, đặt lại ở **mọi lần ghi** và **ghi đè** hạn cũ; `get()` không đụng tới. `ttl=` override được từng lời gọi |
| **Lỗi kho** | **Ngoại lệ** có kiểu riêng, không phải kết cục trong kiểu trả về |
| **Kích thước** | Khởi điểm mỗi file + **trần cứng là con số TỔNG** (`total_max`) |
| ⛔ **Không có** | LRU · quét bảng · Protocol đổi backend · codec tự động |

---

## 1. Hình dạng

### 1.1. Ba lớp nền, và ngoặc vuông chỉ còn ở nơi nó làm việc

```python
# app/infrastructure/store/HamNhipDangNhap.py
from xime.starters.lmdb import CounterStore


class HamNhipDangNhap(
    CounterStore,
    name="ham-nhip-dang-nhap",
    ttl=900,        # cửa sổ đếm
    parts=4,        # ghi nhiều nên chia file
):
    """Đếm lần đăng nhập sai theo (tài khoản, IP)."""
```

```python
class ChongLapWebhook(Store, name="chong-lap-webhook", ttl=86400):
    """bytes, mặc định."""


class ThuThachPasskey(Store[Challenge], name="thu-thach-passkey", ttl=300):
    """Kiểu do app định nghĩa - thân class chỉ còn hành vi."""
    def encode(self, v: Challenge) -> bytes: ...
    def decode(self, raw: memoryview) -> Challenge: ...
```

> ### ⭐ Cấu hình nằm NGOÀI thân class - chủ dự án chốt 2026-08-19
>
> Chỗ vướng của bản đầu: `name` / `ttl` / `parts` khai bằng thuộc tính thì chúng nằm
> **cùng không gian tên** với mọi thứ app viết thêm. Nguyên văn: *"dữ liệu cấu hình
> với dữ liệu nó mang đang nằm 1 chỗ... cần có cái phân biệt giữa data và cấu hình"*.
>
> **Tham số class (PEP 487)** tách triệt để: cấu hình đi vào `__init_subclass__`,
> **không bao giờ** thành thuộc tính do app khai, nên **không thể va tên**. Thân class
> từ đó chỉ còn docstring và hành vi.
>
> ⭐ Kèm hai thứ miễn phí: nó đọc **như một lời khai** (*"lớp này là một CounterStore,
> tên là ..., hạn 900 giây"*), và `mypy` **kiểm được kwargs** theo chữ ký
> `__init_subclass__` nên gõ sai `ttls=900` là đỏ ngay - còn một thuộc tính thừa
> trong thân class thì không gì báo.
>
> ⚠ Áp **cùng quy ước cho `RefData`** để hai lớp nền cùng framework không có hai kiểu
> khai. `CrudRepository` thì không đụng - nó hết cấu hình sau khi `model` suy từ
> generic.
>
> **Ba cách đã cân nhắc và loại:** thuộc tính trần (lẫn, va tên được) · dunder kiểu
> `__store__` (có dấu hiệu nhưng vẫn cùng không gian tên, và không phải quy ước chuẩn
> nào) · inner class `Meta` kiểu Django (**tách sạch không kém, là lựa chọn tốt thứ
> hai**, chỉ tốn một tầng lồng).

⭐ **Vì sao tách lớp nền theo kiểu thay vì bắt mọi bảng viết `Store[int]`** - hai lý
do, và lý do thứ hai quan trọng hơn thẩm mỹ:

1. Kiểu nằm trong **tên lớp nền** nên `get()` khai thẳng `-> int | None`, mypy hiểu
   mà không cần tham số kiểu nào.
2. **`incr` chỉ có nghĩa với số.** Đặt nó lên một `Store` chung là hợp đồng hứa thứ
   nó không giữ được cho mọi kiểu - cùng loại vấn đề
   [luật 03](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md) hay nói, chỉ khác là
   nó lộ ra ở chữ ký chứ không ở giá trị trả về.

> **Nguyên tắc rút ra, dùng được cho cả framework: ngoặc vuông khó chịu khi nó LẶP
> LẠI thứ đã nói ở chỗ khác; nó hết khó chịu khi nó là nguồn DUY NHẤT.**

Ba tình huống trong framework, để lần sau không phải nghĩ lại:

| Tình huống | Ví dụ | Cần ngoặc |
|---|---|---|
| Hàm nhận class làm đối số | `await modbus.read_model(BangTai)` | **Không** - mypy suy từ đối số |
| Lớp nền chuyên biệt theo kiểu | `class HamNhip(CounterStore)` | **Không** - kiểu nằm trong tên lớp |
| Lớp nền chung, kiểu do app định nghĩa | `Store[Challenge]` · `RefData[JwtKeySet]` · `CrudRepository[Category]` | **Có** - không có đường nào khác |

### 1.2. Vào DI bằng `scan`, khác `RefData` và `ProcessLink`

```python
# config/dependency.py
dependency.scan("app.infrastructure.store")
```

Cơ chế: `name` là abstract property nên lớp nền là abstract và scanner bỏ qua;
`__init_subclass__` nhận `name=` rồi gán lên subclass, subclass thành concrete nên
**được đăng ký**. Đúng khuôn `CrudRepository` đang chạy.

Đo 2026-08-19, xác nhận cả ba việc cùng chạy được (tham số class + generic + công tắc
DI):

```text
Store              abstract=True   -> scanner bỏ qua
CounterStore       abstract=True   -> scanner bỏ qua
HamNhipDangNhap    abstract=False  name=ham-nhip-dang-nhap  ttl=900  parts=4  kiểu=int
ThuThachPasskey    abstract=False  name=thu-thach-passkey   ttl=300  parts=1  kiểu=Challenge
QuenKhaiTen        abstract=True   -> quên khai name thì KHÔNG vào DI
```

⭐ Dòng cuối là phần đáng giá: **quên khai `name` thì class không vào DI**, nên nó nổ
lúc khởi động chứ không im lặng chạy với một bảng không tên. Dòng `CounterStore` cũng
đáng nhìn: nó **kế thừa `kiểu=int`** từ `Store[int]` mà subclass không phải khai lại.

⭐ Chỗ này **khác** hai thứ chốt hôm 08-18: `RefData` và `ProcessLink` phải
`configure_*` vì framework cần biết danh sách **trước khi dựng DI** để cấp vùng nhớ
chung. Bảng LMDB không cần - mở một file LMDB là `open` cộng `mmap`, không chạm mạng,
không cấp phát chung.

⚠ **Hệ quả: câu 8 của tài liệu cache TAN chứ không phải được trả lời.** Hôm 08-18 ta
chốt *"mở kho trước DI"* khi còn hình dung một environment gốc. Với "mỗi bảng một thư
mục file riêng do lập trình viên khai" thì không có environment gốc nào để mở - cùng
kiểu tan như mục 4.1 khi bus bỏ queue chung.

### 1.3. Bề mặt API

```python
await store.get(key)                          -> T | None
await store.set(key, value, ttl=None)         -> None
await store.delete(key)                       -> None
await store.set_if_absent(key, v, ttl=None)   -> bool    # nguyên tử
await counter.incr(key, by=1, ttl=None)       -> int     # nguyên tử, CHỈ CounterStore
```

`ttl=None` nghĩa là **dùng mặc định của bảng**, không phải "không hết hạn" - xem mục
1.4.

Ba thứ **cố ý không có ở v1**, ghi lý do để lần sau không ai tưởng là bỏ sót:

| Không có | Vì sao |
|---|---|
| `exists()` | `get() is None` làm được, và `exists` mở ra câu hỏi *"tồn tại nhưng giá trị rỗng thì sao"* |
| `keys()`, quét bảng | LMDB làm được, nhưng nó là lời mời quét toàn bảng trên đường request |
| Protocol để đổi backend | `Store` là **lớp nền cụ thể** dựng thẳng trên LMDB. Lý do duy nhất để tách Protocol là *"backend khác có thể không làm được phép nguyên tử"*, mà ở đây không có backend khác: test mở LMDB thật trong thư mục tạm, không cần server nào |

⭐ Dòng cuối là cách **câu 2 của tài liệu cache tan** - không phải được trả lời. Câu
đó hỏi *"mở rộng `CacheService` hay tách `AtomicStore`"*, và cả hai vế đều giả định ta
đang thiết kế một **Protocol**. Bỏ Protocol thì câu hỏi không còn chỗ đứng.

⚠ **`CacheService` cũ giữ nguyên, không đụng một dòng.** Nó là hợp đồng cho Redis, và
người dùng duy nhất của nó (`TrustKeyL2Cache` của data-service) thuộc **nhóm 1** chứ
không phải nhóm 2 - xem mục 7.1 của tài liệu cache.

---

### 1.4. TTL: hạn theo lần GHI, đọc không đụng tới, và đặt động được

Chủ dự án chốt 2026-08-19: *"cho hạn ghi đi, đọc không liên quan"* và *"phải set động
được, không phải bản ghi nào cũng giống nhau"*.

| Thao tác | Ảnh hưởng tới hạn |
|---|---|
| `set()` | **đặt hạn mới** |
| `incr()` | **đặt hạn mới** |
| `get()` | **không đụng tới** |
| `delete()` | xoá luôn |

⭐ **Hai lý do, và lý do thứ hai là kỹ thuật chứ không phải ngữ nghĩa:**

1. Nó khớp với hình dạng nghiệp vụ chủ dự án mô tả: *sai 5 lần thì khoá 30 giây, hết
   30 giây mở lại cho 5 lần khác*.
2. ⛔ **Nếu đọc mà gia hạn thì mọi lần đọc thành một lần GHI** - phá sập đúng ưu thế
   đã chọn LMDB vì nó (đọc không chặn ai, không cần khoá), và biến một bảng đọc nhiều
   thành bảng tranh khoá ghi liên tục. Xem mục 3.2 và 5.

#### Lưu MỐC hết hạn, không lưu thời lượng còn lại - ghi đè hoàn toàn

Chủ dự án hỏi và chốt 2026-08-19: bản ghi còn 10 giây mà `set(..., ttl=300)` thì nó hết
hạn sau **300 giây kể từ lúc gọi**, không phải 310.

```text
set(khoa, v, ttl=300)   ->   ghi  han = bây_giờ + 300      (đè lên hạn cũ)
```

Đây là hệ quả tự nhiên của việc 8 byte đầu value giữ **mốc tuyệt đối** chứ không giữ
thời lượng: mốc mới thay mốc cũ, không có chỗ nào để cộng dồn. Redis hành xử y hệt
(`SET key val EX 300` đặt lại từ đầu), nên người đã dùng Redis không phải học lại.

> ### ✅ Đồng hồ: `time.time()` - chủ dự án chốt 2026-08-19
>
> Nguyên văn: *"thôi lấy `time.time()` là được rồi. **tin vào máy đang chạy**"*.
>
> | | Được | Mất |
> |---|---|---|
> | **`time.time()` (unix)** ✅ | Đúng cả khi kho **sống qua reboot** (máy dev Windows, file thường). Đọc ra là biết *"hết hạn lúc 14:32:11"* nên **gỡ lỗi được** | Chỉnh giờ hệ thống thì lệch: lùi 1 giờ là mọi thứ sống thêm 1 giờ |
> | ~~`time.monotonic()`~~ | Miễn nhiễm chỉnh giờ | **Vô nghĩa qua reboot** (Python không đảm bảo mốc tham chiếu), và là một con số không đọc được khi cần soi |
>
> ⭐ *"Tin vào máy đang chạy"* là một lựa chọn có ý thức, không phải bỏ qua rủi ro: máy
> chủ chạy NTP nên chỉnh giờ là bước **trượt** mili giây chứ không phải cú nhảy, còn cái
> giá của `monotonic` thì trả ngay trên máy dev ở mọi lần khởi động lại.
>
> ⚠ Ghi ra chỗ nó hỏng để sau này không ai phải đoán: **chỉnh giờ hệ thống lùi lại** thì
> mọi bản ghi sống thêm đúng bằng khoảng lùi. Với cache thì vô hại; với **hãm nhịp** thì
> kẻ tấn công được thêm thời gian, nhưng người chỉnh được giờ máy chủ thì đã có quyền
> lớn hơn thế nhiều rồi.

#### Mặc định 1 tiếng, vô hạn phải khai tường minh

Chủ dự án chốt 2026-08-19: *"ttl cho mặc định 1 tiếng. nếu muốn vô hạn tự khai là vô
hạn"*.

```python
class ChongLapWebhook(Store, name="chong-lap-webhook"):
    """Không khai ttl -> 3600 giây."""


class CoTrangThai(Store, name="co-trang-thai", ttl=NEVER):
    """Cố ý sống tới khi bị xoá hoặc tới khi máy khởi động lại."""
```

⭐ **Đây là "an toàn theo mặc định, thoát ra phải viết rõ", tốt hơn phương án bắt buộc
khai** mà phiên đề nghị: nó không chặn ca dùng hợp lệ, mà vẫn không ai **vô tình** tạo
được một bảng chỉ tăng không giảm. Quan trọng vì kho này **không đuổi theo LRU** (mục
3.6) - bảng không hạn trong kho không đuổi là rò rỉ chắc chắn, chỉ là chậm.

⚠ **`NEVER` là hằng số riêng, KHÔNG dùng `None`** - `ttl=None` ở mức lời gọi đã mang
nghĩa *"dùng mặc định của bảng"*. Hai tình huống bắt người gọi làm hai việc khác nhau
thì phải là hai giá trị khác nhau, đúng
[luật 03](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md).

| Giá trị | Ở lớp | Ở lời gọi |
|---|---|---|
| không khai | 3600 giây | - |
| `ttl=None` | - | dùng mặc định của bảng |
| `ttl=NEVER` | không bao giờ hết hạn | ghi bản ghi này không hết hạn |
| `ttl=300` | mặc định của bảng là 300 | bản ghi này 300 giây |

⚠ Và `NEVER` **không có nghĩa là bền**: kho nằm trên `/dev/shm` nên nó vẫn biến mất khi
máy khởi động lại, chỉ là vào lúc không ai chọn. Xem câu tự kiểm ở mục 1.5.

#### Đặt động theo từng bản ghi

`ttl` trên lớp là **mặc định của bảng**; từng lời gọi override được.

```python
class HamNhipDangNhap(CounterStore, name="ham-nhip-dang-nhap", ttl=30):
    """Mặc định khoá 30 giây."""
```

```python
so_lan = await self._ham_nhip.incr(khoa)
if so_lan >= TRAN_SO_LAN_SAI:
    # leo thang: lần khoá này lâu hơn
    await self._ham_nhip.set(khoa, so_lan, ttl=300)
```

#### ⚠ Cạm bẫy đi kèm: ĐỪNG `incr` khi người dùng đang bị khoá

Vì ghi đặt lại hạn, nếu app vẫn đếm trong lúc người dùng đang bị chặn thì mỗi lần bấm
lại đẩy hạn lùi thêm, và **khoá kéo dài vô hạn**. Người thật gõ sai rồi bấm lại vài lần
là tự khoá mình mãi mãi, mà không có gì báo.

Code mẫu ở mục 2.1 **thoát sớm trước khi `incr`** - đó không phải chi tiết ngẫu nhiên:

```python
so_lan_sai = await self._ham_nhip.get(khoa) or 0
if so_lan_sai >= TRAN_SO_LAN_SAI:
    raise QuaNhieuLanSai()          # <- thoát ở đây, KHÔNG incr
```

---

### 1.5. Câu tự kiểm trước khi đặt bất cứ gì vào kho này

Hai nhóm kho chia theo *có nguồn bền vững hay không*. Nhưng còn một ô nữa mà bảng đó
không vẽ:

| | Có nguồn bền vững | Không có nguồn |
|---|---|---|
| **Mất được** | `RefData` (nhóm 1) | **`Store` (nhóm 2)** |
| **Không mất được** | - | ⛔ **database, không phải kho này** |

Kho nằm trên `/dev/shm` nên **mất sạch khi máy khởi động lại**. Câu để tự kiểm:

> **Máy restart, bảng này rỗng trơn - app có còn chạy đúng không?**

Không thì nó thuộc database. Câu này rẻ, và nó chặn đúng loại nhầm lẫn dễ xảy ra nhất:
chữ **"database"** trong tên LMDB khiến người ta tưởng nó bền.

⚠ Kể cả `ttl=NEVER` cũng không làm nó bền - xem mục 1.4.

---

## 2. Dùng thật trông thế nào

### 2.1. Hãm nhịp đăng nhập, đầu tới cuối

```python
# app/infrastructure/store/HamNhipDangNhap.py
from xime.starters.lmdb import CounterStore


class HamNhipDangNhap(
    CounterStore,
    name="ham-nhip-dang-nhap",
    ttl=900,
    parts=4,
):
    """Đếm lần đăng nhập sai theo (tài khoản, IP)."""
```

```python
# app/application/usecase/auth/DangNhapUseCase.py
TRAN_SO_LAN_SAI = 5


class DangNhapUseCase:
    def __init__(
        self,
        ham_nhip: HamNhipDangNhap,          # inject thẳng, như một repository
        nguoi_dung: NguoiDungRepository,
        read_only: ReadOnlyManager,
    ) -> None:
        self._ham_nhip = ham_nhip
        self._nguoi_dung = nguoi_dung
        self._read_only = read_only

    async def thuc_hien(self, lenh: LenhDangNhap, ip: str) -> KetQuaDangNhap:
        khoa = f"{lenh.ten_dang_nhap}|{ip}"

        so_lan_sai = await self._ham_nhip.get(khoa) or 0
        if so_lan_sai >= TRAN_SO_LAN_SAI:
            raise QuaNhieuLanSai()

        async with self._read_only():
            nd = await self._nguoi_dung.tim_theo_ten(lenh.ten_dang_nhap)

        if nd is None or not nd.khop_mat_khau(lenh.mat_khau):
            await self._ham_nhip.incr(khoa)
            raise ThongTinDangNhapSai()

        await self._ham_nhip.delete(khoa)     # đăng nhập được thì xoá bộ đếm
        return KetQuaDangNhap(nd)
```

Bốn chi tiết đáng nhìn:

| | |
|---|---|
| **Khoá là chuỗi do app ghép** | Framework không áp quy ước nào. `f"{ten}|{ip}"` là của app; bảng khác có thể là `f"org:{org_id}"` |
| **`get()` trả `int | None`** | Không cần `Store[int]`, không cần ép kiểu. `or 0` là của app vì *chưa có bản ghi* và *đếm bằng 0* khác nhau |
| **Bảng inject như một repository** | Cùng tầng, cùng cách. Không có `cache` toàn cục nào để `import` |
| **Nó nằm TRƯỚC lời gọi database** | Đúng lý do tồn tại: chặn trước khi tốn một vòng DB |

### 2.2. Thử thách passkey - hai lời gọi ở hai tiến trình khác nhau

Đây là ca mà nhóm 2 sinh ra để giải: `begin` rơi vào tiến trình A, `finish` rơi vào
tiến trình B, và giữ trong RAM tiến trình thì **tính năng gãy hẳn theo kiểu ngắt
quãng** (xem [luật 01](../../../../.claude/rules/01-song-song-hoa-va-shard.md) mục 4).

```python
class ThuThachPasskey(Store[Challenge], name="thu-thach-passkey", ttl=300):
    """`parts` mặc định 1: ghi ít, không cần chia."""
```

```python
class BatDauPasskeyUseCase:
    def __init__(self, kho: ThuThachPasskey) -> None:
        self._kho = kho

    async def thuc_hien(self, identity_id: str) -> Challenge:
        thu_thach = Challenge.moi()
        await self._kho.set(identity_id, thu_thach)
        return thu_thach


class HoanTatPasskeyUseCase:
    def __init__(self, kho: ThuThachPasskey) -> None:
        self._kho = kho

    async def thuc_hien(self, identity_id: str, chu_ky: bytes) -> None:
        thu_thach = await self._kho.get(identity_id)
        if thu_thach is None:
            raise ThuThachHetHan()
        await self._kho.delete(identity_id)     # dùng một lần
        thu_thach.kiem_chu_ky(chu_ky)
```

⚠ **Xoá TRƯỚC khi kiểm chữ ký**, không phải sau. Kiểm trước rồi xoá thì một thử thách
có thể bị dùng lại trong cửa sổ giữa hai bước.

### 2.3. Chống lặp webhook - dùng `set_if_absent`

```python
class ChongLapWebhook(Store, name="chong-lap-webhook", ttl=86400):
    ...
```

```python
lan_dau = await self._chong_lap.set_if_absent(su_kien_id, b"1")
if not lan_dau:
    return                                  # đã xử lý rồi, bỏ qua
await self._xu_ly(su_kien)
```

Đây là chỗ phép nguyên tử **thật sự cần**: hai tiến trình cùng nhận một webhook thì
đúng một bên nhận `True`.

---

## 3. Chia file theo hash

### 3.1. Cơ chế

Một bảng là một **thư mục** chứa N file. Key nào ở file nào do chính key quyết định:

```text
runtime/cache/ham-nhip-dang-nhap/
    0.mdb   1.mdb   2.mdb   3.mdb

khoá "thang|1.2.3.4"   ->  crc32(...) % 4  ->  1.mdb
khoá "hoa|5.6.7.8"     ->  crc32(...) % 4  ->  3.mdb
```

```python
def _phan(self, khoa: str) -> int:
    return zlib.crc32(khoa.encode()) % self.parts
```

Mọi tiến trình mở cả N file. Đọc hay ghi đều tính hàm đó trước rồi làm việc với đúng
một file. **App không thấy gì cả** - `store.incr("thang|1.2.3.4")` y nguyên.

### 3.2. Vì sao chia, và vì sao chia theo KEY chứ không theo tiến trình ghi

Điểm yếu của LMDB so với Redis: nó khoá ghi ở **mức environment**, một người ghi tại
một thời điểm cho cả file. Chia file là chia khoá ghi.

⚠ Chủ dự án đề xuất ban đầu là **chia theo tiến trình ghi** (học từ bus: mỗi tiến
trình một vùng ghi riêng). Hướng đó cho zero xung đột ghi, nhưng nó phá thứ khác:

| | Chia theo **tiến trình ghi** | Chia theo **hash(key)** |
|---|---|---|
| Ghi tranh khoá | không bao giờ | chỉ khi hai tiến trình trúng cùng file |
| Đọc | phải đọc **cả N** file | đúng **1** file |
| Một key nằm ở | **nhiều file** | **đúng một file** |
| `incr` | ❌ mỗi file một bộ đếm, tổng **không nguyên tử** | ✅ nguyên vẹn |
| `set_if_absent` | ⛔ **hỏng hẳn** - hai tiến trình cùng chiếm một key vào hai file, **cả hai đều thành công** | ✅ nguyên vẹn |

Dòng cuối giết phương án đầu: chống lặp và khoá là lý do chính người ta cần phép
nguyên tử, mà chia theo người ghi thì **mỗi tiến trình là người-chiếm-đầu-tiên trong
vũ trụ riêng của nó**.

> ⭐ **Vì sao bus chia theo người ghi được mà kho thì không:** bus chở **luồng tin**,
> không ai tra cứu gì cả - đọc là đọc hết theo thứ tự. Kho có key và phải trả lời
> *"key này ở đâu"*, nên trục chia buộc phải là key.
>
> Cùng câu đã ghi ở [tài liệu snapshot](12-kho-refdata.md): **dùng
> lại vật liệu thì được, dùng lại sự dễ dàng thì không.**

### 3.3. `parts` do lập trình viên chọn, mặc định 1 (chủ dự án chốt)

```python
class HamNhipDangNhap(CounterStore, name="ham-nhip-dang-nhap", parts=4):
    """Bảng ghi nhiều."""


class ThuThachPasskey(Store[Challenge], name="thu-thach-passkey"):
    """`parts` mặc định 1: ghi ít, không cần chia."""
```

Chủ dự án chốt: *"cho lập trình viên chọn trước dùng bao nhiêu file cho bảng"*, và
*"có thể là 1 file thôi"*. Mặc định **1** vì đó là hình dạng đơn giản nhất chạy được;
tăng khi bảng đó ghi nhiều, mà ghi nhiều nghĩa là **mỗi request một lần ghi** (hãm
nhịp là ca điển hình).

⛔ **`parts` KHÔNG được suy từ số tiến trình.** Số file phải **cố định suốt đời kho**:
đổi N là mọi key nằm sai chỗ. Với cache thì hậu quả chỉ là mất cache (chấp nhận
được), nhưng nếu N bám theo cấu hình tiến trình thì **mỗi lần đổi số tiến trình là
một lần mất sạch cache mà không ai chờ đợi điều đó**.

### 3.4. ⛔ `crc32` chứ KHÔNG phải `hash()` - đo được, và hỏng im lặng

```text
tiến trình | hash() | crc32()
    1      |   5    |    4
    2      |   7    |    4
    3      |   3    |    4
    4      |   1    |    4
```

`hash()` của Python **ngẫu nhiên lại mỗi lần khởi động tiến trình** (hash
randomization cho `str`, mặc định bật từ 3.3). Dùng nó để chọn file thì bốn tiến
trình tính ra **bốn file khác nhau cho cùng một key**, và không có gì báo - mỗi tiến
trình đọc ghi đúng theo logic của chính nó.

Loại lỗi này chỉ hiện khi có nhiều tiến trình, tức **không bao giờ hiện trên máy dev
một tiến trình**. Ghi ra đây vì nó rẻ để tránh và rất đắt để tìm.

### 3.5. Kích thước: khởi điểm mỗi file, TRẦN CỨNG là con số TỔNG

Chủ dự án chốt 2026-08-19 (phương án C trong ba phương án đã cân).

```yaml
lmdb:
  path: /dev/shm/xime-cache     # Linux: thẳng trên RAM. Windows: thư mục thường
  map_size: 64MB                # khởi điểm MỖI file
  total_max: 4GB                # tổng KHÔNG được vượt
```

Mỗi file tự nới gấp đôi khi đầy, nhưng framework **từ chối nới nếu tổng chạm
`total_max`**. Người vận hành chỉ phải trả lời một câu họ thật sự biết: *"cho kho bao
nhiêu RAM"*. Framework **log tổng đang cấp lúc khởi động** để họ thấy con số đó.

⚠ Ba phương án đã cân và lý do loại hai cái kia:

| | Loại vì |
|---|---|
| Một số áp cho mọi file | Không phải tổng thật - người vận hành vẫn phải tự nhân với số bảng nhân số `parts` |
| Khai tổng rồi **chia đều** | Chia đều là sai (bảng chênh nhau nhiều lần), và thêm một bảng là đổi trần mọi bảng khác |

⛔ **Tên bảng KHÔNG khai trong `application.yml`** - nó thuộc code, đã chốt ở mục 1.1.
Chỉ khai riêng trong YAML khi một bảng cần trần lệch chuẩn.

### 3.6. ⛔ KHÔNG đuổi theo LRU - và lý do y hệt lý do của TTL

Redis đuổi được key lâu không dùng nhất (`allkeys-lru`). LMDB không nên, vì:

> LRU cần biết *"lần cuối dùng khi nào"* -> mỗi lần **đọc** phải cập nhật dấu thời gian
> -> **ghi trên đường đọc** -> mọi lượt đọc xếp hàng qua khoá ghi.

Đúng lập luận đã dùng để chốt *"đọc không đụng tới hạn"* ở mục 1.4. Hai quyết định này
là một, đừng lật riêng cái nào.

Nên kho chỉ bỏ key theo **hạn**, cộng nới trần khi đầy:

> ⚠ **Kho này KHÔNG tự nhường chỗ.** Đầy thì nới; chạm `total_max` thì **báo lỗi**, chứ
> không âm thầm vứt dữ liệu của ai đó đi. Ghi rõ trong tài liệu người dùng để không ai
> đọc chữ "cache" rồi tưởng nó hành xử như Redis.

Chấp nhận được vì **mọi bảng đều có hạn** (mặc định 3600, mục 1.4) nên dữ liệu tự chết
đều đặn. Kho chỉ thật sự đầy khi tốc độ ghi vượt tốc độ hết hạn - đó là **tải thật**,
cần nới trần chứ không cần đuổi.

### 3.7. File kho GIỮ qua lần restart app (chủ dự án chốt 2026-08-19)

Ngược với bus - bus **xoá** vùng nhớ khi tắt vì nó chỉ chở liên lạc và tên file mang
`link_id` ngẫu nhiên. Kho thì giữ, và giữ được là nhờ một quyết định trước đó:

> ⭐ **`time.time()` làm cho việc giữ file trở nên an toàn.** Bản ghi cũ mang mốc hết
> hạn tuyệt đối nên sau khi app khởi động lại, thứ nào quá hạn vẫn quá hạn - không có
> bản ghi nào sống dậy sai. Nếu chọn `monotonic` thì giữ file là giữ một đống mốc vô
> nghĩa.

Được: cache **còn ấm** sau mỗi lần restart app, tức không có cú sốc tải lên database
mỗi lần deploy. Mất: không có gì, vì reboot máy vẫn xoá sạch (`/dev/shm` là RAM).

#### ⚠ Cái bẫy đi kèm: đổi `parts` giữa hai lần chạy

Đổi `parts` là **mọi key nằm sai file**, và **không gì báo** - `get()` chỉ trả `None`
nhiều hơn bình thường, trông y hệt một cache lạnh.

Cách chặn rẻ: ghi `parts` vào metadata của kho; khởi động thấy lệch thì **xoá và tạo
lại**, log một dòng. Mất cache một lần, đổi lấy việc không bao giờ chạy trên một kho
lạc chỗ.

⚠ Cùng khuôn với việc `parts` **không được suy từ số tiến trình** (mục 3.3): cả hai đều
là *"con số này đổi thì dữ liệu cũ hết dùng được"*.

### 3.8. Async: gọi thẳng cả đọc lẫn ghi

Số đo ở mục 6.1 nói rõ với đường **đọc**: đẩy sang executor đắt gấp 439 lần chính việc
cần làm. Đường **ghi** cũng vậy trong cấu hình đã chốt - `sync: false` trên tmpfs nên
một giao dịch ghi là 5-20 µs, còn chuyển tầng tốn 20-96 µs.

> **Cả hai đường gọi thẳng trong event loop.** Đừng bọc executor cho tới khi có phép đo
> trên VPS nói ngược lại.

⚠ **Luật thi công đi kèm, bắt buộc:** job dọn key hết hạn (mục 7) **phải ghi theo lô
nhỏ**, không mở một giao dịch ghi dài quét cả bảng. Một người ghi giữ khoá lâu là mọi
tiến trình khác **chặn event loop của chính nó** khi tới lượt ghi - và đó là cách duy
nhất quyết định "gọi thẳng" ở trên có thể hỏng.

Cộng với luật đã ghi ở tài liệu cache mục 7.3: **mở giao dịch đọc, đọc, đóng ngay,
không `await` bên trong**.

---

## 4. Lỗi kho báo bằng NGOẠI LỆ, không phải kết cục trong kiểu trả về

Hợp đồng `CacheService` hôm nay thật ra đã có **ba** kết cục - `bytes` / `None` /
**ném** - chỉ là kết cục thứ ba không được khai, nên mỗi app phải tự đoán rồi bọc
`except Exception` (đọc `TrustKeyL2Cache` của data-service thấy đúng vậy). Mà
`except Exception` **nuốt luôn lỗi lập trình** trong chính đường đó.

Nên việc phải làm là **khai ra**, không phải "thêm":

```python
class StoreUnavailableError(XimeException): ...
```

⚠ Và với `incr` / `set_if_absent` thì **ngoại lệ là fail-closed tự nhiên**: quên bắt
thì request lỗi, không ai chiếm được khoá, an toàn. Kiểu trả về ba kết cục thì người
viết quên nhánh thứ ba là **fail-open im lặng** - hãm nhịp cho qua.

> ⭐ **Ranh giới sạch giữa nó và bus:** *kết quả bình thường thì kiểu trả về; sự cố hạ
> tầng thì ngoại lệ.* Bus trả `NoAnswer` bằng kiểu vì đó là chuyện xảy ra hằng ngày;
> kho không đọc được là sự cố.

App nào muốn fail-soft thì **tự bắt** - đó là quyết định của app, không phải mặc định
của framework, vì mặc định fail-soft cho hãm nhịp là mở toang.

⭐ Đây là cách **câu 7 của tài liệu cache tan**: nó hỏi *"ba kết cục thay vì hai"*, mà
kết cục thứ ba vốn đã có, và chỗ đúng cho nó không phải kiểu trả về.

---

## 5. Xung đột ghi còn lại, và vì sao chưa khử

Chia theo hash vẫn còn 1/N xác suất hai tiến trình ghi trúng cùng file. Trước khi đi
tìm cách khử, đáng hỏi **nó tốn bao nhiêu**:

Một giao dịch ghi LMDB một key nhỏ, `sync: false`, trên tmpfs cỡ **5-20 µs**. Nghĩa
là một file chịu được **hàng chục nghìn lần ghi mỗi giây** trước khi khoá thành nút
thắt. Với hãm nhịp - ca ghi nhiều nhất - app phải chạy hàng chục nghìn request mỗi
giây mới chạm tới.

⚠ Con số đó là **ước lượng, chưa đo thật** (chưa cài `lmdb`). Nhưng đủ để hoãn.

### Đường nâng cấp nếu phép đo trên VPS cho thấy khoá thật sự tranh

Mỗi file có **đúng một người ghi**, định tuyến đường ghi qua bus:

```text
tiến trình k  ->  sở hữu  k.mdb

ghi khoá thuộc file 2:
   nếu tôi LÀ tiến trình 2   ->  ghi thẳng
   nếu không                 ->  link.ask("kho:<ten-bang>", key=..., ...)

đọc:  luôn đọc thẳng, KHÔNG qua bus
```

⭐ Chỗ làm nó chạy được: **LMDB đọc không bao giờ bị ghi chặn** (mỗi reader thấy một
ảnh chụp nhất quán). Nên chỉ cần định tuyến **đường ghi** - mà đường đọc mới là đường
đông.

Giá: (N-1)/N số lần ghi đi một vòng bus, cỡ **35 µs** (`ask` hai chiều, đo 08-18 là
17,4 µs một chiều) so với ghi thẳng 5-20 µs.

✅ **Ba phương án cùng một API bên ngoài** - `Store`, `CounterStore`, `name`, `ttl`,
`parts` không đổi một chữ. Nên đây không phải quyết định khoá cứng: làm bản chia hash
trước, đo trên VPS thật, cần thì nâng cấp mà **không app nào phải sửa**.

Lý do hoãn không phải "chắc là đủ nhanh" mà là **thứ tự**: khử một xung đột chưa ai
đo được, bằng cách nối bus vào đường ghi của kho, là ghép hai hệ thống mới toanh vào
nhau ngay từ bản đầu.

---

## 6. Số đo 2026-08-19, để khỏi đo lại

### 6.1. Đọc từ bộ nhớ không song song hoá được, và không cần

```text
một lần đọc từ page cache        :  0.220 µs
gói vào asyncio.gather (4 lần)   :  6.032 µs/lần   -> đắt gấp  27
đẩy sang thread pool  (4 lần)    : 96.657 µs/lần   -> đắt gấp 439
```

Đọc LMDB **không phải I/O** - nó là `mmap` cộng memcpy, không có điểm nào để nhả cho
việc khác chen vào. Nên `gather` không làm chúng chạy cùng lúc, chỉ thêm chi phí tạo
coroutine; còn thread pool thì chi phí chuyển tầng lớn gấp 439 lần chính việc cần làm.

> **Luật rút ra: đừng bao giờ đẩy một lần ĐỌC kho sang executor.** Ghi thì có thể
> (giao dịch ghi chờ khoá trong thời gian không xác định), đọc thì không.

⚠ **Đo trên Windows, file thường.** Nhưng phép đo đọc **cùng một offset 200.000 lần**
nên trang đó luôn nằm trong page cache - tức đúng điều kiện tmpfs. `/dev/shm` khác
file thường ở lần chạm đầu tiên, ở chuyện ghi xuống đĩa, và ở việc bị đuổi khi bộ nhớ
chật; không chỗ nào chạm vào phép đo này.

Chỗ **có thể lệch trên Linux**: chuyển luồng rẻ hơn nên `run_in_executor` có thể
xuống 20-40 µs thay vì 96. Vẫn đắt hơn một lần đọc cả trăm lần, kết luận không đổi.

### 6.2. Còn phải đo trên VPS Linux khi có

- Một lần `get` LMDB thật (mục 5.4 tài liệu cache mới là ước lượng).
- Một giao dịch ghi thật, và ngưỡng khoá thật sự thành nút thắt.

---

## 7. Còn treo: HẾT

Mọi câu của mảng này đã chốt trong buổi 2026-08-19. Giữ bảng lại làm lịch sử quyết định,
vì cột bên phải ghi **lý do**, và vài đề nghị ban đầu của phiên đã bị bác kèm lý do đáng
đọc trước khi ai đó mở lại.

⚠ Thứ còn lại **không phải câu hỏi thiết kế** mà là hai phép đo phải làm khi có VPS
Linux - xem mục 6.2.

| # | Câu | Đề nghị của phiên |
|---|---|---|
| ~~1~~ | ~~**`incr` có gia hạn TTL không**~~ | ✅ **ĐÃ CHỐT 2026-08-19: CÓ, mọi lần GHI đặt lại hạn; đọc không đụng tới.** Kèm `ttl=` đặt động được từng lời gọi. Xem mục 1.4. ⚠ Đề nghị ban đầu của phiên (*giữ hạn lần đầu*) đã bị bác, và bác đúng: cạm bẫy "khoá vô hạn" mà nó lo **không xảy ra** vì app thoát sớm trước khi `incr`, còn cái giá của việc đọc-gia-hạn thì là thật |
| ~~2~~ | ~~Tên lớp: `Store` hay `Table`~~ | ✅ **CHỐT 2026-08-19: `Store`.** `Table` đúng phép loại suy SQL nhưng hứa nhiều hơn thứ nó có: không cột, không truy vấn, không giao dịch xuyên bảng |
| ~~3~~ | ~~Có làm `StringStore` không~~ | ✅ **CHỐT 2026-08-19: KHÔNG.** Nguyên văn chủ dự án: *"chỉ byte, **ai thích làm gì với byte thì tuỳ**"*. Chuỗi bọc bytes chỉ là `.encode()/.decode()`; mỗi lớp nền thêm vào phải trả giá bằng một lần lưỡng lự lúc chọn |
| ~~4~~ | ~~`Store[T]` tự chọn codec theo kiểu?~~ | ✅ **KHÔNG - app tự viết `encode`/`decode`**, theo chốt *"chỉ byte, ai thích làm gì với byte thì tuỳ"*. Generic chỉ phục vụ **kiểu tĩnh** cho mypy. Ba cái giá của việc framework tự đoán: **phụ thuộc khái niệm** (dataclass/pydantic - đúng loại nợ vừa gỡ ở 0.7.1) · nó **đoán** (`datetime`? kiểu lồng nhau? `Decimal`?) · **thêm field là hỏng ngầm** với bản ghi cũ, mà app tự viết thì nhìn thấy chỗ đó |
| ~~5~~ | ~~`map_size` khai ở đâu~~ | ✅ **CHỐT 2026-08-19: phương án C** - khởi điểm mỗi file + **trần cứng là con số TỔNG**. Xem mục 3.5 |
| ~~6~~ | ~~Dọn key hết hạn~~ | ✅ **CHỐT 2026-08-19: một job nền mỗi bảng.** Theo luật 01 việc này thuộc hạng *chạy hai lần chỉ THỪA* nên **không cần khoá phân tán** |
| ~~7~~ | ~~Đầy trần thì làm gì~~ | ✅ **CHỐT 2026-08-19:** tự nới gấp đôi tới một trần cứng, log `warning` mỗi lần nới (đó là tín hiệu khai thiếu); chạm trần cứng thì **ném thật** + log `critical`. ⛔ Đừng đem lập luận của bus sang: bus đầy là **triệu chứng một tiến trình treo**, kho đầy là **tải thật** |
| ~~8~~ | ~~Đuổi bộ nhớ (LRU)~~ | ✅ **CHỐT 2026-08-19: KHÔNG làm LRU.** Lý do y hệt lý do của TTL - xem mục 3.6 |
| ~~9~~ | ~~TTL do framework làm hay app làm~~ | ✅ **TỰ ĐÓNG** - mục 1.4 đã thiết kế TTL nằm trong framework |

---

## 7b. ✅ Job dọn hàng hết hạn: CHỈ CHẠY Ở PRIMARY (chốt 2026-08-19)

Nó thuộc hạng **"chạy hai lần chỉ THỪA"** của [luật 01](../../../../.claude/rules/01-song-song-hoa-va-shard.md)
- bốn tiến trình cùng dọn thì kết quả y hệt, chỉ tốn công. Nên đây **không phải
yêu cầu đúng đắn**, mà là chuyện tiết kiệm.

Nhưng ba lý do khiến vẫn nên chỉ primary:

| | |
|---|---|
| **Ghi LMDB là độc quyền theo file** | N tiến trình cùng dọn thì N-1 tiến trình **xếp hàng chờ khoá ghi**, đúng thứ việc chia `parts` sinh ra để tránh |
| **Nó không phục vụ ai** | Dọn rác không nằm trên đường request, nên không có lý do gì để nó cạnh tranh với đường request |
| **Đã có chỗ đúng cho nó** | **Adapter hạng đơn nhất** - cha chỉ `start()` ở primary. Không cần cờ, không cần khoá phân tán |

⚠ Hệ quả phải nhớ: **primary chết thì việc dọn dừng cho tới khi thăng cấp xong**. Vô
hại - dữ liệu quá hạn vẫn bị lọc lúc đọc (mục 1.4), việc dọn chỉ giải phóng chỗ.

---

## 8. Liên quan

- [`09-kho-lien-tien-trinh-boi-canh.md`](09-kho-lien-tien-trinh-boi-canh.md) - bối
  cảnh, mục **2.7** là chốt phạm vi một máy. ⚠ Bảng *"chưa quyết"* ở mục **3** của
  file đó **đã đóng hết** - đọc như lịch sử lập luận, đừng đọc như việc còn phải làm.
- [`12-kho-refdata.md`](12-kho-refdata.md) - nhóm 1,
  cho dữ liệu **có** nguồn bền vững. Ranh giới hai nhóm nằm ở đó.
- [`11-bus-lien-tien-trinh.md`](11-bus-lien-tien-trinh.md) - bus. Mục
  5 ở trên là đường nâng cấp dùng tới nó.
- [`10-da-tien-trinh.md`](10-da-tien-trinh.md) -
  mô hình chạy nhiều tiến trình.
- [`../rules/config-discovery.md`](../../rules/config-discovery.md) - phép phân loại
  *"người vận hành có đủ thông tin để chọn giá trị này không"*, dùng ở câu 5 mục 7.
