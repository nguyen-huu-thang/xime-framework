# Core Concepts

**English** | [Tiếng Việt](../vn/core-concepts.md)

[← Getting Started](getting-started.md) · **2/9 - Core Concepts** · [Configuration →](configuration.md)

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

XIME reads the type hints, resolves each dependency, and creates the object - you never call `UserService(...)` yourself.

**Rules:**

- Every parameter must have a type hint. A missing hint means XIME cannot resolve it, and the class is treated as outside the DI system.
- **A parameter with a default value is OPTIONAL.** When nothing in the container can supply its type, XIME drops the parameter and Python applies the default rather than failing at startup. That is what lets the signature below register normally, even though no DI container ever supplies a `str`:

  ```python
  class ModbusClient:
      def __init__(self, device: str = "default") -> None: ...

  dependency.register(ModbusClient)     # OK, device = "default"
  ```

  Same intent as Spring's `@Autowired(required=false)`. **Fail-fast is preserved where it matters:** a parameter with **no** default and no implementation still stops startup - and that is the overwhelming majority of real dependencies.

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
    "my_service.application.usecase",
    "my_service.application.service",
    "my_service.infrastructure.repository",
    "my_service.infrastructure.client",
)
```

Packages that are **excluded** from DI (classes here are never registered):

- `domain`, `dto`, `entity`, `vo`, `constant`, `exception`

These are excluded because they are data objects, not services - injecting them makes no sense.

### Overriding the exclusion list

Those six segments are a **default, not a law**. They carry DDD vocabulary (`vo` means
*value object*), so a project that names things differently - or one that genuinely keeps
services under a package called `domain` - can redeclare them:

```python
dependency.exclude_segments("domain", "dto", "entity", "legacy")   # replaces the default
dependency.exclude_segments()                                       # scan EVERYTHING
```

| What you do | What the framework does |
|---|---|
| **never call it** | uses the six defaults |
| call it with names | **replaces** the default, does not extend it |
| **call it empty** | excludes nothing at all |

⚠ *Not calling it* and *calling it empty* are **two different things**. To scan everything
you must call it empty explicitly; deleting the call returns you to the defaults.

The filter matches **individual segments of the module path**, so `app.domain.model` is
excluded because one segment is `domain`. It only runs while walking **sub-modules**: point
`scan()` straight at `app.domain` and classes declared in that package's own `__init__.py`
**are still registered** - naming it explicitly is taken as intent.

### ⛔ `@dataclass` is NOT excluded, and that is deliberate

A common question: a DTO written as a `@dataclass` left in a scanned package kills startup,
so why doesn't the framework simply skip every `@dataclass`?

**Because `@dataclass` is a legitimate way to write a service**, not a marker meaning "this
is data":

```python
@dataclass
class RoomService:
    repo: RoomRepository        # injected through the field - this works
