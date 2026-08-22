# Starters

[English](../en/starters.md) | **Tiếng Việt**

[← Transaction](transaction.md) · **6/9 - Starters** · [Testing →](testing.md)

---

Starter là module tích hợp tùy chọn, tương tự `spring-boot-starter-*` trong Spring Boot. Mỗi starter cung cấp tích hợp sẵn sàng dùng với một công nghệ cụ thể. Chỉ dùng những gì bạn cần.

---

## SQLAlchemy Starter

`xime.starters.sqlalchemy`

Cung cấp async database session, `SqlAlchemyTransactionManager` và
`SqlAlchemyReadOnlyManager` (khối chỉ đọc).

### Thiết lập

```python
# config/dependency.py
from xime.core.transaction import ReadOnlyManager, TransactionManager
from xime.starters.sqlalchemy import (
    SqlAlchemyReadOnlyManager,
    SqlAlchemyTransactionManager,
)

dependency.bind({
    TransactionManager: SqlAlchemyTransactionManager,
    ReadOnlyManager: SqlAlchemyReadOnlyManager,   # tùy chọn, cho usecase chỉ đọc
})
```

> `ReadOnlyManager` là tùy chọn - không bind thì mọi thứ chạy như cũ. Chi tiết ở
> mục "Khối chỉ đọc" trong [Transaction](transaction.md).

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

Transaction được quản lý bởi use case layer, không phải repository.

### Repository CRUD sẵn - `CrudRepository[T]`

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
trong** `async with self.transaction():` (đường ghi) hoặc
`async with self.read_only():` (đường đọc) - khối do use case layer mở:

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
# config/jwt.py
import os
from xime.starters.jwt import configure_jwt, JwtMiddlewareConfig, KeyContext

configure_jwt(JwtMiddlewareConfig(
    key_context=KeyContext(
        algorithm="RS256",
        public_key_pem=os.environ["JWT_PUBLIC_KEY"],   # chỉ cần khóa CÔNG KHAI để verify
    ),
    identity_claim="sub",
    audience="data-service",
    issuer="https://identity.internal",
    public_paths=["/auth/login", "/auth/refresh", "/health"],
    algorithms=["RS256"],          # danh sách trắng: từ chối khóa khai thuật toán khác
    leeway=30,                     # giây dung sai đồng hồ cho exp / nbf / iat
    require=["exp"],               # token không có exp thì không bao giờ hết hạn - cấm nó
))
```

`WebAdapter` đọc đăng ký này lúc dựng app và tự gắn middleware - không phải gọi thêm hàm nào khác. Bỏ qua `configure_jwt` thì không có middleware nào được gắn.

`KeyContext` khai **tường minh** thuật toán và chất liệu khóa, không tự suy ra từ khóa:

| Nhóm thuật toán | Field cần điền |
| --- | --- |
| HMAC (`HS256`...) | `secret` |
| RSA / EC / EdDSA (`RS256`, `ES256`, `EdDSA`...) | `private_key_pem` để ký, `public_key_pem` để verify |

**Nên đặt `audience`.** Bỏ trống thì token phát cho service khác nhưng ký bằng cùng khóa vẫn được chấp nhận.

**Nên đặt `require=["exp"]`.** `exp` chỉ được kiểm khi claim có mặt, nên token cấp ra mà thiếu nó thì hợp lệ vĩnh viễn.

**`public_paths` so khớp CHÍNH XÁC**, không phải tiền tố. Khai `/docs` không mở `/docs/oauth2-redirect`; chỉ dấu `/` cuối được bỏ qua.

### Khóa xoay theo thời gian - `JwtKeyProvider`

Một khóa tĩnh không sống qua được lúc xoay khóa: trong lúc issuer đổi khóa thì token ký bằng khóa cũ vẫn còn hạn còn token ký bằng khóa mới đã tới. `kid` (RFC 7515 §4.1.4) nói khóa nào đã ký token, và provider biến `kid` đó thành khóa ứng viên.

```python
# config/jwt.py
from collections.abc import Sequence
from xime.starters.jwt import configure_jwt, JwtMiddlewareConfig, KeyContext

class JwksKeyProvider:
    def __init__(self) -> None:
        self._by_kid: dict[str, KeyContext] = {}

    async def load(self) -> None:            # cách làm tươi và nhịp làm tươi là của bạn
        for entry in await fetch_jwks():
            self._by_kid[entry.kid] = KeyContext(
                algorithm=entry.alg, public_key_pem=entry.pem, key_id=entry.kid,
            )

    def keys(self, kid: str | None) -> Sequence[KeyContext]:
        found = self._by_kid.get(kid) if kid else None
        return (found,) if found else ()

