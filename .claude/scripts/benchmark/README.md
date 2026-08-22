# Benchmark của Xime Framework

> Lập **2026-08-22**, trong đợt đo uvloop của 0.8.1. Kết quả đo và cách đọc:
> [`../../docs/ghi-chep/benchmark-hieu-nang.md`](../../docs/ghi-chep/benchmark-hieu-nang.md).

```bash
python .claude/scripts/benchmark/run_all.py            # cả bốn tầng
python .claude/scripts/benchmark/run_all.py http scale # chỉ vài tầng
python .claude/scripts/benchmark/bench_http.py 5       # một tầng, 5 lượt lấy trung vị
```

Cần `ab` (gói `apache2-utils`) cho tầng 2 và 4. Thiếu nó thì hai tầng đó **tự
khai là bỏ qua**, không im lặng cho ra bảng thiếu dòng.

## Bốn tầng, và vì sao phải là bốn

Mỗi tầng chồng thêm một lớp lên tầng dưới. Hiệu số giữa hai dòng liền nhau là
**giá của đúng lớp nằm giữa chúng** - đó là thứ một phép đo đơn lẻ không nói được.

| Tầng | File | Đo cái gì | Client |
|---|---|---|---|
| 1 | `bench_loop.py` | echo TCP trần, Stream API và Protocol API | Python |
| 2 | `bench_http.py` | ASGI trần -> FastAPI -> Xime WebAdapter | **`ab` (C)** |
| 3 | `bench_core.py` | khởi động, DI, Store LMDB, RefData | không có |
| 4 | `bench_scale.py` | cụm N tiến trình chung một cổng | **`ab` (C)** |
| 5 | `bench_ws.py` | WebSocket: tin nhắn trên kết nối sống lâu, và bắt tay | Python |

Tầng 1, 2 và 5 chạy **hai nhánh**: uvloop và loop mặc định. Nhánh "loop mặc định"
của app Xime **không sửa mã framework** - nó chèn một `uvloop.py` giả ném
`ImportError` lên `PYTHONPATH`, tức đi đúng nhánh `except ImportError` mà
`uvloop_factory()` vốn có.

### Công cụ phụ

`_ma_tran_tai.py <tang>` chạy một ma trận tải (keepalive/không × c=10/100/400)
cho một tầng. Dùng khi một tỉ lệ trông đáng ngờ và cần biết nó có đúng ở mọi hình
dạng tải không - chính nó đã xác nhận phát hiện *"uvloop làm chồng Xime chậm đi"*
là thật chứ không phải nhiễu của một cấu hình `ab` cụ thể.

## ⛔ Luật của bộ này: mỗi phép đo phải tự khai nó đo được cái gì

Hai lần trong buổi dựng bộ này, một phép đo cho ra con số **trông hoàn toàn hợp
lý** trong khi nó đang đo **dụng cụ đo**:

| Ca | Kết quả nhìn thấy | Sự thật |
|---|---|---|
| `ab` bắn vào app Xime | uvloop = loop thường | **hợp lệ** - app 100% CPU, `ab` 36% |
| client Python bắn vào echo server | uvloop = loop thường | **vô hiệu** - server 24.8% CPU |

**Hai ca cho ra cùng một hình dạng kết quả, chỉ một trong hai có giá trị.** Nên
mọi dòng kết quả mang một nhãn, và có **BỐN** nhãn chứ không hai:

| Nhãn | Nghĩa | Dùng được không |
|---|---|---|
| `SERVER_BOUND` | server đã kịch trần CPU | **Có** |
| `CLIENT_BOUND` | gấp đôi worker thì tổng tăng -> nút thắt ở client | **KHÔNG. Vứt dòng đó đi** |
| `CHUA_KET_LUAN_DUOC` | hai tín hiệu chỏi nhau, hoặc thiếu dữ kiện | **Không.** Đừng gộp vào `SERVER_BOUND` |
| `MOT_LUONG` | phép đo trong tiến trình, không có client | Có, nhưng đọc là *"một lời gọi tốn bao nhiêu"* |

⚠ **`CHUA_KET_LUAN_DUOC` gộp vào `SERVER_BOUND` là báo xanh cho một phép đo chưa
hề chạy** - đúng thứ [luật 03](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md)
mục 4b cấm, và repo này đã cắn nó một lần với `ShardValueGuard`.

### Hai phép kiểm bắt buộc, đã gắn sẵn vào khung

1. **Bão hoà**: chạy N worker rồi chạy 2N worker. Tổng tăng >= 1.25x nghĩa là
   client cũ là nút thắt. ⚠ Phải so **N với 2N**, không phải **1 với N** - so 1
   với N thì tỉ lệ luôn lớn và mọi phép đo bị dán nhãn client-bound (đã mắc lỗi
   này thật lúc dựng khung).
2. **Bằng chứng nhánh**: mỗi phép đo đọc dòng `event loop: ...` từ log server
   thật. **Không đọc được thì NÉM, không in dấu `?`** - một phép đo không tự
   chứng minh được nó chạy trên nhánh nào thì không có giá trị so sánh.
   ⛔ Vì thế **đừng đặt `logging.level: WARNING`** trong cấu hình app bench: nó
   nuốt đúng dòng bằng chứng đó.

## Vài chỗ dễ vấp khi sửa bộ này

| | |
|---|---|
| `pkill -f <mẫu>` | Mẫu tìm nằm trong chính dòng lệnh của shell, nên nó **tự giết shell**. Dùng PID, hoặc `pgrep -P` |
| `wait` trần trong bash | Đợi luôn cả tiến trình server, treo vĩnh viễn. Dùng `chay_song_song()` của khung |
| Lấy `max` của nhiều lượt | Đó là con số của lần máy tình cờ rảnh nhất. Bộ này lấy **trung vị** |
| Máy không yên tĩnh | Trình duyệt đang mở chiếm >100% CPU. Đóng bớt trước khi đo, hoặc ghi rõ trong kết quả |

## Thêm một phép đo mới

Trả về `list[KetQua]` từ một hàm `chay()`, rồi khai vào `TANG` của `run_all.py`.
`KetQua` bắt buộc có nhãn bão hoà - **không có giá trị mặc định là `SERVER_BOUND`**,
vì mặc định im lặng chính là cách một phép đo chưa chạy trở thành một dòng xanh.
