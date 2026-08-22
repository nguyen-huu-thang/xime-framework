# Route WebSocket không xác thực thì framework kêu, route HTTP thì im

> Người báo: phiên giữ **`Application Layer/dental`**, 2026-08-22, trong đợt nâng
> cấp đa tiến trình 0.8. Framework đo trên máy: `0.8.1`, cài editable, Windows.
>
> Mức: **vừa**, và nó gắn thẳng với **A1** của kiểm toán 2026-08-01 (21 codebase
> fail-open) - xem mục 4, đó là phần đáng đọc nhất.
>
> ⚠ Tôi có PoC **hai chiều**: cùng một ứng dụng, thêm đúng một route `@ws` là
> framework kêu; bỏ nó đi thì im hoàn toàn trong khi route HTTP vẫn mở toang.

## 1. Ở đâu

`xime/adapters/web/_adapter.py`:

| Dòng | Nội dung |
|---|---|
| 475-477 | `jwt_config = jwt_registry.get()`; **`if jwt_config is None: return`** - chưa gọi `configure_jwt()` thì thoát sớm, không kiểm gì thêm |
| 479-497 | Phép kiểm "đúng MỘT nguồn khoá", kèm chú thích nói rõ mục đích |
| 640-653 | `_log.warning(...)` khi **có route WebSocket** mà `configure_jwt()` chưa từng được gọi |

Chú thích ở dòng 479-485 phát biểu mục đích của phép kiểm:

> *"Từ chối "không có cái nào" chính là mục đích của phép kiểm này: thiếu nó thì
> app không lấy được khoá lúc khởi động sẽ lên mà **KHÔNG có middleware xác thực
> nào và tự báo là khoẻ, trong khi mọi endpoint đều mở** - hỏng mà trông y như
> chạy tốt."*

Câu đó mô tả đúng thứ cần chặn. Nhưng phép kiểm nằm **sau** cái `return` ở dòng
476, nên nó chỉ chạy cho ứng dụng **đã gọi** `configure_jwt()`. Ứng dụng không gọi
thì rơi vào đúng trạng thái mà câu trên mô tả, và không có gì kiểm.

## 2. PoC - tái hiện trong ba phút

Một ứng dụng Xime tối giản, một controller mang dữ liệu y tế, **không** gọi
`configure_jwt()`.

```python
# dieu_khien.py
from xime.adapters.web import get

class HoSoController:
    @get("/api/v1/benh-an/{ma}")
    async def doc_ho_so(self, ma: str) -> dict:
        return {"ma": ma, "chan_doan": "sau rang 36", "ghi_chu": "DU LIEU Y TE THAT"}
```

```python
# cauhinh.py
from xime.adapters.web import configure_controllers
from xime.core.config.binding import BindingConfig
from dieu_khien import HoSoController

dependency = BindingConfig()
dependency.register(HoSoController)
configure_controllers("dieu_khien")
__all__ = ["dependency"]
```

```python
# poc.py
import cauhinh
from xime import Application
from xime.adapters.web import WebAdapter

app = Application()
app.add_config(cauhinh)
app.use(WebAdapter())

if __name__ == "__main__":
    app.run()
```

### Kết quả đo

**Lượt A - chỉ có route HTTP:**

```text
INFO | xime.bootstrap             | event loop: asyncio.windows_events.ProactorEventLoop
INFO | xime.adapters.web._adapter | web default: process main serving on 127.0.0.1:8399 (HTTP)
INFO:     Application startup complete.
INFO:     127.0.0.1:56898 - "GET /api/v1/benh-an/BN001 HTTP/1.1" 200 OK
```

```text
$ curl http://127.0.0.1:8399/api/v1/benh-an/BN001        # không token
HTTP 200 -> {"ma":"BN001","chan_doan":"sau rang 36","ghi_chu":"DU LIEU Y TE THAT"}
```

Toàn bộ log khởi động **không có một chữ nào** về xác thực. Đếm dòng khớp
`jwt|auth|token|unauthenticated`: **0**.

**Lượt B - thêm đúng một route `@ws` vào cùng ứng dụng đó:**

```python
@ws("/ws/theo-doi")
class TheoDoiHandler(WebSocketHandler):
    ...
```

```text
WARNING | xime.adapters.web._adapter | 1 WebSocket route(s) registered but
configure_jwt() was never called, so every one of them accepts unauthenticated
connections: TheoDoiHandler
```

