# Kế hoạch triển khai 0.5 (chi tiết, theo thứ tự code)

> Lập ngày 2026-06-22. Đây là kế hoạch THỰC THI chi tiết cho 0.5, bám sát code
> thật trong `xime/`. Phạm vi & lý do nền tảng xem `ke-hoach-0.5.md` và
> `lo-trinh-phien-ban.md`. File này quyết định "code cái gì, file nào, theo
> pattern nào".

## Quyết định đã chốt (2026-06-22)

Chủ dự án chốt trước khi code:

1. **MQTT:** làm cả **pub/sub một chiều + RPC over MQTT** (request/reply qua
   `response_topic` + correlation id) ngay trong 0.5.
2. **Storage:** ship cả **`local` + `s3`/MinIO** cùng đợt.
3. **Interface `StorageService`:** **bytes + stream song song** (`put`/`get` cho
   nhỏ, `put_stream`/`open_stream` cho lớn).
4. **Thư mục test:** **giữ `tests_temp/`** trong đợt này, KHÔNG đổi tên `tests/`.
5. **Thư viện MQTT:** `aiomqtt` (import lười, extra `xime[mqtt]`).

## Đảo thứ tự so với kế hoạch gốc

Kế hoạch gốc (`ke-hoach-0.5.md`) khuyến nghị **audit trước, feature sau**. Chủ dự
án quyết định **code feature trước, audit sau**. Hệ quả ghi nhận: audit (Giai
đoạn 3) sẽ phải soi cả code mới viết (storage + MQTT), nên phạm vi audit **gộp
thêm** hai mảng feature mới này. Trục audit không đổi.

```text
Giai đoạn 1 - Feature C: Storage starter (local + s3) + streaming web
Giai đoạn 2 - Feature B: Adapter MQTT (pub/sub + RPC over MQTT)
Giai đoạn 3 - Audit A: kiểm toán toàn diện core/adapters/starters + vá
Giai đoạn 4 - Phát hành: docs, CHANGELOG, bump 0.5.0, full pytest
```

Thứ tự nội bộ C trước B: storage theo pattern starter quen thuộc (rủi ro thấp),
MQTT là adapter mới mô hình pub/sub khác (rủi ro cao hơn).

---

## Giai đoạn 1 - Feature C: File / Storage

### C.1 Storage starter `xime/starters/storage/` (theo pattern `cache`)

- `storage/_service.py` - Protocol `StorageService` (`@runtime_checkable`), thuần
  interface như `CacheService`. Method (bytes + stream song song):
  - `async def put(self, key, data: bytes, *, content_type=None) -> None`
  - `async def get(self, key) -> bytes | None`
  - `async def put_stream(self, key, chunks: AsyncIterator[bytes], *, content_type=None) -> None`
  - `async def open_stream(self, key, *, offset=0, length=None) -> AsyncIterator[bytes]`
    (`offset`/`length` phục vụ HTTP Range ở C.2)
  - `async def delete(self, key) -> None`
  - `async def exists(self, key) -> bool`
  - `async def stat(self, key) -> StorageStat | None` (size, content_type, etag)
  - `async def url(self, key, *, expires=None) -> str` (backend không hỗ trợ ->
    raise `UnsupportedOperation` rõ ràng)
- `storage/_exceptions.py` - `StorageError`, `ObjectNotFound`, `UnsupportedOperation`.
- `storage/__init__.py` - export `StorageService`, `StorageStat`, exception;
  `__all__ = []` (Protocol không đăng ký DI, giống `cache`).

Triết lý: framework cấp cơ chế, trả/nhận dữ liệu thô; authorization, đặt tên key,
định dạng là việc của app.

### C.2 Backend `local` - starter riêng `xime/starters/localfs/`

Tách backend khỏi Protocol giống `redis` tách khỏi `cache`.

- `localfs/_storage.py` - `LocalFileStorage` implements `StorageService`:
  - Đọc `RuntimeConfig` `storage.local.root` (bắt buộc; thiếu -> `ValueError`).
  - **Chống path traversal:** chuẩn hóa key, từ chối `..`/absolute, ghép trong
    `root` rồi `os.path.realpath` kiểm tra vẫn nằm trong `root`.
  - `put_stream`: ghi file tạm `.part` rồi `os.replace` (atomic).
  - `open_stream`: đọc theo chunk (mặc định 64 KiB) qua `asyncio.to_thread`
    (file IO blocking) - KHÔNG thêm dep `aiofiles`.
  - `url()` -> raise `UnsupportedOperation`.
- `localfs/__init__.py` - `__all__ = ["LocalFileStorage"]`. Không cần extra.

### C.3 Backend `s3`/MinIO - starter riêng `xime/starters/s3/`

