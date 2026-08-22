# Bảng theo dõi: repo ngoài đề nghị gì, kết cục ra sao

> Cập nhật 2026-08-22. Nguồn: [ba báo cáo gốc](README.md) · [phần trả lời](tra-loi-2026-08-22.md).
>
> Bảng này trả lời đúng một câu: **cái nào xong, cái nào bác, cái nào còn treo.**
> Lý do và phép đo thì nằm ở hai file trên - đừng chép lại vào đây.

## Toàn cảnh

| # | Đề nghị | Ai báo | Loại | Kết cục |
|---|---|---|---|---|
| **C6** | gRPC tụt xuống PLAINTEXT khi di trú sang `process:` | `data` | 🔴 Lỗi | ✅ **ĐÃ VÁ** - `0.8.0`, đợt 6 |
| **C7** | Không adapter nào có mốc dương trong log | `data` | 🟡 Lỗi | ✅ **ĐÃ VÁ** - `0.8.0`, đợt 6 |
| **C8** | `xime check config` tố oan khoá hợp lệ | ví dụ gRPC+Socket | 🟡 Lỗi | ✅ **ĐÃ VÁ + COMMIT** `07de5a2` |
| **C9** | Gợi ý lỗi thiếu đăng ký dẫn sai đường | `dental` mục 7 | 🟢 Lỗi | ✅ **ĐÃ VÁ + COMMIT** `07de5a2` |
| **1** | `public_paths` khớp được **tiền tố** | `linh-kien` mục 2 | ✨ Tính năng | ✅ **ĐÃ CODE** 2026-08-22, chờ commit |
| **2** | Một dòng `INFO` khai trạng thái xác thực | `dental` mục 6b | ✨ Tính năng | ✅ **ĐÃ CODE** 2026-08-22, chờ commit |
| **3** | Cảnh báo khi app không có middleware nào | `dental` mục 6a | ✨ Tính năng | ⛔ **BÁC** |
| **4** | Nhận diện danh tính trên đường công khai | `linh-kien` mục 3 | ✨ Tính năng | ⛔⛔ **BÁC VĨNH VIỄN** |
| **5** | Sửa tài liệu *"`configure_jwt` chỉ verify 1 khoá"* | `linh-kien` mục 6 | 📄 Tài liệu | ➖ **KHÔNG PHẢI VIỆC CỦA FRAMEWORK** |

## Đã code 2026-08-22 - hai việc còn treo nay hết treo

| # | Việc | Điều đáng nhớ khi đọc lại |
|---|---|---|
| **1** | `configure_jwt(public_paths=["/api/v1/parts/*"])` | Khớp theo **đoạn đường dẫn**, nên không bao giờ chạm `/api/v1/partsecret`. Dấu `*` ở vị trí khác là **lỗi lúc khởi động**, không bị bỏ qua.<br>⭐ **Ba chỗ khác cũng đọc `public_paths`** và mỗi chỗ từng tự chép luật khớp - registrar WebSocket, trình dựng OpenAPI, phép thêm đường sức khoẻ. Nay cả ba gọi **cùng một hàm**. Vá mỗi middleware là dựng lại đúng lỗi C8 |
| **2** | Dòng `INFO` khai trạng thái xác thực lúc khởi động | Phát ra trong `lifespan` (sau khi route đăng ký xong), đếm **bề mặt API của app** chứ không đếm route hạ tầng. Là `INFO` có chủ ý - cảnh báo thì kêu oan với mọi service công khai hợp lệ |

**Đo:** `2571 passed / 24 skipped / 0 failed = tổng 2595` (`2564 + 31` test mới) ·
`ruff check xime/` sạch · `mypy` **49 lỗi trước và sau, không thêm cái nào**.

⭐⭐ **Một lỗ hổng test do đối chứng tìm ra, đáng nhớ hơn hai tính năng:** bản test đầu của
việc 2 gọi thẳng `_log_auth_state`, nên **xoá lời gọi trong `lifespan` thì 0 test đỏ** -
nó canh **hàm**, không canh **việc hàm được gọi**. Cùng khuôn đã trả giá ở đợt uvloop
`0.8.1`. Đã vá bằng một test dựng app thật rồi chạy `lifespan`.

## Bị bác - và vì sao, gọn một dòng

| # | Vì sao bác |
|---|---|
| **3** | Framework **không biết route nào đáng lẽ phải có xác thực**. Service công khai hoàn toàn là hợp lệ, nên cảnh báo sẽ kêu oan ở mọi lần khởi động - và *một phép dò kêu oan là một phép dò sẽ bị tắt*. Thay bằng việc **2**, cùng mục đích nhưng không có cửa kêu oan |
| **4** | **Một trang gọi máy chủ qua nhiều đường.** Phần riêng của người đăng nhập lấy từ một đường **có xác thực**; không cần nhét danh tính vào đường công khai. Ca sử dụng tự giải được bằng thứ đã có. ⛔ Chủ dự án dặn thẳng: ***"đừng app nào đề nghị nữa"*** |
| **5** | `docs/vn/starters.md` mục 177-206 **đã mô tả đầy đủ** `key_provider` + tra khoá theo `kid`. Chỗ lỗi thời nằm trong **comment của 19 repo app** - framework không sửa được file của người khác |

## ⭐ Một khuôn lặp lại, 4/4 lần, không ngoại lệ

**Framework đo lại thì phạm vi luôn RỘNG HƠN báo cáo:**

| Báo cáo nói | Đo lại ra |
|---|---|
| web kế thừa TLS, gRPC thì không (**2** adapter) | **3** adapter - `socket` cũng kế thừa |
| gRPC thiếu dòng log (**1** adapter) | **3** - `web` có log nhưng không nói chế độ TLS, `socket` không log gì |
| `check config` tố oan khối `socket` (**1** khối, **2** khoá) | **2** khối, **4** khoá - và `socket` còn sai **chiều ngược lại** (khai `socket.path` mà không đường nào đọc) |
| gợi ý lỗi dẫn sai cho `RefData` (**1** registry) | **2** registry - `RefData` **và** handler `ProcessLink` |

📌 **Hệ quả cho quy trình:** nhận một báo cáo thì việc đầu tiên là **tự quét lại toàn bộ
lớp đó**, không phải sửa đúng chỗ được nêu.
