# Core Concepts

**English** | [Tiếng Việt](../vn/core-concepts.md)

[← Getting Started](getting-started.md) · **2/9 — Core Concepts** · [Configuration →](configuration.md)

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
| --- | --- |
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

```text
Binding Validation Failed
  Protocol: UserRepository
  Implementation: JpaUserRepository
  Missing methods:
    - save
```

**Why explicit binding?**

`Protocol` uses structural typing — Python cannot tell if a class intentionally implements an interface or just happens to have the same methods. Explicit binding makes the architectural decision visible in code. See [Interface Binding](../en/core-concepts.md) for the full rationale.

### 4.1 Dynamic binding (multiple implementations)

A binding value can be a **tuple** of implementations instead of a single class. The first element is the default. This lets you swap which implementation an interface uses **across the whole application at runtime**, without touching consumer code.

```python
# config/dependency.py
dependency.bind({
    UserRepository: JpaUserRepository,                            # classic 1-to-1
    PaymentGateway: (StripeGateway, PaypalGateway, MockGateway),  # first = default
})
```

The feature is **off by default** and gated by one runtime flag:

```yaml
# resources/application.yml
xime:
  di:
    dynamic-binding: false   # default; set true to enable runtime switching
```

| Binding value | Flag | Behaviour |
| --- | --- | --- |
| single class | any | Exactly as before. |
| tuple | **off** | Uses the **first element**, injected statically just like a 1-to-1 binding; the other impls are never built. Identical to the classic architecture. |
| tuple | **on** | Every impl becomes an eager singleton; consumers receive a **transparent proxy**; a `Switcher` can repoint the interface app-wide. |

**Consumers never change** - in both modes they depend on the Protocol as usual:

```python
class CheckoutService:
    def __init__(self, gateway: PaymentGateway):     # unchanged
        self.gateway = gateway

    async def pay(self, amount: int) -> str:
        return await self.gateway.charge(amount)     # unchanged
```

When the flag is on, inject a `Switcher` to swap implementations at runtime:

```python
from xime.core.container.switcher import Switcher

class AdminService:
    def __init__(self, switcher: Switcher):
        self.switcher = switcher

    def failover(self):
        self.switcher.use(PaymentGateway, PaypalGateway)  # whole app uses Paypal
        self.switcher.reset(PaymentGateway)               # one interface back to default
        self.switcher.reset()                             # every interface back to default
```

**Notes:**

- Switching is **global**: it swaps a shared pointer, so every consumer / request / coroutine sees the new implementation on its next call; a request already in flight is switched mid-way too. There is no request scope.
- Use it for **system-wide, operational** decisions that apply to all requests and happen rarely: provider failover, kill-switch / maintenance, swapping a provider. When the choice depends on **per-request data** (country, tenant, user) and different requests need different impls at the same time, write a small **router** class that receives every impl via DI and picks per call; do not put `if/case` inside each implementation.
- **Fail-fast:** when the flag is on, every impl in a tuple must satisfy the Protocol, or startup fails. The `Switcher` is always injectable; with the flag off, `use()`/`reset()` raise a clear error.
- A 1-element tuple is treated as a plain single binding (nothing to switch).

---

## 5. Dependency Scopes

| Scope | Description | Default |
| --- | --- | --- |
| `Singleton` | One instance for the entire application lifetime | Yes |
| `Factory` | New instance on every call | No |

All services, use cases, and repositories are singletons by default. Factory scope will be configurable in a future version.

---

## 6. Fail Fast Validation

XIME validates the entire dependency graph before creating any object. Startup fails immediately with a descriptive error for:

**Missing implementation:**

```text
No Implementation Found
  Interface: UserRepository
  Hint: add dependency.bind({UserRepository: YourImpl}) in config/dependency.py
```

**Ambiguous implementation** (multiple candidates, no explicit binding):

```text
Multiple Implementations Found
  Interface: UserRepository
  Candidates: JpaUserRepository, RedisUserRepository
  Hint: add dependency.bind({UserRepository: <chosen impl>}) in config/dependency.py
```

**Circular dependency:**

```text
Circular dependency detected:
  UserService → AuthService → TokenService → UserService
```

**Missing type hint:**

```text
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

The internal event bus decouples components that should not directly depend on each other.
`publish()` is **fire and forget** — it schedules every handler as an independent background
task and returns immediately without waiting for them to complete.

```python
from xime.event import EventBus, EventHandler

