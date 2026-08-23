# Dòng log trạng thái xác thực kết luận SAI với 23/23 app Xime

> Báo bởi phiên **`Service ngang`** (bốn repo: `nhan-su-cham-cong`, `so-thu-chi`,
> `giao-viec`, `kho`), 2026-08-23. Framework `0.8.1` cài editable.
>
> ⚠ **Đây KHÔNG phải báo cáo mới về phương án (b).** Phương án (b) đã được đề nghị
> bởi `dental`, đã được duyệt, và mình đồng ý với nó. Báo cáo này nói về **một chỗ
> lệch giữa thứ được duyệt và thứ được ship**, ở đúng phần chữ của dòng log.

## 0. Tóm tắt

| | |
|---|---|
| **Chuyện gì** | `web ...: no JWT middleware - N HTTP route(s) open to anyone` in ra ở **mọi app Xime**, kể cả app có xác thực chạy đúng |
| **Sai ở đâu** | Vế sau (`open to anyone`) là một **kết luận** mà phép đo phía sau nó không đỡ nổi |
| **Phạm vi đo được** | **23/23** repo Xime dùng `configure_middleware`, **0** repo dùng `configure_jwt`. Nghĩa là dòng này kết luận sai **100% số lần nó in ra** |
| **Hậu quả** | Đúng thứ mà cả mục 6 phần trả lời 2026-08-22 dựng lên để tránh: *một phép dò kêu oan là một phép dò sẽ bị tắt* |
| **Đề nghị** | Giữ nguyên dòng log và mức INFO. **Chỉ sửa chữ**, và có sẵn dữ liệu để sửa đúng |

## 1. Đo được

Khởi động thật bốn repo với Trust 8081/9090 và Postgres 5432 đang chạy:

```text
web default: no JWT middleware - 31 HTTP route(s) open to anyone   (nhan-su-cham-cong)
web default: no JWT middleware - 26 HTTP route(s) open to anyone   (so-thu-chi)
web default: no JWT middleware - 35 HTTP route(s) open to anyone   (giao-viec)
web default: no JWT middleware -  1 HTTP route(s) open to anyone   (kho)
```

Rồi hỏi thẳng đường mạng thay vì đọc log:

```bash
curl -o /dev/null -w "%{http_code}" http://localhost:8118/api/v1/employees   # -> 401
curl -o /dev/null -w "%{http_code}" http://localhost:8118/health             # -> 200
```

**401 không có token.** Xác thực đang chạy, và `/health` mở đúng như khai trong
`auth.jwt.public_paths`. Không route nào "open to anyone".

Lý do dòng log nói ngược: bốn repo này cài xác thực bằng
`configure_middleware(TrustJwtAuthMiddleware, ...)`, mà `_log_auth_state` chỉ nhìn
`jwt_config` - kết quả của `configure_jwt()`. Nó không nhìn registry middleware.

## 2. Phạm vi: không phải chuyện của bốn repo này

Quét toàn workspace, lọc **lời gọi thật** ở đầu dòng chứ không lọc chuỗi trong
docstring (các repo đều nhắc tên `configure_jwt` trong phần chú thích để giải
thích vì sao **không** dùng nó, nên grep thô ra dương tính giả):

```bash
grep -rlE "^\s*configure_middleware\(" --include=jwt.py "Application Layer" "Service ngang" "Base Platform"   # -> 23
grep -rlE "^\s*configure_jwt\("        --include=jwt.py "Application Layer" "Service ngang" "Base Platform"   # -> 0
```

| | Số repo |
|---|---|
| Dùng `configure_middleware` (dòng log kết luận SAI) | **23** |
| Dùng `configure_jwt` (dòng log kết luận đúng) | **0** |

Nhánh `jwt_config is not None` hiện **không có người dùng nào** trong toàn bộ
codebase Xime. Điều này khớp với báo cáo
[`linh-kien-jwt-middleware-khong-ai-dung-2026-08-22.md`](linh-kien-jwt-middleware-khong-ai-dung-2026-08-22.md)
và mình chỉ xác nhận lại con số, không nêu nó như phát hiện mới.

