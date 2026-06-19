# Wishlist tính năng - các ý tưởng tương lai (chưa làm)

> Gom từ phần "Lộ trình tương lai" của hai bản thiết kế gốc
> (`muốn làm thêm/grpc.txt`, `muốn làm thêm/socket.txt`) khi hai tính năng đó đã
> code xong. Đây là danh sách ý tưởng, KHÔNG phải cam kết - chọn làm khi có nhu
> cầu thật từ service. Việc gRPC client + mTLS có kế hoạch riêng chi tiết ở
> `grpc-client-mtls-plan.md`.

## Security / Cross-cutting (request context)

- **Trích xuất danh tính peer mTLS cho gRPC -> request_context** (đề xuất từ
  notification-service, đánh giá 2026-06-19, CHỐT đẩy 0.4). Hiện
  `RequestContextInterceptor` chỉ set `request_id`, không đọc client cert; trong
  khi socket adapter đã có tiền lệ lưu `peer_pid`/`peer_uid` vào request_context
  (`adapters/socket/_peercred.py`). Thiếu bản tương đương cho gRPC mTLS.

  Hướng đã chốt khi đánh giá:
  - Framework chỉ cấp **cơ chế**: đọc CN của client cert đã verify qua
    `context.auth_context()["x509_common_name"]`, **fail-soft** (không mTLS ->
    `None`, không phá request), lưu vào `request_context` dưới **key trung tính**
    (vd `peer_cn`), KHÔNG đóng cứng ngữ nghĩa `caller_service_id`. Lý do: CN có
    thể là định danh service HOẶC `owner_app_identity_id` của APPLICATION subject
    (xem mô hình Subject ở CLAUDE.md gốc) - app tự diễn giải, đúng pattern
    `_peercred.py` lưu sự thật thô.
  - Có thể thêm helper gọn `current_caller() -> str | None` ở `core/security`.
  - **Authorization** (caller nào được làm gì) vẫn ở app, framework không ôm.
  - Nguồn đề xuất: `Base Platform/notification/DE-XUAT-CAI-TIEN-FRAMEWORK.md` mục 1.

- **Tiện ích idempotency dùng chung** (đề xuất notification mục 2, CHƯA đủ chín).
  Nhiều service (notification outbox, payment...) cần dedupe theo key. CHƯA nên
  frameworkize: ngữ nghĩa key/backend/TTL/scope khác nhau nhiều giữa các service
  - để 2-3 service tự làm tới khi pattern hội tụ rồi mới rút lên framework.

## Core DI / Interface Binding

- **Thay `dependency-injector` bằng registry singleton tự viết** (phân tích
  2026-06-19, CHỐT nghiên cứu sâu + thực hiện trong **0.6 / 0.7 / 0.8**). Đây là
  refactor nội bộ, không đổi API người dùng.

  Tóm tắt phân tích đã làm (để khỏi phân tích lại):

  - **Mức phụ thuộc rất nông:** chỉ `xime/core/container/registry.py` chạm
    `dependency-injector`, dùng đúng 3 primitive: `containers.DynamicContainer()`
    (namespace để setattr provider), `providers.Object(obj)` (bọc instance dựng
    sẵn), `providers.Singleton(cls, **kwargs)` (lazy singleton + cache). KHÔNG
    dùng `@inject`/`Provide`, `DeclarativeContainer`, `Configuration`,
    `Resource`, `Factory`, `Selector` - tức gần như toàn bộ phần đặc sản thư
    viện. Mọi logic DI thật (scan, phân giải type hint, dựng graph, phát hiện
    cycle, topo sort) đã tự viết trong `container/`.
  - **Tốc độ:** lõi thư viện là Cython nên provider-call nhanh ở mức vi mô,
    NHƯNG framework dựng singleton eager một lần lúc startup (bước 7), runtime
    service giữ thẳng reference qua constructor injection - không gọi `get()`
    mỗi request. Nên ưu thế Cython gần như không phát huy. Bản tự viết (dict
    `type -> instance`, dựng theo topo order đã có) startup O(n) vài micro
    giây/class, runtime `get` = dict lookup (ngang hoặc nhanh hơn). ~50-80 dòng.
  - **Đa luồng:** `providers.Singleton` thread-safe sẵn (lock chống init hai
    lần), nhưng framework chạy asyncio (một luồng event-loop) + dựng eager lúc
    startup nên dict chỉ còn đọc -> vốn an toàn đa thread trong CPython. Nếu sau
    này có lazy init đa luồng thật, bản tự viết chỉ cần thêm một
    `threading.Lock` (vài dòng).
  - **Đa tiến trình:** thư viện KHÔNG giúp gì - mỗi process là interpreter +
    bộ nhớ tách rời, tự bootstrap container riêng (chuẩn gunicorn/uvicorn nhiều
    worker). Không chia sẻ singleton xuyên process. Tự code hay dùng thư viện
    không khác biệt cho đa tiến trình.
  - **Tính năng tương lai:** phần mạnh của thư viện (`@inject`, declarative,
    config provider, override magic) đúng là thứ framework CỐ TÌNH từ chối vì
    triết lý no-magic. Hai primitive có thể hữu ích (`Factory` = instance mỗi
    lần; `ContextLocalSingleton` cho scope Request/Session dựa ContextVar)
    framework tự làm dễ (đã dùng `ContextVar` trực tiếp ở `core/context/`).
  - **Rủi ro thấp:** có hơn 870 test phủ -> refactor an toàn. Lý do duy nhất
    hoãn: là churn nội bộ không thêm tính năng, không nên nhét vào bản hardening
    0.3.
  - **Lợi ích:** bỏ một dependency Cython (gọn đóng gói/cài đặt), sở hữu trọn
    lõi, nhất quán triết lý "minimal dependency, tự viết logic DI", và dễ tự
    thêm scope `Factory`/`Request` đúng ý sau này.

  Liên quan: mục **Dynamic interface binding** ngay dưới cũng đụng tới lớp
  registry/provider này - cân nhắc làm chung đợt.

