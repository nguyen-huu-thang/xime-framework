# Đóng góp

[English](../en/contributing.md) | **Tiếng Việt**

[← Kiến trúc](architecture.md) · **9/9 — Đóng góp**

---

Cảm ơn bạn đã cân nhắc đóng góp cho XIME. Đây là dự án cá nhân và sự giúp đỡ của cộng đồng là thiết yếu để nó phát triển.

---

## Trước khi bắt đầu

1. Đọc tài liệu [Kiến trúc](architecture.md) để hiểu cách XIME được cấu trúc
2. Đọc tài liệu [Khái niệm cốt lõi](core-concepts.md) để hiểu mô hình DI
3. Xem qua các issue đang mở để biết điều gì đang được thảo luận

---

## Cách đóng góp

### Báo cáo Bug

Mở issue với:

- Bạn mong đợi điều gì
- Điều gì thực sự xảy ra
- Ví dụ tối giản có thể tái tạo (code + thông báo lỗi)

### Đề xuất tính năng

Mở issue mô tả:

- Vấn đề bạn muốn giải quyết
- Bạn tưởng tượng API trông như thế nào
- Tại sao nó phù hợp triết lý XIME (explicit, fail-fast, no magic)

### Gửi Pull Request

1. Fork repository
2. Tạo branch: `git checkout -b feature/my-feature`
3. Thực hiện thay đổi
4. Thêm test cho behavior mới
5. Chạy test suite: `pytest`
6. Mở PR với mô tả rõ ràng về điều đã thay đổi và tại sao

---

## Code Style

- Theo code style hiện có (chưa có linter config — dùng common sense)
- Tất cả tham số constructor phải có type hint
- Không `@inject`, `@service`, hay annotation-based DI — dùng constructor injection
- Fail fast: validate lúc startup, không phải lúc runtime
- Viết test cho behavior mới

---

## Roadmap

Các mảng cần làm, theo thứ tự ưu tiên:

### Ưu tiên cao

| Mảng | Mô tả | Độ khó |
| --- | --- | --- |
| **gRPC Adapter** | Class-based gRPC service handler, tương tự pattern controller | Trung bình |
| **WebSocket support** | WebSocket routing và context management | Trung bình |
| **Exception → HTTP mapping** | Map domain exception đến HTTP status code tự động | Thấp |
| **CLI scaffolding** | `xime new my-service` để tạo cấu trúc project | Trung bình |

### Ưu tiên trung bình

| Mảng | Mô tả | Độ khó |
| --- | --- | --- |
| **Redis starter** | Redis client tích hợp với config binding | Thấp |
| **Cache starter** | Cache abstraction backed by Redis hoặc in-memory | Trung bình |
| **Request scope** | DI instance theo `Request`-scope (một per HTTP request) | Cao |
| **`configure_controllers()` auto-scan** | Tự động thêm controller package vào DI scan | Thấp |
| **Controller scanner `__all__` support** | Tôn trọng `__all__` trong controller package | Thấp |

### Ưu tiên thấp hơn

| Mảng | Mô tả | Độ khó |
| --- | --- | --- |
| **MQ adapter** | Tích hợp RabbitMQ / Kafka | Cao |
| **Savepoint (nested transaction)** | Hỗ trợ nested transaction thực sự | Cao |
| **Cải thiện `@job`** | Ergonomics tốt hơn cho scheduler job | Thấp |
| **Publish lên PyPI** | Package và publish lên PyPI | Thấp |
| **Cải thiện tài liệu** | Thêm ví dụ, tutorial, API reference | Thấp |

---

## Cấu trúc dự án

```text
core/           ← Không có external dependency ngoài python-dependency-injector
adapters/       ← Tích hợp theo giao thức (FastAPI, gRPC, ...)
starters/       ← Tích hợp tùy chọn (SQLAlchemy, JWT, ...)
testing/        ← Test utility
cli/            ← Developer CLI tool
tests_temp/     ← Test suite hiện tại (sẽ được tổ chức lại)
```

---

## Quy tắc thiết kế — Vui lòng đọc kỹ

Các quy tắc này không thể thương lượng cho đóng góp chạm vào Core hoặc adapter:

1. **Không annotation cho vai trò component** — `@service`, `@repository`, `@component`, `@inject` không tồn tại trong XIME
2. **Chỉ constructor injection** — tất cả dependency qua tham số `__init__`
3. **Explicit hơn implicit** — nếu được cấu hình, nó phải được khai báo tường minh ở đâu đó; không có gì tự động phát hiện bằng magic
4. **Fail fast** — nếu cấu hình startup sai, app phải thất bại lúc startup với lỗi rõ ràng
5. **Core không phụ thuộc adapter** — `core/` không được import từ `adapters/` hay bất kỳ thư viện giao thức nào (FastAPI, grpc, v.v.)
6. **Protocol cho interface** — dùng `typing.Protocol`, không phải `ABC`

---

## Câu hỏi?

Mở issue với nhãn `question`. Không có câu hỏi nào là ngớ ngẩn — thiết kế này cố tình khác phần lớn Python framework và xứng đáng được thảo luận.

---

[← Kiến trúc](architecture.md) · **9/9 — Đóng góp**