```

`@dataclass` generates `__init__(self, repo: RoomRepository)`. That is **exactly**
constructor injection, only written differently.

The framework **can** tell them apart (`dataclasses.is_dataclass()`) but deliberately does
not, for two reasons:

1. **DI's boundary is *can it be built*, not *what did the author mean*.** `Protocol`,
   `ABC` and `BaseModel` are excluded because DI **cannot** build them. A `@dataclass` can
   be built, so excluding it would trade a structural rule for a guess about intent -
   something a framework cannot read.
2. **Excluding it would fail SILENTLY, the opposite of today.** Today a misplaced DTO
   **fails at startup with the class name in the message** - annoying, but visible
   immediately and fixed in a minute. If dataclasses were excluded, a service written as a
   dataclass would **vanish from DI without a word**, and the error would surface later,
   somewhere else, as *"No Implementation Found"* for a class sitting right in front of you.

📌 Measured across 31 Xime codebases (2026-08-25): **197 `@dataclass` declarations inside
scanned packages, 0 of them bean-shaped**. So in practice it is always data - but that is
evidence about *habit*, not about *capability*, and the framework must stay correct for
users outside Xime.

**Three correct ways to handle it, best first:**

| Approach | When |
|---|---|
| Put it in `dto/`, `domain/`, ... | the default - cheapest, nothing to declare |
| `__all__` in `__init__.py` listing only DI-managed classes | mixed package you do not want to split |
| `dependency.exclude_segments(...)` with your own segment | a whole layer is data, e.g. `port` |

### Pydantic `BaseModel` IS excluded, for a completely different reason

`BaseModel` never enters DI, alongside `Protocol` and `ABC` - **even inside a scanned
package, even when every field has a default.**

Not because "it is usually data", but because it **cannot** receive a dependency:

```python
def __init__(self, **data: Any) -> None: ...   # BaseModel's real signature
```

Constructor injection matches dependencies **by parameter name**. `**data` has no parameter
name to match, so there is nowhere to plug a wire in - regardless of what the author wants.

If you need a configuration value object as a singleton, use `dependency.configure()`:

```python
class DomainConfig:
    def policy(self) -> SubscriptionPolicy:
        return SubscriptionPolicy(trial_days=14)

dependency.configure(DomainConfig)
```

---

## 3. Class Registration Rules

A class is registered into the DI container only when **all** of these are true:

1. It is not an `ABC` subclass or a `Protocol` subclass
2. **It is not a Pydantic `BaseModel`** (see section 2 - it has nowhere to receive a dependency)
3. All `__init__` parameters have type hints
4. Its package is in the scan list and not in the exclude list

If a class has a parameter without a type hint, it is silently skipped - not an error. This lets third-party classes live in scanned packages without causing problems.

### Three ways into DI, not just `scan()`

`scan()` is the common path but not the only one, and the other two solve exactly the cases
`scan()` cannot:

| Path | Use when | What the framework does |
|---|---|---|
| `dependency.scan("...")` | the class lives in a conventional package | scans and filters by the rules above |
| `dependency.register(A, B)` | the class lives in an **excluded** package but still needs to be a singleton (domain factory, domain service) | **skips the four rules above** - an explicit declaration is honoured; normal constructor injection still applies, so every `__init__` parameter needs a type hint |
| `dependency.configure(Cls)` | you need **custom construction logic**: reading config, building from a secret, calling a third-party factory | calls every public method that has a return type; each becomes **one singleton of that type** |

`configure()` is the answer to *"I have an object I want to build myself and then put into
DI"*:

```python
class DomainConfig:
    # every public method with a return type -> one singleton
    def policy(self) -> SubscriptionPolicy:
        return SubscriptionPolicy(trial_days=14)          # build it however you like

    def encryption(self, cfg: AppConfig) -> KeyEncryptionService:
        return AesKeyEncryptionService(cfg.secret_key)     # parameters are injected

dependency.configure(DomainConfig)
```

Three constraints on a config class:

- **No constructor parameters** - it must be stateless.
- Method parameters (other than `self`) **are injected by the container**, so they need type hints.
- Each method is called **exactly once**; the result is a singleton like any other class.

⚠ The word *"factory"* is misleading here: this is a **factory method that builds a
singleton**, not a mechanism that produces a new instance per call. Xime has **only one
scope, singleton** - see section 5.

---

## 4. Interface Binding with Protocol

Python's `Protocol` enables structural typing - a class satisfies a Protocol if it has the right methods, without explicit inheritance.

Define an interface:

```python
from typing import Protocol

class UserRepository(Protocol):
    async def find_by_id(self, user_id: int) -> User | None: ...
    async def save(self, user: User) -> None: ...
