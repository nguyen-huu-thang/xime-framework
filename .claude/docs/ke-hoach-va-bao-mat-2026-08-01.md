# Kế hoạch vá - kiểm toán bảo mật 2026-08-01

> Phát hiện gốc: [`kiem-toan-bao-mat-0.7.md`](kiem-toan-bao-mat-0.7.md) (24 mục, 12 PoC).
> File này trả lời câu khác: **sửa cái gì, ở đâu, theo thứ tự nào, và kiểm chứng ra sao.**
>
> Trạng thái: **ĐỢT 2 XONG 2026-08-03** (bản 0.7.1) - mười mục framework đã vá,
> có test canh, PoC chạy lại đạt. **Đợt 0, 1, 3, 4, 5 chưa thi công.**
> Kết quả chi tiết + bốn thứ đổi hành vi: [`ket-qua-0.7.1-2026-08-03.md`](ket-qua-0.7.1-2026-08-03.md).

---

> **Phần CHƯA quyết nằm ở file riêng:** [`cho-quyet-bao-mat-2026-08-01.md`](cho-quyet-bao-mat-2026-08-01.md)
> - 5 mục, kèm khuyến nghị và thứ mỗi mục đang chặn. Mục 1 ở đó (**secret để ở file nào**) đang
> chặn đúng đường găng của đợt 0, quyết nó trước.

## 0. Quyết định của chủ dự án (bốn mục chốt 2026-08-01, thêm A6 ngày 2026-08-18)

| Câu hỏi | Đã chốt | Kéo theo gì |
|---|---|---|
| **A6 - secret để ở file nào** (2026-08-18) | ⭐ **Hướng B: dùng `application-{env}.yml` sẵn có. KHÔNG đụng framework** | **Đợt 0 hết bị chặn.** Không thêm tầng nạp config thứ ba, nên không chạm hành vi khởi động của 31 app. ⚠ Kèm một việc bắt buộc: **sửa chú thích trỏ sang `application-secret.yml`** ở mọi `application-production.yml` và ở `saas-foundation/template` - framework **không bao giờ nạp** file đó, để nguyên là mời người sau đặt secret vào chỗ vô hiệu |
| `shop` đổi `jwt.secret` thì người dùng bị đăng xuất hết | **Đổi ngay, chấp nhận đăng xuất** | Không cần cơ chế hai khóa, không cần thời gian ân hạn. Đợt 0 gọn hơn hẳn |
| Vá framework phát hành thế nào | ~~**Vá trong repo, CHƯA đẩy PyPI**~~ → **đã đẩy 0.7.1** | Câu chốt gốc đúng ở thời điểm nó ra. Nay PyPI có 12 bản (`0.1.0` -> `0.7.1`), người ngoài không còn kẹt ở 0.7.0 |
| Một adapter chết | **Cô lập sau khi đã phục vụ** | F10 thành việc thiết kế thật, không phải sửa một dòng. ~~Đợt 3~~ **đã dời sang 0.8** vì nó mở rộng `Adapter` protocol, tức đổi API |
| Lối thoát dev khi thiếu khóa JWT | **Cờ tường minh trong YAML** | `auth.jwt.allow_insecure_dev: true`, phải gõ tay. Không dựa vào `XIME_ENV`.<br>⚠ **Chưa hiện thực, và bản vá 2026-08-18 đã đổi bối cảnh của nó**: `configure_jwt()` không có nguồn khóa nay **nổ lúc khởi động**, nên cờ này (nếu làm) là đường mở khóa tường minh cho ca dev, không còn là thứ chặn fail-open |

---

## 1. Hai sự thật về môi trường, đọc trước khi làm bất cứ gì

### 1.1. Một lần sửa framework là chạm vào cả 31 app NGAY LẬP TỨC

```
site-packages/_editable_impl_xime.pth  ->  D:\code\xime\xime framework\xime\
```

`xime` được cài **editable**, và **không app nào có venv riêng** (đã tìm: không có `.venv`,
không có `venv` ở đâu trong cả hai workspace). Cả 31 codebase chạy chung một Python 3.14 hệ
thống.

Hai hệ quả ngược chiều nhau, phải nhớ cả hai:

- **Tốt:** quyết định "vá trong repo, chưa đẩy PyPI" hoạt động hoàn hảo - sửa file trong
  `xime/` là 31 app có bản vá ngay, không phải cài lại gì.
- **Nguy:** không có vùng đệm. Một bản vá framework làm gãy thứ gì đó là **gãy đồng thời ở
  31 chỗ**. Nên mọi thay đổi ở đợt 2 phải chạy `pytest` của framework **và** bộ test của ít
  nhất 3 app trước khi coi là xong.

### 1.2. `xime.__version__` đang nói dối

```
pyproject.toml          version = "0.7.0"
xime.__version__        0.6.3
dist-info               xime-0.6.3.dist-info
code thực sự chạy       D:\code\xime\xime framework\xime\   (0.7.0)
```

Bản editable được cài từ hồi 0.6.3 nên metadata đứng yên, trong khi code thì đã là 0.7.0.
`xime.__version__` đọc metadata (`importlib.metadata`) nên nó trả **0.6.3**.

**Đừng dùng `xime.__version__` để xác nhận bản vá đã vào chưa** - nó sẽ trả 0.6.3 cả trước lẫn
sau. Kiểm bằng hành vi (chạy PoC) hoặc bằng `grep` vào file nguồn.

