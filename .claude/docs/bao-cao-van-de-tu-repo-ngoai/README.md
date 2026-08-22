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
| [`configure_jwt` không repo nào dùng, và hai chỗ chặn 2 repo di trú về](linh-kien-jwt-middleware-khong-ai-dung-2026-08-22.md) | 2026-08-22 | ✅ **ĐÃ ĐỌC** · ⏳ **CHỜ CHỦ DỰ ÁN** - hai điểm kỹ thuật đã **đo lại và xác nhận đúng**. Mục A (khớp tiền tố) ✅ **DUYỆT**. Mục B (nhận diện trên đường công khai) ⛔ **BÁC VĨNH VIỄN** - chủ dự án dặn *"đừng app nào đề nghị nữa"*. Xem [phần trả lời](tra-loi-2026-08-22.md) mục 5 |
| [Route WebSocket không xác thực thì kêu, route HTTP thì im](dental-http-khong-jwt-thi-im-lang-2026-08-22.md) | 2026-08-22 | ✅ **ĐÃ ĐỌC** · mục 7 **ĐÃ VÁ** (C9, phạm vi rộng hơn: **hai** registry) · mục 6 ✅ **DUYỆT phương án (b)** (một dòng `INFO` khai trạng thái xác thực), **bác (a)**. Xem [phần trả lời](tra-loi-2026-08-22.md) mục 6 |

Chi tiết bản vá, phép đo hai chiều và test canh:
[`../kiem-toan/0.8-kiem-toan-toan-dien.md`](../kiem-toan/0.8-kiem-toan-toan-dien.md)
mục **ĐỢT 6**.

## ⭐ Khuôn lặp lại: framework đo lại thì phạm vi RỘNG HƠN báo cáo, MỌI LẦN

Đây là quan sát đáng giá nhất của cả thư mục, và tới 2026-08-22 nó đúng **5/5
lần** - không có ngoại lệ nào:

| Báo cáo nói | Đo lại ra |
|---|---|
| web kế thừa TLS, gRPC thì không (**2** adapter) | **3** adapter, `socket` cũng kế thừa. gRPC là cái duy nhất lệch - tức là **sót**, không phải lựa chọn thiết kế |
| gRPC thiếu dòng log (**1** adapter) | `web` có log nhưng **không nói chế độ TLS**, `socket` **không log gì**. Bản vá áp cho cả ba |
| `check config` tố oan khối `socket` (**1** khối, **2** khoá) | **2** khối - `lmdb` cũng thiếu `file_mode`/`dir_mode`. Và `socket` còn sai **chiều ngược lại**: khai `socket.path` mà **không đường nào đọc**. Đo trên YAML của chính người báo: **4** lỗi, không phải 2 |
| gợi ý lỗi dẫn sai đường cho `RefData` (**1** registry) | **2** registry nằm ngoài `scan()` - `RefData` và handler `ProcessLink` |

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
