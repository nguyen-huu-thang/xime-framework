# Vòng lặp nền và tắt máy - luật nội bộ Xime Framework

> Lập **2026-08-04** sau lỗi đua khi tắt scheduler (`RuntimeError: The scheduler has not been
> initialized yet`). Chẩn đoán đầy đủ: [`../docs/ghi-chep/loi-dua-scheduler.md`](../docs/ghi-chep/loi-dua-scheduler.md).
>
> Đây là quy tắc **nội bộ repo này**, không phải luật cắt ngang workspace. Framework là nơi
> **quyết định các repo khác vi phạm dễ đến đâu**, nên chỗ này chặt hơn code ứng dụng thông thường.

## 1. Luật

> **`create_task()` chưa chạy dòng nào của coroutine. Đừng viết bất cứ đường tắt nào giả định
> nó đã khởi động.**

Điều kiện gây lỗi **không phải `create_task`** - hàm đó tự nó vô hại. Nó là:

> **`create_task` cộng với một đường tắt giả định task đã khởi động.**

## 2. Bảng phân biệt - dùng khi thêm một vòng lặp nền mới

| Hình dạng | An toàn? | Vì sao |
| --- | --- | --- |
| Vòng lặp dài, tắt bằng `task.cancel()` | **Có** | `cancel()` hợp lệ trên task chưa từng chạy - **không phụ thuộc trạng thái** |
| Task một-việc-một-lần cho từng message/request | **Có** | Không có đường tắt nào giả định chúng đã khởi động |
| Task nền có giữ strong-ref + `add_done_callback` | **Có** | Không ai dọn tài nguyên dưới chân nó |
| **Vòng lặp dài + tắt qua máy trạng thái của bên thứ ba** | ⛔ **NGUY** | Hàm `stop()` của họ có thể **im lặng không làm gì** khi trạng thái chưa đúng |

Dòng cuối là ca đã cắn thật. `AsyncScheduler.stop()` chỉ có tác dụng khi trạng thái đã là
`started`; gọi sớm hơn thì nó trả về y như đã dừng thành công, rồi bước dọn kế tiếp phá dịch vụ
dưới chân task chưa chạy.

## 3. Cách làm đúng

**Ưu tiên primitive của chính thư viện nếu nó có** - thường nó đã giải bài toán này rồi:

```python
await scheduler.start_in_background()   # chờ task_status.started(), task thành con của task group
```

Không có primitive như vậy thì **tự tạo ra sự phân biệt**: chờ một tín hiệu "đã chạy" trước khi
cho phép đường tắt chạy. Đừng dựa vào việc `create_task` được lập lịch "đủ nhanh".

## 4. Kiểm thử: mock KHÔNG bắt được loại lỗi này

Đây là lý do lỗi trên sống sót qua 1512 test.

> Với `AsyncMock`, `create_task(run_until_stopped())` và `start_in_background()` **trông giống hệt
> nhau** - cả hai chỉ là "một hàm được gọi". Khác biệt giữa chúng nằm ở **thứ tự thời gian thật**,
> mà mock thì không có thời gian.

**Bắt buộc:** mọi vòng lặp nền phải có ít nhất một test **không mock**, chạy thật, trong đó có ca
**start rồi stop ngay, không chèn `sleep`**.

⚠ Chèn `sleep` vào test là cách che chính xác lỗi mà test đó sinh ra để bắt. Đo thật lúc chẩn
đoán: `delay=0` đỏ · `delay=0.05` xanh · `delay=0.2` xanh.

> **Một lỗi biến mất khi chèn `sleep` thì gần như luôn là lỗi đua, không phải lỗi cấu hình.**

Khuôn tham chiếu: [`tests_temp/scheduler/test_runner_integration.py`](../../tests_temp/scheduler/test_runner_integration.py).

## 5. Liên quan

- [Luật 03 của workspace](../../../.claude/rules/03-mot-gia-tri-mot-nghia.md) - `stop()` trả về
  giống nhau cho hai tình huống bắt người gọi làm hai việc khác nhau. **Luật 03 áp cho cả hợp đồng
  của thư viện bên thứ ba ta gọi vào**, không chỉ hợp đồng ta viết ra: không sửa được API của họ
  thì nghĩa vụ chuyển sang bên gọi. (Mở rộng này do repo này đề xuất, leader đang đưa lên chủ dự án.)
- Bài học 0.7.0 ở [`../CLAUDE.md`](../CLAUDE.md): *viết ít nhất một test đi đúng con đường tài liệu
  hướng dẫn, không phải con đường tiện nhất cho test.* Mục 4 ở trên là dạng cụ thể của câu đó cho
  vòng lặp nền.
