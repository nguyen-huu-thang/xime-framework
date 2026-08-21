# Cache liên tiến trình: chốt LMDB, và những gì còn treo

> ## ⚠ 2026-08-19: FILE NÀY NAY LÀ **BỐI CẢNH**, KHÔNG PHẢI THIẾT KẾ HIỆN HÀNH
>
> Phần thiết kế đã tách sang **ba** file riêng, và cả ba đều chốt xong:
>
> | Đọc thay | |
> |---|---|
> | [`12-kho-refdata.md`](12-kho-refdata.md) | Nhóm 1, tên chốt **`RefData`** |
> | [`13-kho-store-lmdb.md`](13-kho-store-lmdb.md) | Nhóm 2, tên chốt **`Store`** trên LMDB |
> | [`11-bus-lien-tien-trinh.md`](11-bus-lien-tien-trinh.md) | Bus, tên chốt **`ProcessLink`** |
>
> ⚠⚠ **Bảng "chưa quyết" ở mục 3 ĐÃ ĐÓNG HẾT** - nhưng ba câu trong đó **tan chứ không
> được trả lời** (câu 2 `AtomicStore` · câu 7 ba kết cục · câu 8 mở kho ở đâu): chúng
> giả định một hình dạng thiết kế mà buổi 08-19 không chọn. Đọc bảng đó như **lịch sử
> lập luận**, đừng đọc như việc còn phải làm.
>
> Thứ file này còn giữ giá trị: **mục 1** (bài toán và chỗ nó bị hiểu thành hai nghĩa) ·
> **mục 2** (ranh giới hai nhóm, vì sao LMDB, ⛔ **mục 2.7 phạm vi một máy**) · **mục 4**
> (những chỗ lật `../da-phu-dinh/ke-hoach-0.8-ban-dau.md`) · **mục 5** (số đo) · **mục 6** (đã loại kèm lý do) ·
> **mục 7** (ràng buộc kỹ thuật của LMDB).

