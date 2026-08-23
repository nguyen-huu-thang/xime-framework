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

## Báo cáo 2026-08-23 (2) - `Service ngang/kho`: con mồ côi vô hình, 401 lạnh máy, SIGTERM

Nguyên văn: [`kho-con-mo-coi-vo-hinh-va-401-lanh-may-2026-08-23.md`](kho-con-mo-coi-vo-hinh-va-401-lanh-may-2026-08-23.md).

| # | Họ báo | Của framework? | Xử lý |
|---|---|---|---|
| 1 | Con mồ côi vô hình với phép dò `app.main` và với `netstat` | ✅ **CÓ, và là gốc** | **ĐÃ VÁ** - con tự đi khi cha đi |
| 2 | 401 lạnh máy ấm theo **tiến trình**, cần 8 lần gọi | ⛔ **KHÔNG** - của app | Trả lời + chỉ đường; xem dưới |
| 3 | Con bị `-15` rồi dựng lại, họ **chưa quy được trách nhiệm** | ⚠ **Triệu chứng của #1** | **ĐÃ VÁ phần log**; và mã thoát đã quy được trách nhiệm |

### 1. Vá GỐC chứ không vá triệu chứng - và vì vậy KHÔNG làm thứ họ đề nghị

Đề nghị chính của họ là **cho con một dòng lệnh nhận ra được** (`--xime-process=api-2`).
**Không làm**, hai lý do:

- Nó là **tính năng**, không phải vá lỗi: thêm một bề mặt công khai mới ở bản alpha cuối,
  và dòng lệnh của con do `multiprocessing.spawn` sinh - đổi nó là vá vào ruột CPython,
  phụ thuộc phiên bản.
- Nó vá **triệu chứng**. Câu hỏi đúng không phải *"làm sao tìm con mồ côi"* mà là *"vì sao
  có con mồ côi"*. `_supervisor.py` đã khai đây là kết cục tệ nhất ngay trong docstring của
  chính nó, nhưng chỉ phòng thủ bằng **bắt tín hiệu** - che được cái chết lịch sự của cha,
  không che được `SIGKILL` / `-Force` / cha sập / OOM.

Nay con canh cha bằng `multiprocessing.parent_process()` (thư viện chuẩn, chạy trên cả hai
nền tảng), cha đi thì con đi. **Không còn con mồ côi thì không còn bài toán tìm nó.**

⭐ Ba đề nghị của họ vì vậy được giải quyết theo thứ tự ngược: (3) job object trên Windows -
không cần nữa; (2) ghi vào tài liệu - **có làm**, vì cụm chạy bản cũ vẫn còn ngoài kia; (1)
đổi dòng lệnh - không cần nữa.

### 2. 401 lạnh máy: của app, và framework đã có sẵn lời giải

Họ mô tả đúng hiện tượng, nhưng nguyên nhân nằm ở `config/jwt.py` của họ: bộ khoá verify
đang là **trạng thái riêng của từng tiến trình**. Framework đã có đường cho đúng chuyện này
từ 0.8.0, và nó xoá 401 lạnh máy **hoàn toàn**, không phải giảm bớt:

| Việc | Chỗ nó thuộc về |
|---|---|
| Primary lấy khoá **một lần cho cả cụm** | `run_once()` |
| Khoá nằm ở **bộ nhớ chung**, mọi tiến trình đọc | `RefData` |
| Làm tươi định kỳ | một job đơn nhất (`singleton`) |

⭐ **Điểm mấu chốt họ chưa biết: cha ĐỢI `run_once()` xong rồi mới sinh con tiếp theo**
(`_supervisor.py::run` - `_spawn(ordered[0])` -> `_await_run_once` -> mới tới các con còn
lại). Nên khoá đã nằm trong `RefData` **trước khi con thứ hai ra đời**: không con nào có
cửa sổ lạnh, kể cả con đầu. Con số *"8 lần gọi liên tiếp"* không phải một ngưỡng cần ghi
vào tài liệu - nó là **cái giá của việc chưa làm M5**.

Khuôn chép được: `Application Layer/saas-foundation/template` (đã vá 2026-08-23) và
`Base Platform/data` (repo đầu tiên đi hết M0-M6).

⛔ **Không nhận đề nghị "nạp khoá ở `post_construct`"**: `post_construct` chạy ở **mọi**
tiến trình, nên đó là N lời gọi mạng cho một thứ mà cả cụm dùng chung - đúng thứ `run_once`
sinh ra để thay thế.

### 3. `-15`: quy được trách nhiệm, và họ đã suy luận đúng hướng

Họ để ngỏ giữa *watchdog của framework* và *công cụ chạy lệnh của họ*, và nghiêng về vế thứ
hai vì *"nếu là tín hiệu cả nhóm thì supervisor cũng phải chết"*. Suy luận đó đúng, và mã
thoát chứng minh nó một cách độc lập:

**Trên Windows, `-15` KHÔNG thể đến từ một công cụ bên ngoài.** CPython
(`multiprocessing/popen_spawn_win32.py::wait`) đổi hằng `TERMINATE = 0x10000` thành
`-signal.SIGTERM`, mà `0x10000` chỉ do chính `multiprocessing` ghi. `taskkill /F` ghi `1`,
`Stop-Process -Force` ghi `0xFFFFFFFF`.

Còn ba chỗ giết con trong framework thì **đều log trước khi giết** (`CRITICAL` ở watchdog,
`ERROR` ở `_shutdown`), và nhánh `_shutdown` đặt `_stopping = True` nên câu in ra sẽ là
*"during shutdown"* chứ không phải *"restarting"*. Họ thấy `restarting` và không thấy dòng
nào trong hai loại đó.

> ⇒ Kẻ giết là **một tiến trình `multiprocessing` khác**, tức **một cụm cũ chưa tắt hẳn** -
> chính là mục 1. Hai mục họ báo riêng hoá ra là **một lỗi**.

**Đã vá phần log** theo đúng đề nghị của họ (và đề nghị đó rẻ, đúng, nên nhận nguyên):
dòng exit nay khai *ai giết*, không chỉ khai mã thoát. Lời khai bị xoá khi con được sinh
lại, kẻo lần chết sau bị gán lý do của lần trước.

### ⭐ Khuôn "phạm vi rộng hơn báo cáo" lặp lần thứ 5 - nhưng lần này theo chiều KHÁC

Bốn lần trước là *rộng hơn về số lượng* (2 adapter -> 3, 1 registry -> 2). Lần này là
**rộng hơn về tầng**: họ báo ba vấn đề rời nhau, đo lại thì mục 3 là **triệu chứng của mục
1**, và mục 1 không phải chuyện *phát hiện* mà là chuyện *ngăn chặn*.

📌 Và một chiều ngược, lần thứ hai có vế này: mục 2 **hẹp hơn** báo cáo - họ đề nghị sửa
tài liệu đa tiến trình, nhưng con số của họ đến từ một việc chưa làm trong repo của họ, nên
ghi nó vào tài liệu framework sẽ **dạy sai cho 20 repo còn lại**.

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
