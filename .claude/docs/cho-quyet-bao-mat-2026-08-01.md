# Chờ chủ dự án quyết - đợt bảo mật 2026-08-01

> Bốn quyết định đã chốt nằm ở mục 0 của
> [`ke-hoach-va-bao-mat-2026-08-01.md`](ke-hoach-va-bao-mat-2026-08-01.md). File này ghi
> **phần CÒN LẠI chưa quyết**, kèm khuyến nghị và thứ nó đang chặn.
>
> Quyết xong mục nào thì chuyển kết luận sang kế hoạch vá và **xóa mục đó khỏi đây**, để file
> này luôn chỉ còn thứ thật sự đang treo.

## Bảng nhanh

| # | Chờ quyết | Đang chặn gì | Khuyến nghị |
|---|---|---|---|
| 1 | Secret để ở file nào | **Đợt 0 - đường găng** | Hướng B |
| 2 | 7 file cảnh báo không commit được | Không chặn gì, nhưng tài liệu sẽ mất khi đổi máy | Xử lý từng ca, xem mục 2 |
| 3 | Sau khi vá nội bộ xong có đẩy PyPI không | Không chặn đợt nào | Đẩy 0.7.1 sau khi đợt 2 chạy ổn |
| 4 | Có dựng venv riêng cho app đã deploy không | Làm đợt 4 an toàn hơn | Có, nhưng làm sau đợt vá |
| 5 | Ba câu kỹ thuật của F10 | Đợt 3 | Xem mục 5 |

---

## 1. Secret để ở file nào (A6) - ĐANG CHẶN ĐƯỜNG GĂNG

**Vì sao treo:** chú thích trong `application-production.yml` của `shop` bảo để secret vào
`application-secret.yml`. `YamlConfigLoader.load()` chỉ nạp `application.yml` +
`application-{env}.yml`, **không** có file thứ ba, và file đó không tồn tại ở đâu. Đây là
nguyên nhân trực tiếp khiến secret dev còn nằm lại trong git.

**Đang chặn:** việc 0.1 (đổi `jwt.secret` của `shop`) không làm dứt điểm được cho tới khi biết
secret mới sẽ nằm ở đâu. Đây là mục **gấp nhất toàn đợt**.

| | **Hướng A** - thêm tầng thứ ba vào framework | **Hướng B** - dùng `application-local.yml` đã có ⭐ |
|---|---|---|
| Sửa gì | `core/config/loader.py` nạp thêm `application-secret.yml` sau cùng | Không đụng framework; sửa chú thích ở các app |
| Ưu | Đúng thứ tài liệu đã hứa; secret tách hẳn khỏi cấu hình thường | Không đụng framework nghĩa là không chạm 31 app cùng lúc (xem mục 1.1 của kế hoạch) |
| Nhược | Đổi hành vi nạp config của **cả 31 app**; thêm một chỗ nữa để quên copy lúc deploy | Tên file mang nghĩa "máy của tôi", dùng cho production hơi lệch nghĩa |
| Kèm theo | Phải thêm `application-secret.yml` vào `.gitignore` của mọi repo | Phải sửa chú thích ở **mọi** `application-production.yml` và trong template, kẻo lần sau lại có người tin vào file không tồn tại |

**Khuyến nghị: hướng B.** Lý do không phải kỹ thuật mà là rủi ro: đợt này đang vá bảo mật, và
hướng A đổi cách nạp cấu hình của 31 app đang chạy. Trộn một thay đổi hạ tầng vào giữa đợt vá là
cách chắc chắn để về sau không biết cái gì gây ra cái gì. Nếu vẫn thích hướng A về lâu dài thì
làm nó thành một việc riêng sau khi đợt 2 xong.

---

## 2. Bảy file cảnh báo không commit được

28 file `canh-bao-bao-mat-2026-08-01.md` đã sinh; **21 file đã commit** vào 21 repo. Bảy file
còn lại nằm ngoài tầm git vì ba lý do khác nhau, mỗi lý do cần một quyết định khác nhau.

### 2a. `Base Platform/data` - `.claude/` bị gitignore cố ý

`.gitignore` dòng 17 có `.claude/`. Đây là quyết định đã có từ trước, tôi **không tự gỡ**.

Hệ quả: cảnh báo bảo mật của data-service chỉ tồn tại trên máy này. Đổi máy hoặc clone lại là
mất. Đáng lưu ý vì data-service là nơi giữ file của mọi app, tức là chỗ ba mục lưu trữ
(F2/F13/F16) chạm vào mạnh nhất.

| Lựa chọn | Đánh đổi |
|---|---|
| **Giữ nguyên** | Tôn trọng quyết định cũ. Mất tài liệu khi đổi máy |
| **Gỡ `.claude/` khỏi `.gitignore`** ⭐ | Tài liệu sống cùng code. Nhưng phải rà `.claude/` của repo đó xem có secret hay ghi chú riêng tư không trước khi commit |
| **Ngoại lệ một dòng** `!.claude/docs/canh-bao-bao-mat-*.md` | Chỉ commit file cảnh báo, giữ nguyên phần còn lại. Gọn nhất nếu muốn giữ quyết định cũ |

Khuyến nghị: **ngoại lệ một dòng** - vừa giữ được ý định ban đầu, vừa không mất tài liệu bảo mật.

### 2b. `Application Layer/admin` - `.claude/` nằm NGOÀI repo

