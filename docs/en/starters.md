# Starters

**English** | [Tiếng Việt](../vn/starters.md)

[← Transaction](transaction.md) · **6/9 - Starters** · [Testing →](testing.md)

---

Starters are optional integration modules, similar to `spring-boot-starter-*` in Spring Boot. Each starter provides a ready-to-use integration with a specific technology. Use only what you need.

---

## SQLAlchemy Starter

`xime.starters.sqlalchemy`

Provides async database sessions, the `SqlAlchemyTransactionManager` and the
`SqlAlchemyReadOnlyManager` (read-only blocks).

### Setup

```python
# config/dependency.py
from xime.core.transaction import ReadOnlyManager, TransactionManager
from xime.starters.sqlalchemy import (
    SqlAlchemyReadOnlyManager,
    SqlAlchemyTransactionManager,
)

dependency.bind({
    TransactionManager: SqlAlchemyTransactionManager,
    ReadOnlyManager: SqlAlchemyReadOnlyManager,   # optional, for read-only use cases
})
```

> `ReadOnlyManager` is optional - skip the binding and everything behaves as
> before. See the "Read-only Blocks" section in [Transaction](transaction.md).

```yaml
# resources/application.yml
database:
  url: postgresql+asyncpg://user:pass@localhost/mydb
  pool_size: 10
  max_overflow: 20
```

### Usage

```python
from sqlalchemy.ext.asyncio import AsyncSession
from xime.core.transaction import TransactionManager

class UserRepository:
    def __init__(
        self,
        session: AsyncSession,
        transaction: TransactionManager,
    ) -> None:
        self._session = session
        self._transaction = transaction

    async def find_by_id(self, user_id: int) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        return result.scalar_one_or_none()
```

Transaction is managed by the use case layer, not the repository.

### Built-in CRUD - `CrudRepository[T]`

Instead of every project re-writing the same base repository, the starter ships
`CrudRepository[T]` - similar to Spring Data's `JpaRepository`/`CrudRepository`.
A concrete repository only declares its `model` and adds any custom queries:

```python
from sqlalchemy import select
from xime.starters.sqlalchemy import CrudRepository

class CategoryRepository(CrudRepository[Category]):
    model = Category

    # Custom queries via self.session
    async def find_by_slug(self, slug: str) -> Category | None:
        result = await self.session.execute(
            select(Category).where(Category.slug == slug)
        )
        return result.scalar_one_or_none()
```

Provided methods:

| Method | Description |
| --- | --- |
| `find(id_)` | Get by primary key, returns `None` if absent |
| `find_or_fail(id_)` | Like `find` but raises `EntityNotFoundError` when absent |
| `find_all()` | Return every row of the model |
| `exists(id_)` | `True`/`False` for the given primary key |
| `count()` | Total number of rows |
| `save(entity)` | Add/update then `flush` (entity gets its generated keys) |
| `save_all(entities)` | Add several entities in one `flush`, returns the list |
| `delete(entity)` | Delete then `flush` |

Every method reads the active session via `AsyncSessionFactory`, so they **must be
called inside** `async with self.transaction():` (writes) or
`async with self.read_only():` (reads) - the block is opened by the use case layer:

```python
class CategoryService:
    def __init__(
        self,
        transaction: TransactionManager,
        categories: CategoryRepository,
    ) -> None:
        self.transaction = transaction
        self.categories = categories

    async def rename(self, category_id: int, name: str) -> None:
        async with self.transaction():
            category = await self.categories.find_or_fail(category_id)
            category.name = name
            await self.categories.save(category)
```

> `CrudRepository` declares `model` as an abstract property, so **the base class
> itself is abstract** - the DI scanner skips it; only concrete subclasses (with
> `model` set) become singletons. No spurious singletons, no extra registration.

---

## JWT Starter

`xime.starters.jwt`

Provides JWT token signing, verification and HTTP request-authentication middleware.

### Setup

