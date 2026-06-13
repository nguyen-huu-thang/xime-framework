# Wishlist tính năng - các ý tưởng tương lai (chưa làm)

> Gom từ phần "Lộ trình tương lai" của hai bản thiết kế gốc
> (`muốn làm thêm/grpc.txt`, `muốn làm thêm/socket.txt`) khi hai tính năng đó đã
> code xong. Đây là danh sách ý tưởng, KHÔNG phải cam kết - chọn làm khi có nhu
> cầu thật từ service. Việc gRPC client + mTLS có kế hoạch riêng chi tiết ở
> `grpc-client-mtls-plan.md`.

## Core DI / Interface Binding

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
