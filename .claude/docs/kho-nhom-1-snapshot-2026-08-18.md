> ⚠ **Tên lớp chốt 2026-08-19 là `RefData`, KHÔNG phải `Snapshot`.** Tên file giữ
> nguyên chữ "snapshot" vì nó là mốc ngày, đừng đọc nó như tên API. Mọi chỗ trong tài
> liệu đã đổi.

# Kho nhóm 1 - `RefData` (bộ nhớ chung, không LMDB) - thiết kế 0.8

> Chốt **2026-08-18**, cùng ngày với [`bus-lien-tien-trinh-2026-08-18.md`](bus-lien-tien-trinh-2026-08-18.md).
> Tách ra khỏi [`cache-lien-tien-trinh-2026-08-16.md`](cache-lien-tien-trinh-2026-08-16.md)
> theo yêu cầu của chủ dự án: *"phần không dùng LMDB trước đi, hai phần cũng có ranh
> giới nên cái đầu đi"*.
>
> **Thiết kế, chưa có một dòng code nào.**

## 0. Đọc gì trong hai phút

| Nếu bạn cần | Đọc |
|---|---|
| Biết cái gì thuộc nhóm 1, cái gì thuộc LMDB | mục 1 |
| Sắp code | mục 3 (cấu trúc) rồi mục 4 (cơ chế) |
| Xem API | mục 5 |
| Biết còn treo gì | **mục 10** |

Năm câu tóm tắt:

1. **Nhóm 1 = dữ liệu CÓ NGUỒN BỀN VỮNG**, đọc nhiều, ghi hiếm, **thay trọn gói**. Mất thì nạp lại được.
2. **Hai bản, đổi con trỏ.** Người ghi dựng trọn bản mới vào ô không ai đọc rồi đổi con trỏ.
3. **`publish()` chỉ primary**; mọi tiến trình `read()`. Người khác gọi `publish()` thì **nổ**.
4. **`read()` trả object thật**, không phải bytes - nhờ **số đời làm chìa khoá cho cache L1** trong tiến trình.
5. **`None` nghĩa là CHƯA SẴN SÀNG**, khác hẳn "tập rỗng". Chờ thì chờ ở tầng khởi động, không chờ trong `read()`.

---

## 1. Ranh giới hai nhóm

**Phân theo: dữ liệu có nguồn bền vững hay không.**

| | **Nhóm 1 (file này)** | Nhóm 2 (LMDB) |
|---|---|---|
| Ví dụ | khoá JWT từ Trust · danh bạ app · cấu hình đã phân giải | hãm nhịp · khoá phân tán · thử thách passkey |
| Mất thì | **nạp lại được** | **mất hẳn** |
| Ghi | **hiếm**, và **thay trọn gói** | thường xuyên, sửa từng key |
| Đọc | **rất nhiều**, trên đường nóng | nhiều |
| Cần phép nguyên tử | **không** | **có** (`incr`, `set_if_absent`) |
| Hiện thực | **tự viết trên `shared_memory`** | thư viện `lmdb` |

⭐ Ranh giới này **trùng khớp** với ranh giới [luật 01](../../../.claude/rules/01-song-song-hoa-va-shard.md)
đã vẽ từ 2026-08-04 (*cache có nguồn bền vững KHÔNG phải nợ; trạng thái mà lời gọi
sau phụ thuộc vào thì phải ra khỏi RAM*). Hai bên nghĩ ra độc lập rồi gặp nhau.

### Vì sao tự viết ở đây RẺ, và ba lý do đó chỉ đúng với nhóm 1

1. **Không cần bộ cấp phát bộ nhớ.** Dữ liệu thay **trọn gói** (xoay khoá là có tập
   khoá mới, không phải sửa một khoá trong tập), nên không có cấp và thu từng entry.
   Đây là phần đắt nhất và rủi ro nhất của việc tự viết kho, và nó **không xuất hiện**.
2. **Không có khoá nào cả.** Người đọc không giữ gì, nên người đọc chết không để lại
   hậu quả.
3. **Người ghi chết giữa chừng cũng không sao.** Nó viết vào ô không ai đọc; con trỏ
   chưa đổi nên mọi người vẫn thấy bản cũ nguyên vẹn.