```python
# config/jwt.py
import os
from xime.starters.jwt import configure_jwt, JwtMiddlewareConfig, KeyContext

configure_jwt(JwtMiddlewareConfig(
    key_context=KeyContext(
        algorithm="RS256",
        public_key_pem=os.environ["JWT_PUBLIC_KEY"],   # verifying needs only the PUBLIC key
    ),
    identity_claim="sub",
    audience="data-service",
    issuer="https://identity.internal",
    public_paths=["/auth/login", "/auth/refresh", "/health"],
    algorithms=["RS256"],          # allow-list: refuse keys claiming anything else
    leeway=30,                     # seconds of clock tolerance for exp / nbf / iat
    require=["exp"],               # a token with no exp never expires - forbid it
))
```

`WebAdapter` reads this registration while building the app and attaches the middleware itself - there is no second function to call. Skip `configure_jwt` and no middleware is attached.

`KeyContext` states the algorithm and key material **explicitly**; nothing is inferred from the key:

| Algorithm family | Field to set |
| --- | --- |
| HMAC (`HS256`...) | `secret` |
| RSA / EC / EdDSA (`RS256`, `ES256`, `EdDSA`...) | `private_key_pem` to sign, `public_key_pem` to verify |

**Set `audience`.** Left unset, a token minted for a different service but signed with the same key is still accepted.

**Set `require=["exp"]`.** `exp` is only checked when the claim is present, so a token issued without one is valid forever.

**`public_paths` is matched exactly**, not by prefix. Listing `/docs` does not open `/docs/oauth2-redirect`; only a trailing slash is ignored.

### Keys that rotate - `JwtKeyProvider`

A single static key cannot survive rotation: while an issuer switches keys, tokens signed by the old one are still valid and tokens signed by the new one are already arriving. `kid` (RFC 7515 §4.1.4) says which key signed a token, and a provider turns that into candidate keys.

```python
# config/jwt.py
from collections.abc import Sequence
from xime.starters.jwt import configure_jwt, JwtMiddlewareConfig, KeyContext

class JwksKeyProvider:
    def __init__(self) -> None:
        self._by_kid: dict[str, KeyContext] = {}

    async def load(self) -> None:            # your refresh, on your schedule
        for entry in await fetch_jwks():
            self._by_kid[entry.kid] = KeyContext(
                algorithm=entry.alg, public_key_pem=entry.pem, key_id=entry.kid,
            )

    def keys(self, kid: str | None) -> Sequence[KeyContext]:
        found = self._by_kid.get(kid) if kid else None
        return (found,) if found else ()

configure_jwt(
    JwtMiddlewareConfig(audience="data-service", require=["exp"]),
    key_provider=JwksKeyProvider,          # a CLASS, resolved from the DI container
)
```

`keys()` must be an **in-memory read, never a network call** - it runs on every authenticated request. The framework never fetches, never schedules and never caches: keeping the keys fresh is entirely yours, exactly as with `configure_grpc_tls(provider=...)`. Returning an empty sequence means "I do not know this kid" and the request is rejected with 401.

Supply **exactly one** key source. `key_context` alone is a single static key; `key_provider` alone is a keyset addressed by `kid`. Neither, or both, fails at start-up - refusing "neither" on purpose, because the alternative is an application that boots with no authentication and reports itself healthy while every endpoint is open.

### Signing tokens

```python
from xime.starters.jwt import JwtTokenSigner, KeyContext

class AuthUseCase:
    def __init__(self, signer: JwtTokenSigner) -> None:
        self._signer = signer
        self._key = KeyContext(
            algorithm="RS256",
            private_key_pem=os.environ["JWT_PRIVATE_KEY"],
            key_id="key-2025",
        )

    async def login(self, credentials: LoginCommand) -> str:
        user = await self._authenticate(credentials)
        return self._signer.sign(
            {
                "sub": str(user.id),
                "aud": "data-service",
                "iss": "https://identity.internal",
                "exp": datetime.now(UTC) + timedelta(minutes=30),
            },
            self._key,
        )
```

**You** build the payload in full - the framework adds no claims of its own, not even `exp`.

