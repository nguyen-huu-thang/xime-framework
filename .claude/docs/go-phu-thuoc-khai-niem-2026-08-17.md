# Gỡ phụ thuộc khái niệm khỏi framework (2026-08-17)

> **Trạng thái: ĐÃ LÀM XONG.** Nằm trong **0.7.1** (chủ dự án chốt: 0.7.1 chưa commit nên
> chưa phát hành, gộp vào đây thay vì đẩy sang 0.8). Test **1516 passed, 11 skipped**.
>
> Nguyên tắc chủ dự án ra ngày 2026-08-17, và nó là gốc của toàn bộ file này:
>
> > **"Framework làm ra để nhiều người khác dùng nữa, và không liên quan gì tới các dự án kia
> > của tôi, nên framework không được phụ thuộc gì khái niệm ngoài cả."**

## 1. Đã đổi cái gì

| Gỡ | Thay bằng |
| --- | --- |
| `current_app_id() -> str \| None` | `current_peer_sans() -> tuple[str, ...] \| None` |
| `PEER_APP_ID` | `PEER_SANS` |
| `_APP_ID_SCHEME = "xime-app://"` | (không còn) |
| `_APP_ID_LENGTH = 33` | (không còn) |
| `_read_peer_app_id()` | `_read_peer_sans()` |

`PEER_CN` và `current_caller()` **giữ nguyên** - CN là khái niệm chuẩn X.509.

Ba quyết định của chủ dự án về hình dạng API mới:

1. **Tên khoá `PEER_SANS`**, không phải `PEER_SAN_URIS`. Lý do ở mục 6.
2. **Có helper** `current_peer_sans()`, để đối xứng với `current_caller()`.
3. **Khoá VẮNG MẶT khi không có gì để thuật**, không phải có mặt với tuple rỗng.

✅ Sau đợt này, `grep -rn "xime-app" xime/ tests_temp/` ra **rỗng**. Dữ liệu mẫu trong test
cũng đã đổi sang trung tính (`spiffe://...` và một scheme tự đặt `acme-workload://`), vì test
của một framework không được nhúng scheme của một nơi triển khai cụ thể.

## 2. Cơ chế sau khi đổi

```
[1]  Client mở kết nối gRPC, đưa client cert
      ↓
[2]  gRPC + OpenSSL bắt tay mTLS, XÁC MINH cert theo CA đã cấu hình
     Không đạt → kết nối bị chặn, framework không bao giờ thấy request
      ↓
[3]  gRPC phân giải cert thành dict:  context.auth_context()
        {"x509_common_name": [b"api-backend"],
         "x509_subject_alternative_name": [b"spiffe://cluster.local/ns/default/sa/api",
                                            b"localhost",
                                            b"127.0.0.1",
                                            b"acme-workload://team-7/checkout"]}
     ⚠ Các khoá x509_* CHỈ có mặt khi mTLS đã verify thành công
      ↓
[4]  RequestContextInterceptor  ← interceptor NGOÀI CÙNG, bọc mọi handler
     _set_peer_identity(args):
        cn   = _read_peer_cn(context)     → auth["x509_common_name"][0]
        sans = _read_peer_sans(context)   → decode HẾT entry, không lọc gì
      ↓
[5]  request_context.set(PEER_CN, cn)      (chỉ khi khác None)
     request_context.set(PEER_SANS, sans)  (chỉ khi tuple không rỗng)
      ↓
[6]  Handler nghiệp vụ của app chạy
        current_caller()     → "api-backend"
        current_peer_sans()  → ("spiffe://...", "localhost", "127.0.0.1", "acme-workload://...")
      ↓
[7]  Teardown: request_context.clear() + clear_security()
```

**Bốn tính chất được giữ nguyên** (chúng là phần làm đúng từ đầu):

| Giữ | Vì sao |
| --- | --- |
| **Không parse X.509** - chỉ đọc `auth_context()` | Tính chất sạch nhất của cả cơ chế. Không dependency crypto |
| **Fail-soft tuyệt đối** | Cert lạ không được phép làm hỏng request |
| **Duyệt hết entry**, entry không decode được thì bỏ qua rồi đi tiếp | Một entry rác không che được entry hợp lệ đứng sau |
| **`_wrap_handler` xử lý riêng 4 dạng RPC** | Response-streaming là async generator, `await` sẽ TypeError |

