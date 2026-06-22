# Cây thư mục — Xime Framework

```text
xime/                        ← package root (thin re-export layer)
│
├── core/
│   ├── bootstrap/
│   ├── container/
│   ├── metadata/
│   ├── config/
│   ├── lifecycle/
│   ├── context/
│   ├── contract/            ← endpoint contract dùng chung Socket + gRPC code-first
│   ├── security/
│   ├── event/
│   ├── transaction/
│   └── exception/
│
├── adapters/
│   ├── web/
│   │   ├── openapi/
│   │   ├── routing/         ← routing layer (class-based controllers)
│   │   ├── middleware/      ← pure-ASGI request-context middleware
│   │   ├── files/           ← streaming upload/download (Range, chunked)
│   │   └── ws/
│   ├── grpc/
│   │   ├── codefirst/       ← sinh proto/SDK từ Python DTO
│   │   ├── client/          ← client SDK runtime + codegen
│   │   ├── interceptors/
│   │   ├── routing/
│   │   └── tls/             ← mTLS động
│   ├── socket/              ← Unix domain socket IPC (Linux)
│   │   └── routing/
│   └── mqtt/                ← MQTT pub/sub + RPC over MQTT v5
│       └── routing/
│
├── starters/
│   ├── sqlalchemy/
│   ├── jwt/
│   ├── scheduler/
│   ├── cache/               ← Protocol CacheService
│   ├── redis/               ← backend CacheService
│   ├── storage/             ← Protocol StorageService (+ _keys validate dùng chung)
│   ├── localfs/             ← backend StorageService trên filesystem
│   └── s3/                  ← backend StorageService S3/MinIO
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
- **`contract/`** — Định nghĩa endpoint contract (`@command`/`@stream`) dùng chung Socket + gRPC code-first
- **`security/`** — `SecurityContext`, `AuthenticationManager`, `AuthorizationManager`
- **`event/`** — Event bus nội bộ
- **`transaction/`** — `TransactionManager`, `TransactionContext`
- **`exception/`** — Hệ thống phân cấp exception của framework

---

### `adapters/`

Tích hợp giao thức. Mỗi adapter chịu trách nhiệm thiết lập request `Context` và kết nối giao thức với Core.

- **`web/`** — HTTP + WebSocket server qua FastAPI (ASGI)
  - **`openapi/`** — OpenApiConfig, security schemes (JwtBearer, ApiKey...)
  - **`routing/`** — class-based controllers, decorator `@get`/`@post`...
  - **`middleware/`** — `RequestContextMiddleware` (pure-ASGI)
  - **`files/`** — helper streaming `stream_object` (Range) / `save_upload` (chunked)
  - **`ws/`** — WebSocket handler base, routing WebSocket
- **`grpc/`** — gRPC server qua `grpc.aio`: code-first (sinh proto/SDK), client SDK, interceptors, mTLS động
- **`socket/`** — Unix domain socket IPC (Linux, SO_PEERCRED), dùng chung contract với gRPC code-first
- **`mqtt/`** — MQTT pub/sub (`@subscribe`) + RPC over MQTT v5 (`@rpc`), `MqttPublisher`, auto-reconnect

---

### `starters/`

Các module quickstart tùy chọn, tương tự `spring-boot-starter-*` trong Spring Boot.

- **`sqlalchemy/`** — Async DB session, `SqlAlchemyTransactionManager`
- **`jwt/`** — Xác thực JWT (HS/RSA/EC/EdDSA), middleware, `audience`/`issuer`
- **`scheduler/`** — Lập lịch tác vụ (APScheduler v4)
- **`cache/`** — Abstraction `CacheService` (trung lập backend)
- **`redis/`** — Async Redis client + backend cho `CacheService`
- **`storage/`** — Abstraction `StorageService` (object/blob store) + validate key dùng chung
- **`localfs/`** — Backend `StorageService` trên filesystem local (chống path traversal)
- **`s3/`** — Backend `StorageService` S3/MinIO (multipart, presigned URL)

---

### `testing/`

Tiện ích test và DI overrides dành cho môi trường kiểm thử.

---

### `cli/`

Công cụ dòng lệnh cho developer (scaffolding, codegen, v.v.).
