# Lỗi đua khi tắt scheduler - chẩn đoán, bản vá, và phạm vi thật

> Ghi ngày **2026-08-04** bởi **phiên framework**. Trả lời vướng mắc do `user-locator` nêu ở
> [`../da-phu-dinh/vuong-mac-scheduler-trong-test.md`](../da-phu-dinh/vuong-mac-scheduler-trong-test.md).
>
> ⚠ **Tài liệu đó mô tả đúng triệu chứng nhưng sai nguyên nhân, và ước phạm vi hẹp hơn thực tế.**
> File này thay thế phần chẩn đoán của nó. Giữ nguyên giá trị: mục 3 (ba cách đã thử) và mục 6
> (vì sao đáng làm) vẫn đúng.

## 1. Tóm tắt cho người vội

| | |
|---|---|
| **Triệu chứng** | `RuntimeError: The scheduler has not been initialized yet.` khi ứng dụng có job nền |
| **Nguyên nhân** | `post_construct` phóng vòng lặp scheduler bằng `asyncio.create_task()` rồi trả về **trước khi vòng lặp kịp chạy**. Tắt nhanh -> `stop()` im lặng không làm gì -> `__aexit__` dọn dịch vụ dưới chân task chưa khởi động |
| **Phạm vi** | **Mọi tiến trình Xime có job nền** mà `start` và `stop` cách nhau đủ gần. KHÔNG giới hạn ở test, KHÔNG dính pytest |
| **Bản vá** | Dùng `AsyncScheduler.start_in_background()` - primitive của chính APScheduler, chỉ trả về khi vòng lặp đã báo `started` |
| **Cần app làm gì** | Không gì cả. Framework cài editable nên bản vá có hiệu lực ngay |
| **Có phải nâng dependency?** | Không. `start_in_background` có sẵn từ `apscheduler>=4.0.0a6`, đúng bằng floor đang khai |

## 2. Chẩn đoán sai ở đâu, và vì sao nó sai một cách hợp lý

Bản báo cáo viết:

> `Application.start()` dựng DI container và chạy `post_construct`, **nhưng không khởi tạo
> scheduler** - việc đó chỉ nằm trên đường `run()`.

Vế đầu đúng, vế sau sai. Đọc mã:

- [`core/bootstrap/orchestrator.py`](../../xime/core/bootstrap/orchestrator.py) dòng 95 -
  `instances.extend(self._build_framework_components(...))`, trong đó có `_try_build_scheduler`.
- Ngay sau đó `LifecycleManager.start()` gọi `post_construct()` của `SchedulerRunner`.

Nên `Application.start()` **có** khởi tạo scheduler, đầy đủ. Không có gì nằm riêng trên đường `run()`.

Vì sao suy đoán đó nghe hợp lý: thông báo lỗi nói *"chưa khởi tạo"*, nên hướng tìm tự nhiên là đi
tìm chỗ đáng lẽ phải khởi tạo mà không thấy gọi. **Thông báo lỗi trỏ sai chỗ** - sự thật là đã khởi
tạo rồi bị dọn mất, chứ không phải chưa khởi tạo. Đó cũng là lý do cả ba cách chữa quanh
`scheduler_registry` (mục 3 của bản báo cáo) đều trượt: không cách nào chạm tới nguyên nhân.

## 3. Cơ chế thật, theo đúng thứ tự thời gian

Mã cũ, cuối `SchedulerRunner.post_construct()`:

```python
self._task = asyncio.create_task(self._scheduler.run_until_stopped())
```

`create_task` **xếp hàng** một coroutine rồi trả về ngay; chưa dòng nào của nó chạy. Nếu tắt trước
khi vòng chạy sự kiện kịp lập lịch cho task đó, `pre_destroy` diễn ra thế này:

| # | Lời gọi | Chuyện thật xảy ra |
|---|---|---|
| 1 | `await scheduler.stop()` | **Không làm gì.** Thân hàm là `if self._state is RunState.started and ...`, mà trạng thái vẫn còn `stopped` |
| 2 | `await scheduler.__aexit__(...)` | Dọn event broker + data store, đóng task group, đặt `_services_initialized = False` |
| 3 | `await self._task` | Tới đây `run_until_stopped` **mới** chạy, thấy dịch vụ đã bị dọn -> ném |

### Bằng chứng bằng số đo, không phải suy luận

Cùng một ứng dụng, chỉ chèn thêm `sleep` giữa `start` và `stop`:

```text
delay=0     FAIL -> RuntimeError: This task group is not active
                  | RuntimeError: The scheduler has not been initialized yet
delay=0.05  OK
delay=0.2   OK
```

> **Một lỗi biến mất khi chèn `sleep` thì gần như luôn là lỗi đua, không phải lỗi cấu hình.**
> Đây là dấu hiệu đáng nhớ cho lần sau.

## 4. ⚠ Phạm vi thật: rộng hơn "không viết được test"

Bản báo cáo kết luận (in đậm trong bản gốc):

> *"Đừng đọc tài liệu này thành nhiều repo đang đỏ - không repo nào đỏ cả."*

Câu đó **đúng với thứ đã được đo**, nhưng thứ được đo là *"repo nào gọi `Application()` trong test"*
- một phép đo về **biểu hiện**, không phải về **điều kiện gây lỗi**.

Đối chứng: chạy bằng `asyncio.run()`, không pytest, không pytest-asyncio, không fixture - đúng
đường production đi:

```python
async def main():
    app = Application(config_module="app.config.dependency")
    await app.start()
    await app.stop()

asyncio.run(main())     # -> FAIL trước bản vá
```

Nó đỏ. Nên phát biểu đúng là:

> **Mọi tiến trình Xime có job nền, nếu `start` rồi `stop` cách nhau đủ gần, đều gãy lúc tắt.**

`data`, `notification`, `placement` không thấy lỗi **không phải vì họ sạch** - mà vì service thật
sống hàng giờ giữa `start` và `stop`, nên khoảng đua bị lấp. Họ vẫn nằm trong phạm vi, chỉ là ở
những đường ít ai nhìn: tắt máy nhanh, khởi động thất bại rồi dọn ngược, `KeyboardInterrupt` sớm.
Triệu chứng sẽ là traceback lúc **shutdown** - chỗ người ta hay lướt qua vì "đằng nào cũng đang tắt".

Đây đúng khuôn nhóm đúc kết hôm nay: **phép dò hẹp hơn kết luận**. Người báo đo chính xác thứ họ đo,
và tự bác mình hai lần - việc làm tốt. Nhưng họ đo từ chỗ họ đứng, mà chỗ đó không nhìn được vào
framework. Đó chính là lý do repo này cần có người giữ.

## 5. Bản vá

```python
# Hand the scheduler loop to APScheduler's own supervised task group and WAIT
# until it reports started.
await self._scheduler.start_in_background()
```

`start_in_background()` gọi `self._services_task_group.start(self.run_until_stopped, ...)`. Theo
ngữ nghĩa anyio, `task_group.start()` **chờ tới khi task gọi `task_status.started()`**, mà
`run_until_stopped` chỉ gọi hàm đó **sau khi** đã đặt `_state = RunState.started`. Nên tới lượt
`stop()` thì trạng thái chắc chắn đúng, không còn cửa im lặng bỏ qua.

Kèm hai hệ quả tốt:

- Task thành **con của task group nội bộ APScheduler**, nên `__aexit__` đợi nó dọn xong đúng cách.
  Ta không cần tự giữ `self._task` nữa - thuộc tính đó đã bỏ.
- `except Exception` ở nhánh dọn đổi thành `except BaseException`, để `CancelledError` (không phải
  `Exception` từ Python 3.8) cũng giải phóng tài nguyên APScheduler thay vì rò.

## 6. Vì sao 1512 test không bắt được - phần đáng lo nhất

Toàn bộ `tests_temp/scheduler/test_runner.py` chạy trên `AsyncMock`. Chúng canh được *"runner có gọi
đúng hàm không"*, nhưng **chưa test nào từng chạy một `AsyncScheduler` thật bên trong một
`Application` thật**.

Với mock thì `create_task(run_until_stopped())` và `start_in_background()` **trông giống hệt nhau** -
cả hai chỉ là "một hàm được gọi". Khác biệt giữa chúng nằm ở *thứ tự thời gian thật*, mà mock thì
không có thời gian.

Đây đúng bài học đã ghi trong `.claude/CLAUDE.md` từ đợt kiểm toán 0.7.0:

> *"với mỗi tính năng, viết ít nhất một test đi đúng con đường tài liệu hướng dẫn, không phải con
> đường tiện nhất cho test"*

Bài học có sẵn, in đậm, và mảng scheduler vẫn lọt. Ghi lại ở đây để lần sau đọc thấy **ví dụ**, chứ
không chỉ thấy câu khẩu hiệu.

### Test canh mới

`tests_temp/scheduler/test_runner_integration.py` - Application thật, scheduler thật, không mock:

| Test | Canh điều gì |
|---|---|
| `test_start_then_immediate_stop_does_not_raise` | Ca tái hiện gốc. **Không được thêm `sleep`** vào test này - chính khoảng nghỉ đó che lỗi đi |
| `test_container_is_usable_while_scheduler_runs` | Đúng thứ `user-locator` cần: dựng container để kiểm nối dây |
| `test_start_stop_twice_in_one_process` | `scheduler_registry` là biến toàn cục; canh khuôn "xanh lần đầu, đỏ lần hai" |
| `test_plain_asyncio_run_without_pytest_asyncio` | Đối chứng phạm vi: lỗi không dính pytest |

Thêm ở `test_runner.py`: `test_does_not_spawn_its_own_task` chặn thẳng `run_until_stopped` để không
ai vô tình quay lại `create_task`.

✅ **Đối chứng ngược đã chạy:** `git checkout` bản cũ rồi chạy 4 test mới -> **cả 4 đỏ**, đúng thông
báo lỗi `user-locator` báo. Test xanh không tự chứng minh mình biết kêu.

## 7. Một ca luật 03 nằm trong thư viện ngoài

`AsyncScheduler.stop()` trả về **y hệt nhau** trong hai tình huống bắt người gọi làm hai việc khác nhau:

| Tình huống | `stop()` làm gì | Người gọi đáng lẽ phải |
|---|---|---|
| Vòng lặp **đang chạy** | ra hiệu dừng thật | đợi nó dọn xong |
| Vòng lặp **chưa chạy** | **không làm gì** | đợi nó khởi động xong đã, rồi mới dừng |

Không giá trị trả về, không cảnh báo, không log. Đúng **dấu hiệu 3** của
[luật 03](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md): *trạng thái tạm thời (đang khởi động)
trả về giống hệt kết luận vĩnh viễn (đã dừng)*.

Điểm tổng quát hơn ca này, đã đề xuất lên leader:

> **Luật 03 áp cho cả hợp đồng của thư viện bên thứ ba mà ta gọi vào, không chỉ hợp đồng ta viết
> ra.** Ta không sửa được API của họ, nên nghĩa vụ chuyển thành: chỗ nào gọi một hàm mà *"không làm
> gì"* và *"làm rồi"* trông giống nhau, **bên gọi phải tự tạo ra sự phân biệt** - ở đây là chờ trạng
> thái `started` trước khi có quyền gọi `stop()`.

## 8. Đã rà các adapter khác, và ranh giới để phân biệt

Quét mọi `create_task` / `TaskGroup` trong `xime/`. **Không tìm thấy ca thứ hai** - nhưng con số 0
này chỉ đáng tin kèm lý do, nên đây là ranh giới:

| Hình dạng | Có dính không | Vì sao |
|---|---|---|
| Vòng lặp dài, tắt bằng `task.cancel()` (`socket/_adapter.py` reaper, `socket/_client.py` read loop) | **Không** | `cancel()` hợp lệ trên task chưa từng chạy - không phụ thuộc trạng thái |
| Task một-việc-một-lần cho từng message/request (mqtt, modbus, opcua, `_service_builder`) | **Không** | Không có đường tắt nào giả định chúng đã khởi động |
| `grpc/client/_channel.py::_retire` | **Không** | Giữ strong-ref + `add_done_callback`, không ai dọn tài nguyên dưới chân nó |
| **Vòng lặp dài + tắt qua một máy trạng thái của bên thứ ba** | **CÓ** | Chỉ có scheduler. `stop()` của họ phụ thuộc trạng thái, mà ta không đợi trạng thái đó |

> Điều kiện gây lỗi không phải `create_task`, mà là **`create_task` cộng với một đường tắt giả định
> task đã khởi động**. Ai thêm vòng lặp nền mới thì đối chiếu dòng cuối của bảng.

⚠ Nói cho đúng mức: đây là **"không thấy"**, không phải **"không có"**. Phép quét của tôi hẹp bằng
danh sách tín hiệu tôi nghĩ ra được (`create_task`, `ensure_future`, `TaskGroup`), và một cơ chế
phóng task mà tôi chưa nghĩ tới thì cũng không có trong danh sách đó.

## 9. Bằng chứng

```bash
pytest tests_temp/scheduler/     # 62 passed (58 cũ + 4 mới)
pytest tests_temp/               # 1516 passed, 7 skipped
```

Mã đã sửa: [`xime/starters/scheduler/_runner.py`](../../xime/starters/scheduler/_runner.py).