⚠ **Cả ba lý do này MẤT khi sang bus** (bus cần cấp phát, cần khoá, có nhiều người
ghi). Đó là lý do bus phải là một cấu trúc khác trên cùng loại bộ nhớ - xem mục 1 của
tài liệu bus. **Dùng lại vật liệu thì được, dùng lại sự dễ dàng thì không.**

---

## 2. Vì sao làm nhóm 1 TRƯỚC

Ngoài chuyện nó đơn giản hơn, nó còn **cắt bớt một vấn đề đang treo ở chỗ khác**:

```text
Hôm nay:   mọi tiến trình gọi Trust để có khoá verify JWT
Có nhóm 1: primary gọi Trust -> publish()
           tiến trình phụ    -> read()   <- KHÔNG chạm mạng lần nào
```

Cái vướng của [luật 2.7](da-tien-trinh-main-va-cau-hinh-2026-08-16.md#27--chốt-chiều-2026-08-16-di-dựng-đủ-ở-mọi-tiến-trình-cái-nào-không-được-chạy-thì-tắt-bằng-cờ)
(*"`post_construct` không được chạm mạng"*, trong khi khoá JWT phải nạp từ Trust) co
từ **mọi tiến trình** xuống **chỉ primary**. Không giải hết, nhưng cắt phần lớn bề
mặt.

Cùng lý do, câu 7.1 (`TrustKeyL2Cache`) cũng nhẹ đi: trong phạm vi một máy, nhiều
tiến trình dùng chung một bản thay vì mỗi tiến trình một bản.

---

## 3. Cấu trúc

### 3.1. Hình dạng

```text
Vùng nhớ của snapshot "jwt-keys"
┌──────────────────────────────────────────────────────────┐
│ HEADER                                                   │
│   so_doi        8B    0 = CHƯA AI PUBLISH LẦN NÀO        │
│   con_tro       1B    0 hoặc 1 - bản nào đang dùng       │
│   nguoi_ghi     1B    id tiến trình đang giữ quyền ghi   │
│   ghi_luc       8B    monotonic_ns, CHỈ để quan sát      │
│   so_doan       2B    số đoạn dữ liệu đang có            │
│   do_dai_A/B    4B+4B                                    │
├──────────────────────────────────────────────────────────┤
│ bản A                                                    │
│ bản B                                                    │
└──────────────────────────────────────────────────────────┘
```

⚠ **Tổng = 2 × `max_bytes` + header.** Khai `max_bytes = 64 KB` là mất **128 KB**, và
trên Windows là mất **thật** ngay lúc khởi động (không thưa như Linux).

### 3.2. `con_tro` là 1 byte, và đó không phải chuyện tiết kiệm

Ghi một byte là **nguyên tử trên mọi kiến trúc thực tế**, nên người đọc không bao giờ
thấy một giá trị nửa vời. Đừng đổi nó thành `int` nhiều byte để "cho gọn".

### 3.3. ⭐ Chia đoạn khi dữ liệu lớn (chủ dự án chốt 2026-08-18)

Nguyên văn: *"nếu nó nặng quá thì cắt file ra thành từng đoạn rồi ghi vào từng phần,
cấp phát liên tục. Còn nếu nhỏ mà ước tính được thì cấp phát một lần."*

```text
con_tro  ->  danh sách đoạn:  ["jwt-keys-a3f9-0", "jwt-keys-a3f9-1", ...]
```

Mỗi đoạn là một `shared_memory` riêng. Ba điều kiện để nó không mất giá trị:

| | |
|---|---|
| **Chỉ THÊM đoạn, không bao giờ thu trong một lần chạy** | Thu thì phải đếm xem ai còn đọc đoạn cũ. App restart là sạch, mà nhóm 1 tăng chậm |
| **Người đọc tự attach đoạn lạ**, không ai phải đồng bộ | Thấy số đời mới, thấy tên đoạn chưa biết thì attach. Người ghi không chờ ai |
| ⭐ **`decode` đọc theo dòng, đừng nối đoạn trước** | `msgpack` có `unpacker.feed(chunk)`. Nối thành một `bytes` liền là **một lần copy toàn bộ** - vứt đi chính thứ đang cố giữ |

> ⭐ **Thứ tự làm: khai hình dạng NGAY từ v1 (con trỏ trỏ tới danh sách đoạn), nhưng
> v1 chỉ dùng MỘT đoạn.** Nếu v1 làm "một vùng liền" thì ngày cần nhiều đoạn là đổi
> cấu trúc vùng nhớ, tức đổi cách mọi tiến trình đọc.

---

## 4. Cơ chế

### 4.1. Ghi - thứ tự bắt buộc

```text
1. encode() ra bytes (hoặc danh sách đoạn)
2. ghi vào ô KHÔNG được con trỏ trỏ tới
3. ghi do_dai của ô đó
4. đổi con_tro sang ô vừa ghi        <- 1 byte, nguyên tử
5. TĂNG so_doi                        <- SAU CÙNG
6. ghi_luc = monotonic_ns()
7. (tuỳ chọn) announce qua ProcessLink
```

**Bước 5 phải sau cùng.** `so_doi` là thứ người đọc dùng để xác nhận dữ liệu nhất
quán; tăng nó trước khi con trỏ đổi xong là mời người đọc tin vào một bản chưa xong.

### 4.2. Đọc - seqlock

```text
1. doi_1   = đọc so_doi
2. nếu doi_1 == 0  ->  trả None (CHƯA SẴN SÀNG), dừng
3. nếu doi_1 == doi_da_unpack  ->  trả object trong cache L1, dừng    <- đường thường lệ
4. con_tro = đọc con trỏ, đọc dữ liệu ở ô đó
5. doi_2   = đọc lại so_doi
6. nếu doi_2 != doi_1  ->  làm lại từ bước 1 (có trần số vòng)
7. decode(), lưu vào cache L1 cùng doi_1, trả object
```

⚠ **Bước 3 là đường chạy 99,99% số lần**: một phép so số nguyên, không đọc dữ liệu,
không decode, không copy.

### 4.3. ⚠ Ca mà hai bản A/B KHÔNG tự né được

```text
người đọc: đọc con trỏ = A ... rồi bị hoãn (GC, OS cắt lượt)
người ghi: publish lần 1 (A->B), publish lần 2 (B->A), đang ghi ĐÈ lên A
người đọc: tỉnh dậy, đọc A  ->  RÁCH
```

Với ghi vài giờ một lần thì gần như không thể. Nhưng *"gần như"* không phải một bảo
đảm, và loại lỗi này **không có triệu chứng** - nó ra một lỗi msgpack ngẫu nhiên mỗi
vài tháng. Đó là lý do bước 5 và 6 của 4.2 **bắt buộc**, không phải phòng xa.

⚠ **Một giả định phải khai ra:** x86 có thứ tự ghi mạnh nên seqlock kiểu này gần như
luôn đúng; **ARM thì yếu hơn** và về lý thuyết cần rào bộ nhớ, thứ CPython không phơi
ra. Xime chưa chạy ARM, nhưng đây là loại giả định nên nằm trong tài liệu chứ đừng
nằm ngầm.

**Trần số vòng lặp lại** phải có, kèm log. Vòng lặp vô hạn im lặng là cách hỏng tệ
nhất.

### 4.4. Cache L1: số đời làm chìa khoá

```python
def read(self):
    doi = self._doc_so_doi()
    if doi != self._doi_da_unpack:
        self._object = self.decode(self._doc_ban_dang_dung())
        self._doi_da_unpack = doi
    return self._object
```

⚠ **Object trả về là DÙNG CHUNG trong tiến trình, không được sửa.** Sửa nó là sửa bản
của mọi người. Framework **không chặn** - cùng ranh giới đã chốt cho `read_only()` ở
0.6.3 (chặn được thì phải hook và trả phí runtime cho mọi lời đọc, trái nguyên tắc
minimal magic). Bù bằng quy tắc tài liệu.

### 4.5. Quyền ghi: chỉ primary, và **nổ** nếu sai

Cơ chế hai bản chỉ đúng với **đúng một người ghi**. Hai người cùng dựng bản mới vào ô
trống là hỏng, và **hỏng im lặng**.

`nguoi_ghi` nằm trong header; `publish()` từ tiến trình khác thì **ném**, không log
rồi bỏ qua. Cùng khuôn `nguoi_nhan` của bus.

---

## 5. API

### 5.1. Khuôn: subclass, giống `CrudRepository[T]`

```python
# app/snapshot/jwt_keys.py
class JwtKeyRefData(RefData[JwtKeySet], name="jwt-keys", max_bytes=64 * 1024):
    def encode(self, value: JwtKeySet) -> bytes: ...
    def decode(self, raw: memoryview) -> JwtKeySet: ...
```

> ⚠ **ĐỔI 2026-08-19: cấu hình đi bằng THAM SỐ CLASS, không phải thuộc tính trong
> thân.** Bản 08-18 khai `name = "jwt-keys"` và `max_bytes = ...` trong thân class.
> Chủ dự án chốt hôm sau rằng **cấu hình và dữ liệu phải tách**, nên cả `RefData` lẫn
> `Store` dùng PEP 487. Lý do đầy đủ và ba cách đã loại nằm ở
> [tài liệu nhóm 2](kho-nhom-2-store-2026-08-19.md), mục 1.1.

```python
# app/config/snapshots.py
from xime.core.refdata import configure_refdata
from app.snapshot.jwt_keys import JwtKeyRefData

configure_refdata([JwtKeyRefData, AppRegistryRefData])
```

```python
# noi doc - moi tien trinh
class TrustKeyProvider:
    def __init__(self, snap: JwtKeyRefData):        # inject THANG, co kieu
        self._snap = snap

    def keys(self, kid: str | None) -> Sequence[KeyContext]:
        return self._refdata.read_or_fail().resolve(kid)

# noi ghi - CHI primary
await self._refdata.publish(keyset_moi)
```

### 5.2. Năm chỗ ăn khớp với thứ đã có (không phải khớp ngẫu nhiên)

1. **`configure_refdata([Class, ...])` truyền CLASS** - đúng khuôn
   `configure_link(handlers=[...])` và `configure_jwt(key_provider=...)` của 0.7.2.
2. **Một chỗ khai duy nhất.** Framework import class lúc config chạy (**trước DI**),
   đọc `name` + `max_bytes` để cha tạo vùng nhớ; tới lúc dựng DI mới dựng instance.
3. **Lớp nền abstract nên scanner bỏ qua**, chỉ subclass vào DI - y hệt `CrudRepository`.
4. **Generic `[T]`** nên IDE và `mypy --strict` hiểu `read()` trả gì.
   `snapshots.get("jwt-keys")` kiểu chuỗi thua hẳn ở điểm này.
5. **`read()` / `read_or_fail()`** đúng cặp `find()` / `find_or_fail()` của
   `CrudRepository`, và `EntityNotFoundError` là tiền lệ cho `RefDataNotReadyError`.

### 5.3. Ba kết cục, không cần thêm bit cờ

Chủ dự án hỏi có cần một bit làm cờ không. **Không cần** - `so_doi` đã phân biệt đủ,
và thêm bit là tạo hai nguồn sự thật cho cùng một câu hỏi:

| `so_doi` | Nghĩa | `read()` trả |
|---|---|---|
| `0` | **chưa ai publish lần nào** = chưa sẵn sàng | `None` |
| `> 0`, dữ liệu rỗng | đã có bản, và **bản đó thật sự rỗng** | object rỗng |
| `> 0`, có dữ liệu | bình thường | object |

`None` mang **đúng một** nghĩa nên không phạm [luật 03](../../../.claude/rules/03-mot-gia-tri-mot-nghia.md),
và `T | None` thì `mypy` ép người gọi xử lý nhánh đó.

⚠ Cảnh báo gốc của tài liệu cache vẫn nguyên: *rỗng phải mang nghĩa "chưa sẵn sàng",
không được lẫn với "không có khoá nào" - lẫn thì lúc khởi động có cửa sổ mà request
xác thực **bị từ chối oan, hoặc tệ hơn là được cho qua**.*

### 5.4. Chờ khi chưa sẵn sàng - chủ dự án chốt

Nguyên văn: *"mấy tiến trình nói chuyện được với nhau mà. `None` thì chờ, nào cái kia
ghi xong báo tôi đã xong thì đọc lại."*

Ba chi tiết đi kèm:

| | |
|---|---|
| ⛔ **`read()` KHÔNG tự chờ** | Chờ trong `read()` là treo request. Chờ là một lời gọi riêng: `await refdata.wait_ready(timeout)` |
| **Chờ ở tầng khởi động**, không ở đường phục vụ | Tiến trình chưa nhận request cho tới khi các snapshot **bắt buộc** đã sẵn sàng |
| ⚠ **Phải có timeout** | Primary có thể chết trước khi kịp publish. Chờ vô hạn là treo cả tiến trình mà không ai biết vì sao |

📌 Các lần publish **sau lần đầu** thì **không cần bus**: đọc `so_doi` là biết. Bus chỉ
cần cho ca chờ lần đầu, và (tuỳ chọn) để tiến trình chủ động decode lại trước khi
request tới, giảm độ trễ của request đầu sau mỗi lần xoay khoá.

---

## 6. Vòng đời

Dùng chung với bus, không có gì riêng:

```text
CHA:  1. sinh mã lần chạy (link_id, random)
      2. tạo vùng nhớ cho từng snapshot + từng kênh bus
      3. sinh PRIMARY trước
      4. sinh các con còn lại NGAY, KHÔNG đợi primary publish xong
         (chốt 2026-08-19 - con nào cần thì tự chờ, xem câu 1 mục 10)
        │
CON:  1. đọc biến môi trường
      2. ATTACH vùng nhớ                  <- CHƯA có DI
      3. import config, dựng DI
      4. khởi động adapter
```

⭐ **RefData dựng TRƯỚC DI**, không qua `post_construct` - nó là hạ tầng của
framework. Cùng lập luận và cùng bước với bus, và nó **đóng câu 8 của tài liệu cache**.

> ### ✅ Bước 4 ĐÃ BỎ - chủ dự án chốt 2026-08-19: **sinh con đồng thời, không đợi**
>
> Nguyên văn: *"sinh con đồng thời, None thì chúng đợi nhau, **chúng có thể nói chuyện
> được với nhau mà**"*.
>
> Cơ chế chờ qua bus (mục 5.4) đã xử lý trọn tình huống `None`, nên việc cha đợi chỉ là
> một tối ưu để xoá hẳn `None` khỏi tiến trình phụ - và nó đổi lấy hai thứ: **khởi động
> cả cụm chậm đi** bằng thời gian primary nạp xong, và phải khai thêm *"snapshot nào là
> bắt buộc"*. Không đáng.
>
> ⭐ Đây là ca thứ hai trong ngày mà **một câu treo hoá ra đã có đáp án ở chỗ khác** -
> giống câu 8 của tài liệu cache. Đáng nhớ: khi một mảnh thiết kế mới ra đời (ở đây là
> cơ chế chờ), nên rà lại danh sách câu treo xem nó vừa đóng cái nào.
>
> Phần dưới giữ làm lịch sử lập luận.

⭐⭐ **Bước 4 (ĐÃ BỎ) từng CÓ TÊN: đó là `run_once()`** (chốt cuối ngày 2026-08-18, xem banner đầu
mục 2.9 của [tài liệu đa tiến trình](da-tien-trinh-main-va-cau-hinh-2026-08-16.md)).
Primary `publish()` snapshot bắt buộc **trong `run_once()`**, rồi báo cha. Đề xuất đáng
cân nhắc: nếu cha đợi primary publish xong rồi mới sinh
các con còn lại thì `read()` trả `None` **không bao giờ xảy ra ở tiến trình phụ**. Cửa
sổ chỉ còn trong lòng chính primary, nơi code khởi động của nó kiểm soát được. Giá
phải trả: khởi động cả cụm chậm đi bằng thời gian primary nạp xong (một lời gọi Trust,
vài trăm ms), và phải khai **snapshot nào là bắt buộc**. Dùng lại đúng tín hiệu ready
của F10, không thêm cơ chế.

⛔ **ĐÃ BÁC 2026-08-19** (câu 1 mục 10): cha **KHÔNG đợi**, sinh con đồng thời. Chủ dự
án chỉ ra câu này **đã có đáp án từ 08-18** - cơ chế chờ qua bus xử lý gọn rồi, nên
việc cha đợi chỉ là **tối ưu thêm**, mà nó đổi lấy khởi động chậm cả cụm cộng một
nghĩa vụ khai báo mới.

**Tên vùng nhớ, dọn rác, bẫy Windows cấp phát thật**: y hệt bus, xem mục 6 của tài
liệu đó. Không lặp lại ở đây.

---

## 7. Quan sát

```python
@dataclass(frozen=True)
class RefDataStats:
    name: str
    so_doi: int              # 0 = chua san sang
    ghi_luc_ms: int | None   # lan publish cuoi
    dung_bytes: int
    tran_bytes: int
    so_doan: int
    nguoi_ghi: str | None
    loi_thoi: bool           # publish gan nhat that bai vi vuot tran
```

Cùng ba nguyên tắc đã chốt cho `stats()` của bus: **ảnh chụp gần đúng** (không giữ
khoá, docstring phải nói thẳng) · **trả toàn cụm** · **counter không reset**.

Framework tự kêu, không đợi app hỏi:

| Sự kiện | |
|---|---|
| `dung_bytes` vượt **80%** trần | log WARNING. **Đây là lớp thật sự cứu** |
| `publish()` vượt trần | log CRITICAL + đặt `loi_thoi = True` |
| `decode()` hỏng | log CRITICAL |

---

## 8. Vượt trần: vì sao nó nguy hơn ở bus

Với bus, payload quá cỡ là bug lập trình. Với snapshot thì:

> Primary không `publish()` được → **mọi tiến trình dùng bản cũ mãi mãi**. Khoá JWT đã
> xoay mà cả cụm vẫn verify bằng khoá cũ, và **không request nào lỗi** cho tới khi
> token ký bằng khoá mới xuất hiện.

Ba lớp, không phải một:

1. **Cảnh báo ở 80% trần** - lớp thật sự cứu, vì nó báo trước.
2. **Vượt thì `publish()` nổ, giữ nguyên bản cũ** - bản cũ vẫn đúng, không hỏng dữ liệu.
3. **Đánh dấu `loi_thoi` trong `stats()`** - một `publish` thất bại mà không ai biết
   là chỗ tệ nhất.

Cộng với cơ chế chia đoạn ở 3.3 khi dữ liệu thật sự lớn.

---

## 9. Kiểm thử

Cùng luật với bus: **phải spawn tiến trình thật**. Bài học đã trả giá ở lỗi đua
scheduler (sống sót qua 1512 test vì chạy trên `AsyncMock`), ghi trong
[`rules/background-tasks.md`](../rules/background-tasks.md) mục 4.

Bốn ca bắt buộc:

```text
1. primary publish, tiến trình khác read được đúng object
2. đọc trong lúc đang publish -> luôn ra một bản NGUYÊN VẸN (cũ hoặc mới, không rách)
3. read() trước khi publish lần nào -> None, KHÔNG phải object rỗng
4. tiến trình không phải primary gọi publish() -> NỔ
```

Ca 3 đi **thành cặp** với ca đối chứng: publish một tập rỗng rồi read phải ra **object
rỗng**, không phải `None`. Chỉ có một vế thì cách sửa sai *"luôn trả None khi rỗng"*
cũng qua được.

---

## 10. Còn treo: HẾT

### ✅ TÁM CÂU ĐÃ CHỐT HẾT 2026-08-19 - giữ bảng làm lịch sử quyết định

| # | Câu | Đề nghị của phiên |
|---|---|---|
| ~~1~~ | ~~**Cha có đợi primary publish xong rồi mới sinh các con còn lại không**~~ | ✅ **CHỐT 2026-08-19: KHÔNG. Sinh con đồng thời.** Chủ dự án chỉ ra câu này **đã có đáp án từ 08-18** ở mục 5.4: *"None thì chúng đợi nhau, chúng nói chuyện được với nhau mà"*. Cơ chế chờ qua bus đã xử lý gọn, nên việc cha đợi chỉ là một **tối ưu thêm** - và nó đổi lấy khởi động chậm cả cụm cộng phải khai *snapshot nào bắt buộc*, để tránh một tình huống vốn đã có đường xử lý |
| ~~2~~ | ~~`publish()` **sync hay async**~~ | ✅ **CHỐT 2026-08-19: bất đồng bộ.** `encode()` trong executor (msgpack một dict lớn tốn mili giây), memcpy chạy thẳng. Nó hiếm nên chi phí chuyển tầng không đáng |
| ~~3~~ | ~~`decode()` **ném lỗi thì sao**~~ | ✅ **CHỐT 2026-08-19: ném ra**, cộng đánh dấu trong `stats()`. Trả bản cũ là nói dối về số đời. Cùng lý do đã chốt cho `LifecycleManager` 2026-07-30: đừng dọn thay để rồi che lỗi gốc |
| ~~4~~ | ~~Mỗi RefData **một vùng nhớ riêng** hay chung~~ | ✅ **CHỐT 2026-08-19: RIÊNG.** Nguyên văn: *"các bảng nên **không liên quan gì đến nhau. kể cả bộ nhớ**"*. Được ba thứ: kích thước độc lập (khoá JWT 64 KB, danh bạ app 1 MB) · **thêm/bớt một bảng không đổi bố cục của bảng khác** · `publish()` một cái không chạm byte nào của cái kia. Tổng RAM **bằng nhau** ở cả hai cách nên không mất gì. Cùng lý do đã chốt *"một bảng một file LMDB"* |
| ~~5~~ | ~~Cache L1 có cần khoá giữa các luồng~~ | ✅ **CHỐT 2026-08-19: không.** Nguyên văn: *"nào đa luồng tính tiếp"*. Ghi thành **ràng buộc** để ngày bật `N>1` biết đây là chỗ phải xem lại |
| ~~6~~ | ~~Tên lớp~~ | ✅ **CHỐT 2026-08-19: `RefData`.** Chủ dự án chọn nó thay vì `Snapshot` sau khi cân bốn tên. Nó là thuật ngữ chuẩn cho *dữ liệu ít đổi, đọc nhiều*, và sát ca dùng thật (khoá, thông số cấu hình). ⚠ Hai tên đã loại kèm lý do: `Registry` (gợi ý thêm/bớt **từng mục**, ngược với *thay trọn gói*) · `Catalog` (gợi ý duyệt nhiều mục, mà đây chỉ có **một** giá trị) |
| ~~7~~ | ~~Trần số vòng seqlock lặp lại~~ | ✅ **CHỐT 2026-08-19: trần 100 vòng, quá thì NÉM.** ⭐ Lý do đặt trần **không phải để xử lý ca thường** (có hai bản A/B nên người đọc và người ghi không đụng nhau; lặp quá một vòng gần như không xảy ra) mà là: **không trần thì một lỗi lạ biến thành request treo vô hạn, không log, không triệu chứng**. Có trần thì nó thành một exception chỉ đúng chỗ |
| ~~8~~ | ~~Quyền ghi chuyển thế nào khi **thăng cấp primary**~~ | ✅ **CHỐT 2026-08-19: đúng như đề nghị** - dính vào cơ chế thăng cấp nên chốt cùng lúc với chỗ đó, không quyết riêng ở đây. Câu con của mục 4.5 |

### Đã chốt trong buổi này

`RefData[T]` subclass · object chứ không bytes · primary ghi · `None` = chưa sẵn
sàng và **không cần bit cờ** · chờ qua bus khi chưa sẵn sàng · chia đoạn khi lớn ·
thứ tự ghi và thứ tự đọc ở mục 4.

---

## 11. Liên quan

- [`bus-lien-tien-trinh-2026-08-18.md`](bus-lien-tien-trinh-2026-08-18.md) - dùng chung
  `link_id`, cách dọn rác, bẫy Windows, khuôn `stats()`, và **kênh báo "đã sẵn sàng"**.
- [`cache-lien-tien-trinh-2026-08-16.md`](cache-lien-tien-trinh-2026-08-16.md) - buổi
  gốc chốt hướng hai nhóm. ⚠ Nay chỉ còn là **bối cảnh** - nhóm 2 đã tách sang
  [`kho-nhom-2-store-2026-08-19.md`](kho-nhom-2-store-2026-08-19.md) và chốt xong.
- [`da-tien-trinh-main-va-cau-hinh-2026-08-16.md`](da-tien-trinh-main-va-cau-hinh-2026-08-16.md)
  - mô hình chạy, thứ tự khởi động, và **luật 2.7** mà nhóm 1 vừa cắt bớt một mảng.
- [Luật 01](../../../.claude/rules/01-song-song-hoa-va-shard.md) - ranh giới *cache có
  nguồn bền vững không phải nợ*, trùng khớp với ranh giới hai nhóm ở mục 1.
- [Luật 03](../../../.claude/rules/03-mot-gia-tri-mot-nghia.md) - `None` = chưa sẵn
  sàng, tách khỏi "tập rỗng".
