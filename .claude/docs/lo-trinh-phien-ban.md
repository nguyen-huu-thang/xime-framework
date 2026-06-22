# Lộ trình phiên bản Xime Framework

> Chỉ mục tổng các mốc phiên bản đã chốt, để tra nhanh "việc X làm ở bản nào".
> Chi tiết từng mục nằm ở các doc được trỏ tới. Cập nhật 2026-06-22.
> Hiện tại: 0.5.0 (pyproject đã đồng bộ 0.5.0).

| Bản | Chủ đề | Trạng thái |
| --- | --- | --- |
| 0.3 | Hardening + hoàn tất gRPC | Đã phát hành (2026-06-20) |
| 0.4 | Cross-cutting + starters | Đã phát hành (2026-06-20) |
| 0.5 | Kiểm toán toàn diện + Messaging/IoT (MQTT) + File | Đã phát hành (2026-06-22) |
| 0.6 | Thay `dependency-injector` + dynamic interface binding | Đã chốt mốc, cần nghiên cứu sâu |
| 0.7 | Fieldbus công nghiệp (Modbus TCP + OPC UA) | Đã chốt mốc (dời từ 0.5, 2026-06-21) |
| 0.8 | Dự phòng cho cụm DI / wishlist | Mở |

---

## 0.3 - Hardening & hoàn tất gRPC

Chi tiết đầy đủ: `ke-hoach-0.3.md`.

