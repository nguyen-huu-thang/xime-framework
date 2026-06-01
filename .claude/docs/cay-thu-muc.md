# Cây thư mục — Xime Framework

```text
xime/
│
├── core/
│   ├── bootstrap/
│   ├── container/
│   ├── metadata/
│   ├── config/
│   ├── lifecycle/
│   ├── context/
│   ├── security/
│   ├── event/
│   └── exception/
│
├── adapters/
│   ├── fastapi/
│   ├── grpc/
│   ├── websocket/
│   └── mq/
│
├── starters/
│   ├── sqlalchemy/
│   ├── redis/
│   ├── jwt/
│   ├── cache/
│   └── scheduler/
│
├── testing/
│
└── cli/
```

## Giải thích các thư mục

### `core/`

Nền tảng framework, không phụ thuộc vào bất kỳ adapter hay thư viện giao thức nào.

- **`bootstrap/`** — Điểm khởi động ứng dụng, điều phối toàn bộ quá trình startup
- **`container/`** — Package scanning, phân giải type hint, xây dựng và kiểm tra dependency graph
- **`metadata/`** — Tiện ích xử lý type metadata
- **`config/`** — Hệ thống cấu hình hai tầng (Framework config + Runtime config)
- **`lifecycle/`** — Hook vòng đời (`PostConstruct`, `PreDestroy`)
- **`context/`** — Dữ liệu theo phạm vi request thông qua `ContextVar`
- **`security/`** — `SecurityContext`, `AuthenticationManager`, `AuthorizationManager`
- **`event/`** — Event bus nội bộ
- **`exception/`** — Hệ thống phân cấp exception của framework

---

### `adapters/`

Tích hợp giao thức. Mỗi adapter chịu trách nhiệm thiết lập request `Context` và kết nối giao thức với Core.

- **`fastapi/`** — HTTP server, routing, middleware, OpenAPI
- **`grpc/`** — gRPC server thông qua `grpc.aio`
- **`websocket/`** — Hỗ trợ WebSocket
- **`mq/`** — Tích hợp message queue

---

### `starters/`

Các module quickstart tùy chọn, tương tự `spring-boot-starter-*` trong Spring Boot.

- **`sqlalchemy/`** — Async DB session, `SqlAlchemyTransactionManager`
- **`redis/`** — Redis client
- **`jwt/`** — Xác thực JWT
- **`cache/`** — Abstraction caching
- **`scheduler/`** — Lập lịch tác vụ

---

### `testing/`

Tiện ích test và DI overrides dành cho môi trường kiểm thử.

---

### `cli/`

Công cụ dòng lệnh cho developer (scaffolding, codegen, v.v.).