> Cùng một ứng dụng, cùng một tình trạng *"không có xác thực"*. Thêm một route
> WebSocket thì framework nói. Bỏ nó đi, để lại route HTTP mang bệnh án, thì
> framework im.

## 3. Vì sao bất đối xứng này đáng nhìn lại

Cảnh báo WebSocket ra đời từ **F1** của kiểm toán 0.7, và chú thích ngay tại chỗ
(`_adapter.py:642-649`) giải thích lý do:

> *"chính sự im lặng quanh chuyện đó là lý do F1 sống lâu."*

Lập luận đó đúng, và nó **không có gì riêng cho WebSocket**. Một route HTTP không
xác thực cũng mở, cũng im, và trong workspace này nó phổ biến hơn nhiều: 21 repo
có `app/config/jwt.py`, **0 repo** gọi `configure_jwt` (số đo của phiên
`linh-kien-dien-tu`, cùng ngày).

⚠ Khác biệt về **hậu quả** thì nghiêng về phía ngược lại với cảnh báo hiện có:
route WebSocket trong workspace gần như chưa ai dùng, còn route HTTP thì đang chở
bệnh án và hồ sơ y tế.

## 4. ⭐ Chỗ nối với A1, và lý do tôi viết báo cáo này thay vì im lặng

`0.7.2` được ghi nhận là đã **lấp gốc** của A1 - `configure_jwt()` thiếu nguồn
khoá thì nổ lúc khởi động. Điều đó **đúng**, nhưng nó đúng với một điều kiện
không được nói ra:

> Bản vá chỉ có hiệu lực với ứng dụng **luôn gọi** `configure_jwt()`. Đặt lời gọi
> đó sau một `if` là quay lại A1 nguyên vẹn, và framework **không nói gì**.

Và cái `if` đó không phải giả định. Nó là khuôn đang được **khuyến khích** ở chỗ
khác trong chính hệ sinh thái này. `config/scheduler.py` của `linh-kien-dien-tu`
viết, có lý lẽ đàng hoàng:

> *"Trust tắt thì **không đăng ký job nào cả**, thay vì đăng ký rồi để job tự
> kiểm rồi thoát sớm... cách này giữ đúng lời hứa của log."*

Áp đúng khuôn đó cho JWT thì ra:

```python
if _TRUST_BAT:
    configure_jwt(...)          # ⛔ trust tắt -> không có xác thực, im lặng
```

Câu đó đọc lên **hợp lý y hệt** khi viết cho scheduler, và ở đây nó mở toang mọi
endpoint. Đây là hình dạng mà một người cẩn thận vẫn viết ra được.

📌 Nói cách khác: sau `0.7.2`, đường rơi vào A1 **hẹp lại nhưng chưa đóng**, và
chỗ hở còn lại nằm đúng ở điểm mù của log.

## 5. ⛔ Lập luận CHỐNG lại việc thêm cảnh báo - đọc trước phần đề xuất

Tôi không nghĩ đây là chuyện hiển nhiên, và có ít nhất ba lý do đáng cân nhắc để
**không** làm:

| Lý do | Trọng lượng |
|---|---|
| **Ứng dụng công khai hoàn toàn là hợp lệ và không hiếm.** Một service chỉ có `/healthz` và vài endpoint đọc công khai thì cảnh báo này là tiếng ồn ở mọi lần khởi động | **Nặng nhất.** Và *một phép dò kêu oan là một phép dò bị tắt* - chính framework đã viết câu đó cho ngưỡng 3 giây của `share_load()` |
| WebSocket khác HTTP ở chỗ **không có cách nào khác để xác thực** ngoài lớp của framework, còn HTTP thì app có thể tự cài middleware riêng - và 21 repo trong workspace đang làm đúng thế | Đáng kể. Cảnh báo sẽ kêu oan với **cả 21 repo đó** |
| Framework không biết route nào *đáng lẽ* phải có xác thực. `/healthz` và `/api/v1/benh-an/{ma}` với nó là hai dòng giống nhau | Đáng kể |

⚠ Lý do thứ hai một mình đủ để bác đề xuất ngây thơ *"cứ có route HTTP mà không
`configure_jwt()` thì cảnh báo"*: nó sẽ kêu ở mọi repo Xime hiện có, đúng vào lúc
những repo đó **đang có** middleware xác thực tự viết chạy tốt.