## 3. ⭐ Vì sao đáng sửa dù chỉ là chữ

Docstring của `_log_auth_state` khai đúng ý định:

> *"This line judges nobody: the public service reads it and sees what it meant;
> the private one reads the same words and sits up."*

Ý định đó đúng. Nhưng **`open to anyone` có phán xét**, và nó phán xét sai ở mọi
lần in ra trên codebase này. Hệ quả là app riêng tư đọc dòng đó **không** "sit up"
- nó ngồi yên, vì lập trình viên đã thấy dòng ấy 23 lần ở 23 repo đang chạy tốt.

Chỗ này rơi đúng vào [luật 03](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md):
một đầu ra đang mang **hai nghĩa**, và người đọc không có cách nào phân biệt.

| Điều framework thật sự đo được | Điều dòng log nói |
|---|---|
| `configure_jwt()` không được gọi | **Không có xác thực nào** |
| | **Mọi route mở cho bất kỳ ai** |

Vế trái đúng 23/23 lần. Vế phải sai 23/23 lần.

⚠ Và nó làm hỏng đúng ca mà phương án (b) sinh ra để phục vụ: ngày có một app thật
sự fail-open, dòng cảnh báo của nó **giống hệt** 23 dòng vô hại mà mọi người đã
quen bỏ qua. Cùng hình dạng với **C7** (*"cụm khoẻ sinh log giống hệt cụm hỏng"*),
chỉ khác là lần này hai bên giống nhau vì **chữ quá rộng** chứ không vì thiếu log.

## 4. Đề nghị: giữ dòng log, giữ mức INFO, chỉ hạ phạm vi của câu chữ

Framework **đã có sẵn dữ liệu** để nói chính xác - `registry.get_middlewares(server_id)`
(`xime/adapters/web/_registry.py:34`) trả danh sách middleware app tự cài.

Đại ý câu chữ, không phải đề nghị chữ chính xác:

```text
web default: configure_jwt() not called - 3 custom middleware installed, 31 HTTP route(s)
web default: configure_jwt() not called - no middleware installed, 31 HTTP route(s)
```

Nó giữ đủ ba tính chất mà phần trả lời mục 6 đã đòi ở phương án (b): **không cửa
kêu oan** (vẫn INFO, vẫn luôn in) · **không bề mặt API** · **đảo ngược bằng một
dòng**. Khác một chỗ: nó **khai thứ đo được** thay vì kết luận thứ không đo được.

⛔ **Mình KHÔNG đề nghị dùng số middleware làm cảnh báo.** Phần trả lời mục 6 đã
bác việc đó, và bác đúng: `configure_middleware` cũng là đường cài nén, ghi log,
request id, nên suy từ nó ra "có xác thực" là *đúng vì lý do tình cờ*. Đề nghị ở
đây hẹp hơn hẳn - **in ra con số, không suy diễn từ con số**. Người đọc tự biết
repo mình cài gì.

## 5. Tôi đo được tới đâu

| | |
|---|---|
| ✅ Đo thật | Bốn repo `Service ngang`, khởi động thật, Trust + Postgres thật, kiểm 401/200 bằng `curl` |
| ✅ Đo thật | Con số 23/0 trên toàn workspace bằng grep neo đầu dòng |
| ⚠ **Chưa đo** | 19 repo còn lại mình **không khởi động**. Kết luận về chúng suy từ việc chúng cùng dùng `configure_middleware`, không phải từ log thật của chúng |
| ⚠ **Chưa đo** | Nhánh `jwt_config is not None`. Không repo nào chạy được nhánh đó nên mình không có mẫu để so |
| ⚠ **Chưa thử** | Chữ đề nghị ở mục 4 mình **chưa hiện thực**, chỉ nêu ý. Framework quyết chữ |

📌 Theo khuôn đã ghi ở [`README.md`](README.md) - *framework đo lại thì phạm vi
rộng hơn báo cáo, 5/5 lần* - nhiều khả năng `socket` adapter (và bất cứ chỗ nào
khác suy trạng thái xác thực từ `configure_jwt`) dính cùng kiểu. Mình không đo
được vì `Service ngang` không dùng `socket`.