⚠ **Bất đối xứng còn tồn tại, chưa sửa:** `PEER_SANS` **chỉ có ở gRPC**. Web adapter không đọc
client cert (đã grep, rỗng hoàn toàn), nên một app phục vụ HTTPS + mTLS không nhận được gì. Hàm
thì nằm ở `core/` mà chỉ **một** adapter cấp dữ liệu cho nó. Đây là hiện trạng, không phải
quyết định - ai cần thì mở việc riêng.

## 3. Vì sao độ dài 33 là chỗ nặng nhất, không phải scheme

Phép kiểm `if len(app_id) != 33: continue` **không log gì**, nên nó biến một dấu hiệu bất
thường thành `None`, mà `None` cũng là giá trị của *"cert không có entry nào"*. Một giá trị hai
nghĩa, đúng [luật 03](../../../.claude/rules/03-mot-gia-tri-mot-nghia.md).

Và nó **mâu thuẫn thật với người tiêu thụ duy nhất**. `data-service` viết trong
`ResolveSubject.py`:

```python
except ValueError as error:
    # Framework fail-soft tuyệt đối khi đọc SAN, nên chuỗi lạ vẫn tới được
    # đây. Từ chối chứ không bỏ qua: cert mang định danh app sai dạng là
    # dấu hiệu bất thường, không phải request vô danh bình thường.
```

Câu *"chuỗi lạ vẫn tới được đây"* **chỉ đúng một nửa**: chuỗi lạ **đúng 33 ký tự** thì tới
được, chuỗi lạ **sai độ dài** thì không bao giờ tới. Họ phòng thủ dựa trên một giả định không
đủ và không có cách nào biết.

⭐ **Và phép kiểm đó không mua thêm an toàn nào**: `data-service` đã tự giải Base62 đầy đủ bằng
`IdService.from_string()`, một phép kiểm mạnh hơn hẳn kiểm độ dài. Framework trả giá bằng
coupling cộng một đường vứt im lặng, để đổi lấy một phép kiểm mà hạ nguồn dù sao cũng làm lại,
kỹ hơn.

Gỡ nó ra thì `data-service` **lấy lại được phép phân biệt** mà nó đã viết code để dùng.

## 4. Điều tra nguồn gốc: vì sao coupling lọt vào

Phần này quan trọng hơn bản vá, vì người kế tiếp sẽ gặp đúng hoàn cảnh đó.

### 4.1. Dòng thời gian

| Mốc | Việc |
| --- | --- |
| **2026-06-19** | notification-service đề xuất framework đọc danh tính peer mTLS. Framework **đánh giá rồi mới chốt** đẩy vào 0.4 |
| ~2026-06-20 | `PEER_CN` ra ở 0.4, **giữ trung tính** |
| **2026-07-26** | Mục `PEER_APP_ID` vào wishlist, ghi rõ *"đặt **cho đợt hồn - xác**"* |
| **2026-07-27 sáng** | Workspace khảo sát *"còn gì chặn app chạy thật"*. Bối cảnh: *"cert của 6 app **vừa được khắc `xime-app://` xong cùng ngày**"* |
| **2026-07-27 cùng ngày** | Viết thiết kế **và** code xong **và** đóng mục. File khảo sát tự ghi: *"CẬP NHẬT 2026-07-27 (cùng ngày, sau khi khảo sát xong): A1 và M1 ĐÃ LÀM XONG"* |

Thiết kế và hiện thực gói trong **một ngày**, dưới sức ép "6 app đang bị chặn".

⚠ **Nhưng bản thân code không chắp vá**: có tài liệu thiết kế riêng, 29 test, fail-soft nhất
quán, xử lý cả hai dạng SAN, tên property đã kiểm chứng trong source gRPC. **Thứ vội là quyết
định PHẠM VI, không phải tay nghề.** Đừng đọc file này như một lời phê tay nghề.

