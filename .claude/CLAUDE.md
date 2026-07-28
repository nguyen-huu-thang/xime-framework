# XIME Framework — Hướng dẫn phiên làm việc

Python backend framework đã phát hành **0.6.3** (đã **kiểm toán toàn diện
2026-07-01**, chưa push PyPI): toàn bộ core, các adapter (web, gRPC code-first +
client SDK, socket, **MQTT**) và starters (gồm **storage/localfs/s3**,
**mail SMTP**) đã có code và test (**1223 passed, 5 skipped** trong `tests_temp/`;
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
- **`PEER_APP_ID` - định danh app từ SAN cert (ĐÃ LÀM 0.6.3):** `docs/peer-app-id-tu-san-cert.md`
- **TLS/HTTPS cho web adapter (ĐÃ LÀM 0.6.3, mức 2 đã bỏ):** `docs/tls-cho-web-adapter.md`
- **Backlog lỗi cần sửa (event bus tests, pb2 collision):** `docs/backlog-sua-loi.md`
- **Wishlist tính năng tương lai (bidi, transport TCP, retry...):** `docs/wishlist-tinh-nang.md`

## Việc đang chờ làm ở repo này

> **Hiện KHÔNG còn việc nào đang chờ ở repo framework.** Hai mắt xích đặt ngày 2026-07-27
> đều đã làm xong ở **0.6.3**:
>
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
> Việc lớn tiếp theo theo lộ trình là **0.7 Fieldbus** (`docs/ke-hoach-0.7.md`).