## 6. Đề xuất, đã lọc qua mục 5

Tôi đề xuất **cách hẹp nhất** còn giữ được giá trị, chứ không phải cách phủ rộng:

**a. Cảnh báo chỉ khi ứng dụng KHÔNG CÓ middleware nào cả.**

Framework biết `configure_middleware()` đã được gọi hay chưa. Điều kiện:

```text
có route HTTP  AND  configure_jwt() chưa gọi  AND  không có middleware tuỳ biến nào
```

Ba vế cộng lại thì 21 repo hiện tại **không dính** (chúng đều gọi
`configure_middleware(TrustJwtAuthMiddleware, ...)`), còn ứng dụng thật sự chạy
trần thì kêu. Nó cũng bắt đúng ca `if _TRUST_BAT:` ở mục 4 - vì nhánh đó không cài
middleware nào.

**b. Hoặc rẻ hơn nữa: một dòng `INFO` nói về trạng thái xác thực, luôn in.**

```text
INFO | web default: JWT middleware active (aud=dental, 5 public path(s))
INFO | web default: no JWT middleware - 45 HTTP route(s) are open
```

Không kêu oan được vì nó không phải cảnh báo, và nó cấp thứ đang thiếu: **một mốc
dương để đối chiếu**. Đây đúng khuôn mà báo cáo
[`data-service-grpc-khong-bao-minh-da-len`](data-service-grpc-khong-bao-minh-da-len-2026-08-21.md)
đã nêu và framework đã nhận ở C7 - *trạng thái tốt phải có dấu vết, nếu không thì
không có gì để so khi nghi ngờ*. Ở đây là **cùng một lỗ hổng, ở một adapter khác**.

⭐ Nếu chỉ chọn một, tôi chọn **(b)**. Nó rẻ hơn, không có cửa kêu oan, và nó vá
đúng thứ làm A1 sống lâu: không phải chuyện *thiếu một phép kiểm*, mà là chuyện
**trạng thái "không có xác thực" trông giống hệt trạng thái "có xác thực"** trong
log khởi động.

## 7. Một chỗ nhỏ hơn nhiều, ghi kèm vì cùng đợt

**`RefData` vắng mặt khi ứng dụng dựng container bằng tay trong test.**

`StartupOrchestrator` (`orchestrator.py:86-88`) làm hai dòng:

```python
container.register_instance(RefDataArena, self._refdata)
container.register(*refdata_registry.classes())
```

Ứng dụng nào có test canh nối dây DI (khuôn `test_di_wiring.py`, đang có ở nhiều
repo Application Layer) thì phải **tự chép hai dòng đó**, nếu không mọi lớp nhận
một bảng `RefData` qua constructor sẽ báo thiếu phụ thuộc - và thông báo hiện ra
là *"add the package containing 'TrustCertificateRefData' to dependency.scan()"*,
tức nó **chỉ sai hướng**: thêm vào `scan()` không giải quyết được gì.

Mức: **thấp**, và có thể là chủ ý (dựng container trong test là việc của app).
Nhưng thông báo lỗi thì đáng sửa dù không thêm helper nào - nó dẫn người đọc đi
sai đường.

## 8. Tôi đo được tới đâu

| Đã đo | Chưa đo |
|---|---|
| PoC hai chiều ở mục 2, chạy thật trên Windows, `0.8.1` editable | **Chưa thử trên Linux.** Không có lý do gì để khác, nhưng chưa chạy |
| Đọc `_adapter.py` dòng 470-500 và 625-655, `_config.py`, `_provider.py` | Chưa đọc `JwtAuthenticator` và đường WebSocket sâu hơn |
| Xác nhận `jwt_registry.set()` **không kiểm gì**, phép kiểm nằm ở web adapter | Chưa kiểm adapter gRPC có đường tương tự không |
| Con số `21 repo có config/jwt.py, 0 repo gọi configure_jwt` là **của phiên `linh-kien-dien-tu`**, tôi trích lại chứ không tự đếm | - |

⚠ Repo tôi (`dental`) **không đang thủng vì chuyện này**: nó gọi
`configure_middleware(TrustJwtAuthMiddleware, ...)` vô điều kiện, và nhánh
fail-open của nó chỉ mở khi `trust.enabled: false` **và** không có PEM tĩnh. Tôi
báo vì đường rơi vào A1 vẫn còn, không vì repo tôi đang hỏng.