### 4.2. Bằng chứng đối chứng: chính framework này đã từng làm ĐÚNG với y hệt loại yêu cầu

Tháng 6, cùng kênh, cùng loại yêu cầu. Wishlist ghi lại lý lẽ khi đánh giá `PEER_CN`:

> Lưu vào `request_context` dưới **key trung tính** (vd `peer_cn`), **KHÔNG đóng cứng ngữ nghĩa
> `caller_service_id`**. Lý do: CN có thể là định danh service **HOẶC** `owner_app_identity_id`
> của APPLICATION subject - **app tự diễn giải**, đúng pattern `_peercred.py` lưu **sự thật thô**.

Nguyên tắc đã có, đúng, và viết ra thành chữ. Một tháng sau nó bị bỏ qua.

### 4.3. Câu văn chính xác nơi ranh giới bị trượt

`peer-app-id-tu-san-cert.md` mục 4.4:

> Có thể kiểm độ dài 33 ký tự trước khi lưu (fail-soft: sai độ dài -> coi như không có).
> **Đây là kiểm định dạng, không phải kiểm nghiệp vụ, nên vẫn đúng ranh giới framework.**

Và mục 8 "Ràng buộc phải giữ" của cùng tài liệu:

> **Key trung tính.** Đặt tên `peer_app_id`, không phải `application_id` hay
> `owner_app_identity_id` - framework không gắn ngữ nghĩa nghiệp vụ.

⭐ **Kỷ luật còn nguyên, nhưng bị áp vào SAI BỀ MẶT.** Người viết nhớ trung tính hoá **cái
tên**, quên mất **cái giá trị**. Ranh giới được kiểm ở chỗ dễ thấy, không được kiểm ở chỗ thật
sự chở khái niệm ngoài vào.

### 4.4. Hai cơ chế khiến người cẩn thận vẫn trượt

**a. Framework bị xếp vào cùng bảng việc với các service của nền tảng.** Bảng của khảo sát xếp
`M1 | framework chưa đọc SAN | phạm vi sửa: xime framework` **cùng cột** với `M2, M3, M4 |
data-service`. Tài liệu thiết kế mở đầu: *"Framework là **mắt xích đầu tiên** trong 4 mắt xích
còn đứt."*

> Khoảnh khắc gọi framework là *"mắt xích 1 trong 4 mắt xích của nền tảng"*, ta đã thôi coi nó
> là một sản phẩm độc lập. Trong khung nhìn đó, *"framework đọc `xime-app://`"* là việc hoàn
> toàn hợp lý - **không ai thấy có gì sai cả.**

**b. Cụm từ "kiểm định dạng" nghe như chuyện kỹ thuật thuần tuý.** Nhưng `33` không phải định
dạng phổ quát - nó là hệ quả của việc application-service chọn KSUID 24 byte + Base62 pad trái.

> **Coupling không lọt vào qua sự cẩu thả. Nó lọt vào khi được dán nhãn là chuyện kỹ thuật, và
> khi framework được xếp vào cùng danh sách công việc với các thành phần của nền tảng.**

⚠ Đối chứng cho thấy điều này tránh được: bản Java của `organization`/`payment` làm cùng việc và
**tự khai bất biến chéo repo ra thành chữ**: `/** Base62 của 24 byte, pad trái - phải khớp
AppIdentityCodec của Trust. */`. Cùng một sự phụ thuộc, một bên gọi tên nó ra, một bên gọi nó là
chuyện kỹ thuật.

## 5. Số đo quyết định: người dùng đã bỏ phiếu bằng chân

Đo 2026-08-17 trên toàn bộ `D:\code\xime` + `D:\code\Monolithic`:

| Thứ framework cấp | Tính chất | Repo dùng helper | Repo tự viết lại |
| --- | --- | --- | --- |
| `current_caller()` (CN) | **trung tính** | **4/4** (`data`, `lưu trữ/data`, `notification`, `placement`) | **0** |
| `current_app_id()` | **mang khái niệm Xime** | **1/5** (chỉ `data`) | **4/5** |

