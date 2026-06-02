# XIME Framework

**English** | [Tiếng Việt](README-vn.md)

> A Python backend framework that brings Spring Boot-style developer experience while respecting Python's philosophy.

---

XIME is not another HTTP framework. It sits **on top of** FastAPI, SQLAlchemy, and gRPC — providing a convention engine, automatic dependency injection, and architectural guardrails so you can focus on business logic instead of wiring.

```python
# Before XIME — wire everything manually
container.user_service = providers.Singleton(
    UserService,
    repository=container.user_repository,
    transaction=container.transaction_manager,
)

# With XIME — just write your class
class UserService:
    def __init__(
        self,
        repository: UserRepository,
        transaction: TransactionManager,
    ):
        self.repository = repository
        self.transaction = transaction
```

XIME reads your type hints, scans your packages, builds the dependency graph, validates it at startup, and wires everything together — automatically.

---

## Why XIME?

Python has excellent libraries for HTTP, databases, and serialization. What it lacks is a **convention layer** that:

- Automatically discovers and wires dependencies from constructor type hints
- Enforces architectural boundaries through directory structure
- Validates the dependency graph at startup — not at runtime when a user hits an endpoint
- Provides a consistent structure for Clean Architecture / DDD / Modular Monolith projects

XIME fills that gap. It does not replace FastAPI or SQLAlchemy — it makes them easier to use at scale.

---

## How It Works

```
Application Code
      ↓
   XIME Core          ← scanning, DI, lifecycle, config
      ↓
Dependency Injector   ← runtime DI engine
      ↓
Python Objects
```

XIME's startup pipeline:

1. Load framework configuration (`config/dependency.py`)
2. Load runtime configuration (`resources/application.yml`)
3. Scan declared packages
4. Resolve type hints
5. Build dependency graph
6. **Validate graph** — detect cycles, missing implementations, ambiguous bindings
7. Create singletons
8. Start adapters (FastAPI, gRPC, ...)

If anything is wrong, the app **fails immediately at startup** with a clear error — not later in production.

---

## Quick Start

```python
# app/main.py — REST only
from xime import Application
from xime.adapters.web import WebAdapter

app = Application()
app.use(WebAdapter())
app.run()
```

```python
# app/main.py — REST + gRPC simultaneously
from xime import Application
from xime.adapters.web import WebAdapter
from xime.adapters.grpc import GrpcAdapter

app = Application()
app.use(WebAdapter())
app.use(GrpcAdapter())
app.run()
```

```python
# app/config/dependency.py
from xime import BindingConfig

dependency = BindingConfig()
dependency.scan("application.usecase", "infrastructure.repository")
dependency.bind({UserRepository: JpaUserRepository})
```

```python
# app/api/rest/user_controller.py
from xime.adapters.web.routing import get, post

class UserController:
    prefix = "/users"

    def __init__(self, use_case: GetUserUseCase) -> None:
        self._use_case = use_case

    @get("/{user_id}", response_model=UserResponse)
    async def get_user(self, user_id: int) -> UserResponse:
        return await self._use_case.execute(user_id)
```

```python
# app/main.py
from xime import Application
from xime.adapters.web import WebAdapter

app = Application()
app.use(WebAdapter())
app.run()
```

```bash
python app/main.py
```

---

## Features

| Feature | Description |
|---|---|
| **Constructor Injection** | Declare dependencies as constructor params — XIME wires them |
| **Directory-Driven DI** | Package location determines component role — no annotations |
| **Interface Binding** | Explicit `Protocol` → implementation mapping, validated at startup |
| **Fail Fast** | Circular deps, missing implementations, ambiguous bindings → startup error |
| **Lifecycle Hooks** | `PostConstruct`, `PreDestroy` for managed startup/shutdown |
| **Event Bus** | Internal pub/sub for decoupled domain events |
| **Request Context** | Per-request data via `ContextVar`, set by adapters |
| **Security Context** | `AuthenticationManager`, `AuthorizationManager` in core |
| **Two-Layer Config** | Framework config (Python) + Runtime config (YAML) |
| **Transaction API** | Explicit `async with self.transaction():` — no hidden AOP |
| **Class-Based Controllers** | Controllers are DI singletons, methods map to routes |

---

## Starters

Optional modules, similar to `spring-boot-starter-*`:

| Starter | What it provides |
|---|---|
| `xime.starters.sqlalchemy` | Async DB session, `SqlAlchemyTransactionManager` |
| `xime.starters.jwt` | JWT signing, verification, middleware |
| `xime.starters.scheduler` | Cron-style task scheduling |
| `xime.starters.redis` | Redis client integration |
| `xime.starters.cache` | Cache abstraction layer |

---

## Design Principles

- **Explicit over implicit** — binding, routing, config are always declared, never auto-discovered by magic
- **Constructor injection only** — no `@inject`, no field injection, no `@autowired`
- **No annotations for roles** — `@service`, `@repository`, `@component` do not exist; directory determines role
- **Fail fast** — errors surface at startup, not at runtime
- **Thin wrapper** — XIME does not rewrite FastAPI, SQLAlchemy, or gRPC; it orchestrates them

---

## Project Status

XIME is in **active development**. Core DI, lifecycle, event bus, security context, configuration, JWT starter, scheduler starter, and the Web adapter routing layer are implemented. The framework is not yet published to PyPI.

---

## Contributing

XIME is a solo project that needs community help to grow. There is a lot of ground to cover: gRPC adapter, WebSocket support, Redis/Cache starters, CLI scaffolding, documentation, testing utilities, and more.

**Ways to contribute:**

- Read the [architecture docs](docs/en/architecture.md) to understand the design
- Pick an open area from the [roadmap](docs/en/contributing.md#roadmap)
- Open an issue to discuss a feature or bug
- Submit a pull request

Please read [CONTRIBUTING](docs/en/contributing.md) before opening a PR.

---

## Documentation

| Document | Description |
|---|---|
| [Getting Started](docs/en/getting-started.md) | First app in 5 minutes |
| [Architecture](docs/en/architecture.md) | How XIME is structured internally |
| [Core Concepts](docs/en/core-concepts.md) | DI, interface binding, scopes |
| [Configuration](docs/en/configuration.md) | Framework config + runtime YAML |
| [Routing](docs/en/routing.md) | Class-based controllers, route decorators |
| [Transaction](docs/en/transaction.md) | Explicit transaction management |
| [Starters](docs/en/starters.md) | SQLAlchemy, JWT, Scheduler, Redis |
| [Testing](docs/en/testing.md) | DI overrides, fakes, test utilities |
| [Contributing](docs/en/contributing.md) | How to contribute, roadmap |

---

## License

MIT
