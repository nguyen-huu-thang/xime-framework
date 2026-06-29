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

### Repository CRUD sẵn — `CrudRepository[T]`

Thay vì mỗi dự án tự viết lại một base repository giống hệt nhau, starter cung cấp
sẵn `CrudRepository[T]` - tương tự `JpaRepository`/`CrudRepository` của Spring Data.
Repository con chỉ cần khai báo `model` rồi viết thêm query đặc thù:

```python
from sqlalchemy import select
from xime.starters.sqlalchemy import CrudRepository

class CategoryRepository(CrudRepository[Category]):
    model = Category

    # Query đặc thù tự viết qua self.session
    async def find_by_slug(self, slug: str) -> Category | None:
        result = await self.session.execute(
            select(Category).where(Category.slug == slug)
        )
        return result.scalar_one_or_none()
```

Các method có sẵn:

| Method | Mô tả |
| --- | --- |
| `find(id_)` | Lấy theo khóa chính, trả `None` nếu không có |
| `find_or_fail(id_)` | Như `find` nhưng ném `EntityNotFoundError` khi không có |
| `find_all()` | Lấy toàn bộ bản ghi của model |
| `exists(id_)` | `True`/`False` theo khóa chính |
| `count()` | Tổng số bản ghi |
| `save(entity)` | Thêm/cập nhật rồi `flush` (entity nhận khóa sinh tự động) |
| `save_all(entities)` | Thêm nhiều entity trong một `flush`, trả lại danh sách |
| `delete(entity)` | Xóa rồi `flush` |

Mọi method đọc session đang hoạt động qua `AsyncSessionFactory`, nên **phải gọi
trong** `async with self.transaction():` (transaction do use case layer mở):

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

> `CrudRepository` khai báo `model` là abstract property nên **chính lớp nền là
> abstract** - DI scanner bỏ qua nó, chỉ repository con (đã set `model`) mới thành
> singleton. Không sinh singleton thừa, không cần đăng ký gì thêm.

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

## Storage Starter

`xime.starters.storage`

Định nghĩa `StorageService` - hợp đồng lưu trữ object/blob trung lập backend (một `Protocol`). Business code phụ thuộc `StorageService`; backend cụ thể (filesystem local hoặc S3/MinIO) được bind tường minh trong `config/dependency.py`. Giống `CacheService`, object là `bytes` thô (hoặc stream bytes) - framework không áp đặt cách đặt tên, authorization hay content-type.

Hai dạng truy cập:

- `put` / `get` - bytes nguyên object, tiện cho object nhỏ.
- `put_stream` / `open_stream` - stream bytes async cho object lớn không nạp hết vào RAM (`open_stream` nhận `offset`/`length` cho HTTP Range).

Kèm `delete`, `exists`, `stat` (size/content-type/etag) và `url` (presigned URL nếu backend hỗ trợ). Key là tương đối; **mọi backend** đều từ chối key rỗng/tuyệt đối/`..` (traversal) như nhau.

### Backend filesystem local — `xime.starters.localfs`

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
    root: /var/lib/myapp/objects   # bắt buộc
```

Ghi nguyên tử (file tạm `.part` rồi `os.replace`); chặn path traversal; IO file chạy trong worker thread. Không cần thư viện thêm. `url()` ném `UnsupportedOperation` - phục vụ file qua helper web bên dưới.

### Backend S3 / MinIO — `xime.starters.s3`

Cài bằng `pip install "xime[s3]"`.

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
    bucket: my-bucket            # bắt buộc
    region: us-east-1            # tùy chọn
    endpoint_url: http://minio:9000   # tùy chọn (MinIO / S3-compatible)
    access_key: ...              # tùy chọn (hoặc lấy từ env / instance role)
    secret_key: ...
    addressing_style: path       # tùy chọn: "path" (MinIO) | "virtual"
```

`S3ClientProvider` mở client async ở `PostConstruct`, đóng ở `PreDestroy`. `put_stream` dùng multipart upload (abort khi lỗi), `open_stream` dùng ranged GET, `url()` trả presigned URL. `aioboto3` được import lười.

### Streaming qua HTTP — `xime.adapters.web.files`

Hai helper stream object lên/xuống HTTP không buffer, gọi trong controller:

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
        # Tôn trọng HTTP Range -> 206 Partial Content; 404 nếu không có.
        return await stream_object(self._storage, key, request=request)

    @post("/files/{key:path}")
    async def upload(self, key: str, file: UploadFile):
        # Stream theo chunk; vượt giới hạn -> 413 PayloadTooLarge.
        await save_upload(self._storage, key, file, max_bytes=50 * 1024 * 1024)
        return {"key": key}
```

Đổi backend (local ⇆ S3) chỉ là một dòng bind; code controller không đổi.

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