Và phép đo thứ ba là phép đo quyết định: **`grep x509_common_name` ngoài framework ra RỖNG.**
Không repo nào tự đi lấy CN.

> **Helper trung tính: 100% dùng, 0% tự viết. Helper mang khái niệm nền tảng: 20% dùng, 80% tự
> viết.** Cùng framework, cùng loại việc, cùng những người viết. Khác duy nhất một biến.

**Bốn repo tự viết KHÔNG phải vì không biết:** framework 0.6.3 ra 2026-07-29, họ viết
2026-07-31 → 08-01, và docstring của họ **liệt kê framework ra** rồi vẫn không gọi:

> *"Khuôn này đã có ở payment-service, **ở framework (`PEER_APP_ID`)** và ở HR - COPY, đừng viết
> lại."*

**Cơ chế có khả năng nhất:** `payment-service` (Java) đọc SAN từ 2026-07-29 và **buộc phải tự
viết** vì không dùng được framework Python. Rồi HR lấy payment làm khuôn, ba repo sau copy HR.
Một cách làm sinh ra vì bắt buộc ở Java đã thành "bản chuẩn" cho các service Python vốn có sẵn
đường dùng framework.

📌 Điều này đáng ghi độc lập với chuyện trung tính: luật *"phần code lặp lại thì COPY từ bản
chuẩn"* của workspace **chưa nói bản chuẩn nào thắng khi có hai bản ở hai ngôn ngữ**.

**Bằng chứng phụ ủng hộ nguyên tắc "sự thật thô":** ba repo dùng `current_caller()` cho ba việc
khác nhau hẳn (allowlist phân quyền · `caller_service_id` cho log · `caller_cn` ghi vết) mà
**không ai phải sửa framework**. Đúng y lý lẽ 0.4 đã dự đoán.

## 6. Vì sao `PEER_SANS` mà không phải `PEER_SAN_URIS`

Tên `..._URIS` **nói sai về nội dung**. `x509_subject_alternative_name` của gRPC Python là
**danh sách phẳng, KHÔNG gắn nhãn loại**:

```
spiffe://cluster.local/ns/default/sa/api    ← URI
localhost                                    ← DNS
127.0.0.1                                    ← IP
acme-workload://team-7/checkout              ← URI
```

Bốn entry, một danh sách, không nhãn. (Bản Java **có** nhãn - `SAN_TYPE_URI = 6` - vì API Java
trả cặp `(type, value)`. Python thì không.)

Nên đặt tên `..._URIS` mà bên trong có `localhost` và `127.0.0.1` là **một cái tên nói sai về
giá trị nó chở** - đúng loại lỗi đang đi dọn. Và lọc theo `://` cho khớp cái tên thì lại là
**diễn giải**, thứ vừa quyết đưa ra khỏi framework.

## 7. Hai góc nhìn đã cân, và vì sao chỉ lấy tầng nền

| | Góc 1: cho khai báo scheme | Góc 2: trả thô, app tự làm |
| --- | --- | --- |
| Ủng hộ mạnh nhất | **6 bản sao trong nhà đã chứng minh** hướng ngược lại thất bại, và 4 bản viết **kém hơn** bản chuẩn (thiếu xử lý `URI:`, thiếu kiểm độ dài) | Là nguyên tắc framework **tự viết ra ở 0.4**, và `_peercred.py` đã có bản làm đúng |
| Chi phí | Framework vẫn biết khái niệm *"định danh nằm trong một SAN URI"* - mỏng hơn, nhưng không bằng 0 | Bài toán 6 bản sao quay lại, lần này ở người ngoài |

**Chủ dự án chọn tầng nền, không lấy tầng tiện.** Phương án hai tầng (`PEER_SANS` + một
`configure_peer_identity()` tuỳ chọn) đã được cân và **bác**.

⚠ **Nếu về sau ai định thêm lại tầng tiện thì đọc hai điều này trước:**

1. **Đừng đặt vào `application.yml`.** Theo [`rules/config-discovery.md`](../rules/config-discovery.md),
   scheme SAN **không đổi giữa dev và prod** nên nó là *quyết định kiến trúc của Developer*, tức
   thuộc **Python qua `configure_*`**. Cùng phép kiểm đã dùng để xếp đường dẫn cert TLS vào YAML
   nhưng `configure_grpc_tls(provider=...)` vào Python.
