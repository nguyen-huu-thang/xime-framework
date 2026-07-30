# Starters

**English** | [Tiếng Việt](../vn/starters.md)

[← Transaction](transaction.md) · **6/9 — Starters** · [Testing →](testing.md)

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

> `ReadOnlyManager` is optional — skip the binding and everything behaves as
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

### Built-in CRUD — `CrudRepository[T]`

Instead of every project re-writing the same base repository, the starter ships
`CrudRepository[T]` — similar to Spring Data's `JpaRepository`/`CrudRepository`.
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
> itself is abstract** — the DI scanner skips it; only concrete subclasses (with
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
))
```

`WebAdapter` reads this registration while building the app and attaches the middleware itself - there is no second function to call. Skip `configure_jwt` and no middleware is attached.

`KeyContext` states the algorithm and key material **explicitly**; nothing is inferred from the key:

| Algorithm family | Field to set |
| --- | --- |
| HMAC (`HS256`...) | `secret` |
| RSA / EC / EdDSA (`RS256`, `ES256`, `EdDSA`...) | `private_key_pem` to sign, `public_key_pem` to verify |

**Set `audience`.** Left unset, a token minted for a different service but signed with the same key is still accepted.

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

An expired token, a bad signature, or a mismatched `aud`/`iss` all raise `AuthenticationException`.

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

### Local filesystem backend — `xime.starters.localfs`

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

### S3 / MinIO backend — `xime.starters.s3`

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

### Streaming over HTTP — `xime.adapters.web.files`

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

[← Transaction](transaction.md) · **6/9 — Starters** · [Testing →](testing.md)
