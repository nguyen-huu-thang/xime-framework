# Core Concepts

**English** | [Tiếng Việt](../vn/core-concepts.md)

---

## 1. Constructor Injection

XIME uses constructor injection exclusively. Every dependency is declared as a typed constructor parameter:

```python
class UserService:
    def __init__(
        self,
        repository: UserRepository,
        transaction: TransactionManager,
    ):
        self.repository = repository
        self.transaction = transaction
```

XIME reads the type hints, resolves each dependency, and creates the object — you never call `UserService(...)` yourself.

**Rules:**
- Every parameter must have a type hint. A missing hint means XIME cannot resolve it, and the class is treated as outside the DI system.
- No `@inject`, no `@autowired`, no field injection.

---

## 2. Directory-Driven Registration

Annotation-based discovery (`@Service`, `@Component`) is replaced by directory-based discovery:

| Directory | Role |
|---|---|
| `application/usecase/` | Use case layer |
| `application/service/` | Application service layer |
| `infrastructure/repository/` | Repository layer |
| `infrastructure/client/` | External service clients |

You declare which packages to scan in `config/dependency.py`:

```python
dependency.scan(
    "application.usecase",
    "application.service",
    "infrastructure.repository",
    "infrastructure.client",
)
```

Packages that are **excluded** from DI (classes here are never registered):

- `domain`, `dto`, `entity`, `vo`, `constant`, `exception`

These are excluded because they are data objects, not services — injecting them makes no sense.

---

## 3. Class Registration Rules

A class is registered into the DI container only when **all** of these are true:

1. It is not an `ABC` subclass or a `Protocol` subclass
2. All `__init__` parameters have type hints
3. Its package is in the scan list and not in the exclude list

If a class has a parameter without a type hint, it is silently skipped — not an error. This lets third-party classes live in scanned packages without causing problems.

---

## 4. Interface Binding with Protocol

Python's `Protocol` enables structural typing — a class satisfies a Protocol if it has the right methods, without explicit inheritance.

Define an interface:

```python
from typing import Protocol

class UserRepository(Protocol):
    async def find_by_id(self, user_id: int) -> User | None: ...
    async def save(self, user: User) -> None: ...
```

Write the implementation — **no inheritance required**:

```python
class JpaUserRepository:
    async def find_by_id(self, user_id: int) -> User | None:
        ...
    async def save(self, user: User) -> None:
        ...
```

Declare the binding explicitly in `config/dependency.py`:

```python
dependency.bind({
    UserRepository: JpaUserRepository,
})
```

XIME validates at startup that `JpaUserRepository` implements all methods declared in `UserRepository`. If a method is missing, startup fails:

```
Binding Validation Failed
  Protocol: UserRepository
  Implementation: JpaUserRepository
  Missing methods:
    - save
```

**Why explicit binding?**

`Protocol` uses structural typing — Python cannot tell if a class intentionally implements an interface or just happens to have the same methods. Explicit binding makes the architectural decision visible in code. See [Interface Binding](../en/core-concepts.md) for the full rationale.

---

## 5. Dependency Scopes

| Scope | Description | Default |
|---|---|---|
| `Singleton` | One instance for the entire application lifetime | Yes |
| `Factory` | New instance on every call | No |

All services, use cases, and repositories are singletons by default. Factory scope will be configurable in a future version.

---

## 6. Fail Fast Validation

XIME validates the entire dependency graph before creating any object. Startup fails immediately with a descriptive error for:

**Missing implementation:**
```
No Implementation Found
  Interface: UserRepository
  Hint: add dependency.bind({UserRepository: YourImpl}) in config/dependency.py
```

**Ambiguous implementation** (multiple candidates, no explicit binding):
```
Multiple Implementations Found
  Interface: UserRepository
  Candidates: JpaUserRepository, RedisUserRepository
  Hint: add dependency.bind({UserRepository: <chosen impl>}) in config/dependency.py
```

**Circular dependency:**
```
Circular dependency detected:
  UserService → AuthService → TokenService → UserService
```

**Missing type hint:**
```
Missing Type Hint
  Class: UserService
  Parameter: repository
  Hint: add a type annotation — def __init__(self, repository: UserRepository)
```

---

## 7. Package Scanning and `__init__.py`

By default, scanning a package finds all classes in all submodules. You can restrict which classes are exported using `__all__`:

```python
# application/usecase/__init__.py
__all__ = ["GetUserUseCase", "CreateUserUseCase"]
```

With `__all__` present, only the listed classes are scanned. Without it, everything is scanned.

---

## 8. Lifecycle Hooks

Classes can hook into the application lifecycle:

```python
from xime.lifecycle import PostConstruct, PreDestroy

class DatabasePool:
    def __init__(self) -> None:
        self._pool = None

    async def on_start(self) -> None:   # called after all singletons are created
        self._pool = await create_pool()

    async def on_stop(self) -> None:    # called before shutdown
        await self._pool.close()

PostConstruct.register(DatabasePool, "on_start")
PreDestroy.register(DatabasePool, "on_stop")
```

---

## 9. Event Bus

The internal event bus decouples components that should not directly depend on each other:

```python
from xime.event import EventBus, EventHandler

class UserCreatedEvent:
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id

class NotificationHandler(EventHandler[UserCreatedEvent]):
    async def handle(self, event: UserCreatedEvent) -> None:
        await send_welcome_email(event.user_id)
```

Publish from a use case:

```python
class CreateUserUseCase:
    def __init__(self, bus: EventBus, repository: UserRepository) -> None:
        self._bus = bus
        self._repository = repository

    async def execute(self, command: CreateUserCommand) -> User:
        user = await self._repository.save(User(...))
        await self._bus.publish(UserCreatedEvent(user.id))
        return user
```

---

## 10. Request Context

Request-scoped data flows through `ContextVar`, not through function parameters or global state:

```python
from xime.context import current_user, request_id
```

Adapters (middleware) set context at the start of each request. Business code reads it:

```python
class AuditService:
    async def log(self, action: str) -> None:
        user = current_user.get()
        rid = request_id.get()
        await self._repository.save_log(user.id, rid, action)
```

Because `ContextVar` is async-safe, each concurrent request has its own isolated context.
