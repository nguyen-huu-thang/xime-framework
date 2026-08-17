# PEER_APP_ID: đọc định danh APPLICATION từ SAN của client cert

> ## ⛔⛔ TÍNH NĂNG NÀY ĐÃ BỊ GỠ HẲN Ở 0.7.1 (2026-08-17)
>
> **Đừng đọc file này như hiện trạng.** `PEER_APP_ID` và `current_app_id()` không còn tồn
> tại; thay bằng `PEER_SANS` / `current_peer_sans()` trả **mọi** entry SAN, thô, không lọc.
> Hiện trạng + lý do:
> [`go-phu-thuoc-khai-niem-2026-08-17.md`](go-phu-thuoc-khai-niem-2026-08-17.md).
>
> Lý do gỡ: hai hằng số `xime-app://` và **độ dài 33** là quy ước của **Xime Platform**,
> không phải khái niệm phổ quát, nên chúng không thuộc về một framework dùng chung. Chủ dự
> án ra nguyên tắc 2026-08-17: *"framework không được phụ thuộc gì khái niệm ngoài cả"*.
>
> ⭐ **Giữ nguyên file này, KHÔNG sửa nội dung bên dưới**, vì hai mục của nó là bằng chứng
> quan trọng nhất về việc coupling đã lọt vào bằng đường nào:
>
> - **Mục 4.4** - câu *"đây là kiểm định dạng, không phải kiểm nghiệp vụ, nên vẫn đúng ranh
>   giới framework"* chính là chỗ ranh giới bị trượt. `33` không phải một định dạng phổ
>   quát; nó là hệ quả của việc application-service chọn KSUID 24 byte.
> - **Mục 8** - ràng buộc *"key trung tính... framework không gắn ngữ nghĩa nghiệp vụ"* cho
>   thấy **kỷ luật đã có sẵn** nhưng bị áp vào **cái tên** thay vì **cái giá trị**.
>
> Bài học rút ra: coupling không lọt vào qua sự cẩu thả - nó lọt vào khi được dán nhãn là
> chuyện kỹ thuật thuần tuý, và khi framework bị xếp vào cùng danh sách công việc với các
> service của nền tảng (*"mắt xích đầu tiên trong 4 mắt xích còn đứt"*, mục 1 bên dưới).

> **Trạng thái lúc viết: ĐÃ LÀM ở 0.6.3** (2026-07-27). Giữ lại làm tài liệu thiết kế + bối cảnh.
>
> Đặt 2026-07-27, sau khi Trust đã khắc định danh app vào cert thật và 6 app đang chạy
> với cert đó. Framework là **mắt xích đầu tiên** trong 4 mắt xích còn đứt.
>
> **Đã hiện thực đúng thiết kế dưới đây**, với hai điểm chệch nhỏ có chủ đích:
>
> - `_set_peer_cn` đổi tên thành **`_set_peer_identity`** và set cả `PEER_CN` lẫn
>   `PEER_APP_ID` trong một chỗ (mục 3.2 đã gợi ý phương án này) nên hai đường gọi
>   unary/streaming không phải sửa riêng.
> - Entry SAN không decode được UTF-8 bị **bỏ qua rồi duyệt tiếp**, thay vì trả `None`
>   ngay. Vẫn thoả ca test ở mục 5 (chỉ có entry hỏng → `None`) nhưng bền hơn: một entry
>   rác không che mất entry `xime-app://` hợp lệ đứng sau nó.
>
> Định dạng SAN (mục 4.3) xử lý được **cả hai** khả năng nên không cần kiểm chứng bằng
> cert thật trước khi chốt. Test: `tests_temp/grpc/test_peer_identity.py`, 29 passed.
> Mục 6 dưới đây vẫn dùng được nếu về sau cần đối chiếu với cert thật.

---

## 1. Bối cảnh: tại sao framework cần đọc thêm một thứ nữa

Xime Platform có mô hình định danh gọi là **"hồn - xác"**:

- **Hồn** = `identity_id` của một APPLICATION (24 byte KSUID, bất biến), do
  application-service cấp. Một app có nhiều tiến trình service nhưng **chung một hồn**.
- **Xác** = cert mTLS do Trust cấp cho **từng tiến trình**, mỗi tiến trình một cert khác
  nhau (CN khác nhau).

Trust khắc hồn vào cert dưới dạng **SAN URI** `xime-app://<Base62 33 ký tự>`. Cert của
service nền tảng (trust, identity, user, data...) **không** có entry này.

Ví dụ cert thật của backend app gym (đang chạy trên máy dev):