```

Write the implementation - **no inheritance required**:

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

`Protocol` uses structural typing - Python cannot tell if a class intentionally implements an interface or just happens to have the same methods. Explicit binding makes the architectural decision visible in code. See [Interface Binding](../en/core-concepts.md) for the full rationale.

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
  Hint: add a type annotation - def __init__(self, repository: UserRepository)
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

A class hooks into the application lifecycle by **naming the methods correctly** - no registration call, no decorator. `PostConstruct` and `PreDestroy` are `Protocol`s; the framework checks with `isinstance` at startup/shutdown:

```python
class DatabasePool:
    def __init__(self) -> None:
        self._pool = None

    async def post_construct(self) -> None:   # called after ALL singletons are created
        self._pool = await create_pool()

    async def pre_destroy(self) -> None:      # called before shutdown
        await self._pool.close()
```

Ordering: `post_construct()` runs in topological order (dependencies before dependents); `pre_destroy()` runs in reverse. Two classes with no dependency between them that still need an order declare `dependency.order([A, B])`.

### The rule that matters: clean up as far as you opened

`pre_destroy()` **is only called for instances whose `post_construct()` COMPLETED**. This is deliberate (decided 2026-07-30): running `pre_destroy` on a half-initialised object raises a second error (`AttributeError` on a field that never got set) that buries the original one - exactly when you most need to read the original.

Consequence: when `post_construct()` **fails midway** - a resource was opened, then a later step raised - nothing closes that resource. The clean-up responsibility lives inside `post_construct` itself, the only place that knows how far it got:

```python
async def post_construct(self) -> None:
    self._pool = await create_pool()      # step 1 - opens a resource
    try:
        await self._warm_cache()          # step 2 - may fail
    except Exception:
        await self._pool.close()          # undo step 1, then re-raise
        raise
```

When several resources open in sequence, `AsyncExitStack` beats nested try/except:

```python
from contextlib import AsyncExitStack

async def post_construct(self) -> None:
    async with AsyncExitStack() as stack:
        self._pool = await stack.enter_async_context(create_pool())
        self._mq = await stack.enter_async_context(connect_broker())
        await self._warm_cache()          # fails here -> stack closes both
        self._stack = stack.pop_all()     # success -> keep them open

async def pre_destroy(self) -> None:
    await self._stack.aclose()
```

`pop_all()` is the crux: reaching the end of the block hands ownership to `pre_destroy`; failing midway lets `AsyncExitStack` close everything already opened, in reverse order.

### A third hook: `run_once()` - work done ONCE for the whole cluster

`post_construct()` runs in **every process**. With a single process that is the whole story; with four, *"run at startup"* has **two** meanings that pull in opposite directions:

| | Every process | **Once for the cluster** |
|---|---|---|
| **Runs once, then done** | `post_construct()` | **`run_once()`** |
| **Runs forever** | `Adapter.start()` | a `scaling="singleton"` adapter |

```python
class KeyRefreshJob:
    async def post_construct(self) -> None:      # EVERY process, and must be LIGHT
        self._cache = {}

    async def run_once(self) -> None:            # ONCE for the whole cluster
        await self._refdata.publish(await self._trust.fetch_keys())
```

Same mechanism as the other two hooks: **name the method correctly**, no decorator, nothing to register. The framework runs it on the primary after every `post_construct()` has finished and **before any adapter serves**.

The right place for: migrations, fetching signing keys the first time, consuming a bootstrap certificate ticket. None of those should run four times in a four-process cluster.

⚠ **`run_once()` must be REPEATABLE**: if the primary dies partway, the promoted process runs it again. And it **deliberately has no undo hook** - none of the cases above leave anything to clean up.

⚠ A **single-process** application still runs `run_once()`: it *is* the whole cluster. There is no branch to forget. Details: [Multi-process](multi-process.md).

---

## 9. Event Bus

The internal event bus decouples components that should not directly depend on each other.
`publish()` is **fire and forget** - it schedules every handler as an independent background
task and returns immediately without waiting for them to complete.

```python
from xime.core.event import EventBus, EventHandler

class UserCreatedEvent:
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id