`KeyContext.key_id` becomes the `kid` header. Signing without one is legal, but it is a decision rather than a detail: a token that names no key cannot be routed to one, so no verifier can hold two keys at once for it, so you can never rotate without a flag day.

Extra JOSE headers go through `headers=`, e.g. `headers={"typ": "at+jwt"}` for an RFC 9068 access token. Three names are refused rather than merged: `alg` (PyJWT lets a header value override the `algorithm` argument, so it would silently contradict `KeyContext.algorithm`), `b64` (switches PyJWT into detached-payload mode) and `kid` (it must name the key that actually signed, and `KeyContext.key_id` is the one place that knows which).

```python
# config/dependency.py
dependency.scan("xime.starters.jwt")     # registers PyJwtTokenSigner / PyJwtTokenVerifier
```

### Verifying tokens

```python
from xime.starters.jwt import JwtTokenVerifier, KeyContext

class TokenUseCase:
    def __init__(self, verifier: JwtTokenVerifier) -> None:
        self._verifier = verifier
        self._key = KeyContext(algorithm="RS256", public_key_pem=os.environ["JWT_PUBLIC_KEY"])

    async def verify(self, token: str) -> dict:
        return self._verifier.verify(
            token, self._key, audience="data-service", issuer="https://identity.internal"
        )
```

An expired token, a bad signature, a mismatched `aud`/`iss`, a missing required claim or an algorithm outside `algorithms` all raise `AuthenticationException`. `verify()` also takes `algorithms=`, `leeway=` and `require=`, with the same meanings as in `JwtMiddlewareConfig`.

### JWT middleware

The middleware is attached by `configure_jwt(...)` above. It extracts the `Authorization: Bearer <token>` header, verifies it, fills `SecurityContext`, and puts every verified claim into the request context:

```python
from xime.core.context import request_context
from xime.core.security import identity
from xime.starters.jwt._middleware import JWT_CLAIMS

user_id = identity.get()                    # the identity_claim (default "sub")
claims  = request_context.get(JWT_CLAIMS)   # every verified claim
```

Paths listed in `public_paths` bypass authentication entirely. **Matching is exact, not by prefix**: listing `/docs` leaves `/docs/oauth2-redirect` protected. With JWT on, list both `/docs` and `/openapi.json` to keep Swagger reachable.

**To open a whole branch**, end the entry with `/*`: `/api/v1/parts/*` opens `/api/v1/parts` and everything under it. Matching is by path **segment**, so it never reaches `/api/v1/partsecret` or `/api/v1/parts-admin` - that is exactly the hole a bare `startswith` opens, and why the framework matches by segment.

⚠ A `*` in **any other position** (`/api/*/parts`, `/api/**`) is a **start-up error**, not an ignored entry. An ignored one matches nothing, so the author reads their config as a pattern that is silently not one. `/*` is refused with its own message: it is not a configuration of the middleware but the absence of it.

The same list also governs `@ws` routes and the padlock in Swagger - **one matching rule, one source** - so `/*` opens the same branch in all three places.

> ### ⛔ A public path never looks at the token, even when the client sends one
>
> On a path listed in `public_paths` the middleware returns **before** it touches the
> `Authorization` header. The handler always sees `identity = None`, even when the caller
> is signed in and sent a perfectly good token. This is **deliberate and settled**, not a
> gap waiting to be filled.
>
> The question this raises: *"my product page is public, but a signed-in staff member
> opening it should also see their own drafts - how?"*
>
> **Call two endpoints, not one.** A web page talks to the server through many APIs, not
> one: fetch the part everybody may see from the public path, and the signed-in user's
> own data from an ordinary **authenticated** path. No endpoint has to carry two modes,
> and the decision of *what to show to whom* stays where it belongs - in the frontend.
>
> **An expired token is the frontend's job too, not the middleware's.** The browser is
> the only party that knows how long its token has left, so it must fetch a new access
> token **before** the old one expires, and rotate the refresh token as soon as a page
> loads with it near expiry. Both dead means signed out - that is the correct outcome,
> not a bug to fix.
>
> ⚠ This assumes a **dynamic frontend**. A static HTML page cannot know whether it is
> signed in, and that is an accepted limit.