Việc dọn chuyện này (`pip install -e . --force-reinstall`) **không** nằm trong kế hoạch vá - nó
là việc vệ sinh riêng, và làm lúc đang vá thì lẫn lộn nguyên nhân khi có gì hỏng.

---

## 2. Bốn nguyên tắc của đợt vá này

1. **Sửa nguồn trước, bản sao sau.** `saas-foundation/template` là nguồn của 20 app. Sửa
   template trước rồi mới lan, kẻo app thứ 22 mang lại lỗi cũ.
2. **Mỗi bản vá phải có cách chứng minh nó có tác dụng.** PoC nào đã bắt được lỗi thì sau khi
   vá phải chạy lại chính PoC đó và thấy nó chuyển sang ĐẠT. Không có PoC thì viết test.
3. **Không gộp vá bảo mật với refactor.** Mỗi commit một mục, ghi mã phát hiện (A1, F2...)
   trong message. Cần revert thì revert được đúng một thứ.
4. **Vá xong một đợt thì cập nhật trạng thái** ở cả báo cáo gốc lẫn 28 file
   `canh-bao-bao-mat-2026-08-01.md` trong các repo. Tài liệu nói "CHƯA VÁ" trong khi đã vá là
   cách nhanh nhất để phiên sau làm lại từ đầu.

---

## ĐỢT 0 - Trong ngày: chặn thứ đang chảy máu

### 0.1. `shop` - đổi chuỗi ký JWT và giết token cũ (A3)

**Vì sao đứng đầu:** đây là chỗ duy nhất vừa có secret nằm trong git, vừa đã deploy thật
(`shop.scime.click`). Mọi mục khác là nguy cơ; mục này là cửa đang mở.

**Làm gì**

1. Sinh secret mới: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
2. Đặt vào `Monolithic/shop/backend/resources/application-production.yml` dưới khối `jwt:`
   (file này đã có sẵn và đã trong git - **xem bước 4, đây chỉ là chỗ tạm**).
3. **Xóa** giá trị fallback trong code:
   `app/service/authentication_service.py:30`
   ```python
   # trước
   self._secret: str = config.get("jwt.secret", "dev-secret-CHANGE-IN-PRODUCTION")
   # sau - thiếu cấu hình thì NỔ, không âm thầm dùng chuỗi đoán được
   secret = config.get("jwt.secret")
   if not secret or secret.startswith("dev-secret"):
       raise RuntimeError("jwt.secret chưa được cấu hình (hoặc còn là giá trị dev mẫu)")
   self._secret = secret
   ```
4. **Dứt secret ra khỏi git.** Đây là chỗ vướng A6 - xem 0.2 ngay dưới. Trước khi 0.2 xong
   thì cách tạm là `application-secret.yml`... **không dùng được** (framework không nạp).
   Nên thứ tự đúng là: **làm 0.2 trước, rồi quay lại bước này.**
5. Vô hiệu token đang sống: bảng blacklist hiện chỉ chặn theo `jti` khi logout, không chặn
   hàng loạt. Vì secret đổi, **mọi token ký bằng secret cũ tự động fail chữ ký** - tức là
   việc "giết token cũ" xảy ra miễn phí khi đổi secret. Không phải làm gì thêm.
6. Thông báo cho người dùng: đăng nhập lại một lần. (Chủ dự án đã chấp nhận.)

**Kiểm chứng:** lấy một token cũ còn hạn, gọi một endpoint cần đăng nhập, phải nhận 401
`E1020`. Đăng nhập lại, token mới phải chạy.

**Rủi ro:** nếu `XIME_ENV` không được đặt thành `production` trên máy chủ thì
`application-production.yml` **không được nạp** và secret mới không có tác dụng - app quay về
giá trị trong `application.yml`. **Kiểm biến môi trường trên máy chủ TRƯỚC**, đây đúng là bẫy
F7 (thiếu profile thì im lặng).

### 0.2. Chốt chỗ để secret, vì A3 không xong được nếu không có (A6)

Chú thích trong `application-production.yml` bảo để secret vào `application-secret.yml`, nhưng
`YamlConfigLoader.load()` chỉ nạp `application.yml` + `application-{env}.yml`. File đó không tồn
tại và không bao giờ được đọc.

**Hai hướng, cần chọn một** (tôi khuyến nghị hướng B):

| | Hướng A: thêm tầng thứ ba vào framework | Hướng B: dùng `application-local.yml` đã có |
|---|---|---|
| Sửa gì | `loader.py` nạp thêm `application-secret.yml` sau cùng | Không sửa framework, chỉ sửa chú thích ở các app |
| Ưu | Đúng thứ tài liệu đã hứa; tách bạch secret khỏi cấu hình | Không đụng framework, không rủi ro cho 31 app |
| Nhược | Đổi hành vi nạp config của cả 31 app; thêm một chỗ nữa để quên | `application-local.yml` mang nghĩa "máy của tôi", dùng cho production hơi lệch nghĩa |
| Hợp khi | Muốn quy ước lâu dài, rõ ràng | Muốn xong đợt 0 nhanh và không đụng framework |

Chọn B thì phải sửa chú thích ở **mọi** `application-production.yml` và trong tài liệu template,
nếu không lần sau lại có người tin vào file không tồn tại.

### 0.3. Năm app Monolithic còn lại - đổi secret trước khi deploy (A3)

`auto-garage`, `dental-clinic`, `english-center`, `rental-management`, `spa` dùng **đúng cùng
một chuỗi** với `shop`. Chưa deploy nên chưa gấp, nhưng làm luôn trong đợt 0 vì nó chỉ là copy
việc 0.1 sang 5 chỗ, và để không ai lỡ tay deploy trước khi vá.

