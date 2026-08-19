# XIME Framework — Hướng dẫn phiên làm việc

Python backend framework. **0.7.2 ĐÃ PHÁT HÀNH** - đo lại 2026-08-18: PyPI có
**13 bản** (`0.1.0` -> `0.7.2`), `pyproject.toml` = `0.7.2`, `xime.__version__` =
`0.7.2`, commit `3cfc3f3 v0.7.2` bên phát triển.

> ⚠⚠ **Dòng cũ ghi *"0.7.1 đã phát hành, repo đang làm dở 0.7.2"* là SAI, đừng tin
> lại.** Đây là **lần thứ ba** cùng một khuôn ở repo này (trước đó: *"chưa push
> PyPI"* và *"0.7.0 chưa commit"*). Nó đúng lúc viết rồi bị bỏ quên sau khi phát
> hành. **Kiểm bằng lệnh, đừng kiểm bằng trí nhớ:**
>
> ```bash
> python -c "import urllib.request,json; print(sorted(json.load(urllib.request.urlopen('https://pypi.org/pypi/xime/json'))['releases']))"
> ```

⚠ **Hai thứ CÒN THIẾU sau khi 0.7.2 lên PyPI** (đo 2026-08-18, chủ dự án tự xử lý -
phiên không tự commit/tag):

| | Trạng thái |
|---|---|
| **Git tag `v0.7.2`** | **chưa có ở cả hai repo.** ⚠ Dòng cũ ghi *"cả hai repo chưa có git tag nào"* cũng SAI: **đã có `v0.6.3`, `v0.7.0`, `v0.7.1`**, chỉ thiếu đúng `v0.7.2` |
| **Repo phát hành `upload`** | commit mới nhất vẫn là **`a3fcad8 v0.7.1`**, tức nó **KHÔNG còn giữ đúng bản đã lên PyPI** - trái với chính lời dặn ở đoạn ngay dưới |

⚠ **Repo phát hành `D:\code\xime framework\upload` CHỈ được copy sang khi có bản mới
để phát hành** - nó giữ đúng bản đã lên PyPI, nên nó lệch với repo phát triển trong
suốt thời gian làm dở là **bình thường**, không phải nợ. Đừng đồng bộ nó giữa chừng.

⚠ **Ngay lúc này thì nó KHÔNG đúng bản đã lên PyPI** (`a3fcad8 v0.7.1` trong khi PyPI
đã có `0.7.2`), nên câu trên tạm thời không mô tả đúng hiện trạng. Đó là **nợ thật**,
không phải "lệch bình thường".

Vì `xime` cài **editable** nên mọi thay đổi ở đây có hiệu lực ngay với cả 31 app trên
máy này, kể cả phần chưa phát hành. Chủ dự án tự đẩy PyPI, **đừng đẩy hộ**.

> ## 0.7.2 (ĐÃ PHÁT HÀNH, PyPI có `0.7.2`) có gì
>
> - ⭐ **JWT: khóa xoay theo `kid`** - `JwtKeyProvider`, verify theo `kid`, ba knob
>   PyJWT từng bị giấu (`algorithms` **danh sách trắng**, `leeway`, `require`),
>   `sign(headers=)`, và ⛔ **`configure_jwt()` không có nguồn khóa nay NỔ lúc khởi
>   động**. Chi tiết + phép đo:
>   [`docs/jwt-keyset-va-trung-tinh-2026-08-18.md`](docs/jwt-keyset-va-trung-tinh-2026-08-18.md).
>   Test **1553 passed, 11 skipped**. **Không phá app nào.**
> - ⭐ **F3 - sàn dependency**: nâng **10 sàn** vì advisory (`pyjwt` `python-multipart`
>   `starlette` `fastapi` `msgpack` `aiosmtplib` `protobuf` `cryptography` `pytest`),
>   **sửa 3 sàn khai SAI** (`sqlalchemy` lệch 38 bản patch · `aiomqtt` mâu thuẫn với
>   `paho-mqtt` cùng extra · `pytest-asyncio` nổ với pytest 9), thêm
>   `.claude/scripts/check_dep_advisories.py` thành **bước 1b** của hướng dẫn phát
>   hành. Test **1553** trên 24 sàn ghim thật, rồi 1553 + data-service 388 +
>   linh-kien 295 trên môi trường mới. Chi tiết ở `CHANGELOG.md` `[0.7.2]`.
>   ⚠ **Môi trường chung đã nâng theo**: `starlette` 0.52.1 -> 1.6.0 (nhảy một bản
>   lớn), `python-multipart` 0.0.22 -> 0.0.32, `cryptography` 49 -> 50.
> - ⭐ **F14 - khoá lưu trữ: từ chối gạch ngược và NUL**. `validate_object_key` dùng
>   `PurePosixPath` nên khoá kiểu Windows lọt hết ba phép kiểm rồi mang **BA** nghĩa
>   khác nhau (local Windows từ chối · local **Linux NHẬN** · S3 nhận, không phòng
>   tuyến nào) - trong khi docstring của chính hàm đó hứa *"đổi backend không đổi
>   tập key hợp lệ"*.
>   ⭐ Phần đáng vá nhất hoá ra là **NUL chứ không phải `\`**: `exists()` trả `False`
>   cho khoá sai (**dấu hiệu 3 của luật 03**) và `put()` ném `ValueError` trần thay vì
>   `StorageError`. Test đi **thành cặp**, hai backend **import chung** `UNSAFE_KEYS`;
>   đối chứng gỡ vá ra **5 đỏ**. Test **1563 passed, 11 skipped** + data-service 388.
>   **Không app nào phải sửa** - `data-service` đã tự chuẩn hoá `\` -> `/` từ trước.
> - ⭐ **F17 - MQTT RPC: reply topic do BÊN GỌI đặt**. Adapter publish reply bằng
>   credential broker của **dịch vụ**, tới topic **bên gọi chỉ định** - trên broker có
>   ACL theo client thì bên gọi mượn được quyền của ta (*confused deputy*), và nó còn
>   điều khiển trọn `CorrelationData`. Thêm `mqtt.rpc.reply_topics`; chủ dự án chốt
>   **cảnh báo chứ không chặn**. ⚠ Là **topic filter MQTT**, không phải tiền tố chuỗi.
>   Test **1577 passed** (+14). **Không app nào dùng MQTT** nên không đụng ai.
> - ⭐ **F15 - trần task `EventBus`**. `publish()` sinh một task mỗi handler, không
>   trần; đo được **100.000 task** từ 50k publish, và **36 MB** từ 20k event 1 KB vì
>   `_pending` giữ sống chính object event. Chủ dự án chốt **BỎ** khi quá trần, cấu
>   hình bằng **`configure_event_bus()` trong `config/*.py`** (framework config, KHÔNG
>   phải `application.yml`), kèm **`never_drop=(...)`** cho thứ không được phép mất và
>   `max_pending=None` cho ai cố ý bỏ trần. Test **1593 passed** (+16).
>   ⛔ Nợ luật 03 (bỏ và xếp lịch cùng trả `None`) khai ra, cố ý để **0.8**.
> - ⭐⭐ **F1 - WebSocket: có đường đăng ký route, và có xác thực**. ⚠ Đổi API công
>   khai trong một bản patch, chủ dự án chốt vì **chưa app nào dùng WS**.
>   ⚠⚠ Kiểm toán bỏ sót: **framework KHÔNG CÓ đường đăng ký route WS nào cả** - nên
>   đây là **làm nốt tính năng chưa làm**, không phải vá lỗi.
>   ⭐ **Xác thực nằm ở lớp ĐĂNG KÝ ROUTE, không nằm trong `on_connect`** (khác đề
>   xuất kiểm toán): đặt trong `on_connect` là để lớp con xoá chốt chặn bằng một dòng
>   override. `@ws("/path")` · token qua **subprotocol** · `JwtAuthenticator` dùng
>   chung với HTTP · đóng kết nối khi token hết hạn. Tài liệu: `docs/{vn,en}/websocket.md`.
>   **1624 passed** (+31).

> ## 0.7.1 (ĐÃ PHÁT HÀNH) có gì (chi tiết: [`docs/ket-qua-0.7.1-2026-08-03.md`](docs/ket-qua-0.7.1-2026-08-03.md))
>
> 1. **Server streaming cho bản ghi CÓ KIỂU** - `@stream` + handler async
>    generator `-> AsyncIterator[Model]`, proto ra `returns (stream Resp)` không
>    wrapper. Trả lời yêu cầu của phiên data-service + user-service. Kèm
>    `stream_deadline_ms` (mặc định 0 = không giới hạn) và keepalive gRPC hai đầu.
>    ⚠ Chỗ chặn thật nằm ở **fallback proto-only** của trình sinh SDK (đường
>    service Java -> Python) - yêu cầu gốc không thấy chỗ này.
> 2. **Đợt 2 kế hoạch vá bảo mật**: F2, F4, F5, F6, F7, F8, F11, F12, F13, F16.
> 3. **(2026-08-04) Lỗi đua khi tắt scheduler** - chi tiết:
>    [`docs/loi-dua-scheduler-2026-08-04.md`](docs/loi-dua-scheduler-2026-08-04.md).
>    `SchedulerRunner` phóng vòng lặp bằng `create_task` rồi trả về trước khi nó
>    kịp chạy; tắt nhanh thì `stop()` **im lặng không làm gì** và `__aexit__` dọn
>    dịch vụ dưới chân task chưa khởi động. Nay dùng `start_in_background()`.
>    ⚠ **Đừng quay lại `asyncio.create_task(run_until_stopped())`** - có test canh
>    (`test_does_not_spawn_its_own_task`). Chạm **mọi app có job nền**, không phải
>    chỉ chuyện viết test như báo cáo ban đầu nói.
> 4. ⛔⭐ **(2026-08-17) GỠ PHỤ THUỘC KHÁI NIỆM - BREAKING** - chi tiết:
>    [`docs/go-phu-thuoc-khai-niem-2026-08-17.md`](docs/go-phu-thuoc-khai-niem-2026-08-17.md).
>    Chủ dự án ra nguyên tắc: *"framework làm ra để nhiều người khác dùng nữa...
>    nên framework không được phụ thuộc gì khái niệm ngoài cả"*. Đã gỡ
>    **`current_app_id()` / `PEER_APP_ID`** cùng hai hằng số đóng cứng
>    (`xime-app://` và **độ dài 33**, hệ quả của việc application-service chọn
>    KSUID 24 byte). Thay bằng **`current_peer_sans()` / `PEER_SANS`** trả **mọi**
>    entry SAN, thô, không lọc. ⚠ **`Base Platform/data` HỎNG NGAY** (editable
>    install, không có ân hạn) - chủ dự án chấp nhận, đã ghi thông báo vào repo họ.
>    ⭐ Số đo đáng nhớ: helper **trung tính** (`current_caller`) được **4/4** repo
>    dùng, **0** tự viết; helper **mang khái niệm** được **1/5** dùng, **4/5** tự
>    viết lại. Người dùng đã bỏ phiếu bằng chân trước khi ta kịp nhận ra.
> 4b. ⭐ **(2026-08-18) JWT: khóa xoay theo `kid` + trả nợ trung tính** - chi tiết:
>    [`docs/jwt-keyset-va-trung-tinh-2026-08-18.md`](docs/jwt-keyset-va-trung-tinh-2026-08-18.md).
>    **Cùng khuôn mục 4 nhưng NGƯỢC CHIỀU**: `PEER_APP_ID` sai vì framework *biết
>    quá nhiều* về Xime; `KeyContext` sai vì nó *biết quá ít* về JWT. Bằng chứng
>    cùng dạng: **21/21 repo tự viết lại** (413 dòng/app).
>    Thêm **`JwtKeyProvider`** (`keys(kid)`, một method, đồng bộ, khuôn
>    `configure_grpc_tls`) · verify theo `kid` · ba knob PyJWT từng bị giấu
>    (`algorithms` **danh sách trắng**, `leeway`, `require`) · `sign(headers=)`.
>    ⛔ **`configure_jwt()` không có nguồn khóa nay NỔ lúc khởi động** - đóng lý do
>    tồn tại của lỗ fail-open A1. **Không phá app nào.**
>    ⚠ **Không tự vá 19 app** - lỗ nằm ở `config/jwt.py` của họ. Nhưng migration
>    chỉ là **xóa `TrustJwtAuthMiddleware` (105 dòng mã verify chép tay)** và giữ
>    nguyên `TrustKeyProvider` + `JwtKeySet`. **Vá `saas-foundation/template`
>    trước** - nó là nguồn sinh sôi.
>    ⭐ Chủ dự án chốt bỏ `refresh()` (*"để người lập trình app chủ động"*), và lựa
>    chọn đó khiến framework **không sinh thêm dòng nợ nghĩa 1 nào**.
> 5. **(2026-08-17) Khai ba phụ thuộc bắc cầu** -
>    [`docs/phu-thuoc-bac-cau-chua-khai-2026-08-17.md`](docs/phu-thuoc-bac-cau-chua-khai-2026-08-17.md).
>    `starlette` **hết** là phụ thuộc trực tiếp (4 chỗ đổi sang `fastapi`, cùng
>    object) · `paho-mqtt>=2.1` vào extra `mqtt` (không tránh được: `aiomqtt` 2.x
>    không có `Properties` riêng) · `botocore` **tên trần, cố ý không phiên bản**
>    (aiobotocore ghim nó vào dải 16 bản patch dịch theo mỗi bản mới).
>
> Test: **1516 passed, 11 skipped** + bốn app thật (data 347, linh-kien 295,
> shop 166, crm 53).
> ⚠ Skip tăng 7 -> 11 **không phải vì test bị tắt**: hai extra `mqtt`/`s3` trước
> nay chưa từng cài nên vài module bị skip **cả gói** (đếm là 1); cài rồi thì
> chúng được thu thập thành từng test. Đổi lại **2 test giờ chạy thật**.
>
> **Bốn thứ đổi hành vi** (bảng đầy đủ ở CHANGELOG + mục 3 của bản kết quả):
> `stream_object` ép tải xuống với kiểu ngoài danh sách an toàn (**SVG cố ý
> không inline**) · `save_upload` bỏ qua `Content-Type` client khai và có trần
> 32 MiB · `configure_cors` nổ lúc khởi động với cấu hình sai kiểu · deadline của
> server-stream tách sang khoá riêng.
>
> ⚠ **Bộ test OPC UA nhạy với tải máy**: chạy nguyên bộ lúc máy bận thì 4 test
> `tests_temp/opcua/test_server.py` có thể đỏ, chạy lại một mình thì 70/70 xanh.
> Đừng vội kết luận bản vá gây ra.

Lịch sử: **0.7.0 ĐÃ COMMIT VÀ ĐÃ LÊN PyPI** (kiểm chứng 2026-08-01 qua PyPI JSON
API: 11 bản `0.1.0` -> `0.7.0`; commit `bd2c594 v0.7.0` ở repo phát triển,
`99036ae v0.7.0` ở repo phát hành). Hệ quả: API đã có người tải về dùng, đổi API
phải theo semver.

> **Dòng "0.7.0 chưa commit, chưa lên PyPI" ở tài liệu cũ là SAI, đừng tin lại.**
> Nó đúng lúc viết (2026-07-30) rồi bị bỏ quên sau khi phát hành. Cùng loại với
> lỗi "chưa push PyPI" trước đó. Kiểm bằng lệnh, đừng kiểm bằng trí nhớ:
> `python -c "import urllib.request,json; print(sorted(json.load(urllib.request.urlopen('https://pypi.org/pypi/xime/json'))['releases']))"`
>
> Ghi chú: **cả hai repo chưa có git tag nào** dù bước 8 của hướng dẫn phát hành
> yêu cầu `git tag v0.7.0`. Commit có, tag không.

## Repo này ĐÃ VÀO NHÓM CHAT (từ 2026-08-04)

Trước đây repo này không có phiên trong nhóm, dù **30 codebase Python phụ thuộc vào nó** và nó
cài **editable** (mỗi thay đổi ở đây có hiệu lực ngay với cả 30 app, không ai phải cài lại gì).
Hậu quả đã xảy ra: các phiên khác **đoán** về framework rồi kết luận sai.

| Chỗ | Dùng khi |
| --- | --- |
| `D:\temp\xime\nhom-chat\CHAT-CHUNG.md` | **loa** - sắp đổi thứ nhiều người dùng, lỗi cắt ngang nhiều repo. **Dùng nhiều nhất** ở repo này |
| `D:\temp\xime\nhom-chat\leader-framework\framework-gui-leader.md` | file **tôi ghi**, leader đọc |
| `.../leader-framework/leader-gui-framework.md` | file **leader ghi**, tôi đọc. Đừng sửa |

**Luật: chỉ ghi vào file mang tên mình, tin mới nhất trên cùng, lấy giờ bằng `Get-Date -Format "HH:mm"`.**
Cần kênh riêng với repo khác thì **xin leader mở**, đừng tự tạo. Bối cảnh nhóm:
[`docs/lam-viec-voi-nhom-2026-08-04.md`](docs/lam-viec-voi-nhom-2026-08-04.md).

⚠ **Ranh giới chủ dự án dặn 2026-08-04:** sửa lỗi / nâng cấp lặt vặt thì **phối hợp với leader**;
**quyết định cấu trúc, đổi cấu trúc, hoặc thứ ảnh hưởng lớn tới framework thì HỎI CHỦ DỰ ÁN TRƯỚC**.
Ví dụ đang chờ: đổi thứ tự phân giải `__version__` (mục ngay dưới).

### ⚠ `xime.__version__` trả lời câu "lần cuối ai CÀI LẠI gói", không phải "mã đang chạy là bản nào"

✅ **Đã chạy lại `pip install -e .` ngày 2026-08-18** theo yêu cầu chủ dự án, và sau
đợt phát hành 0.7.2 thì nay `xime.__version__` = `importlib.metadata` =
`pyproject.toml` = **`0.7.2`**. Đo lại cuối ngày 2026-08-18: **khớp cả ba**.

⚠ **Nhưng cơ chế thì không đổi, nên chuyện này sẽ lặp lại.** `xime/__init__.py` lấy version từ
`importlib.metadata.version("xime")`, chỉ fallback sang hằng số trong mã khi metadata vắng. Cài
editable thì **mã nạp thẳng từ repo (luôn mới), còn metadata đóng băng tại lần `pip install -e`
cuối**. Trước hôm nay nó đứng ở `0.6.3` suốt hai bản.

Ngay lúc này thì **đang khớp**, nhưng nó sẽ lệch lại ngay khi bắt đầu code 0.8 mà chưa cài lại.
Đó là một giá trị mang hai nghĩa, đúng
[luật 03](../../.claude/rules/03-mot-gia-tri-mot-nghia.md).

**Cách kiểm đúng vẫn là: hỏi code, đừng hỏi số.**

```python
from xime.starters.jwt import JwtKeyProvider   # co -> ma la 0.7.2-dev
from xime.core.contract import stream          # co -> ma tu 0.7.1 tro len
```

Còn treo, thẩm quyền thuộc chủ dự án: **đổi thứ tự ưu tiên của `__version__`** (đổi một giá trị
công khai mà 31 codebase đọc được).

## Ba thư mục, đừng nhầm (đổi cấu trúc 2026-08-01)

| Thư mục | Là gì |
| --- | --- |
| `d:\code\xime\xime framework` | **repo PHÁT TRIỂN** (chỗ này): code, `tests_temp/`, `.claude/`, két token `pypi_token.py`. Remote GitHub `nguyen-huu-thang/xime-framework` |
| `D:\code\xime framework\upload` | **repo PHÁT HÀNH**: chỉ thứ đóng gói. Build + upload PyPI ở đây. Repo git riêng, **không có remote** |
| `D:\code\xime framework\website` | **trang xime-framework.org** (Next.js xuất tĩnh). Không dính gì tới gói PyPI |

Trước 2026-08-01 repo phát hành nằm thẳng ở `D:\code\xime framework`; nay lùi
vào `upload/` để nhường chỗ cho `website/`. `.git` + `.gitignore` chuyển theo nên
`upload/` vẫn tự chứa, build cho kết quả y hệt (đã kiểm: sdist 230 file,
`twine check` PASSED). Lệnh upload nay là
`python pypi_token.py --upload "D:/code/xime framework/upload/dist"`.

Toàn bộ core, các adapter (web, gRPC code-first + client SDK, socket, **MQTT**,
**Modbus TCP**, **OPC UA**) và starters (gồm **storage/localfs/s3**,
**mail SMTP**) đã có code và test (**1516 passed, 7 skipped** ở 0.7.1 - con số 1463/5
trong các tài liệu viết trước 2026-08-03 là của 0.7.0; skip gồm test tích hợp
MQTT/S3 cần broker/MinIO và test phân quyền file chỉ chạy trên POSIX). Không còn ở
giai đoạn thiết kế - khi sửa, đọc code thật trong `xime/` và chạy `pytest` trước khi
kết luận.

Trạng thái các mảng lớn (cập nhật 2026-07-29):

- **Core DI / lifecycle / config / event bus:** hoàn thành. **Bản 0.6** đã gỡ hẳn
  `dependency-injector` (registry singleton viết lại bằng dict dùng class làm key +
  `RLock` double-checked, API không đổi) và thêm **dynamic interface binding**:
  `bind` chấp nhận value tuple nhiều impl (phần tử đầu = mặc định), cờ runtime
  `xime.di.dynamic-binding` (mặc định tắt = hành vi cũ); khi bật, consumer nhận
  `DynamicProxy` trong suốt và `Switcher` đổi impl toàn cục lúc runtime. Chi tiết:
  `docs/ke-hoach-0.6.md`, `rules/interface-binding.md` mục 12.
- **Web adapter:** hoàn thành, có `configure_middleware` /
  `configure_exception_handlers`. **Mới (0.6.1):** middleware lấy
  dependency từ DI / runtime config qua marker `Inject(...)` / `FromConfig(...)`
  làm giá trị option (phân giải lúc `build_app`, `adapters/web/_markers.py`) +
  helper `configure_cors(...)` (`adapters/web/_cors.py`) - app không phải subclass
  `WebAdapter` nữa. `RequestContextMiddleware` + `JwtAuthMiddleware`
  là **pure-ASGI** (0.5, sửa context-bleeding). File streaming ở
  `adapters/web/files` (`stream_object` Range, `save_upload`).
  **Mới (0.6.3): HTTPS.** Khối `server.ssl` trong `application.yml` ->
  `ServerTlsConfig` (`certfile`/`keyfile`/`keyfile_password`/`ca_certs`/
  `cert_reqs`/`ciphers`); để trống = HTTP thuần như cũ. `cert_reqs` dùng **chữ**
  (`none`/`optional`/`required`), không phải số `ssl.CERT_*`. Validate fail-fast ở
  `_tls_kwargs()` (`adapters/web/_adapter.py`) vì lỗi gốc của uvicorn khi cert
  khai nửa vời không debug được (`AssertionError` rỗng message); chỉ forward
  option thực sự được cấu hình - truyền `ssl_cert_reqs=None` sẽ ném `ValueError`.
  Multi-server: `WebAdapter(..., ssl=...)`, để trống thì **kế thừa** `server.ssl`
  (server phụ không được âm thầm chạy HTTP). Cert phải là **CA công cộng**
  (certbot), KHÔNG dùng cert Trust - browser không tin CA nội bộ. Thiết kế, phần
  đã bỏ (mức 2) và hướng nâng cấp: `docs/tls-cho-web-adapter.md`.
- **gRPC code-first (server):** hoàn thành - `xime grpc generate/check`, sinh
  proto + lock + sidecar `contract.json`, serve qua nối dây động, mTLS động
  (`configure_grpc_tls`).
- **gRPC client SDK:** hoàn thành Phase 1-4 - `xime grpc client` sinh SDK
  (kèm `--package`), `configure_grpc_clients` + DI, `XimeGrpcChannel` (deadline,
  lỗi typed, mTLS động, retry policy 0.3 chỉ unary, `tls.server_id` multi-server).
- **Socket adapter:** hoàn thành (dùng chung contract với gRPC code-first).
- **MQTT adapter (0.5):** hoàn thành - `@subscribe` (pub/sub) + `@rpc` (RPC over
  MQTT v5), `MqttPublisher`, auto-reconnect, định tuyến bằng Subscription
  Identifier, extra `xime[mqtt]` (aiomqtt import lười). Vòng lặp live cần broker
  thật để test E2E (`tests_temp/mqtt/test_integration.py`, guard-skip).
- **Storage starter (0.5):** hoàn thành - Protocol `StorageService` + backend
  `localfs` (chống path traversal, ghi nguyên tử) và `s3` (multipart, presigned,
  MinIO; extra `xime[s3]`). Key chuẩn hóa chung qua `storage/_keys.py`.
- **Mail starter (0.6.2):** hoàn thành - Protocol `MailService` + backend
  `SmtpMailService` (aiosmtplib, extra `xime[mail]`, import lười). `send(EmailMessage)`
  async đồng-bộ-logic: await tới khi gửi xong, timeout nội bộ, thất bại ->
  `MailSendError` (giữ `__cause__`). `EmailMessage` (frozen dataclass) hỗ trợ
  HTML + text (cả hai -> multipart/alternative), nhiều người nhận, `cc`, `reply_to`,
  `sender` override `mail.from`. Mỗi `send()` mở/đóng một kết nối SMTP (không pool),
  tự chọn STARTTLS (587) / TLS ngầm (465) theo cổng. Đọc `mail.*` từ `RuntimeConfig`
  (`mail.smtp.host` bắt buộc). Gửi nền là việc của app (tự `create_task`). Hiện thực:
  `xime/starters/mail/`.
- **SQLAlchemy starter:** thêm `CrudRepository[T]` (0.6.1) - base repository generic
  cho sẵn `find/find_or_fail/find_all/exists/count/save/save_all/delete`; `model`
  là abstract property nên lớp nền là abstract (scanner bỏ qua), chỉ subclass set
  `model` mới vào DI. `find_or_fail` ném `EntityNotFoundError`. Hiện thực:
  `xime/starters/sqlalchemy/repository.py`.
- **Khối chỉ đọc `read_only()` (0.6.3):** usecase không ghi dùng `ReadOnlyManager`
  (`core/transaction/readonly.py`) - manager **riêng, cùng cấp** với
  `TransactionManager`, KHÔNG phải method của nó (tách binding để sau này trỏ đường
  đọc sang read replica bằng một dòng `bind`, không sửa code nghiệp vụ). Impl:
  `starters/sqlalchemy/readonly.py`. Bốn điểm dễ phá khi sửa: (1) **không bao giờ
  commit**; (2) lồng trong khối đang chạy thì **mượn session**, thoát ra không làm
  gì - đừng đổi thành ném lỗi, ca "service chỉ đọc ghép vào usecase có ghi" là ca
  thật; (3) **`expunge_all()` phải chạy TRƯỚC `rollback()`**, bỏ dòng đó thì entity
  trả ra ngoài ném `DetachedInstanceError` (có 2 test canh, đã kiểm chứng bằng cách
  xóa thử); (4) không gọi `begin()` tường minh, để autobegin. **Ranh giới đã chốt:**
  framework KHÔNG chặn việc sửa entity đọc ngoài transaction (thay đổi bị bỏ im
  lặng) - cố ý, bù bằng quy tắc tài liệu, đừng đề xuất hook SQLAlchemy event. Chi
  tiết: `rules/transaction.md`.
- **Modbus adapter (0.7):** hoàn thành - master (đọc theo yêu cầu + `@poll`/
  `@on_change`) và slave (`@serve`/`@on_write`). Trục chính là **Device Model khai
  báo** (`@device` + `Holding/Input/Coil/Discrete`) tự giải mã thanh ghi. Bốn điểm
  dễ phá khi sửa: (1) **địa chỉ có hai đường vào tường minh** - `Holding(2)` là
  0-based, `Holding(modicon=40003)` là số datasheet; đừng gộp thành một tham số
  "thông minh", nhập nhèm sẽ đọc nhầm thanh ghi mà KHÔNG báo lỗi; (2) **planner gom
  range theo `max_gap`, KHÔNG đọc một block lớn** - block lớn quét trúng địa chỉ
  không tồn tại là hỏng cả lần đọc (`ILLEGAL DATA ADDRESS`); (3) **`@on_change`
  không bắn ở lần đọc đầu** (chỉ lấy mốc) - đổi thành bắn là mọi handler kêu lúc
  khởi động; (4) **bốn vùng nhớ là bốn không gian tách biệt**, một lệnh đọc không
  bao giờ trải qua hai vùng. Phần slave dùng `SimData`/`SimDevice`, KHÔNG dùng
  `ModbusServerContext` (đã deprecated, xóa ở pymodbus v4, và trên 3.14 còn lệch
  địa chỉ một đơn vị). Extra `xime[modbus]`, floor `pymodbus>=3.14`. Tài liệu:
  `docs/{vn,en}/modbus.md`.
- **OPC UA adapter (0.7):** hoàn thành - client (`read`/`read_model`/`write`,
  `@on_node_change`) và server (`@serve_nodes`/`@on_node_write`), đủ ba mức bảo
  mật None/Sign/SignAndEncrypt. Ba điểm dễ phá: (1) **đọc bằng
  `read_attributes()`, KHÔNG dùng `read_values()`** - hàm sau vứt StatusCode từng
  node nên NodeId sai trả `None` im lặng; (2) **giá trị đầu tiên chỉ là mốc**
  (`initial=False` mặc định) để giống quy tắc `@on_change` của Modbus; (3) **node
  có `@on_node_write` thì client làm chủ**, vòng refresh không ghi đè. Handler
  chạy trong task riêng vì `asyncua` gọi callback ĐỒNG BỘ. Extra `xime[opcua]`.
  Tài liệu: `docs/{vn,en}/opcua.md`.
- **JWT (0.5):** thêm ép `audience`/`issuer`, phơi claim qua `request_context[JWT_CLAIMS]`.
- **Danh tính peer mTLS (0.6.3):** ngoài `PEER_CN` (định danh **tiến trình** gọi, có từ
  0.4) nay còn **`PEER_APP_ID`** - định danh **APPLICATION** sở hữu tiến trình đó, đọc từ
  SAN URI `xime-app://<Base62 33 ký tự>` của client cert. Helper `current_app_id()` cạnh
  `current_caller()` (`core/security/peer.py`); trích xuất ở
  `adapters/grpc/interceptors/_context.py` (`_read_peer_app_id`, gọi trong
  `_set_peer_identity` nên cả unary lẫn streaming đều có). SAN là property **nhiều giá
  trị** -> duyệt hết entry, chấp nhận cả dạng `URI:` prefix, fail-soft tuyệt đối (cert lạ
  -> `None`, không bao giờ ném). Framework chỉ cấp sự thật thô: KHÔNG giải Base62, KHÔNG
  kiểm app tồn tại, KHÔNG kiểm quyền. Bối cảnh: `docs/peer-app-id-tu-san-cert.md`.
- **Cờ boolean trong runtime config (0.6.3):** đọc bằng `RuntimeConfig.get_bool(key)`, đừng
  dùng `bool(runtime.get(key))` - `bool("false")` là `True` nên chuỗi trong YAML sẽ bật
  nhầm tính năng. `get_bool` ép kiểu bằng chính bộ parse của Pydantic, giá trị lạ ném
  `StartupException`.
- **Kiểm toán toàn diện 0.5:** xem `docs/kiem-toan-0.5.md` (mọi phát hiện đã xử lý).
- **Kiểm toán trước khi đẩy PyPI (0.7.0): XONG 2026-07-30** - xem
  `docs/kiem-toan-0.7.md`. Khác hai đợt trước ở chỗ soi thêm **lớp đóng gói/phát
  hành** (build, nội dung wheel/sdist, cài vào venv trắng, floor deps,
  `mypy --strict` phía người dùng) và **tính đúng đắn của tài liệu** - hai lớp mà
  1427 test không chạm tới. 16 phát hiện, **đã vá hết**, +27 test canh.
- **Kiểm toán toàn diện 0.6.2:** xem `docs/kiem-toan-0.6.md` (không có lỗi CAO;
  M1a/b/c "thiếu test" là báo động giả - đã có test; M2 version fallback + L1-L5
  hardening nhỏ đã vá; bài học: kiểm "có test cho X" bằng Grep nội dung, không Glob tên file).
- **Backlog lỗi: HIỆN KHÔNG CÒN MỤC NÀO MỞ** (`docs/backlog-sua-loi.md` - cả 11 mục
  đã đóng). Đừng đọc file đó để "tìm việc"; nó chỉ còn giá trị tra cứu lỗi cũ đã sửa
  thế nào. Hai mục theo dõi B1/B2 từ kiểm toán 0.6 cũng đã xử lý ở 0.6.3.

## Tài liệu cần đọc khi bắt đầu

- **Tổng quan dự án & kiến trúc:** `../CLAUDE.md`
- **Nguyên tắc code & DI:** `rules/coding.md`
- **Thiết kế Transaction:** `rules/transaction.md`
- **Interface Binding (Protocol):** `rules/interface-binding.md`
- **Code ở mức module phải nhẹ (mới 2026-08-19):** `rules/module-level-code.md` - mọi thứ
  ngoài `if __name__` chạy **`N+1`** lần (cha cũng chạy lại `main.py`). Mức module chỉ được
  **KHAI BÁO**, không được **LÀM**. ⚠ Giá trị không tất định (`uuid4()`, `time.time()`) hỏng
  **tệ hơn** kết nối thừa: mỗi tiến trình một giá trị khác, mà code đọc nó tin là dùng chung.
  Hai phép dò **không thay thế nhau**: một đo *hậu quả* (chậm), một tìm *nguyên nhân* (tên hàm)
- **Vòng lặp nền & tắt máy (mới 2026-08-04):** `rules/background-tasks.md` - `create_task` chưa
  chạy dòng nào; đừng viết đường tắt giả định task đã khởi động. Kèm bảng phân biệt hình dạng an
  toàn / nguy, và lý do **mock không bắt được loại lỗi này**

## Tài liệu thiết kế chi tiết (đọc khi cần)

- **Lộ trình phiên bản (0.3 -> 0.9, tra "việc X làm bản nào"):** `docs/lo-trinh-phien-ban.md`
- **Kế hoạch 0.8 (thiết kế ban đầu chốt 2026-06-27: Multi-process Runtime + Bus + config):** `docs/ke-hoach-0.8.md`
- **Cache liên tiến trình - BỐI CẢNH (2026-08-16). ⚠ Phần thiết kế đã tách sang hai file riêng, xem hai mục ngay dưới:** `docs/cache-lien-tien-trinh-2026-08-16.md`
  - Chốt: **tách bus khỏi kho** · cache chia **HAI nhóm theo việc có nguồn bền vững hay không**
    (nhóm 1 tự viết shared memory hai-bản-đổi-con-trỏ, nhóm 2 **LMDB**, mỗi bảng một file) ·
    **đa tiến trình TRƯỚC, đa luồng để sau**
  - ⚠ Lý do hoãn đa luồng là **số đo, không phải sở thích**: `grpcio` chưa có wheel free-threaded
    và gRPC là xương sống của Xime, nên bật bản không GIL là **GIL tự bật lại** -> N luồng chậm
    hơn một luồng. `lmdb` cũng chưa có. Tín hiệu duy nhất đáng theo dõi để xét lại
  - ✅ **Bảng "chưa quyết" ở mục 3 ĐÃ ĐÓNG HẾT 2026-08-19** - xem `docs/kho-nhom-2-store-2026-08-19.md`.
    ⚠ Ba câu **tan chứ không được trả lời** (câu 2 `AtomicStore` · câu 7 ba kết cục · câu 8 mở
    kho ở đâu): chúng giả định một hình dạng thiết kế mà buổi 08-19 không chọn. Đọc bảng đó
    như **lịch sử lập luận**, đừng đọc như việc còn phải làm. Và **3 chỗ bổ sung/lật một phần
    `ke-hoach-0.8.md`** (DI scope hai tầng -> bốn tầng, primitive asyncio không qua được ranh
    giới loop, kết nối DB nhân theo M×N); chỗ thứ tư (*kiểu queue*) **đã tan** vì bus bỏ hẳn
    queue chung
  - ⭐ **`link_id` của bus giải luôn mục 7.2** (số hiệu đời kho / fencing token) trong phạm vi
    một máy. ⛔ Nhưng **7.1 `TrustKeyL2Cache` thì không** - nó cần chia sẻ giữa nhiều máy
- **⭐⭐ Đa tiến trình: `main.py`, cấu hình, mô hình chạy (2026-08-16, PHẦN LỚN ĐÃ CHỐT):**
  `docs/da-tien-trinh-main-va-cau-hinh-2026-08-16.md` - nửa sau cùng buổi với file trên.
  **Đọc mục 5 trước khi động vào `core/bootstrap` hoặc bất kỳ adapter nào**
  - **`main.py` chốt**: `import config` · `add_config(config)` · `use(...)` **ở mức module**;
    `if __name__` chỉ còn `share_load().run()`. **Không id tiến trình nào trong code** - cấu
    hình khai ma trận `process_id × server_id`, ô giao nhau là cổng
  - **Mô hình chạy chốt**: tiến trình gốc **giữ socket nhưng không phục vụ** (`bind`, không bao
    giờ `accept`, không dựng DI, không chết); con là `python -m app.main` **chạy lại** với
    `XIME_PROCESS_ID`, sinh bằng **`multiprocessing`** (truyền được socket **và** vẫn import lại
    main). Lý do chọn chạy lại thay vì entry riêng: **một đường khởi động duy nhất** - hai đường
    là hai bản trôi lệch, và loại lệch đó không có triệu chứng. `primary` nay là **con thứ
    nhất**, nên supervisor **thăng cấp** được con khác khi nó chết
  - **Chia tải theo adapter**: web + unix socket dùng **cha giữ socket** (chạy cả Linux lẫn
    Windows) · gRPC dùng **`SO_REUSEPORT`**, Windows **không có đường nào** → phải báo lỗi lúc
    khởi động, đừng để nổ bằng `WinError 10048` giữa chừng
  - ⭐ **BA hạng adapter, không phải hai**: nhân bản (web, grpc) · **phân mảnh** (modbus, opcua,
    **mqtt** - mỗi tiến trình một cụm thiết bị / một tập topic; nhân bản cho *dư thừa*, phân mảnh
    thì **không**) · **đơn nhất** (scheduler). ⚠ Bản đầu ghi *"bốn hạng"* khi mqtt còn xếp riêng;
    sửa 2026-08-19 vì phần 3 của mảng adapter dựng thẳng trên phân loại này
  - ⛔ **MQTT: giữ là CLIENT, KHÔNG tự viết broker** (5.7.4, chốt sau khi chủ dự án hỏi về nhà
    thông minh / nhà máy / nông nghiệp thông minh). Lý do nặng nhất: **firmware đầu kia không sửa
    được**, nên broker thiếu tính năng = thiết bị không kết nối được và không có đường vá. Dùng
    **Mosquitto** (EPL/EDL), lên **EMQX OSS** khi cần cluster - đổi broker chỉ là đổi một dòng
    `host`. ⭐ Cái đáng đầu tư thay vào đó: **Sparkplug B** · lưu chuỗi thời gian · engine quy
    tắc · **sổ đăng ký + danh tính thiết bị** (Xime đã có sẵn nền: Trust, hồn-xác, `PEER_APP_ID` -
    đây mới là chỗ khác được). Kèm **ba tín hiệu để xét lại**, chưa cái nào xuất hiện
  - **Chia tải MQTT: chia THEO TOPIC, không dùng shared subscription.** ⭐ Lý do quyết định là
    **thứ tự trong một thiết bị**: `$share` phát `bật`→`tắt`→`bật` cho ba tiến trình xử lý song
    song thì trạng thái ghi xuống DB là *cái nào thắng cuộc đua*, không phải cái đến sau. Cùng
    khái niệm partition key của luật 01 - khoá phải là **thiết bị/cụm**, ⛔ đừng chia theo loại đo.
    Ba việc còn nợ: tách `client_id` khỏi `_server_id` · `client_id`+`topics` vào khối `processes`
    (ba tầng, **không** cần bốn tầng như Modbus) · **topic filter phải đến từ cấu hình, không phải
    hằng trong `@subscribe`**. ✅ Backpressure thì **đã có** (semaphore trước `create_task`)
  - ⭐ **Fieldbus (5.7.3), chốt chiều**: tách **LOẠI** (`bang-tai`, code biết) khỏi **THỰC THỂ**
    (`BT-01`, cấu hình biết) - bốn tầng khoá `process → modbus → loại → thực thể`. Kèm luật
    **web KHÔNG gọi thẳng adapter fieldbus** (kernel chia request ngẫu nhiên nên gọi thẳng hỏng
    *một nửa số lần* - kiểu lỗi tệ nhất để gỡ): đọc qua DB/vùng nhớ chung, **ghi qua BUS**. Đây
    là ca dùng cụ thể đầu tiên của bus, và nó **dùng lại kênh cha-con vốn đã cần** cho thăng cấp
    primary nên gần như miễn phí
  - ⭐ **Nguyên tắc chủ dự án nêu (2): *"cứ thay đổi code framework thoải mái, để code phục vụ
    thiết kế"*** → đổi API dứt khoát, không giữ hai đường tương thích
  - ✅ ~~**Câu khó nhất còn lại: `post_construct` ở tiến trình phụ**~~ **ĐÓNG 2026-08-18** bằng
    Protocol **`RunOnce`** - xem khối *"Buổi 2026-08-18"* ngay dưới. Mô tả cũ của vấn đề:
    (mục 2.9). Không cắt được ở
    mức tiến trình (cắt luôn pool DB, key JWT) **và cũng không cắt được ở mức class** vì hook đặt
    trên method - `KeyRefreshJob` vừa nạp key ban đầu (mọi tiến trình cần) vừa chạy vòng lặp
    (chỉ primary). Kèm một cái giá chưa ai nêu: **hoãn là biến fail-fast thành fail-late**
  - ⭐ **`add_config(module)` không phải chuyện thẩm mỹ, nó là ĐIỀU KIỆN CẦN**: auto-discovery
    hiện tại dò bằng `__main__.__spec__.parent`, mà giá trị đó **khác ở tiến trình con** → im
    lặng rơi xuống `BindingConfig()` rỗng, DI trống, không gì báo. Kèm phát hiện
    `_import_config_siblings()` dùng `pkgutil.iter_modules` là **auto-scan, vi phạm chính
    `rules/config-discovery.md`**
  - ⭐ **Nguyên tắc chủ dự án nêu: adapter phải đổi theo thiết kế, thiết kế không đổi theo adapter**.
    Ca cụ thể: `MqttAdapter` gộp `_server_id = client_id`, và cái gộp đó **tạo ra một giới hạn
    KHÔNG có thật** ("MQTT không nhân bản được")
  - ⭐ **Nguyên lý DI**: DI = tổng khai báo trừ phần đơn nhất; **chỉ loại trừ được node ĐẦU DÒNG**
    (không ai phụ thuộc vào nó). Đề nghị biến thành **phép kiểm tự động** vì đồ thị đã có sẵn
  - ⚠ **Hai nguyên tắc rút ra khi chủ dự án bác đề xuất**: *một chốt chặn không được phụ thuộc
    thành phần TUỲ CHỌN* (bác khoá LMDB - nó vắng mặt đúng lúc cần nhất) · *đừng viết bộ cân
    bằng tải* - `SO_REUSEPORT` + nginx **cùng máy** lấy được cùng lợi ích mà không mất LMDB;
    thứ phá LMDB là **nhiều máy và cách ly filesystem**, không phải bản thân reverse proxy
  - Mục 8 liệt kê **19 đề xuất đã bị bác kèm lý do** - đọc trước khi đề xuất lại. Đáng nhớ nhất:
    **LMDB làm đệm ghi cho Postgres** (cái giá thật là *mọi đường đọc về sau phải nhớ hỏi LMDB
    trước*, nghĩa vụ không cưỡng chế được) · **cho MQTT qua bộ cân bằng tải** (sai chiều kết
    nối: app MQTT là client, không mở cổng nào)
  - Còn lại: **3 chỗ chủ dự án xem hôm sau** (tách đăng ký job khỏi chạy scheduler · cổng server
    phụ · luật "code mức module phải nhẹ") + 6 câu cũ ở mục 9.2
  - **Cộng với file cache, phần lớn `ke-hoach-0.8.md` không còn cần: nên VIẾT LẠI chứ không bổ sung**
- **⭐⭐ Bus liên tiến trình `ProcessLink` (2026-08-18, THIẾT KẾ ĐÓNG):**
  `docs/bus-lien-tien-trinh-2026-08-18.md` - thay hẳn phần Bus của `ke-hoach-0.8.md`, và **lật
  cả bản phác 5.7.4b** của file đa tiến trình. Chưa có một dòng code nào.
  - ⚠ **KHÁC HẲN `EventBus` trong `core/event/`**, không dùng chung một dòng nào. Tên cố ý không
    chung gốc từ (`link.ask` vs `event_bus.publish`) vì gọi nhầm thì **không có triệu chứng**:
    tin không bao giờ ra khỏi tiến trình, không lỗi, không log
  - **Cơ chế**: bộ nhớ chung (`shared_memory`), **mỗi tiến trình một vùng ghi riêng** nên không
    tranh chấp ghi và **giữ được thứ tự**; `mp.Semaphore` làm **chuông**, bitmap "ai chưa đọc"
    làm **sự thật**. ⭐ **Cha KHÔNG nằm trên đường đi** - hết nút cổ chai, hết điểm chết
  - **Định tuyến**: kênh + khoá, **lọc ở bên nhận**, `key` ở header nên lọc mà **chưa chạm
    payload**. Không có tên tiến trình ở bất cứ đâu - cùng lý do đã chặn `current_process_id()`
  - **Bốn kết cục** của `ask` (luật 03): `Done` · `NoOwner` (lỗi **cấu hình**) · `NoAnswer` ·
    `Failed`. ⚠ `Done` nghĩa là *handler đã nhận và trả lời*, **không** nhất thiết là *việc đã
    làm xong* - ngữ nghĩa đó do app định nghĩa
  - **at-most-once**: hạ bit **trước** khi làm. Muốn chắc thì **app tự thêm hàng đợi động**
  - **Đầy thì vòng lại và đè**, kèm bắt buộc **đếm `missed`** của người chưa đọc. Nhờ vậy một
    tiến trình treo **tự chịu**, không nghẽn ai
  - ⭐ Đo được: **bộ nhớ chung 17,4 µs · socketpair 16,8 µs, gần như BẰNG NHAU** (thời gian bị
    chi phối bởi *đánh thức*, không phải copy) · `mp.Lock` 0,85 µs · **"kiểm tra chỗ trống rồi
    mới đặt" thật sự đua: 4/2000 slot bị cấp hai lần**
  - **Bus dựng TRƯỚC DI**, nên nó **KHÔNG dính** câu treo `post_construct` ở tiến trình phụ.
    Cha dùng chính bus làm **kênh điều khiển** qua kênh nội bộ `__xime__` (framework luôn tạo),
    nên **ràng buộc (b) của thăng cấp primary hết cần pipe riêng** và **F10 đi cùng đường**
  - ⚠ Thiết kế cho **`N = 1` luồng mỗi tiến trình**. `N > 1` không đòi đổi cấu trúc chia sẻ,
    chỉ thêm một tầng phân phối bên trong tiến trình (và tầng đó **không được dùng
    `asyncio.Queue`**)
  - Mục 11 liệt kê **19 hướng đã loại kèm lý do** - đọc trước khi đề xuất lại
  - ⭐⭐ **Mục 12 - nó đỡ được gì cho phần khác của 0.8**: đóng hẳn **2** câu của tài liệu kho
    (mở kho ở đâu · nút cổ chai queue chung) · cho khuôn sẵn cho **4** câu chưa quyết (trong đó
    **`link_id` giải bài toán fencing token** gần như miễn phí) · mở lối cho **3** câu treo
    (⭐ **`post_construct` phải PHÁT BIỂU LẠI** - luật 2.7 vốn đã cấm nó chạm mạng và
    `create_task`, nên vấn đề nhỏ hơn nhiều; **scheduler cùng lời giải**; **pipe cha-con**).
    ⛔ Kèm **2 chỗ KHÔNG chuyển được**: *"đầy là triệu chứng"* chỉ đúng cho bus chứ không đúng
    cho kho · và **bus khai kích thước ở `.py` trong khi kho đề xuất `application.yml`** - phải
    soi một lần có chủ ý
- **⭐⭐ Kho nhóm 1 - `RefData` (2026-08-18, THIẾT KẾ XONG):**
  `docs/kho-nhom-1-snapshot-2026-08-18.md` - phần kho **không dùng LMDB**, tách khỏi tài liệu
  cache theo yêu cầu chủ dự án. Chưa có dòng code nào.
  - **Ranh giới hai nhóm**: dữ liệu **có nguồn bền vững** hay không. Nhóm 1 = khoá JWT, danh bạ
    app, cấu hình đã phân giải - đọc nhiều, ghi hiếm, **thay trọn gói**, mất thì nạp lại được
  - ⭐ **Ba lý do khiến tự viết ở đây RẺ chỉ đúng với nhóm 1** (không cần cấp phát · không có
    khoá nào · người ghi chết giữa chừng vô hại) - **cả ba đều MẤT khi sang bus**. Dùng lại vật
    liệu thì được, dùng lại sự dễ dàng thì không
  - **API**: `RefData[T]` **subclass** đúng khuôn `CrudRepository` (lớp nền abstract, subclass
    khai `name` mới vào DI, có generic nên `mypy` hiểu), `configure_refdata([Class, ...])`
    truyền **class** như `configure_link`, và `read()`/`read_or_fail()` đúng cặp
    `find()`/`find_or_fail()`
  - `read()` trả **object thật, không copy** - **số đời làm chìa khoá cache L1**, đường thường
    lệ chỉ là **một phép so số nguyên**. ⚠ Object đó **dùng chung, không được sửa**
  - **`None` = CHƯA SẴN SÀNG**, tách hẳn khỏi *tập rỗng*. Không cần thêm bit cờ - `so_doi` đã
    đủ. ⛔ **`read()` KHÔNG tự chờ** (chờ trong `read()` là treo request); chờ là lời gọi riêng
    ở tầng khởi động, **có timeout**
  - **Chỉ primary `publish()`**, người khác gọi thì **nổ** - hai người ghi là hỏng **im lặng**
  - ⭐ **Chia đoạn khi dữ liệu lớn** (chủ dự án chốt): chỉ THÊM không thu · người đọc tự attach
    đoạn lạ · **`decode` phải đọc theo dòng** (`unpacker.feed`), nối đoạn trước là một lần copy
    toàn bộ. **Khai hình dạng ngay từ v1, nhưng v1 chỉ dùng một đoạn**
  - ⚠ **Vượt trần nguy hơn ở bus**: primary không publish được thì **cả cụm dùng bản cũ mãi
    mãi**, và **không request nào lỗi** cho tới khi token ký bằng khoá mới xuất hiện. Ba lớp:
    cảnh báo 80% · nổ nhưng giữ bản cũ · đánh dấu `loi_thoi` trong `stats()`
  - ⭐ **Nó cắt bớt một mảng của cái vướng ở luật 2.7**: primary gọi Trust rồi publish, tiến
    trình phụ chỉ read nên **không chạm mạng lần nào**
  - ✅ **Mục 10: 8/8 câu ĐÃ CHỐT 2026-08-19.** Đáng nhớ: **mỗi RefData một vùng nhớ
    RIÊNG** (*"các bảng nên không liên quan gì đến nhau, kể cả bộ nhớ"*) · trần seqlock
    **100 vòng rồi NÉM** (không trần thì một lỗi lạ thành request treo vô hạn, không
    log, không triệu chứng) · và câu 1 (*cha có đợi primary publish*) **đã có đáp án từ
    08-18** - cơ chế chờ qua bus, nên cha **sinh con đồng thời, không đợi**
- **⭐⭐ Kho nhóm 2 - `Store` trên LMDB (2026-08-19, THIẾT KẾ XONG):**
  `docs/kho-nhom-2-store-2026-08-19.md` - phần kho **dùng LMDB**, cho dữ liệu **không có
  nguồn bền vững** (hãm nhịp, thử thách passkey, chống lặp). Chưa có dòng code nào.
  - ⛔⭐ **Phạm vi: MỘT máy, luôn luôn** (chủ dự án chốt, mục 2.7 tài liệu cache).
    *"nhiều máy tôi đã chia shard"* - đừng nêu phương án nhiều máy nữa, kể cả dưới dạng
    đường lui
  - **Ba lớp nền**: `Store` (bytes) · `CounterStore` (int, có `incr`) · `Store[T]` (kiểu
    riêng của app). ⭐ Tách theo kiểu **không phải chuyện thẩm mỹ**: `incr` chỉ có nghĩa
    với số, đặt nó lên một `Store` chung là hợp đồng hứa thứ nó không giữ được
  - ⭐ **Cấu hình đi bằng THAM SỐ CLASS (PEP 487)**, không phải thuộc tính trong thân:
    `class HamNhip(CounterStore, name="...", ttl=900, parts=4)`. Chủ dự án nêu chỗ vướng
    *"cấu hình với dữ liệu đang nằm 1 chỗ"*; kwargs tách triệt để, không thể va tên, và
    `mypy` kiểm được. **Áp cùng quy ước cho `RefData`**
  - **Vào DI bằng `scan`**, không cần `configure_*` - khác `RefData`/`ProcessLink` vì
    mở một file LMDB không cần cấp phát chung. ⚠ Hệ quả: **câu 8 của tài liệu cache TAN**
  - **Chia file theo `crc32(key) % parts`**, `parts` do lập trình viên chọn, mặc định 1.
    ⛔ Chia theo **tiến trình ghi** (đề xuất ban đầu) cho zero xung đột nhưng **phá hẳn
    `set_if_absent`** - mỗi tiến trình thành người-chiếm-đầu-tiên trong vũ trụ riêng.
    ⛔ **`crc32` chứ không phải `hash()`** - `hash()` ngẫu nhiên lại mỗi tiến trình, đo
    được, và hỏng hoàn toàn im lặng
  - **Lỗi kho báo bằng NGOẠI LỆ**, không phải kết cục trong kiểu trả về: với `incr` /
    `set_if_absent` thì ngoại lệ là **fail-closed tự nhiên**, còn quên một nhánh của kiểu
    trả về là **fail-open im lặng**. ⭐ Ranh giới với bus: *kết quả bình thường thì kiểu
    trả về; sự cố hạ tầng thì ngoại lệ*. Đây là cách **câu 7 tan**
  - ⭐ Số đo: **đọc từ page cache 0,22 µs · gather đắt gấp 27 · thread pool đắt gấp 439**.
    Đọc LMDB không phải I/O nên **không song song hoá được, và không cần**
  - ✅ **Mục 7: còn treo HẾT.** `incr` **gia hạn TTL mỗi lần GHI**, đọc không đụng tới -
    đề nghị ban đầu của phiên (*giữ hạn lần đầu*) đã bị bác, và bác đúng: cạm bẫy "khoá
    vô hạn" mà nó lo **không xảy ra** vì app thoát sớm trước khi `incr`. Thứ còn lại
    **không phải câu hỏi thiết kế** mà là hai phép đo phải làm khi có VPS Linux
- **Kế hoạch triển khai 0.5 (đã phát hành 2026-06-22 - feature trước, audit sau):** `docs/ke-hoach-trien-khai-0.5.md`
- **Báo cáo kiểm toán 0.5 (mọi phát hiện H1/M1-M7/L1-L11/I1-I2 đã xử lý):** `docs/kiem-toan-0.5.md`
- **Kế hoạch 0.6 (ĐÃ PHÁT HÀNH 2026-06-23: Việc 1 thay `dependency-injector` + Việc 2 dynamic interface binding; version + CHANGELOG đã đồng bộ 0.6.0):** `docs/ke-hoach-0.6.md`
- **Kế hoạch 0.3 (hardening):** `docs/ke-hoach-0.3.md`
- **Thiết kế tổng thể:** `docs/tai-lieu-thiet-ke.md`
- **Giới thiệu & triết lý:** `docs/gioi-thieu-framework.md`
- **Cây thư mục dự án:** `docs/cay-thu-muc.md`
- **Entry point ứng dụng (`main.py`):** `docs/app-entry-point.md`
- **Routing layer (class-based controllers, `_make_handler`):** `docs/routing-layer.md`
- **Kế hoạch gRPC Client SDK + mTLS động (chốt 2026-06-12):** `docs/grpc-client-mtls-plan.md`
- **Kế hoạch 0.7 (CODE XONG 2026-07-30, chưa commit: Modbus + OPC UA; có bảng tiến độ, 4 quyết định đã chốt, 4 chỗ API pymodbus lệch so với thiết kế):** `docs/ke-hoach-0.7.md`
- **⭐ Kết quả 0.7.1 (2026-08-03): server-stream có kiểu + đợt 2 vá bảo mật:** `docs/ket-qua-0.7.1-2026-08-03.md`
- **Yêu cầu gốc của phiên data-service/user-service (đã làm xong):** `docs/yeu-cau-server-stream-kieu-du-lieu-2026-08-02.md`
- **Kiểm toán bảo mật 0.7 + kế hoạch vá (đợt 2 xong, đợt 0/1/3/4/5 chưa):** `docs/kiem-toan-bao-mat-0.7.md`, `docs/ke-hoach-va-bao-mat-2026-08-01.md`, `docs/cho-quyet-bao-mat-2026-08-01.md`
- **`PEER_APP_ID` - định danh app từ SAN cert (ĐÃ LÀM 0.6.3):** `docs/peer-app-id-tu-san-cert.md`
- **TLS/HTTPS cho web adapter (ĐÃ LÀM 0.6.3, mức 2 đã bỏ):** `docs/tls-cho-web-adapter.md`
- **Backlog lỗi cần sửa (event bus tests, pb2 collision):** `docs/backlog-sua-loi.md`
- **Wishlist tính năng tương lai (bidi, transport TCP, retry...):** `docs/wishlist-tinh-nang.md`

## Việc đang chờ làm ở repo này

> ### ⭐ Nguyên tắc chia bản (chốt 2026-08-16) - đọc trước hai bảng dưới
>
> **0.7.x KHÔNG đổi API công khai một dòng nào; mọi thay đổi API gom vào 0.8.**
>
> Chủ dự án chốt *"đổi dứt khoát, không giữ hai đường"* - mà đổi dứt khoát rải rác qua
> nhiều bản patch là thứ tệ nhất cho 31 app dùng chung một cây mã editable. Nguyên tắc này
> quyết định gần hết việc xếp mục nào vào đâu.

### 0.7.x - vá và phát hành, không chạm API

| # | Việc | Ghi chú |
| --- | --- | --- |
| 1 | ✅ ~~Commit + đẩy PyPI 0.7.1~~ **và 0.7.2** | **XONG** - đo 2026-08-18: PyPI có **13 bản**, mới nhất `0.7.2`; commit `3cfc3f3 v0.7.2` bên phát triển. ⚠ **Hai thứ còn thiếu**: **tag `v0.7.2`** (tag `v0.6.3`/`v0.7.0`/`v0.7.1` thì ĐÃ CÓ - dòng cũ ghi *"chưa có tag nào"* là sai) · và **repo phát hành `upload` mới ở `a3fcad8 v0.7.1`**, chưa theo kịp bản đã lên PyPI |
| 2 | ✅ ~~A1 - keyset JWT nhiều khoá theo `kid`~~ | **XONG 2026-08-18 phía framework** - xem mục 4b ở trên và [`docs/jwt-keyset-va-trung-tinh-2026-08-18.md`](docs/jwt-keyset-va-trung-tinh-2026-08-18.md). ⚠ **Phần ở 19 app thì CHƯA**: framework không với tới `config/jwt.py` của họ. Nó chỉ **xoá lý do tồn tại** của lỗ - nay có ô thứ ba thay vì phải chọn giữa *"có sẵn PEM lúc khởi động"* và *"không middleware nào"*. Việc còn lại: vá **`saas-foundation/template` trước** (nguồn sinh sôi của 20 app kia), rồi lần lượt |
| 3 | ✅ ~~**F3 - nâng sàn dependency**~~ | **XONG 2026-08-18**, và **rộng hơn đề xuất gốc**: nâng **10 sàn** vì advisory, **sửa 3 sàn khai SAI**, thêm `.claude/scripts/check_dep_advisories.py` làm **bước 1b** của hướng dẫn phát hành. Chi tiết: `CHANGELOG.md` mục `[0.7.2]` + mục F3 của [`docs/kiem-toan-bao-mat-0.7.md`](docs/kiem-toan-bao-mat-0.7.md).<br>⭐ Ba thứ đáng nhớ: vế *"nâng `fastapi` để kéo `starlette`"* của đề xuất gốc **SAI** (mọi fastapi 0.115-0.132 giữ cận dưới `starlette>=0.40.0` đứng yên, chỉ nắp trên di chuyển) nên nay **khai `starlette` trực tiếp** dù không import gì từ nó · phép thử **cài ở đúng sàn rồi chạy test** ra nhiều lỗi hơn `pip-audit`, và cả ba đều **không phải advisory** (`aiomqtt`/`paho-mqtt` mâu thuẫn nhau; `pytest`/`pytest-asyncio` metadata khai hợp mà chạy thì nổ; `sqlalchemy>=2.0` sai suốt **38 bản patch**) · **một advisory không vá được**, đã ghi nhận kèm lý do (`apscheduler` PYSEC-2026-282 - an toàn nhờ **cách nối dây mặc định**, không nhờ thư viện).<br>⚠ **Sàn là `>=` nên pip mặc định cài bản MỚI NHẤT - một sàn sai vì vậy hoàn toàn vô hình cho tới ngày có người ghim xuống.** Đó là lý do bước 1b phải chạy mỗi lần phát hành |
| 4 | ✅ ~~**F14 · F15 · F17**~~ (đợt 5 XONG) | **F14 XONG 2026-08-18**: `validate_object_key` từ chối `\` và NUL. ⭐ Phạm vi thật **rộng hơn một trục** so với báo cáo: không phải hai backend nhận hai tập khoá mà **BA** kết quả cho cùng một khoá (local Windows từ chối · local **Linux NHẬN** vì `\` là tên file hợp lệ · S3 nhận, không phòng tuyến nào). ⭐ Phần đáng vá nhất hoá ra là **NUL, không phải `\`**: `exists()` trả `False` cho khoá sai (**dấu hiệu 3 luật 03**) và `put()` ném `ValueError` trần thay vì `StorageError` - rò kiểu ngoại lệ qua biên API công khai. Test đi **thành cặp**, hai backend **import chung** `UNSAFE_KEYS` chứ không chép tay; đối chứng gỡ vá ra **5 đỏ**. Không app nào phải sửa (`data-service` đã tự chuẩn hoá `\`->`/` từ trước). **1563 passed** (+10).<br>**F17 XONG cùng ngày**: `mqtt.rpc.reply_topics` - chủ dự án chốt **cảnh báo chứ không chặn**. ⚠ Khoá dùng **topic filter MQTT**, không phải tiền tố chuỗi, và **không** mang tên `reply_prefix` như kiểm toán đề xuất - `nhamay/reply/` đọc như tiền tố hợp lý nhưng là filter thì khớp **không gì cả**. Chưa khai thì hành vi y hệt cũ, chỉ một WARNING lúc khởi động và **chỉ khi** client có `@rpc`. ⭐ Bốn chi tiết cố ý, đừng gỡ: kiểm **trước** khi gọi handler (để log vẫn ra khi handler ném lỗi) · cảnh báo **khử trùng lặp + trần 64 topic** (không thì bên gọi biến cảnh báo thành lũ log bằng cách đổi topic - cùng họ F15) · filter sai cú pháp **nổ lúc khởi động** · cảnh báo khởi động chỉ kêu khi thực sự có `@rpc`. Test **thành cặp ở cả hai tầng** (phải kêu / phải im); đối chứng gỡ phép kiểm ra **4 đỏ** còn nhóm "phải im" vẫn xanh. **1577 passed** (+14).<br>**F15 XONG cùng ngày**: trần task `EventBus`, chủ dự án chốt **BỎ** khi quá trần, và chốt luôn chỗ đặt cấu hình - *"bao nhiêu thì bỏ là việc của người thiết kế app... đặt vào file .py cho lập trình viên"*. Nên là **`configure_event_bus()` trong `config/*.py`, KHÔNG có khoá nào trong `application.yml`**. ⭐ Chủ dự án bổ sung giữa chừng thứ cả kiểm toán lẫn tôi đều thiếu: **`never_drop=(AuditEvent, ...)`** - *"lỡ cái quan trọng bỏ lại dở"*; một con số duy nhất thì đối xử với event kiểm toán y hệt event thông báo. ⭐ Đo được hai thứ báo cáo gốc chưa nói: `_pending` giữ tham chiếu mạnh nên **bộ nhớ tăng theo KÍCH THƯỚC EVENT** (20k event x 1 KB = 36 MB), và **task tồn đọng cũng là quyền hạn tồn đọng** (ngữ cảnh bảo mật sống qua `clear_security()`). ⚠ Ba chi tiết đừng gỡ: **bỏ NGUYÊN CON** (nửa event là trạng thái không ai thiết kế cho) · bộ đếm hãm nhịp của cảnh báo *miễn trần* phải **RIÊNG** (`0 % 1000 == 0` khiến bản nháp đầu kêu ở mọi lần publish, có test canh) · mặc định **10.000** chứ không phải không trần. ⛔ **Nợ luật 03 khai ra, cố ý để 0.8**: bên gọi không phân biệt được event bị bỏ với event đã xếp lịch, cả hai trả `None`. Test **16 cái đi thành cặp**, đối chứng ra **8 đỏ / 8 xanh**. **1593 passed** (+16).<br>⚠ **Phát hiện kèm, CHƯA làm**: framework **không bao giờ tự gọi `drain()` lúc tắt máy** nên handler đang chạy bị cắt ngang - tài liệu nay bảo người dùng tự gọi trong `PreDestroy`, sửa tử tế thì thuộc 0.8 vì chạm vòng đời adapter. ⛔ **F9 ĐÃ BỊ XOÁ, không phải được vá**: nó là *"`_read_peer_app_id` neo đầu chuỗi thay vì `find()`"*, mà bản gỡ phụ thuộc khái niệm 2026-08-17 đã bỏ hẳn việc lọc scheme nên **không còn chuỗi nào để neo** |
| 5 | ✅ ~~**F1 - đường xác thực WebSocket**~~ | **XONG 2026-08-18 trong 0.7.2** - chủ dự án chốt làm ngay, **vượt luật "0.7.x không đổi API công khai"** một cách có ý thức vì chưa app nào dùng WS. ⚠⚠ **Kiểm toán bỏ sót một mảnh làm đổi cả bức tranh: framework KHÔNG CÓ đường đăng ký route WebSocket nào cả** - `WebSocketHandler` là lớp nền không gắn được vào app, PoC của kiểm toán chạy được vì nó tự dựng `WebSocketRoute` bằng Starlette. Nên đây là **làm nốt một tính năng chưa làm**, không phải vá lỗi. ⭐⭐ **Chỗ lệch khỏi đề xuất, đáng nhớ nhất: xác thực chạy ở lớp ĐĂNG KÝ ROUTE, KHÔNG nằm trong `on_connect`** - đặt trong `on_connect` là biến chốt chặn thành thứ lớp con xoá đi chỉ bằng cách override, mà đó là method đầu tiên ai cũng override; có test canh handler tự `accept()` vẫn không tới được. Gồm: `@ws("/path")` · **`JwtAuthenticator` tách khỏi middleware** (HTTP và WS dùng CHUNG một định nghĩa "token hợp lệ") · token qua **subprotocol** `xime.bearer.` (trình duyệt không đặt được header - giới hạn nền tảng) · `close_on_token_expiry` mặc định BẬT · `public_paths` dùng chung với HTTP · WARNING khi có `@ws` mà chưa `configure_jwt()`. ⛔ **Kiểm `Origin` cố ý KHÔNG làm**: CSWSH chỉ thật khi xác thực bằng **cookie**, mà subprotocol thì trang kẻ tấn công không có token - **ngày nào thêm cookie thì kiểm `Origin` thành bắt buộc**. ⚠ Hai lỗi trong chính bộ test, khuôn dễ lặp: TTL dưới 1 giây vô dụng (PyJWT ép `exp` về int) và **bản đầu chỉ đòi "bị ngắt" nên xanh cả khi bắt tay bị TỪ CHỐI** - đo đúng triệu chứng của nguyên nhân khác hẳn. 31 test mới, đối chứng **5 đỏ**. **1624 passed** (+31) |
| 6 | Đợt 0 + phần còn lại đợt 1 (A2, A4) | **Nằm ở repo app, không phải framework.** Đợt 0 vẫn chờ chủ dự án quyết A6 (chỗ để secret) |

⚠ **F10 (cô lập adapter, đợt 3) ĐÃ CHUYỂN SANG 0.8** - nó mở rộng `Adapter` protocol, tức
đổi API cho mọi adapter kể cả adapter người dùng tự viết, mà 0.8 đã có sẵn một đợt đổi API
adapter một lượt và supervisor cần đúng tín hiệu "ready" đó.

### 0.8 - đa tiến trình + đổi API adapter một lượt

> ## ⭐⭐⭐ THIẾT KẾ 0.8 ĐÃ ĐÓNG (2026-08-19) - đọc HAI file này trước
>
> | Đọc | |
> |---|---|
> | [`docs/ban-giao-2026-08-19.md`](docs/ban-giao-2026-08-19.md) | **Bàn giao** - bức tranh, **bảy cạm bẫy**, thứ đáng học, việc còn treo |
> | [`docs/ke-hoach-code-0.8-2026-08-19.md`](docs/ke-hoach-code-0.8-2026-08-19.md) | **Kế hoạch thi công** - bảy giai đoạn, và **một câu phải hỏi chủ dự án** trước giai đoạn 6 |
>
> ⚠⚠ **Chưa có một dòng code nào của 0.8.** Sáu tài liệu thiết kế là bản vẽ.
>
> ⚠ **Câu chờ chủ dự án:** framework **không có `/healthz` và `/readyz`** (đo: grep ra rỗng),
> nhưng **ba** quyết định của 0.8 dựa vào chúng - bảng phân biệt hai đầu dò ở 5.7.1, `/readyz`
> của con phụ, và F10 *"luôn báo ra ngoài"*. Ba phương án ở mục 1 của kế hoạch; đề nghị **B+**
> (cấp dữ liệu **cộng** `configure_health()` mặc định TẮT).

> ## ⭐⭐ Buổi 2026-08-19 chốt gì (đọc khối này trước)
>
> Một mảng đóng trọn, một mảng cũ đóng nốt, và **một ràng buộc về phạm vi bản**.
>
> | # | Chốt | Ghi ở |
> |---|---|---|
> | 1 | ⛔⭐ **Kho liên tiến trình LUÔN là phạm vi MỘT MÁY** - *"nhiều máy tôi đã chia shard"*. Đừng nêu phương án nhiều máy nữa | mục 2.7 [`docs/cache-lien-tien-trinh-2026-08-16.md`](docs/cache-lien-tien-trinh-2026-08-16.md) |
> | 2 | **Kho nhóm 2 = `Store` trên LMDB** - ba lớp nền, chia file theo `crc32(key) % parts`, TTL mốc tuyệt đối | [`docs/kho-nhom-2-store-2026-08-19.md`](docs/kho-nhom-2-store-2026-08-19.md) |
> | 3 | **Kho nhóm 1 đổi tên `Snapshot` -> `RefData`**, và **8/8 câu treo chốt hết** | [`docs/kho-nhom-1-snapshot-2026-08-18.md`](docs/kho-nhom-1-snapshot-2026-08-18.md) |
> | 4 | **Cổng server phụ: CẤM HẲN đối số trong code** - *"làm lại 1 lần cho tử tế, chấp nhận đau thương"* | mục 9.1 tài liệu đa tiến trình |
> | 5 | **Fieldbus + MQTT lùi sang 0.8.1** | bảng phạm vi ngay dưới |
> | 6 | ⭐ **Đổi API adapter - PHẦN 1 (định danh) CHỐT**: `adapter_id` ở Protocol · `server_id` giữ · **`target_id`** mới | [`docs/doi-api-adapter-2026-08-19.md`](docs/doi-api-adapter-2026-08-19.md) |
> | 7 | ⭐⭐ **Watchdog kiểu phần cứng** cho con; **systemd canh cha**; `N=3`/`T=60` chống domino | mục 2.8b, 2.8c tài liệu đa tiến trình |
> | 8 | **Bỏ vế "tắt bằng cờ"** của 2.7 · **năm ca nhánh supervisor** · **chấp nhận downtime** khi nâng cấp | mục 2.7, 5.5b, 5.5c |
> | 12 | ⭐⭐ **Đổi API adapter - PHẦN 4 (vòng đời) CHỐT -> MẢNG ADAPTER ĐÓNG TRỌN 5/5**: tách `start()` + `serve()` · F10 ba tình huống · trạng thái đi bằng **BUS** chứ không nhồi vào watchdog | [`docs/doi-api-adapter-2026-08-19.md`](docs/doi-api-adapter-2026-08-19.md) mục 4 |
> | 11 | ⭐ **Đổi API adapter - PHẦN 3 (hạng nhân bản) CHỐT**: tham số class `scaling=` + `unique_per_process=` · **`@subscribe` mất một VAI, giữ nguyên chữ ký** | [`docs/doi-api-adapter-2026-08-19.md`](docs/doi-api-adapter-2026-08-19.md) mục 3 và 2.6b |
> | 10 | **Job dọn `Store` chỉ chạy ở primary** · **luật "code mức module nhẹ"** vào `rules/module-level-code.md` · **"cha không có mồm" HOÃN** | `rules/module-level-code.md` |
> | 9 | ⭐ **Đổi API adapter - PHẦN 2 (cấu hình) CHỐT**: adapter **thôi biết về khoá** · cấm `ssl=` · **gỡ `ServerConfig` khỏi core** | [`docs/doi-api-adapter-2026-08-19.md`](docs/doi-api-adapter-2026-08-19.md) mục 2 |
>
> ### ⭐ Thứ áp cho CẢ HAI kho: cấu hình đi bằng THAM SỐ CLASS (PEP 487)
>
> ```python
> class HamNhipDangNhap(CounterStore, name="ham-nhip-dang-nhap", ttl=900, parts=4):
>     """Thân class chỉ còn docstring và hành vi."""
> ```
>
> Chủ dự án nêu chỗ vướng: *"dữ liệu cấu hình với dữ liệu nó mang đang nằm 1 chỗ... cần
> có cái phân biệt giữa data và cấu hình"*. Tham số class tách triệt để - cấu hình đi vào
> `__init_subclass__`, **không bao giờ** thành thuộc tính do app khai nên **không thể va
> tên**, và `mypy` kiểm được kwargs. Ba cách đã loại: thuộc tính trần · dunder `__store__`
> · inner class `Meta` (tách sạch không kém, **là lựa chọn tốt thứ hai**).
>
> ⚠ Áp cho cả `RefData` - hai lớp nền cùng framework không được có hai kiểu khai.
>
> ### ⭐⭐ 0.8 là bản ALPHA CUỐI CÙNG, và đó là ràng buộc chứ không phải ghi chú
>
> 0.9 đổi sang `4 - Beta` nơi *"API coi như đã chốt"*. Nên:
>
> | | |
> |---|---|
> | Mảng **"đổi API adapter một lượt"** phải làm ĐỦ ở 0.8 | Sót một chỗ là sót vĩnh viễn, hoặc phải phá tương thích ở Beta |
> | ⚠ **`0.8.1` chỉ được HIỆN THỰC, không đổi API** | Fieldbus/MQTT lùi 0.8.1, nhưng **tên và chữ ký phải khai xong ở 0.8** |
>
> ⭐ Hệ quả: phải chốt tên cho **nhóm adapter kết nối RA** (mqtt, modbus, opcua) ngay ở
> 0.8, dù việc chia tải của chúng làm ở 0.8.1.
>
> ### ⚠ Ba số đo của buổi, đừng đo lại
>
> | Đo | Kết quả |
> |---|---|
> | Đọc từ page cache vs `gather` vs thread pool | **0,22 µs · 6,03 µs (x27) · 96,7 µs (x439)**. Đọc LMDB không phải I/O nên **không song song hoá được, và không cần** |
> | `hash()` cùng một chuỗi ở 4 tiến trình | **4 giá trị KHÁC NHAU**; `crc32` thì như nhau. Dùng `hash()` chia file là hỏng hoàn toàn im lặng |
> | Runtime đọc tham số generic qua `__orig_bases__` | **Đọc được**, và công tắc abstract vào DI **vẫn nguyên** - quên khai `name` thì class không vào DI |
>
> ### ⭐ Hai chỗ "câu treo hoá ra đã có đáp án ở chỗ khác"
>
> Câu *"cha có đợi primary publish xong không"* đã được cơ chế **chờ qua bus** trả lời từ
> 08-18; câu *"mở kho ở đâu"* **tan** khi chốt mỗi bảng một thư mục file riêng.
>
> > **Khi một mảnh thiết kế mới ra đời, nên rà lại danh sách câu treo xem nó vừa đóng
> > cái nào.** Hai lần trong hai ngày, nên đây là thói quen đáng giữ chứ không phải may.
>
> ### ⭐ Phần 1 của mảng adapter: HAI tên, không phải một
>
> | Tầng | Tên |
> |---|---|
> | **Protocol `Adapter`** | **`adapter_id`** - thành viên Protocol, `use()` kiểm bằng `isinstance` và **nổ ngay** |
> | Hạng **điểm phục vụ** (web, grpc, socket) | **`server_id`** giữ nguyên |
> | Hạng **kết nối ra** (mqtt, modbus, opcua) | **`target_id`** mới, thay `client_id` · `device` · `server` |
>
> ⚠ Phát biểu gốc *"mọi adapter cùng một tên"* **bị lật một nửa**: ép một tên cho cả sáu
> là dán sai nhãn. Cái sai thật không phải *"sáu adapter bốn tên"* mà là **ba adapter
> cùng hạng dùng ba tên khác nhau**.
>
> ⭐ Bốn phát hiện khi đo code: **Protocol `Adapter` chỉ import dưới `TYPE_CHECKING`** nên
> `@runtime_checkable` **chưa từng có tác dụng** (thử thật: object rỗng `use()` được hai
> lần) · `client_id` mqtt **đã mang hai nghĩa** (khoá tra + giá trị dự phòng) · **hai
> `MqttAdapter` khác id hôm nay là HỎNG THẬT** vì `MqttConfig.resolve()` đọc một khối
> `mqtt` duy nhất · `client_id` mang **hai nghĩa ngược nhau** trong cùng framework (gRPC
> client SDK dùng cho *tên service đích*, mqtt dùng cho *tên của chính ta*).
>
> ### ⭐⭐ Watchdog: bài học phải chép theo là **vỗ ở đâu quyết định đo cái gì**
>
> Lỗi kinh điển của firmware là đặt lệnh vỗ trong **ngắt timer** - watchdog vẫn xanh khi
> vòng lặp chính đã treo. Bản dịch: vỗ ở **thread riêng** chỉ đo *"process còn tồn tại"*
> (`waitpid` đã trả lời rồi); vỗ ở **task trên event loop chính** mới đo *"loop chưa bị
> chặn"* - đúng cách hỏng mà cả `waitpid` lẫn health check đều mù.
>
> ⚠ **Chỗ đặt lệnh vỗ là HỢP ĐỒNG, không phải chi tiết hiện thực.** Chuyển sang thread
> riêng thì watchdog xanh mãi mãi và không gì báo. Phải có test canh.
>
> ⛔ **Watchdog là tín hiệu GIẾT, không phải tín hiệu THĂNG CẤP.** Giết → `waitpid` xác
> nhận exit → mới thăng cấp. Nhờ vậy ca "hai primary" đóng chặt: A đã chết thật, không
> phải bị coi là chết.
>
> ✅ **Ai canh cha: `systemd` `WatchdogSec` + `sd_notify`.** Nguyên tắc phần cứng:
> *watchdog không nằm trên con CPU nó canh*. Cha canh con vì cha sinh ra con; cha thì do
> thứ sinh ra cha canh. Nhất quán với *"đừng viết bộ cân bằng tải"*.
>
> ⭐ Cha treo là **hỏng chậm**: con vẫn phục vụ, chỉ mất khả năng **tự phục hồi** - không
> ai thấy gì cho tới lần đầu có con chết. Đó là lý do systemd là đủ.
>
> ### ⚠ Ba số đo nữa của buổi chiều
>
> | Đo | Kết quả |
> |---|---|
> | Vỗ một nhịp watchdog / cha đọc | **193 ns / 124 ns**. Nhịp 1 giây thì không đo nổi chi phí |
> | RSS theo tầng import (`python` trần → `+Application` → `+web+grpc` → `+sqlalchemy`) | **14 → 36 → 57 → 83 MB**. Cha chạy lại `main.py` nên nó gánh **cả cây import**: ~83 MB, không phải 14 MB như câu *"cha chỉ đọc YAML"* gợi ý |
> | 27 app thật dùng adapter gì | `WebAdapter` 25 · `GrpcAdapter` 9, **cả hai đều mở cổng**, **0 app có 0 adapter** |
>
> ### ⚠ Chỗ trống đã rà ra ở bản chốt 08-16, và kết cục
>
> | | Kết cục |
> |---|---|
> | **A.** Con treo thì ai phát hiện (2.8a tự mâu thuẫn) | ✅ **Watchdog** |
> | **B.** Nâng cấp code không downtime | ✅ **Chấp nhận downtime ngắn**, đường ra ghi sẵn (`exec` kế thừa fd kiểu nginx) |
> | **C.** Tắt êm | ⏭ **Hoãn**, và **bỏ luôn** trường *mức bận* trong nhịp vỗ vì nó chỉ sinh ra để phục vụ C |
> | **D.** `N`/`T` chống domino | ✅ `N=3`, `T=60`. ⚠ **Hai công tắc riêng**: *dựng lại con* vẫn làm, chỉ *cấp vai primary* mới dừng |
> | **E.** "Cờ tắt" ở 2.7 | ✅ **Bỏ**. Phân biệt bằng **ai gọi**, không bằng cờ trong object - *"không có gì để quên"* |
>
> ⚠ **Chỗ trống còn mở duy nhất: CHA KHÔNG CÓ MỒM** (mục 2.8c). *"Kêu to"* của chống
> domino và `/healthz` tổng cùng vấp một chỗ - cha không dựng DI, không phục vụ. Watchdog
> giải xong **vế dữ liệu**; vế **đường ra** chưa chốt hình dạng (file JSON ghi nguyên tử ·
> unix socket · HTTP riêng), và ⛔ phương án *"một con phơi ra hộ"* **đã loại** vì giám
> sát đi qua thứ nó giám sát.
>
> ### ⭐ Phần 2 của mảng adapter: adapter THÔI BIẾT về khoá
>
> Cách tóm tắt cũ (*"thống nhất sáu quy ước khoá"*) **sai trọng tâm**. Lời giải không
> phải thống nhất tên khoá mà là: framework đọc `processes.<p>.<loại>.<id>` rồi **đẩy ô
> đã lọc** vào adapter. Sáu quy ước khoá biến mất khỏi adapter; chỉ còn **một chỗ duy
> nhất** biết ánh xạ.
>
> | Chốt | |
> |---|---|
> | **Khoá YAML cũ GIỮ NGUYÊN** | App không `share_load()` vẫn đọc `server.port` như cũ - **31 app không sửa một dòng YAML** |
> | **Mỗi adapter một kiểu cấu hình riêng** | Framework *tìm đúng ô*, adapter *hiểu ô đó*. Một `AdapterConfig` chung là hợp đồng hứa nhiều hơn thứ nó giữ |
> | **Cấm `ssl=` trong code** | ⚠ Lý do **khác** `host`/`port`: cổng cấm vì *mô tả sự thật* (cha bind), `ssl` cấm vì **ngoại lệ hết lý do tồn tại** - server phụ nay có ô riêng |
> | **`client_id` + `topics`** | Vào **`processes.<p>.mqtt.<id>`** (ba tầng, như web/grpc), khối `mqtt:` làm mặc định và bị ghi đè. ⛔ Đề nghị đầu của phiên (`mqtt.clients.<id>`) **SAI**: một trục thì ba tiến trình nhận cùng `client_id` và đá nhau trên broker - lời giải đúng đã có ở mục 5.7.4 từ 08-16 |
> | **`processes:` và `share_load()` không khớp -> NỔ** | Hai nhánh loại trừ nhau, nhưng sửa nhầm chỗ thì không gì báo |
> | **GỠ `ServerConfig` khỏi core** | Core đang biết về *"HTTP adapter"* - cùng khuôn `PEER_APP_ID` đã gỡ 08-17 |
>
> ⭐⭐ **Hai phép đo làm đổi cách làm:**
>
> | Đo | Kết quả |
> |---|---|
> | Ai gọi `runtime.server` trong framework + 27 app | **Đúng MỘT file: `adapters/web/_adapter.py`** - chính adapter sở hữu nó. Gỡ `ServerConfig` **không phá ai** |
> | `opcua` đọc cấu hình nhiều server kiểu gì | **Đã hiện thực đúng khuôn "chung + ghi đè"** (`pick()` tra entry -> raw -> mặc định, tên lạ thì `StartupException` kèm danh sách). ⭐ Chép sang mqtt là xong, **đừng thiết kế lại** |
>
> ⚠ **Phải chốt cùng phần 2 dù thi công ở 0.8.1: `@subscribe` đổi vai.** `topics` vào
> `clients.<id>` thì `@subscribe("nhamay/+/nhiet-do")` **mất vai định tuyến**, thành
> *khai báo năng lực* - đó là đổi ý nghĩa một decorator công khai.
>
> ⚠ **Một phép dò bắt nhầm, ghi để người sau khỏi giật mình:** grep `get("server...")`
> ra cả modbus và opcua, trông như chúng đọc cấu hình của web. **Không phải** - đó là
> `modbus.server` / `opcua.server`, khoá con trong khối của chính chúng. Phép dò khớp
> theo **hình dạng chuỗi**, không theo **ngữ cảnh**.
>
> ### ⭐ Phần 3: hạng nhân bản khai bằng THAM SỐ CLASS, cùng khuôn `Store`
>
> ```python
> class WebAdapter(Adapter, scaling="replicated"): ...
> class MqttAdapter(Adapter, scaling="sharded",
>                    unique_per_process=("client_id",),   # phải KHÁC NHAU
>                    disjoint_per_process=("topics",)): ... # tập phải KHÔNG GIAO NHAU
> class ModbusAdapter(Adapter, scaling="sharded", disjoint_per_process=("devices",)): ...
> class SchedulerAdapter(Adapter, scaling="singleton"): ...
> ```
>
> ⚠ **BA hạng, không phải bốn** - tài liệu ghi *"bốn"* từ hồi mqtt còn xếp riêng, sửa
> 2026-08-19. ⭐ **Nhân bản cho *dư thừa*, phân mảnh thì KHÔNG**: web chết một con thì ba
> con còn phục vụ; modbus chết một con thì **cụm thiết bị của nó không ai đọc**.
>
> ⭐ Hạng là **ĐIỀU KIỆN** chứ không phải nhãn: *"mqtt nhân bản được NẾU mỗi bản có
> `client_id` riêng"* - nên phải có `unique_per_process`, và đó là thứ biến docstring
> thành phép kiểm số 4 chạy được. ⚠ Tên tham số **tiếng Anh** (bản nháp của phiên viết
> tiếng Việt): mọi API công khai của framework đang dùng tiếng Anh, framework làm ra cho
> người ngoài dùng.
>
> ⭐⭐ **HAI phép kiểm, hai tên - và MQTT cần cả hai cùng lúc**, đó là bằng chứng tách
> đúng: `client_id` phải **khác nhau**, `topics` phải **không giao nhau**. *"Khác nhau"*
> áp cho một **giá trị đơn**, *"không giao nhau"* áp cho một **tập** - ép chung một phép
> kiểm là hoặc bỏ sót một loại, hoặc viết một phép kiểm mơ hồ. Fieldbus chỉ cần vế thứ
> hai (tập **thực thể** nó phụ trách, không phải một trường của adapter).
>
> ✅ **`scaling` BẮT BUỘC khai, không mặc định.** Mặc định `replicated` là **nguy**
> (adapter chưa nghĩ tới nhân bản bị nhân bản, hỏng im lặng); mặc định `singleton` thì
> app chậm mà không ai biết vì sao. Đúng khuôn `Store` phải khai `name`.
> ⛔ `replicated`/`singleton` **khai hai tham số kia là LỖI** - tham số bị bỏ qua im lặng
> là chỗ để người ta tin vào thứ không xảy ra.
>
> ⭐ `scaling="singleton"` là chỗ `SchedulerRunner` sẽ về, và nó **làm vế "tắt bằng cờ"
> của 2.7 hết cần** - không ai gọi thì không chạy. ⏭ Câu *thăng cấp primary khởi động
> adapter singleton thế nào* **để phần 4 trả lời** (nó đụng docstring `start()`).
>
> ### ⭐⭐ `@subscribe` mất một VAI, KHÔNG đổi chữ ký
>
> Đọc code mới thấy: chuỗi topic đi qua **hai đường** - (a) đăng ký với broker, (b) định
> tuyến nội bộ qua `subscription_id`. **Chia tải chỉ cần đổi vai (a)**, nên đây là **tách
> một giá trị mang hai nghĩa** (luật 03 ở tầng decorator), không phải "chuyển topic sang
> cấu hình" như phiên nói lúc đầu.
>
> ✅ **Chốt P2**: subscribe theo cấu hình, dispatcher khớp topic **thật** với filter trong
> code. ⛔ Bỏ P1 (tính giao hai filter) vì nó đòi một thuật toán có ca biên khó (`#` ở
> giữa, `+` chồng `#`) mà **sai thì im lặng** - cái mất của P2 chỉ là một *tối ưu*, cái
> mất của P1 là *tính đúng đắn*.
>
> ⭐ Ba cảnh báo lúc khởi động; đáng giá nhất là **route không tiến trình nào nghe** - nó
> bắt được thứ mà nếu không có thì **một loại message rơi vào hư không**, hệ thống trông
> vẫn khoẻ. ✅ Không app nào phải sửa: không khai `topics` thì chạy y hệt hôm nay.
>
> ### ⭐⭐ Phần 4: tách `start()` + `serve()`, và ba thư viện dưới ĐÃ tách sẵn
>
> ```python
> async def start(self, app) -> None:   # chiếm tài nguyên, TRẢ VỀ khi xong
> async def serve(self) -> None:        # phục vụ, CHẶN
> async def stop(self) -> None:
> ```
>
> ⭐ Đo được: gRPC có `start()` **non-blocking** + `wait_for_termination()` · uvicorn có
> `startup()` + `main_loop()` · asyncio socket có `start_unix_server()` + `serve_forever()`.
> **gRPC adapter đã gọi đúng hai bước ở hai dòng liền nhau** - framework chỉ đang gộp
> chúng lại. Nên P1 **không ép hình dạng mới**, nó **thôi che giấu** cấu trúc vốn có.
> ⛔ Loại P2 (`asyncio.Event` adapter tự set): nghĩa vụ ngầm, quên thì framework đợi mãi -
> đúng khuôn `getattr(_server_id, None)` vừa sửa ở phần 1.
>
> ### F10: ba tình huống, ba xử lý - ranh giới nay CƯỠNG CHẾ ĐƯỢC
>
> | Lỗi từ | Xử lý |
> |---|---|
> | `start()` **lúc khởi động** | **SẬP** cả tiến trình |
> | `start()` **lúc thăng cấp** | ⭐ **TỪ CHỐI VAI primary, KHÔNG sập** - nếu sập thì đó chính là domino, mất ba tiến trình đang phục vụ vì một cái cert |
> | `serve()` | **CÔ LẬP** adapter đó, log `CRITICAL`, báo ra ngoài |
>
> Kiểm toán muốn ranh giới này từ 0.7 nhưng **không hiện thực được** vì `start()` gộp hai
> giai đoạn. P1 giải nó.
>
> ✅ **Framework LUÔN cô lập + LUÔN báo ra ngoài; ai phản ứng là việc tầng trên** (cha qua
> bus · LB qua `/readyz` · systemd qua `/healthz` · không ai thì app im). Cùng nguyên tắc
> *"đừng viết bộ cân bằng tải"* và *"systemd canh cha"*.
>
> ✅ **Adapter cuối cùng chết thì tiến trình VẪN SỐNG** (chủ dự án bác đề nghị *"thoát"*
> của phiên): còn sống thì `/healthz` còn trả lời, log còn đọc được, còn gỡ lỗi được.
>
> ### ⭐⭐ Trạng thái adapter đi bằng BUS, KHÔNG nhồi vào nhịp watchdog
>
> Phiên đề nghị nhồi *số adapter còn phục vụ* vào byte `trangThai` của nhịp vỗ. Chủ dự án
> bác: *"cha con giao tiếp được với nhau mà, việc gì cứ phải cho mỗi watchdog"*.
>
> | Cơ chế | Trả lời câu | Hình dạng |
> |---|---|---|
> | **Watchdog** | *"tôi còn quay không"* | nhịp đều đặn, **một câu duy nhất** |
> | **`ProcessLink`** | *"vừa có chuyện gì xảy ra"* | **sự kiện**, bao nhiêu thông tin cũng được |
>
> Nhồi trạng thái vào nhịp vỗ là bắt **một cơ chế trả lời hai câu** - đúng thứ luật 03
> cấm, và phiên suýt làm **ngay sau khi trích dẫn nó ba lần**. Hai lý do kỹ thuật cùng
> chiều: nhịp 1 giây thì tin **trễ tới 1 giây**; nhịp vỗ là **poll**, bus là **push**.
>
> ⭐ Hệ quả: **nhịp vỗ còn ĐÚNG một trường `mocVo`** sau hai lần cắt (*mức bận* rồi
> *trangThai*). Cả hai lần cùng một khuôn - *thấy có sẵn một kênh chạy đều đặn nên muốn
> gửi kèm thứ khác vào đó: rẻ về cơ chế, đắt về ngữ nghĩa*.
>
> ⚠ **Danh sách chờ *"cha không có mồm"* nay DÀI GẤP ĐÔI**: (1) kêu to khi dừng thăng cấp
> (2) `/healthz` tổng (3) **cảnh báo khi con từ chối vai primary** (4) **báo adapter bị cô
> lập**. ⭐ Nhưng chỉ chặng **cha -> bên ngoài** là hoãn; *con -> cha* đã thông qua bus, và
> *con -> log* đã thông qua stderr. Hôm nay cảnh báo **tới được journald, không tới được
> người**.
>
> ### ✅ MẢNG ADAPTER ĐÓNG TRỌN 5/5
>
> | Phần | |
> |---|---|
> | 1. Định danh · 2. Cấu hình · 3. Hạng nhân bản · 4. Vòng đời | ✅ chốt |
> | **5.** `SchedulerRunner` thành adapter đơn nhất | Thi công, không cần quyết - đã có `scaling="singleton"` |
>
> ### Còn lại của 0.8
>
> | | |
> |---|---|
> | ⚠ Câu **E** | `@poll`/`@on_change` chạy một lần **mỗi thực thể** - **đổi chữ ký thật**, khác `@subscribe`. Thi công 0.8.1, **chữ ký phải chốt ở 0.8** |
> | Hai phép dò của luật *code mức module nhẹ* | Ngưỡng bao nhiêu - chốt được lúc code |
> | ⏭ Đã hoãn có ý thức | *cha không có mồm* · *supervisor trông tiến trình ngoài* · *tắt êm* |
>
> Cộng **hình dạng đường ra cho cha** (mục 2.8c - chủ dự án chốt **HOÃN** 2026-08-19).

> ## Buổi 2026-08-18 chốt gì
>
> Ba mảng, hai tài liệu mới, và **một câu treo từ 08-16 đã đóng**.
>
> | # | Chốt | Ghi ở |
> |---|---|---|
> | 1 | **Bus liên tiến trình = `ProcessLink`** - bộ nhớ chung, mỗi tiến trình một **vùng ghi riêng**, semaphore làm chuông và bitmap làm sự thật, **cha KHÔNG nằm trên đường đi** | [`docs/bus-lien-tien-trinh-2026-08-18.md`](docs/bus-lien-tien-trinh-2026-08-18.md) |
> | 2 | **Kho nhóm 1 = `RefData[T]`** - hai bản đổi con trỏ, `read()` trả **object** (số đời làm chìa khoá cache L1), **chỉ primary `publish()`**, `None` = *chưa sẵn sàng*, **chia đoạn khi lớn** | [`docs/kho-nhom-1-snapshot-2026-08-18.md`](docs/kho-nhom-1-snapshot-2026-08-18.md) |
> | 3 | ✅ **`post_construct` ở tiến trình phụ: ĐÓNG** bằng Protocol **`RunOnce`** | mục 2.9 của tài liệu đa tiến trình |
>
> ### ⭐ Mục 3 là thứ đáng nhớ nhất của buổi
>
> Bài toán hoá ra là **hai trục, bốn ô** - và ba ô **đã có nhà** từ trước:
>
> | | **Mọi tiến trình** | **Một lần cho cả cụm** |
> |---|---|---|
> | **Chạy một lần rồi thôi** | `post_construct()` | ⛔ **thiếu** -> nay là **`run_once()`** |
> | **Chạy mãi** | `Adapter.start()` | **adapter hạng đơn nhất** |
>
> Chủ dự án gọi tên đúng chỗ vướng: *"hai cái chạy lần đầu khác nhau đang bị nhét vào
> một cái"*. Tách ra, đặt tên khác, là xong.
>
> ⛔ **Không decorator, không khai `config/`** - `RunOnce` là **Protocol với tên method
> quy ước**, đúng khuôn `post_construct`/`pre_destroy` vốn có (kiểm ở
> `xime/core/lifecycle/hooks.py`). Ba hook nay cùng họ.
>
> ⭐ **Đối chiếu Spring Boot**: nó có ô (1) và (3), **KHÔNG có ô (2) và (4)** trong core -
> phải mượn **ShedLock / Quartz clustering / ZooKeeper leader election**. Lý do: các
> instance Spring **độc lập, không có quan hệ cha-con**. Xime thì *ai là primary* là
> **sự thật của kernel** (`waitpid`), nên làm được hai ô đó **không cần khoá phân tán,
> không leader election, không thêm thành phần vận hành nào**.
>
> ### ⚠ Luật 2.7 đã được PHÁT BIỂU LẠI
>
> Chủ dự án nêu *"luật 2.7 đang có vấn đề đấy"*, và vấn đề là nó **cấm mà không chỉ
> đường**: câu *"mở phải lười"* không dùng được cho khoá JWT, vì `JwtKeyProvider.keys()`
> chốt ở 0.7.2 nói **không bao giờ gọi mạng**. Nay mỗi loại việc có một nhà (bảng ở mục
> 2.7).
>
> ### ⚠ Ba số đo của buổi, đừng đo lại
>
> | Đo | Kết quả |
> |---|---|
> | `shared_memory` + `Semaphore` vs `socketpair` | **17,4 µs vs 16,8 µs - gần như BẰNG NHAU.** Thời gian bị chi phối bởi **đánh thức**, không phải copy |
> | "kiểm tra chỗ trống rồi mới đặt" với 4 tiến trình | **4/2000 slot bị cấp hai lần** - đua có thật, đo được |
> | `create_async_engine` | nằm trong `__init__`, **không mở kết nối**. Pool DB lười thật |
>
> ### ⛔ Việc thi công phát sinh
>
> **`SchedulerRunner` KHÔNG phải Adapter** (đo 2026-08-18) - nó khởi động vòng lặp
> trong `post_construct`, tức việc ô (4) đang ở nhà ô (1), và chạy ở **mọi tiến trình**.
> Chuyển nó thành **adapter hạng đơn nhất** thuộc nhóm *"đổi API adapter một lượt"*.
>
> ### ✅ "Hôm sau bàn tiếp" ĐÃ BÀN XONG 2026-08-19
>
> Cả ba việc đặt ra cuối buổi 08-18 đều đóng, và **hai trong ba đóng theo cách không ai
> đoán trước**:
>
> | Việc đặt ra 08-18 | Kết cục |
> |---|---|
> | Kho nhóm 2 - *"8 câu treo, hai câu là API công khai"* | ✅ Chốt hết. ⚠ Nhưng **hai câu API công khai đó TAN chứ không được trả lời**: bỏ Protocol thì câu *"mở rộng `CacheService` hay tách `AtomicStore`"* mất chỗ đứng, và *"ba kết cục"* hoá ra kết cục thứ ba **vốn đã có**, chỉ chưa được khai |
> | `TrustKeyL2Cache` - *"chỗ duy nhất phạm vi một máy không phủ được"* | ✅ Đóng, và **câu hỏi đặt sai**: khoá Trust **có nguồn bền vững** nên nó thuộc **nhóm 1**, `RefData` giải, không phải LMDB |
> | 8 câu treo của nhóm 1 | ✅ Chốt hết 8/8. Câu 1 (*cha có đợi primary publish*) **đã có đáp án từ chính buổi 08-18** - cơ chế chờ qua bus |


⚠⚠ **Thiết kế đổi hẳn 2026-08-16.** `docs/ke-hoach-0.8.md` (bản 2026-06-27) **phần lớn
không còn dùng** - đừng đọc nó như hiện trạng, **nên viết lại chứ không bổ sung**. Hai tài
liệu thay thế: `docs/da-tien-trinh-main-va-cau-hinh-2026-08-16.md` (mô hình chạy, `main.py`,
cấu hình, adapter) và `docs/cache-lien-tien-trinh-2026-08-16.md` (kho liên tiến trình).

| Nhóm | Gồm |
| --- | --- |
| **Mô hình chạy** | Supervisor giữ socket · `share_load()` · con chạy lại `main.py` với `XIME_PROCESS_ID` qua `multiprocessing` · thăng cấp primary · kênh cha-con |
| **Cấu hình** | Khối `processes` · `add_config(module)` · `count: N` · `shared: true` |
| **Đổi API adapter một lượt** | Tên định danh · tách `client_id` khỏi `server_id` · cổng từ cấu hình · hạng nhân bản là dữ liệu · **vòng đời + ready (F10)** |
| ~~**Fieldbus**~~ | ⏭ **LÙI SANG 0.8.1** (chủ dự án chốt 2026-08-19). Tách **loại** khỏi **thực thể** · `@poll` per-instance · log khi bỏ qua adapter |
| ~~**MQTT**~~ | ⏭ **LÙI SANG 0.8.1** (cùng ngày). Ba việc ở 5.7.4 - chỉ có nghĩa khi có nhiều tiến trình, và **chưa app nào dùng MQTT/Modbus/OPC UA thật** nên không chặn ai |
| **Kho liên tiến trình** | ✅ **CẢ HAI NHÓM CHỐT HẾT.** Nhóm 1 `RefData` (8/8 câu): `docs/kho-nhom-1-snapshot-2026-08-18.md`. Nhóm 2 `Store` trên LMDB: `docs/kho-nhom-2-store-2026-08-19.md`. ⛔ Phạm vi **một máy, luôn luôn** |
| **Bus** (`ProcessLink`) | ✅ **THIẾT KẾ XONG 2026-08-18** - `docs/bus-lien-tien-trinh-2026-08-18.md`. Bộ nhớ chung, mỗi tiến trình một **vùng ghi riêng**; **cha KHÔNG nằm trên đường đi** |
| ~~⛔ **Chặn phần thăng cấp**~~ | ✅ **HẾT CHẶN** - `post_construct` ở tiến trình phụ đóng 2026-08-18 bằng Protocol `RunOnce` |
| ~~**Luật "code mức module nhẹ"**~~ | ✅ **VIẾT XONG 2026-08-19**: `rules/module-level-code.md`. Còn lại là **hiện thực hai phép dò** |
| **Thi công** | ⬜ `SchedulerRunner` thành adapter hạng đơn nhất · ✅ job dọn `Store` **chỉ ở primary** (chốt 2026-08-19) |

✅ **Đường cắt ĐÃ THI HÀNH 2026-08-19: fieldbus và MQTT lùi sang 0.8.1.** Ba nhóm đầu
cộng bus và hai kho là hạ tầng nền, đủ cho app web/gRPC chạy nhiều tiến trình. Fieldbus
và MQTT phục vụ hướng IoT-nhà máy, mà **hôm nay chưa app nào dùng Modbus/OPC UA/MQTT
thật** nên chúng không chặn ai.

⚠ Bus thì **ở lại 0.8** dù ca dùng gốc của nó là fieldbus: nó đã thành **kênh điều khiển
của chính framework** (kênh nội bộ `__xime__`, thăng cấp primary, F10), nên nó là hạ
tầng nền chứ không còn là thứ phục vụ riêng fieldbus.

Khi làm 0.8 nhớ nhắc chủ dự án **kiểm lại kỹ logic JWT starter**.

Việc mở ngày 2026-08-01 vẫn còn: dựng trang **xime-framework.org** ở
`D:\code\xime framework\website` (Next.js xuất tĩnh, ưu tiên SEO).

> ### ⚠ A1 (fail-open JWT): gốc rễ nằm ở REPO NÀY, không phải ở 21 app
>
> Đo 2026-08-04 (chi tiết + giới hạn phép đo:
> [`docs/ke-hoach-va-bao-mat-2026-08-01.md`](docs/ke-hoach-va-bao-mat-2026-08-01.md) mục 1.1):
> **19/21 codebase còn fail-open**, 2 đã vá (`san-the-thao`, `cho-thue-thiet-bi` - chép được),
> và **`saas-foundation/template` nằm trong nhóm chưa vá** nên mọi app clone từ nay đều thừa
> hưởng lỗ hổng.
>
> Vì sao cả 21 repo **tự viết** `TrustJwtAuthMiddleware` thay vì dùng `configure_jwt` của ta:
> `JwtMiddlewareConfig.key_context` là **đúng một khoá tĩnh**; `grep kid` trong `starters/jwt/`
> chỉ ra **một** chỗ - `_signer.py` lúc KÝ. **Phía verify không có dòng nào xử lý `kid`.**
>
> **A1 không phải 21 lỗi độc lập - nó là MỘT khoảng trống của framework, nhân lên 21 lần.**
>
> ✅ **Khoảng trống đó ĐÃ LẤP 2026-08-18** - `JwtKeyProvider` + verify theo `kid` + ba kết cục
> lúc khởi động. Chi tiết: [`docs/jwt-keyset-va-trung-tinh-2026-08-18.md`](docs/jwt-keyset-va-trung-tinh-2026-08-18.md).
>
> ⚠⚠ **Nhưng 19 app VẪN fail-open, và câu này phải đọc kỹ:** lỗ hổng nằm trong `config/jwt.py`
> **của họ** (không lấy được khoá -> không gọi `configure_middleware`), mà framework không với tới
> đó. Bản vá **không sửa app nào cả** - nó **xoá lý do tồn tại** của lỗ: trước đây họ phải chọn
> giữa *"có sẵn chuỗi PEM lúc khởi động"* và *"không có middleware nào"*; nay có ô thứ ba.
>
> ⭐ **Đừng đọc dòng "A1 xong" ở bảng việc thành "A1 đã an toàn".** Cách duy nhất để nó thật sự
> đóng là từng app chuyển sang `configure_jwt(config, key_provider=...)`, và **`saas-foundation/template`
> phải đi trước** vì nó là nguồn sinh sôi của 20 app kia - 18 file còn lại là nợ đứng yên, template
> là nợ **đang sinh thêm**.
>
> ⚠ Chỗ họ phải quyết khi chuyển: `JwtKeySet.resolve(kid)` hiện làm *"theo kid nếu có, ngược lại
> **thử tất cả**"*. Framework nay không suy diễn khi `kid` vắng - nó gọi `keys(None)` và tin câu
> trả lời. *"Thử tất cả"* nên được xem lại: nó biến `kid` từ phép định tuyến thành thứ trang trí.

---

> ### ✅ XONG: kiểm toán trước khi đẩy 0.7.0 lên PyPI
>
> **Hoàn tất 2026-07-30. Mọi phát hiện đã vá, không còn mục nào mở.**
> Báo cáo đầy đủ: `docs/kiem-toan-0.7.md` (16 phát hiện: 3 Cao, 8 Trung, 5 Thấp).
>
> Bằng chứng: **1463 passed, 5 skipped**; **1463 passed** khi chạy lại với đúng bộ
> floor deps; `twine check` PASSED; sdist 230 file/354 KB không rò rỉ; cài **từ
> sdist** vào venv trắng chạy được; `ruff check xime/` còn 1 cảnh báo style;
> `mypy --strict` phía người dùng sạch; **343/343 dòng import trong tài liệu chạy được**.
>
> **Ba lỗi mức Cao đáng nhớ** - cả ba đều nằm ở chỗ nối, không phải thuật toán, và
> **1427 test cũ không thể bắt được** vì test luôn đi đường tắt mà người dùng thật
> không có:
>
> 1. **Mọi web app không cài extra `[jwt]` sập lúc khởi động** - có từ **0.2.0**,
>    nằm trong cả 10 bản đã lên PyPI. `WebAdapter` đọc registry JWT ở mọi lần khởi
>    động, mà import submodule đó kéo theo `__init__` của package vốn `import jwt`
>    ở mức module. Vá: nạp PyJWT lười (`starters/jwt/_pyjwt.py`).
> 2. **`dependency.register(ModbusClient)` / `(OpcuaClient)` chết lúc khởi động** -
>    đúng dòng lệnh tài liệu hướng dẫn. `device: str = "default"` có type hint, mà
>    type hint là tín hiệu opt-in DI nên container đi tìm binding cho `str`. Vá: bỏ
>    annotation (đúng cơ chế opt-out của framework) - **đừng thêm `: str` lại**.
> 3. **Server OPC UA không công bố được node không phải `float`** - biến OPC UA lấy
>    kiểu từ giá trị lúc tạo; node không khai `default=` bị tạo Double nên đẩy
>    `bool`/`str` bị `BadTypeMismatch`, mà lỗi đó bị nuốt nên node đứng im ở `0.0`
>    mãi mãi. Vá: suy kiểu từ annotation trong model.
>
> **Bài học ghi lại cho lần sau:** với mỗi tính năng, viết ít nhất một test đi
> **đúng con đường tài liệu hướng dẫn**, không phải con đường tiện nhất cho test.
>
> **Ba script kiểm chứng đã lưu lại ở `.claude/scripts/`** (có README riêng) - mỗi
> cái đều đã bắt lỗi thật, chạy lại trước mỗi lần phát hành:
> `check_doc_imports.py` (mọi import trong tài liệu có chạy?),
> `check_doc_register.py` (mọi class tài liệu bảo `register()` có dựng được?),
> `find_reexport_gap.py` (`__init__.py` nào phá `mypy --strict` của người dùng?).
>
> **Hai quyết định của chủ dự án ngày 2026-07-30, ĐÃ LÀM:**
>
> - **Tham số constructor có default = tham số KHÔNG bắt buộc.** Container bỏ
>   tham số đó ra khỏi kế hoạch dựng khi không ai cấp được kiểu của nó, để Python
>   dùng default (tương đương `@Autowired(required=false)`). Đây là **gốc rễ** của
>   lỗi số 2 ở trên, nên annotation `device: str` đã được **trả lại**.
>   `XimeContainer._drop_unsatisfiable_optional_deps()`, 9 test canh trong
>   `tests_temp/DI/test_08_optional_dependencies.py`. Fail-fast vẫn nguyên với
>   tham số KHÔNG có default.
> - **Thứ tự dựng singleton nay xác định.** `DependencyGraph` giữ thứ tự khai báo
>   thay vì duyệt `set` của type (thứ tự `set` phụ thuộc `id()` nên đổi theo từng
>   process). Trước đây thứ tự `post_construct` giữa các singleton độc lập đổi
>   theo từng lần chạy - order nào cũng hợp lệ, nhưng bug phụ thuộc order sẽ chỉ
>   tái hiện thỉnh thoảng.
>
> **Còn ghi nhận, KHÔNG vá** (mục cuối báo cáo): test bảo mật OPC UA chưa từng bắt
> tay Sign/SignAndEncrypt thật. `LifecycleManager` không gọi `pre_destroy()` cho
> instance mà `post_construct()` ném lỗi - **chủ dự án chốt 2026-07-30: GIỮ
> NGUYÊN** (dọn object khởi tạo dở sẽ che lỗi gốc); bù bằng hợp đồng "mở được đến
> đâu, tự dọn đến đó" ghi trong docstring `PostConstruct` + core-concepts.md
> (mẫu try/except và `AsyncExitStack.pop_all()`). Đừng đề xuất đổi lại.
>
> **Lưu ý cũ đã SAI, đừng tin lại:** "chưa push PyPI". Thực tế đã có **10 bản**
> (0.1.0 - 0.6.3) trên PyPI từ trước.
>
> Két sắt token + hướng dẫn phát hành 8 bước: `pypi_token.py` ở gốc repo PHÁT
> TRIỂN (trong `.gitignore`), xem bằng `python pypi_token.py --guide`. Hướng dẫn
> đã cập nhật đường dẫn `upload/` ngày 2026-08-01.

Sau đợt kiểm toán trên, **0.7.0 đã commit và đã lên PyPI** (xác nhận 2026-08-01).
Bản kế tiếp **0.7.1** đã code xong 2026-08-03, xem bảng "việc đang chờ" ở trên.
Trước đó, hai mắt xích đặt ngày 2026-07-27 đã làm xong ở **0.6.3**:

> - **`PEER_APP_ID`** (`docs/peer-app-id-tu-san-cert.md`) - mắt xích tiếp theo của đợt
>   "hồn - xác" nằm ở **data-service**, không phải repo này.
> - **TLS cho web adapter** (`docs/tls-cho-web-adapter.md`) - mức 1 xong, app bật HTTPS
>   chỉ bằng khối `server.ssl` trong `application.yml`, không sửa code. **Mức 2 đã bỏ
>   hẳn**, đừng đề xuất lại: nó không tránh được việc private key chạm đĩa nên không giải
>   quyết được vấn đề nó sinh ra để giải quyết. Khi việc restart lúc certbot gia hạn
>   thành phiền thì làm **mức 1.5** (mục 4.0 của tài liệu đó): nạp đè `load_cert_chain()`
>   lên `SSLContext` đang phục vụ - đã kiểm chứng bằng handshake TLS thật, kết nối mới
>   nhận cert mới ngay.
>
> Việc lớn tiếp theo theo lộ trình là **0.8 đa tiến trình + đổi API adapter một
> lượt**. ⚠ **Thiết kế đổi hẳn 2026-08-16** - `docs/ke-hoach-0.8.md` (bản
> 2026-06-27) phần lớn không còn dùng; đọc `docs/da-tien-trinh-main-va-cau-hinh-2026-08-16.md`
> và `docs/cache-lien-tien-trinh-2026-08-16.md`. Bảng việc đầy đủ ở mục "Việc đang
> chờ làm ở repo này" phía trên. Khi code 0.8 nhớ nhắc chủ dự án kiểm tra lại kỹ
> logic JWT starter.