class UserCreatedEvent:
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id

class NotificationHandler:
    async def handle(self, event: UserCreatedEvent) -> None:
        await send_welcome_email(event.user_id)
```

Publish from a use case — the caller is not blocked:

```python
class CreateUserUseCase:
    def __init__(self, bus: EventBus, repository: UserRepository) -> None:
        self._bus = bus
        self._repository = repository

    async def execute(self, command: CreateUserCommand) -> User:
        user = await self._repository.save(User(...))
        await self._bus.publish(UserCreatedEvent(user.id))
        # returns here — handlers run in the background
        return user
```

Multiple handlers for the same event run concurrently. If a handler raises, the exception
is logged and does not affect other handlers or the publisher.

Register handlers explicitly, typically in a `PostConstruct` hook:

```python
event_bus.subscribe(UserCreatedEvent, notification_handler)
event_bus.subscribe(UserCreatedEvent, audit_handler)
```

**Testing** — use `drain()` to wait for all in-flight handlers before asserting:

```python
await use_case.execute(command)
await event_bus.drain()
assert notification_mock.called
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

### Peer identity (mTLS)

For gRPC calls over verified mTLS, the framework reads the client certificate's Common Name into the request context and exposes it via a helper:

```python
from xime.core.security import current_caller

caller = current_caller()   # the verified CN, or None when there is no mTLS
```

This is fail-soft: a plaintext or server-only-TLS call leaves `current_caller()` returning `None` and never breaks the request. The framework only provides the mechanism (who called); authorization - what that caller may do - stays in the application. The CN is raw: it may be a service id or an application identity, and the app decides how to interpret it.

---

## 11. Multi-Server Support

A single XIME process can run multiple `WebAdapter` and `GrpcAdapter` instances simultaneously — each on a different port with its own set of controllers or servicers.

```python
# app/main.py
from xime import Application
from xime.adapters.web import WebAdapter
from xime.adapters.grpc import GrpcAdapter

app = Application()
app.use(WebAdapter())                               # server_id="default", port from application.yml
app.use(WebAdapter("admin", "127.0.0.1", 8081))    # server_id="admin", explicit host + port
app.use(GrpcAdapter())                              # server_id="default", port from application.yml
app.use(GrpcAdapter("internal", port=50052))        # server_id="internal", explicit port
app.run()
```

**Assigning controllers to a server** — declare a `server_id` class variable:

```python
class PublicController:
    prefix = "/api/v1"
    # no server_id → defaults to "default"

class AdminController:
    prefix = "/admin"
    server_id = "admin"   # only registered on WebAdapter("admin", ...)
```

**Rules:**

- `server_id` defaults to `"default"` when omitted on both adapters and controllers/servicers.
- Non-default adapters **must** provide explicit `host` and `port` in the constructor — no config file reading for them.
- Two adapters of the same type with the same `server_id` → `ValueError` at `app.use()`.
- All adapters share the same DI container singletons — no duplication of business objects.
- TLS/mTLS is only supported for the `"default"` gRPC adapter.
- Per-server OpenAPI config: `configure_openapi(config, server_id="admin")`.

---

## 12. Initialization Order (`dependency.order`)

By default, `post_construct()` hooks run in topological dependency order — classes that are depended on first. When two classes have no constructor dependency on each other but one's `post_construct()` must complete before the other's, use `dependency.order()`:

```python
# app/config/dependency.py
dependency.order(
    [TrustSelfCertificateLoader, GrpcExternalCredentialsProvider],
    [DatabasePool, UserRepository, UserService],
)
```

This is equivalent to `@DependsOn` in Spring Boot, but declared centrally in the config file.

**Syntax:** each positional argument is an ordered list. `[A, B, C]` means:

- `A.post_construct()` completes before `B.post_construct()` starts
- `B.post_construct()` completes before `C.post_construct()` starts

Multiple lists can be passed; the framework merges them into a single ordering graph.

**Fail fast at startup:**

```text
Initialization Order Error
  Classes not found in DI container: UnknownClass
  Every class in dependency.order() must be registered.

Initialization Order Conflict
  A cycle was detected in the combined dependency and order rules:
  ServiceA → ServiceB → ServiceA
```

**What it does NOT affect:** constructor injection order. `dependency.order()` only controls the sequence in which `post_construct()` hooks are called after all singletons are created.

---

[← Getting Started](getting-started.md) · **2/9 — Core Concepts** · [Configuration →](configuration.md)