Repo của admin đặt ở `admin/backend/` (đúng như `Application Layer/CLAUDE.md` đã ghi: "repo đặt
ở admin\backend\, khác khuôn 4 app trên"), nhưng `.claude/` lại nằm ở `admin/`. Nên **toàn bộ**
`.claude/docs/` của admin - gồm cả `ket-qua-nang-cap-2026-08-01.md` viết trước phiên này - đều
không được version control.

Đây là chuyện có từ trước, không phải do đợt này gây ra, nhưng đợt này làm nó lộ ra.

| Lựa chọn | Đánh đổi |
|---|---|
| **Chuyển `.claude/` vào `admin/backend/`** ⭐ | Đồng bộ với 20 repo còn lại. Nhưng đổi đường dẫn thì mọi con trỏ tới tài liệu admin phải sửa theo |
| **Đưa repo lên `admin/`** | Đúng khuôn nhất, nhưng là đổi cấu trúc repo - việc lớn, không nên làm giữa đợt vá |
| **Giữ nguyên** | Không tốn gì. Tài liệu admin vẫn ngoài git như hiện tại |

Khuyến nghị: **chuyển `.claude/` vào `backend/`**, nhưng làm **sau** đợt vá - nó không chặn gì.

### 2c. Năm app Monolithic chưa phải repo git

`auto-garage`, `dental-clinic`, `english-center`, `rental-management`, `spa`: `git rev-parse`
báo không phải repo. Không có lịch sử, không có khả năng quay lui.

Đáng chú ý vì cả năm app này **đang giữ chuỗi ký JWT** (mục A3) - loại file mà lịch sử thay đổi
là thứ ta cần nhất khi có sự cố.

| Lựa chọn | Đánh đổi |
|---|---|
| **`git init` cho từng app** ⭐ | Có lịch sử, có thể quay lui. Phải viết `.gitignore` cho đúng trước lần commit đầu, kẻo commit nhầm `application.yml` chứa secret - đúng cái bẫy A3 đã sập ở `shop` |
| **Giữ nguyên** | Không tốn gì, nhưng năm app không có lưới an toàn nào |

Khuyến nghị: **`git init`**, và làm **sau** khi đã đổi secret (việc 0.3), để lần commit đầu tiên
không chứa chuỗi ký cũ trong lịch sử.

### 2d. Hai file `CLAUDE.md` đầu mối cũng ngoài git

`D:\code\xime\CLAUDE.md` và `D:\code\Monolithic\CLAUDE.md` không thuộc repo nào (thư mục gốc
workspace không phải repo). Hai dòng chỉ đường tới báo cáo bảo mật mà tôi thêm vào đó **không
được commit ở đâu cả**.

Đây là hiện trạng có sẵn của workspace, không phải việc phát sinh. Nêu ra để biết: nếu đổi máy
thì hai dòng đó mất, và phiên sau sẽ không tìm thấy đường tới báo cáo.

---

## 3. Sau khi vá nội bộ xong, có đẩy PyPI không

Quyết định hiện tại là **vá trong repo, chưa đẩy PyPI**. Hợp lý cho 31 app nội bộ (cài editable
nên có bản vá ngay), nhưng gói đã công khai **11 bản trên PyPI**, nên người dùng ngoài vẫn đang
nhận bản 0.7.0 còn nguyên F1, F2, F3, F4.

Câu hỏi thật không phải "có đẩy không" mà là: **gói này có người ngoài dùng thật không?** Nếu
có thì việc giữ bản vá lại là quyết định ảnh hưởng tới người khác, không chỉ tới dự án.

**Khuyến nghị:** đẩy **0.7.1** sau khi đợt 2 chạy ổn nội bộ vài ngày. Semver cho phép đổi hành
vi ở bản vá khi đó là sửa lỗi bảo mật; ghi rõ phần nào đổi hành vi trong `CHANGELOG.md`.

Kiểm số lượt tải để biết có ai dùng thật không:
`https://pypistats.org/packages/xime`

---

## 4. Có dựng venv riêng cho app đã deploy không

Hiện **không app nào có venv riêng** - cả 31 codebase dùng chung một Python 3.14 hệ thống. Nghĩa
là nâng phiên bản một gói cho một app là nâng cho cả 31 app.

Việc này làm **đợt 4** (nâng sàn dependency, F3) rủi ro hơn mức cần thiết.

**Khuyến nghị:** có, ít nhất cho app đã deploy (`shop`), nhưng **làm sau đợt vá** - trộn vào
giữa thì khi có gì hỏng sẽ không biết do bản vá hay do đổi môi trường. Đây là việc hạ tầng, tôi
đã ghi nó vào mục "việc KHÔNG làm trong đợt này" của kế hoạch.

---

## 5. Ba câu kỹ thuật còn mở của F10

Hướng đã chốt: **lỗi trước khi phục vụ thì sập luôn; lỗi sau khi đã phục vụ thì cô lập.** Nhưng
chốt hướng chưa đủ để code, còn ba câu (chi tiết ở đợt 3 của kế hoạch):

1. **"Đã phục vụ" xác định thế nào?** `Adapter` protocol hiện chỉ có `start()`/`stop()`, không
   có tín hiệu "đã bind cổng, sẵn sàng". Thêm nghĩa là **đổi API cho mọi adapter**, gồm cả
   adapter do người dùng framework tự viết.
2. **Ai giữ trạng thái "adapter này đã chết"?** Framework hiện không có khái niệm health.
3. **Nếu chính web adapter chết thì `/health` do ai trả lời?** Lúc đó buộc phải sập cả tiến
   trình - tức là quy tắc có ngoại lệ, phải viết ra thành văn.

Ba câu này trả lời được trong lúc code, không cần quyết trước. Nêu ở đây để không ai tưởng đợt 3
là "sửa một dòng" rồi ước lượng sai thời gian.
