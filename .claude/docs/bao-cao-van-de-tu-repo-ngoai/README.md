# Vấn đề do repo NGOÀI báo về framework

Thư mục này giữ **báo cáo gốc**, nguyên văn, do phiên giữ một repo khác viết. Nó
khác `kiem-toan/` ở nguồn: `kiem-toan/` là framework **tự soi**, còn đây là thứ
người **dùng** framework va phải khi chạy thật.

⭐ Giữ nguyên văn thay vì tóm tắt lại, vì hai lý do: người trong repo đo đúng hơn
người đứng ngoài (họ có cấu hình thật, tải thật, cert thật), và **phần "tôi đo
được tới đâu"** ở cuối mỗi báo cáo là thứ một bản tóm tắt luôn làm rơi mất.

## Trạng thái

> ⭐ **Muốn nhìn nhanh cái nào xong / bác / còn treo: [`bang-theo-doi.md`](bang-theo-doi.md).**
> Bảng dưới đây là sổ chi tiết theo từng báo cáo; bảng kia gộp theo từng đề nghị.

| Báo cáo | Ngày | Trạng thái |
|---|---|---|
| [gRPC tụt xuống PLAINTEXT khi đổi sang `process:`](data-service-grpc-tls-roi-khi-doi-sang-process-2026-08-21.md) | 2026-08-21 | ✅ **ĐÃ VÁ** - C6, đợt 6 |
| [gRPC không báo mình đã lên](data-service-grpc-khong-bao-minh-da-len-2026-08-21.md) | 2026-08-21 | ✅ **ĐÃ VÁ** - C7, đợt 6 |
| [`xime check config` báo oan `socket.dir` / `socket.session_timeout`](vi-du-grpc-socket-check-config-socket-thieu-khoa-2026-08-22.md) | 2026-08-22 | ✅ **ĐÃ ĐỌC · ĐÃ VÁ** - C8. Phạm vi thật **rộng gấp đôi**: `lmdb` cũng dính, và `socket` còn **thừa** một khoá phantom |
| [`configure_jwt` không repo nào dùng, và hai chỗ chặn 2 repo di trú về](linh-kien-jwt-middleware-khong-ai-dung-2026-08-22.md) | 2026-08-22 | ✅ **ĐÃ ĐỌC · CHỦ DỰ ÁN ĐÃ QUYẾT** - hai điểm kỹ thuật đã **đo lại và xác nhận đúng**. Mục A (khớp tiền tố) ✅ **DUYỆT**. Mục B (nhận diện trên đường công khai) ⛔ **BÁC VĨNH VIỄN** - chủ dự án dặn *"đừng app nào đề nghị nữa"*. Xem [phần trả lời](tra-loi-2026-08-22.md) mục 5 |
| [Route WebSocket không xác thực thì kêu, route HTTP thì im](dental-http-khong-jwt-thi-im-lang-2026-08-22.md) | 2026-08-22 | ✅ **ĐÃ ĐỌC** · mục 7 **ĐÃ VÁ** (C9, phạm vi rộng hơn: **hai** registry) · mục 6 ✅ **DUYỆT phương án (b)** (một dòng `INFO` khai trạng thái xác thực), **bác (a)**. Xem [phần trả lời](tra-loi-2026-08-22.md) mục 6 |
| [Dòng log trạng thái xác thực kết luận SAI với 23/23 app](service-ngang-log-xac-thuc-ket-luan-sai-2026-08-23.md) | 2026-08-23 | ✅ **ĐÃ ĐỌC · ĐO LẠI XÁC NHẬN ĐÚNG · ĐÃ VÁ + COMMIT** `d1328e2` - hậu kiểm của phương án (b) vừa ship. `open to anyone` là **kết luận** mà phép đo phía sau không đỡ nổi: sai **100% số lần in ra** (23 repo dùng `configure_middleware`, 0 repo dùng `configure_jwt`). Đề nghị **chỉ sửa chữ**, giữ dòng log và giữ mức INFO. ⭐ Framework đo lại: con số 23/0 **đúng**, và phạm vi **rộng hơn báo cáo** - `no JWT middleware` cũng sai chữ, không chỉ `open to anyone` |
| [Con mồ côi VÔ HÌNH với phép dò quen thuộc, và 401 lạnh máy đếm theo TIẾN TRÌNH](kho-con-mo-coi-vo-hinh-va-401-lanh-may-2026-08-23.md) | 2026-08-23 | ✅ **ĐÃ ĐỌC · ĐÃ VÁ + COMMIT** `548c731`. **Mục 1 = lỗi framework, và là GỐC** - `_supervisor.py` khai con mồ côi là kết cục tệ nhất nhưng chỉ phòng thủ bằng *bắt tín hiệu*, nên `SIGKILL`/`-Force`/cha sập/OOM đều lọt. Nay **con tự canh cha** bằng `multiprocessing.parent_process()` (thư viện chuẩn, cả hai nền tảng) - đo thật trên cụm 3 tiến trình: `-Force` lên cha thì cả ba con thoát, cổng được trả. ⛔ **KHÔNG** làm thứ họ đề nghị chính (thêm `--xime-process=` vào dòng lệnh): đó là tính năng, và nó vá **triệu chứng** - không còn con mồ côi thì không còn bài toán tìm nó. **Mục 3 hoá ra là triệu chứng của mục 1**: trên Windows `-15` **không thể** đến từ công cụ ngoài (CPython đổi `TERMINATE = 0x10000` thành `-SIGTERM`; `taskkill /F` ghi 1, `Stop-Process -Force` ghi `0xFFFFFFFF`), nên nó là bằng chứng một **cụm cũ chưa tắt hẳn**; log nay khai *ai giết*. ⛔ **Mục 2 KHÔNG phải lỗi framework** - `run_once` + `RefData` đã giải trọn, và cha **đợi `run_once` xong mới sinh con tiếp theo** nên không con nào có cửa sổ lạnh; con số *8 lần* là giá của việc chưa làm M5 |
| [`public_health_paths()` không export, `/healthz` của middleware tự viết trả 401](nha-tro-public-health-paths-khong-export-2026-08-25.md) | 2026-08-25 | ✅ **ĐÃ ĐỌC · ĐO LẠI XÁC NHẬN ĐÚNG · ĐÃ VÁ** 2026-08-25 - hàm có từ `0.8.0`, docstring tự khai *"middleware JWT cho chúng đi qua"*, nhưng **thiếu ở `__all__`**. ⭐ Đo lại thì phạm vi rộng hơn, và lần này nó **LẬT lý do phản đối** chứ không chỉ nới con số: báo cáo lo *export nó là hợp thức hoá middleware JWT tự viết*, nhưng `admin` dùng nó cho **hàng rào IP** - chỗ dùng không dính gì tới JWT và **không biến mất** khi chuyển sang `configure_jwt`. Nên đường *"không export, sửa docstring thành chi tiết nội bộ"* sẽ ghi một **câu sai**. **8 repo** đang gọi nó từ `._health` trong **code sản phẩm**, và đó là lời import riêng tư **duy nhất** ngoài thư mục `test/` của cả 28 repo. Đã export + viết lại docstring (thêm hai thứ chưa tài liệu nào nói: dùng `configure_jwt` thì **đừng** gọi · phải gọi **sau** `configure_health()`, gọi sớm nhận tuple rỗng và hàng rào chặn mất `/healthz` **không một lời báo**) + 5 test canh. 📌 Mục 4 của báo cáo **tự lỗi thời trong ngày**: `nha-tro` đã chuyển sang `configure_jwt` sáng cùng ngày nên dòng lách của họ đã biến mất - người báo là repo duy nhất **đã thoát**, 8 repo họ không đo thì vẫn kẹt |

