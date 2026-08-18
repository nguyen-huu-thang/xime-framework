<div align="center">

# XIME Framework

**Spring Boot-style developer experience for Python - without betraying Python's philosophy.**

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://pypi.org/project/xime/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**English** | [Tiếng Việt](README-vn.md)

[Documentation](docs/en/getting-started.md) · [Examples](#-example-projects)

</div>

---

XIME is a convention layer for Python microservices. It sits **on top of** FastAPI, SQLAlchemy, and gRPC - providing automatic dependency injection, startup-time graph validation, and architectural guardrails so you can focus on business logic instead of wiring.

```python
# Before XIME - wire everything manually
container.user_service = providers.Singleton(
    UserService,
    repository=container.user_repository,
    transaction=container.transaction_manager,
)

# With XIME - just write your class
class UserService:
    def __init__(
        self,
        repository: UserRepository,
        transaction: TransactionManager,
    ):
        self.repository = repository
        self.transaction = transaction
```

XIME reads your type hints, scans your packages, builds the dependency graph, validates it at startup, and wires everything together - automatically.

---

## Why XIME?

Python has excellent libraries for HTTP, databases, and serialization. What it lacks is a **convention layer** that:

- Automatically discovers and wires dependencies from constructor type hints
- Enforces architectural boundaries through directory structure
- Validates the dependency graph at startup - not at runtime when a user hits an endpoint
- Provides a consistent structure for Clean Architecture / DDD / Modular Monolith projects

XIME fills that gap. It does not replace FastAPI or SQLAlchemy - it makes them easier to use at scale.

---

## Why not dependency-injector, injector, or lagom?

These are solid libraries. XIME used to lean on `dependency-injector` for its singleton storage layer, but as of 0.6 the registry is hand-rolled (a plain dict keyed by the class object), so XIME has no third-party DI dependency at all. The difference is scope:

| | dependency-injector / injector | lagom | XIME |
|---|---|---|---|
| Auto-scan packages by directory | No - manual wiring required | No | Yes |
| Startup-time graph validation | No | Partial | Yes - cycles, missing impl, ambiguous bindings |
| Code-first gRPC generation | No | No | Yes |
| Web framework integration | No | No | Yes - controllers, middleware, lifecycle |
| Explicit transaction management | No | No | Yes - `async with self.transaction():` |
| Designed for microservice structure | No | No | Yes |

If you only need DI, use `dependency-injector` or `lagom`. If you want a full convention layer that wires DI, HTTP, gRPC, transactions, and lifecycle together - use XIME.

---

## How It Works

```text
Application Code
      ↓
   XIME Core          ← scanning, DI, lifecycle, config
      ↓
  DI Container        ← core/container, built-in
      ↓
Python Objects
```

XIME's startup pipeline:

1. Load framework configuration (`config/dependency.py`)
2. Load runtime configuration (`resources/application.yml`)
3. Scan declared packages
4. Resolve type hints
5. Build dependency graph
6. **Validate graph** - detect cycles, missing implementations, ambiguous bindings
7. Create singletons
8. Start adapters (FastAPI, gRPC, ...)

If anything is wrong, the app **fails immediately at startup** with a clear error - not later in production.

---

## Installation

```bash
pip install xime
```

Adapters and starters are optional - install only what you need:

```bash
pip install "xime[web]"          # Uvicorn ASGI server
pip install "xime[sqlalchemy]"   # async DB sessions + transactions
pip install "xime[jwt]"          # JWT authentication
pip install "xime[scheduler]"    # cron-style task scheduling
pip install "xime[redis]"        # Redis client + cache backend
pip install "xime[grpc]"         # gRPC adapter (code-first)
pip install "xime[socket]"       # Unix domain socket IPC
pip install "xime[mqtt]"         # MQTT adapter (pub/sub + RPC over MQTT v5)
pip install "xime[s3]"           # S3 / MinIO storage backend
pip install "xime[mail]"         # SMTP email sending (aiosmtplib)
pip install "xime[modbus]"       # Modbus TCP adapter (master + slave)
pip install "xime[opcua]"        # OPC UA adapter (client + server)
pip install "xime[all]"          # everything above
```

> Requires **Python 3.12+**.

---

## Quick Start

**1. Define a controller** - a plain class; methods map to routes.

```python
# app/api/rest/user_controller.py
from xime.adapters.web.routing import get

class UserController:
    prefix = "/users"

    def __init__(self, use_case: GetUserUseCase) -> None:
        self._use_case = use_case

    @get("/{user_id}", response_model=UserResponse)
    async def get_user(self, user_id: int) -> UserResponse:
        return await self._use_case.execute(user_id)
```

**2. Configure dependency injection** - declare which packages to scan and bind interfaces to implementations.

```python
# app/config/dependency.py
from xime import BindingConfig

dependency = BindingConfig()
dependency.scan("application.usecase", "infrastructure.repository")
dependency.bind({UserRepository: JpaUserRepository})
```

**3. Bootstrap the application.**

```python
# app/main.py
from xime import Application
from xime.adapters.web import WebAdapter

app = Application()
app.use(WebAdapter())
app.run()
```

**4. Run it.**

```bash
python -m app.main
```

<details>
<summary><b>Going further - multiple protocols & servers</b></summary>

```python
# REST + gRPC simultaneously
from xime import Application
from xime.adapters.web import WebAdapter
from xime.adapters.grpc import GrpcAdapter

app = Application()
app.use(WebAdapter())
app.use(GrpcAdapter())
app.run()
```

```python
# Multiple servers in one process (public API + internal admin)
from xime import Application
from xime.adapters.web import WebAdapter

app = Application()
app.use(WebAdapter())                              # server_id="default", port from application.yml
app.use(WebAdapter("admin", "127.0.0.1", 8081))   # server_id="admin", explicit host/port
app.run()
```

</details>

---

## 📦 Example Projects

The best way to learn XIME is to read real code. These open-source projects are built on the framework - clone them, run them, and use them as references for structuring your own service:

| Project | What it demonstrates | Good for |
| --- | --- | --- |
| [**xime-shop-example**](https://github.com/nguyen-huu-thang/xime-shop-example) | An e-commerce demo using a straightforward layered architecture. | 🟢 Getting started |
| [**data-service**](https://github.com/nguyen-huu-thang/data-service) | A production-grade microservice: Hexagonal / DDD, gRPC, SQLAlchemy, multi-tenant sharding. The most complete reference. | 🔵 Real-world patterns |
| [**notification-service**](https://github.com/nguyen-huu-thang/notification-service) | An async, IO-bound notification microservice with event-driven patterns. | 🔵 Async & events |
| [**xime-grpc-socket-example**](https://github.com/nguyen-huu-thang/xime-grpc-socket-example) | One app serving gRPC (code-first, dynamic mTLS) and Unix Domain Sockets side by side, with shared `@command` / `@stream` contracts and different security models. | 🟣 Multi-transport |

> New to XIME? Start with **xime-shop-example** for the fundamentals, then study **data-service** for full Hexagonal/DDD patterns at production scale. To see one app speak gRPC and sockets at once, read **xime-grpc-socket-example**.

---

## Features

| Feature | Description |
| --- | --- |
| **Constructor Injection** | Declare dependencies as constructor params - XIME wires them |
| **Directory-Driven DI** | Package location determines component role - no annotations |
| **Interface Binding** | Explicit `Protocol` → implementation mapping, validated at startup |
| **Dynamic Binding** | Bind one `Protocol` to several impls (a tuple) and swap them app-wide at runtime via `Switcher`; off by default, consumers keep their code |
| **Fail Fast** | Circular deps, missing implementations, ambiguous bindings → startup error |
| **Lifecycle Hooks** | `PostConstruct`, `PreDestroy` for managed startup/shutdown |
| **Initialization Order** | `dependency.order([A, B, C])` - control `post_construct()` execution order across independent classes |
| **Multi-Server** | Multiple `WebAdapter` / `GrpcAdapter` / `SocketAdapter` per process, each with its own `server_id` |
| **Event Bus** | Internal pub/sub for decoupled domain events |
| **Request Context** | Per-request data via `ContextVar`, set by adapters |
| **Security Context** | `AuthenticationManager`, `AuthorizationManager` in core |
| **Two-Layer Config** | Framework config (Python) + Runtime config (YAML) |
| **Transaction API** | Explicit `async with self.transaction():` - no hidden AOP; `async with self.read_only():` for reads |
| **Class-Based Controllers** | Controllers are DI singletons, methods map to routes |
| **Code-First gRPC** | Write Python DTOs, XIME generates `.proto` + stubs; field-number stability via lock file; typed server streaming with `@stream` + `yield` (no chunk wrapper, so a Java peer reads the `.proto` and understands it) |
| **gRPC Client SDK** | Generate a typed Pydantic client from `.proto`, inject via DI; deadlines, typed errors, automatic retry |
| **HTTPS** | TLS for the HTTP server via a `server.ssl` block in `application.yml`, including client-certificate verification; misconfiguration stops startup instead of silently serving plain HTTP |
| **Dynamic mTLS** | Certificate rotation without restart for both inbound servers and outbound clients |
| **Peer Identity** | gRPC reads the verified client cert into request context (fail-soft): `current_caller()` gives the CN, `current_peer_sans()` every Subject Alternative Name — raw and uninterpreted, so you match your own scheme (SPIFFE IDs or otherwise) |
| **Socket Adapter** | Unix Domain Socket IPC for same-host Native Engine calls (Linux); `@command` / `@stream` |
| **MQTT Adapter** | Message-driven transport for IoT/embedded: `@subscribe` (pub/sub) + `@rpc` (request/reply over MQTT v5); auto-reconnect; bounded concurrency |
| **Modbus Adapter** | Talk to PLCs directly: declarative device model that decodes registers (endianness, word order, scale), safe read planning, `@poll` / `@on_change`, and slave mode (`@serve` / `@on_write`) |
| **OPC UA Adapter** | Client and server for the modern industrial protocol: node models, real subscriptions (`@on_node_change`), all three security levels |
| **File Storage** | Backend-neutral `StorageService` (local filesystem / S3 / MinIO); bytes + streaming APIs; HTTP Range download and chunked upload helpers |

---

## Starters

Optional modules, similar to `spring-boot-starter-*`:

| Starter | What it provides | Status |
| --- | --- | --- |
| `xime.starters.sqlalchemy` | Async DB session, `SqlAlchemyTransactionManager`, `SqlAlchemyReadOnlyManager` (read-only blocks), `CrudRepository` (built-in CRUD) | ✅ Implemented |
| `xime.starters.jwt` | JWT signing, verification, middleware, **keys rotated by `kid`** | ✅ Implemented |
| `xime.starters.scheduler` | Cron-style task scheduling | ✅ Implemented |
| `xime.starters.cache` | `CacheService` abstraction (backend-neutral) | ✅ Implemented |
| `xime.starters.redis` | Async Redis client + `CacheService` backend | ✅ Implemented |
| `xime.starters.storage` | `StorageService` abstraction (object/blob store) | ✅ Implemented |
| `xime.starters.localfs` | Local filesystem `StorageService` backend | ✅ Implemented |
| `xime.starters.s3` | S3 / MinIO `StorageService` backend (multipart, presigned URL) | ✅ Implemented |
| `xime.starters.mail` | `MailService` abstraction + SMTP backend (async, HTML + text) | ✅ Implemented |

---

## Design Principles

- **Explicit over implicit** - binding, routing, config are always declared, never auto-discovered by magic
- **Constructor injection only** - no `@inject`, no field injection, no `@autowired`
- **No annotations for roles** - `@service`, `@repository`, `@component` do not exist; directory determines role
- **Fail fast** - errors surface at startup, not at runtime
- **Thin wrapper** - XIME does not rewrite FastAPI, SQLAlchemy, or gRPC; it orchestrates them

---

## Project Status

XIME is in **active development**. The following are implemented: core DI (hand-rolled singleton registry, **no third-party DI dependency**) with **dynamic interface binding** (one Protocol → many impls, swapped at runtime), lifecycle, event bus, security context, configuration, JWT starter (audience/issuer enforcement, **keysets addressed by `kid`**, clock leeway, required claims), scheduler starter, SQLAlchemy starter, Cache + Redis starters, **Storage starter** (local filesystem + S3/MinIO) with **HTTP file streaming** (Range download, chunked upload), Web adapter (FastAPI + routing, pure-ASGI request-context & JWT middleware, custom middleware & exception handlers, **DI/config-aware middleware via `Inject`/`FromConfig` markers + first-class `configure_cors`**), gRPC adapter (proto-first + **code-first**, **typed server streaming**, **dynamic mTLS**), **gRPC client SDK** (typed, DI-injected, deadlines + typed errors + automatic retry), **Socket adapter** (Unix Domain Socket IPC), **MQTT adapter** (pub/sub + RPC over MQTT v5), **Modbus adapter** (declarative device model, master polling + slave mode), **OPC UA adapter** (node models, subscriptions, server mode, full security), multi-server support, **WebSocket** (`@ws` routing, handshake authentication over `Sec-WebSocket-Protocol`, close-on-token-expiry), and initialization order (`dependency.order()`).

The core is covered by **1500+ tests**.

See the [CHANGELOG](CHANGELOG.md) for release history.

---

## Documentation

| Document | Description |
| --- | --- |
| [Getting Started](docs/en/getting-started.md) | First app in 5 minutes |
| [Architecture](docs/en/architecture.md) | How XIME is structured internally |
| [Core Concepts](docs/en/core-concepts.md) | DI, interface binding, scopes |
| [Configuration](docs/en/configuration.md) | Framework config + runtime YAML |
| [Routing](docs/en/routing.md) | Class-based controllers, route decorators |
| [Transaction](docs/en/transaction.md) | Explicit transaction management + read-only blocks |
| [Code-First gRPC](docs/en/grpc-codefirst.md) | Generate `.proto` from Python DTOs; field-number stability; `xime grpc generate/check`; dynamic mTLS |
| [gRPC Client SDK](docs/en/grpc-client.md) | Generate a typed client SDK; inject it via DI; deadlines, typed errors, retry, dynamic mTLS |
| [WebSocket](docs/en/websocket.md) | `@ws` routes, token in a subprotocol, authentication before the handler, close on token expiry |
| [Socket Adapter](docs/en/socket-adapter.md) | Unix Domain Socket IPC for same-host Native Engine calls |
| [MQTT Adapter](docs/en/mqtt.md) | Message-driven pub/sub + RPC over MQTT v5 for IoT/embedded |
| [Modbus Adapter](docs/en/modbus.md) | Declarative device models, read planning, polling and slave mode for PLCs |
| [OPC UA Adapter](docs/en/opcua.md) | Node models, subscriptions, server mode, and all three security levels |
| [File Storage](docs/en/file-storage.md) | `StorageService` (local / S3 / MinIO) + HTTP Range download & chunked upload |
| [Starters](docs/en/starters.md) | SQLAlchemy, JWT, Scheduler, Cache, Redis, Storage (local / S3 + HTTP streaming) |
| [Testing](docs/en/testing.md) | DI overrides, fakes, test utilities |
| [Contributing](docs/en/contributing.md) | How to contribute, roadmap |

---

## Contributing

XIME is a solo project that needs community help to grow. There is still ground to cover: multi-process runtime, CLI scaffolding, testing utilities, and more.

**Ways to contribute:**

- Read the [architecture docs](docs/en/architecture.md) to understand the design
- Pick an open area from the [roadmap](docs/en/contributing.md#roadmap)
- Open an issue to discuss a feature or bug
- Submit a pull request

Please read [CONTRIBUTING](docs/en/contributing.md) before opening a PR.

---

## License

Released under the [MIT License](LICENSE).