```text
SAN UniformResourceIdentifier  spiffe://localhost/gym
SAN DNSName                    localhost
SAN IPAddress                  127.0.0.1
SAN UniformResourceIdentifier  xime-app://0FM4Roe2BT16XvEB7Y65VMv2xAZ68sdoZ
```

Framework hiện chỉ đọc **CN** của cert (`PEER_CN`). CN là danh tính của **xác** (tiến
trình). Không có cách nào biết tiến trình đó thuộc app nào -> data-service không thể phân
giải Subject APPLICATION, và toàn bộ mô hình quyền cho app đứng lại ở đây.

---

## 2. Việc cần làm (phạm vi hẹp, cố ý)

Thêm `PEER_APP_ID` cạnh `PEER_CN`. Framework **chỉ cấp cơ chế**, không diễn giải:

| Framework làm | Framework KHÔNG làm |
|---|---|
| Đọc SAN của client cert đã verify | Kiểm app đó có tồn tại không |
| Lọc entry có prefix `xime-app://` | Giải Base62 ra bytes |
| Lưu phần sau prefix vào `request_context` | Kiểm quyền của app |
| Fail-soft: không có -> `None` | Từ chối request khi thiếu |

Authorization vẫn là việc của ứng dụng. Đây đúng nguyên tắc đã áp cho `PEER_CN` và
`peer_pid`/`peer_uid` của socket adapter: **lưu sự thật thô, app tự diễn giải**.

---

## 3. File cần sửa

### 3.1. `xime/core/security/peer.py`

Thêm hằng số và helper, giữ nguyên phần cũ:

```python
PEER_APP_ID = "peer_app_id"


def current_app_id() -> str | None:
    """Base62 identity của APPLICATION sở hữu tiến trình gọi, hoặc None."""
    return request_context.get(PEER_APP_ID)
```

Nhớ export ở `xime/core/security/__init__.py` (chỗ đang export `current_caller`).

### 3.2. `xime/adapters/grpc/interceptors/_context.py`

Đây là file chính. Hiện có:

- `_read_peer_cn(context)` - đọc `auth_context()["x509_common_name"]`, fail-soft
- `_set_peer_cn(handler_args)` - lấy context (tham số thứ 2), set vào `request_context`
- `RequestContextInterceptor` gọi `_set_peer_cn(args)` ở **hai** chỗ:
  `_wrap_unary` (dòng ~138) và `_wrap_streaming` (dòng ~155)

Thêm `_read_peer_app_id(context)` theo đúng khuôn `_read_peer_cn`, rồi gọi trong cùng
hàm `_set_peer_cn` (hoặc đổi tên thành `_set_peer_identity` và set cả hai key) để **không
phải sửa hai chỗ gọi**.

---

## 4. Chi tiết kỹ thuật đã kiểm chứng

### 4.1. Tên property gRPC

**`x509_subject_alternative_name`** - đã kiểm chứng trong grpc Python cài trên máy này:
`grpc/aio/_base_server.py:303` nêu đích danh property này cạnh `x509_common_name`. Không
phải đoán.

### 4.2. Kiểu dữ liệu trả về

`auth_context()` trả `dict[str, list[bytes]]`. Khác với CN, SAN **có nhiều giá trị** -
cert app có 4 entry (xem mục 1), nên phải **duyệt cả list**, không lấy `values[0]`:

```python
values = auth.get("x509_subject_alternative_name") or auth.get(
    b"x509_subject_alternative_name"
)
```

Vẫn giữ cách chấp nhận cả key `str` lẫn `bytes` như `_read_peer_cn` đang làm.

### 4.3. Định dạng giá trị SAN

Không chắc gRPC trả entry URI kèm prefix loại nào. Hai khả năng cần xử lý được cả hai:

- `b"xime-app://0FM4Roe2..."` - giá trị trần
- `b"URI:xime-app://0FM4Roe2..."` - có tiền tố loại (kiểu openssl in ra)

Cách an toàn: tìm chuỗi con `xime-app://` trong từng entry rồi cắt từ đó, thay vì
`startswith`. **Kiểm chứng thực tế bằng cách in `auth_context()` ra log** khi có kết nối
mTLS thật từ một app (mục 6) trước khi chốt.

### 4.4. Giá trị lưu vào context

Lưu **phần sau `xime-app://`**, tức Base62 33 ký tự, KHÔNG lưu cả URI. Lý do: đây là dạng
mà application-service dùng trong REST path và JWT `sub`, và là dạng service khác giải mã
ngược ra `identity_id`. Nếu lưu cả scheme, mọi consumer đều phải tự cắt.

Có thể kiểm độ dài 33 ký tự trước khi lưu (fail-soft: sai độ dài -> coi như không có).
Đây là kiểm định dạng, không phải kiểm nghiệp vụ, nên vẫn đúng ranh giới framework.

