# Architecture

**English** | [Tiếng Việt](../vn/architecture.md)

[← Testing](testing.md) · **8/9 - Architecture** · [Contributing →](contributing.md)

---

## Layered Overview

```text
Application Code   ← your business logic, controllers, use cases
      ↓
   XIME Core       ← scanning, DI, lifecycle, config, event, security
      ↓
  DI Container     ← core/container, built-in
      ↓
Python Objects
```

XIME sits between your application code and the DI container. It automates scanning, graph building, and wiring so you never hand-wire singletons or pass dependencies manually. The container is a **hand-rolled singleton registry** (a dict keyed by the class object), so XIME has no third-party DI dependency.

---

## Core Modules

```text
core/
├── bootstrap/    ← Application entry point, startup orchestration
├── container/    ← Package scanning, type resolution, dependency graph, singleton registry, dynamic binding
├── metadata/     ← Type hint utilities
├── config/       ← Two-layer config system
├── lifecycle/    ← PostConstruct / PreDestroy hooks
├── context/      ← Per-request data via ContextVar
├── contract/     ← Shared endpoint contracts for Socket and gRPC code-first
├── security/     ← SecurityContext, AuthenticationManager, AuthorizationManager
├── event/        ← Internal event bus (fire and forget, background tasks)
├── transaction/  ← TransactionManager + ReadOnlyManager (read-only blocks) and their contexts
└── exception/    ← Framework exception hierarchy
```

**Core has no dependency on FastAPI, gRPC, or any protocol library.** It works at the Python object level.

---

## Adapters

Adapters translate between protocols and XIME Core. Each adapter:

1. Receives an incoming message (HTTP request, gRPC call, MQ message)
2. Sets up the request `Context` (user, trace ID, etc.)
3. Calls the appropriate handler (controller, service handler)
4. Tears down context after the call

```text
adapters/
├── web/           ← HTTP + WebSocket via FastAPI (ASGI)
│   ├── openapi/   ← OpenAPI config, security schemes
│   ├── routing/   ← Class-based controller registration
│   ├── middleware/ ← Context middleware
│   └── ws/        ← WebSocket support
├── grpc/          ← gRPC server via grpc.aio, code-first proto generation, TLS/mTLS
└── socket/        ← Unix Domain Socket IPC, frame protocol, peer authentication (Linux)
```

---

## Starters

Optional integration modules, similar to `spring-boot-starter-*`.

```text
starters/
├── sqlalchemy/   ← AsyncSession, transaction + read-only, CrudRepository  ✅ implemented
├── jwt/          ← JWT sign/verify (PyJWT), middleware        ✅ implemented
├── scheduler/    ← Cron-style task runner (APScheduler)      ✅ implemented
├── redis/        ← Redis client                              🔲 planned
└── cache/        ← Cache abstraction                         🔲 planned
```

Starters depend on Core but are not required. They register their components into the DI container just like any other user-defined class.

---

## Startup Pipeline

```text
Application.start()
  │
  ├─ 1. Load BindingConfig     (from config/dependency.py)
  ├─ 2. Load RuntimeConfig     (from resources/application.yml)
  ├─ 3. Scan packages          (PackageScanner)
  ├─ 4. Resolve type hints     (TypeResolver)
  ├─ 5. Build dependency graph (GraphBuilder)
  ├─ 6. Validate graph         (GraphValidator)
  │       ├─ detect cycles
  │       ├─ find missing bindings
  │       └─ validate Protocol implementations
  ├─ 7. Create singletons      (core/container)
  └─ 8. Start adapters         (WebAdapter, GrpcAdapter, ...)
```

Step 6 is the key differentiator - validation happens **before** any singleton is created. A misconfigured application never starts silently.

---

## Dependency Graph

The graph is a directed acyclic graph (DAG) of constructor dependencies.

```text
UserController → GetUserUseCase → UserRepository (Protocol)
                                        ↓ (binding)
                               JpaUserRepository
```

XIME builds this graph by:

1. Inspecting `__init__` signature of each scanned class
2. Reading type hints of each parameter
3. Resolving Protocol → concrete class via the binding registry
4. Checking for cycles

---

## Configuration System

XIME uses a two-layer config model:

| Layer | Who writes it | Format | Purpose |
| --- | --- | --- | --- |
| Framework config | Developer | Python | DI scan, bindings, routing, security |
| Runtime config | Operator | YAML | host, port, DB URL, secrets |

Framework config is imported at startup. Runtime config is loaded from `resources/application.yml` and merged with `resources/application-{env}.yml`. The active env is read from `XIME_ENV` or `APP_ENV`.

---

## Request Context

Each adapter sets up a `ContextVar`-based context at the start of a request:

```python
# In a middleware / request handler
current_user.set(authenticated_user)
request_id.set(generate_id())
```

Business logic reads context passively:

```python
user = current_user.get()
```

Context is automatically isolated per-request because `ContextVar` is async-safe - each asyncio task has its own copy.

---

## Security Model

Security is split between Core and adapters:

- **Core** - `SecurityContext`, `AuthenticationManager`, `AuthorizationManager`, `SecuritySession`
- **Adapters** - HTTP middleware that performs authentication and populates `SecurityContext`

Business logic calls `AuthorizationManager` to check permissions. It never touches HTTP headers or tokens directly.

---

## Transaction Model

Transactions are **explicit** context managers, not hidden AOP proxies:

```python
async with self.transaction():
    await self.repository.save(entity)
```

`TransactionManager` is a Core interface. `SqlAlchemyTransactionManager` (in the SQLAlchemy starter) is the concrete implementation. Business code only depends on the interface.

Read-only use cases use `ReadOnlyManager`, a separate sibling interface rather than a method on `TransactionManager`:

```python
async with self.read_only():
    return await self.repository.find_all()
```

A read-only block never commits. Keeping it a separate interface means reads can be pointed at a replica later with a single `bind` line. Details: [Transaction](transaction.md).

---

## Testing

The `testing/` module provides:

- `FakeTransactionManager` / `FakeReadOnlyManager` - in-memory transaction and read-only block for unit tests
- DI override helpers - replace a singleton with a test double without touching production config

```python
dependency.bind({UserRepository: FakeUserRepository})
```

---

## What XIME Does NOT Do

- Does not implement HTTP routing logic (FastAPI does)
- Does not implement SQL queries (SQLAlchemy does)
- Does not implement JWT cryptography (PyJWT does)
- Does not create a new ORM, HTTP server, or gRPC runtime

XIME orchestrates these tools. It does not replace them.

---

[← Testing](testing.md) · **8/9 - Architecture** · [Contributing →](contributing.md)