Mỗi app **một giá trị riêng** - đừng sinh một chuỗi rồi dán cả 6 chỗ, vì như thế chỉ đổi từ
"secret công khai dùng chung" sang "secret bí mật dùng chung", vẫn là một điểm gãy duy nhất.

---

## ĐỢT 1 - Chặn máu ở tầng ứng dụng (21 + 23 codebase)

Đợt này **không đụng framework**, chỉ sửa file cấu hình và một hàm trong mỗi app. Rủi ro thấp,
lợi ích lớn nhất trên mỗi giờ bỏ ra.

### 1.1. A1 - đảo fail-open thành fail-closed (21 codebase)

> #### 📊 ĐO LẠI 2026-08-04 bởi phiên framework - **19/21 còn hở, 2 đã vá**
>
> Đọc mã cả 21 file thay vì chép lại con số cũ:
>
> ```text
> 21 file  app/config/jwt.py
> 19 file  VẪN fail-open  (keyset is None -> log warning -> return, KHÔNG cài middleware)
>  2 file  ĐÃ VÁ          san-the-thao · cho-thue-thiet-bi
> ```
>
> **a. Đã có bản mẫu chạy được, chép thẳng - đừng thiết kế lại.**
> `Application Layer/san-the-thao/backend/app/config/jwt.py` hiện thực đúng khối mã bên dưới,
> kèm `logger.critical` khi cờ dev bật. Họ dùng đúng `get_bool(...)` chứ không `get(...)`.
>
> **b. ⚠ `saas-foundation/template` NẰM TRONG NHÓM 19 CHƯA VÁ - vá nó TRƯỚC.**
> 18 file kia là nợ **đứng yên**; template là nợ **đang sinh sôi**, vì mọi app clone từ nay đều
> thừa hưởng lỗ hổng. Vá template là **chặn nguồn**, đáng tách thành việc riêng làm trước.
>
> **c. Gốc rễ nằm ở framework, không phải ở 21 app.** Vì sao cả 21 repo tự viết
> `TrustJwtAuthMiddleware` thay vì dùng `configure_jwt`: `JwtMiddlewareConfig.key_context` là
> **đúng một khoá tĩnh**, và `grep kid` trong `starters/jwt/` chỉ ra **một** chỗ - `_signer.py`
> lúc KÝ. Phía verify **không có dòng nào** xử lý `kid`. Framework ký được kèm `kid` nhưng
> không verify theo `kid`, không giữ bộ nhiều khoá, không làm tươi khi Trust xoay khoá.
>
> > **A1 không phải 21 lỗi độc lập. Nó là MỘT khoảng trống của framework, nhân lên 21 lần** -
> > phần khó nhất của thứ mọi app phải tự viết là *"không có khoá thì làm gì"*, và 19/21 quyết
> > định sai theo cùng một kiểu. Vá 19 file xong, app thứ 22 vẫn sẽ tự viết và tự quyết lại.
>
> **Đề xuất kèm theo (CHƯA LÀM, chờ chủ dự án):** đưa keyset nhiều khoá theo `kid` + tự làm tươi
> + fail-closed vào starter JWT của framework, để quyết định đó được quyết **một lần, một chỗ**.
> Xếp vào loại hỏi chủ dự án vì nó thêm API công khai vào gói MIT đã phát hành, và vì fail-closed
> mặc định có thể làm app đang chạy dừng khởi động.
>
> ⚠ Giới hạn của phép đo: khớp theo **hình dạng mã** (`keyset is None` rồi `return`). Repo viết
> fail-open theo hình dạng khác thì phép dò **không kêu**. Nên **19 là cận dưới**.

**Sửa ở đâu:** `app/config/jwt.py`, hàm `configure()`, nhánh `if keyset is None`.

**Sửa thành gì** (theo quyết định "cờ tường minh trong YAML"):

```python
def configure() -> None:
    config = _load_config()
    keyset = _build_keyset(config)

    if keyset is None:
        # Không có khóa verify = không có xác thực. Đây phải là lỗi khởi động,
        # không phải cảnh báo: app chạy tiếp nghĩa là mọi API thành công khai.
        if not config.get_bool("auth.jwt.allow_insecure_dev", False):
            raise StartupException(
                "\nKhông có khóa verify JWT\n"
                "  Nguyên nhân: trust.enabled=false (hoặc thiếu application.yml) "
                "VÀ không có auth.jwt.public_key_pem/public_key_file\n"
                "  Hệ quả nếu bỏ qua: app chạy KHÔNG CÓ xác thực, mọi API công khai\n"
                "  Sửa    : bật trust.enabled, hoặc khai public_key_pem\n"
                "  Chỉ DEV: đặt auth.jwt.allow_insecure_dev: true trong "
                "application-local.yml"
            )
        logger.critical(
            "CHẠY KHÔNG CÓ XÁC THỰC - auth.jwt.allow_insecure_dev đang bật. "
            "TUYỆT ĐỐI không dùng cấu hình này ngoài máy dev."
        )
        return

    configure_middleware(TrustJwtAuthMiddleware, ...)   # như cũ
```

Ba chi tiết cố ý:

- Dùng **`get_bool`** chứ không `config.get(...)`. `bool("false")` là `True`, nên đọc bằng
  `get()` trần thì viết `allow_insecure_dev: "false"` trong YAML lại **bật** chế độ mở. Đây
  đúng là cái bẫy `get_bool` sinh ra để chặn.
