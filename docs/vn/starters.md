# Starters

[English](../en/starters.md) | **Tiếng Việt**

[← Transaction](transaction.md) · **6/9 — Starters** · [Testing →](testing.md)

---

Starter là module tích hợp tùy chọn, tương tự `spring-boot-starter-*` trong Spring Boot. Mỗi starter cung cấp tích hợp sẵn sàng dùng với một công nghệ cụ thể. Chỉ dùng những gì bạn cần.

---

## SQLAlchemy Starter

`xime.starters.sqlalchemy`

Cung cấp async database session và `SqlAlchemyTransactionManager`.

### Thiết lập

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

### Sử dụng

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

Transaction được quản lý bởi use case layer, không phải repository.

---

## JWT Starter

`xime.starters.jwt`

Cung cấp JWT token signing, verification và HTTP middleware xác thực request.

### Thiết lập

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

### Ký Token

```python
from xime.starters.jwt import JwtSigner

class AuthUseCase:
    def __init__(self, signer: JwtSigner) -> None:
        self._signer = signer

    async def login(self, credentials: LoginCommand) -> str:
        user = await self._authenticate(credentials)
        return self._signer.sign({"sub": str(user.id), "email": user.email})
```

### Xác minh Token

```python
from xime.starters.jwt import JwtVerifier

class TokenUseCase:
    def __init__(self, verifier: JwtVerifier) -> None:
        self._verifier = verifier

    async def verify(self, token: str) -> dict:
        return self._verifier.verify(token)
```

### JWT Middleware

Middleware tự động trích xuất và validate header `Authorization: Bearer <token>`, điền vào `SecurityContext`:

```python
# config/security.py
from xime.starters.jwt import configure_jwt_middleware

configure_jwt_middleware(public_paths=["/auth/login", "/health"])
```

---

## Scheduler Starter

`xime.starters.scheduler`

Cung cấp lập lịch tác vụ định kỳ kiểu cron.

### Thiết lập

```python
# config/dependency.py
from xime.starters.scheduler import configure_scheduler

configure_scheduler()
```

### Định nghĩa Job

```python
from xime.starters.scheduler import job

class ReportJob:
    def __init__(self, report_service: ReportService) -> None:
        self._service = report_service

    @job(cron="0 8 * * *")   # mỗi ngày lúc 08:00
    async def send_daily_report(self) -> None:
        await self._service.generate_and_send()

    @job(interval_seconds=60)  # mỗi 60 giây
    async def sync_cache(self) -> None:
        await self._service.sync()
```

Job class là DI singleton — chúng nhận dependency qua constructor giống như bất kỳ class nào khác.

---

## Redis Starter *(Đang kế hoạch)*

`xime.starters.redis`

> **Chưa implement.** Dự kiến: async Redis client được cấu hình sẵn và đăng ký vào DI container.

---

## Cache Starter *(Đang kế hoạch)*

`xime.starters.cache`

> **Chưa implement.** Dự kiến: cache abstraction layer với backend có thể hoán đổi (Redis, in-memory, v.v.) để business code không phụ thuộc vào implementation cache cụ thể.

---

## Dùng nhiều Starter cùng lúc

Các starter kết hợp tốt với nhau. Một production service điển hình có thể dùng:

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
