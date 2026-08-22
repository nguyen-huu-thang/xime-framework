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
| **1** | `public_paths` khớp được **tiền tố** | `linh-kien` mục 2 | ✨ Tính năng | 🔨 **DUYỆT, CHƯA CODE** |
| **2** | Một dòng `INFO` khai trạng thái xác thực | `dental` mục 6b | ✨ Tính năng | 🔨 **DUYỆT, CHƯA CODE** |
| **3** | Cảnh báo khi app không có middleware nào | `dental` mục 6a | ✨ Tính năng | ⛔ **BÁC** |
| **4** | Nhận diện danh tính trên đường công khai | `linh-kien` mục 3 | ✨ Tính năng | ⛔⛔ **BÁC VĨNH VIỄN** |
| **5** | Sửa tài liệu *"`configure_jwt` chỉ verify 1 khoá"* | `linh-kien` mục 6 | 📄 Tài liệu | ➖ **KHÔNG PHẢI VIỆC CỦA FRAMEWORK** |

## Còn treo - đúng hai việc

| # | Việc | Ràng buộc phải nhớ khi code |
|---|---|---|
| **1** | `configure_jwt(public_paths=["/api/v1/parts/*"])` | ⛔ **Không `startswith` trần** - `/api/v1/parts/*` khớp `/api/v1/partsecret` là một lớp lỗ hổng, hỏng theo chiều **chặt sang lỏng**. Khớp theo **đoạn đường dẫn**.<br>⚠ Là **ĐỔI HÀNH VI**, không phải thuần cộng thêm - ký tự `*` trong đường dẫn đang có sẽ đổi nghĩa.<br>⚠ **Test đi thành cặp**: đường trong tiền tố phải MỞ **và** đường chỉ *giống* tiền tố phải ĐÓNG |
| **2** | Một dòng `INFO` lúc khởi động khai app có xác thực hay không | Không cấu hình, không cờ, không tên công khai mới. Chỉ in ra thứ framework vốn đã biết |

**Cách giao:** hai commit **riêng**, mỗi việc xong thì dừng và báo - theo cách chủ dự án
dặn 2026-08-22 (*"vá dần dần, nhiều lần commit vá, rồi commit `v0.8.2` sau cùng"*).

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
