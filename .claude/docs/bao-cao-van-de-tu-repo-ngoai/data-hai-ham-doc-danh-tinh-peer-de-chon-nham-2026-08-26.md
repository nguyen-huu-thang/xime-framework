# `current_caller()` và `current_peer_sans()` trả lời HAI câu hỏi khác nhau, nhưng đọc như hai cách lấy cùng một thứ

> Báo cáo từ phiên **`Base Platform/data`**, ngày **2026-08-26**.
> Framework đang dùng: `0.8.1` (cài editable từ `D:\code\xime\xime framework`).
>
> ⚠ **Đây KHÔNG phải lỗi code.** Cả hai hàm làm đúng thứ chúng khai. Đây là đề nghị
> **sửa tài liệu**, và tôi mang theo một ca thật vừa cắn repo tôi để bạn cân xem có
> đáng không.

## 1. Chuyện gì

Repo tôi có một chốt chặn khai rõ *"chỉ app admin được gọi RPC này"*. Nó viết thế này,
và sống một tháng:

```python
from xime.core.security import current_caller

self._caller_authorizer.authorize(current_caller())   # so voi ["admin"]
```

Sai đơn vị. Trong mô hình định danh của Xime Platform, một **ứng dụng** có **nhiều tiến
trình**, mỗi tiến trình một cert riêng: CN mang định danh **tiến trình**, còn định danh
**ứng dụng** nằm ở SAN. Nên chốt đó chặn theo *xác* trong khi thứ cần chặn là *hồn*.

Hỏng theo hai chiều ngược nhau, và cả hai đều im lặng:

| Chiều | Hậu quả |
|---|---|
| App admin chạy tiến trình thứ hai (service-id khác) | **chặn oan**, mà `PERMISSION_DENIED` nhìn y hệt một cuộc tấn công |
| Một service-id đổi chủ ở tầng cấp cert | allowlist **im lặng** trỏ sang chủ mới |

Đã sửa sang `current_peer_sans()` + tra danh bạ. Đo live 4/4 trên tiến trình thật.

## 2. Vì sao tôi nghĩ nó dính tới tài liệu framework, chứ không chỉ dính tới tôi

Đọc lại hai docstring cạnh nhau trong `xime/core/security/peer.py`:

| Hàm | Docstring nói gì |
|---|---|
| `current_peer_sans()` | **rất kỹ**: SAN là chỗ chở *workload identity*, ví dụ SPIFFE ID; kèm đoạn mẫu cắt nhãn `URI:` rồi `startswith`; kèm cảnh báo `find`/`in` nhận nhầm `https://...?redirect=spiffe://attacker` |
| `current_caller()` | *"raw Common Name extracted from a verified client certificate"*, cộng câu *"framework chỉ cấp cơ chế (ai gọi)"* |

Câu **"ai gọi"** là chỗ tôi trượt. Nó đúng, nhưng nó là câu trả lời cho **cả hai** hàm,
nên khi cần *"ai gọi"* thì `current_caller()` là cái tên đọc thuận nhất - ngắn hơn, trả
một chuỗi thay vì một tuple phải tự khớp. Người viết chốt chặn cầm ngay nó.

> Hai hàm không phải **hai cách lấy** cùng một thứ; chúng là **hai danh tính khác nhau
> ở hai mức bền vững khác nhau**. Tài liệu hiện nói kỹ về *cách khớp* SAN, nhưng không
> nói ở đâu rằng phải **chọn giữa** hai hàm, và chọn theo tiêu chí gì.

Đây là dạng nhẹ của thứ chính các bạn đã gặp ở mục A1: một API đúng, dùng sai, và cái
sai **không có triệu chứng** vì cả hai đường đều trả về một chuỗi hợp lệ.

## 3. Đề nghị: một đoạn ngắn trong docstring `current_caller()`, giữ nguyên trung lập

Tôi cố ý **không** đề nghị thêm helper hay hằng số nào: framework 0.7.1 đã gỡ
`current_app_id()` vì `xime-app://` là quy ước của Xime chứ không phải khái niệm phổ
quát, và tôi cho rằng quyết định đó đúng. Đề nghị ở đây nằm trọn trong phần tài liệu và
không nhắc tên scheme nào:

> **CN nhận diện *một peer cụ thể* (thường là một tiến trình / một lần cấp cert).** Nơi
> triển khai nào cho nhiều peer dùng chung **một danh tính logic bền vững hơn** thì danh
> tính đó thường nằm ở SAN, không nằm ở CN - xem `current_peer_sans()`. Chốt phân quyền
> theo CN trong trường hợp ấy sẽ chặn oan peer mới và đi theo bất kỳ thay đổi nào ở tầng
> cấp cert.

Một dòng đối xứng ở `current_peer_sans()` (*"cần biết peer cụ thể nào thì xem
`current_caller()`"*) sẽ khép vòng, để ai vào từ hàm nào cũng thấy hàm kia.

## 4. Tôi đo được tới đâu

| | |
|---|---|
| Đọc mã nguồn | `xime/core/security/peer.py` bản đang cài editable, cả hai docstring |
| Ca thật | `Base Platform/data`, chốt `PurgeObject`, sống từ 2026-06-23 tới 2026-08-26 |
| Đã sửa và đo live | 4/4 vế trên tiến trình thật (cert đúc từ CA dev), 439 test xanh |
| **Chưa đo** | **Repo khác.** Tôi không quét xem bao nhiêu repo đang chốt phân quyền bằng `current_caller()` |

⚠ Mục cuối là chỗ tôi muốn nói rõ, vì thư mục này có một khuôn lặp *"framework đo lại thì
phạm vi rộng hơn báo cáo, 7/7 lần"*. Tôi báo trong đúng phạm vi mình chạm tới - một repo,
một chốt chặn. Nếu bạn quét cả 28 repo thì nhiều khả năng con số khác, và tôi không có cơ
sở để đoán nó.

Bối cảnh rộng hơn: chủ dự án ra chỉ đạo 2026-08-26 rằng **mọi service phải kiểm danh tính
caller trên cổng mTLS**, nên số chỗ gọi hai hàm này sắp tăng nhanh trong vài ngày tới. Đó
là lý do tôi báo bây giờ chứ không để dành - sửa tài liệu trước khi nhiều repo cùng viết
lớp chặn thì rẻ hơn hẳn sửa sau.

## 5. Không có gì chặn ai

Bản vá của tôi không cần framework đổi gì. Báo cáo này thuần là đề nghị tài liệu; bác bỏ
thì tôi không mất gì, và tôi cũng hiểu nếu bạn thấy nó nằm quá gần một quy ước riêng của
Xime mà framework cố ý đứng ngoài.

- phiên `data`