### The start-up log line about authentication - and what it does NOT say

Every web adapter prints exactly one `INFO` line at start-up, stating what the framework knows about authentication on that server:

```text
web default: JWT middleware active (aud=clinic, 1 public path(s), 31 HTTP route(s))
web default: configure_jwt() not called - 3 custom middleware installed, 31 HTTP route(s)
web default: configure_jwt() not called - no middleware installed, 31 HTTP route(s)
```

It exists because an application that protects its data and one that serves every route to anybody used to produce **identical** start-up logs - a `diff` showed zero differing lines, both saying *"startup complete"*. Putting `configure_jwt()` behind an `if` drops you back into the fail-open shape, and until this release nothing said so.

> ### ⛔ The second line does NOT say your application lacks authentication
>
> This is the easiest line to misread, so plainly: `configure_jwt() not called` is a
> **measurement**, not a **conclusion**. The framework knows exactly one fact - whether
> that function was called - and it stops there.
>
> Installing your own authentication middleware through `configure_middleware(...)` is a
> **legitimate and common** way to do it: when the application fetches keys from its own
> service, or applies authorisation rules the framework has no business knowing. Those
> applications get the second line, and their requests without a token still return `401`
> exactly as they should.
>
> That is why the middleware count is **printed but never interpreted**.
> `configure_middleware` is also how compression, logging and request ids get installed,
> so inferring *"this application is authenticated"* from a non-zero count would be right
> by accident. The reader knows what their application installs; the framework does not.
>
> **The shape worth stopping at is the third line** - `configure_jwt()` not called **and**
> no middleware at all. There, nothing is in front of anyone.

⛔ **It is `INFO`, deliberately not a warning.** A fully public service is legitimate and not rare, and the framework cannot tell `/healthz` from `/api/v1/records/{id}`. Warning there cries wolf at every start-up of an application doing nothing wrong, and **a probe that cries wolf is a probe someone turns off** - at which point the genuinely fail-open application also prints a line nobody reads any more.

📌 The wording was not free. The first version said *"no JWT middleware - N HTTP route(s) open to anyone"*: it measured **one** fact and printed **two** conclusions it had no evidence for. Across the 23 applications that reported back, that sentence was wrong every single time it printed. The current wording is the result of narrowing the claim down to what is actually measured.

The route count measures the **application's API surface**: `/docs`, `/openapi.json` and `/healthz` declare `include_in_schema=False` and are not counted. They are open too, but a number the author cannot map back to their own code tells them nothing.

> **Needs the extra:** `pip install "xime[jwt]"`. Without it, calling `configure_jwt` makes the app **fail at startup** with the command to run, rather than waiting for the first request carrying a token.

---

## Scheduler Starter

`xime.starters.scheduler`

Provides cron-style and fixed-interval periodic task scheduling (backed by APScheduler). Install with `pip install "xime[scheduler]"`.

### Defining a Job

A job is a class that implements the `ScheduledJob` protocol - a single `async def run(self) -> None` method. Job classes are DI singletons, so they receive their dependencies through the constructor like any other class:

```python
class DailyReportJob:
    def __init__(self, report_service: ReportService) -> None:
        self._service = report_service

    async def run(self) -> None:
        await self._service.generate_and_send()

class CacheSyncJob:
    def __init__(self, cache_service: CacheService) -> None:
        self._service = cache_service

    async def run(self) -> None:
        await self._service.sync()
```

### Setup

Register jobs by passing a `SchedulerConfig` to `configure_scheduler()`. Use `CronJob` for a 5-field cron expression and `IntervalJob` for a fixed interval:

```python
# config/scheduler.py
from xime.starters.scheduler import (
    configure_scheduler,
    SchedulerConfig,
    CronJob,
    IntervalJob,
)

configure_scheduler(SchedulerConfig(
    jobs=[
        CronJob(job_class=DailyReportJob, cron="0 8 * * *"),   # every day at 08:00
        IntervalJob(job_class=CacheSyncJob, seconds=60),        # every 60 seconds
    ],
    timezone="Asia/Ho_Chi_Minh",   # optional, default "UTC"
))
```

