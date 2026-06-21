# Contributing

**English** | [Tiếng Việt](../vn/contributing.md)

[← Architecture](architecture.md) · **9/9 — Contributing**

---

Thank you for considering contributing to XIME. This is a solo project and community help is essential for it to grow.

---

## Before You Start

1. Read the [Architecture](architecture.md) doc to understand how XIME is structured
2. Read the [Core Concepts](core-concepts.md) doc to understand the DI model
3. Look through open issues to see what is already being discussed

---

## How to Contribute

### Report a Bug

Open an issue with:

- What you expected
- What actually happened
- A minimal reproducible example (code + error message)

### Suggest a Feature

Open an issue describing:

- The problem you want to solve
- How you imagine the API would look
- Why it fits XIME's philosophy (explicit, fail-fast, no magic)

### Submit a Pull Request

1. Fork the repository
2. Create a branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Add tests for new behavior
5. Run the test suite: `pytest`
6. Open a PR with a clear description of what changed and why

---

## Code Style

- Follow the existing code style (no linter config yet — use common sense)
- All constructor parameters must have type hints
- No `@inject`, `@service`, or annotation-based DI — use constructor injection
- Fail fast: validate at startup, not at runtime
- Write tests for new behavior

---

## Roadmap

Areas that need work, roughly in priority order:

### High Priority

| Area | Description | Difficulty |
| --- | --- | --- |
| **gRPC Adapter** | Class-based gRPC service handlers, similar to controller pattern | Medium |
| **WebSocket support** | WebSocket routing and context management | Medium |
| **Exception → HTTP mapping** | Map domain exceptions to HTTP status codes automatically | Low |
| **CLI scaffolding** | `xime new my-service` to generate project structure | Medium |

### Medium Priority

| Area | Description | Difficulty |
| --- | --- | --- |
| **Redis starter** | Redis client integration with config binding | Low |
| **Cache starter** | Cache abstraction backed by Redis or in-memory | Medium |
| **Request scope** | `Request`-scoped DI instances (one per HTTP request) | High |
| **`configure_controllers()` auto-scan** | Auto-add controller packages to DI scan | Low |
| **Controller scanner `__all__` support** | Respect `__all__` in controller packages | Low |

### Lower Priority

| Area | Description | Difficulty |
| --- | --- | --- |
| **MQ adapter** | RabbitMQ / Kafka integration | High |
| **Savepoints (nested transactions)** | True nested transaction support | High |
| **Decorator-based job registration** | Optional `@job` decorator as an alternative to `SchedulerConfig` | Low |
| **PyPI publish** | Package and publish to PyPI | Low |
| **Documentation improvements** | More examples, tutorials, API reference | Low |

---

## Project Structure

```text
core/           ← No external dependencies except python-dependency-injector
adapters/       ← Protocol-specific integration (FastAPI, gRPC, ...)
starters/       ← Optional integrations (SQLAlchemy, JWT, ...)
testing/        ← Test utilities
cli/            ← Developer CLI tools
tests_temp/     ← Current test suite (will be reorganized)
```

---

## Design Rules — Please Read

These rules are non-negotiable for contributions that touch Core or adapters:

1. **No annotations for component roles** — `@service`, `@repository`, `@component`, `@inject` do not exist in XIME
2. **Constructor injection only** — all dependencies via `__init__` parameters
3. **Explicit over implicit** — if it's configured, it must be explicitly declared somewhere; nothing is auto-discovered by magic
4. **Fail fast** — if startup configuration is wrong, the app must fail at startup with a clear error
5. **Core has no adapter dependencies** — `core/` must not import from `adapters/` or any protocol library (FastAPI, grpc, etc.)
6. **Protocol for interfaces** — use `typing.Protocol`, not `ABC`

---

## Questions?

Open an issue labeled `question`. There are no stupid questions — the design is intentionally different from most Python frameworks and deserves discussion.

---

[← Architecture](architecture.md) · **9/9 — Contributing**