configure_jwt(
    JwtMiddlewareConfig(audience="data-service", require=["exp"]),
    key_provider=JwksKeyProvider,          # một CLASS, resolve từ DI container
)
```

`keys()` bắt buộc **đọc bộ nhớ, không bao giờ gọi mạng** - nó chạy ở mọi request đã xác thực. Framework không lấy, không hẹn giờ, không cache: giữ cho khóa luôn mới hoàn toàn thuộc về bạn, y như với `configure_grpc_tls(provider=...)`. Trả về dãy rỗng nghĩa là "tôi không biết kid này" và request bị từ chối 401.

Phải cấp **đúng một** nguồn khóa. Chỉ `key_context` là một khóa tĩnh; chỉ `key_provider` là bộ khóa định địa chỉ bằng `kid`. Không có cái nào, hoặc có cả hai, đều hỏng lúc khởi động - từ chối "không có cái nào" là có chủ ý, vì đường còn lại là một app khởi động không có xác thực và tự báo là khỏe trong khi mọi endpoint đều mở.

### Ký Token

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

Payload do **bạn** dựng hoàn toàn - framework không tự thêm claim nào, kể cả `exp`.

`KeyContext.key_id` trở thành header `kid`. Ký mà không có nó là hợp lệ, nhưng đó là một quyết định chứ không phải chi tiết: token không gọi tên khóa nào thì không định tuyến được tới khóa, nên không bên verify nào giữ hai khóa cùng lúc cho nó được, nên bạn không bao giờ xoay khóa mà không phải cắt dịch vụ.

Header JOSE thêm vào thì truyền qua `headers=`, ví dụ `headers={"typ": "at+jwt"}` cho access token theo RFC 9068. Ba tên bị từ chối chứ không gộp: `alg` (PyJWT cho giá trị header ghi đè tham số `algorithm`, nên nó sẽ âm thầm mâu thuẫn với `KeyContext.algorithm`), `b64` (chuyển PyJWT sang chế độ detached payload) và `kid` (nó phải gọi tên đúng khóa đã ký, mà chỉ `KeyContext.key_id` biết đó là khóa nào).

```python
# config/dependency.py
dependency.scan("xime.starters.jwt")     # đăng ký PyJwtTokenSigner / PyJwtTokenVerifier
```

### Xác minh Token

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

Token hết hạn, sai chữ ký, lệch `aud`/`iss`, thiếu claim bắt buộc, hoặc thuật toán nằm ngoài `algorithms` đều ném `AuthenticationException`. `verify()` cũng nhận `algorithms=`, `leeway=` và `require=`, nghĩa giống hệt trong `JwtMiddlewareConfig`.

### JWT Middleware

Middleware được gắn bởi chính `configure_jwt(...)` ở trên. Nó trích header `Authorization: Bearer <token>`, verify, rồi điền `SecurityContext` và đặt toàn bộ claim vào request context:

```python
from xime.core.context import request_context
from xime.core.security import identity
from xime.starters.jwt._middleware import JWT_CLAIMS