`CronJob` and `IntervalJob` accept an optional `id` (defaults to the class name). `IntervalJob` combines `hours` / `minutes` / `seconds`; a zero interval is rejected at startup (fail-fast). The scheduler starts after all singletons are constructed and stops gracefully on shutdown, waiting for any in-flight job to finish.

### ⛔ A job runs ONCE for the whole cluster, not once per process

When the application runs several processes (`share_load()`), the scheduler runs **on the primary process only**. The other processes keep the adapter in `standby` and never tick. This is the **design**, not a temporary limitation, and no configuration key changes it.

Why: nearly every real job touches something **shared** - a table in the database, an email to a customer, a sync cursor. Running it four times there is not four times faster, it is four emails and a cursor advanced four notches. That is the *"running twice is WRONG"* class, and it fails **silently**: no exception, no failing test, just a customer receiving the same message four times.

| | Runs once, then done | Runs forever |
|---|---|---|
| **On every process** | `post_construct()` | adapter with `scaling="replicated"` |
| **Once for the cluster** | `run_once()` | **the scheduler** |

### "But my job needs to run on every process"

Before looking for a way, run this test - it rules out almost everything:

> **Does my job read or write something only THIS process has, or something every process can reach?**

If every process can reach it, the primary alone is enough and running it anywhere else only costs more. If only this process has it, then the real question is not *"how do I run a job on every process"* but *"why is my business data sitting in one process's memory"* - that is what needs fixing, with [`RefData`](refdata.md) or [`Store`](store.md).

Auditing what is left, exactly two kinds of work genuinely have to run per process, and **neither is business logic**:

| Kind | Why it lives outside the scheduler |
|---|---|
| **Sampling this process's own metrics** (RSS, requests served, queue depth) | The primary cannot see another process's counters. But the cluster shares **one socket**, so a scrape lands on a random process - **without aggregation the number is meaningless no matter how many schedulers you run**. The answer is to collect through [`ProcessLink`](process-link.md) and push once, not to duplicate the job |
| **A device one process exclusively holds** (Modbus, OPC UA, a subset of MQTT topics) | This is genuine business logic, but it belongs to a `sharded` adapter and has its own mechanism (`@poll`, `@on_change` run once **per entity**). It does not go through the scheduler |

And if you really do need a periodic loop on every process - sampling your own resources, say - **do not wait for the framework to unlock anything**. That shape is already writable today and costs nothing:

```python
import asyncio
import contextlib

from xime.core.bootstrap.adapter import Adapter

class ResourceSampler(Adapter, scaling="replicated"):
    adapter_kind = "sampler"

    def __init__(self) -> None:
        self.adapter_id = "default"
        self._stopped = asyncio.Event()

    async def start(self, app) -> None: ...

    async def serve(self) -> None:
        while not self._stopped.is_set():
            await self._sample()          # touches only this process's counters
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stopped.wait(), timeout=15)

    async def stop(self) -> None:
        self._stopped.set()

app.use(ResourceSampler())
```

That is exactly what `SchedulerAdapter` already is, differing by one `scaling` argument and by where it lives.

---

## Three places to keep shared state - which one

Since 0.8 the framework offers three things that look alike. They **do not
replace each other**:

| | `RefData` | `Store` (LMDB) | `CacheService` (Redis) |
|---|---|---|---|
| Scope | **one machine** (shared memory) | **one machine** (local file) | **several machines** |
| Data | has a durable source, **replaced wholesale** | has **no** durable source | anything |
| Who writes | **primary only** | every process | every process, every machine |
| Examples | JWT keys, app directory | rate limits, passkey challenges, replay protection | anything two machines must both see |

