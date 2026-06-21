# Starters

**English** | [Tiếng Việt](../vn/starters.md)

[← Transaction](transaction.md) · **6/9 — Starters** · [Testing →](testing.md)

---

Starters are optional integration modules, similar to `spring-boot-starter-*` in Spring Boot. Each starter provides a ready-to-use integration with a specific technology. Use only what you need.

---

## SQLAlchemy Starter

`xime.starters.sqlalchemy`

Provides async database sessions and the `SqlAlchemyTransactionManager`.

### Setup

```python
# config/dependency.py
from xime.transaction import TransactionManager
from xime.starters.sqlalchemy import SqlAlchemyTransactionManager

dependency.bind({
    TransactionManager: SqlAlchemyTransactionManager,
})
```

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
from xime.transaction import TransactionManager

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

---

## JWT Starter

`xime.starters.jwt`

Provides JWT token signing, verification, and an HTTP middleware that authenticates requests.

### Setup

```python
# config/dependency.py
from xime.starters.jwt import configure_jwt, JwtConfig

configure_jwt(JwtConfig(
    secret_key="your-secret-key",
    algorithm="HS256",
    expiry_seconds=3600,
))
```

```yaml
# resources/application.yml
jwt:
  secret_key: ${JWT_SECRET}
  algorithm: HS256
  expiry_seconds: 3600
```

### Signing a Token

```python
from xime.starters.jwt import JwtSigner

class AuthUseCase:
    def __init__(self, signer: JwtSigner) -> None:
        self._signer = signer

    async def login(self, credentials: LoginCommand) -> str:
        user = await self._authenticate(credentials)
        return self._signer.sign({"sub": str(user.id), "email": user.email})
```

### Verifying a Token

```python
from xime.starters.jwt import JwtVerifier

class TokenUseCase:
    def __init__(self, verifier: JwtVerifier) -> None:
        self._verifier = verifier

    async def verify(self, token: str) -> dict:
        return self._verifier.verify(token)
```

### JWT Middleware

The middleware automatically extracts and validates the `Authorization: Bearer <token>` header, populating `SecurityContext`:

```python
# config/security.py
from xime.starters.jwt import configure_jwt_middleware

configure_jwt_middleware(public_paths=["/auth/login", "/health"])
```

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

## Using Multiple Starters

Starters compose cleanly. A typical production service might use:

```python
# config/dependency.py
dependency.bind({
    TransactionManager: SqlAlchemyTransactionManager,
    UserRepository: JpaUserRepository,
})

# config/security.py
configure_jwt_middleware(public_paths=["/auth/login", "/health"])

# config/routing.py
configure_controllers("api.rest")

# config/scheduler.py
configure_scheduler(SchedulerConfig(jobs=[
    CronJob(job_class=DailyReportJob, cron="0 8 * * *"),
]))
```


---

[← Transaction](transaction.md) · **6/9 — Starters** · [Testing →](testing.md)
