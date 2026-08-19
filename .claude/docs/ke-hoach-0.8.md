# Kế hoạch 0.8 - Multi-process Runtime + Bus liên Worker

> ## ⛔⛔ FILE NÀY PHẦN LỚN ĐÃ LỖI THỜI - ĐỪNG ĐỌC NHƯ HIỆN TRẠNG
>
> Buổi thiết kế **2026-08-16** lật hoặc thay phần lớn bản này. **Nên VIẾT LẠI chứ
> không bổ sung.** Đọc hai file sau trước:
>
> | Đọc thay | Nội dung |
> |---|---|
> | [`da-tien-trinh-main-va-cau-hinh-2026-08-16.md`](da-tien-trinh-main-va-cau-hinh-2026-08-16.md) | Mô hình chạy, `main.py`, cấu hình, adapter phải đổi gì |
> | [`cache-lien-tien-trinh-2026-08-16.md`](cache-lien-tien-trinh-2026-08-16.md) | Kho liên tiến trình (LMDB + shared memory), lý do hoãn đa luồng |
> | **[`bus-lien-tien-trinh-2026-08-18.md`](bus-lien-tien-trinh-2026-08-18.md)** | **Bus - thay hẳn phần Bus của file này.** Tên chốt `ProcessLink` |
| **[`kho-nhom-1-snapshot-2026-08-18.md`](kho-nhom-1-snapshot-2026-08-18.md)** | **Kho nhóm 1** - tên chốt **`RefData`**. Dữ liệu **có** nguồn bền vững |
| **[`kho-nhom-2-store-2026-08-19.md`](kho-nhom-2-store-2026-08-19.md)** | **Kho nhóm 2** - tên chốt **`Store`**, trên LMDB. Dữ liệu **không** có nguồn |
>
> **Ba thứ trong file này KHÔNG còn dùng:**
>
> | Bản 2026-06-27 | Thay bằng |
> |---|---|
> | Bus Manager + single shared queue + mutex + transport abstraction + API broadcast | **Bộ nhớ chung, mỗi tiến trình một vùng ghi riêng; cha KHÔNG chuyển tiếp tin nào.** Bus chở **tín hiệu** (dữ liệu đi LMDB / shared memory), có **phản hồi** với **bốn kết cục**, định tuyến bằng **kênh + khoá lọc ở bên nhận**. Chi tiết: [`bus-lien-tien-trinh-2026-08-18.md`](bus-lien-tien-trinh-2026-08-18.md) |
> | DI scope `global` / `worker`; Worker 0 giữ global singleton; Worker 0 chết thì crash toàn chương trình | **DI dựng ĐỦ ở mọi tiến trình**, cái nào không được chạy thì **tắt bằng cờ**. Supervisor **thăng cấp** một con đang chạy khi primary chết |
> | HTTP routing tới worker (defer hẳn) | Không cần - **mỗi tiến trình một cổng, hoặc chung cổng qua kernel** |
>
> **Còn dùng được:** `BusMessage`, phần hàng đợi, và mục "Mảng 2 - Config cải thiện".
>
> Phần dưới giữ nguyên làm **lịch sử thiết kế**, đừng xoá: nó cho biết vì sao từng
> chọn như vậy, và bốn chỗ mà buổi 08-16 bổ sung/lật là bốn chỗ đáng học.

Trạng thái: **Thiết kế ban đầu chốt 2026-06-27. Chưa code.**
Khi bắt tay code, bổ sung chi tiết implementation vào file này.

---

## Hai mảng chính

| Mảng | Nội dung | Khối lượng |
| --- | --- | --- |
| 1 | Multi-process Runtime + Bus liên Worker | Lớn |
| 2 | Config cải thiện (carry-over từ kế hoạch cũ) | Nhỏ |

---

## Mảng 1 - Multi-process Runtime

### Động lực

Framework backend Python bị giới hạn bởi GIL - một process chỉ dùng được một
nhân CPU tại một thời điểm. Giải pháp chuẩn là spawn nhiều process. Xime cần
tích hợp mô hình này vào runtime để developer không phải tự lo gunicorn hay
process management ngoài framework.

Traffic inter-worker thực tế rất thấp (config sync, cert rotation, cache
invalidation) - không cần thiết kế high-throughput messaging.

### Nguyên tắc thiết kế

- **Mặc định TẮT.** Khi chưa bật, ứng dụng chạy single-process như hiện tại,
  không có gì thay đổi. Bật tường minh trong cấu hình (giống cờ
  `xime.di.dynamic-binding` của 0.6).
- Mỗi worker hoàn toàn độc lập: FastAPI app riêng, DI container riêng,
  singleton riêng, event loop riêng. Không chia sẻ Python object giữa worker.
- Bus chỉ truyền Message (dữ liệu serialize được), không truyền object.
- `core/event/` (event bus intra-process) và Bus này (inter-process) **độc lập**
  nhau - muốn event lan sang worker khác thì dùng Bus, không phải event bus cũ.

### Kiến trúc

```
                    Master Process
                          |
                    Bus Manager
                          |
              Single Shared Queue (mutex ghi)
                          |
         +----------------+----------------+
         |                |                |
      Worker 0         Worker 1        Worker N
   (FastAPI + DI)   (FastAPI + DI)  (FastAPI + DI)
```

**Bus Manager** (process riêng hoặc thread trong master - TBD):

- Quản lý vòng đời worker (spawn, monitor, restart).
- Đọc message từ shared queue và phân phối tới worker đích.
- Quản lý vòng đời shared memory.

