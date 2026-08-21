# Vấn đề do repo NGOÀI báo về framework

Thư mục này giữ **báo cáo gốc**, nguyên văn, do phiên giữ một repo khác viết. Nó
khác `kiem-toan/` ở nguồn: `kiem-toan/` là framework **tự soi**, còn đây là thứ
người **dùng** framework va phải khi chạy thật.

⭐ Giữ nguyên văn thay vì tóm tắt lại, vì hai lý do: người trong repo đo đúng hơn
người đứng ngoài (họ có cấu hình thật, tải thật, cert thật), và **phần "tôi đo
được tới đâu"** ở cuối mỗi báo cáo là thứ một bản tóm tắt luôn làm rơi mất.

## Trạng thái

| Báo cáo | Ngày | Trạng thái |
|---|---|---|
| [gRPC tụt xuống PLAINTEXT khi đổi sang `process:`](data-service-grpc-tls-roi-khi-doi-sang-process-2026-08-21.md) | 2026-08-21 | ✅ **ĐÃ VÁ** - C6, đợt 6 |
| [gRPC không báo mình đã lên](data-service-grpc-khong-bao-minh-da-len-2026-08-21.md) | 2026-08-21 | ✅ **ĐÃ VÁ** - C7, đợt 6 |

Chi tiết bản vá, phép đo hai chiều và test canh:
[`../kiem-toan/0.8-kiem-toan-toan-dien.md`](../kiem-toan/0.8-kiem-toan-toan-dien.md)
mục **ĐỢT 6**.

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
