# Benchmark hiệu năng: bốn tầng, và uvloop lãi ở đâu

> | | |
> |---|---|
> | **Trạng thái** | **ĐANG DÙNG** - đo lần đầu 2026-08-22 |
> | **Thuộc bản** | `0.8.1` (đợt uvloop), nhưng bộ đo không gắn với bản nào |
> | **Thay cái gì** | Không thay gì. Trước đây framework **không có** benchmark nào |
> | **Bị thay bởi** | Chưa. Số liệu thì lỗi thời theo máy và theo bản; **cách đo** thì không |
>
> Bộ đo chạy được: [`../../scripts/benchmark/`](../../scripts/benchmark/README.md).
> Bối cảnh đợt uvloop: [`../kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](../kiem-toan/0.8.1-ket-qua-do-tren-linux.md).

## 0. Ba câu trả lời, đọc cái này là đủ

| Câu hỏi | Trả lời đo được |
|---|---|
| **uvloop lãi bao nhiêu?** | **Tuỳ hình dạng tải, và ranh giới đã đo được rõ:** truyền trên kết nối đã mở thì **lãi** (loop trần +38%, tin nhắn WebSocket +11%); xử lý request kiểu HTTP thì **lỗ ~10%** (REST 0.91x, bắt tay WebSocket 0.93x) |
| **Xime đắt hơn FastAPI bao nhiêu?** | Chồng ba tầng: ASGI trần **100%** -> FastAPI **66%** -> Xime **41%**. Tức Xime lấy đi ~38% thông lượng so với FastAPI trần |
| **Cụm nhiều tiến trình có mở rộng không?** | **Có, gần tuyến tính: 2.00x với 2 tiến trình, 3.88x với 4**, và **N/N tiến trình thật sự nhận việc** |

⚠ Cả ba câu trên đo trên **một endpoint gần như không làm gì** (`{"ok":"1"}`).
Ứng dụng thật có database, có JWT, có nghiệp vụ - mọi tỉ lệ ở đây sẽ dịch về
phía *"tầng framework càng không quan trọng"*. Xem mục 5.

## 1. Máy và cách đo

**Số liệu dưới đây lấy từ MỘT lượt `run_all.py` duy nhất** (25 phép đo, 0 dòng
phải vứt vì client-bound, 3 dòng `CHUA_KET_LUAN_DUOC` được khai rõ tại chỗ), để
mọi tỉ lệ so được với nhau. Các lượt rời rạc chạy trước đó cho cùng kết quả.

Debian 13 (trixie), kernel `6.12.101`, **16 CPU**. Python **3.13.5**, uvloop
**0.22.1**, uvicorn **0.52.4**, httptools 0.8.0.
⚠ **Máy không yên tĩnh**: trình duyệt chiếm >100% CPU trong lúc đo. Con số tuyệt
đối vì thế là **sàn**; các **tỉ lệ** thì ít bị ảnh hưởng vì hai nhánh chạy xen kẽ.

Nhánh "loop mặc định" của app Xime **không sửa mã framework**: chèn một
`uvloop.py` giả ném `ImportError` lên `PYTHONPATH`, đi đúng nhánh
`except ImportError` mà `uvloop_factory()` vốn có.

## 2. Tầng 1 - event loop trần (echo TCP)

| API | uvloop | mặc định | tỉ lệ | hiệu suất/%CPU |
|---|---|---|---|---|
| Stream (`start_server`) | 109,554 rtt/s (81% CPU) | 79,382 (97% CPU) | **1.38x** | **1.64x** |
| Protocol (`create_server`) | 120,437 rtt/s (65% CPU) | 121,502 (90% CPU) | 0.99x | **1.38x** |

⚠ **Hai dòng uvloop bị đánh dấu `CHUA_KET_LUAN_DUOC`**: server còn dư sức (64-81%
CPU) trong khi client Python đã hết hơi. Nên **thông lượng uvloop đo được là SÀN,
không phải trần**, và ô `0.93x` không đọc được thành *"uvloop chậm hơn"*.

⭐ **Chỉ số vững ở tầng này là hiệu suất trên mỗi %CPU**, vì nó không chết theo
dụng cụ đo: hai nhánh làm cùng một khối lượng việc, cái nào tốn ít CPU hơn thì rẻ
hơn. Theo chỉ số đó uvloop **luôn thắng, 1.31x tới 1.61x**.

📌 Chênh lệch giữa hai hàng cũng đáng nhớ: **Protocol API nhanh hơn Stream API
đáng kể ở cả hai nhánh**. Con số "2-4x" của uvloop trên internet gần như luôn đo
bằng Protocol API - `StreamReader/StreamWriter` thêm một lớp Python nằm **ngoài**
phạm vi uvloop thay thế được.

## 3. Tầng 2 - HTTP (client là `ab`, viết bằng C)

Trung vị 3 lượt, `-k -n 20000 -c 100`. Cả sáu dòng đều `SERVER_BOUND` (94-99% CPU)
nên **đều tin được**.

| Chồng | uvloop | mặc định | tỉ lệ | so với ASGI trần |
|---|---|---|---|---|
| ASGI trần | 10,799 req/s | 10,631 | **1.02x** | 100% |
| FastAPI | 7,151 | 7,961 | **0.90x** | 66% |
| **Xime WebAdapter** | **4,396** | **4,838** | **0.91x** | **41%** |

### ⛔ Phát hiện đi ngược giả định của 0.8.1: uvloop làm chồng Xime CHẬM ĐI

Dao động trong mỗi nhánh dưới 2% (ba lượt: 4,388 / 4,396 / 4,454 và 4,833 /
4,838 / 4,840), nên đây **không phải nhiễu**. Hai lượt chạy đầy đủ cách nhau một
tiếng cho ra cùng kết quả (0.89x rồi 0.91x). Đối chứng trên sáu hình dạng tải:

| tải | uvloop | mặc định | tỉ lệ |
|---|---|---|---|
| keepalive c=10 | 4,341 | 4,546 | 0.95x |
| keepalive c=100 | 4,488 | 4,770 | 0.94x |
| keepalive c=400 | 4,366 | 4,461 | 0.98x |
| đóng mỗi lần c=10 | 4,565 | 4,426 | 1.03x |
| đóng mỗi lần c=100 | 4,261 | 4,784 | 0.89x |
| đóng mỗi lần c=400 | 4,348 | 4,572 | 0.95x |

**5/6 ô cho thấy uvloop chậm hơn.** Câu chuyện khớp với tầng 1: uvloop tăng tốc
tầng loop/transport, nhưng nó cũng có **chi phí cố định mỗi callback**. Khi ứng
dụng kẹt ở công việc mức Python thì phần lãi không có chỗ hiện ra, còn chi phí
thì vẫn phải trả.

> **uvloop lãi tỉ lệ nghịch với lượng việc mức Python trên mỗi request.** Ba dòng
> của bảng chính xếp đúng theo trục đó: **1.02x -> 0.90x -> 0.91x**.

⚠ **Đây KHÔNG phải lý do gỡ uvloop**, và cũng không phải lý do giữ nguyên mà
không nói gì. Xem mục 6.

## 4. Tầng 3 - lõi framework (đo trong tiến trình, một luồng)

Không có client nên không có bài toán bão hoà; đổi lại đọc là *"một lời gọi tốn
bao nhiêu"*, không phải *"cả máy chịu được bao nhiêu"*.

| Phép đo | Số đo |
|---|---|
| `import xime` | **140 ms** (đã trừ 10 ms Python trần) |
| `+ adapters.web` | 257 ms |
| `+ adapters.grpc` | 303 ms |
| `DI: get()` singleton | **~13,7 triệu op/s** |
| `Store` LMDB `set` | 54,850 op/s |
| `Store` LMDB `get` (có) | 74,300 op/s |
| `Store` LMDB `get` (không có) | 88,000 op/s |
| `Store` LMDB `incr` | 50,300 op/s |
| **`RefData.read()` 4KB** | **~4,6 triệu op/s** |
| `RefData.publish()` 4KB | 19,600 op/s |

Ba chỗ đáng đọc:

**a. `DI.get()` ~13 triệu op/s là con số PHẢI lớn, không phải con số đáng khoe.**
Xime dựng toàn bộ đồ thị eager lúc khởi động, nên `get()` lúc chạy chỉ là một lần
tra dict. Nó nhỏ đi nghĩa là có gì đó đang dựng lại object - **hỏng**, không phải
chậm. Đo hai biến thể (không dep / một dep) và chúng bằng nhau, đúng như thiết kế.

**b. `RefData.read()` nhanh hơn `Store.get()` khoảng 60 lần**, và đó là lý do hai
thứ này tồn tại tách nhau: `RefData` đọc thẳng từ bộ nhớ chung có cache L1, còn
`Store` phải mở một transaction LMDB. Ranh giới *có nguồn bền vững hay không* hoá
ra trùng với ranh giới hiệu năng - đọc khoá JWT ở đường nóng mỗi request thì phải
là `RefData`, không được là `Store`.

**c. `Store.get()` cho khoá KHÔNG tồn tại nhanh hơn khoá có (86,8k so với 73k).**
Đáng nhớ vì đó là **ca thường gặp nhất của hãm nhịp** - phần lớn lần kiểm là
"người này chưa có bản ghi nào". Bench nào chỉ đo khoá-có thì đang đo ca hiếm.

**d. 145 ms cho `import xime`** cộng thêm cho mỗi adapter. Nhân với `N+1` tiến
trình (cha cũng import lại - xem [`rules/module-level-code.md`](../../rules/module-level-code.md)),
nên một cụm 4 tiến trình trả khoảng **1,3 giây** chỉ để import.

## 5. Tầng 4 - cụm nhiều tiến trình (`share_load`)

| Cụm | req/s | mở rộng | lý tưởng | CPU | tiến trình trả lời |
|---|---|---|---|---|---|
| 1 tiến trình | 4,321 | 1.00x | 1.00x | 97% | 1/1 |
| **2 tiến trình** | **8,629** | **2.00x** | 2.00x | 194% | **2/2** |
| **4 tiến trình** | **16,763** | **3.88x** | 4.00x | 328% | **4/4** |

⭐ **Đây là kết quả tốt nhất của cả buổi đo, và nó là tính năng đầu bảng của 0.8.**
Mở rộng gần như tuyến tính, kernel chia tải đều.

⚠ Cột cuối là phép kiểm **không thay được bằng rps**: cách hỏng đáng sợ nhất của
mô hình này không làm giảm thông lượng mà **làm mất một nửa năng lực trong im
lặng** - con thứ hai khởi động thành công, log *"serving"*, rồi không nhận nổi
một kết nối nào (ca `WinError 87` trên Windows). Một cụm 4 tiến trình mà chỉ 2
cái trả lời vẫn cho ra một con số rps **trông bình thường**.

📌 **Đặt cạnh mục 3 thì ra một kết luận thực dụng:** thêm một tiến trình cho
**+100%** thông lượng, còn uvloop cho **-10%**. Với một app Xime điển hình, nút
điều chỉnh có ích là `count:`, không phải event loop.

## 5b. Tầng 5 - WebSocket: cùng app, đổi hình dạng tải

Tầng 2 nói uvloop **chậm hơn**, tầng 1 nói uvloop **nhanh hơn**. Tầng này hỏi
câu còn lại: **cùng một app Xime, đổi hình dạng tải từ REST sang kết nối sống
lâu thì nghiêng về bên nào?** Cùng framework, cùng app, cùng máy - nên hiệu số
quy được về đúng một nguyên nhân.

| Phép đo | uvloop | mặc định | tỉ lệ |
|---|---|---|---|
| **Tin nhắn trên một kết nối đã mở** | **7,543 tin/s** | 6,825 | **1.11x** |
| Bắt tay (200 kết nối cùng lúc) | 1,542 conn/s | 1,654 | **0.93x** |

⭐⭐ **Hai dòng này chia đôi câu chuyện, và chúng khớp với hai tầng trên tới mức
không thể là trùng hợp:**

| Loại việc | Đo ở đâu | uvloop |
|---|---|---|
| Xử lý một request kiểu HTTP | REST **0.91x** · bắt tay WS **0.93x** | **lỗ ~8-9%** |
| Truyền trên kết nối đã mở | tin nhắn WS **1.11x** · loop trần **1.38x** | **lãi 11-38%** |

> **Ranh giới không phải "WebSocket hay REST". Nó là "xử lý request kiểu HTTP"
> so với "truyền trên một kết nối đã mở".** Bắt tay WebSocket là một request
> HTTP-upgrade, và nó rơi đúng vào nhóm thứ nhất - cùng phía với REST, khác phía
> với chính những tin nhắn chạy sau nó trên cùng cái socket đó.

⚠ Client tầng này là Python (`websockets`) chứ không phải C, nên đọc **tỉ lệ**,
đừng đọc con số tuyệt đối như trần của server.

## 6. uvloop: giữ hay bỏ

**Khuyến nghị: GIỮ, và ghi rõ nó lãi ở đâu.** Ba lý do:

1. **Chi phí bằng 0 khi không dùng tới**: không có uvloop thì `uvloop_factory()`
   trả `None` và app chạy y hệt mọi bản trước 0.8.1.
2. **REST không phải cả framework, và điều này nay ĐO ĐƯỢC chứ không còn là suy
   luận.** Tầng 5 chạy **cùng một app Xime** và cho **1.11x** ở tin nhắn
   WebSocket. Xime có sáu adapter; mọi thứ sống trên một kết nối đã mở - socket
   adapter, gRPC streaming, MQTT, fieldbus, WebSocket - nằm đúng phía uvloop lãi.
3. **Hiệu suất trên mỗi %CPU luôn thắng** (1.31x-1.61x ở tầng 1). Trên VPS 2 lõi
   tính tiền theo CPU thì đó là chỉ số đáng giá hơn thông lượng đỉnh.

⛔ **Đừng thêm công tắc bật/tắt uvloop** để "cho người dùng tự chọn". Lý do đã
ghi ở mục 6.1 của [`../sap-toi/tang-toc-uvicorn-uvloop.md`](../sap-toi/tang-toc-uvicorn-uvloop.md),
và số liệu này không đổi được lý do đó: người vận hành không có đủ thông tin để
chọn, mà chính người viết framework cũng phải đo mới biết.

⏳ **Thứ CHƯA đo**: gRPC streaming · socket adapter dưới tải · MQTT · phản hồi
lớn (nhiều KB) · app có I/O database thật. WebSocket thì **đã đo** (tầng 5) và
nó xác nhận đúng chiều dự đoán, nên bốn cái còn lại nhiều khả năng cùng chiều -
**nhưng "nhiều khả năng" không phải một phép đo.**

## 7. Bài học về CÁCH đo, phần không lỗi thời theo máy

**a. Một phép đo phải tự khai nó đo được cái gì.** Hai lần trong buổi này, một
con số trông hợp lý hoá ra đang đo **dụng cụ đo**:

| Ca | Nhìn thấy | Sự thật |
|---|---|---|
| `ab` bắn vào app Xime | uvloop = loop thường | **hợp lệ** - app 100% CPU, `ab` 36% |
| client Python bắn echo server | uvloop = loop thường | **vô hiệu** - server 24.8% CPU |

Hai ca **cùng một hình dạng kết quả**, chỉ một cái có giá trị. Không có phép kiểm
bão hoà thì không cách nào tách ra.

**b. Phải so N với 2N, không phải 1 với N.** Bản đầu của khung so một worker với
N worker, và vì một worker thì đương nhiên thiếu nên **mọi phép đo đều bị dán
nhãn client-bound** - kể cả những phép đo hoàn toàn hợp lệ.

**c. Bằng chứng nhánh phải nằm trong kết quả.** Lượt đầu của tầng 2 in loop `?`
cho các dòng Xime, vì chính tôi đặt `logging.level: WARNING` và nuốt mất dòng
`event loop:`. Khung nay **ném lỗi** thay vì in `?`: một phép đo không tự chứng
minh được nó chạy nhánh nào thì không có giá trị so sánh.

**d. Lấy trung vị, đừng lấy max.** Max là con số của lần máy tình cờ rảnh nhất.

**e. `wait` trần trong bash đợi luôn tiến trình server** (đã treo một lượt đo 10
phút), và **`pkill -f <mẫu>` tự giết shell** vì mẫu nằm trong chính dòng lệnh.

## 8. Liên quan

- [`../../scripts/benchmark/README.md`](../../scripts/benchmark/README.md) - cách chạy, bốn nhãn, chỗ dễ vấp.
- [`../kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](../kiem-toan/0.8.1-ket-qua-do-tren-linux.md) - đợt đo uvloop, bốn phép đo bắt buộc.
- [`../sap-toi/tang-toc-uvicorn-uvloop.md`](../sap-toi/tang-toc-uvicorn-uvloop.md) - thiết kế uvloop, mục 6.1 vì sao không có công tắc.
- [`../thiet-ke/12-kho-refdata.md`](../thiet-ke/12-kho-refdata.md) và [`13-kho-store-lmdb.md`](../thiet-ke/13-kho-store-lmdb.md) - ranh giới *có nguồn bền vững hay không*, mà mục 4b cho thấy trùng với ranh giới hiệu năng.
- [`../../rules/module-level-code.md`](../../rules/module-level-code.md) - vì sao chi phí import nhân với `N+1`.
