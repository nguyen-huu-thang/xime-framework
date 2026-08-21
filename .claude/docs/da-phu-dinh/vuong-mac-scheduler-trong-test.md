# Vướng mắc từ `user-locator`: không viết được test dựng container khi repo có job nền

> | | |
> |---|---|
> | **Trạng thái** | ⛔ **BỊ PHỦ ĐỊNH** - chẩn đoán trong file này **SAI** |
> | **Viết ngày** | 2026-08-04, bởi phiên `user-locator` |
> | **Bị thay bởi** | [`../ghi-chep/loi-dua-scheduler.md`](../ghi-chep/loi-dua-scheduler.md), cùng ngày |
> | **Còn giá trị** | **mục 3** (ba cách đã thử) và **mục 6** (vì sao đáng làm) |

> ## ✅ ĐÃ GIẢI QUYẾT 2026-08-04 - và chẩn đoán trong file này SAI
>
> **Đọc [`../ghi-chep/loi-dua-scheduler.md`](../ghi-chep/loi-dua-scheduler.md) thay cho mục 2 và mục 5
> của file này.** Tóm tắt ba chỗ lệch:
>
> | File này nói | Sự thật đo được |
> |---|---|
> | `Application.start()` **không** khởi tạo scheduler | **Có** khởi tạo, đủ cả `post_construct` |
> | Chỉ ảnh hưởng việc **viết test**; "không repo nào đỏ cả" | Lỗi đua, nổ với **mọi Application sống ngắn**, tái hiện được bằng `asyncio.run()` thuần |
> | Cần framework **thêm API mới** tách dựng container khỏi vòng đời | **Không cần.** Là bug, đã vá. `user-locator` khôi phục hai test cũ nguyên trạng được |
>
> Phần vẫn còn giá trị: **mục 3** (ba cách đã thử - đúng, và không cách nào chạm nguyên nhân thật)
> và **mục 6** (vì sao đáng làm - lập luận vẫn đứng vững).

---

> Ghi ngày **2026-08-04** bởi **phiên leader** (workspace gốc `D:\code\xime`), theo yêu cầu chủ dự án.
> Người phát hiện: phiên `user-locator`. Họ đã tắt, nên tài liệu này thay cho việc hỏi lại họ.
>
> ⚠ **Đọc mục 5 trước khi ước lượng công việc** - phạm vi thật hẹp hơn nhiều so với bản báo cáo đầu tiên, và bản đầu đó đã bị chính người báo bác bỏ bằng số đo.

## 1. Hiện tượng

Repo `user-locator` thêm job nền đầu tiên (`CertRotationJob`). Ngay sau đó **mọi test gọi `Application.start()` đều chết**:

```text
RuntimeError: The scheduler has not been initialized yet.
```

## 2. Nguyên nhân, theo phân tích của người báo

`Application.start()` dựng DI container và chạy `post_construct`, **nhưng không khởi tạo scheduler** - việc đó chỉ nằm trên đường `run()`.

Hệ quả: **repo nào thêm job nền đầu tiên là loại test này đỏ**, và người viết sẽ tưởng mình cấu hình sai.

⚠ Đây là **phân tích của người báo, không phải kết luận của người giữ framework**. Việc đầu tiên nên làm là kiểm chứng lại nó trong mã framework thay vì tin.

## 3. Ba cách đã thử, đều KHÔNG qua

Ghi lại để người sửa không mất thời gian thử lại:

| # | Cách | Kết quả |
|---|---|---|
| 1 | `async with` thay cho cặp `start()` / `stop()` | không qua |
| 2 | `scheduler_registry.reset()` trong hàm dựng của test | không qua |
| 3 | reset ở **mức module**, trước mọi test | không qua |

Lý do chung người báo đưa ra: **framework dựng scheduler sớm hơn chỗ registry bị xoá.**

## 4. Đề nghị

> **Có cách tách "dựng container" khỏi "chạy vòng đời" không?**

Nếu có, `user-locator` khôi phục ngay hai test đã gỡ.