Chi tiết bản vá, phép đo hai chiều và test canh:
[`../kiem-toan/0.8-kiem-toan-toan-dien.md`](../kiem-toan/0.8-kiem-toan-toan-dien.md)
mục **ĐỢT 6**.

## ⭐ Khuôn lặp lại: framework đo lại thì phạm vi RỘNG HƠN báo cáo, MỌI LẦN

Đây là quan sát đáng giá nhất của cả thư mục, và tới 2026-08-25 nó đúng **7/7
lần** - không có ngoại lệ nào:

| Báo cáo nói | Đo lại ra |
|---|---|
| web kế thừa TLS, gRPC thì không (**2** adapter) | **3** adapter, `socket` cũng kế thừa. gRPC là cái duy nhất lệch - tức là **sót**, không phải lựa chọn thiết kế |
| gRPC thiếu dòng log (**1** adapter) | `web` có log nhưng **không nói chế độ TLS**, `socket` **không log gì**. Bản vá áp cho cả ba |
| `check config` tố oan khối `socket` (**1** khối, **2** khoá) | **2** khối - `lmdb` cũng thiếu `file_mode`/`dir_mode`. Và `socket` còn sai **chiều ngược lại**: khai `socket.path` mà **không đường nào đọc**. Đo trên YAML của chính người báo: **4** lỗi, không phải 2 |
| gợi ý lỗi dẫn sai đường cho `RefData` (**1** registry) | **2** registry nằm ngoài `scan()` - `RefData` và handler `ProcessLink` |
| `open to anyone` sai chữ (**1** vế) | **cả câu** sai - `no JWT middleware` cũng sai với người cài middleware JWT của chính họ |
| `public_health_paths` thiếu export, **1** repo lách (`nha-tro`) | **8** repo lách, trong **code sản phẩm**. Và người báo là repo duy nhất **đã thoát** - phạm vi họ đo là phạm vi họ vừa rời khỏi |