> **Trạng thái lúc viết, 2026-08-16: ĐANG BÀN.** Đây là biên bản một buổi trao đổi thiết
> kế, không phải thiết kế đã chốt.
>
> Ghi lại để **không bị trôi** và để buổi sau bàn tiếp từ đây, không phải bàn lại
> từ đầu.
>
> ✅ **Cập nhật 2026-08-20: CẢ HAI NHÓM ĐÃ CODE.** Nhóm 2 tách sang
> [`13-kho-store-lmdb.md`](13-kho-store-lmdb.md) ->
> `xime/starters/lmdb/`; nhóm 1 sang
> [`12-kho-refdata.md`](12-kho-refdata.md) ->
> `xime/core/refdata/`. Dòng cũ *"chưa có một dòng code nào"* **hết đúng hoàn
> toàn**; đọc file này như **lý do**, hiện trạng thì ở `CHANGELOG.md`.
>
> ⚠ Và một chốt mới làm đổi khung mở đầu của chính file này: **Redis Ở LẠI**
> (2026-08-20) - xem [mục 2.7b](#27b--redis-ở-lại-chủ-dự-án-chốt-2026-08-20).
>
> Liên quan trực tiếp tới [`../da-phu-dinh/ke-hoach-0.8-ban-dau.md`](../da-phu-dinh/ke-hoach-0.8-ban-dau.md) - xem mục 4, có
> mấy chỗ buổi này **lật giả định nền** của bản kế hoạch đó.

---

## 0. Đọc gì trong hai phút

| | |
|---|---|
| **Vì sao có việc này** | Làm được phần lớn thứ Redis đang giữ: cache và trạng thái chung giữa nhiều **tiến trình**. ⚠ **KHÔNG phải bỏ hẳn Redis** - chủ dự án chốt 2026-08-20 rằng nó **ở lại** cho trạng thái nhiều **MÁY** cùng thấy, xem [mục 2.7b](#27b--redis-ở-lại-chủ-dự-án-chốt-2026-08-20) |
| **Chốt lớn nhất** | **Cache chia làm HAI nhóm theo việc dữ liệu có nguồn bền vững hay không**, và mỗi nhóm một cơ chế. Không có một cơ chế nào phục vụ cả hai cho tốt |
| **Nhóm 1** (có nguồn bền vững) | Tự viết trên `multiprocessing.shared_memory`, cơ chế **hai bản đổi con trỏ** |
| **Nhóm 2** (không có nguồn) | **LMDB**, mỗi "bảng" một file riêng |
| **Mô hình chạy** | **Đa tiến trình trước, đa luồng để sau.** Lý do ở mục 2.5, và nó là số đo chứ không phải sở thích |
| ⛔⭐ **Phạm vi** | **MỘT máy, luôn luôn** (chủ dự án chốt 2026-08-19, mục 2.7). Nhiều máy **đã giải bằng chia shard** - đừng bàn phương án nhiều máy nữa |
| **Chưa quyết** | Mục 3. ⚠ **Câu 2 và câu 7 chỉ là gợi ý tạm của phiên 08-16**, không phải khung phải theo - chủ dự án nói rõ 2026-08-19 |

---

## 1. Bài toán, và chỗ nó bị hiểu thành hai nghĩa

Cụm "cache liên tiến trình" đang mang **hai nghĩa khác nhau**, và chúng đòi hai
thứ ngược nhau. Đây là luật 03 ở tầng kiến trúc, và tách được nó ra là phần có
giá trị nhất của buổi này:

| Nghĩa | Ví dụ thật trong nền tảng | Mất thì sao | Cần gì |
|---|---|---|---|
| **(a) Tăng tốc đọc** | khoá ký JWT từ Trust, danh bạ app, cấu hình, theme | **chậm** đi, nạp lại từ nguồn là xong | đọc nhanh, không cần bền vững, không cần nguyên tử |
| **(b) Giữ sự thật chung** | bộ đếm hãm đăng nhập, khoá phân tán cho job nền, thử thách passkey | **SAI, và sai im lặng** | **phép nguyên tử**, một điểm tuần tự hoá duy nhất |

Ranh giới thật **không phải** "đọc nhiều hay ghi nhiều" - đó chỉ là triệu chứng.
Ranh giới là:

> **Dữ liệu này có một nguồn bền vững ở nơi khác không?**

Nhóm (a) đọc nhiều ghi hiếm **vì** nó chỉ là bản sao của một nguồn khác. Nhóm (b)
ghi nhiều **vì** nó là trạng thái đang tích luỹ, và chính vì thế nó không có nơi
nào để đọc lại.

⚠ Nhóm (b) chính là danh sách mà [luật 01](../../../../.claude/rules/01-song-song-hoa-va-shard.md)
mục 6 bắt phải ra khỏi bộ nhớ tiến trình. Nên đây không phải tối ưu, nó là **điều
kiện để bật tiến trình thứ hai** của `identity` và `user`.

---

## 2. Đã chốt

### 2.1. Bus và kho là HAI thứ riêng, không gộp

Chủ dự án chốt. Lý do: chúng ngược nhau ở gần như mọi trục, ép chung một cơ chế
thì hỏng cả hai.

| | Bus | Kho |
|---|---|---|
| Bản chất | dòng **sự kiện** | **trạng thái** |
| Đọc | tiêu thụ một lần, có thứ tự | truy cập ngẫu nhiên, đọc đi đọc lại |
| Tần suất | thấp (config sync, xoay cert) | cao, nằm trên đường nóng |
| Mất một phần | mất tin là mất hẳn | đọc lại là có |

⚠ **Hệ quả cho `../da-phu-dinh/ke-hoach-0.8-ban-dau.md`:** bản kế hoạch đó chọn *một shared queue duy
nhất + mutex ghi*, và nêu lý do là *"traffic inter-worker thực tế rất thấp"*.
Quyết định tách kho ra khỏi bus **giữ nguyên giả định đó**, vì cache không còn đi
qua queue. Nếu sau này ai định đưa cache lên bus thì phải đọc lại mục 4.1.

### 2.2. Nhóm 1: tự viết trên shared memory, hai bản đổi con trỏ

> ## ✅ NHÓM 1 ĐÃ CÓ TÀI LIỆU RIÊNG, THIẾT KẾ CHI TIẾT 2026-08-18
>
> **[`12-kho-refdata.md`](12-kho-refdata.md)** - tên
> chốt là **`RefData[T]`**. Tách ra theo yêu cầu chủ dự án (*"phần không dùng LMDB
> trước đi"*), và hoá ra tách được sạch: **phần lớn 8 câu treo ở mục 3 chỉ thuộc
> nhóm 2**.
>
> Đã chốt ở đó: API subclass kiểu `CrudRepository` · `read()` trả **object** chứ không
> bytes (số đời làm chìa khoá cache L1) · **chỉ primary `publish()`** · `None` = *chưa
> sẵn sàng* và **không cần thêm bit cờ** · chờ qua bus khi chưa sẵn sàng · **chia đoạn
> khi dữ liệu lớn** · thứ tự ghi và thứ tự đọc.
>
> ⭐ Và nó **cắt bớt một mảng của cái vướng ở luật 2.7**: primary gọi Trust rồi
> `publish()`, tiến trình phụ chỉ `read()` nên **không chạm mạng lần nào**.
>
> Phần dưới giữ làm bản tóm tắt cơ chế.

Chốt hướng (chi tiết hiện thực chưa chốt). Hình dạng:

```
[ số đời ] [ con trỏ đang dùng: 0 hay 1 ] [ bản A ] [ bản B ]
```

Người ghi dựng trọn bản mới vào ô **không** được dùng rồi đổi con trỏ. Người đọc
đọc con trỏ, đọc bản đó, đọc lại con trỏ để chắc nó chưa đổi giữa chừng (seqlock).

Ba lý do khiến việc tự viết ở đây **rẻ**, và cần ghi lại kẻo lần sau có người
tưởng phải viết một bảng băm:

1. **Không cần bộ cấp phát bộ nhớ.** Tập dữ liệu được thay **trọn gói** (xoay khoá
   là có tập khoá mới, không phải sửa một khoá trong tập), nên không có cấp phát
   và thu hồi từng entry. Đây là phần đắt nhất và rủi ro nhất của việc tự viết kho,
   và nó không xuất hiện ở đây.
2. **Không có khoá nào cả.** Người đọc không giữ gì, nên người đọc chết không để
   lại hậu quả.
3. **Người ghi chết giữa chừng cũng không sao.** Nó viết vào ô không ai đọc, con
   trỏ chưa đổi nên mọi người vẫn thấy bản cũ nguyên vẹn. **Cái khó nhất của bộ
   nhớ chung (tiến trình chết giữa lúc ghi) ở đây tự biến mất**, không phải do ta
   giải khéo.

⚠ **Một chỗ phải quyết ngay khi code, vì nó im lặng:** lúc worker đọc mà tiến
trình lấy khoá **chưa ghi lần đầu xong** thì vùng nhớ rỗng. Rỗng phải mang nghĩa
*"chưa sẵn sàng"*, **không được lẫn** với *"không có khoá nào"* - nếu lẫn thì lúc
khởi động sẽ có cửa sổ mà request xác thực bị từ chối oan, hoặc tệ hơn là được cho
qua. Giải rẻ: số đời khởi tạo bằng 0, và 0 nghĩa là chưa có gì.

### 2.3. Nhóm 2: LMDB

> ## ✅ NHÓM 2 ĐÃ CÓ TÀI LIỆU RIÊNG, THIẾT KẾ CHI TIẾT 2026-08-19
>
> **[`13-kho-store-lmdb.md`](13-kho-store-lmdb.md)** - tên chốt là
> **`Store`**. Tách ra theo đúng cách đã tách nhóm 1.
>
> Đã chốt ở đó: ba lớp nền (`Store` / `CounterStore` / `Store[T]`) · cấu hình đi bằng
> **tham số class** · vào DI bằng `scan` · **chia file theo `crc32(key) % parts`** ·
> lỗi kho báo bằng **ngoại lệ**.
>
> ⚠ **Câu 2, 7 và 8 ở mục 3 dưới đây đã TAN** - không phải được trả lời. Xem lý do ở
> tài liệu nhóm 2, mục 1.2, 1.3 và 4.
>
> Phần dưới giữ làm bối cảnh vì sao chọn LMDB.

**Chủ dự án chốt 2026-08-16**, sau khi cân nhắc và bác hai phương án khác (xem
mục 6). Nguyên văn lý do: *không tự tin để tự viết, cũng không muốn dùng SQLite.*

⚠ Ghi lại cho trung thực: **khuyến nghị của phiên lúc đó là SQLite**, vì phần
Python phải viết bù cho LMDB rơi đúng vào chỗ LMDB yếu (xem mục 6.3). Chủ dự án
nghe lập luận đó rồi vẫn chọn LMDB. **Đây là quyết định đã cân nhắc, không phải
bỏ sót - đừng mở lại.**

### 2.4. Một "bảng" là một file LMDB riêng, không trộn

Chủ dự án chốt. Đây là lựa chọn tốt hơn vẻ ngoài của nó:

> ### ⭐ BỔ SUNG 2026-08-19 - ba ý, mỗi ý đóng một câu đang treo
>
> Nguyên văn: *"tôi tính mỗi bảng là dùng 1 LMDB, **bảng do lập trình viên khai**. **giống
> mỗi bảng trong sql**, nhưng **linux thì ngay trên ram**. **win thì chỉ là máy dev**."*
>
> | Ý | Đóng câu nào |
> |---|---|
> | **Bảng do lập trình viên khai** | Danh sách bảng là **framework config** (`.py`), không phải `application.yml` - xem [3.1](#31-khuôn-cấu-hình-đề-xuất-chưa-chốt) |
> | **Giống bảng SQL** | Khái niệm để người dùng bám vào đã có sẵn, không phải dạy cái mới. ⚠ Kèm một chỗ **KHÁC** SQL phải nói rõ: **không có giao dịch xuyên bảng** |
> | **Linux ngay trên RAM** | Mặc định trỏ `/dev/shm`, không phải đĩa. **Đây là mặc định, không phải tùy chọn nâng cao** |
> | **Win chỉ là máy dev** | Hạ cấp toàn bộ [7.4](#74-windows-khác-linux-ở-hai-chỗ) từ *"phải giải"* xuống *"ảnh hưởng máy dev"* |
>
> ⚠ Một hệ quả của *"trên RAM"* phải ghi ra vì nó ngược với trực giác về từ "database":
> **kho mất sạch khi máy khởi động lại**. Với cache thì đúng ý; nhưng đừng để ai đặt vào đó
> thứ không được phép mất. Còn `sync: false` thì **hết ý nghĩa** khi đã nằm trên tmpfs - không
> có đĩa nào để đồng bộ xuống.

LMDB khoá ghi **ở mức environment**, tức một người ghi tại một thời điểm cho **cả
kho**. Gộp mọi bảng vào một file thì hãm nhịp, khoá job nền và thử thách passkey
**tranh cùng một khoá ghi**. Tách file thì mỗi bảng một khoá ghi riêng, chúng ghi
song song thật. Đây là cách vá đúng chỗ LMDB yếu nhất.

Hai cái giá, đều chấp nhận được nhưng phải nhớ:

- **Không có giao dịch xuyên bảng.** Không sửa nguyên tử hai bảng cùng lúc được.
  Với cache thì gần như không bao giờ cần.
- **Mỗi kho chiếm trọn trần của nó trong không gian địa chỉ ảo.** Linux 64 bit thì
  vô hại (file thưa). **Windows thì file bị cấp phát THẬT ngay khi tạo**, nên tổng
  đĩa bằng tổng các trần: bốn kho mỗi kho 1 GB là mất 4 GB đĩa máy dev dù chưa ghi
  gì.

### 2.5. Đa tiến trình trước, đa luồng để sau

Chủ dự án hỏi "chọn một trong hai thì cái nào dễ hơn". Trả lời: **đa tiến trình,
và khoảng cách không gần.** Đây là kết luận từ số đo ở mục 5, không phải sở thích:

| | |
|---|---|
| **Lý do quyết định** | `grpcio` **chưa có wheel free-threaded**, và gRPC là xương sống giao tiếp của toàn Xime. Import nó trên bản Python không GIL là **GIL bật lại ngay**, lúc đó N luồng chỉ là N luồng tranh nhau một GIL, tức **chậm hơn một luồng**. Không phải "khó hơn", là "lợi ích âm" |
| Cộng thêm | `lmdb` cũng chưa có wheel free-threaded. Và 31 codebase đang dùng chung **một Python 3.14 bản thường**, muốn thử phải cài `python3.14t` riêng và di cư cả môi trường |
| Bên kia có gì | **Đa tiến trình có bản tối giản dùng được ngay, không cần viết một dòng framework nào**: `uvicorn --workers N` sau một bộ cân bằng tải |
| Và không lãng phí | Ngày free-threading chín, mọi thứ làm cho đường tiến trình **vẫn dùng lại được** (scope, hợp đồng `CacheService`, việc rà trạng thái chia sẻ). Ngược lại làm luồng trước thì ngày cần nhiều tiến trình phải làm lại phần liên tiến trình từ đầu |

> **Đi tiến trình trước là đường một chiều không mất gì; đi luồng trước là đặt cược
> vào lịch phát hành của người khác.**

**Tín hiệu duy nhất đáng theo dõi để xét lại: ngày `grpcio` ra wheel
free-threaded.** Kiểm bằng lệnh ở mục 5, vài tháng một lần.

### 2.6. Mô hình tổng quát là M tiến trình × N luồng, mỗi luồng một event loop

Chủ dự án muốn thiết kế tổng quát, dù *"bình thường không dùng hết đâu"*.

Mô hình này có tiền lệ: **Vert.x và Netty làm đúng vậy** (multi-reactor), nginx thì
là M tiến trình mỗi cái một loop. Ưu điểm của việc khai tổng quát: **ba chế độ trở
thành hai con số**, không phải ba nhánh code.

| Chế độ | Là gì | Backend cache |
|---|---|---|
| `M=1, N=1` | hiện tại | `dict` trong tiến trình |
| `M=n, N=1` | **0.8 như đang thiết kế, và là thứ làm trước** | shared memory (nhóm 1) + LMDB (nhóm 2) |
| `M=1, N=n` | free-threading | `dict` chia sẻ giữa luồng |
| `M=m, N=n` | tổng quát | LMDB giữa tiến trình + `dict` trong tiến trình |

⚠ **`N` không phải "cách tốt hơn để dùng nhiều nhân". Nó là cách duy nhất để vừa
dùng nhiều nhân vừa chia sẻ bộ nhớ.** Không cần chia sẻ bộ nhớ thì `M` làm cùng
việc mà rẻ hơn mọi mặt. Ba câu hỏi để biết cần gì:

1. Một nhân CPU đã hết chưa? Chưa thì dừng, `M=1 N=1`.
2. Các đơn vị song song có cần nhìn cùng một khối dữ liệu trong bộ nhớ không?
   Không thì tăng `M`. Có thì mới tăng `N`.
3. Có trạng thái nào mà lần gọi sau phụ thuộc lần gọi trước không? Có, và `M>1`,
   thì cần kho liên tiến trình.

**Áp vào Xime hôm nay:** 13 app dọc và 5 service ngang gần như chắc chắn ở
`M=1 N=1` vĩnh viễn (mỗi khách là một tiệm vài người, chúng chờ database chứ không
tính toán). `data`, `identity`, `user` sẽ tăng `M` khi cần. **Ứng viên duy nhất
hiện nay có lý do thật cho `N>1` là `user-locator`**, vì nó giữ index tra cứu
trong RAM (`CountingBloomHashmapIndex`) và nhân bản index theo tiến trình là RAM
nhân M lần, trên VPS mà RAM đang là nút thắt. Thư mục `AI/` sau này cũng vậy (model
vài GB không có cửa nhân bản).

---

---

## 2.7. ⛔⭐ PHẠM VI LÀ MỘT MÁY - chủ dự án chốt 2026-08-19, ĐỪNG MỞ LẠI

Nguyên văn: *"tôi dùng cái này cho cache liên tiến trình. **phục vụ request**. **luôn là 1
máy**. đừng bàn nhiều máy nữa. **nhiều máy tôi đã chia shard**."*

| | |
|---|---|
| **Kho này là gì** | Cache liên tiến trình, nằm **trên đường đi của request** |
| **Phạm vi** | **MỘT máy.** Không phải "một máy trước, nhiều máy sau" - là điều kiện thiết kế |
| **Nhiều máy thì sao** | **Đã giải bằng chia shard**, không giải bằng kho chia sẻ |

⭐ **Lý do nó đúng chứ không phải một sự cắt bớt:** shard làm cho *một máy* đủ dùng.
Mọi request của cùng một chủ thể đi về cùng một shard, tức cùng một máy - nên trạng thái mà
các request của chủ thể đó phụ thuộc vào nhau **chỉ cần chia sẻ trong máy ấy**. Dựng thêm một
kho bắc qua nhiều máy là giải lại một bài toán đã giải, bằng cơ chế đắt hơn và có thêm chế
độ hỏng.

⛔ **Hệ quả cho mọi phiên sau: không nêu phương án nhiều máy nữa** - không Redis cluster,
không đồng bộ giữa máy, kể cả dưới dạng *"đường lui"* hay *"ngày mai cần thì"*.

### ⚠⚠ Nhưng câu trên nói về HAI thứ khác nhau - tách ra 2026-08-20

Chủ dự án chỉnh: *"cái phạm vi 1 máy là cho DỰ ÁN CỦA TÔI thôi. Tôi làm framework cho
mọi người dùng thì tôi phải làm nhiều trường hợp hơn... họ có thể nhiều máy, Docker,
k8s các kiểu."*

Đọc lại nguyên văn chốt 08-19 thì thấy nó vốn đã nói vậy: *"nhiều máy **tôi** đã chia
shard"*. Chữ *"tôi"* là **Xime Platform**, không phải framework. Bản ghi ở trên đã
tổng quát hoá nó thành một điều kiện thiết kế của framework, và đó là chỗ sai.

| Câu | Là loại gì | Áp cho ai |
|---|---|---|
| *"`RefData`, `Store`, `ProcessLink` chỉ trong một máy"* | **Sự thật của CƠ CHẾ** - `shared_memory` và một file LMDB tự nó không bắc qua máy | **Mọi người dùng framework** |
| *"chúng tôi không cần kho liên máy vì đã chia shard"* | **Chính sách TRIỂN KHAI của Xime Platform** | **Chỉ Xime** |

⭐ Trộn hai câu đó làm một là đúng khuôn `PEER_APP_ID` đã phải gỡ ở 0.7.1: **framework
mang khái niệm của một người dùng cụ thể vào trong nó**. Nguyên tắc chủ dự án đã ra khi
đó vẫn đứng nguyên - *"framework làm ra để nhiều người khác dùng nữa, nên nó không được
phụ thuộc gì khái niệm ngoài cả"*.

⛔ **Cái vẫn còn hiệu lực nguyên vẹn:** đừng đi làm `RefData`/`Store`/`ProcessLink`
phiên bản nhiều máy. Không phải vì Xime không cần, mà vì **cơ chế của chúng là bộ nhớ
chung và file cục bộ** - bắc qua máy là viết một thứ khác hẳn, và thứ đó đã có tên:
Redis, sau `CacheService`.

✅ **Cái hết hiệu lực:** câu *"framework không phục vụ ca nhiều máy"*. Nó phục vụ -
qua `CacheService`. Xem [mục 2.7b](#27b--redis-ở-lại-chủ-dự-án-chốt-2026-08-20).

✅ **Đóng luôn mục 7.1** (`TrustKeyL2Cache`) - xem ở đó.

⚠ Điều kiện duy nhất đi kèm, ghi ra để không ai quên: lập luận trên đứng khi **định
tuyến theo shard**. Ngày một bộ cân bằng tải chia request của cùng một tổ chức sang hai máy
khác nhau thì kho một máy không còn đủ. Đây là **một dòng điều kiện**, không phải một đề
xuất mở lại.

---

## 2.7b. ⭐ Redis Ở LẠI - chủ dự án chốt 2026-08-20

Nguyên văn: *"tôi vẫn muốn giữ redis cho một số vấn đề. không phải lúc nào cũng dùng
LMDB được."*

⚠⚠ **Đây KHÔNG phải mở lại [mục 2.7](#27--phạm-vi-là-một-máy---chủ-dự-án-chốt-2026-08-19-đừng-mở-lại).**
Hai câu nói về hai thứ khác nhau, và ranh giới là:

> **`RefData` · `Store` · `ProcessLink` là MỘT MÁY vì CƠ CHẾ của chúng là vậy (bộ nhớ
> chung, file cục bộ). `CacheService` là chỗ framework phục vụ ca NHIỀU MÁY.**

⭐⭐ **Và trọng tâm ở đây phải đặt đúng chỗ, chủ dự án chỉnh 2026-08-20:** Redis
**không** phải thứ giữ lại cho một ca hẹp. Nó là **câu trả lời của framework cho cả
một lớp triển khai** - Docker, k8s, N bản sao sau một Service, không có định tuyến
theo shard. Xime Platform tự nó không rơi vào lớp đó vì đã chia shard; **người dùng
framework thì có**, và framework làm cho họ nữa.

Nói cách khác: `Store`/`RefData` là **đường nhanh của một máy**, `CacheService` là
**đường chung của nhiều máy**. Không cái nào là ngoại lệ của cái nào.

### ⭐ Một ca cụ thể, và nó chính là điều kiện mục 2.7 tự viết ra

📌 Ca dưới đây đáng đọc vì nó cho thấy cơ chế, **không** phải vì nó là lý do duy nhất
giữ Redis - lý do chính là lớp triển khai nhiều máy ở trên.

Dòng cuối 2.7: *"lập luận trên đứng khi **định tuyến theo shard**. Ngày một bộ cân bằng
tải chia request của cùng một tổ chức sang hai máy khác nhau thì kho một máy không còn
đủ."*

**Hãm nhịp đăng nhập là đúng ca đó, và nó đã tồn tại rồi** - không phải một tương lai
giả định:

| Hãm nhịp giữ ở đâu | Hạn mức thật bị nhân theo |
|---|---|
| RAM tiến trình | **số tiến trình** |
| `Store` (LMDB) | **số máy** |
| Redis | không nhân |

⭐ `Store` đóng đúng **một tầng** của lỗ hổng, không đóng cả cái lỗ. Và **chia shard
không cứu được tầng còn lại**: shard cắt theo `org_id`, còn hãm nhịp khoá theo **IP hoặc
tên đăng nhập** - hai trục khác nhau, mà người **chưa đăng nhập được thì chưa có
`org_id` nào** để mà định tuyến.

Ba ca nữa `Store` không làm được, ghi ra để khỏi phải dò lại: **khoá phân tán** giữa các
máy · **pub/sub** (LMDB không có gì tương đương) · dữ liệu lớn hơn trần `total_max` của
một máy.

### Hệ quả thi công

| | |
|---|---|
| `starters/cache` + `starters/redis` | **GIỮ.** Chúng là Protocol + backend, đúng khuôn `storage`; xoá một trong hai là lựa chọn tệ nhất |
| ⛔ Chiều ngược lại | Đừng dùng Redis cho thứ `Store` làm được - một vòng mạng cho mỗi lần đọc hãm nhịp là giá thật trả cho thứ nằm sẵn trong RAM cùng máy |
| Bảng chọn ba chiều cho người dùng | `docs/{vn,en}/starters.md`, và docstring của `CacheService` |
| [Mục 7.1](#71--trustkeyl2cache---đã-đóng-2026-08-19-mỗi-máy-một-kho-riêng) | **Không đổi.** Khoá Trust có nguồn bền vững nên `RefData` giải; chuyển sang nó nay là **lựa chọn**, không phải bắt buộc |

📌 Đo 2026-08-20 trước khi quyết: `CacheService` có **đúng một** chỗ dùng thật trong 31
codebase (`TrustKeyL2Cache` của data-service; `lưu trữ/data` là bản mirror của cùng mã).
Con số đó là lý do câu hỏi *"có nên xoá không"* được đặt ra - và nó **không** phải lý do
để xoá, vì thứ quyết định là **việc mà không cái nào khác làm được**, không phải số
người đang dùng hôm nay.

---

## 3. Chưa quyết - phải chốt trước khi viết dòng code đầu tiên

Bảng này là **việc của buổi sau**. Cột khuyến nghị là ý kiến của phiên, chưa ai gật.

> ⚠⚠ **ĐỌC TRƯỚC BẢNG: câu 2 và câu 7 là GỢI Ý TẠM, không phải khung phải theo.**
> Chủ dự án nói rõ 2026-08-19: *"câu 2 và câu 7 chỉ là phiên trước gợi ý tạm"*. Buổi sau
> **bàn lại từ nhu cầu thật**, đừng bắt đầu từ hai lựa chọn đã viết sẵn ở đây.
>
> ⚠ Và cả bảng này viết **trước khi có chốt phạm vi một máy** ([mục 2.7](#27--phạm-vi-là-một-máy---chủ-dự-án-chốt-2026-08-19-đừng-mở-lại)),
> nên mọi chỗ nó cân nhắc chuyện nhiều máy đều **hết hiệu lực**.

| # | Quyết định | Khuyến nghị của phiên |
|---|---|---|
| 1 | **Nhiều kho thì lấy ra bằng gì?** `CacheService` là một Protocol nên không bind được cho N kho cùng lúc | Một `LmdbStores` inject được, `stores.get("rate_limit") -> CacheService`. Kho tên `default` thì bind luôn cho `CacheService`. Cùng khuôn `RedisClientProvider` đang có.<br>✅ **Có tiền lệ từ 2026-08-18**: bus dùng `configure_link(channels={"fieldbus": ChannelSpec(...)})`. Cùng khuôn cho `configure_lmdb(stores={...})` |
| 2 | ⭐ **Mở rộng `CacheService` hay tách `AtomicStore` riêng?** Hợp đồng hiện có đúng 4 method (`get/set/delete/exists`), **không có phép nguyên tử nào**, mà nhóm 2 sống bằng `incr` và `set_if_absent` | **Tách Protocol thứ hai.** Không phá tương thích với ai đang dùng `CacheService`, và nói đúng sự thật rằng không phải kho nào cũng làm được phép nguyên tử.<br>✅ **Cùng lập luận đã dùng ở bus 2026-08-18**: `on_announce` và `on_request` tách làm hai decorator vì **hai hợp đồng khác nhau** (khác kiểu trả về), không gộp rồi bắt người viết tự đoán |
| 3 | **TTL do framework làm hay app làm?** | **Framework**, vì mục tiêu là mọi dự án được hưởng. Khuôn value: 8 byte hạn dùng ở đầu, phần còn lại là payload. ⚠ Cắt bằng `memoryview`, **`value[8:]` là một lần copy toàn bộ** và như thế là vứt đi chính thứ đã trả tiền để có ở LMDB |
| 4 | **Dọn key hết hạn** | Một job nền mỗi kho, chu kỳ khai trong config. Theo luật 01 việc này thuộc hạng *chạy hai lần chỉ THỪA* nên **không cần khoá phân tán** |
| 5 | **Đầy trần thì làm gì** | Tự nới gấp đôi tới một trần cứng khai trong config, log `warning` mỗi lần nới (đó là tín hiệu khai thiếu). Chạm trần cứng thì ném thật + log `critical`.<br>⛔ **ĐỪNG đem lập luận của bus sang đây.** Bus bỏ cấp phát động vì nó chở **tín hiệu thưa**, nên đầy là triệu chứng của một tiến trình treo. Kho thì ngược: nó giữ **trạng thái tăng theo số người dùng thật**, nên đầy là **tải thật**. Hai bản chất khác nhau, hai lời giải khác nhau |
| 6 | **Đuổi bộ nhớ** | **Không làm LRU thật.** Nó đòi ghi trên đường đọc, mà LMDB một-người-ghi thì làm vậy là phá sập mô hình: các lượt đọc vốn không chặn nhau bỗng xếp hàng qua khoá ghi. Chỉ đuổi theo hạn dùng, cộng dọn theo thời điểm **ghi** khi đầy. **Ghi rõ giới hạn này trong tài liệu** để không ai tưởng nó là Redis |
| 7 | ⭐ **Ba kết cục thay vì hai** (luật 03) | `có giá trị` / `không có key` / `không hỏi được kho`. ⚠ Gộp lỗi kho vào `None` thì **hãm nhịp gặp lỗi kho sẽ CHO QUA**, và `set_if_absent` không biết mình đã chiếm được khoá hay chưa nên **hai worker cùng chạy một job**. Cả hai đều im lặng.<br>✅ **Hình dạng đã chốt ở bus 2026-08-18: KIỂU TRẢ VỀ, không phải ngoại lệ.** Lý do dùng nguyên được: ngoại lệ dễ bị `except Exception` nuốt chung với lỗi mạng, mà *"không hỏi được kho"* là **lỗi hạ tầng** người vận hành phải thấy |
| ~~8~~ | ~~**Mở kho ở đâu**~~ | ✅ **ĐÓNG 2026-08-18: mở TRƯỚC khi dựng DI, KHÔNG qua `post_construct`.** Kho là **hạ tầng của framework**, không phải component của app - cùng lập luận đã dùng cho bus, xem [`11-bus-lien-tien-trinh.md`](11-bus-lien-tien-trinh.md) mục 6.1. Được hai thứ: câu này có đáp án, **và kho ra khỏi danh sách chờ câu treo `post_construct`**.<br>⚠ Cảnh báo cũ vẫn đúng và **tự thoả**: bước đó nằm **sau** khi tách tiến trình, và đã chốt dùng `spawn` chứ không `fork`, nên master không mở kho |
| 9 | **Async** | Đọc gọi thẳng trong event loop (vài micro giây, đẩy sang thread còn đắt hơn). **Ghi phải qua executor**, vì lệnh ghi có thể chờ khoá ghi toàn kho trong thời gian không xác định, và chờ đó chặn cả event loop |

⭐ **Mục 2 và mục 7 là thêm API công khai vào gói MIT đã có trên PyPI** (11 bản,
`0.1.0` -> `0.7.0`), nên chúng thuộc loại **phải chủ dự án gật**, không phải chi
tiết hiện thực.

### 3.1. Khuôn cấu hình đề xuất (chưa chốt)

> ⚠⚠ **PHẢI SOI MỘT LẦN CÓ CHỦ Ý: hai tài liệu đang chỉ hai chỗ khác nhau cho cùng
> loại tham số.**
>
> | | Kích thước khai ở đâu |
> |---|---|
> | **Bus** (chốt 2026-08-18) | **`config/link.py`**, file `.py`, theo luật đã chốt ở F15 |
> | **Kho** (khuôn dưới đây) | **`application.yml`**, khối `lmdb:` |
>
> Chưa chắc cái nào sai. Phép phân loại đã chốt ở F15 và ghi trong
> [`rules/config-discovery.md`](../../rules/config-discovery.md) là: ***người vận hành có
> ĐỦ THÔNG TIN để chọn giá trị này không?*** Áp vào từng khoá thì **câu trả lời khác
> nhau**:
>
> | Khoá | Ai đủ thông tin |
> |---|---|
> | `map_size`, `map_size_max` | **vận hành** - đây là dung lượng đĩa/RAM còn lại |
> | `max_readers` | **vận hành** - phụ thuộc số tiến trình nhân số luồng |
> | `ttl_sweep_seconds` | **lập trình viên** - phụ thuộc nhịp dữ liệu của app |
>
> ✅ **MỘT NỬA CÂU NÀY ĐÃ ĐÓNG 2026-08-19:** chủ dự án chốt *"bảng do **lập trình viên**
> khai"*, nên **danh sách bảng nằm ở `.py`**, không phải `application.yml`. Đúng phép phân
> loại đã chốt ở F15: người vận hành **không biết** app cần những bảng nào, và thêm/bớt một
> bảng là **đổi code**, không phải đổi cấu hình.
>
> Còn lại đúng phần **kích thước**: nên nhiều khả năng nó **tách đôi**, và đó là kết luận hợp lý. Nhưng phải quyết một
> lần có chủ ý, chứ không để hai file chốt hai kiểu rồi sáu tháng sau không ai biết
> bản nào đúng - đúng khuôn hỏng đã gặp ngày 2026-07-31 khi hai bộ test canh khoá hai
> luật khác nhau mà không ai thấy.

```yaml
lmdb:
  # Thư mục gốc chứa các kho. Mỗi kho một thư mục con.
  # Linux muốn thuần RAM thì trỏ vào /dev/shm.
  path: "./runtime/cache"

  defaults:
    map_size: "256MB"        # trần khởi điểm
    map_size_max: "2GB"      # trần cứng, không bao giờ vượt
    grow_at_percent: 75      # vượt ngưỡng thì tự nới
    max_readers: 256
    sync: false              # cache: không chờ đĩa xác nhận
    ttl_sweep_seconds: 60

  stores:
    rate_limit:        { map_size: "64MB" }
    dist_lock:         { map_size: "16MB" }
    passkey_challenge: { map_size: "32MB", ttl_sweep_seconds: 15 }
```

Bốn chi tiết cố ý:

1. **`map_size` viết dạng chuỗi có đơn vị** (`"256MB"`), không phải số byte trần.
   Người vận hành đọc `268435456` không biết là bao nhiêu, và gõ thiếu một số 0 thì
   không ai thấy.
2. `defaults` cộng khai riêng từng kho, app chỉ khai kho nào lệch chuẩn.
3. ⚠ **`max_readers` phải có mặt.** LMDB mặc định **126** người đọc đồng thời, đếm
   theo **cặp (tiến trình, luồng)**. Nhiều worker cộng thread pool là chạm trần
   thật, và lỗi `MDB_READERS_FULL` rất khó lần ra nguyên nhân.
4. `sync: false` là mặc định đúng cho cache, nhưng phải khai được, vì ngày ai đó
   dùng kho này cho thứ không mất được thì họ cần bật lên.

---

## 4. Phải thiết kế thêm (ngoài phạm vi kho)

### 4.1. ~~⚠ `../da-phu-dinh/ke-hoach-0.8-ban-dau.md` chọn kiểu queue theo một giả định mà cache sẽ lật~~

> ## ✅ MỤC NÀY TAN 2026-08-18, không phải được trả lời
>
> Bus thiết kế lại ([`11-bus-lien-tien-trinh.md`](11-bus-lien-tien-trinh.md))
> **không còn Bus Manager, không còn queue chung, và cha không nằm trên đường đi** -
> mọi tiến trình đọc thẳng cùng một vùng nhớ. Nút cổ chai mà mục này cảnh báo
> **không tồn tại nữa**.
>
> Đoạn cuối (*"cần hỏi đáp thì tách làm hai đường, đừng ép chung một queue"*) cũng
> thành thừa: hỏi đáp đã có sẵn qua `correlation_id` trên cùng cấu trúc, không phải
> một đường riêng.
>
> Giữ nguyên phần dưới làm lịch sử - nó cho biết vì sao bản 06-27 chọn queue chung.


Bản kế hoạch chọn **một shared queue duy nhất + mutex ghi**, lý do ghi rõ:
*"traffic inter-worker thực tế rất thấp (config sync, cert rotation, cache
invalidation)"*.

Quyết định 2.1 (tách kho khỏi bus) **giữ được giả định đó**. Nhưng nếu sau này có
ai định đưa lời gọi cache lên bus thì phải biết: cache là đường nóng (một request
HTTP có thể gọi `get()` vài lần, nhân với N worker), và lúc đó Bus Manager thành
**nút cổ chai tuần tự hoá của cả ứng dụng**, tức multi-process mất hết ý nghĩa vì
mục đích ban đầu là thoát GIL.

Nếu có ngày cần hỏi/đáp trên bus thì **tách làm hai đường, đừng ép chung một
queue**: quảng bá giữ queue chung + Bus Manager; hỏi/đáp thì mỗi worker một cặp
hộp thư riêng, không qua Bus Manager.

### 4.2. DI scope: 0.8 thiết kế hai tầng, mô hình M×N cần bốn

`../da-phu-dinh/ke-hoach-0.8-ban-dau.md` có `global` và `worker`. Với M×N thì `worker` mang hai nghĩa và
phải tách:

| Scope | Bao nhiêu instance | Ai dùng chung |
|---|---|---|
| `global` | 1 toàn hệ thống | mọi tiến trình, mọi loop |
| `process` | M | các loop trong cùng tiến trình |
| `loop` | M × N | riêng một loop |
| `request` | theo request | **đã có sẵn** qua `ContextVar` |

⚠ Kèm một luật mà mô hình đa tiến trình không cần: **mọi singleton ở scope
`process` phải an toàn khi nhiều luồng gọi cùng lúc**. Ở mô hình cũ mỗi worker một
bản nên không ai phải nghĩ tới. Đây là thay đổi lớn nhất **với người viết ứng
dụng**, không chỉ với framework.

**Cách trả thuế ít nhất (đề xuất):** **tổng quát ở hợp đồng, hoãn ở hiện thực.**
Định nghĩa đủ bốn scope **ngay từ đầu** vì scope là hợp đồng và đổi sau thì mọi app
phải sửa; nhưng chỉ **hiện thực** `loop` khi có ca dùng thật. Mặc định là chế độ
đơn giản nhất, và ở đó người viết app không cần biết `M` với `N` tồn tại.

### 4.3. Primitive của asyncio không đi qua được ranh giới loop

Cái bẫy lớn nhất của chế độ `N>1`, và nó im lặng:

`asyncio.Lock`, `Event`, `Queue`, `Future` **gắn chặt vào một event loop cụ thể**.
Dùng từ loop khác thì hoặc treo, hoặc lỗi khó hiểu, và không có gì cảnh báo lúc
viết. Mọi chỗ chia sẻ giữa các loop phải là `threading.Lock` cộng
`loop.call_soon_threadsafe`.

Ba chỗ trong framework dính ngay khi bật `N>1`:

- **`EventBus`** hiện `create_task` trong loop của người publish. Nhiều loop thì
  handler đăng ký ở loop khác **không bao giờ chạy**. Sẽ thành **ba tầng**: trong
  loop, giữa loop, giữa tiến trình.
- **Xoay cert và job nền** phải chạy đúng một chỗ, không phải mỗi loop một bản.
- **`threading.Lock` giữ lâu thì chặn cả loop** vì nó không awaitable. Luật phải
  là: khoá dùng chung giữa các loop chỉ giữ trong vài chục micro giây, **không bao
  giờ bọc quanh IO**.

### 4.4. Con số dễ nổ nhất: kết nối database nhân theo M × N

`asyncpg` gắn kết nối với **một event loop cụ thể**, SQLAlchemy async engine cũng
vậy. Pool **không chia sẻ được giữa các loop**, mỗi loop một pool.

```
2 VPS × 8 luồng × pool 5 = 80 kết nối cho MỘT service
```

Postgres mặc định `max_connections = 100`, mà có 9 service Base cộng mười mấy app.
**Đây là thứ sẽ nổ trước CPU.** Giải bằng pool nhỏ, pgbouncer, hoặc `N` nhỏ. Ràng
buộc này kéo `N` thực tế xuống thấp hơn số nhân CPU khá nhiều.

### 4.5. Ai nhận kết nối và chia cho ai

**Giữa tiến trình:** `SO_REUSEPORT` là cách sạch, kernel tự chia. ⚠ **Windows không
có cái tương đương** - `SO_REUSEADDR` bên đó cho tiến trình sau **cướp** cổng chứ
không chia tải. Chuyển file descriptor thì Linux có `SCM_RIGHTS`, Windows phải
`WSADuplicateSocket`. Hai đường hoàn toàn khác nhau.

> **Đề xuất cắt phạm vi:** chế độ đa tiến trình **chỉ hỗ trợ Linux**, Windows chỉ
> chạy `M=1`. Máy dev là Windows nhưng prod là VPS Linux, nên giá thật khá nhỏ và
> nó cắt đi một nửa độ phức tạp.

**Giữa các luồng trong một tiến trình:** dễ hơn nhiều, cùng không gian bộ nhớ, một
luồng accept rồi đưa socket cho loop khác bằng `call_soon_threadsafe`.

### 4.6. Framework nên tự hỏi runtime rồi nói ra

```
Cấu hình: processes=2, threads_per_process=8
Runtime : Python 3.14 (GIL đang BẬT)
-> 8 luồng sẽ không chạy song song. Hoặc cài bản free-threaded, hoặc đặt threads=1.
```

`sys._is_gil_enabled()` trả lời được. Không có dòng này thì người ta cấu hình 8
luồng, thấy hiệu năng y hệt, rồi kết luận sai về nguyên nhân. Và vì **bất kỳ thư
viện C nào chưa khai hỗ trợ cũng âm thầm bật lại GIL**, đây là thứ sẽ xảy ra thật.

### 4.7. Món nợ ẩn: framework đang giả định chỉ có một luồng

Những chỗ hôm nay an toàn **nhờ GIL** sẽ không còn an toàn khi bật free-threading:
registry của DI, tập task đang chờ của event bus, các cache L1 trong tiến trình, bộ
đệm kênh gRPC.

Thao tác đơn lẻ trên `dict` và `set` của CPython vẫn nguyên tử ở bản free-threaded,
nhưng **một chuỗi đọc rồi ghi thì không** - và đó là hình dạng phổ biến nhất trong
code khởi tạo lười.

> **Việc đáng làm sớm KHÔNG phải bật free-threading, mà là rà soát và đánh dấu mọi
> trạng thái chia sẻ trong `core/`.** Việc đó có ích ngay cả khi không bao giờ bật,
> vì nó làm rõ chỗ nào là trạng thái dùng chung. **Chưa làm.**

---

## 5. Số đo 2026-08-16, để khỏi đo lại

### 5.1. Wheel free-threaded trên PyPI

| Thư viện | `cp313t`/`cp314t` | Ghi chú |
|---|---|---|
| pydantic-core, pyyaml, uvloop, httptools, websockets, msgpack, sqlalchemy, asyncpg, cryptography, hiredis | **có `cp314t`** | Toàn bộ lõi web và DB đã sẵn sàng |
| **grpcio** | **KHÔNG**, và không có bản thuần Python | ⛔ **chặn nặng nhất**, xem 2.5 |
| **protobuf** | không có `cp314t`, nhưng **có bản thuần Python** | Chạy được, chậm hơn nhiều khi serialize |
| **lmdb** | **KHÔNG**, không có bản thuần Python | py-lmdb ít được cập nhật |

Lệnh đo lại (chạy từ repo này):

```bash
python -c "
import urllib.request, json
pkgs = ['pydantic-core','pyyaml','uvloop','httptools','websockets','grpcio','protobuf','msgpack','sqlalchemy','asyncpg','cryptography','lmdb','hiredis']
for p in pkgs:
    d = json.load(urllib.request.urlopen(f'https://pypi.org/pypi/{p}/json', timeout=20))
    files = [f['filename'] for f in d['urls']]
    ft = sorted({t for f in files for t in ('cp313t','cp314t') if t in f})
    print('%-14s %-10s %s' % (p, d['info']['version'], ','.join(ft) or 'KHONG'))
"
```

⚠ **"Không có wheel" khác "không hỗ trợ"** - về lý thuyết build from source được.
Nhưng với `grpcio` (C++ lớn) thì đó không phải đường đi thực tế, và dù build được
cũng chưa chắc khai `Py_mod_gil`.

### 5.2. Cơ chế GIL tự bật lại

Extension C phải khai `Py_mod_gil = Py_MOD_GIL_NOT_USED`. **Chưa khai thì CPython
tự bật lại GIL cho cả tiến trình**, in một `RuntimeWarning`, rồi chạy tiếp bình
thường.

> Ứng dụng vẫn chạy, mọi test vẫn xanh, chỉ có **toàn bộ lợi ích đa luồng biến
> mất** và không có gì hỏng để ai nhận ra. Ép tắt được bằng `PYTHONGIL=0` nhưng đó
> là nói với runtime *"tôi biết thư viện này chưa an toàn, cứ chạy đi"*, và giá là
> hỏng dữ liệu hoặc sập ngẫu nhiên. **Không nên.**

### 5.3. Trạng thái free-threading của chính Python

| | |
|---|---|
| 3.13 | thử nghiệm |
| **3.14** | **chính thức được hỗ trợ** (PEP 779), nhưng **vẫn là bản dựng riêng** `python3.14t`, không phải mặc định |
| Chi phí khi chạy một luồng | 3.13 chậm hơn ~40%, 3.14 rút còn ~5-10% |
| Mô hình bộ nhớ | Java có JMM từ lâu; Python **chưa có** bản đặc tả tương đương |

### 5.4. Bậc độ lớn một lần đọc, gọi từ Python

Ước lượng để so tương quan, **không phải số đo trên máy này**:

| | Một lần `get` |
|---|---|
| Redis qua TCP loopback | 30 - 60 µs |
| Redis qua unix socket | 25 - 40 µs |
| SQLite trong RAM, prepared | 5 - 15 µs |
| LMDB trong RAM | 2 - 4 µs |

⚠ Redis xử lý một lệnh `GET` chỉ tốn **cỡ một micro giây**; toàn bộ phần còn lại là
giá của việc **đi qua ranh giới tiến trình**. Đó là lý do một thư viện nhúng
"chậm" vẫn thắng một server "nhanh" khi đo một thao tác.

**Chưa ai đo thật trên máy này.** Nếu cần con số thật thì viết một script đặt hai
bên cạnh nhau, ước nửa giờ.

### 5.5. Redis đang được dùng ở đâu trong nền tảng (quét 2026-08-16)

Mỏng hơn nhiều so với cảm giác. Ca dùng thật đáng kể **duy nhất**:
`Base Platform/data/app/integration/trust/key/TrustKeyL2Cache.py` - L2 chia sẻ khoá
xác thực Trust giữa **nhiều instance data-service**, fail-soft tuyệt đối. Ngoài ra
`application-service` (Java) có khai `spring.data.redis` trong `application.yml`.

⚠ **Ca này nằm NGOÀI phạm vi mọi thứ chốt hôm nay** - xem mục 7.1.

---

## 6. Đã cân nhắc và LOẠI, kèm lý do

Ghi để không ai bàn lại từ đầu.

### 6.1. Hướng "một worker giữ kho, các worker khác hỏi qua bus"

Từng được chọn giữa buổi rồi bị chính chủ dự án thay bằng hướng truy cập trực
tiếp. Lý do loại: cần thêm point-to-point + ghép cặp hỏi/đáp vào 0.8 (bản kế hoạch
ghi rõ là *để bản sau*), Worker 0 chết là **mất sạch kho**, và mọi lời gọi cache
phải qua một tiến trình nên nó thành nút cổ chai.

Lợi thế nó có mà các hướng khác không có, ghi lại phòng khi cần: **kho nằm trong
một event loop đơn luồng nên mọi phép nguyên tử là miễn phí**, không cần lock,
không cần script Lua.

### 6.2. Postgres làm nơi giữ sự thật

Khuyến nghị ban đầu của phiên. Ưu: không thêm thành phần vận hành, **qua được nhiều
máy**, `advisory lock` đã được luật 01 công nhận sẵn. Nhược: mili giây thay vì micro
giây, thêm WAL.

**Chủ dự án chọn phạm vi một máy** nên lợi thế lớn nhất của nó (nhiều máy) không
dùng tới.

### 6.3. SQLite

Khuyến nghị **thứ hai và mạnh hơn** của phiên, sau khi phân tích phần Python phải
viết bù cho LMDB. Chủ dự án bác thẳng: *"cũng không muốn dùng sqlite"*.

Lập luận đã đưa ra, giữ lại vì nó vẫn đúng và có thể cần khi đo thật:

> Lợi thế của LMDB **chỉ còn nguyên vẹn ở thao tác `get` đơn thuần**, tức nghĩa (a)
> - mà nghĩa (a) đã được giải bằng shared memory tự viết ở nhóm 1. Phần giao cho
> LMDB (nhóm 2) lại đúng phần nó yếu nhất khi gọi từ Python:

| Thao tác | LMDB + Python | SQLite |
|---|---|---|
| `get` có kiểm TTL | 2-4 µs | 5-15 µs |
| `set` có TTL | 10-30 µs | 10-30 µs |
| **`incr` nguyên tử** | 20-40 µs, **giữ khoá ghi toàn kho suốt vòng đọc-sửa-ghi bằng Python** | 10-20 µs, **một câu chạy trọn trong C** |
| **Dọn 10 nghìn key hết hạn** | vài chục ms, duyệt cursor bằng Python | vài ms, một câu có chỉ mục |

Cộng thêm: SQLite **không thêm phụ thuộc** (có sẵn stdlib), **có sẵn TTL và nguyên
tử** ở dạng đã biết viết, còn LMDB thì TTL, dọn dẹp và đuổi bộ nhớ đều phải tự làm.

⚠ **Đây là quyết định đã cân nhắc của chủ dự án, không phải bỏ sót. Đừng mở lại**
trừ khi có số đo thật cho thấy phần Python viết bù ăn hết lợi thế.

### 6.4. Tự viết kho cho cả nhóm 2

Loại vì lý do chủ dự án nêu: *không tự tin để tự viết*. Đó là đánh giá đúng - phần
đắt nhất là **bộ cấp phát bộ nhớ đa tiến trình chịu lỗi bằng Python**, cộng chuyện
**một worker bị kill giữa lúc ghi để lại kho hỏng và khoá không nhả** (POSIX có
robust mutex nhưng **Python không phơi ra**).

> **Khác biệt bản chất giữa hai mô hình, đáng nhớ: hỏi/đáp cô lập lỗi, truy cập
> trực tiếp thì không.** Ở mô hình hỏi/đáp, client chết chỉ đứt một kết nối. Ở mô
> hình truy cập trực tiếp, một worker chết giữa lúc ghi có thể phá kho của tất cả.

### 6.5. Giữ Redis

Không loại hẳn - xem 7.1. Nhưng cho phạm vi một máy thì Redis mất gần hết lợi thế
(thứ nó giỏi nhất là **nối nhiều máy nhiều service**), trong khi vẫn ăn RAM riêng
trên VPS mà RAM đang là nút thắt, cộng một round trip mỗi lần đọc.

---

## 7. Ràng buộc còn nguyên, đừng tưởng đã xong

### 7.1. ✅ `TrustKeyL2Cache` - ĐÃ ĐÓNG 2026-08-19: **mỗi máy một kho riêng**

Nó chia sẻ giữa **các instance data-service, có thể khác máy, và sống qua restart**.
LMDB một máy không làm được. Hai lối:

- giữ Redis riêng cho nó, hoặc
- chấp nhận **mỗi máy một kho riêng**, mỗi máy tự gọi Trust một lần.

> ### ⭐ VÀ NÓ KHÔNG THUỘC NHÓM 2 - chỉnh 2026-08-19
>
> Mục này nằm ở tài liệu LMDB nên dễ bị đọc thành *"khách hàng của nhóm 2"*. Không phải:
> khóa xác thực Trust **có nguồn bền vững** (chính Trust), mất thì gọi lại được - tức đúng
> định nghĩa **nhóm 1** ở [mục 1](#1-bài-toán-và-chỗ-nó-bị-hiểu-thành-hai-nghĩa).
>
> Nên lời giải của nó là **`RefData`** ([`12-kho-refdata.md`](12-kho-refdata.md)),
> không phải LMDB. Và nó khớp tới từng chi tiết: tập khóa **thay trọn gói**, **một** tiến
> trình (primary) gọi Trust rồi `publish()`, các tiến trình khác chỉ `read()` nên **không
> chạm mạng lần nào** - đúng câu đã ghi ở mục 5.4 của tài liệu snapshot.
>
> ⚠ Hệ quả cho bảng “khách hàng của nhóm 2”: **trừ ca này ra**. Nhóm 2 chỉ phục vụ thứ
> **không có nguồn bền vững** - hãm nhịp, thử thách passkey, chống lặp (idempotency key).

✅ **Chủ dự án chốt 2026-08-19: lối thứ hai.** Đây không phải một quyết định riêng cho
mục này mà là **hệ quả trực tiếp của [mục 2.7](#27--phạm-vi-là-một-máy---chủ-dự-án-chốt-2026-08-19-đừng-mở-lại)**:
phạm vi luôn là một máy, nhiều máy đã giải bằng chia shard.

Mỗi máy một kho riêng, mỗi máy tự gọi Trust một lần. Chấp nhận được vì tầng đó **vốn
fail-soft tuyệt đối** (đọc code: `TrustKeyL2Cache` bọc `except Exception` quanh mọi lời gọi,
hỏng thì rơi về L1 + Trust), nên cái giá thật chỉ là **mỗi máy một vòng gọi Trust thêm**,
không phải một chế độ hỏng mới.

⚠ Việc còn lại là **thi công**: `data-service` đang bind `CacheService: RedisCacheService`.
Đổi sang backend một máy là một dòng `bind`, không sửa `TrustKeyL2Cache`.

📌 Ghi chú 2026-08-18: **bus KHÔNG giải mục này** (nó cũng chỉ một máy). Nó chỉ giúp
một chút nếu chọn lối thứ hai: khi một tiến trình lấy khoá mới về, nó `announce` cho
các tiến trình **cùng máy**, nên chúng không phải poll số đời của vùng nhớ nhóm 1.
Tiện lợi, không phải lời giải.

### 7.2. Số hiệu đời kho (fencing token)

Kho trên tmpfs mất sạch khi máy khởi động lại. Với cache thì đúng ý. **Với khoá
phân tán thì không**: sau reboot mọi khoá biến mất, hai job có thể cùng tin mình
giữ khoá - đúng thứ luật 01 bắt phải chặn, và nó xảy ra đúng lúc không ai để ý.

Cần một số hiệu tăng dần qua mỗi lần kho khởi động lại, để job cầm khoá đời cũ biết
mình đã mất khoá.

> ### ⭐ Có lời giải gần như miễn phí từ 2026-08-18: dùng **`link_id`**
>
> Bus đã bắt **cha sinh một mã lần chạy ngẫu nhiên** rồi truyền cho con qua biến môi
> trường (`XIME_LINK_ID`), vì tên vùng nhớ chung phải duy nhất giữa 31 app trên cùng
> một máy. Mã đó **chính là số hiệu đời** mà mục này cần:
>
> - Job cầm khoá ghi kèm `link_id` của lần chạy đã cấp khoá.
> - Đọc lại thấy `link_id` **khác** thì khoá vô hiệu, tự bỏ.
>
> ⭐ **Không cần tăng đơn điệu.** Ca này chỉ cần biết *đời kho đã đổi*, không cần biết
> đời nào mới hơn. Nên một mã ngẫu nhiên là đủ, và nó đã phải có sẵn cho bus.
>
> ⚠ **Chỉ đúng trong phạm vi MỘT MÁY**, mà đó đúng là phạm vi đã chốt cho LMDB. Nhiều
> máy thì mỗi cha một `link_id` nên phép so luôn ra "khác" và mọi khoá luôn vô hiệu.
> Ngày kho bắc qua nhiều máy thì lời giải này **hết hiệu lực**, không phải chỉ kém đi.
>
> ⚠ App khởi động lại (kho trên đĩa còn nguyên, `link_id` đổi) thì mọi khoá **vô hiệu
> hết**, và đó là **đúng**: app restart nghĩa là mọi job của nó đã chết, khoá của
> chúng đáng bị bỏ.

**Chưa chốt hình dạng hiện thực**, nhưng hết là "chưa thiết kế".

### 7.3. Trần LMDB nới được, nhưng có bẫy

- `env.set_mapsize(n)` nới được lúc chạy, **chỉ nới lên, không thu nhỏ** (muốn thu
  phải `env.copy(compact=True)`). Điều kiện: **không có giao dịch nào đang mở trong
  chính tiến trình đó**.
- ⚠ **Đa tiến trình**: worker A nới trần, worker B vẫn map vùng cũ. B tự map lại ở
  giao dịch kế tiếp, nhưng nếu B đang giữ một giao dịch bắc qua thời điểm đó thì
  nhận `lmdb.MapResizedError`. Mẫu xử lý: bắt lỗi, gọi `env.set_mapsize(0)` (0 =
  lấy theo kích thước hiện tại trong file) rồi thử lại. **Phải có ở mọi đường vào
  kho, không riêng đường ghi.**
- ⚠ **Bẫy "đầy giả", hay cắn nhất**: LMDB tái dùng trang trống, nhưng **một giao
  dịch đọc mở lâu** giữ ảnh chụp cũ nên trang cũ không được thu hồi, kho phình dù
  dữ liệu không tăng. Trong code async, hình dạng nguy hiểm là **`await` một thứ gì
  đó ở giữa một giao dịch đọc** - giao dịch sống theo thời gian chờ chứ không theo
  thời gian làm việc.

  > **Luật phải đặt trong starter: mở, đọc, đóng ngay, không `await` bên trong.**

- Theo dõi bằng `env.info()` (`map_size`, `last_pgno`) và `env.stat()` (`psize`).
  `last_pgno` đếm cả trang trống nên hơi bi quan, nhưng đủ làm ngưỡng cảnh báo.

### 7.4. Windows khác Linux ở hai chỗ (⬇ hạ cấp 2026-08-19: **chỉ là máy dev**)

> Chủ dự án chốt: *"win thì chỉ là máy dev"*. Nên mục này **không còn là việc phải giải**,
> chỉ là thứ phải **chạy được** trên máy dev. Cụ thể: không đi tìm ổ RAM cho Windows, và
> không thiết kế gì quanh việc file bị cấp phát thật - chỉ cần **trần mặc định khiêm tốn** để
> máy dev không mất vài GB đĩa cho kho rỗng.

| | Linux | Windows |
|---|---|---|
| File LMDB | thưa, nới trần gần như miễn phí | **cấp phát thật ngay theo trần** |
| Thuần RAM | `/dev/shm` (tmpfs) | **không có tmpfs**, phải cài ổ RAM của bên thứ ba (không khuyến nghị) |

Máy dev Windows nên khai trần khiêm tốn và để cơ chế tự nới lo phần sau; VPS Linux
thì khai rộng tay cũng không sao.

⚠ Và: **"nằm trên file" không đồng nghĩa "đọc từ đĩa"**. Cả hai hệ đều giữ nội dung
file trong page cache, LMDB mmap thẳng vào đó. Khác biệt thật giữa tmpfs và file
thường chỉ còn: ghi có bị đẩy xuống đĩa không (tắt được bằng cờ), có chiếm chỗ đĩa
không, và bộ nhớ chật thì có bị đẩy ra không.

### 7.5. Ba thứ nữa phải nhớ khi code

- ⚠ **`value[8:]` để cắt tiền tố TTL là một lần copy toàn bộ**, vứt đi chính tính
  không sao chép của LMDB. Dùng `memoryview`, và nhớ đóng giao dịch đọc **sau** khi
  memoryview hết hiệu lực.
- ⚠ **Environment không sống sót qua `fork`.** Master không mở kho; mỗi worker tự
  mở trong bước khởi động của chính nó. Windows dùng `spawn` nên không dính, nhưng
  code phải đúng cho cả hai.
- **Đóng gói**: starter mới `xime/starters/lmdb/`, extra `xime[lmdb]`, **import
  lười** đúng khuôn `redis`/`s3`/`mail`/`mqtt`/`modbus`/`opcua` đang có.

---

## 8. Liên quan

- [`../da-phu-dinh/ke-hoach-0.8-ban-dau.md`](../da-phu-dinh/ke-hoach-0.8-ban-dau.md) - Multi-process Runtime + Bus. **Mục 4.1,
  4.2 của file này bổ sung/lật một phần bản đó**, chưa gộp vào.
- [`lo-trinh-phien-ban.md`](../lo-trinh-phien-ban.md) - 0.8 chưa code, chưa gắn việc
  này vào bản nào.
- [`../rules/background-tasks.md`](../../rules/background-tasks.md) - job nền và tắt
  máy; job dọn TTL ở mục 3 phải theo luật này.
- Luật 01 của workspace, [mục 6](../../../../.claude/rules/01-song-song-hoa-va-shard.md)
  - hai hạng lịch chạy nền, và danh sách trạng thái phải ra khỏi bộ nhớ tiến trình.
  Đó chính là nhóm (b) ở mục 1.
- Luật 03 của workspace - [một giá trị một nghĩa](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md).
  Áp ba lần trong file này: mục 1 (hai nghĩa của "cache"), mục 2.2 (rỗng nghĩa là
  gì), mục 3 #7 (ba kết cục).