- Log mức **`critical`** chứ không `warning`. Warning trôi mất trong log khởi động.
- Thông báo lỗi nêu **hệ quả** ("mọi API công khai"), không chỉ nêu triệu chứng. Người đọc log
  lúc 2 giờ sáng cần biết ngay mức độ.

**Thứ tự thi công**

1. Sửa `Application Layer/saas-foundation/template/app/config/jwt.py` trước.
2. Chạy test của template.
3. Lan sang 20 repo. Vì đoạn code giống hệt nhau, viết một script vá thay vì sửa tay 20 lần -
   nhưng **chạy test từng repo sau khi vá**, đừng vá cả loạt rồi mới test.
4. Repo nào có `application.yml` với `trust.enabled: true` (đã kiểm: hầu hết) thì sau khi vá
   vẫn khởi động bình thường. Repo nào nổ nghĩa là repo đó **đang chạy không xác thực** - đó
   là phát hiện, không phải lỗi của bản vá.

**Kiểm chứng:** tạm đổi `trust.enabled` thành `false` ở một app, khởi động, phải thấy
`StartupException` chứ không phải app lên và trả 200.

### 1.2. A2 - gỡ regex CORS khớp mọi IP công cộng (23 codebase)

**Sửa ở đâu:** `resources/application.yml`, khóa `cors.allow_origin_regex`.

**Cách sửa - hai bước, đừng bỏ bước hai:**

1. **Xóa dòng `allow_origin_regex` khỏi `application.yml`** (file gốc = file dùng khi deploy).
2. **Chuyển nó xuống `application-local.yml`** với regex đã siết về đúng dải riêng tư:

```yaml
# application-local.yml - CHỈ máy dev, không bao giờ đi kèm khi deploy
cors:
  allow_origin_regex: '^http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?$'
```

Bỏ bước hai thì lập trình viên mở app bằng IP LAN sẽ vấp CORS, rồi sẽ có người dán lại regex
cũ vào `application.yml` cho nhanh - và ta quay về điểm xuất phát sau ba tuần.

`Base Platform/data` cũng nằm trong danh sách 23 này (`resources/application.yml`), đừng bỏ sót
vì nó không phải app dọc.

**Kiểm chứng:** chạy `.claude/scripts/bao-mat/poc_cors_real.py` sau khi sửa giá trị trong đó
cho khớp cấu hình mới - `http://203.0.113.66` phải **không** còn nhận được `ACAO`.

**Rủi ro:** app nào đang thật sự được truy cập qua IP LAN ở môi trường thật (ví dụ máy tính
quầy trong tiệm gọi backend qua `http://192.168.1.x:8107`) sẽ gãy. Regex ở bước 2 vẫn cho phép
dải `192.168.*` và `10.*`, nhưng **chỉ khi file `application-local.yml` có mặt**. Cần rà lại có
mô hình triển khai nào như vậy không trước khi làm.

### 1.3. A4 - đóng `/docs`, `/redoc`, `/openapi.json` (toàn bộ app)

Bỏ ba đường này khỏi `auth.jwt.public_paths` trong `application.yml`, giữ `/health` và
`/webhooks/payment`. Muốn xem tài liệu API thì đăng nhập rồi mở - middleware sẽ cho qua vì đã
có token.

Chuyển ba đường đó xuống `application-local.yml` nếu muốn mở sẵn lúc dev.

---

## ĐỢT 2 - Framework: những mục vá được ngay

Nhắc lại mục 1.1: mỗi thay đổi ở đây chạm 31 app cùng lúc. Chạy `pytest` của framework
(1463 test) sau **mỗi** mục, không dồn.

### 2.1. F2 - cắt chuỗi XSS lưu trữ (ưu tiên cao nhất trong đợt)

Ba lớp, làm cả ba, vì mỗi lớp một mình đều lách được:

**Lớp 1 - `save_upload` không tin client** (`adapters/web/files/_upload.py:47`)

```python
# Content-Type của phần multipart là do CLIENT khai -> không dùng để quyết định
# trình duyệt sẽ render kiểu gì. Suy từ tên file, không đoán được thì trả về
# kiểu trung tính.
resolved_type = content_type or _sniff_from_name(upload_file.filename)
```
với `_sniff_from_name` dùng `mimetypes.guess_type`, mặc định `application/octet-stream`.
Giữ tham số `content_type` để app nào biết rõ vẫn ép được.

**Lớp 2 - `stream_object` luôn gắn nosniff** (`_download.py`, chỗ dựng `headers`)

```python
headers: dict[str, str] = {
    "Accept-Ranges": "bytes",
    "X-Content-Type-Options": "nosniff",
}
```

**Lớp 3 - ép tải xuống với mọi kiểu không nằm trong danh sách an toàn**

```python
_INLINE_SAFE = {"image/png", "image/jpeg", "image/gif", "image/webp",
                "application/pdf", "video/mp4", "text/plain"}
...
force_download = download or media_type.split(";")[0].strip() not in _INLINE_SAFE
disposition = "attachment" if force_download else "inline"
```
và gắn `Content-Disposition` **kể cả khi không có `filename`** (chỉ `attachment` trần cũng đủ
chặn render).

**Đây là đổi hành vi.** App nào đang dựa vào việc `stream_object` trả `text/html` inline sẽ
đổi cách chạy. Đã quét: không app nào làm vậy, nhưng ghi vào `CHANGELOG.md` mục "hành vi đổi".

