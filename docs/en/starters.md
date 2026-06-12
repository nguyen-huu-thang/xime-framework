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

## Redis Starter *(Planned)*

`xime.starters.redis`

> **Not yet implemented.** Planned: a configured async Redis client registered into the DI container.

---

## Cache Starter *(Planned)*

`xime.starters.cache`

> **Not yet implemented.** Planned: a cache abstraction layer with swappable backends (Redis, in-memory, etc.) so business code never depends on a specific cache implementation.

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


---

[← Transaction](transaction.md) · **6/9 — Starters** · [Testing →](testing.md)