class NotificationHandler:
    async def handle(self, event: UserCreatedEvent) -> None:
        await send_welcome_email(event.user_id)
```

Publish from a use case - the caller is not blocked:

```python
class CreateUserUseCase:
    def __init__(self, bus: EventBus, repository: UserRepository) -> None:
        self._bus = bus
        self._repository = repository

    async def execute(self, command: CreateUserCommand) -> User:
        user = await self._repository.save(User(...))
        await self._bus.publish(UserCreatedEvent(user.id))
        # returns here - handlers run in the background
        return user
```

Multiple handlers for the same event run concurrently. If a handler raises, the exception
is logged and does not affect other handlers or the publisher.

Register handlers explicitly, typically in a `PostConstruct` hook:

```python
event_bus.subscribe(UserCreatedEvent, notification_handler)
event_bus.subscribe(UserCreatedEvent, audit_handler)
```

**Testing** - use `drain()` to wait for all in-flight handlers before asserting:

```python
await use_case.execute(command)
await event_bus.drain()
assert notification_mock.called
```

### The in-flight ceiling, and how to say "never drop this"

`publish()` schedules **one asyncio Task per handler** and returns immediately. Without a ceiling, any user-reachable path that publishes lets a caller multiply tasks by request count. Each pending task also **keeps the event object alive**, so memory grows with **event size**, not with a fixed per-task overhead.

Since 0.7.2 in-flight tasks are capped, **default 10,000**. Past the cap an event is dropped **whole** (never half its handlers) and counted.

#### From 0.8: `publish()` tells you what happened

Up to 0.7.2 `publish()` returned `None` for **all three** situations below, so a caller had no way to tell a dropped event from a scheduled one. That was a known debt, and 0.8 pays it:

```python
from xime.core.event import PublishOutcome

outcome = await self._bus.publish(OrderCreated(order.id))
if outcome is PublishOutcome.DROPPED:
    # The system is losing work - this is backpressure, not a one-off error.
    self._metrics.increment("events_dropped")
```

| Value | Meaning | What the caller should do |
|---|---|---|
| `SCHEDULED` | handlers scheduled as background tasks | nothing |
| `NO_HANDLERS` | **nobody subscribed** to this event type | harmless at runtime, but if you believed someone was listening this is a wiring bug, and this is the only place it shows |
| `DROPPED` | over the cap, the event was dropped **whole** | throttle upstream, raise the cap, or declare `never_drop` |

⚠ **Do not use the value as a boolean** - all three are truthy. Compare explicitly against the member you care about.

✅ **Nothing old breaks**: ignore the return value and `publish()` behaves exactly as before.

That number is a **design decision of the application**, not an environment setting: it follows from how long your handlers run and how large your events are. So it lives in **Python**, beside routing and DI bindings, not in `application.yml`:

```python
# config/event.py
from xime.core.event import configure_event_bus