2. **Cẩn thận với chữ "cho chọn trả về trường nào của cert".** Đường đó dẫn tới issuer, serial,
   fingerprint - và để làm được thì framework **phải parse X.509**, tức mất đi tính chất sạch
   nhất của cả cơ chế. Ai cần trường khác thì tự đọc cert bằng `cryptography`.

## 8. Ai bị ảnh hưởng

| Repo | Tình trạng |
| --- | --- |
| **`Base Platform/data`** | ✅ **ĐÃ SỬA XONG cùng ngày, 387 test xanh** (382 cũ + 5 mới). Hỏng ngay lúc gỡ (`ImportError`), phiên của họ tự sửa sau khi nhận thông báo. Họ thêm `_app_id_from_peer_sans()` và **ba nhánh trước nay không chạm tới được nay đã có test** - đúng phép phân biệt mà phép kiểm độ dài 33 đang xoá |
| 4 Service ngang (`crm`, `giao-viec`, `nhan-su-cham-cong`, `so-thu-chi`) | ✅ **Không ảnh hưởng** - họ tự đọc `auth_context()`. **Đã thông báo** (xem dưới) |
| 2 repo Java (`organization`, `payment`), `Trust`, 16 app dọc | ✅ Không ảnh hưởng |
| `D:\code\Monolithic` | ✅ Không dính gì - không file nào chứa `xime-app` hay `current_app_id` |

⚠ **Editable install nên không có thời gian ân hạn**: khoảnh khắc `current_app_id` bị xoá là
`data-service` import lỗi, không có bản cũ để rơi về.

**Ba dòng data-service cần sửa** (việc của phiên họ):

```python
# ResolveSubject.py
_LABEL, _SCHEME = "URI:", "xime-app://"

def _app_id_from_peer_sans() -> str | None:
    for entry in current_peer_sans() or ():
        value = entry.removeprefix(_LABEL)   # nhãn loại SAN nếu transport có thêm
        if value.startswith(_SCHEME):        # NEO ĐẦU chuỗi, đừng dùng find()
            return value[len(_SCHEME):]
    return None
```

> ### ⚠ Đoạn mẫu ĐẦU TIÊN tôi viết cho họ SAI, và phiên `data-service` bắt được
>
> Bản đầu chỉ có `s.startswith(_SCHEME)`, **không cắt nhãn `URI:`**. Nó chỏi với chính bảng hợp
> đồng ngay dưới nó, chỗ ghi framework *"trả nguyên văn, kể cả nhãn `URI:` nếu transport có
> thêm"*. Chép nguyên si thì cert dạng `URI:xime-app://...` **rơi im lặng thành `None`**, tức
> thành *"thiếu Authorization"* - **đúng loại hỏng mà cả bản vá này sinh ra để gỡ**.
>
> Họ chọn `entry.find(...)` để bù, và **đúng ở vế họ nhìn**: bản framework cũ so theo vị trí kèm
> chú thích *"grpc có thể trả URI trần hoặc kèm tiền tố loại SAN, cả hai đều phải chạy"*.
>
> ⚠ **Nhưng `find()` mở một lỗ khác**, và đó là lý do đoạn mẫu nay có hai dòng thay vì một:
> tìm chuỗi con ở bất kỳ đâu sẽ nhận cả `https://example.com/?redirect=xime-app://attacker` -
> entry đó **chứa** scheme mà không **thuộc** scheme. Đây đúng là mục **F9** của kế hoạch bảo
> mật, thứ tôi khai là *"đã bị xoá"* ở mục 9.3 - nó bị xoá **khỏi framework**, nhưng lời cảnh
> báo thì **di trú sang mọi bên gọi**, và tôi đã không nói ra điều đó khi viết đoạn mẫu.
>
> **Dạng đúng là cắt nhãn RỒI neo đầu** - an toàn cả hai chiều. Đã sửa ở: docstring
> `current_peer_sans()` (đi lên PyPI), `CHANGELOG`, file này, và thông báo của cả 5 repo.
>
> 📌 Bài học: **`find()` và `startswith` không phải hai lựa chọn phong cách; chúng là hai lỗ hổng
> ngược chiều nhau, và lời giải nằm ở chỗ thứ ba.** Bản framework cũ chọn một vế và có F9 để trả
> giá; đoạn mẫu đầu của tôi chọn vế kia mà không biết mình đang chọn.