**Kiểm chứng:** `poc_web2.py` PoC 8 phải chuyển từ "THỦNG" sang không khai thác được.

### 2.2. F8 - Content-Disposition theo RFC 6266

`_download.py:108`, thay f-string bằng:

```python
from urllib.parse import quote

def _content_disposition(disposition: str, filename: str) -> str:
    # Header HTTP mã hóa latin-1: tên file tiếng Việt ném UnicodeEncodeError ->
    # HTTP 500. RFC 6266 giải bằng cặp filename= (ASCII) + filename*= (UTF-8).
    ascii_name = filename.encode("ascii", "replace").decode("ascii")
    ascii_name = "".join(c for c in ascii_name if c not in '"\\' and c.isprintable())
    return (f'{disposition}; filename="{ascii_name}"; '
            f"filename*=UTF-8''{quote(filename, safe='')}")
```

**Kiểm chứng:** `poc_web.py` PoC 3 - tải file tên `Hóa đơn.pdf` phải ra 200 và trình duyệt
lưu đúng tên có dấu.

Đây là mục **sửa một lỗi đang xảy ra**, không phải phòng ngừa: sản phẩm Việt Nam mà tải file
tên có dấu là 500.

### 2.3. F4 - `configure_cors` ép kiểu và fail-fast

`adapters/web/_cors.py`, sau khi phân giải `FromConfig` (tức là trong `resolve_options` hoặc
ngay trước `add_middleware`), kiểm:

```python
if isinstance(allow_origins, str):
    raise StartupException(
        "\nCORS: cors.allow_origins phải là DANH SÁCH, không phải chuỗi\n"
        f"  Nhận được: {allow_origins!r}\n"
        "  Hệ quả nếu bỏ qua: Starlette so khớp bằng chuỗi con, nên "
        "'https://app.example.co' khớp 'https://app.example.com'\n"
        "  Sửa: cors:\\n  allow_origins:\\n    - \"https://...\""
    )
if "*" in (allow_origins or ()) and allow_credentials:
    raise StartupException(
        "\nCORS: allow_origins ['*'] đi cùng allow_credentials=true là mở toang\n"
        "  Starlette sẽ PHẢN CHIẾU origin của người gọi (không trả '*'), nên "
        "trình duyệt KHÔNG chặn - mọi trang web đọc được dữ liệu kèm cookie."
    )
```

**Và sửa chú thích sai ở đầu file** (dòng 22-23) - hiện nó viết "trình duyệt sẽ chặn", điều đó
không đúng và làm người đọc tưởng framework tự bảo vệ.

**Kiểm chứng:** `poc_web.py` PoC 2 - cả hai ca phải chuyển thành lỗi khởi động.

### 2.4. F5 - che secret trong `__repr__` của `RuntimeConfig`

`core/config/runtime.py`, thêm vào class:

```python
_SENSITIVE = ("secret", "password", "token", "key", "credential", "passwd")

def __repr__(self) -> str:
    return f"RuntimeConfig({self._redacted(self._dump)!r})"

__str__ = __repr__

@classmethod
def _redacted(cls, value, key: str = ""):
    if any(s in key.lower() for s in cls._SENSITIVE) and not isinstance(value, dict):
        return "***"
    if isinstance(value, dict):
        return {k: cls._redacted(v, k) for k, v in value.items()}
    return value
```

`.get()` không đổi - chỉ che lúc in.

**Kiểm chứng:** `poc_config.py` PoC 9 - `repr(cfg)` không còn chứa hai chuỗi bí mật.

### 2.5. F6 - nói ra khi đang chạy chế độ không an toàn

Không đổi mặc định (sẽ phá tương thích), chỉ **log một lần lúc khởi động**:

| File | Thêm gì |
|---|---|
| `adapters/grpc/_adapter.py`, nhánh `add_insecure_port` | `_log.warning("gRPC server '%s' đang chạy PLAINTEXT, không xác thực client. Bật grpc.tls.enabled + mutual để dùng mTLS.", server_id)` |
| cùng file, khi `tls.enabled` nhưng `mutual=False` | cảnh báo riêng: có mã hóa nhưng **ai cũng gọi được** |
| `adapters/opcua/_adapter.py` + `_server.py` khi `security == "None"` | cảnh báo không mã hóa, không xác thực |
| `adapters/mqtt/_adapter.py` khi `tls is None` và có `username` | cảnh báo credential đi trên dây trần |
| `adapters/socket/_peercred.py` khi `read_peer_cred` trả None | cảnh báo một lần: không kiểm được danh tính peer, chỉ còn dựa vào quyền file |

Mục này rẻ và có tác dụng lâu dài: mọi lỗi cấu hình bảo mật về sau sẽ tự lộ ra trong log thay
vì im lặng.

### 2.6. F7 - nói ra khi thiếu file profile

`core/config/loader.py`, trong `load()`:

```python
override_path = self._resources_dir / f"application-{env}.yml"
if not override_path.exists():
    _log.warning(
        "XIME_ENV=%r nhưng không tìm thấy %s - chạy bằng application.yml. "
        "Nếu đây là môi trường thật, cấu hình production KHÔNG được áp dụng.",
        env, override_path,
    )
```

Mục này là mắt xích nối A1 với A3 (0.1 bước 6): nó làm cho "quên đặt `XIME_ENV`" thành một
dòng log thay vì một sự cố im lặng.

### 2.7. F11 - cảnh báo khi `configure_jwt` không ép `audience`

`adapters/web/_adapter.py::_add_jwt_middleware`, sau khi lấy `jwt_config`:

```python
if jwt_config.audience is None:
    _log.warning(
        "configure_jwt() không đặt audience - token cấp cho service khác vẫn "
        "được chấp nhận. Nền tảng dùng chung khóa ký NÊN đặt audience."
    )
```

Không app nội bộ nào dính (cả 21 app dùng middleware tự viết có ép `aud`), nhưng gói đã công
khai trên PyPI nên người dùng ngoài cần biết.

### 2.8. F12 - không gửi tên class exception nội bộ cho lỗi chưa map

`adapters/grpc/interceptors/_error.py`, `_error_metadata` nhận thêm thông tin đã map hay chưa:

```python
def _error_metadata(exc: Exception, mapped: bool) -> tuple[tuple[str, str], ...]:
    name = type(exc).__name__ if mapped else "InternalError"
    return ((XIME_ERROR_METADATA_KEY, name),)
```

Nhất quán với `_safe_details()` vốn đã che `str(exc)` cho lỗi chưa map.

### 2.9. F13 + F16 - dọn localfs

| Mục | Sửa |
|---|---|
| Tên file tạm đụng nhau | `f"{path.name}.{uuid4().hex}.part"` thay `os.getpid()`. Đây là **lỗi toàn vẹn dữ liệu thật**, không phải chỉ bảo mật: hai upload cùng key trong cùng tiến trình đang ghi đè nhau |
| Quyền file | thêm `storage.local.file_mode` (mặc định `0o600`), `os.chmod` sau khi ghi |
| `put()` không nguyên tử | cho đi chung đường staging với `put_stream` |
| `save_upload` không giới hạn | `max_bytes: int = 32 * 1024 * 1024` thay `None`; muốn bỏ giới hạn thì truyền `None` tường minh |

Đổi mặc định `max_bytes` **là đổi hành vi** - app nào đang cho tải file lớn hơn 32 MiB sẽ gãy.
Rà trước, hoặc chọn ngưỡng cao hơn.

---

## ĐỢT 3 - F10: cô lập adapter (việc thiết kế, không phải sửa một dòng)

> ⚠⚠ **CHUYỂN SANG 0.8 (quyết 2026-08-16). Đừng làm ở 0.7.x.**
>
> Chính mục này viết: *"Phải mở rộng protocol - **đây là đổi API cho mọi adapter**,
> gồm cả adapter người dùng tự viết."* Mà 0.8 đã có một đợt đổi API adapter một lượt
> (tên định danh, tách `client_id`, cổng từ cấu hình, hạng nhân bản), **và supervisor
> đa tiến trình cần đúng tín hiệu "ready" này** để biết khi nào con sẵn sàng - xem
> [`da-tien-trinh-main-va-cau-hinh-2026-08-16.md`](da-tien-trinh-main-va-cau-hinh-2026-08-16.md)
> mục 4.5.
>
> Làm ở 0.7.x là **đổi API adapter hai lần trong hai bản liên tiếp**. Gộp vào 0.8.
>
> Ba câu hỏi thiết kế dưới đây **vẫn nguyên giá trị**, chỉ đổi chỗ thi công.

Chủ dự án đã chốt hướng: **lỗi trước khi phục vụ thì sập luôn; lỗi sau khi đã phục vụ thì cô
lập.** Nhưng chốt hướng không có nghĩa là chốt cách làm - còn ba câu phải trả lời khi bắt tay:

1. **"Đã phục vụ" xác định thế nào?** Mỗi adapter cần một tín hiệu "tôi đã bind cổng và sẵn
   sàng". Hiện `Adapter` protocol chỉ có `start()`/`stop()`, không có gì báo trạng thái đó.
   Phải mở rộng protocol - đây là đổi API cho mọi adapter, gồm cả adapter người dùng tự viết.
2. **Ai biết một adapter đã chết?** Cần một chỗ giữ trạng thái (`Application.adapter_health()`
   chẳng hạn) để `/health` đọc được. Framework hiện **không có** khái niệm health.
3. **`/health` là của web adapter.** Nếu chính web adapter chết thì không còn ai trả lời -
   lúc đó buộc phải sập cả tiến trình. Nghĩa là quy tắc có ngoại lệ, phải viết ra.

**Đề xuất cách làm:** thay `asyncio.TaskGroup` bằng `asyncio.gather(..., return_exceptions=True)`
cộng một vòng giám sát; adapter nào ném sau khi đã báo "ready" thì ghi `CRITICAL`, đánh dấu
không lành mạnh, các adapter còn lại chạy tiếp. Adapter ném **trước** khi ready thì hủy tất cả
như hiện nay.

**Ước lượng:** một ngày code cộng nửa ngày test, và nó chạm vào `core/bootstrap` - phần lõi
nhất. Vì vậy xếp sau đợt 2, đừng làm song song.

**Việc kèm theo, nên làm cùng:** đưa endpoint `/health` chuẩn vào framework. Hiện mỗi app tự
viết, và báo cáo kiểm toán app admin từng ghi `/actuator/health` trả 503 ở 5/6 service Java vì
Redis không bật - tức là khái niệm "lành mạnh" đang mỗi nơi một kiểu.

---

## ĐỢT 4 - F3: nâng sàn dependency

**Không** phát hành PyPI (theo quyết định), nhưng vẫn phải sửa `pyproject.toml` để lần dựng môi
trường sau không rơi vào bộ có CVE.

