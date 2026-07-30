# XIME Framework — Hướng dẫn phiên làm việc

Python backend framework, bản đang làm là **0.7.0** - **chưa commit, chưa lên
PyPI** (tag git cuối cùng vẫn là `v0.6.3`; đừng đánh số thành 0.7.1, không có
bản 0.7.0 nào đã phát hành để mà vá). **Các bản 0.1.0 - 0.6.3 ĐÃ có trên PyPI** -
kiểm chứng 2026-07-29 qua PyPI JSON API, đừng tin lại dòng "chưa push PyPI" ở tài
liệu cũ. Hệ quả: API đã có người tải về dùng, đổi API phải theo semver.

Toàn bộ core, các adapter (web, gRPC code-first + client SDK, socket, **MQTT**,
**Modbus TCP**, **OPC UA**) và starters (gồm **storage/localfs/s3**,
**mail SMTP**) đã có code và test (**1463 passed, 5 skipped** trong `tests_temp/`;
5 skip gồm 2 test tích hợp MQTT/S3 cần broker/MinIO và 1 test phân quyền file chỉ
chạy trên POSIX). Không còn ở giai đoạn thiết kế - khi sửa, đọc code thật trong
`xime/` và chạy `pytest` trước khi kết luận.

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

## Tài liệu thiết kế chi tiết (đọc khi cần)

- **Lộ trình phiên bản (0.3 -> 0.9, tra "việc X làm bản nào"):** `docs/lo-trinh-phien-ban.md`
- **Kế hoạch 0.8 (thiết kế ban đầu chốt 2026-06-27: Multi-process Runtime + Bus + config):** `docs/ke-hoach-0.8.md`
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
- **`PEER_APP_ID` - định danh app từ SAN cert (ĐÃ LÀM 0.6.3):** `docs/peer-app-id-tu-san-cert.md`
- **TLS/HTTPS cho web adapter (ĐÃ LÀM 0.6.3, mức 2 đã bỏ):** `docs/tls-cho-web-adapter.md`
- **Backlog lỗi cần sửa (event bus tests, pb2 collision):** `docs/backlog-sua-loi.md`
- **Wishlist tính năng tương lai (bidi, transport TCP, retry...):** `docs/wishlist-tinh-nang.md`

## Việc đang chờ làm ở repo này

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
> Két sắt token + hướng dẫn phát hành 8 bước: `pypi_token.py` ở gốc repo (trong
> `.gitignore`), xem bằng `python pypi_token.py --guide`.

Sau đợt kiểm toán trên, **không còn việc nào đang chờ** - 0.7.0 sẵn sàng commit
và đẩy PyPI. Trước đó, hai mắt xích đặt ngày 2026-07-27 đã làm xong ở **0.6.3**:

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
> Việc lớn tiếp theo theo lộ trình là **0.8 Multi-process Runtime + Bus liên
> Worker** (`docs/ke-hoach-0.8.md`, thiết kế ban đầu chốt 2026-06-27, chưa code).
> Khi code 0.8 nhớ nhắc chủ dự án kiểm tra lại kỹ logic JWT starter.