⭐ Sửa xong thì **xoá luôn được câu chú thích sai** ở dòng 71-73 của họ, vì từ nay chuỗi sai độ
dài thật sự tới được `IdService.from_string()`.

### Đã thông báo cho 5 repo (2026-08-17, theo chỉ đạo chủ dự án: ghi thẳng vào `CLAUDE.md` + `.claude/` của họ)

| Repo | Ghi gì |
|---|---|
| `Base Platform/data` | Khối cảnh báo **đầu `CLAUDE.md`** + `.claude/docs/framework-go-current-app-id-2026-08-17.md` |
| 4 Service ngang | Khối ở **đầu `CLAUDE.md`** + `.claude/docs/framework-doi-cach-doc-san-2026-08-17.md` mỗi repo |

⚠ **Nội dung gửi 4 Service ngang KHÁC câu tóm tắt ban đầu, vì phép đo cho kết quả khác.** Câu
giao việc là *"bản tự viết của họ lỏng hơn bản chuẩn"*. Đọc code cả 4 (chúng giống hệt nhau) thì
ra bốn khác biệt, và chúng **không cùng loại**:

| Khác biệt | Còn là "lỏng hơn" không |
|---|---|
| `gia_tri.decode()` trần → ném `UnicodeDecodeError`, **phá fail-soft**, và entry rác che luôn entry hợp lệ đứng sau | ✅ **Có, và đây là chỗ nặng nhất** |
| Chỉ tra khoá `str`, không tra khoá `bytes` | ✅ Có |
| `startswith` không chấp dạng `URI:` | ⚠ **Đổi loại**: trước là "framework che hộ", nay là **câu hết ai sở hữu** |
| Không kiểm độ dài 33 | ❌ **KHÔNG còn là thiếu sót** - framework vừa cố ý bỏ phép kiểm đó |

Và thứ **chắc chắn** cần họ sửa lại không nằm trong bốn cái trên: **docstring của họ trỏ vào
`PEER_APP_ID`, một API vừa bị xoá** - con trỏ chết.

⚠ Cũng đã khai rõ với họ rằng **hai gap thật hiện chưa với tới được** (Trust đặt SAN dạng ASCII),
để họ không phải vá gấp một thứ không đang chảy máu. Ghi ra ở đây vì đó là phần dễ bị lược mất
khi truyền tin qua nhiều lớp.

## 9. Việc còn để mở

### 9.1. ⛔ CÒN NỢ: năm chỗ docstring vẫn nhắc tên service nội bộ

Đợt này **chỉ dọn phần code và `README`**, chưa dọn văn xuôi trong docstring. Năm chỗ sau vẫn
đang đi lên PyPI cho người lạ đọc:

| Chỗ | Nội dung |
|---|---|
| `adapters/grpc/tls/_config.py:10` | *"internal servers use the Trust-issued certificate"* |
| `adapters/grpc/tls/_provider.py:32` | *"resolver synchronized from Trust Service"* |
| `adapters/web/_adapter.py:164-165` | ví dụ cert dùng `gym.xime.vn` |
| `starters/jwt/_middleware.py:32` | *"(dental-clinic #001)"* - số hiệu issue của một app nội bộ |
| `adapters/web/middleware/_context.py:17` | *"(dental-clinic #001)"* |

Với người ngoài thì `Trust Service` là danh từ vô nghĩa và `dental-clinic #001` là thứ họ không
có cách nào tra. **Sửa chữ, không đụng logic, khoảng 15 phút.** Chưa làm vì chủ dự án hoãn cả
nhóm việc này (xem 9.2).

### 9.2. Test canh nguyên tắc - CHỦ DỰ ÁN HOÃN (2026-08-17)

