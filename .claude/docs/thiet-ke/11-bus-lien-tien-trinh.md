# Bus liên tiến trình (`ProcessLink`) - thiết kế 0.8

> Chốt **2026-08-18**. Thay hẳn phần Bus của [`../da-phu-dinh/ke-hoach-0.8-ban-dau.md`](../da-phu-dinh/ke-hoach-0.8-ban-dau.md)
> (bản 2026-06-27), thứ mà buổi 08-16 đã lật phần lớn.
>
> ✅ **ĐÃ CODE 2026-08-20** (giai đoạn 2 của kế hoạch thi công): `xime/core/link/`,
> **90 test**, năm ca bắt buộc ở mục 9 đều chạy bằng **tiến trình thật**. Tài liệu
> người dùng: `docs/{vn,en}/process-link.md`.
>
> ⚠ Dòng cũ *"đây là thiết kế, chưa có một dòng code nào"* hết đúng từ ngày đó.
>
> ⚠⚠ **MỘT CHỖ CỦA THIẾT KẾ ĐÃ ĐỔI lúc thi công**, chủ dự án chốt 2026-08-20 sau
> khi xem phép đo: **thứ tự hai bước cuối khi ghi một dòng** đảo lại, và bước đè
> thêm việc hạ bit. Bản cũ giữ nguyên ở
> [4.1b](#41b-bản-cũ-của-thứ-tự-ghi-giữ-làm-lịch-sử). Đọc
> [4.1](#41-ghi-không-tranh-chấp-vì-mỗi-người-một-vùng) trước khi động vào đường ghi.

## 0. Đọc gì trong hai phút

| Nếu bạn cần | Đọc |
|---|---|
| Hiểu nó **là cái gì và khác `EventBus` chỗ nào** | mục 1, kèm **giới hạn `N = 1`** |
| Sắp code | mục 3 và 4 (cấu trúc + cơ chế), rồi mục 5 (API) |
| Sắp bàn lại một hướng | **mục 11** trước, 19 hướng đã loại kèm lý do |
| Cần con số | mục 10, đừng đo lại |
| Muốn biết nó **đỡ được gì cho phần khác của 0.8** | **mục 12** |

Bốn câu tóm tắt toàn bộ:

1. **Bộ nhớ chung, không socket.** Mỗi kênh một vùng nhớ, mỗi tiến trình một **vùng ghi riêng** trong đó nên **không có tranh chấp ghi** và **thứ tự được giữ**.
2. **Bitmap "ai chưa đọc" là sự thật, semaphore chỉ là chuông.** Thức dậy thì quét, quét không thấy gì thì ngủ tiếp.
3. **Cha không nằm trên đường đi.** Nó tạo vùng nhớ, sinh con, dọn bit của con đã chết. Không chuyển tiếp tin nào.
4. **Framework quản header, app quản payload.** Payload là bytes thô, framework không giải mã, không có sổ đăng ký kiểu.

---

## 1. Nó là cái gì, và nó KHÁC `EventBus`

⚠ Đây là chỗ dễ nhầm nhất, và nhầm thì **không có triệu chứng**: tin không bao giờ
ra khỏi tiến trình, không lỗi, không log.

| | `EventBus` (`core/event/bus.py`) | **`ProcessLink`** (mới) |
|---|---|---|
| Phạm vi | **trong một tiến trình** | **giữa các tiến trình** |
| Chở gì | object Python, không serialize | **bytes**, qua bộ nhớ chung |
| Chở loại gì | **event** - đã xảy ra rồi, ai quan tâm thì nghe | **lệnh và câu hỏi** - có đích, có thể chờ trả lời |
| Phản hồi | không có | **có** (`ask`) |
| Handler chạy | `create_task`, song song | **tuần tự theo kênh** |
| Đăng ký | `subscribe(Type, handler)` | `@on_announce` / `@on_request` |

Hai thứ **không dùng chung một dòng code nào**, và tên cố ý không chung gốc từ:
`link.ask(...)` với `event_bus.publish(...)` không thể gõ nhầm thành nhau.

### ⚠ Giới hạn phải khai ra: thiết kế này dành cho `N = 1` luồng mỗi tiến trình

Đơn vị của bus là **TIẾN TRÌNH**, không phải luồng: một semaphore cho mỗi tiến trình,
một bit cho mỗi tiến trình. Đúng với mô hình `M` tiến trình `× N = 1` luồng, tức thứ
[đã chốt làm trước](09-kho-lien-tien-trinh-boi-canh.md) (*"đa tiến trình trước, đa
luồng để sau"*).

Ngày bật `N > 1` thì **cấu trúc chia sẻ không phải đổi**, chỉ thêm một tầng bên trong
tiến trình: một loop giữ vòng đọc, rồi phân phối cho các loop khác. ⚠ Tầng đó
**không được dùng `asyncio.Queue`** - primitive của asyncio gắn chặt một event loop
(xem mục 4.3 của tài liệu cache), nên phải là `loop.call_soon_threadsafe`.

Ghi ra để không ai đọc bản này rồi tưởng nó đã phủ `N > 1`.

### Vai sau khi tách kho khỏi bus

Quyết định 2.1 của [`09-kho-lien-tien-trinh-boi-canh.md`](09-kho-lien-tien-trinh-boi-canh.md)
đã tách **trạng thái** ra khỏi **sự kiện**. Nên `ProcessLink` chỉ còn chở **tín hiệu**:
thưa, nhỏ, có đích. Dữ liệu đi LMDB và vùng nhớ chung nhóm 1.

Ranh giới thực dụng: **thứ 4 KB không đủ chứa thì đó là dữ liệu, không phải tín hiệu.**

### Ca dùng đầu tiên, và nó là lý do bus tồn tại

Web nhận *"dừng băng tải BT-01"*, nhưng dây Modbus tới BT-01 nằm ở tiến trình
`line-2`. Luật đã chốt ở [`10-da-tien-trinh.md`](10-da-tien-trinh.md)
mục 5.7.3: **web không gọi thẳng adapter fieldbus** - đọc qua DB hoặc vùng nhớ
chung, **ghi qua bus**.

---

## 2. Định tuyến: kênh + khoá, lọc ở bên nhận

### 2.1. Không có địa chỉ tiến trình, ở bất cứ đâu

> Người gửi khai *"gửi trên kênh `fieldbus`, dành cho `BT-01`"*.
> Nó **không bao giờ** khai *"gửi tới `line-2`"*.

Lý do là lý do đã dùng để chặn `current_process_id()`: có tên tiến trình trong tay
thì sớm muộn có người viết `if process_id == "main"` trong use case, và dời một dây
Modbus sang tiến trình khác thành **sửa code** thay vì sửa cấu hình.

### 2.2. Bên nhận lọc, và nó lọc mà **chưa chạm payload**

`key` nằm ở header nên framework đọc được và đưa thẳng cho handler:

```python
@on_request("fieldbus")
async def dieu_khien(self, key: str, payload: bytes) -> bytes | None:
    if key not in self.thiet_bi_cua_toi:
        return None                    # chua he cham vao payload
    lenh = self.giai_ma(payload)       # chi giai ma khi da biet la cua minh
```

Ba tiến trình không liên quan bỏ qua tin **không tốn một lần giải mã nào**.

⚠ Không thể khai danh sách khoá trong decorator: **khoá đến từ cấu hình, không từ
code**. Luật fieldbus đã chốt *"tên thực thể không bao giờ là hằng trong code
nghiệp vụ"*.

### 2.3. Trả `None` chính là cách nói "không phải của tôi"

| Handler trả | Framework làm |
|---|---|
| `None` | chỉ hạ bit. **Không** ghi `nguoi_nhan` |
| `bytes` | ghi `nguoi_nhan` = id của tôi; nếu là `ask` thì ghi dòng trả lời |

Không ai trả khác `None` cho tới lúc người hỏi hết giờ thì `nguoi_nhan` vẫn là 255,
tức **`NoOwner`**. Cơ chế bốn kết cục chạy mà không cần thêm khái niệm nào.

---

## 3. Cấu trúc dữ liệu

### 3.1. Một kênh = một vùng nhớ chung, chia N vùng ghi

```text
Vùng nhớ của kênh "fieldbus"
┌────────────────────────────────────────────────────────────┐
│ HEADER KÊNH                                                │
│   so_dong_moi_vung · co_payload · so_tien_trinh             │
│   missed[0..N-1]        <- đếm tin bị đè khi người đó chưa đọc │
├────────────────────────────────────────────────────────────┤
│ BITMAP, xếp thành N dãy LIỀN NHAU (không rải trong dòng)    │
│   dãy bit chưa-đọc của tiến trình 0   (1 bit / dòng)        │
│   dãy bit chưa-đọc của tiến trình 1                         │
│   ...                                                       │
├────────────────────────────────────────────────────────────┤
│ VÙNG GHI của tiến trình 0   <- CHỈ tiến trình 0 ghi         │
│ VÙNG GHI của tiến trình 1                                   │
│ ...                                                         │
└────────────────────────────────────────────────────────────┘
```

⭐ **Bitmap xếp thành dãy liền nhau, không rải trong từng dòng.** Nhờ vậy tiến
trình 2 thức dậy chỉ cần đọc **dãy của riêng nó** (1024 dòng = 128 byte) rồi
`int.from_bytes(...) != 0` là biết ngay có tin hay không, **một phép so**. Rải
trong dòng thì phải quét cả bảng.

### 3.2. Một dòng

```text
[ da_ghi_xong  1B ]   0 = đang ghi dở, người đọc BỎ QUA
[ loai         1B ]   0 = announce (broadcast) · 1 = request (claim)
[ nguoi_nhan   1B ]   255 = chưa ai nhận
[ nguoi_gui    1B ]   cho dump()
[ ghi_luc      8B ]   monotonic_ns, CHỈ để quan sát
[ so_thu_tu    8B ]   tăng mãi, để sắp đúng thứ tự khi vòng lại
[ correlation 16B ]   ghép ask với reply
[ key         32B ]   bên nhận lọc bằng cái này
[ do_dai       4B ]
[ payload      ... ]  bytes thô, cỡ cố định khai trước
```

### 3.3. Ba trường sinh ra chỉ vì API quan sát, và phải có từ đầu

`missed[]` trong header kênh · `ghi_luc` · `nguoi_gui`. Hàm `stats()` viết lúc nào
cũng được, nhưng **dữ liệu nó đọc thì phải được ghi từ trước**. Thêm sau là đổi
khuôn bảng, tức đổi cách mọi tiến trình đọc.

⚠ `missed` **không thể** nằm trong dòng: nó được tăng **đúng lúc dòng bị đè mất**.

---

## 4. Cơ chế

### 4.1. Ghi: không tranh chấp, vì mỗi người một vùng

> ## ⚠⚠ SỬA 2026-08-20 lúc thi công - THỨ TỰ HAI BƯỚC CUỐI ĐẢO LẠI
>
> Chủ dự án chốt sau khi xem phép đo. Bản dưới đây là bản **đang chạy trong code**;
> bản cũ giữ ở [4.1b](#41b-bản-cũ-của-thứ-tự-ghi-giữ-làm-lịch-sử) để người sau thấy
> nó từng được viết ra và vì sao nó đổi.

```text
1. tìm dòng tiếp theo trong VÙNG CỦA MÌNH (không ai khác đụng vào)
2. nếu dòng đó còn bit chưa đọc  ->  tăng missed[] của những người đó
                                 ->  và HẠ BIT của họ xuống      <- MỚI
3. đặt da_ghi_xong = 0            <- mở dòng ra, nó đang dở
4. ghi payload, key, correlation, so_thu_tu, ghi_luc
5. đặt da_ghi_xong = 1            <- dòng đã dùng được
6. bật bit chưa-đọc của MỌI TIẾN TRÌNH KHÁC   <- SAU CÙNG
7. release semaphore của MỌI tiến trình khác
```

**Bất biến mà thứ tự này giữ, và là thứ đáng nhớ hơn cả bảy bước:**

> **Một bit chưa-đọc chỉ được bật khi dòng nó trỏ tới ĐÃ HOÀN TẤT.**

Lý do nằm ở chỗ **người đọc chỉ tìm thấy một dòng QUA BIT của nó**: bitmap là danh
sách việc phải làm, còn `da_ghi_xong` chỉ là phép kiểm sau đó. Nên bit là thứ phải
đặt sau cùng, không phải trước.

#### Ca mà bản cũ không xét: người ghi chết giữa bước bật-bit và bước hoàn-tất

Bản cũ chống được *"đọc dòng nửa vời"* - và bản mới cũng chống được, y hệt. Chỗ hai
bản khác nhau là **thứ để lại khi người ghi chết đúng khoảng giữa**:

| | Bản cũ (bit trước) | **Bản mới (hoàn tất trước)** |
|---|---|---|
| Đọc được dòng nửa vời? | không | không |
| Để lại gì | **một bit không bao giờ hạ được** | tin mất |
| Đã được khai nhận chưa | ⛔ không có trong danh sách chấp nhận nào | ✅ **at-most-once**, đã khai ở 4.2 |

Bit treo vì vòng đọc làm đúng như 4.2 bảo: thấy cờ 0 thì *"bỏ qua vòng này, xem lại
sau"* - mà bước hạ bit nằm **sau** bước kiểm cờ, nên nó không bao giờ tới lượt.

#### Đo thật 2026-08-20, không phải suy luận

Mô phỏng bằng cách gọi tay từng bước rồi dừng lại (thứ cần đo là **trạng thái để
lại**, không phải cách nó sinh ra):

```text
BẢN CŨ  - chết giữa bước bật-bit và hoàn-tất
  B quét 5 vòng, bit còn lại: [0]        -> CÒN TREO
  A vòng lại đè lên dòng đó -> missed của B = 1
  ⚠ B bị tính là LỠ MỘT TIN, mà tin đó chưa bao giờ hoàn tất

BẢN MỚI - chết giữa hoàn-tất và bật-bit
  B quét 5 vòng, bit còn lại: []          -> đã sạch
  A vòng lại đè lên dòng đó -> missed của B = 0

CA THƯỜNG LỆ (không ai chết): hai bản GIỐNG HỆT NHAU
```

Ba hậu quả của một bit treo, xếp theo mức đáng lo:

| | |
|---|---|
| ⭐ **`missed` đếm sai vĩnh viễn** | Lần đầu người ghi vòng lại tới dòng đó, nó thấy bit còn nên tăng `missed`. Mà `missed` là **chỉ số chẩn đoán chính** của bus - thứ trả lời *"có tiến trình nào đang treo không"*. Nhiễm số đếm giả vào đó là làm hỏng đúng cái đồng hồ dựng lên để nhìn |
| **`unread` không bao giờ về 0** | Kéo theo ngưỡng cảnh báo 80% (7.3) có thể chạm sai và kêu mãi - mà **phép dò kêu oan là phép dò sẽ bị tắt** |
| Lãng phí nhỏ | Mỗi lần thức dậy phải xét thêm một dòng chết |

#### Bước 2 nay hạ bit, và đó là cùng một bản vá

Bản cũ chỉ *"tăng `missed[]`"*. Ở ca thường lệ, hạ bit là **thừa thật** - ngay sau đó
bước 6 bật lại cho mọi người. Nó chỉ có giá trị ở đúng ca trên, chỉ là ở đầu kia của
vòng đời một dòng: người ghi chết **sau khi mở dòng ra để đè**. Không hạ thì dòng đó
mang cờ 0 cộng bit cũ còn nguyên - rò bit y hệt.

⚠ Và thứ tự trong chính bước 2 cũng quan trọng: **hạ bit TRƯỚC khi đặt `da_ghi_xong
= 0`**. Ngược lại thì giữa hai lệnh có một khoảnh khắc "cờ 0 + bit còn", tức đúng
trạng thái vừa đi tránh.

#### Một đường thứ ba đã cân và loại

Giữ thứ tự cũ, nhưng cho vòng đọc **hạ bit ngay cả khi thấy cờ chưa hoàn tất**. Bit
hết treo được, nhưng đổi lại nó hạ nhầm bit của một dòng **đang được ghi hợp lệ** -
biến một ca hiếm (chết đúng khoảng giữa) thành **mất tin ở ca thường lệ**. Loại.

⚠ **Test canh:** `tests_temp/link/test_write_protocol.py` khoá đúng bất biến ở trên
bằng cách soi trạng thái **ngay tại thời điểm** `set_bit` và `write_payload` được
gọi. Không có nó thì ai đó "dọn cho gọn" sẽ đảo lại, và mọi test chức năng vẫn xanh.

### 4.1b. Bản cũ của thứ tự ghi, giữ làm lịch sử

```text
3. ghi payload, key, correlation, so_thu_tu, ghi_luc
4. bật TẤT CẢ bit chưa-đọc lên 1
5. đặt da_ghi_xong = 1        <- sau cùng, đây là dấu "dòng này dùng được"
```

> ~~Bước 5 sau bước 3 và 4 là bắt buộc: người đọc thấy `da_ghi_xong = 0` thì bỏ qua,
> nên **không bao giờ đọc được dòng nửa vời**, kể cả khi người ghi chết giữa chừng.~~

Câu đó **đúng ở vế nó nói** - không ai đọc được dòng nửa vời với thứ tự nào cũng vậy.
Chỗ nó thiếu là **nửa còn lại của cùng câu "kể cả khi người ghi chết giữa chừng"**:
nó xét hậu quả cho *người đọc dòng đó*, không xét hậu quả cho *bit trỏ vào dòng đó*.

📌 Giữ nguyên vết gạch thay vì xoá, vì bản cũ từng là kết luận có chữ **"bắt buộc"**,
và người đọc cần thấy nó từng đúng chứ không chỉ thấy nó sai.

### 4.2. Đọc: hạ bit TRƯỚC, rồi mới làm

```text
1. thức dậy (semaphore) hoặc bị đánh thức lại
2. đọc dãy bit của mình -> có bit nào lên không
3. với mỗi dòng có bit lên, theo thứ tự so_thu_tu:
   a. nếu da_ghi_xong = 0  -> bỏ qua vòng này, xem lại sau
   b. HẠ BIT CỦA MÌNH XUỐNG 0      <- trước khi làm bất cứ gì
   c. gọi handler(key, payload)
   d. nếu handler trả bytes -> ghi nguoi_nhan, và ghi dòng trả lời nếu cần
   e. nếu cả dãy bit của dòng này đã về 0 -> xoá dòng
```

📌 Sau khi [4.1](#41-ghi-không-tranh-chấp-vì-mỗi-người-một-vùng) đảo thứ tự
(2026-08-20), nhánh **a** gần như không bao giờ chạy: bit chỉ được bật sau khi dòng
đã hoàn tất. Giữ nó vì nó rẻ và vì nó là **phòng tuyến thứ hai** cho thứ bất biến kia
hứa - và bất biến nào cũng chỉ đúng tới khi có người sửa code.

⚠ **Hạ bit trước là quyết định có ý thức, không phải tiện tay.**

| | Chết giữa chừng thì | |
|---|---|---|
| Hạ bit **trước**, rồi làm | tin **mất** | ✅ đã chọn: **at-most-once** |
| Làm xong **rồi** mới hạ | khởi động lại **làm lại lần nữa** | at-least-once |

Chọn at-most-once để nhất quán với *"không làm đảm bảo giao tuyệt đối"* (mục 9).
Ứng dụng nào cần chắc thì **tự thêm một hàng đợi động ở phía app**: handler chỉ nhét
vào hàng đợi rồi trả về ngay, phần bền vững là việc của app.

### 4.3. Semaphore là **chuông**, bitmap là **sự thật**

Hai câu hỏi khác nhau, và chỉ một cái được trả lời bằng bộ nhớ:

| Câu | Ai trả lời |
|---|---|
| *"Có tin nào tôi chưa đọc không?"* | **bitmap** |
| *"Làm sao tôi biết mà đi nhìn?"* | **semaphore** |

Semaphore là **bộ đếm, không phải sự thật**, và nó lệch theo cả hai chiều:

- **Lệch thừa (vô hại):** 3 tin đến, release 3 lần, người đọc thức một lần và đọc cả
  3. Còn dư 2 lượt release nên nó thức thêm 2 lần rồi **không thấy gì**. Đây là
  **thức dậy giả**, và nó là chuyện bình thường chứ không phải lỗi.
- **Lệch thiếu (chết người):** nếu ai đó "tối ưu" bằng cách *đã release rồi thì thôi*,
  sẽ có lúc tin đến mà không ai đánh chuông, và người đọc **ngủ quên** với tin còn
  trong bảng.

> **Hai luật, đừng phá:**
> **1. Người gửi LUÔN release, không bao giờ tối ưu bỏ qua.**
> **2. Thức dậy thì QUÉT. Quét không thấy gì thì ngủ tiếp, đó không phải lỗi.**

Luật 1 còn đóng một cửa sổ đua: giữa lúc *"quét thấy trống"* và lúc *"gọi acquire để
ngủ"*, tin có thể đến. Vì đã release nên bộ đếm lên 1, `acquire()` **trả về ngay**
thay vì ngủ.

### 4.4. Đầy thì vòng lại và đè

Không có hạn dùng theo đồng hồ trong dòng. Người ghi đi hết vùng của mình thì vòng
về đầu và **đè lên dòng cũ nhất**, bất kể còn ai chưa đọc.

| | Hạn dùng theo đồng hồ | **Vòng lại thì đè** |
|---|---|---|
| Cần đồng hồ | có | **không** |
| Ai đi dọn | phải có ai đó quét | **không ai** - người ghi tự đè |
| Bộ nhớ | không tự giới hạn | **tự giới hạn bởi kích thước vùng** |

⚠ **Bắt buộc kèm theo:** trước khi đè, người ghi nhìn bitmap xem còn ai chưa đọc rồi
**tăng `missed[]` của những người đó**. Bit bị đè là dấu vết biến mất; không đếm ngay
lúc đó thì tin mất trong im lặng tuyệt đối - đúng thứ vừa đi vá ở F15.

⚠ **Và hạ bit của họ luôn** (bổ sung 2026-08-20 lúc thi công, chủ dự án chốt). Ở ca
thường lệ nó thừa - ngay sau đó người ghi bật lại bit cho mọi người. Nó có giá trị ở
đúng một ca: người ghi **chết sau khi đã mở dòng ra để đè**. Không hạ thì dòng đó
mang cờ chưa-hoàn-tất cộng bit cũ còn nguyên, và bit ấy **không bao giờ hạ được** -
xem [4.1](#41-ghi-không-tranh-chấp-vì-mỗi-người-một-vùng), cùng một bản vá ở đầu kia
của vòng đời một dòng.

⭐ **Hệ quả tốt:** một tiến trình treo **tự chịu hậu quả**, không nghẽn ai. Nếu chọn
*"chờ mọi người đọc xong mới xoá"* thì nó giữ bit mãi và cả nhà tắc.

### 4.5. Timeout nằm ở phía người hỏi, không nằm trong bảng

`ask` có `timeout`, đo bằng đồng hồ của tiến trình hỏi. Hết giờ mà `nguoi_nhan` vẫn
255 thì kết luận `NoOwner`.

### 4.6. Xoá dòng

| Loại | Xoá khi |
|---|---|
| **announce** | **mọi bit đọc về 0** - người đọc cuối cùng tự xoá |
| **request** | có người **ghi `nguoi_nhan`**, hoặc bị đè khi vòng lại |

Không cần tiến trình dọn dẹp riêng. Việc duy nhất cha còn làm: con chết thì
`waitpid` xác nhận, rồi **xoá bit của id đó khỏi mọi dòng đang chờ**.

### 4.7. Handler chạy TUẦN TỰ theo kênh

```text
mỗi KÊNH  = một vòng xử lý riêng, tin trong kênh chạy tuần tự
các kênh  = độc lập, song song với nhau
```

⭐ Đây là lý do tồn tại của cả phần vùng-ghi-riêng. `create_task` cho từng tin là
**vứt bỏ thứ tự vừa xây**: `bật` và `tắt` chạy song song thì trạng thái cuối là *cái
nào thắng cuộc đua*, đúng thứ đã dùng để bác shared subscription của MQTT.

Hai hệ quả phải chấp nhận:

- Một handler chậm **chặn kênh của nó**. Đó là cái giá của thứ tự, và nó đúng: lệnh
  sau không nên chạy trước khi lệnh trước xong.
- Muốn song song thì **tách kênh**, không phải tách task. Kênh là đơn vị thứ tự.

Lợi phụ: không cần trần task, không lặp lại bài toán F15. Số tin chờ đã bị chặn sẵn
bởi kích thước bảng.

---

## 5. API

### 5.1. Ba phép gửi

```python
await link.announce("cauhinh", payload=b"...")                       # kiểu 1
await link.send("fieldbus", key="BT-01", payload=b"stop")            # kiểu 2
res = await link.ask("fieldbus", key="BT-01", payload=b"stop",
                     timeout=2.0)                                     # kiểu 3
```

Phân theo **người gửi cần biết gì**, không phải theo bao nhiêu người nhận.

### 5.2. Bốn kết cục của `ask`

```python
match res:
    case Done(value):    ...   # handler đã nhận và trả lời
    case NoOwner():      ...   # KHÔNG ai nhận -> lỗi CẤU HÌNH, đừng thử lại
    case NoAnswer():     ...   # có đích nhưng quá hạn -> xem tiến trình còn sống không
    case Failed(detail): ...   # có người nhận và người đó HỎNG -> lỗi nghiệp vụ
```

Bốn tình huống khiến người gọi làm **bốn việc khác nhau**, nên phải là bốn giá trị
([luật 03](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md)). Gộp `Failed` vào
`NoAnswer` là nói *"không ai trả lời"* về một ca **đã có người trả lời**.

⚠ **`Done` nghĩa là "handler đã nhận và trả lời", KHÔNG nhất thiết là "việc đã làm
xong".** Handler nhét vào hàng đợi rồi trả `b"da nhan"` thì `Done` mang nghĩa *đã
nhận*. Ngữ nghĩa đó do app định nghĩa; framework không hứa hộ.

### 5.3. Hai decorator

```python
class FieldbusHandler:
    def __init__(self, modbus: ModbusClient, cfg: RuntimeConfig):
        self.modbus = modbus
        self.thiet_bi_cua_toi = cfg.devices_of("bang-tai")   # từ CẤU HÌNH

    @on_request("fieldbus")
    async def dieu_khien(self, key: str, payload: bytes) -> bytes | None:
        if key not in self.thiet_bi_cua_toi:
            return None
        await self.modbus.write(..., device=key)
        return b"ok"

    @on_announce("cauhinh")
    async def cau_hinh_doi(self, key: str, payload: bytes) -> None:
        ...
```

Hai decorator chứ không một, vì hai **hợp đồng** khác nhau: khác ở **kiểu trả về**,
nên viết sai là lỗi kiểu chứ không phải lỗi lúc chạy.

📌 Chủ dự án ghi nhận không thích dạng `@` (đã bỏ `@service`, `@component` từ trước).
Chấp nhận cho 0.8.0 với lý do: **decorator ở đây chỉ ghi vào một registry**, không
phải proxy hay AOP, nên đổi sang cách khác sau này là đổi đúng một chỗ.

### 5.4. Khai ở đâu

```text
app/
├─ config/
│  ├─ __init__.py       gom tất cả, đây là thứ main.py add_config()
│  ├─ dependency.py
│  ├─ web.py
│  ├─ grpc.py
│  ├─ scheduler.py
│  └─ link.py           ← MỚI
└─ link/                ← code handler, KHÔNG phải config
   ├─ fieldbus.py
   └─ cauhinh.py
```

```python
# app/config/link.py
from xime.core.link import ChannelSpec, configure_link

from app.link.cauhinh import CauHinhHandler
from app.link.fieldbus import FieldbusHandler

configure_link(
    channels={
        "fieldbus": ChannelSpec(rows=256, payload_bytes=512),
        "cauhinh":  ChannelSpec(rows=64,  payload_bytes=4096),
    },
    handlers=[FieldbusHandler, CauHinhHandler],
)
```

```python
# app/config/__init__.py
from config.dependency import dependency

from config import grpc, link, scheduler, web  # noqa: F401

__all__ = ["dependency"]
```

Bốn chi tiết cố ý:

1. **`handlers=` nhận CLASS, không nhận instance.** Framework lấy từ DI nên handler
   được inject bình thường. Cùng khuôn `configure_jwt(key_provider=...)` và
   `configure_grpc_tls(provider=...)` của 0.7.2.
2. **Kích thước kênh khai ở file `.py`, không trong `application.yml`.** Đúng luật
   chốt ở F15: chọn số dòng và cỡ payload đòi biết *handler chạy bao lâu, tin của app
   to cỡ nào* - hai thứ người vận hành không biết và không quyết được.
3. **Khai kênh và khai handler tách nhau**: một handler phục vụ nhiều kênh được, và
   một kênh có thể chỉ để **gửi**.
4. **`channels` phải giống nhau ở mọi tiến trình**, vì vùng nhớ là chung. Tự đúng nhờ
   `config/` được import y hệt ở mọi tiến trình.

### 5.5. Bốn phép kiểm lúc khởi động

| Tình huống | Kết cục |
|---|---|
| Decorator khai kênh `"filedbus"` mà `channels` không có | **lỗi.** Chắc chắn gõ sai, và handler đó sẽ im lặng không bao giờ chạy |
| `channels` khai kênh mà không handler nào nghe | **hợp lệ.** Tiến trình chỉ gửi là ca bình thường |
| **Hai handler cùng khai một kênh** | **lỗi** - một kênh một handler |
| App có mở kênh mà cấu hình chỉ khai **một** tiến trình | **cảnh báo rồi chạy tiếp** |

Ca cuối: `M=1` thì `announce`/`send` không có ai nhận và `ask` luôn trả `NoOwner`.
Đây là **quyết định thiết kế của app**, framework không tự chạy bus trong tiến trình
để làm ra vẻ ổn. Nhưng cũng không im lặng - cùng triết lý F6/F7.

### 5.6. Một kênh một handler

Nhiều handler thì phải trả lời *"ai được nhận"*, mà câu đó lại phụ thuộc thứ chỉ biết
lúc chạy - đúng cái vòng vừa thoát ra khi bỏ định tuyến theo tên tiến trình. Muốn
nhiều nhánh thì handler tự phân nhánh.

---

## 6. Vòng đời

### 6.1. Thứ tự khởi động

```text
CHA:  1. sinh mã lần chạy (random)
      2. tạo vùng nhớ chung + semaphore cho từng kênh
      3. sinh con với XIME_PROCESS_ID + XIME_LINK_ID
        │
CON:  1. đọc biến môi trường
      2. ATTACH vùng nhớ                  <- ở đây, CHƯA có DI
      3. import config, dựng DI
      4. lấy handler từ DI, gắn vào vòng xử lý kênh
      5. khởi động adapter
```

⭐ **Bus dựng TRƯỚC DI**, không đi qua `post_construct` nào cả. Nó là hạ tầng của
framework, không phải component của app.

### ⭐ Kênh nội bộ `__xime__` - framework LUÔN tạo, không phụ thuộc app khai gì

Cha dùng chính bus làm **kênh điều khiển**: gửi *"bạn là primary từ giờ"*, nhận
*"tôi đã sẵn sàng"* (tức tín hiệu ready của **F10**). Nó ghi được mà **không cần DI**
- chỉ là ghi bytes vào vùng ghi của nó rồi release semaphore - nên không phá nguyên
tắc *cha không dựng DI*.

Nhờ vậy **ràng buộc (b) của thăng cấp primary hết cần một pipe riêng** (xem mục 2.8
của tài liệu đa tiến trình).

⚠ **Điều kiện bắt buộc:** kênh `__xime__` do **framework tạo**, luôn tồn tại, không
phụ thuộc app có khai kênh nào không. Nếu để nó phụ thuộc app thì chốt chặn thăng cấp
primary phụ thuộc một thành phần **tuỳ chọn** - đúng thứ chủ dự án đã bác khi loại
phương án khoá trong LMDB: *"chắc gì trong mọi trường hợp cái LMDB đã chạy"*.

Hệ quả: cha có một **vùng ghi riêng** trong bảng như mọi tiến trình khác, và nó cũng
đếm vào `max_processes`.

Điều này **gỡ được một phụ thuộc**: câu treo *"`post_construct` ở tiến trình phụ"*
([`10-da-tien-trinh.md`](10-da-tien-trinh.md)
mục 2.9) vẫn còn nguyên cho pool DB, key JWT, job nền - nhưng **bus ra khỏi danh sách
chờ**.

### 6.2. Tên vùng nhớ

```python
ma_lan_chay = secrets.token_hex(8)              # cha sinh, MỘT lần
os.environ["XIME_LINK_ID"] = ma_lan_chay

f"xime-link-{os.getpid()}-{ma_lan_chay}-{ten_kenh}"
```

Con **không tự đoán tên, nó nhận tên** qua biến môi trường.

⚠ Bắt buộc phải duy nhất: máy này có **31 codebase Xime**, chạy cùng lúc lúc phát
triển, và hai app cùng đặt tên kênh `"fieldbus"` sẽ attach vào **đúng một vùng nhớ**,
đọc tin của nhau, hạ bit của nhau. Triệu chứng sẽ là *"thỉnh thoảng nhận được tin
lạ"*.

Không đặt tên theo tên app: hai bản của cùng một app chạy song song lúc dev là chuyện
bình thường.

### 6.3. Dọn rác - ba lớp

> ### ✅ Chủ dự án chốt 2026-08-19: bus **XOÁ** file khi tắt, kho thì **GIỮ**
>
> Nguyên văn: *"bus cho xoá đi. nó **liên lạc giữa các tiến trình thôi**. file cũng
> **random** ai mà biết được"*.
>
> Hai lý do đều đúng và độc lập nhau: bus không chứa dữ liệu ai cần lại sau khi app
> tắt, **và** tên vùng nhớ mang `link_id` ngẫu nhiên của lần chạy nên lần chạy sau
> không có cách nào tìm lại - giữ lại chỉ là rác không ai nhặt được.
>
> ⚠ **Ngược với kho `Store`**, nơi file cố ý sống qua lần restart app để cache còn ấm.
> Hai quyết định ngược nhau, mỗi cái đúng với bản chất của mình - xem
> [tài liệu nhóm 2](13-kho-store-lmdb.md) mục 3.7.

⚠ **Chỉ Linux mới có vấn đề này.** Trên Windows vùng nhớ biến mất khi handle cuối
đóng. Trên Linux nó là file thật trong `/dev/shm/`, mà `/dev/shm` là **RAM**.

**Lớp 1 - `unlink()` trong `finally`.** Che tắt êm, `Ctrl+C`, `SIGTERM`, mọi
exception. Đây là 99% số lần tắt.

```python
finally:
    for shm in cac_vung_nho:
        shm.close()
        shm.unlink()      # CHỈ cha gọi unlink; con chỉ close
```

⚠ Con gọi `unlink` thì các con khác **không attach được nữa**.

**Lớp 2 - dọn lúc khởi động.** Che `kill -9`, mất điện. Pid trong tên cho biết chủ:

```python
for f in os.listdir("/dev/shm"):
    if not f.startswith("xime-link-"):
        continue
    pid = int(f.split("-")[2])
    try:
        os.kill(pid, 0)              # 0 = không gửi gì, chỉ HỎI còn sống không
    except ProcessLookupError:
        os.unlink(f"/dev/shm/{f}")
```

⚠ Pid được hệ điều hành **tái dùng**, nên đôi khi bỏ sót một lần dọn. Hậu quả là một
file rác sống thêm một vòng. Đừng cố giải chính xác, giá không xứng.

**Lớp 3 - `resource_tracker` của Python.** Có sẵn, không phải làm gì. Nó cũng là lý
do bạn thấy `leaked shared_memory objects` khi quên `unlink` - **đừng tắt cảnh báo
đó**, nó đang làm đúng việc.

### 6.4. ⚠ Windows cấp phát THẬT ngay khi tạo

Không thưa như Linux. Tổng RAM mất = tổng mọi kênh, mất ngay lúc khởi động:

```text
4 kênh × 256 dòng × 4 KB   =    4 MB      ổn
4 kênh × 4096 dòng × 64 KB =    1 GB      mất trắng lúc khởi động
```

Cùng cái bẫy đã ghi cho LMDB (mục 2.4 file cache). Khai `rows × payload_bytes` có ý
thức, đừng cho dư cho chắc.

> ⚠ **Bus và `RefData` cố ý KHÔNG có trần tổng** (chủ dự án chốt 2026-08-19 khi phiên
> nêu chuyện ba cơ chế cùng ăn RAM mà không ai cộng): *"2 cái kia không có trần, giữ
> nguyên, không cần làm gì"*. Chỉ `Store` có `total_max`, vì nó là cái **nới động** nên
> cần một chỗ dừng; bus và RefData thì kích thước đứng yên từ lúc khai, người viết
> nhìn thấy con số của mình ngay tại chỗ khai.

### 6.5. Số tiến trình cố định

Bảng cố định lúc tạo, `max_processes` **không phải khai riêng ở đâu cả** - framework
đếm từ khối `processes:` trong `application.yml`. Con chết thì con mới **thay đúng
chỗ cũ**, giữ nguyên id, nên không cần bảng cấp id động.

> ⚠ **Đối chiếu với `parts` của kho, hai quy tắc NGƯỢC NHAU và đều đúng** (ghi cạnh
> nhau 2026-08-19 vì người đọc rời hai tài liệu sẽ tưởng là lệch):
>
> | | Suy từ số tiến trình? | Vì sao |
> |---|---|---|
> | `max_processes` của bus | **Có, và phải** | Bảng **cấp lại mỗi lần khởi động**, không có dữ liệu cũ để lạc chỗ |
> | `parts` của `Store` | ⛔ **Cấm** | Kho **sống qua lần khởi động**, suy là mỗi lần đổi số tiến trình lại mất sạch cache |

⚠ Điều kiện: **`waitpid` xác nhận đã exit hẳn rồi mới cho con mới lên**. Cấp id khi
con cũ chưa chết hẳn thì hai tiến trình cùng nghĩ mình là id 2 và cùng hạ một bit.
Đây đúng ràng buộc (a) của thăng cấp primary - tin kernel, không tin health check.

### 6.6. Tiến trình mới sinh đọc gì

Bitmap **đã là** tiến độ đọc, không cần con trỏ riêng, và nó **sống sót qua việc tiến
trình chết** (nằm trong bộ nhớ chung).

Tiến trình mới lên đọc mọi dòng còn bit của id nó, và đó là hành vi **đúng cho cả hai
loại**:

| Loại dòng còn lại | Đọc lại có đúng không |
|---|---|
| announce (*"khoá JWT vừa xoay"*) | **đúng và cần thiết** - nó phải biết |
| request đã có người nhận | dòng **đã bị xoá**, không còn ở đó |
| request chưa ai nhận | **nên nhận** - đó là công việc chưa ai làm |

---

## 7. Quan sát

### 7.1. API

```python
@dataclass(frozen=True)
class ReaderStats:
    process_id: str        # tên trong cấu hình: "main", "line-2"
    unread: int
    missed: int            # tổng tích luỹ, KHÔNG reset

@dataclass(frozen=True)
class ChannelStats:
    name: str
    rows_total: int
    rows_used: int
    oldest_unread_age_ms: int | None
    readers: tuple[ReaderStats, ...]

@dataclass(frozen=True)
class LinkStats:
    link_id: str
    channels: tuple[ChannelStats, ...]


class ProcessLink:
    def stats(self) -> LinkStats: ...
    def dump(self, channel: str) -> tuple[RawRow, ...]: ...   # CHỈ để gỡ lỗi
```

### 7.2. Bảy quyết định đằng sau

1. ⭐ **`stats()` trả về TOÀN CỤM**, không chỉ tiến trình gọi. Bitmap nằm trong bộ nhớ
   chung nên ai cũng đọc được số của mọi người: một endpoint `/health` ở tiến trình
   web trả lời được tình trạng của cả đàn, kể cả `line-2` không có cổng HTTP nào.
2. **`missed` phải là trường có sẵn** - xem 3.3.
3. **`oldest_unread_age_ms` đòi `ghi_luc` 8 byte mỗi dòng.** Đáng, vì `unread = 47`
   không nói gì nếu không biết nhịp, còn *"47 tin, cũ nhất 8 phút trước"* thì ai cũng
   hiểu là **tắc**. Dùng `monotonic_ns` chứ không phải giờ hệ thống - giờ hệ thống
   nhảy khi đồng bộ NTP và cho ra tuổi âm.
4. ⚠ **`stats()` là ảnh chụp GẦN ĐÚNG**, không giữ khoá. Docstring **phải nói thẳng**,
   nếu không sớm muộn có người viết `if stats.rows_used == 0:` làm chốt chặn logic và
   nó sai đúng một lần trong một nghìn lần.
5. **Counter tích luỹ, không reset.** App muốn biết *"5 phút qua mất bao nhiêu"* thì
   tự lấy hiệu hai lần đọc. Có hàm reset thì hai chỗ cùng gọi ăn mất số của nhau.
6. **`process_id` trả tên, nhưng framework KHÔNG cho biết tên của chính mình.**
   `stats()` không đánh dấu dòng nào là bạn, nên nó dùng để hiển thị chứ không rẽ
   nhánh được. Ai thật sự cần thì đọc biến môi trường, và đó là hành động có ý thức,
   nhìn thấy được khi review.
7. **`dump()` tách riêng và tên nói rõ là công cụ gỡ lỗi.** Trộn với `stats()` thì có
   người gọi nó mỗi 10 giây trong `/health` và chở toàn bộ payload ra ngoài.

```python
@dataclass(frozen=True)
class RawRow:
    row: int
    loai: str                      # "announce" | "request"
    key: str
    nguoi_gui: str
    nguoi_nhan: str | None
    chua_doc_boi: tuple[str, ...]
    payload: bytes                 # THÔ, framework không giải mã được
    age_ms: int
```

### 7.3. Framework tự kêu, không đợi app hỏi

| Sự kiện | Framework làm |
|---|---|
| Đè lên dòng chưa đọc | tăng `missed`, **log WARNING có hãm nhịp** |
| Handler chạy quá `N` giây | log WARNING kèm tên kênh và `key` |
| Bảng đầy tới ngưỡng (vd 80%) | log WARNING một lần khi vượt, một lần khi tụt |

Khuôn hãm nhịp chép thẳng từ `EventBus` (F15): **kêu ở lần đầu, rồi mỗi 1000 lần một
dòng**, và **bộ đếm hãm nhịp phải RIÊNG cho từng loại cảnh báo**. Lý do đã ghi trong
code đó: một dòng log xuất hiện đúng một lần đọc như sự cố lẻ, không như mất mát đang
diễn ra.

---

## 8. Xử lý lỗi

| Ca | Xử lý |
|---|---|
| Handler của **`on_request`** ném lỗi | bắt, ghi dòng trả lời mang cờ lỗi -> người hỏi nhận **`Failed`** |
| Handler của **`on_announce`** ném lỗi | **log rồi đi tiếp.** Không có ai chờ. Bit đã hạ nên tin không quay lại |
| Handler **treo** | **không huỷ**, chỉ log cảnh báo |
| Payload vượt trần | **nổ ngay lúc gửi**, không trả về kết cục |

**`Failed` mang tên class lỗi + `str(exc)`, cắt cứng độ dài (vd 200 byte).** Không
chở traceback: người hỏi ở tiến trình khác **không debug được bằng traceback của tiến
trình kia** - họ không có ngữ cảnh, không có biến. Traceback đầy đủ **log tại tiến
trình bị lỗi**, nơi có đủ mọi thứ.

Payload vượt trần nổ ngay vì đó là **bug của người viết app**, không phải trạng thái
lúc chạy. Trả về một kết cục là mời người ta `except` rồi bỏ qua.

### ⚠ Một hệ quả tinh tế của "handler treo"

Handler treo **sau khi đã hạ bit** nhưng **trước khi ghi `nguoi_nhan`**. Người hỏi hết
giờ, nhìn vào thấy 255, kết luận **`NoOwner`** - tức *"sửa cấu hình, đừng thử lại"*,
trong khi sự thật là *"tiến trình kia đang treo"*.

Không vá bằng cơ chế, mà bằng một luật viết ra:

> **Handler phải nhanh.** Việc lâu thì nhét vào hàng đợi của app rồi trả về ngay.
> Handler không bao giờ chạy lâu thì ca này không tồn tại.

Cộng với log cảnh báo ở 7.3, vì kênh tắc mà im lặng thì người vận hành thấy *"mọi thứ
bình thường, chỉ là không có gì xảy ra"*.

### Treo là CỤC BỘ, không lan

```text
Tiến trình A                        Tiến trình B, C, D
├─ vòng xử lý "fieldbus"  TREO      ├─ vòng xử lý "fieldbus"  chạy
├─ vòng xử lý "cauhinh"   chạy      ├─ vòng xử lý "cauhinh"   chạy
├─ web adapter            chạy      ├─ web adapter            chạy
└─ gRPC adapter           chạy      └─ gRPC adapter           chạy
```

Hậu quả duy nhất: **A mất tin** (bị đè khi vòng lại). B, C, D không sao. Đây là nhờ
quyết định 4.4.

---

## 9. Kiểm thử

⚠ **Test phải spawn tiến trình THẬT.** Bus toàn bộ là chuyện đua: hai tiến trình, hai
lịch, một vùng nhớ. Mock đi thì test xanh mà không chứng minh được gì.

Repo này đã trả giá cho bài học đó: lỗi đua scheduler sống sót qua **1512 test** vì
test chạy trên `AsyncMock`, và với mock thì `create_task` và `start_in_background`
**trông giống hệt nhau**. Luật [`rules/background-tasks.md`](../../rules/background-tasks.md)
mục 4 đã ghi thành văn.

Năm ca bắt buộc chạy bằng tiến trình thật:

```text
1. hai tiến trình gửi và nhận qua lại
2. tiến trình chết giữa chừng, con mới lên, id tái dùng đúng
3. bảng đầy, vòng lại đè, bên bị lỡ ĐẾM ĐÚNG số tin mất
4. handler ném lỗi -> Failed tới được người hỏi
5. không ai nhận    -> NoOwner, KHÔNG phải NoAnswer
```

Ca 3 và 5 phải đi **thành cặp** với ca đối chứng (bị lỡ thì đếm, không lỡ thì không
được đếm nhầm; không ai nhận khác với có người nhận nhưng chậm) - đúng khuôn đã dùng
ở F14, F15, F17.

⚠ Mỗi `spawn` mất ~0,5-1 giây trên Windows. Gom vào một module riêng để không làm
chậm cả bộ test.

---

## 10. Số đo 2026-08-18, đừng đo lại

Đo trên máy này, Windows 11, Python 3.14.7, `spawn` thật.

| Phép đo | Kết quả | Ý nghĩa |
|---|---|---|
| `shared_memory` + `Semaphore` round-trip | **17,4 µs** | cơ chế đã chọn |
| `socketpair` round-trip | **16,8 µs** | ⭐ **gần như BẰNG NHAU** |
| `mp.Lock` acquire+release, không tranh chấp | **0,85 µs** | rẻ hơn tưởng |
| `sleep(0,5 ms)` thực tế | **1,00 ms** | poll có nghỉ chậm hơn semaphore ~60 lần |
| `sleep(1 ms)` thực tế | **1,48 ms** | |
| 4 tiến trình "kiểm tra chỗ trống rồi mới đặt", 2000 slot | **4 slot bị cấp HAI lần** | ⭐ đua có thật, đo được |
| `loop.add_reader` trên `ProactorEventLoop` | **NotImplementedError** | pipe không dùng được với asyncio trên Windows |
| `mp.Connection` có method async | **KHÔNG CÓ** | |
| Truyền socket qua `spawn` trên Windows | **OK** (`DupSocket`) | |

⭐ **Con số quan trọng nhất là hai dòng đầu: bộ nhớ chung KHÔNG nhanh hơn socket ở quy
mô này.** Thời gian bị chi phối bởi **đánh thức tiến trình** (chuyển ngữ cảnh qua
kernel), không phải bởi copy dữ liệu. Nên đừng chọn bộ nhớ chung vì tưởng nó nhanh
hơn - lý do thật nằm ở mục 11.

---

## 11. Đã bác bỏ, kèm lý do (đừng bàn lại)

### Từ bản 2026-06-27

| Đề xuất | Ai bác | Lý do |
|---|---|---|
| **Bus Manager** là thành phần riêng | phiên | Kênh cha-con đã phải có sẵn cho thăng cấp primary. Rồi chính nó cũng bị bỏ, xem dưới |
| **Transport abstraction** (`Redis`/`Tcp`/`UnixSocket`) | phiên | Chủ dự án đã chốt **không chia sẻ bộ nhớ giữa hai máy**, và `ProcessLink` là kênh **trong một máy** theo thiết kế. Giữ một lớp trừu tượng cho một tương lai đã bị loại là chi phí thuần: nó ép mọi API xuống mẫu số chung của các transport không bao giờ tồn tại. ⚠ Lập luận này **không** dựa vào chuyện bỏ Redis - Redis ở lại cho trạng thái liên MÁY (chốt 2026-08-20), nhưng đó là việc của tầng ứng dụng qua `CacheService`, không phải một transport của bus |
| **Broadcast-only** | ca dùng thật | Lệnh điều khiển cần phản hồi và cần phân biệt *"không ai nhận"* với *"đã làm xong"* |
| **DI scope `global`/`worker`**, Worker 0 giữ global singleton | buổi 08-16 | DI nay dựng đủ ở mọi tiến trình, tắt bằng cờ; primary **thăng cấp** được |
| Hình mẫu *"ClassA global gọi ClassB per-worker rồi broadcast"* | hệ quả | Không còn là hình dạng chính |

### Trong buổi 2026-08-18

| Đề xuất | Ai bác | Lý do |
|---|---|---|
| **Định tuyến theo bảng năng lực** (cha tra *"ai giữ BT-01"*) | phiên tự rút | Bắt cha biết thêm một khái niệm trong khi cả kiến trúc đang giữ cha càng ít biết càng tốt. Và bảng đó **chỉ đúng với thứ khai trong cấu hình** - thứ động thì cha mù |
| **`socketpair` làm cơ chế truyền** | **chủ dự án** | Loopback vẫn đi qua TCP stack, chiếm cổng ephemeral, nằm trong tầm firewall và phần mềm bảo mật. ⭐ Đổi lại được một thứ lớn: **cha ra khỏi đường đi**, hết nút cổ chai và hết điểm chết |
| **Con trỏ đọc riêng** thay cho bitmap | phiên tự rút sau khi chủ dự án chỉ ra | Bitmap **đã là** tiến độ đọc, và nó nằm trong bộ nhớ chung nên **sống sót qua việc tiến trình chết**; con trỏ trong RAM riêng thì mất sạch |
| **Cấp phát động nhiều bảng** khi tải cao | phiên, chủ dự án đồng ý hoãn | **Bảng đầy là triệu chứng, không phải nguyên nhân**: bus chở tín hiệu thưa, đầy thì gần như chắc chắn có một tiến trình treo. Thêm bảng chỉ hoãn thời điểm phát hiện. Cộng ba chi phí: con phải attach vùng mới (mà lý do tạo vùng mới là *hết chỗ gửi tin*), Windows cấp phát thật, và trạng thái "vòng về bảng 1 khi chưa trống hết" |
| **Hạn dùng theo đồng hồ trong mỗi dòng** | **chủ dự án** | *"Vòng lại thì đè"* rẻ hơn: không cần đồng hồ, không cần ai đi dọn, và **tự giới hạn bộ nhớ** |
| **Đảm bảo giao tuyệt đối** | phiên | Tin chỉ mất khi tiến trình đích chết, mà nó chết thì cũng đang giữ kết nối Modbus, nên **không đường phần mềm nào dừng được băng tải đó**. Fail-safe nằm ở **watchdog trên PLC**. Đầu tư vào *"bus không bao giờ mất tin"* là mua một bảo đảm mà lớp dưới không có |
| **Poll bằng vòng lặp đọc bit** | số đo | Poll không nghỉ đốt một nhân **mỗi tiến trình**; poll có nghỉ chậm hơn semaphore ~60 lần |
| **`create_task` cho từng tin** | phiên | Vứt bỏ thứ tự vừa xây bằng vùng ghi riêng. Cùng lý do đã dùng để bác shared subscription MQTT |
| **Nhiều handler một kênh** | **chủ dự án** | *"Nhiều lại như cái id tiến trình, mà ban đầu chắc gì đã biết được có bao nhiêu tiến trình chạy đâu"* - câu *"ai được nhận"* lại phụ thuộc thứ chỉ biết lúc chạy |
| **`Channel`** làm tên | phiên | Trùng `XimeGrpcChannel` đã có |
| **`SignalBus`** / **`Mailbox`** | phiên | Còn chữ `bus`, và `signal` đụng `SIGTERM`; `Mailbox` gợi sai chiều (một-tới-một) |
| **Chở traceback trong `Failed`** | phiên | Người hỏi ở tiến trình khác không debug được bằng traceback của tiến trình kia, mà dòng thì có trần cố định |
| **Huỷ handler khi quá giờ** | phiên | Handler đang ghi giữa chừng xuống Modbus, huỷ ngang để lại thiết bị ở trạng thái không ai thiết kế cho |
| **Framework tự chạy bus khi `M=1`** | **chủ dự án** | *"Lập trình viên phải biết trước là có code cho nhiều tiến trình hay không rồi. Nếu cứ bắt gửi thì cũng không ai nhận."* Cho nó "chạy" là làm ra vẻ ổn trong khi không có gì ổn |
| **Framework quản kiểu payload** (sổ đăng ký `kind`) | **chủ dự án** | Để lập trình viên tự pack. Framework chở bytes, không hứa gì về nội dung. ⛔ Và **không dùng `pickle`**: payload đến từ tiến trình khác, `pickle` là thực thi mã tuỳ ý |
| **Framework tự cache lại tin cho chắc** | **chủ dự án** | Đọc là hạ bit ngay. Muốn chắc thì **app tự thêm hàng đợi động** |

---

## 12. Thiết kế này giải luôn được gì ở chỗ khác

Rà một lượt sau khi chốt, 2026-08-18.

### 12.1. Đóng hẳn hai câu của tài liệu kho

| Câu | Đóng bằng |
|---|---|
| **Mục 3 câu 8** - *"mở kho ở đâu"* | **Trước DI, không qua `post_construct`** - cùng lập luận "kho là hạ tầng, không phải component của app". Kèm lợi ích thứ hai: **kho ra khỏi danh sách chờ câu treo `post_construct`** |
| **Mục 4.1** - *"queue chung sẽ thành nút cổ chai nếu ai đó đưa cache lên bus"* | **Tan, không phải được trả lời.** Không còn Bus Manager, không còn queue chung, cha không nằm trên đường đi |

### 12.2. Cho khuôn sẵn cho bốn câu chưa quyết

| Câu | Khuôn |
|---|---|
| ~~Kho mục 3 câu 1 - nhiều kho lấy bằng gì~~ | ⛔ **KHUÔN NÀY BỊ BỎ 2026-08-19.** Kho nhóm 2 chốt **vào DI bằng `dependency.scan(...)`, KHÔNG có `configure_lmdb`** - vì mở một file LMDB **không cần cấp phát chung**, khác hẳn bus và `RefData` (hai cái đó phải cấp vùng nhớ ở cha **trước khi** con dựng DI, nên cha buộc phải biết danh sách trước). ⭐ Khuôn của bus vẫn đúng cho thứ **cần cấp phát trước**; nó chỉ không áp cho kho nhóm 2 |
| ~~Kho mục 3 câu 2 - tách `AtomicStore` hay không~~ | ⚠ **Câu này TAN 2026-08-19**, không phải được trả lời: kho nhóm 2 bỏ hẳn Protocol, dùng **lớp nền cụ thể** `Store` dựng thẳng trên LMDB, nên không còn hai hợp đồng nào để mà tách. Khuôn của bus vẫn đúng, chỉ là không có đối tượng áp |
| ~~Kho mục 3 câu 7 - ba kết cục~~ | ⛔⚠ **CHỐT 2026-08-19 NGƯỢC HẲN dòng này: kho nhóm 2 báo lỗi bằng NGOẠI LỆ.** Lý do: với `incr` / `set_if_absent` thì ngoại lệ là **fail-closed tự nhiên**, còn quên một nhánh của kiểu trả về là **fail-open im lặng** - hãm nhịp hỏng thành *cho qua*. ⭐ Ranh giới đúng: *kết quả bình thường thì kiểu trả về; sự cố hạ tầng thì ngoại lệ*. Bus khác kho ở chỗ `NoOwner`/`NoAnswer` là **kết quả bình thường**, không phải sự cố. **Đừng đọc dòng cũ này như hướng dẫn** |
| Kho mục 7.2 - số hiệu đời kho (fencing token) | ⭐ **`link_id`**. Cha đã phải sinh một mã lần chạy cho tên vùng nhớ; khoá ghi kèm mã đó, đọc thấy khác thì tự bỏ. **Không cần tăng đơn điệu** vì chỉ cần biết *đời đã đổi*. ⚠ Chỉ đúng trong phạm vi một máy |

### 12.3. ⭐ Mở lối cho ba câu đang treo ở tài liệu đa tiến trình

| Câu | Lối ra |
|---|---|
| **`post_construct` ở tiến trình phụ** (2.9) | Rà lại thì **luật 2.7 vốn đã cấm** `post_construct` chạm mạng và `create_task`, nên câu hỏi phải **phát biểu lại** và nó nhỏ hơn nhiều. Đề xuất **ba tầng hook**, dùng đúng lập luận *hai hợp đồng thì hai chỗ khai* |
| **Câu A - scheduler tách đăng ký khỏi chạy** (9.1) | **Cùng hình dạng và cùng lời giải** với câu trên. Hai câu treo, một lời giải |
| **Ràng buộc (b) của thăng cấp primary** (2.8) | **Bus thay pipe cha-con**, và **F10** (tín hiệu ready) đi cùng đường. Điều kiện: kênh nội bộ `__xime__` do framework luôn tạo - xem 6.1 |

### 12.4. Hai chỗ mở rộng luật sẵn có

- **Luật *"không gọi thẳng adapter fieldbus"*** (5.7.3 của tài liệu đa tiến trình) áp
  cho **mọi adapter hạng phân mảnh**, gồm cả **MQTT** sau khi chia theo topic.
- **Nợ luật 03 của `EventBus`** (F15: `publish()` trả `None` cho cả *bị bỏ* lẫn *đã
  xếp lịch*) nay có khuôn bốn kết cục để trả. Kèm: `drain()` lúc tắt máy và *"kênh
  phải xử lý nốt rồi mới đóng"* là **cùng một bài toán tắt êm** - gộp làm một cơ chế.

### 12.5. ⛔ Hai chỗ KHÔNG chuyển được, đừng áp nhầm

| | Vì sao |
|---|---|
| ***"Đầy là triệu chứng, không phải nguyên nhân"*** chỉ đúng cho **bus** | Bus chở tín hiệu **thưa**, đầy thì gần như chắc chắn có tiến trình treo. Kho giữ **trạng thái tăng theo người dùng thật**, đầy là **tải thật**. Câu 5 của kho (*tự nới gấp đôi*) **giữ nguyên** |
| ~~**Chỗ khai kích thước**~~ | ✅ **ĐÃ SOI VÀ CHỐT 2026-08-19**, và nó **tách đôi đúng như dự đoán**: `parts` + `ttl` ở **`.py`** (lập trình viên quyết), `map_size` + `total_max` ở **`application.yml`** (vận hành quyết). Bus khai ở `.py` **cũng đúng** theo cùng phép phân loại - chọn số dòng và cỡ payload đòi biết nhịp tin của app. Xem [tài liệu nhóm 2](13-kho-store-lmdb.md) mục 3.5 |

### 12.6. Không đỡ được gì

DI scope bốn tầng · kết nối DB nhân theo `M × N` · rà soát trạng thái chia sẻ trong
`core/` (bus còn **thêm** một cái vào danh sách đó) · cổng server phụ · tên thống nhất
cho định danh sáu adapter · `@poll` per-instance · supervisor trông tiến trình ngoài.

⚠ **`TrustKeyL2Cache` đã bị gạch khỏi danh sách này 2026-08-19** - không phải vì bus
giải được, mà vì **nó không thuộc nhóm 2**: khoá xác thực Trust **có nguồn bền vững**
(chính Trust), nên nó là ca của `RefData`. Xem mục 7.1 tài liệu cache.

---

## 13. Còn lại

Phần lõi đóng hết. ✅ **Đã code xong 2026-08-20** - phần dưới nay là *"còn lại sau
khi thi công"*, không còn là *"còn lại trước khi thi công"*.

### 13.0. Thi công phát sinh gì (2026-08-20)

| | |
|---|---|
| **Đổi thiết kế: thứ tự ghi** | Xem [4.1](#41-ghi-không-tranh-chấp-vì-mỗi-người-một-vùng). Chủ dự án chốt |
| **Bốn phép kiểm khởi động (5.5)** | ✅ 3/4 đã có: kênh lạ trong decorator → lỗi · kênh không handler → hợp lệ · hai handler một kênh → lỗi. ⬜ **Phép kiểm thứ tư** (*app mở kênh mà cấu hình chỉ khai MỘT tiến trình → cảnh báo*) **phải đợi giai đoạn 3** - nó đọc khối `processes:`, thứ chưa tồn tại |
| **Bộ đếm `so_thu_tu` dùng chung, không khoá** | Hai người ghi đồng thời có thể lấy trùng số, và khi đó thứ tự giữa đúng hai dòng ấy không xác định. Chấp nhận: hai tin **thực sự đồng thời** thì vốn không có thứ tự đúng nào để mà giữ. Trong phạm vi MỘT người ghi thì số luôn tăng, vì nó ghi tuần tự |
| **Ghi `nguoi_nhan` là ngoại lệ DUY NHẤT của luật "vùng ghi riêng"** | Một byte, trên dòng của **người gửi**. Phải nằm đó vì chỉ người gửi đọc nó, và nó là thứ tách `NoOwner` khỏi `NoAnswer`. Đã ghi chú tại chỗ trong code |
| ⚠ **`NoAnswer` hẹp hơn tưởng** | Người nhận chỉ đánh dấu `nguoi_nhan` **sau khi handler trả lời**, nên một handler **còn đang chạy** lúc người hỏi hết giờ cho ra `NoOwner`, không phải `NoAnswer`. Đây đúng là điều mục 8 đã khai (*"handler treo → người hỏi thấy `NoOwner`"*) và đã chọn vá bằng **luật** *"handler phải nhanh"* chứ không bằng cơ chế. Có test khoá hành vi này để người sau không tưởng là bug mới |
| Chi tiết hiện thực khác | Phát sinh lúc code, không phải quyết định thiết kế |
| `post_construct` ở tiến trình phụ | **KHÔNG chặn bus** (bus dựng trước DI, xem 6.1). ⭐ Và rà 2026-08-18 cho thấy **câu đó phải phát biểu lại**, nhỏ hơn mô tả ban đầu nhiều - xem 12.3 |
| Kênh `__xime__` đếm vào `max_processes` | Hệ quả của 6.1: cha có vùng ghi riêng như mọi tiến trình. Nhỏ, nhưng đừng quên khi tính kích thước |

⚠ **Một giới hạn cố ý, không phải nợ:** thiết kế này dành cho `N = 1` luồng mỗi tiến
trình - xem mục 1. `N > 1` không đòi đổi cấu trúc chia sẻ, chỉ thêm một tầng phân
phối bên trong tiến trình.

---

## 14. Liên quan

- [`10-da-tien-trinh.md`](10-da-tien-trinh.md)
  - mô hình chạy, `main.py`, cấu hình, bốn hạng adapter. Mục **5.7.3** là ca dùng gốc
  của bus (fieldbus), mục **5.7.4b** là bản phác đầu tiên mà file này thay thế.
- [`12-kho-refdata.md`](12-kho-refdata.md) - **kho
  nhóm 1 (`RefData`)**, chốt cùng ngày. Dùng chung `link_id`, cách dọn rác, bẫy
  Windows và khuôn `stats()` của bus; và nó **dùng bus** làm kênh báo *"đã sẵn sàng"*.
- [`09-kho-lien-tien-trinh-boi-canh.md`](09-kho-lien-tien-trinh-boi-canh.md) - kho
  liên tiến trình. Mục **2.1** là quyết định tách bus khỏi kho, thứ định hình toàn bộ
  vai của bus.
- [`../da-phu-dinh/ke-hoach-0.8-ban-dau.md`](../da-phu-dinh/ke-hoach-0.8-ban-dau.md) - bản 2026-06-27, **phần Bus đã bị file này
  thay hẳn**. Giữ làm lịch sử.
- [Luật 03](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md) - bốn kết cục của
  `ask`, và `stats()` phải khai là ảnh chụp gần đúng.
- [Luật 01](../../../../.claude/rules/01-song-song-hoa-va-shard.md) - nghĩa 1, và khái
  niệm khoá phân mảnh (ở đây kênh là đơn vị thứ tự).
- [`rules/background-tasks.md`](../../rules/background-tasks.md) - mục 4, lý do test phải
  chạy tiến trình thật.