user_id = identity.get()                    # claim identity_claim (mặc định "sub")
claims  = request_context.get(JWT_CLAIMS)   # toàn bộ claim đã verify
```

Đường dẫn trong `public_paths` bỏ qua xác thực hoàn toàn. **So khớp là chính xác từng đường dẫn**, không phải theo tiền tố: khai `/docs` thì `/docs/oauth2-redirect` vẫn bị bảo vệ. Bật JWT mà muốn xem Swagger thì khai đủ cả `/docs` và `/openapi.json`.

> ### ⛔ Đường công khai KHÔNG bao giờ nhìn token, kể cả khi client có gửi
>
> Trên một đường trong `public_paths`, middleware thoát ra **trước khi** chạm tới header
> `Authorization`. Handler luôn nhận `identity = None`, dù người gọi đang đăng nhập và
> gửi một token hoàn hảo. Đây là **thiết kế cố ý và đã chốt**, không phải chỗ còn thiếu.
>
> Câu hỏi hay gặp: *"trang sản phẩm của tôi công khai, nhưng nhân viên đang đăng nhập mở
> nó thì phải thấy thêm bản nháp của mình - làm sao?"*
>
> **Gọi hai đường, không phải một.** Một trang web gọi máy chủ qua nhiều API chứ không
> phải một: phần ai cũng xem được thì lấy từ đường công khai, phần riêng của người đăng
> nhập thì lấy từ một đường **có xác thực** bình thường. Không cần đường nào mang hai chế
> độ, và phần quyết định *"hiện gì cho ai"* nằm đúng chỗ của nó - ở frontend.
>
> **Token hết hạn cũng là việc của frontend, không phải của middleware.** Trình duyệt là
> bên duy nhất biết token của mình còn bao lâu, nên nó phải xin cấp access token mới
> **trước khi** hết hạn, và xin xoay refresh token ngay khi vào trang nếu nó sắp hết.
> Cả hai đã chết thì coi như chưa đăng nhập - đó là kết quả đúng, không phải lỗi cần vá.
>
> ⚠ Cách này đòi **frontend động**. Trang tĩnh chỉ có HTML thì không biết mình đang đăng
> nhập hay không, và đó là giới hạn chấp nhận.


> **Cần extra:** `pip install "xime[jwt]"`. Thiếu nó mà vẫn gọi `configure_jwt` thì app **nổ lúc khởi động** kèm câu lệnh cần chạy, chứ không đợi tới request đầu tiên mang token.

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

## Ba chỗ để đặt trạng thái dùng chung - chọn cái nào

Từ 0.8 framework có ba thứ trông giống nhau. Chúng **không thay thế nhau**:

| | `RefData` | `Store` (LMDB) | `CacheService` (Redis) |
|---|---|---|---|
| Phạm vi | **một máy** (bộ nhớ chung) | **một máy** (file cục bộ) | **nhiều máy** |
| Dữ liệu | có nguồn bền vững, **thay trọn gói** | **không** có nguồn bền vững | bất kỳ |
| Ai ghi | **chỉ primary** | mọi tiến trình | mọi tiến trình, mọi máy |
| Ví dụ | khoá JWT, danh bạ app | hãm nhịp, thử thách passkey, chống lặp | thứ hai máy phải cùng thấy |

⭐⭐ **Ranh giới, và nó là chuyện CƠ CHẾ chứ không phải sở thích:** `RefData`,
`Store` và `ProcessLink` dựng trên **bộ nhớ chung và file cục bộ**, nên chúng dừng ở
ranh giới một máy - **và một container cũng là một máy**. `CacheService` là chỗ
framework phục vụ ca **nhiều máy**: k8s, Docker Compose `scale`, nhiều VPS sau một
bộ cân bằng tải.

> **`RefData` / `Store` là đường nhanh của MỘT máy. `CacheService` là đường chung
> của NHIỀU máy.** Không cái nào là ngoại lệ của cái nào.

⚠ Đừng đọc `Store` như bản thay thế của Redis. Chạy ba pod thì mỗi pod có **kho
riêng của nó** - `Store` không hỏng, nó chỉ có phạm vi đúng như thiết kế.

### Ví dụ cụ thể: `Store` đóng đúng một tầng của một lỗ hổng

Hãm nhịp đăng nhập giữ trong RAM tiến trình thì hạn mức bị **nhân theo số tiến
trình** - bốn tiến trình là kẻ tấn công có bốn lần hạn mức. `Store` sửa đúng chỗ
đó: cả cụm trên **một máy** dùng chung một bảng.

⚠ Nhưng nếu chạy **hai máy** sau một bộ cân bằng tải thì hạn mức lại **nhân theo
số máy**. Cùng một cách hỏng, chỉ nhỏ hơn. Và nó **không giải được bằng chia
shard**: shard cắt theo `org_id`, còn hãm nhịp thì khoá theo IP hoặc tên đăng
nhập - hai trục khác nhau, và người chưa đăng nhập được thì chưa có `org_id` nào.

> **Ranh giới gọn: mọi thứ framework tự cấp (`RefData`, `Store`, `ProcessLink`)
> là MỘT MÁY, luôn luôn. Cần nhiều máy cùng thấy thì đó là lựa chọn của ứng
> dụng, và nó đi qua `CacheService`.**

Ba ca nữa mà `Store` không làm được, để khỏi phải tự dò lại: **khoá phân tán**
giữa các máy · **pub/sub** (LMDB không có gì tương đương) · dữ liệu lớn hơn trần
`total_max` của một máy.

⛔ Ngược lại, đừng dùng Redis cho thứ `Store` làm được: một vòng mạng cho mỗi
lần đọc hãm nhịp là trả giá thật cho một thứ nằm sẵn trong RAM cùng máy.

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

### Backend filesystem local - `xime.starters.localfs`

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

### Backend S3 / MinIO - `xime.starters.s3`

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

### Streaming qua HTTP - `xime.adapters.web.files`

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