## 5. ⚠ Phạm vi THẬT - đo rồi, hẹp hơn bản báo cáo đầu

Bản báo cáo đầu tiên (11:26) viết *"giới hạn áp cho MỌI repo Xime"* và ngờ rằng `identity` và `data` "có thể đang có test đỏ mà đổ cho nguyên nhân khác". Leader yêu cầu đo trước khi chuyển đi. **Người báo tự đo và tự bác mình hai lần** (11:30):

| Repo | Có `config/scheduler.py`? | Gọi `Application()` trong test? |
|---|---|---|
| `data` | có | **0 file** (trên 49 file test) |
| `placement` | có | **0 file** |
| `notification` | có | **0 file** |
| `user-locator` | có | **có** |
| `identity` | - | **KHÔNG ÁP DỤNG** - đây là repo **Java** |

Hai chỗ sai của bản đầu:

1. **`identity` là repo Java.** `Application.start()` là API của Xime Framework, **chỉ dành cho Python**. Nó không thể chạm tới họ.
2. **Ba repo Python kia có job nền nhưng không repo nào dựng container trong test**, nên giới hạn này không chạm ai trong số họ.

> **Sự thật: hiện chỉ `user-locator` dính**, vì đó là repo duy nhất viết test dựng thật container.

**Đừng đọc tài liệu này thành "nhiều repo đang đỏ" - không repo nào đỏ cả.**

## 6. Vì sao vẫn đáng làm, dù chỉ một repo dính

Điểm này quan trọng hơn con số, và nó là lập luận của chính người báo sau khi đo:

> Framework **chưa hỗ trợ** một việc đáng lẽ nên có - **kiểm nối dây bằng test** - và hôm nay đúng một repo cần tới nó.

Trong một ngày, `user-locator` vấp **ba lần** cùng một khuôn *"viết ra rồi không ai nối vào"*:

| # | Thứ tồn tại | Ai gọi |
|---|---|---|
| 1 | handler gRPC | quên khai `bindings` -> `UNIMPLEMENTED` |
| 2 | package handler | `packages` khai một bên, `dependency.scan` bên kia |
| 3 | `CertRotationJob` | **không ai** - job xoay cert chưa từng chạy |

**Test dựng container chính là loại test bắt được nhóm lỗi đó.** Framework không cho viết test kiểu ấy nghĩa là mọi repo Python phải phát hiện nhóm này **bằng cách vấp phải nó**.

Ba repo Python kia không đỏ **không phải vì họ sạch** - mà vì họ không có loại test đó, nên nhóm lỗi này ở chỗ họ **chưa ai nhìn**.

⚠ Ca thứ 3 đáng chú ý riêng: nó **hỏng muộn**. Job xoay cert không chạy thì hôm nay không đau; ngày cert hết hạn thì bắt tay TLS hỏng hết, và nguyên nhân là **một dòng đăng ký chưa bao giờ tồn tại**. Nó được phát hiện chỉ vì phiên `identity` soi bằng mắt sau khi trình quét báo "0 tín hiệu".

## 7. Người báo đã làm gì với phần của họ

Gỡ hai test, **kèm ghi chú đầy đủ ngay trong file** (gồm cả ba cách đã thử ở mục 3), và nói rõ:

- **Cái mất:** *"container dựng được"* và *"index là một thể hiện dùng chung"* nay không còn được canh bằng test.
- **Cái còn:** mỗi lần chạy service thật vẫn chứng minh chúng, vì thiếu binding là **chết lúc khởi động**.

Nên đây là nợ **có kế toán**, không phải test bị xoá cho xanh.

## 8. Trạng thái khi ghi tài liệu này

`user-locator` đã có cert mTLS thật (shard `UL0000`, DB `user_locator_service`), và `CertRotationJob` **đã được đăng ký, chạy xong ngay lượt đầu, có test canh**. Vướng mắc ở tài liệu này **không chặn họ** - nó chỉ làm mất hai test.
