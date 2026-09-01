"""Nền dùng chung của ba hệ thống con đa tiến trình.

`core/bootstrap`, `core/link` và `core/refdata` đều cần vài thứ giống hệt nhau -
ngữ cảnh sinh tiến trình, cách mở một vùng nhớ chung, cách ghi vào nó - và
**không cái nào trong ba nên phải import cái kia để có**. Gói này là chỗ duy
nhất cả ba đi tới được mà không tạo một cạnh phụ thuộc mới giữa chúng.

📌 Trước 2026-09-01 nó là một tệp lẻ nằm ngay trong `core/`, tên `_mp.py`.
Chuyển vào gói riêng theo yêu cầu của chủ dự án, với lý do đáng nhớ hơn chỗ đặt:
*"để file ngoài như thế sau nó lại thành bãi rác đấy"*.

## ⛔ Luật của gói này, để nó không thành bãi rác

Một thứ chỉ được vào đây khi thoả **cả hai**:

1. **Ít nhất hai hệ thống con cần nó.** Một hệ thống con dùng thì nó thuộc về
   hệ thống con đó, không thuộc về đây.
2. **Không import gì ngoài thư viện chuẩn.** Đây là điều kiện sống của gói: nó
   nằm dưới cùng, nên mọi lời import nó thêm vào là một cạnh phụ thuộc mà cả ba
   hệ thống con phải gánh. Có test canh: `tests_temp/api_surface/test_phan_tang.py`.

Không thoả điều 1 thì để nguyên chỗ cũ. Không thoả điều 2 thì nó thuộc về một
tầng cao hơn, không phải ở đây.

⚠ Đây là gói **riêng tư**. Ứng dụng đừng import từ đây - không có gì trong này
là API công khai, và tên có thể đổi bất cứ lúc nào.
"""

from ._mp import MP_CONTEXT, ghi_o, view_of

__all__ = ["MP_CONTEXT", "ghi_o", "view_of"]
