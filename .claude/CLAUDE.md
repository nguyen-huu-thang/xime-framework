# XIME Framework — Hướng dẫn phiên làm việc

Python backend framework. Bản mới nhất **trên PyPI** vẫn là **0.7.0**; trong repo
đã là **0.7.1 - CODE XONG 2026-08-03, CHƯA COMMIT, CHƯA ĐẨY PyPI** (chủ dự án tự
đẩy, đừng đẩy hộ). Vì `xime` cài **editable** nên code 0.7.1 đã có hiệu lực ngay
với cả 31 app trên máy này, dù PyPI chưa có.

> ## 0.7.1 có gì (chi tiết: [`docs/ket-qua-0.7.1-2026-08-03.md`](docs/ket-qua-0.7.1-2026-08-03.md))
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

### ⚠ `xime.__version__` trả `0.6.3` là ĐÚNG theo cơ chế, không phải ai quên bump

Đo 2026-08-04: `xime.__version__` = `0.6.3` · `importlib.metadata` = `0.6.3` ·
`pyproject.toml` = `0.7.1` · dist-info = `xime-0.6.3.dist-info` · `from xime.core.contract import
stream` **chạy được** (tức mã đang là 0.7.1).

`xime/__init__.py` lấy version từ `importlib.metadata.version("xime")`, chỉ fallback sang hằng số
trong mã khi metadata vắng. Mà cài editable thì **mã nạp thẳng từ repo (luôn mới), còn metadata
đóng băng tại lần `pip install -e` cuối** - ở đây là hồi 0.6.3.

Nên `0.6.3` trả lời câu *"lần cuối ai cài lại gói"*, không phải *"mã đang chạy là bản nào"* - một
giá trị mang hai nghĩa, đúng [luật 03](../../.claude/rules/03-mot-gia-tri-mot-nghia.md).

**Cách kiểm đúng: hỏi code, đừng hỏi số.** Hai việc còn treo, thẩm quyền khác nhau: chạy lại
`pip install -e .` (đụng môi trường dùng chung -> chờ leader/chủ dự án gật) · đổi thứ tự ưu tiên
của `__version__` (đổi giá trị công khai 30 codebase có thể đọc -> **hỏi chủ dự án**).

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
- **Vòng lặp nền & tắt máy (mới 2026-08-04):** `rules/background-tasks.md` - `create_task` chưa
  chạy dòng nào; đừng viết đường tắt giả định task đã khởi động. Kèm bảng phân biệt hình dạng an
  toàn / nguy, và lý do **mock không bắt được loại lỗi này**

## Tài liệu thiết kế chi tiết (đọc khi cần)

