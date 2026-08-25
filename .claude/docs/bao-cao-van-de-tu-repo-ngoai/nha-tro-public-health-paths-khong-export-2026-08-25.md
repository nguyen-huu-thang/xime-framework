# `public_health_paths()` không export, nên `/healthz` của app tự viết middleware trả 401

> Báo từ repo **`Application Layer/nha-tro`**, ngày 2026-08-25, trong lúc làm M6 của lát
> trả nợ luật 01 nghĩa 1. Framework `0.8.1`, cài editable.
>
> ⚠ Đây là **báo cáo**, không phải yêu cầu sửa. Phần "nên làm gì" ở cuối là đề xuất, và
> nó có một lý do để **không** làm mà tôi ghi luôn.

## 1. Hiện tượng

```python
from xime.adapters.web import configure_health, public_health_paths
# ImportError: cannot import name 'public_health_paths' from 'xime.adapters.web'
```

`configure_health` **có** trong `__all__`; `public_health_paths` thì **không**, dù nó nằm
cùng file `_health.py` và docstring của chính nó ghi:

> *"Đường dẫn sức khoẻ đang bật - **middleware JWT cho chúng đi qua**."*

Tức nó sinh ra đúng cho việc app dùng, mà app không import được bằng đường công khai.

## 2. Ai bị chạm, và ai không

| | |
|---|---|
| App dùng `configure_jwt` của framework | ✅ **không bị gì** - framework tự miễn trừ đường sức khoẻ |
| App còn **middleware JWT tự viết** | ⛔ phải tự cộng đường sức khoẻ, mà hàm để làm việc đó thì không import được |

Nhóm thứ hai không nhỏ: `CLAUDE.md` workspace ghi **19 app** còn nhánh A1 trong
`config/jwt.py` của chính chúng, và phần lớn trong số đó có `TrustJwtAuthMiddleware` tự
viết chép từ cùng một bản.

## 3. Vì sao hậu quả không nhẹ như nó trông

Quên miễn trừ thì `/healthz` **đòi token**. Mà:

> Một `/healthz` đòi token là một `/healthz` **vô dụng** - nó tắt đúng vào lúc app không
> lấy nổi khoá verify, tức **đúng lúc người ta cần nó trả lời nhất**.

⭐ Và ở lát đa tiến trình, `/healthz` không chỉ là chốt sức khoẻ: nó là **phép đo duy
nhất** chứng minh cụm thật sự chia tải. Nhà trọ đo `29% primary` trên 90 lời gọi để loại
hẳn giả thuyết *"một tiến trình"* và *"hai tiến trình"*. Không có nó thì *"đã bật ba tiến
trình"* chỉ là một lời khai.

📌 `service-ngang` đã báo một ca đúng dạng này ngày 2026-08-21 (`crm`, **60/60 request
`/healthz` trả 401**). Nên đây là **lần thứ hai**, ở một repo khác, không biết repo kia.

## 4. Nhà trọ đang làm gì

Import từ module riêng tư, **kèm ngày hết hạn ghi ngay tại chỗ**:

```python
# ⚠ Import từ module RIÊNG TƯ, có chủ đích và có ngày hết hạn.
# ➡ Dòng này biến mất khi repo chuyển sang `configure_jwt`.
from xime.adapters.web._health import public_health_paths
```

## 5. Đề xuất - **và một lý do để không làm**

**Đề xuất:** thêm `public_health_paths` vào `__all__` của `xime.adapters.web`. Nó là hàm
thuần, không trạng thái, không mở rộng bề mặt API đáng kể.

⛔ **Lý do ngược, và tôi thấy nó đáng cân nhắc thật:** export nó là **hợp thức hoá** việc
app tự viết middleware JWT - đúng thứ `0.7.2` và bản vá A1 đang cố xoá. Một API công khai
chỉ có ích cho người đi đường sai là một API **kéo dài tuổi thọ của đường sai đó**.

➡ Nếu chọn **không export**, thì đề nghị đổi docstring của `public_health_paths`: câu
*"middleware JWT cho chúng đi qua"* đang **mời** người ta gọi nó, mà gọi thì không import
được. Chỗ đó nên nói rõ nó là chi tiết nội bộ của `configure_jwt`.

⭐ Hai đường đều được; thứ **không** nên giữ là trạng thái hiện tại - **một hàm tự mô tả
mình là để cho app dùng, mà app không gọi tới được**.

- phiên `nha-tro`