- `s3/_client.py` - `S3ClientProvider` (giống `RedisClientProvider`): đọc
  `storage.s3.*` (endpoint_url, region, bucket, access_key, secret_key, max...),
  import lười `aioboto3`, `pre_destroy` đóng session/client.
- `s3/_storage.py` - `S3FileStorage` implements `StorageService`. `url()` ->
  presigned URL thật; `open_stream` dùng `Range`; `put_stream` dùng multipart.
- `s3/__init__.py` - `__all__ = ["S3ClientProvider", "S3FileStorage"]`.
- pyproject: thêm extra `s3 = ["aioboto3>=12"]`, thêm vào `all`.

App chọn backend bằng binding tường minh:
```python
dependency.bind({ StorageService: LocalFileStorage })   # hoặc S3FileStorage
```

### C.4 Streaming ở web adapter `xime/adapters/web/files/`

- `web/files/_download.py` - helper `stream_object(storage, key, *, filename=None, request=None)`:
  trả `StreamingResponse` từ `open_stream`; parse `Range` -> `offset`/`length`,
  trả `206` + `Content-Range`/`Accept-Ranges`; set `Content-Type`/
  `Content-Length`/`Content-Disposition` từ `stat()`.
- `web/files/_upload.py` - helper `save_upload(storage, key, upload_file, *, max_bytes=None)`:
  đọc `UploadFile` theo chunk -> `put_stream`; vượt `max_bytes` -> raise
  `PayloadTooLarge` (map HTTP 413).
- `web/files/__init__.py` - export hai helper. Không đăng ký DI (tiện ích gọi
  trong controller).

Hoãn sang 0.6: presigned-URL upload trực tiếp lên S3, multipart resumable (tUS).

### C.5 Test (trong `tests_temp/`)

- `tests_temp/starters/storage/` - `LocalFileStorage` (put/get/stream/exists/
  delete/stat, path traversal bị chặn, atomic replace).
- S3: test bằng moto/fake nếu có; nếu không, interface-compliance + skip khi
  thiếu extra.
- `tests_temp/web/files/` - Range download (200 vs 206), upload chunked, vượt
  `max_bytes` -> 413.

---

## Giai đoạn 2 - Feature B: Adapter MQTT (pub/sub + RPC over MQTT)

Thư mục `xime/adapters/mqtt/`, đứng ngang `web/grpc/socket`. `aiomqtt` import
lười, extra `xime[mqtt]`.

### B.1 Decorator routing `_decorators.py`

- `@subscribe("sensors/+/temperature", qos=1)` - gắn `SubscribeInfo(topic, qos)`
  (mẫu `_route`/`RouteInfo`). Handler nhận `(payload: bytes, topic: str, message)`,
  KHÔNG ép deserialize.
- `@rpc("service/echo", qos=1)` - RPC over MQTT: handler có `request: BaseModel`
  + return `BaseModel`; adapter trả ra `response_topic` (MQTT v5 property hoặc
  convention `<topic>/reply/<correlation_id>`), kèm `correlation_data`.

### B.2 Scanner + builder `routing/_scanner.py`, `routing/_builder.py`

- Mẫu `ControllerScanner` + `SocketEndpointBuilder`: tìm controller có
  `SUBSCRIBE_ATTR`/`RPC_ATTR`, resolve instance qua DI, build bảng
  `topic-filter -> bound handler`.
- Fail-fast startup: handler phải `async def`; `@rpc` phải có `request`/return
  BaseModel; trùng topic-filter trên cùng client -> `StartupException`.
- Match topic theo luật wildcard MQTT (`+`, `#`) khi dispatch.

### B.3 Adapter + publisher `_adapter.py`, `_publisher.py`, `_config.py`

- `MqttAdapter(client_id="default")` implements `Adapter` (`start`/`stop`), mẫu
  `SocketAdapter`:
  - `start()`: import lười `aiomqtt`; connect; subscribe toàn bộ topic; vòng lặp
    nhận message -> dispatch.
  - **Auto-reconnect:** bọc vòng lặp connect lại + **re-subscribe** toàn bộ topic
    sau reconnect.
  - Mỗi message: `request_context.set("request_id", uuid4)`; `finally` ->
    `request_context.clear()` + `clear_security()` (nhất quán mọi adapter).
  - Concurrency: xử lý message trong task riêng có **giới hạn** (semaphore, config
    `max_concurrency`); giữ reference task như socket adapter.
  - `stop()`: hủy task, disconnect sạch (idempotent).
- `MqttPublisher` (singleton DI): `await publisher.publish(topic, payload, qos=0, retain=False)`.
  Cân nhắc tách client thành provider (giống `RedisClientProvider`) để DI quản lý
  vòng đời, adapter chỉ subscribe/dispatch - quyết khi code.