⭐⭐ **The line, and it is about MECHANISM rather than taste:** `RefData`,
`Store` and `ProcessLink` are built on shared memory and local files, so they stop
at a machine boundary - **and a container is a machine**. `CacheService` is where
the framework serves the **several machines** case: k8s, `docker compose scale`,
several VPS behind a load balancer.

> **`RefData` / `Store` are the fast path within ONE machine. `CacheService` is the
> shared path across MANY.** Neither is an exception to the other.

⚠ Do not read `Store` as a replacement for Redis. Run three pods and each pod has
**its own store** - `Store` is not broken there, its scope is exactly what it says.

### A concrete example: `Store` closes one layer of a hole

A login rate limit kept in process memory has its threshold **multiplied by the
number of processes** - four processes give an attacker four times the budget.
`Store` fixes precisely that: the whole cluster on **one machine** shares one
table.

⚠ But run **two machines** behind a load balancer and the threshold is again
**multiplied by the number of machines**. The same failure, just smaller. And
sharding does not fix it: shards are cut by `org_id`, while a rate limit is keyed
by IP or username - a different axis, and someone who cannot log in yet has no
`org_id` at all.

> **The line: everything the framework provides itself (`RefData`, `Store`,
> `ProcessLink`) is ONE MACHINE, always. Something several machines must see is
> the application's own choice, and it goes through `CacheService`.**

Three more things `Store` cannot do, so you do not have to rediscover them: a
**distributed lock** across machines, **pub/sub** (LMDB has no equivalent), and
data larger than one machine's `total_max`.

⛔ The other way round, do not reach for Redis where `Store` would do: a network
round trip per rate-limit read is a real price for something already sitting in
RAM on the same machine.

---

## Cache Starter

`xime.starters.cache`

Defines `CacheService`, a backend-neutral key/value cache contract (a `Protocol`). Business code depends on `CacheService`; the concrete backend (e.g. Redis) is bound explicitly in `config/dependency.py`, so the implementation can be swapped without touching business code.

`CacheService` deals in raw `bytes` by design - the framework does not impose a serialization policy. Callers encode/decode (JSON, pickle, msgpack, plain UTF-8) as their domain requires. TTL is expressed in whole seconds; `None` means the entry never expires.

```python
from typing import Protocol

class CacheService(Protocol):
    async def get(self, key: str) -> bytes | None: ...
    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...
```

### Usage

```python
from xime.starters.cache import CacheService

class TokenService:
    def __init__(self, cache: CacheService) -> None:
        self._cache = cache

    async def remember(self, token: str, user_id: int) -> None:
        await self._cache.set(f"token:{token}", str(user_id).encode(), ttl=3600)

    async def lookup(self, token: str) -> int | None:
        raw = await self._cache.get(f"token:{token}")
        return int(raw) if raw is not None else None
```

---

## Redis Starter

`xime.starters.redis`

Provides an async Redis client (`RedisClientProvider`) and `RedisCacheService`, a Redis-backed implementation of `CacheService`. Install with `pip install "xime[redis]"`.

### Setup

```python
# config/dependency.py
from xime.starters.cache import CacheService
from xime.starters.redis import RedisCacheService

dependency.scan("xime.starters.redis")
dependency.bind({
    CacheService: RedisCacheService,
})
```

```yaml
# resources/application.yml
redis:
  url: redis://localhost:6379/0
  max_connections: 10   # optional, default 10
```

`RedisClientProvider` reads `redis.url` (required - missing it fails fast at startup) and `redis.max_connections`, owns the connection pool, and closes it on `PreDestroy` during shutdown. The `redis` package is imported lazily, so the starter module stays importable even when the extra is not installed - only services that scan this package need it.

### Using a different backend

Because business code depends only on `CacheService`, swapping backends is a one-line binding change:

```python
# Production: Redis
dependency.bind({ CacheService: RedisCacheService })

# Testing: an in-memory fake that satisfies the CacheService Protocol
dependency.bind({ CacheService: InMemoryCacheService })
```

---

## Storage Starter

`xime.starters.storage`