Đề xuất: quét hằng số và văn xuôi trong `xime/` tìm khái niệm của bên ngoài, có **danh sách cho
phép tường minh** cho namespace của chính framework (`xime-error`, `_xime_route_info`,
`xime.di.dynamic-binding`, `http://xime.dev/opcua`...), kèm **positive control** chứng minh phép
dò biết kêu.

⚠ **Giới hạn đã khai trước khi đề xuất, và nó là lý do đáng hoãn:** phép dò này **không bắt được
`_APP_ID_LENGTH = 33`**, vì đó chỉ là một con số, không có từ khoá nào để khớp. Nó bắt được
**cửa vào** (chuỗi scheme), và số 33 chỉ có nghĩa khi đi kèm scheme - nhưng ai hardcode một luật
định dạng mà không kèm chuỗi nào thì guard im lặng. Đúng cảnh báo của [luật 03 mục 4b](../../../.claude/rules/03-mot-gia-tri-mot-nghia.md):
*kết quả rỗng của một phép dò mang hai nghĩa*.

Điều kiện tiên quyết nếu có ngày làm: **dọn 9.1 TRƯỚC rồi mới bật guard.** Bật rồi cho 5 chỗ đó
vào danh sách cho phép là biến guard thành thứ hợp pháp hoá đúng cái nó sinh ra để chặn.

### 9.3. Còn lại

- **Web adapter không đọc client cert** (mục 2). Hiện trạng, chưa ai mở việc.
- ⚠ **F9 KHÔNG đơn giản là "bị xoá" - nó DI TRÚ.** Bản đầu của mục này khai *"F9 bị xoá, không
  phải được vá"* vì framework không còn chuỗi nào để neo. **Câu đó chỉ đúng trong phạm vi
  framework.** Lỗ hổng F9 mô tả (`find()` khớp scheme ở **bất kỳ đâu** trong entry, nên
  `https://example.com/?redirect=xime-app://attacker` được nhận) **nay là bài toán của mọi bên
  gọi**, vì chính họ là người khớp scheme.

  Nên nghĩa vụ của framework đổi từ *"tự neo đúng"* sang *"nói cho bên gọi biết phải neo"*. Đã
  làm: docstring `current_peer_sans()` cảnh báo tường minh đừng dùng `find()`/`in`, và đoạn mẫu ở
  cả `CHANGELOG` lẫn 5 thông báo đều dùng **cắt nhãn rồi neo đầu**.

  📌 Đây là khuôn đáng nhớ: **gỡ một thứ ra khỏi framework không xoá được bài toán nó đang giải -
  chỉ chuyển bài toán sang người dùng.** Gỡ mà không kèm cảnh báo là đẩy nợ đi mà không nói.
- **Câu `URI:` nay HẾT AI SỞ HỮU.** Bản cũ dùng `find()` nên chấp được dạng `URI:xime-app://...`;
  nay framework trả thô nên câu *"gRPC có bao giờ trả kèm nhãn `URI:` không"* không còn ai trả
  lời. Thực tế đang chạy là dạng trần nên hôm nay không ai gãy, nhưng nếu đổi thì **mọi bên gọi
  cùng gãy một lúc**. Đã ghi vào thông báo của cả 5 repo, và đoạn mẫu đã cắt nhãn phòng trước.

## 10. Liên quan

- [`peer-app-id-tu-san-cert.md`](peer-app-id-tu-san-cert.md) - thiết kế gốc 0.6.3. **Giữ làm
  lịch sử**, đừng đọc như hiện trạng. Mục 4.4 và 4.5 của nó là chỗ ranh giới bị trượt
- [`phu-thuoc-bac-cau-chua-khai-2026-08-17.md`](phu-thuoc-bac-cau-chua-khai-2026-08-17.md) - ba
  ca phụ thuộc bắc cầu, làm cùng đợt này
- [`../rules/config-discovery.md`](../rules/config-discovery.md) - phép kiểm YAML hay Python
- [luật 03 của workspace](../../../.claude/rules/03-mot-gia-tri-mot-nghia.md) - `None` hai nghĩa
