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

Cung cấp lập lịch tác vụ định kỳ kiểu cron và theo khoảng thời gian cố định (dựa trên APScheduler). Cài bằng `pip install "xime[scheduler]"`.

### Định nghĩa Job

Một job là class implement Protocol `ScheduledJob` - đúng một method `async def run(self) -> None`. Job class là DI singleton nên nhận dependency qua constructor giống mọi class khác:

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

### Thiết lập

Đăng ký job bằng cách truyền `SchedulerConfig` vào `configure_scheduler()`. Dùng `CronJob` cho biểu thức cron 5 trường và `IntervalJob` cho khoảng thời gian cố định:

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
        CronJob(job_class=DailyReportJob, cron="0 8 * * *"),   # mỗi ngày lúc 08:00
        IntervalJob(job_class=CacheSyncJob, seconds=60),        # mỗi 60 giây
    ],
    timezone="Asia/Ho_Chi_Minh",   # tùy chọn, mặc định "UTC"
))
```

`CronJob` và `IntervalJob` nhận thêm `id` tùy chọn (mặc định là tên class). `IntervalJob` cộng dồn `hours` / `minutes` / `seconds`; khoảng bằng 0 bị từ chối lúc startup (fail-fast). Scheduler khởi động sau khi mọi singleton được dựng xong và dừng êm khi shutdown, chờ job đang chạy dở hoàn tất.

---

## Cache Starter

`xime.starters.cache`

Định nghĩa `CacheService` - contract key/value cache trung lập backend (một `Protocol`). Business code phụ thuộc vào `CacheService`; backend cụ thể (vd Redis) được bind tường minh trong `config/dependency.py`, nên có thể hoán đổi implementation mà không đụng business code.

`CacheService` làm việc với `bytes` thô có chủ đích - framework không áp đặt chính sách serialize. Caller tự encode/decode (JSON, pickle, msgpack, UTF-8 thuần) tùy nghiệp vụ. TTL tính bằng giây nguyên; `None` nghĩa là không hết hạn.

```python
from typing import Protocol

class CacheService(Protocol):
    async def get(self, key: str) -> bytes | None: ...
    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...
```

### Cách dùng

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

Cung cấp async Redis client (`RedisClientProvider`) và `RedisCacheService` - implementation của `CacheService` dựa trên Redis. Cài bằng `pip install "xime[redis]"`.

### Cài đặt

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
  max_connections: 10   # tùy chọn, mặc định 10
```

`RedisClientProvider` đọc `redis.url` (bắt buộc - thiếu thì fail fast lúc startup) và `redis.max_connections`, sở hữu connection pool và đóng nó ở `PreDestroy` khi shutdown. Package `redis` được import lười nên module starter vẫn import được kể cả khi chưa cài extra - chỉ service nào scan package này mới cần.

### Dùng backend khác

Vì business code chỉ phụ thuộc `CacheService`, đổi backend chỉ là sửa một dòng binding:

```python
# Production: Redis
dependency.bind({ CacheService: RedisCacheService })

# Testing: fake in-memory thỏa Protocol CacheService
dependency.bind({ CacheService: InMemoryCacheService })
```

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

# config/scheduler.py
configure_scheduler(SchedulerConfig(jobs=[
    CronJob(job_class=DailyReportJob, cron="0 8 * * *"),
]))
```

---

[← Transaction](transaction.md) · **6/9 — Starters** · [Testing →](testing.md)
