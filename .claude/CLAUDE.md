# XIME Framework — Hướng dẫn phiên làm việc

Python backend framework đã phát hành **0.6.1**: toàn bộ core, các adapter (web,
gRPC code-first + client SDK, socket, **MQTT**) và starters (gồm **storage/localfs/s3**)
đã có code và test (**1101 passed, 4 skipped** trong `tests_temp/`; 4 skip gồm 2 test
tích hợp MQTT/S3 cần broker/MinIO). Không còn ở giai đoạn thiết kế - khi sửa, đọc
code thật trong `xime/` và chạy `pytest` trước khi kết luận.

Trạng thái các mảng lớn (cập nhật 2026-06-29):

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
- **SQLAlchemy starter:** thêm `CrudRepository[T]` (0.6.1) - base repository generic
  cho sẵn `find/find_or_fail/find_all/exists/count/save/save_all/delete`; `model`
  là abstract property nên lớp nền là abstract (scanner bỏ qua), chỉ subclass set
  `model` mới vào DI. `find_or_fail` ném `EntityNotFoundError`. Hiện thực:
  `xime/starters/sqlalchemy/repository.py`.
- **JWT (0.5):** thêm ép `audience`/`issuer`, phơi claim qua `request_context[JWT_CLAIMS]`.
- **Kiểm toán toàn diện 0.5:** xem `docs/kiem-toan-0.5.md` (mọi phát hiện đã xử lý).
- **Backlog còn mở:** xem `docs/backlog-sua-loi.md`.

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
- **Backlog lỗi cần sửa (event bus tests, pb2 collision):** `docs/backlog-sua-loi.md`
- **Wishlist tính năng tương lai (bidi, transport TCP, retry...):** `docs/wishlist-tinh-nang.md`