- **Lộ trình phiên bản (0.3 -> 0.9, tra "việc X làm bản nào"):** `docs/lo-trinh-phien-ban.md`
- **Kế hoạch 0.8 (thiết kế ban đầu chốt 2026-06-27: Multi-process Runtime + Bus + config):** `docs/ke-hoach-0.8.md`
- **⭐ Cache liên tiến trình - chốt LMDB + việc còn treo (2026-08-16, ĐANG BÀN):** `docs/cache-lien-tien-trinh-2026-08-16.md`
  - Chốt: **tách bus khỏi kho** · cache chia **HAI nhóm theo việc có nguồn bền vững hay không**
    (nhóm 1 tự viết shared memory hai-bản-đổi-con-trỏ, nhóm 2 **LMDB**, mỗi bảng một file) ·
    **đa tiến trình TRƯỚC, đa luồng để sau**
  - ⚠ Lý do hoãn đa luồng là **số đo, không phải sở thích**: `grpcio` chưa có wheel free-threaded
    và gRPC là xương sống của Xime, nên bật bản không GIL là **GIL tự bật lại** -> N luồng chậm
    hơn một luồng. `lmdb` cũng chưa có. Tín hiệu duy nhất đáng theo dõi để xét lại
  - Còn treo: **9 quyết định**, trong đó 2 là **API công khai** (mở rộng `CacheService` hay tách
    `AtomicStore` · ba kết cục thay vì hai). Và **4 chỗ bổ sung/lật một phần `ke-hoach-0.8.md`**
    (kiểu queue, DI scope hai tầng -> bốn tầng, primitive asyncio không qua được ranh giới loop,
    kết nối DB nhân theo M×N)
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
  - ⭐ **Bốn hạng adapter, không phải hai**: nhân bản (web, grpc) · **phân mảnh** (modbus, opcua -
    mỗi tiến trình một cụm thiết bị; nhân bản cho *dư thừa*, phân mảnh thì **không**) · đơn nhất ·
    mqtt
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
  - ⛔ **Câu khó nhất còn lại: `post_construct` ở tiến trình phụ** (mục 2.9). Không cắt được ở
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
| 1 | **Commit + đẩy PyPI 0.7.1** | Code xong, CHANGELOG xong, version đã bump. Chủ dự án tự đẩy. Repo phát hành `upload/` **chưa đồng bộ**; cả hai repo **chưa có git tag nào**, kể cả v0.7.0 |
| 2 | ✅ ~~A1 - keyset JWT nhiều khoá theo `kid`~~ | **XONG 2026-08-18 phía framework** - xem mục 4b ở trên và [`docs/jwt-keyset-va-trung-tinh-2026-08-18.md`](docs/jwt-keyset-va-trung-tinh-2026-08-18.md). ⚠ **Phần ở 19 app thì CHƯA**: framework không với tới `config/jwt.py` của họ. Nó chỉ **xoá lý do tồn tại** của lỗ - nay có ô thứ ba thay vì phải chọn giữa *"có sẵn PEM lúc khởi động"* và *"không middleware nào"*. Việc còn lại: vá **`saas-foundation/template` trước** (nguồn sinh sôi của 20 app kia), rồi lần lượt |
| 3 | **F3 - nâng sàn dependency** (đợt 4) | `pyjwt>=2.13` · `python-multipart>=0.0.31` · `fastapi>=0.115.3`. ⚠ Phải **cài thử và chạy hết bộ test**, đừng chỉ sửa số - nếu không là thay một lời khai đã kiểm chứng bằng một lời khai đoán mò |
| 4 | **F14 · F15 · F17** (đợt 5) | Đều không phá tương thích: `validate_object_key` từ chối `\` và NUL · trần task `EventBus` · allowlist `ResponseTopic` của MQTT RPC. ⛔ **F9 ĐÃ BỊ XOÁ, không phải được vá**: nó là *"`_read_peer_app_id` neo đầu chuỗi thay vì `find()`"*, mà bản gỡ phụ thuộc khái niệm 2026-08-17 đã bỏ hẳn việc lọc scheme nên **không còn chuỗi nào để neo** |
| 5 | **F1 - đường xác thực WebSocket** (đợt 5) | Làm được ở 0.7.x nếu opt-in. **Phải xong TRƯỚC app `xime chat`**, mà app đó chưa bắt đầu |
| 6 | Đợt 0 + phần còn lại đợt 1 (A2, A4) | **Nằm ở repo app, không phải framework.** Đợt 0 vẫn chờ chủ dự án quyết A6 (chỗ để secret) |

⚠ **F10 (cô lập adapter, đợt 3) ĐÃ CHUYỂN SANG 0.8** - nó mở rộng `Adapter` protocol, tức
đổi API cho mọi adapter kể cả adapter người dùng tự viết, mà 0.8 đã có sẵn một đợt đổi API
adapter một lượt và supervisor cần đúng tín hiệu "ready" đó.

### 0.8 - đa tiến trình + đổi API adapter một lượt

⚠⚠ **Thiết kế đổi hẳn 2026-08-16.** `docs/ke-hoach-0.8.md` (bản 2026-06-27) **phần lớn
không còn dùng** - đừng đọc nó như hiện trạng, **nên viết lại chứ không bổ sung**. Hai tài
liệu thay thế: `docs/da-tien-trinh-main-va-cau-hinh-2026-08-16.md` (mô hình chạy, `main.py`,
cấu hình, adapter) và `docs/cache-lien-tien-trinh-2026-08-16.md` (kho liên tiến trình).

| Nhóm | Gồm |
| --- | --- |
| **Mô hình chạy** | Supervisor giữ socket · `share_load()` · con chạy lại `main.py` với `XIME_PROCESS_ID` qua `multiprocessing` · thăng cấp primary · kênh cha-con |
| **Cấu hình** | Khối `processes` · `add_config(module)` · `count: N` · `shared: true` |
| **Đổi API adapter một lượt** | Tên định danh · tách `client_id` khỏi `server_id` · cổng từ cấu hình · hạng nhân bản là dữ liệu · **vòng đời + ready (F10)** |
| **Fieldbus** | Tách **loại** khỏi **thực thể** · `@poll` per-instance · log khi bỏ qua adapter |
| **MQTT** | Ba việc ở 5.7.4 - **chỉ có nghĩa khi có nhiều tiến trình**, nên không cần làm sớm |
| **Kho liên tiến trình** | LMDB (nhóm 2) + shared memory hai-bản-đổi-con-trỏ (nhóm 1) |
| **Bus** | **Viết lại** theo vai mới: chở tín hiệu, có phản hồi, qua kênh cha-con |
| ⛔ **Chặn phần thăng cấp** | **`post_construct` ở tiến trình phụ** - chưa có lời giải |

**Đường cắt nếu 0.8 quá dài:** ba nhóm đầu là hạ tầng nền, đủ cho app web/gRPC chạy nhiều
tiến trình. Fieldbus/MQTT/bus phục vụ hướng IoT-nhà máy, mà **hôm nay chưa app nào dùng
Modbus/OPC UA/MQTT thật** nên chúng không chặn ai.

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