| Gói | Sàn hiện tại | Đề xuất | Vì sao |
|---|---|---|---|
| `pyjwt` | `>=2.8` | `>=2.13` | 8 advisory, thư viện đứng giữa mọi quyết định xác thực |
| `python-multipart` | `>=0.0.7` | `>=0.0.31` | 7 advisory, nằm trên đường upload |
| `fastapi` | `>=0.110.1` | `>=0.115.3` | để kéo `starlette>=0.40` (11 advisory) |

**Cạm bẫy đã biết:** chú thích trong `pyproject.toml` ghi rõ các sàn hiện tại **đã được cài thử
và chạy hết bộ test**. Nâng sàn thì phải **làm lại đúng việc đó**, đừng chỉ sửa số - nếu không
ta thay một lời khai đã kiểm chứng bằng một lời khai đoán mò.

**Và nhớ mục 1.1:** không app nào có venv riêng. Nâng phiên bản một gói là nâng cho cả 31 app
cùng lúc. Nếu ngại, đây là lúc đáng cân nhắc dựng venv riêng cho ít nhất các app đã deploy -
nhưng đó là việc hạ tầng, không thuộc kế hoạch vá này.

**Thêm vào quy trình phát hành:** `pip-audit` chạy trên **bộ sàn**, không phải bộ đang cài
(máy dev luôn có bản mới nên chạy trên bản đang cài sẽ không thấy gì). Ghi cạnh ba script đã có
trong `.claude/scripts/`.

---

## ĐỢT 5 - Phần còn lại, làm lúc rảnh

| Mã | Việc | Ghi chú |
|---|---|---|
| ~~**F1**~~ | ✅ **XONG 2026-08-18 (0.7.2)** - `@ws` + xác thực qua subprotocol | Chủ dự án chốt làm ngay, vượt luật "0.7.x không chạm API" một cách có ý thức vì chưa app nào dùng WS. ⚠⚠ Kiểm toán bỏ sót: **framework KHÔNG CÓ đường đăng ký route WS nào cả**, nên đây là làm nốt tính năng chưa làm. ⭐ Xác thực nằm ở **lớp đăng ký route**, không nằm trong `on_connect`. Chi tiết: [`kiem-toan-bao-mat-0.7.md`](kiem-toan-bao-mat-0.7.md) mục F1 |
| ~~**F9**~~ | ⛔ **KHÔNG CÒN ÁP DỤNG** | `_read_peer_app_id` đã bị **XOÁ** ở 0.7.1 (gỡ phụ thuộc khái niệm). Không còn hàm nào lọc scheme, nên không còn chuỗi nào để neo. ⚠ Đây là ca **một mục kiểm toán biến mất vì thứ nó nói tới bị xoá**, không phải vì được vá - hai chuyện khác nhau, và bảng trạng thái ghi "chưa vá" suốt hai tuần vì không ai phân biệt |
| ~~**F14**~~ | ✅ **XONG 2026-08-18** - `validate_object_key` từ chối `\` và NUL | ⭐ Phạm vi thật rộng hơn: **BA** kết quả cho một khoá (local Windows / local **Linux** / S3), và phần nặng nhất là **NUL** chứ không phải `\` (`exists()` trả `False` cho khoá sai - dấu hiệu 3 luật 03; `put()` ném `ValueError` trần). Chi tiết: [`kiem-toan-bao-mat-0.7.md`](kiem-toan-bao-mat-0.7.md) mục F14 |
| ~~**F15**~~ | ✅ **XONG 2026-08-18** - `configure_event_bus(max_pending, never_drop)` | Chủ dự án chốt **BỎ** khi quá trần, và chốt cấu hình nằm ở **file `.py` cho lập trình viên**, không phải `application.yml` (người vận hành không biết handler chạy bao lâu / event to cỡ nào). ⭐ Bổ sung **`never_drop`** cho event không được phép mất - *"lỡ cái quan trọng bỏ lại dở"*. ⛔ Nợ luật 03 khai ra, để 0.8. Chi tiết: [`kiem-toan-bao-mat-0.7.md`](kiem-toan-bao-mat-0.7.md) mục F15 |
| ~~**F17**~~ | ✅ **XONG 2026-08-18** - `mqtt.rpc.reply_topics` | Chủ dự án chốt **cảnh báo chứ không chặn**. ⚠ Là **topic filter MQTT** chứ không phải tiền tố, và **không** mang tên `reply_prefix`: `nhamay/reply/` đọc như tiền tố hợp lý nhưng là filter thì khớp **không gì cả**. Chi tiết: [`kiem-toan-bao-mat-0.7.md`](kiem-toan-bao-mat-0.7.md) mục F17 |
| **A5** | 6 app Monolithic: đảo fail-open ở middleware | Việc lớn hơn vẻ ngoài - phải rà từng route xem route nào cố ý công khai |
| **A7** | `callback_secret` sinh ngẫu nhiên thay vì đặt tay | Gộp vào lúc làm lại quy trình đăng ký app |

---

## Bảng tổng: thứ tự và phụ thuộc

| Đợt | Việc | Phụ thuộc | Công sức | Trạng thái |
|---|---|---|---|---|
| 0.2 | Chốt chỗ để secret (A6) | - | 1 giờ | ⬜ |
| 0.1 | `shop` đổi secret (A3) | **cần 0.2 xong trước** | 1 giờ | ⬜ |
| 0.3 | 5 app Monolithic đổi secret (A3) | 0.2 | 1 giờ | ⬜ |
| 1.1 | A1 fail-closed, 21 codebase | - | nửa ngày | 🔄 **2/21 xong** (đo 2026-08-04). ⚠ `saas-foundation/template` còn hở -> vá TRƯỚC, xem mục 1.1 |
| 1.2 | A2 gỡ regex CORS, 23 codebase | - | 2 giờ | ⬜ |
| 1.3 | A4 đóng `/docs` | - | 1 giờ | ⬜ |
| 2.1 | F2 XSS lưu trữ | - | 2 giờ | ✅ 0.7.1 |
| 2.2 | F8 Content-Disposition | - | 1 giờ | ✅ 0.7.1 |
| 2.3 | F4 CORS ép kiểu | nên sau 1.2 | 1 giờ | ✅ 0.7.1 |
| 2.4 | F5 che secret khi in | - | 1 giờ | ✅ 0.7.1 |
| 2.5 | F6 cảnh báo chế độ mở | - | 2 giờ | ✅ 0.7.1 |
| 2.6 | F7 cảnh báo thiếu profile | - | 30 phút | ✅ 0.7.1 |
| 2.7 | F11 cảnh báo thiếu audience | - | 15 phút | ✅ 0.7.1 |
| 2.8 | F12 metadata lỗi gRPC | - | 15 phút | ✅ 0.7.1 |
| 2.9 | F13+F16 dọn localfs | - | 2 giờ | ✅ 0.7.1 |
| 3 | F10 cô lập adapter | sau đợt 2 | 1,5 ngày | ⬜ |
| 4 | F3 nâng sàn dependency | - | nửa ngày | ⬜ |
| 5 | Phần còn lại | - | tùy lúc | ⬜ |

**Đường găng:** 0.2 → 0.1. Mọi thứ khác chạy song song được.

Tổng đợt 0 + 1 + 2: khoảng **3 ngày công**, và nó xử lý xong 1 mục nghiêm trọng cùng 5 mục cao.

---

## Kiểm chứng: chạy lại đúng thứ đã bắt được lỗi

Sau mỗi đợt:

```bash
# 1. Bộ test framework (đợt 2 trở đi bắt buộc)
cd "D:/code/xime/xime framework" && pytest        # kỳ vọng: 1463 passed, 5 skipped