📌 **Hệ quả cho quy trình, không phải cho bốn lỗi này:** nhận một báo cáo thì việc
đầu tiên là **tự quét lại toàn bộ lớp đó**, không phải sửa đúng chỗ được nêu. Người
báo đo trong phạm vi họ **chạm tới**, và phạm vi đó luôn hẹp hơn framework - không
phải vì họ đo kém, mà vì họ dùng một phần.

⚠ Chiều ngược lại cũng có thật và đáng nhớ hơn: ở [luật 03 mục 4e](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md)
người báo (`leader`) nêu 2 mã lỗi còn `payment` tự quét ra 4. **Cả hai chiều dẫn
tới cùng một việc phải làm.**

## Hai chỗ framework đọc rộng hơn báo cáo

Ghi ở đây vì nó là bài học về cách nhận một báo cáo từ ngoài, không phải về hai
lỗi cụ thể:

| Báo cáo nói | Framework đo lại ra |
|---|---|
| web kế thừa, gRPC thì không (**hai** adapter) | Có **ba** adapter, và `socket` cũng kế thừa. gRPC là cái duy nhất lệch - tức là **sót**, không phải lựa chọn thiết kế |
| gRPC thiếu dòng log (**một** adapter) | `web` có dòng log nhưng **không nói chế độ TLS**, `socket` **không log gì**. Bản vá áp cho cả ba |

Cùng khuôn với ca `payment` ở [luật 03 mục 4e](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md):
người báo nêu 2 mã lỗi, repo tự quét ra 4. **Nhận một báo cáo về phạm vi thì việc
đầu tiên là tự quét lại toàn bộ, không phải sửa đúng chỗ được nêu** - nhưng lần
này chiều ngược lại với ca đó: ở đây người đứng ngoài báo hẹp, người trong repo mở
rộng ra.

## Cách viết một báo cáo vào đây

Không có khuôn bắt buộc. Hai báo cáo đầu tiên đặt một tiêu chuẩn đáng theo, và
phần đáng chép nhất là **mục cuối**:

> **"Phạm vi tôi đo được tới đâu"** - khai rõ đo trên mấy repo, mấy adapter, nhánh
> nào **chưa** đo, và chỗ nào là *đọc code* chứ không phải *chạy thật*.

Nó biến một báo cáo thành thứ dùng được: người nhận biết phải tự đo thêm ở đâu,
thay vì phải đoán xem con số 0 nghĩa là *không có vi phạm* hay *chưa ai nhìn*.