configure_event_bus(
    max_pending=50_000,                        # light handlers, small events
    never_drop=(AuditEvent, PaymentEvent),     # things you cannot afford to lose
)
```

Two ways to say "do not drop":

| Declaration | Meaning |
|---|---|
| `never_drop=(AuditEvent,)` | **Exempt a few types**; everything else still has a ceiling. Matched by **exact type**, like handler lookup - a subclass does not inherit the exemption |
| `max_pending=None` | **No ceiling at all**, exactly the pre-0.7.2 behaviour. A valid choice, as long as it is a deliberate one |

⚠ `never_drop` **moves** the risk, it does not remove it: a flood of an exempt event still grows without bound, and the bus logs a WARNING saying so once it is past the ceiling. Exempt what you cannot afford to lose, not what you would merely prefer to keep.

To pick the number, observe:

```python
event_bus.dropped            # total events dropped
event_bus.dropped_by_type()  # per type - which event is actually losing
```

The log says *one was just dropped* (throttled, so a flood of events cannot become a flood of log lines); those two say *how many*. Only the second is usable for choosing a ceiling.

⛔ **The caller cannot tell a dropped event from a scheduled one** - both return `None`. This is a known debt against the project's "one value, one meaning" rule, deliberately left for 0.8 because closing it changes a public signature. The practical consequence: **do not use the event bus for anything whose loss you must detect** - either declare it in `never_drop`, or do not route it through the bus.

⚠ Also note the framework never calls `drain()` at shutdown, so in-flight handlers are cut off. Call it from your own `PreDestroy` hook if they must finish.

---

## 10. Request Context

Request-scoped data flows through `ContextVar`, not through function parameters or global state:

```python
from xime.core.context import request_context
```

`request_context` is a key-value store for the **current async context** - one dict per request, holding whatever you put in it (trace id, locale, correlation id, feature flags).

Adapters (middleware) set context at the start of each request. Business code reads it:

```python
class AuditService:
    async def log(self, action: str) -> None:
        rid = request_context.get("request_id")
        await self._repository.save_log(rid, action)
```

Who the caller is travels separately, through `SecurityContext`, not through this key-value store:

```python
from xime.core.security import identity

user_id = identity.get()
```

Because `ContextVar` is async-safe, each concurrent request has its own isolated context. Every `set()` builds a NEW dict rather than mutating in place, so a child task spawned with `asyncio.create_task` keeps its own snapshot and is not emptied when the parent clears its context.

### Peer identity (mTLS)

For gRPC calls over verified mTLS, the framework reads the client certificate's Common Name into the request context and exposes it via a helper:

```python
from xime.core.security import current_caller

caller = current_caller()   # the verified CN, or None when there is no mTLS
```

This is fail-soft: a plaintext or server-only-TLS call leaves `current_caller()` returning `None` and never breaks the request. The framework only provides the mechanism (who called); authorization - what that caller may do - stays in the application. The CN is raw: it may be a service id or an application identity, and the app decides how to interpret it.

---

## 11. Multi-Server Support

A single XIME process can run multiple `WebAdapter` and `GrpcAdapter` instances simultaneously - each on a different port with its own set of controllers or servicers.

```python
# app/main.py
from xime.adapters.grpc import GrpcAdapter
from xime.adapters.web import WebAdapter
from xime.core.bootstrap import Application

import config

app = Application()
app.add_config(config)
app.use(WebAdapter())               # server_id="default"
app.use(WebAdapter("admin"))        # server_id="admin"
app.use(GrpcAdapter())
app.use(GrpcAdapter("internal"))

if __name__ == "__main__":
    app.run()
```

Addresses live in `application.yml`, not in code:

```yaml
process:
  web:
    default: { port: 8086 }
    admin:   { host: 127.0.0.1, port: 8081 }
  grpc:
    default:  { port: 50051 }
    internal: { port: 50052 }
```

⚠ **A single-port application never writes this block** - the flat `server:` /
`grpc.port` keys still work. You only need `process:` for a **second** endpoint.
Details: [Multi-process](multi-process.md).

**Assigning controllers to a server** - declare a `server_id` class variable:

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
- Non-default adapters **must** provide explicit `host` and `port` in the constructor - no config file reading for them.
- Two adapters of the same type with the same `server_id` → `ValueError` at `app.use()`.
- All adapters share the same DI container singletons - no duplication of business objects.
- TLS/mTLS is only supported for the `"default"` gRPC adapter.
- Per-server OpenAPI config: `configure_openapi(config, server_id="admin")`.

---

## 12. Initialization Order (`dependency.order`)

By default, `post_construct()` hooks run in topological dependency order - classes that are depended on first. When two classes have no constructor dependency on each other but one's `post_construct()` must complete before the other's, use `dependency.order()`:

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

[← Getting Started](getting-started.md) · **2/9 - Core Concepts** · [Configuration →](configuration.md)