# 2. PoC - mục nào vá rồi thì PoC tương ứng phải chuyển sang ĐẠT
python .claude/scripts/bao-mat/poc_web.py         # F1+F14 (đã vá 08-18), F4, F8
python .claude/scripts/bao-mat/poc_web2.py        # F2
python .claude/scripts/bao-mat/poc_config.py      # F5, F7
python .claude/scripts/bao-mat/poc_cors_real.py   # A2

# 3. Test của ít nhất 3 app, vì sửa framework là chạm 31 app cùng lúc (mục 1.1)
cd "D:/code/xime/Base Platform/data" && pytest
cd "D:/code/xime/Application Layer/linh-kien-dien-tu/backend" && pytest
cd "D:/code/Monolithic/shop/backend" && pytest
```

**Đừng kiểm bằng `xime.__version__`** - xem mục 1.2, nó trả 0.6.3 bất kể có vá hay không.

---

## Việc KHÔNG làm trong đợt này

Ghi rõ để người sau không tưởng đã xong:

- **Không đẩy PyPI** (quyết định của chủ dự án). Nghĩa là người dùng ngoài vẫn nhận bản 0.7.0
  có F1, F2, F3, F4... cho tới khi có quyết định khác. Nếu gói này thật sự có người ngoài dùng
  thì đây là điều cần xem lại.
- **Không kiểm service Java** (Trust, identity, user, payment, application, agent,
  organization). Hai kết luận của báo cáo phụ thuộc phần đó: F9 (chính sách cấp SAN của Trust)
  và A2 (thuộc tính `SameSite` của cookie refresh do identity đặt).
- **Không kiểm frontend** (XSS phía trình duyệt, CSP). F2 vá ở backend, nhưng CSP là lớp phòng
  thủ thứ hai mà hiện không có.
- **Không dựng venv riêng cho từng app.** Đáng làm, nhưng là việc hạ tầng, làm lẫn vào đợt vá
  sẽ không biết cái gì gây ra cái gì.
- **Không dọn chuyện `xime.__version__` lệch metadata** - việc vệ sinh riêng (mục 1.2).

---

## Rủi ro của chính đợt vá này

| Rủi ro | Khả năng | Cách giảm |
|---|---|---|
| Sửa framework làm gãy 31 app cùng lúc | Trung bình | Chạy pytest framework + 3 app sau **mỗi** mục, không dồn |
| A1 fail-closed làm app không khởi động được | Cao ở app cấu hình thiếu | Đó là **mục đích**, không phải lỗi. Nhưng thi công vào giờ thấp điểm, và kiểm `trust.enabled` của từng repo trước |
| A2 gỡ regex làm gãy truy cập qua IP LAN | Thấp - trung bình | Rà mô hình triển khai trước; giữ dải riêng tư trong `application-local.yml` |
| F2 đổi Content-Type làm gãy tính năng xem ảnh/PDF | Thấp | Danh sách `_INLINE_SAFE` giữ đúng các kiểu đang dùng thật |
| `shop` đổi secret mà `XIME_ENV` chưa đặt đúng trên máy chủ | **Cao** | Kiểm biến môi trường trên máy chủ TRƯỚC khi đổi. Đây đúng là bẫy F7 |
| Vá xong nhưng quên cập nhật 28 file cảnh báo | Cao | Nguyên tắc 4 ở mục 2. Phiên sau đọc "CHƯA VÁ" sẽ làm lại từ đầu |