Defines `StorageService`, a backend-neutral object/blob store contract (a `Protocol`). Business code depends on `StorageService`; the concrete backend (local filesystem or S3/MinIO) is bound explicitly in `config/dependency.py`. Like `CacheService`, objects are raw `bytes` (or raw byte streams) - the framework imposes no naming, authorization, or content-type policy.

It offers two access shapes:

- `put` / `get` - whole-object bytes, convenient for small objects.
- `put_stream` / `open_stream` - async byte streams for large objects that must not be buffered fully in memory (`open_stream` takes `offset`/`length` for HTTP Range).

Plus `delete`, `exists`, `stat` (size/content-type/etag) and `url` (presigned URL where supported). Keys are backend-relative; **every backend** rejects empty, absolute, and `..` (traversal) keys identically.

### Local filesystem backend - `xime.starters.localfs`

```python
# config/dependency.py
from xime.starters.storage import StorageService
from xime.starters.localfs import LocalFileStorage

dependency.scan("xime.starters.localfs")
dependency.bind({ StorageService: LocalFileStorage })
```

```yaml
# resources/application.yml
storage:
  local:
    root: /var/lib/myapp/objects   # required
```

Writes are atomic (staged to a `.part` file then `os.replace`); path traversal is rejected; file IO runs in worker threads. No extra dependency. `url()` raises `UnsupportedOperation` - serve files via the web helper below.

### S3 / MinIO backend - `xime.starters.s3`

Install with `pip install "xime[s3]"`.

```python
# config/dependency.py
from xime.starters.storage import StorageService
from xime.starters.s3 import S3FileStorage

dependency.scan("xime.starters.s3")
dependency.bind({ StorageService: S3FileStorage })
```

```yaml
# resources/application.yml
storage:
  s3:
    bucket: my-bucket            # required
    region: us-east-1            # optional
    endpoint_url: http://minio:9000   # optional (MinIO / S3-compatible)
    access_key: ...              # optional (else from env / instance role)
    secret_key: ...
    addressing_style: path       # optional: "path" (MinIO) | "virtual"
```

`S3ClientProvider` opens the async client in `PostConstruct` and closes it in `PreDestroy`. `put_stream` uses multipart upload (aborted on error), `open_stream` issues a ranged GET, and `url()` returns a presigned URL. `aioboto3` is imported lazily.

### Streaming over HTTP - `xime.adapters.web.files`

Two helpers stream stored objects to/from HTTP without buffering, called from inside a controller:

```python
from fastapi import Request, UploadFile
from xime.adapters.web.routing import get, post
from xime.adapters.web.files import stream_object, save_upload
from xime.starters.storage import StorageService

class FileController:
    def __init__(self, storage: StorageService) -> None:
        self._storage = storage

    @get("/files/{key:path}")
    async def download(self, key: str, request: Request):
        # Honours HTTP Range -> 206 Partial Content; 404 if missing.
        return await stream_object(self._storage, key, request=request)

    @post("/files/{key:path}")
    async def upload(self, key: str, file: UploadFile):
        # Streams in chunks; over the cap -> 413 PayloadTooLarge.
        await save_upload(self._storage, key, file, max_bytes=50 * 1024 * 1024)
        return {"key": key}
```

Swapping backend (local ⇆ S3) is a one-line binding change; controller code is unchanged.

---

## Using Multiple Starters

Starters compose cleanly. A typical production service might use:

```python
# config/dependency.py
dependency.bind({
    TransactionManager: SqlAlchemyTransactionManager,
    UserRepository: JpaUserRepository,
})

# config/jwt.py
configure_jwt(JwtMiddlewareConfig(
    key_context=KeyContext(algorithm="RS256", public_key_pem=os.environ["JWT_PUBLIC_KEY"]),
    audience="my-service",
    public_paths=["/auth/login", "/health"],
))

# config/routing.py
configure_controllers("api.rest")

# config/scheduler.py
configure_scheduler(SchedulerConfig(jobs=[
    CronJob(job_class=DailyReportJob, cron="0 8 * * *"),
]))
```


---

[← Transaction](transaction.md) · **6/9 - Starters** · [Testing →](testing.md)
