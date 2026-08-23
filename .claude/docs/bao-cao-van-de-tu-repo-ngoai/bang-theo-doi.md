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
| **2** | Một dòng `INFO` khai trạng thái xác thực | `dental` mục 6b | ✨ Tính năng | ✅ **ĐÃ CODE + ĐÃ SỬA CHỮ** - bản đầu kết luận sai 100%, xem mục **7** |
| **7** | Dòng log ở mục 2 **kết luận SAI với 23/23 app** | `Service ngang` | 🟡 Lỗi | ✅ **ĐÃ VÁ** 2026-08-23, chờ commit |
| **3** | Cảnh báo khi app không có middleware nào | `dental` mục 6a | ✨ Tính năng | ⛔ **BÁC** |
| **4** | Nhận diện danh tính trên đường công khai | `linh-kien` mục 3 | ✨ Tính năng | ⛔⛔ **BÁC VĨNH VIỄN** |
| **5** | Sửa tài liệu *"`configure_jwt` chỉ verify 1 khoá"* | `linh-kien` mục 6 | 📄 Tài liệu | ➖ **KHÔNG PHẢI VIỆC CỦA FRAMEWORK** |
| **6** | Job scheduler chạy riêng **từng tiến trình** | chủ dự án hỏi | ❓ Câu hỏi | ⛔ **KHÔNG LÀM** - có lời giải, xem dưới |

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

## ⛔⛔ Mục 7: dòng log của chính mục 2 kết luận sai - hậu kiểm 2026-08-23

Phiên `Service ngang` báo về **ngay hôm sau** khi mục 2 được code. Họ đúng, và framework đo
lại xác nhận từng con số.

Câu cũ: `no JWT middleware - N HTTP route(s) open to anyone`. Nó đo **một** sự kiện
(`configure_jwt()` có được gọi không) rồi in ra **hai** kết luận không có bằng chứng.

| | Số repo |
|---|---|
| Cài xác thực bằng `configure_middleware` - câu cũ kết luận **SAI** | **23** |
| Dùng `configure_jwt` - câu cũ kết luận đúng | **0** |

⭐⭐ **Vì sao nặng hơn chuyện chữ nghĩa:** dòng log này **là** bản vá A1. *Một phép dò kêu
oan là một phép dò sẽ bị tắt* - khi cùng một câu xuất hiện dưới 23 ứng dụng khoẻ mạnh thì
ứng dụng thật sự fail-open in ra một dòng **không ai còn đọc**. Bản vá còn trong code nhưng
hết tác dụng với người đọc, tức đúng thứ nó sinh ra để chặn.

⚠ Và nó lặp lại đúng lý do framework đã dùng để **bác** phương án 6a (mục **3**) hôm trước.
Bác đúng, rồi tự dựng lại cùng cái bẫy ở chỗ khác.

**Chữ hiện tại khai thứ đo được, không kết luận** - số middleware được **in ra chứ không
diễn giải**, vì `configure_middleware` cũng là đường cài nén, log, request id. Hình dạng
fail-open thật là dòng *"no middleware installed"*, và nó tự nói ra.

⭐ Lần đầu phạm vi framework đo có **cả hai chiều**: rộng hơn báo cáo ở chỗ `no JWT
middleware` **cũng sai** chứ không chỉ `open to anyone` (nên sửa cả câu), hẹp hơn ở chỗ họ
đoán `socket` adapter dính - **không**, chỉ `web/_adapter.py` đọc `jwt_registry`.

**Đo:** `tests_temp/web/` **49 passed / 1 skipped**, bộ test dòng log **8 -> 14**. Hai đối
chứng: quay về chữ cũ -> **8 đỏ** · gộp middleware mọi server -> **1 đỏ**, đúng test canh
chuyện đó.

📌 Tài liệu cho phiên app: `docs/{vn,en}/starters.md` mục *"Dòng log khởi động về xác thực -
và điều nó KHÔNG nói"*.

## Bị bác - và vì sao, gọn một dòng

| # | Vì sao bác |
|---|---|
| **3** | Framework **không biết route nào đáng lẽ phải có xác thực**. Service công khai hoàn toàn là hợp lệ, nên cảnh báo sẽ kêu oan ở mọi lần khởi động - và *một phép dò kêu oan là một phép dò sẽ bị tắt*. Thay bằng việc **2**, cùng mục đích nhưng không có cửa kêu oan |
| **4** | **Một trang gọi máy chủ qua nhiều đường.** Phần riêng của người đăng nhập lấy từ một đường **có xác thực**; không cần nhét danh tính vào đường công khai. Ca sử dụng tự giải được bằng thứ đã có. ⛔ Chủ dự án dặn thẳng: ***"đừng app nào đề nghị nữa"*** |
| **5** | `docs/vn/starters.md` mục 177-206 **đã mô tả đầy đủ** `key_provider` + tra khoá theo `kid`. Chỗ lỗi thời nằm trong **comment của 19 repo app** - framework không sửa được file của người khác |

## ⛔ Câu hỏi 6: scheduler và đa tiến trình - hỏi một lần, trả lời một lần

Chủ dự án hỏi 2026-08-23. Ghi ở đây để **không phiên app nào phải hỏi lại**.

**Câu hỏi:** hẹn giờ hiện chỉ chạy ở một tiến trình. Có nghiệp vụ nào cần hẹn giờ riêng
cho từng tiến trình không? Nếu có thì là thiếu sót, hay giải được bằng liên lạc đa tiến trình?

**Trả lời: 0 ca nghiệp vụ**, và lý do là cấu trúc chứ không phải may mắn - nghiệp vụ chạm
dữ liệu của khách, mà dữ liệu của khách không bao giờ nằm riêng trong bộ nhớ một tiến trình
(luật 01 nghĩa 1 cấm đúng điều đó).

⭐ **Phép kiểm đưa cho phiên app khi họ hỏi:** *một job nghiệp vụ mà cần chạy riêng từng
tiến trình là một job đang phụ thuộc vào thứ chỉ tiến trình đó có - tức nó đã vi phạm luật
01 từ trước, và bản vá đúng không phải cho nó chạy N lần mà là đẩy trạng thái kia ra ngoài.*

Hai loại việc thật sự phải chạy theo tiến trình thì **đều ở ngoài scheduler**: quan trắc số
đo của chính tiến trình (gom qua `ProcessLink` rồi đẩy một lần - cụm chung socket nên không
gộp thì con số vô nghĩa) và thiết bị mà một tiến trình độc quyền giữ (adapter hạng `sharded`,
cơ chế `@poll`/`@on_change`).

**Không thêm gì vào API.** Đường thoát đã có và không tốn gì: adapter `scaling="replicated"`
với `serve()` là vòng lặp `sleep`. Thêm một trường phạm vi vào `IntervalJob` là mở một cửa
**hỏng im lặng** - khai nhầm cho một job gửi email là gửi bốn lần, không lỗi, không test đỏ.

Đầy đủ: [`.claude/CLAUDE.md`](../../CLAUDE.md) mục *"Vì sao scheduler KHÔNG chạy theo tiến
trình"* · tài liệu người dùng ở `docs/{vn,en}/starters.md` mục Scheduler.

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