**Shared Queue:**

- Một queue duy nhất (không phải per-worker SPSC).
- Worker muốn gửi message thì ghi vào queue, đợi turn (mutex).
- Bus Manager đọc và fan-out tới worker đích.
- Thiết kế đơn giản hợp lý vì tần suất ghi thấp.

### DI Scope mới

Hiện tại Xime chỉ có một scope ngầm định: singleton per-worker (mỗi worker
tạo instance độc lập). 0.8 thêm scope tường minh:

| Scope | Số instance | Vị trí | Ghi chú |
| --- | --- | --- | --- |
| `worker` | N (một/worker) | Mỗi worker | Mặc định, hành vi hiện tại |
| `global` | 1 (toàn hệ thống) | Worker 0 | Mới trong 0.8 |

**Quy tắc `global` scope:**

- Instance duy nhất sống trên **Worker 0**.
- Worker khác (1..N) **không tạo** instance của class này - nếu khai báo inject
  vào class chạy ở worker khác → **startup fail** với thông báo rõ.
- Global singleton thường là "đầu chuỗi" - nó gọi class khác, không ai inject
  ngược lại nó từ worker khác (ví dụ: scheduler task chỉ chạy 1 lần, fetch
  config từ external service 1 lần).
- **Worker 0 chết:** Bus Manager cố restart Worker 0 và dựng lại global
  singleton. Nếu không được → crash toàn chương trình (global singleton là
  critical component).

**Cú pháp khai báo scope** - TBD (xác định khi thiết kế chi tiết). Ràng buộc:
không dùng annotation trên class, phải explicit trong `config/dependency.py`.

Ví dụ hướng đi (chưa chốt):

```python
dependency.register(KeyFetcher, scope="global")
dependency.register(LocalCache, scope="worker")   # hoặc bỏ qua vì là default
```

### Bus API (0.8 scope: broadcast-only)

Chỉ có broadcast trong 0.8. Point-to-point (`send(worker=N)`) để phiên bản sau
khi có use case thực tế.

Tên hàm - TBD. Hướng sơ bộ:

```python
await bus.broadcast(message)   # push tới tất cả worker
```

Developer không cần biết IPC, shared memory, queue - chỉ cần biết gửi message.

### Cấu trúc Message

```python
@dataclass
class BusMessage:
    message_id: str
    timestamp: float
    source_worker: int
    event_type: str
    payload: bytes        # serialized, dùng msgpack hoặc tương đương
```

### Transport Abstraction

Thiết kế theo Transport layer để sau có thể swap mà không đổi API:

```
BusTransport (Protocol)
    SharedMemoryTransport   <- 0.8 implement
    UnixSocketTransport     <- tương lai
    RedisTransport          <- tương lai (distributed)
    TcpTransport            <- tương lai
```

0.8 chỉ implement `SharedMemoryTransport`. Khi cần distributed thì thêm
`RedisTransport` mà API ứng dụng không đổi.

### Pattern ứng dụng điển hình

```
ClassA (global, Worker 0):
    - Scheduler gọi A.run(b) một lần duy nhất
    - A nhận B qua tham số
    - A.run() gọi b.update(data)

ClassB (per-worker):
    - Mỗi worker có một B (cache, state...)
    - B.update() cập nhật local + gọi bus.broadcast(DataUpdated(data))
    - Worker khác nhận broadcast → gọi b.update(data) trên instance của mình
```

### Câu hỏi còn mở / TBD

| Câu hỏi | Ghi chú |
| --- | --- |
| Bus Manager là process riêng hay thread trong master? | Ảnh hưởng overhead và lifecycle |
| Tên cụ thể các hàm Bus API | Thiết kế chi tiết sau |
| Cú pháp khai báo scope trong `dependency.py` | Thiết kế chi tiết sau |
| HTTP request routing đến worker | **Defer hẳn** - không làm trong 0.8 |
| Cờ bật runtime tên gì, đặt ở đâu trong YAML | Thiết kế chi tiết sau |

### Known limitations (0.8)

- HTTP request routing chưa được thiết kế - 0.8 có thể chưa tích hợp với web
  adapter (chạy multi-process nhưng load balancing ngoài framework).
- Worker 0 chết và restart mất thời gian - trong khoảng đó global singleton
  không tồn tại, ứng dụng xử lý thế nào là TBD.
- Chỉ có SharedMemoryTransport - giới hạn single machine.

---

## Mảng 2 - Config cải thiện

Chi tiết xác định khi bắt tay code. Điểm khởi đầu (từ kế hoạch cũ):

- Rà pattern `configure_*` (openapi/routing/middleware/exception_handlers/...):
  đặt tên, chữ ký, vị trí có nhất quán không.
- Ranh giới hai tầng Framework config (Python) và Runtime config (YAML): còn
  rõ ràng và hợp lý không, có chỗ trùng lặp.
- Thông điệp lỗi khi thiếu/sai khóa YAML: đủ rõ ràng (fail-fast) chưa.

Ràng buộc giữ nguyên: **Explicit is better than implicit**, minimal magic,
fail-fast lúc startup.

Phần còn dư sau 0.8 chuyển sang 0.9.

---

## Bước cuối - Rà soát trước khi phát hành

Sau khi code xong cả hai mảng: soi lại phần vừa thêm, bắt mâu thuẫn logic /
lỗi message / khoảng trống test. Không cần toàn diện như 0.5; chỉ soi những
gì 0.8 chạm tới.