- `_config.py` - `MqttConfig.resolve(runtime)` đọc `mqtt.*`: `host` (thiếu ->
  fail-fast), `port`, `username`/`password`, `client_id`, `keepalive`, `tls`
  (optional), LWT, `default_qos`, `max_concurrency`. Registry +
  `configure_mqtt_controllers(*packages)` theo mẫu `socket_registry`.
- RPC over MQTT: dùng MQTT v5 `ResponseTopic` + `CorrelationData`. Handler trả
  BaseModel -> serialize (JSON mặc định) -> publish ra `response_topic`. Lỗi ->
  publish payload lỗi theo convention error đồng nhất REST/gRPC/socket.

### B.4 Tích hợp orchestrator

- Chạy qua `app.use(MqttAdapter(...))` + `app.run()` như mọi adapter; publisher là
  DI singleton, controller scan qua `dependency.scan`. Không cần đụng
  `StartupOrchestrator` trừ khi publisher cần client do adapter sở hữu -> khi đó
  dùng provider tách.

### B.5 pyproject + test

- Extra `mqtt = ["aiomqtt>=2.0"]`, thêm vào `all`.
- `tests_temp/adapters/mqtt/` - scanner/builder fail-fast, topic-match wildcard,
  dispatch + context set/clear, RPC round-trip (broker giả/mock client).

### Câu hỏi mở MQTT (quyết lúc code chi tiết, không chặn kế hoạch)

- Controller MQTT **riêng** (không dùng chung web/grpc) vì pub/sub không có
  return - đề xuất tách riêng.
- TLS client cert MQTT -> lưu `peer_cn` vào `request_context` cho đồng bộ mTLS
  gRPC (làm nếu kịp, không thì ghi backlog).

---

## Giai đoạn 3 - Audit A: Kiểm toán toàn diện

> Rủi ro do đảo thứ tự: audit phải soi cả code mới (storage/MQTT). Gộp code mới
> vào phạm vi audit để không bỏ sót.

Cách làm (KHÔNG vừa đọc vừa sửa):

1. Đọc kỹ TỪNG FILE: `core/` -> `adapters/` (gồm `mqtt`) -> `starters/` (gồm
   `storage`/`localfs`/`s3`).
2. Ghi mọi phát hiện vào báo cáo mới `.claude/docs/kiem-toan-0.5.md`, phân loại
   mức nghiêm trọng (Cao/Trung/Thấp): file:line, hiện tượng, gốc rễ, hướng vá.
3. Vá theo mức nghiêm trọng giảm dần; mỗi nhóm vá xong chạy `pytest`.

8 trục soi xuyên suốt (theo `ke-hoach-0.5.md`): mâu thuẫn logic giữa các phần,
nhất quán cross-cutting (key `request_context`, `clear_security()` ở mọi
teardown), an toàn async/race, rò rỉ tài nguyên (PreDestroy đóng đủ/đúng thứ tự),
fail-fast startup, edge case marshal/serialize, khoảng trống test, dọn backlog.

Mục cụ thể A.x - context bleeding ASGI in-process (dental-clinic #001):

- Chuyển `RequestContextMiddleware` (cân nhắc cả `JwtAuthMiddleware`) từ
  `BaseHTTPMiddleware` sang **pure ASGI middleware**
  (`async def __call__(self, scope, receive, send)`), set/clear ContextVar cùng
  context với app downstream.
- Rà toàn bộ middleware web còn dùng `BaseHTTPMiddleware`.
- Thêm test ASGITransport tái hiện kịch bản (request có token -> request không
  token kỳ vọng 401) trong `tests_temp/web/`.

---

## Giai đoạn 4 - Phát hành 0.5.0

- Cập nhật `.claude/docs/cay-thu-muc.md`, `tai-lieu-thiet-ke.md`,
  `lo-trinh-phien-ban.md` (đánh dấu 0.5 phát hành), `.claude/CLAUDE.md`.
- CHANGELOG 0.5.0; bump `version` trong `pyproject.toml` -> `0.5.0`.
- Chạy full `pytest` xác nhận xanh trước khi kết luận.

---

## Tóm tắt file đụng tới

| Loại | Đường dẫn |
|---|---|
| Mới (storage) | `xime/starters/storage/`, `xime/starters/localfs/`, `xime/starters/s3/` |
| Mới (web file) | `xime/adapters/web/files/` |
| Mới (mqtt) | `xime/adapters/mqtt/` (+ `routing/`) |
| Sửa | `pyproject.toml` (extras `s3`, `mqtt`, `all`, bump version) |
| Sửa (audit) | `xime/adapters/web/middleware/_context.py`, `jwt/_middleware.py`, + theo phát hiện |
| Doc/test mới | `.claude/docs/kiem-toan-0.5.md`, `tests_temp/{starters,adapters,web}/...` |