- **Dynamic interface binding - nhiều implementation cho một interface, đổi
  được lúc runtime** (ý tưởng, chốt ghi nhận 2026-06-13, CHƯA thiết kế chi
  tiết, CHƯA làm trong các phiên bản gần đây).

  Hiện tại `dependency.bind({Interface: Impl})` chỉ map một interface → một
  implementation duy nhất; framework resolve thành singleton lúc startup và
  consumer giữ thẳng reference qua constructor injection.

  Ý tưởng: trong file config, liệt kê TẤT CẢ các implementation của một
  interface. Trong đó một cái là **primary / mặc định** (cấu hình y như hiện
  tại), các cái còn lại là **phụ**, chỉ liệt kê ra để framework biết. Khi ứng
  dụng chạy, framework cung cấp một hàm để app **đổi implementation đang dùng
  một cách động**, và cũng **trả lại được implementation mặc định**.

  Ví dụ hình dung (API chưa chốt):

  ```python
  # config/dependency.py - liệt kê primary + các phụ
  dependency.bind_many(
      PaymentGateway,
      primary=StripeGateway,
      alternatives=[PaypalGateway, MockGateway],
  )

  # runtime - app tự đổi
  switcher.use(PaymentGateway, PaypalGateway)   # đổi sang phụ
  switcher.reset(PaymentGateway)                # trả lại primary mặc định
  ```

  Câu hỏi mở cần giải khi thiết kế chi tiết (KHÔNG quyết bây giờ):

  - **Xung đột với constructor injection + "no magic proxy":** consumer đã giữ
    reference trực tiếp tới impl được inject lúc startup. Đổi binding lúc runtime
    sẽ KHÔNG tự đổi reference đó trừ khi chèn một lớp gián tiếp (provider /
    lookup / proxy). Điều này va vào triết lý "Minimal Magic, no proxy". Cần
    quyết: inject một `Provider[T]` / handle thay vì inject thẳng `T`? Hay chấp
    nhận chỉ những ai gọi `container.get()` mới thấy impl mới?
  - **Phạm vi đổi:** global cho cả app, hay request-scoped qua `ContextVar`
    (mỗi request dùng impl khác nhau, không ảnh hưởng request khác)?
  - **Vòng đời:** alternative có được khởi tạo sẵn (eager singleton) lúc startup
    để fail-fast, hay lazy lúc lần đầu `use()`? PostConstruct/PreDestroy chạy thế
    nào khi đổi qua lại?
  - **Thread/async safety** khi nhiều coroutine cùng đọc/đổi binding.
  - **Tương thích fail-fast hiện có:** quy tắc "nhiều candidate mà không có
    binding tường minh → startup fail" (xem `rules/interface-binding.md`) cần
    nới để cho phép khai báo nhiều impl có chủ đích, nhưng vẫn validate mọi
    alternative đều thỏa Protocol lúc startup.

