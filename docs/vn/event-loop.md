# Event loop

[English](../en/event-loop.md) | **Tiếng Việt**

[← Đa tiến trình](multi-process.md) · **Event loop** · [Testing →](testing.md)

---

Mọi thứ trong Xime chạy trên một event loop của asyncio. Bình thường bạn không
phải nghĩ tới nó. Trang này dành cho hai lúc bạn cần: khi muốn biết **hôm nay
mình đang chạy trên loop nào**, và khi đang cân nhắc **có nên đổi loop để chạy
nhanh hơn không**.

Từ bản `0.8.1`, Xime tự chọn hiện thực loop tốt nhất cho nền tảng đang chạy.
**Bạn không phải khai gì cả** - không khoá cấu hình, không công tắc.

---

## Loop nào đang chạy - hỏi chính ứng dụng

Mỗi lần khởi động, Xime ghi một dòng ở mức `INFO`:

```text
INFO | xime.bootstrap | event loop: uvloop.Loop
```

```text
INFO | xime.bootstrap | event loop: asyncio.windows_events.ProactorEventLoop
```

Dòng này in **hiện thực đang chạy thật**, không in ý định. Khác biệt đó không
phải chuyện chữ nghĩa: trước `0.8.1`, `uvloop` **đã nằm sẵn trên đĩa ở mọi cài
đặt Linux** của Xime (nó đi kèm `uvicorn[standard]`) mà **chưa bao giờ chạy một
lần nào**, và không có gì báo. Nhìn `pip list` thấy đủ gói rồi kết luận *"đã
bật"* là sai.

> Muốn biết mình đang chạy trên loop nào thì **đọc log của chính tiến trình
> đó**, đừng suy từ danh sách gói đã cài.

---

## Xime chọn loop thế nào

| Nền tảng | Loop | Vì sao |
| --- | --- | --- |
| Linux, macOS | **uvloop** nếu import được, ngược lại mặc định | Nhanh hơn ở phần lớn công việc - xem số đo bên dưới |
| Windows, có `share_load()` dùng chung cổng | `SelectorEventLoop` | Loop proactor mặc định **không** accept được trên socket mà tiến trình khác đã gắn vào IOCP của nó (`WinError 87`) |
| Windows, còn lại | mặc định (proactor) | |

`uvloop` không có bản cho Windows và sẽ không bao giờ có. Trên Windows, phần
uvloop của bảng trên đơn giản là không tồn tại.

### uvloop đến từ đâu

```bash
pip install 'xime[web]'     # kéo theo uvicorn[standard], trong đó có uvloop
```

Không cài extra `web`, hoặc cài `uvicorn` trần, thì không có `uvloop` và ứng
dụng chạy trên loop mặc định. **Chi phí bằng 0**: Xime thử import, không được
thì đi tiếp, không cảnh báo gì.

Xime **không** khai `uvloop` thành phụ thuộc riêng và **không** gọi
`uvloop.install()`. Hàm đó đặt policy toàn cục của cả tiến trình, tức là đụng
vào code không phải của Xime đang chạy chung.

---

## ⚠ uvloop KHÔNG làm REST nhanh hơn - nó làm chậm khoảng 10%

Đây là phần đáng đọc nhất của trang này, và nó ngược với thứ hầu hết bài viết
về uvloop nói.

Số đo trên **cùng một ứng dụng Xime**, Debian 13, Python 3.13.5, uvloop 0.22.1,
dao động dưới 2%, hai lượt cách nhau một tiếng cho cùng kết quả:

| Loại việc | uvloop so với loop mặc định |
| --- | --- |
| **Xử lý một request kiểu HTTP**: REST `0.91x` · bắt tay WebSocket `0.93x` | **lỗ 8-9%** |
| **Truyền trên kết nối đã mở**: tin nhắn WebSocket `1.11x` · echo TCP trần `1.38x` | **lãi 11-38%** |

Trục phân chia **không phải giao thức**. Bắt tay WebSocket là một request
HTTP-upgrade, nên nó rơi **cùng phía với REST** - khác phía với chính những tin
nhắn chạy sau nó **trên cùng cái socket đó**.

Cách hiểu: uvloop nhanh hơn ở phần **vào ra**, nhưng một request HTTP tiêu phần
lớn thời gian ở chỗ khác (phân tích cú pháp, định tuyến, dựng đối tượng, chạy
code của bạn). Lãi ở tầng dưới không đủ bù, và trên chồng HTTP của Python nó
còn hoá ra lỗ.

### Vậy vì sao Xime vẫn dùng uvloop

- **Không mất gì khi vắng mặt.** Không có uvloop thì ứng dụng chạy y như mọi
  bản trước.
- **REST không phải cả framework.** Năm adapter còn lại (gRPC, socket, MQTT,
  Modbus, OPC UA) đều sống trên **kết nối đã mở** - đúng phía có lãi.
- **Hiệu suất trên mỗi %CPU luôn thắng** (1.31x tới 1.64x). Trên máy tính tiền
  theo CPU, đó là chỉ số đáng giá hơn thông lượng đỉnh.

### 📌 Nút điều chỉnh có ích không phải event loop

Nếu bạn đang đọc trang này để tìm cách chạy nhanh hơn, con số đáng nhớ là đây:

| Việc | Thông lượng |
| --- | --- |
| Thêm một tiến trình (`count:` trong khối `processes:`) | **+100%** |
| Đổi event loop | **-10%** cho REST |

Xem [Đa tiến trình](multi-process.md). Cụm Xime mở rộng gần tuyến tính: 2.00x
với hai tiến trình, 3.88x với bốn.

---

## Vì sao không có công tắc bật/tắt

Câu hỏi tự nhiên sau khi đọc mục trên: *"vậy cho tôi tắt uvloop cho REST đi"*.

Xime cố ý không có khoá đó, vì **người vận hành không có đủ thông tin để chọn**.
Trả lời được câu *"ứng dụng của tôi nên dùng loop nào"* thì phải biết tỉ lệ
request kiểu HTTP so với công việc trên kết nối đã mở, biết mỗi handler tiêu
thời gian ở đâu, và phải đo trên chính máy chạy thật. Chính người viết framework
cũng phải đo mới biết, và kết quả đo lật ngược giả định ban đầu.

Một khoá cấu hình ở đây chỉ tạo ra hai kết cục: hoặc không ai đụng tới, hoặc có
người đặt sai dựa trên một bài viết trên mạng.

Cần thật thì bạn vẫn chặn được ở tầng cài đặt: cài `uvicorn` trần thay vì
`uvicorn[standard]`, hoặc gỡ `uvloop` khỏi môi trường. Xime tự thấy và đi tiếp.

---

## Liên quan

- [Đa tiến trình](multi-process.md) - `share_load()`, khối `processes:`, và lý
  do Windows phải đổi sang loop selector khi dùng chung cổng.
- [WebSocket](websocket.md) - adapter hưởng lợi nhiều nhất từ uvloop, ở phần
  tin nhắn chứ không phải phần bắt tay.