- Nhóm 1 vá bug: warn `def` vs `async def` (#9), interceptor abort hai lần (#2),
  default `str(exc)` lộ nội bộ (#1a), `asyncio.Lock` cert rotate (#7), bỏ
  hardcode `server_id="default"` (#8).
- Nhóm 2: retry policy YAML cho gRPC client.
- Nhóm 4: bump `0.3.0` + cập nhật docs + CHANGELOG.

## 0.4 - Cross-cutting + starters

Chi tiết kế hoạch: `ke-hoach-0.4.md`. Nguồn ý tưởng: `wishlist-tinh-nang.md`
(mục "Security / Cross-cutting" và "Starters").

- Trích xuất danh tính peer mTLS (CN client cert) -> `request_context`, key
  trung tính + helper `current_caller()`. (đề xuất notification mục 1)
- `cache/` starter (Protocol `CacheService`) + `redis/` starter (client +
  impl của CacheService).
- Cân nhắc thêm (chưa chốt cứng): gRPC reflection + health checking; error
  catalog visibility-aware (#1b).

## 0.5 - Kiểm toán toàn diện + Messaging/IoT + File

> **ĐÃ PHÁT HÀNH 2026-06-22.** Cả ba nhóm hoàn tất: audit toàn diện (báo cáo
> `kiem-toan-0.5.md`, mọi phát hiện đã xử lý), adapter MQTT (pub/sub + RPC over
> MQTT v5), storage starter (local + s3/MinIO) + streaming web. Test: 1051 passed,
> 4 skipped. Chi tiết thực thi: `ke-hoach-trien-khai-0.5.md`.

Chi tiết đầy đủ: `ke-hoach-0.5.md`. Kế hoạch THỰC THI chi tiết (thứ tự code,
file nào, pattern nào) + các quyết định đã chốt 2026-06-22:
`ke-hoach-trien-khai-0.5.md`.

> **Đổi phạm vi 2026-06-21:** bản gốc (chốt 2026-06-19) là bản KHÔNG thêm tính
> năng, chỉ kiểm toán. Chủ dự án quyết định gộp thêm hai mảng feature: **adapter
> MQTT (messaging/IoT)** và **làm việc với file (storage starter + streaming web)**.
> Audit vẫn là trục chính, làm trước; feature làm sau trên nền đã sạch.

- **Nhóm A - Kiểm toán toàn diện** (trục chính): đọc kỹ TỪNG FILE core/adapters/
  starters, ghi `docs/kiem-toan-0.5.md`, phân loại theo mức nghiêm trọng rồi mới
  vá. Gồm fix issue context-bleeding khi test ASGI in-process (dental-clinic #001):
  chuyển `RequestContextMiddleware` từ `BaseHTTPMiddleware` sang pure ASGI middleware.
- **Nhóm B - Adapter MQTT**: pub/sub message-driven (`@subscribe`) và RPC over
  MQTT v5 (`@rpc`), `MqttPublisher`, auto-reconnect, định tuyến bằng Subscription
  Identifier, extra `xime[mqtt]` (aiomqtt import lười).
- **Nhóm C - File**: storage starter (Protocol `StorageService`, backend local
  và s3/MinIO) theo pattern cache/redis, kèm streaming upload/download lớn ở web
  adapter (Range, multipart, chunked).

Phạm vi kiểm toán (đọc thật kỹ, không lướt):

- **Toàn bộ `xime/core/`** - DI container (scan, resolver, graph, registry),
  lifecycle, config hai tầng, context (`ContextVar`), event bus, security,
  transaction, exception hierarchy, metadata. Đây là nền, soi trước.
- **Toàn bộ `xime/adapters/`** - web, grpc (codefirst + client + tls +
  interceptors), socket. Soi từng file.
- **Toàn bộ `xime/starters/`** - sqlalchemy, jwt, scheduler (+ cache/redis nếu
  0.4 đã thêm).

Các trục cần soi xuyên suốt:

1. **Mâu thuẫn logic giữa các phần** - vd thứ tự interceptor (RequestContext ->
   Error -> custom), vòng đời context được set/clear nhất quán giữa web/grpc/
   socket, error mapping có đồng nhất ba transport không.
2. **Nhất quán cross-cutting** - các key trong `request_context` (request_id,
   peer_*, caller...), việc `clear_security()` luôn chạy ở teardown mọi adapter,
   quy ước mã lỗi/exception giống nhau giữa REST/gRPC/socket.
3. **An toàn async / race condition** - đã có tiền lệ #7 (channel rotation).
   Soi mọi chỗ chia sẻ state mutable giữa coroutine: registry, tls registry,
   client channels, event bus tasks.
4. **Rò rỉ tài nguyên** - channel (retired pool), AsyncSession, socket, scheduler
   job, gRPC server. PreDestroy có đóng đủ và đúng thứ tự không.
5. **Fail-fast lúc startup** - mọi sai cấu hình (thiếu binding, thiếu type hint,
   circular, thiếu provider TLS, controller lệch server_id) có nổ rõ ràng lúc
   startup không, hay âm thầm hỏng lúc runtime.
6. **Edge case marshal/serialize** - bytes/decimal/uuid/date/optional/repeated/
   map/nested/enum. Đã từng có bug ở đây (#3, #marshal bytes) -> soi kỹ lại.
7. **Khoảng trống test** - `tests_temp/` (tên cho thấy có thể là thư mục tạm,
   cân nhắc chuẩn hóa thành `tests/`). Tìm nhánh code chưa có test, nhất là
   đường lỗi và teardown.
8. **Dọn backlog tồn đọng** - đối chiếu `backlog-sua-loi.md`, các mục `[ ]` còn
   mở ở `grpc-client-mtls-plan.md` (dọn dẹp data-service phía service), TODO
   rải trong code.

Cách làm đề xuất khi tới 0.5: đi theo từng package, mỗi file ghi phát hiện vào
một báo cáo kiểm toán (`docs/kiem-toan-0.5.md`), phân loại theo mức nghiêm trọng,
rồi mới vá. KHÔNG vừa đọc vừa sửa lung tung để tránh bỏ sót.

## 0.6 - Thay `dependency-injector` + dynamic interface binding

Chi tiết + toàn bộ phân tích: `wishlist-tinh-nang.md` (mục đầu phần "Core DI /
Interface Binding").

- Thay `dependency-injector` bằng registry singleton tự viết (refactor nội bộ,
  không đổi API người dùng). Phân tích mức phụ thuộc/tốc độ/đa luồng/đa tiến
  trình đã làm sẵn 2026-06-19.
- Dynamic interface binding (`bind_many`/`switcher`) - đụng cùng lớp registry,
  cân nhắc làm chung đợt. Có thể tràn sang 0.8 nếu cần.

## 0.7 - Fieldbus công nghiệp (Modbus TCP + OPC UA)

Chi tiết đầy đủ: `ke-hoach-0.7.md`. Dời từ 0.5 (quyết 2026-06-21).

- Xime đóng vai client/master chủ động đọc PLC/thiết bị nhà máy - mô hình
  polling/subscribe, khác cả RPC lẫn pub/sub của MQTT.
- **Modbus TCP** (pymodbus, extra `xime[modbus]`) làm trước vì đơn giản; **OPC UA**
  (asyncua, extra `xime[opcua]`, bảo mật phức tạp hơn) cân nhắc tách tiếp.
- **Chốt trước khi đầu tư:** nếu có edge gateway phía trước (gateway nói Modbus
  với PLC rồi đẩy MQTT lên Xime) thì có thể KHÔNG cần hai adapter này - MQTT đủ.

## Chưa gắn mốc (wishlist thuần)

Xem `wishlist-tinh-nang.md`: bidi streaming, `@proto_field`, sinh SDK từ
ContractModel, SDK đa ngôn ngữ, socket Transport -> TCP/Named Pipe, idempotency
helper, gRPC reflection/health (nếu 0.4 không lấy).
