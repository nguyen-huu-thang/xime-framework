# XIME Framework — Hướng dẫn phiên làm việc

Python backend framework đã triển khai **~95%**: toàn bộ core, các adapter (web,
gRPC code-first + client SDK, socket) và starters đã có code và test (hơn 870
test trong `tests_temp/`). Không còn ở giai đoạn thiết kế - khi sửa, đọc code
thật trong `xime/` và chạy `pytest` trước khi kết luận.

Trạng thái các mảng lớn (cập nhật 2026-06-13):

- **Core DI / lifecycle / config / event bus:** hoàn thành.
- **Web adapter:** hoàn thành, có `configure_middleware` /
  `configure_exception_handlers`.
- **gRPC code-first (server):** hoàn thành - `xime grpc generate/check`, sinh
  proto + lock + sidecar `contract.json`, serve qua nối dây động, mTLS động
  (`configure_grpc_tls`).
- **gRPC client SDK:** hoàn thành Phase 1-4 - `xime grpc client` sinh SDK
  (kèm `--package`), `configure_grpc_clients` + DI, `XimeGrpcChannel` deadline
  + lỗi typed + mTLS động. Còn lại: retry policy, gen từ ContractModel.
- **Socket adapter:** hoàn thành (dùng chung contract với gRPC code-first).
- **Backlog còn mở:** xem `docs/backlog-sua-loi.md`.

## Tài liệu cần đọc khi bắt đầu

- **Tổng quan dự án & kiến trúc:** `../CLAUDE.md`
- **Nguyên tắc code & DI:** `rules/coding.md`
- **Thiết kế Transaction:** `rules/transaction.md`
- **Interface Binding (Protocol):** `rules/interface-binding.md`

## Tài liệu thiết kế chi tiết (đọc khi cần)

- **Thiết kế tổng thể:** `docs/tai-lieu-thiet-ke.md`
- **Giới thiệu & triết lý:** `docs/gioi-thieu-framework.md`
- **Cây thư mục dự án:** `docs/cay-thu-muc.md`
- **Entry point ứng dụng (`main.py`):** `docs/app-entry-point.md`
- **Routing layer (class-based controllers, `_make_handler`):** `docs/routing-layer.md`
- **Kế hoạch gRPC Client SDK + mTLS động (chốt 2026-06-12):** `docs/grpc-client-mtls-plan.md`
- **Backlog lỗi cần sửa (event bus tests, pb2 collision):** `docs/backlog-sua-loi.md`
- **Wishlist tính năng tương lai (bidi, transport TCP, retry...):** `docs/wishlist-tinh-nang.md`
