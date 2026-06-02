# Starters

**English** | [Tiếng Việt](../vn/starters.md)

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

Provides cron-style periodic task scheduling.

### Setup

```python
# config/dependency.py
from xime.starters.scheduler import configure_scheduler

configure_scheduler()
```

### Defining a Job

```python
from xime.starters.scheduler import job

class ReportJob:
    def __init__(self, report_service: ReportService) -> None:
        self._service = report_service

    @job(cron="0 8 * * *")   # every day at 08:00
    async def send_daily_report(self) -> None:
        await self._service.generate_and_send()

    @job(interval_seconds=60)  # every 60 seconds
    async def sync_cache(self) -> None:
        await self._service.sync()
```

Job classes are DI singletons — they receive their dependencies via the constructor like any other class.

---

## Redis Starter

`xime.starters.redis`

Provides a configured Redis client.

### Setup

```yaml
# resources/application.yml
redis:
  host: localhost
  port: 6379
  db: 0
  password: ${REDIS_PASSWORD}
```

```python
from xime.starters.redis import RedisClient

class SessionRepository:
    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis

    async def set_session(self, key: str, data: dict, ttl: int) -> None:
        await self._redis.set(key, json.dumps(data), ex=ttl)

    async def get_session(self, key: str) -> dict | None:
        raw = await self._redis.get(key)
        return json.loads(raw) if raw else None
```

---

## Cache Starter

`xime.starters.cache`

Provides a cache abstraction layer. The backing implementation (Redis, in-memory, etc.) is swappable without changing business code.

```python
from xime.starters.cache import CacheManager

class ProductService:
    def __init__(
        self,
        cache: CacheManager,
        repository: ProductRepository,
    ) -> None:
        self._cache = cache
        self._repository = repository

    async def get_product(self, product_id: int) -> Product:
        cached = await self._cache.get(f"product:{product_id}")
        if cached:
            return cached

        product = await self._repository.find_by_id(product_id)
        await self._cache.set(f"product:{product_id}", product, ttl=300)
        return product
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
configure_scheduler()
```