## Starters (CHỐT mốc 0.4)

> Bộ starter dự kiến trong thiết kế tổng thể (`tai-lieu-thiet-ke.md` mục 14,
> `cay-thu-muc.md`) gồm 5 cái. ĐÃ CÓ CODE: `sqlalchemy`, `jwt`, `scheduler`.
> CÒN THIẾU 2 cái dưới đây - trước 2026-06-19 chưa gắn vào phiên bản nào, nay
> chốt làm trong **0.4**.

- **`cache/` starter - abstraction caching** (Protocol `CacheService`). Định
  hình interface caching dùng chung (get/set/delete/ttl...), tách khỏi backend
  cụ thể theo đúng pattern interface-binding.
- **`redis/` starter - Redis client**. Vừa là client Redis độc lập, vừa là MỘT
  implementation của `CacheService` (binding `CacheService -> RedisCacheService`
  trong `config/dependency.py`). Lifecycle: đóng connection pool lúc PreDestroy
  (mục "Close Database / Redis / gRPC Channels" trong trình tự shutdown đã có ở
  thiết kế).

Quan hệ: `cache` (interface) nên định hình trước hoặc cùng lúc với `redis`
(impl). Làm gần nhau trong cùng đợt 0.4.

## Code-First gRPC (server + contract)

- **`@proto_field(rename_from=..., number=...)`** - đổi tên field nhưng giữ
  nguyên số (tương thích nhị phân), hoặc pin số thủ công. Hiện rename field =
  xoá field cũ (vào reserved) + thêm field mới.
- **Bidi streaming** - `@stream` có cả upload lẫn download đồng thời trên một
  endpoint. v1 chỉ có client-stream HOẶC server-stream.
- **Map `Union` tổng quát → `oneof`** - hiện chỉ hỗ trợ `Optional[T]`
  (`T | None`), chưa map union nhiều nhánh sang `oneof`.
- **gRPC reflection + health checking tự động** - để `grpcurl`, load balancer,
  k8s probe dùng được mà không cần khai báo tay.
- **Sinh tài liệu kiểu OpenAPI cho gRPC** từ ContractModel.
- **proto `import` thư viện ngoài tùy ý** - hiện chỉ tự sinh `common.proto` nội
  bộ theo `server_id`.

## gRPC Client SDK

> Đã làm Phase 1-4 (xem `grpc-client-mtls-plan.md`). Còn lại:

- **Sinh SDK trực tiếp từ ContractModel** cho Xime-to-Xime (fidelity cao hơn
  sinh từ `.proto`, giữ nguyên Decimal/UUID... không cần sidecar). Đang ở Phase 4.
- **Retry policy đầy đủ trong YAML** (`grpc.clients.<id>.retry`). Đang ở Phase 4.
- **Sinh SDK đa ngôn ngữ** (C++/Rust/Go) từ ContractModel - hiện chỉ sinh Python.

## Socket Adapter

- **Credit-based flow control per-session** - bỏ head-of-line blocking. v1 chấp
  nhận head-of-line (server gửi tuần tự trong một connection).
- **Lớp `Transport` trừu tượng → TCP / Named Pipe** - để chạy được ngoài Linux
  (Windows) hoặc cross-host. v1 chỉ có `UnixTransport` (UDS, Linux). Thiết kế đã
  chừa sẵn interface `Transport` mỏng (open/accept/close) để cắm vào không đụng
  tầng session/protocol/dispatch.
- **Bidirectional stream** - upload + download đồng thời trên một endpoint.
- **Reconnect / retry tự động phía client** - v1 để client tự xử lý.

## Đã hoàn thành (không còn trong wishlist)

- ~~Sinh SDK client từ Contract~~ - đã làm (Python, từ `.proto` + sidecar).
- ~~Contract Model dùng chung Socket + gRPC code-first~~ - đã làm
  (`xime/core/contract/`).
- ~~Một Controller → nhiều transport~~ - đã làm (cùng `@command`/`@stream`).