### 4.5. Bảng chữ Base62 của platform

`0-9A-Za-z`, big-endian, pad trái. 24 byte -> **đúng 33 ký tự**. Framework không cần
giải mã, chỉ cần biết độ dài để kiểm sơ bộ.

---

## 5. Test

Test hiện có ở `tests_temp/grpc/test_peer_identity.py` dựng **fake ServicerContext** bằng
`unittest.mock`, `ctx.auth_context.return_value = auth`. Không cần cert thật, không cần
server. Viết thêm theo đúng khuôn đó:

| Ca | Mong đợi |
|---|---|
| `auth_context()` ném exception | `None` (fail-soft) |
| Không có key SAN | `None` |
| SAN chỉ có spiffe/DNS/IP (cert nền tảng) | `None` |
| SAN có `xime-app://<33 ký tự>` lẫn giữa các entry khác | trả đúng 33 ký tự, không kèm scheme |
| Có nhiều entry `xime-app://` | chọn cái đầu (cert hợp lệ không bao giờ có 2) |
| Giá trị không decode được UTF-8 | `None`, không ném |
| Handler xong | `request_context` đã clear, không rò sang request sau |
| Streaming handler | cũng set được `PEER_APP_ID` |

Chạy: `pytest tests_temp/grpc/test_peer_identity.py -q`.

---

## 6. Cách kiểm chứng bằng cert thật (khi cần chắc chắn về định dạng SAN)

Trên máy dev đã có sẵn 6 app mang cert có SAN app. Cách nhanh nhất:

1. Cert nằm trong DB của từng app, bảng `trust_certificate`, cột `public_cert` (base64
   DER, **không phải PEM** - phải `base64.b64decode` rồi
   `x509.load_der_x509_certificate`). DB: `gym`, `xime_spa`, `gara`, `nha_tro`,
   `xime_admin`, `saas_template` (user `thang` / `123456` trên localhost:5432).
2. Hoặc cấp một file bootstrap mới rồi soi bằng
   `Base Platform/Trust/kiem-tra-cert-san.py <file>.bootstrap`.
3. Muốn xem gRPC thật sự đưa gì vào `auth_context()`: tạm log `dict(auth)` trong
   `_read_peer_cn`, chạy một app gọi sang service Python có gRPC server bật mTLS.

---

## 7. Ai sẽ tiêu thụ `PEER_APP_ID` (để hiểu vì sao thiết kế thế này)

**data-service** là consumer đầu tiên:

- Request không có JWT nhưng có `PEER_APP_ID` -> Subject loại `APPLICATION`
  (`SubjectType.APPLICATION` đã có sẵn trong enum, chưa nơi nào dựng).
- JWT thắng khi cả hai cùng có.
- Audit ghi cặp: subject (app = hồn) + actor (`PEER_CN` = tiến trình = xác).
- REST public không có client cert nên APPLICATION subject không bao giờ đến từ ngoài mesh.

Việc đó **không thuộc framework**. Framework chỉ đưa sự thật thô vào context.

---

## 8. Ràng buộc phải giữ

- **Fail-soft tuyệt đối.** Mọi exception bị nuốt, trả `None`. Một cert lạ không bao giờ
  được phép làm hỏng request. Cùng lý do đã áp cho `_read_peer_cn`.
- **Không đổi hành vi `PEER_CN`.** Có service đang dựa vào nó:
  data-service dùng `current_caller()` + allowlist `grpc.internal.allowed_callers` để bảo
  vệ endpoint nội bộ (`InternalCallerAuthorizer`, fail-closed). Đụng vào là vỡ.
- **Không thêm dependency mới.** Chỉ đọc dict từ `auth_context()`, không parse X.509.
- **Key trung tính.** Đặt tên `peer_app_id`, không phải `application_id` hay
  `owner_app_identity_id` - framework không gắn ngữ nghĩa nghiệp vụ.

---

## 9. Liên quan

- Wishlist gốc: [`wishlist-tinh-nang.md`](wishlist-tinh-nang.md), mục "Trích thêm SAN
  `xime-app://` -> `PEER_APP_ID`" (đặt 2026-07-26).
- Kế hoạch tổng của đợt: `D:\code\xime\thiết kế chi tiết trong giai đoạn khởi nghiệp\ke-hoach-hon-xac.md`
  Phase 3.1.
- Mô hình hồn - xác + cách Trust khắc SAN:
  `D:\code\xime\.claude\docs\dang-ky-app-va-dinh-danh-hon-xac.md`.
- Khảo sát toàn cảnh 4 mắt xích còn đứt:
  `D:\code\xime\.claude\docs\khao-sat-ha-tang-cho-app-chay-that.md`.
