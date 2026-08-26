# Khái niệm cốt lõi

[English](../en/core-concepts.md) | **Tiếng Việt**

[← Bắt đầu nhanh](getting-started.md) · **2/9 - Khái niệm cốt lõi** · [Cấu hình →](configuration.md)

---

## 1. Constructor Injection

XIME chỉ dùng constructor injection. Mọi dependency được khai báo là tham số constructor có type hint:

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

XIME đọc type hint, giải quyết từng dependency và tạo object - bạn không bao giờ phải gọi `UserService(...)` thủ công.

**Quy tắc:**

- Mỗi tham số phải có type hint. Thiếu hint đồng nghĩa XIME không thể giải quyết nó, class đó được coi là nằm ngoài DI system.
- **Tham số có giá trị mặc định là tham số KHÔNG bắt buộc.** Nếu không thứ gì trong container cấp được kiểu của nó, XIME bỏ qua tham số đó và Python dùng giá trị mặc định - thay vì báo lỗi lúc startup. Nhờ vậy chữ ký dưới đây đăng ký được bình thường, dù không DI container nào cấp `str`:

  ```python
  class ModbusClient:
      def __init__(self, device: str = "default") -> None: ...

  dependency.register(ModbusClient)     # OK, device = "default"
  ```

  Tương đương `@Autowired(required=false)` của Spring. **Fail-fast vẫn nguyên ở chỗ quan trọng:** tham số **không** có mặc định mà thiếu implementation thì startup vẫn nổ - và đó là đa số áp đảo các dependency thật.

- Không `@inject`, không `@autowired`, không field injection.

---

## 2. Directory-Driven Registration

Phát hiện dựa trên annotation (`@Service`, `@Component`) được thay bằng phát hiện dựa trên thư mục:

| Thư mục | Vai trò |
| --- | --- |
| `application/usecase/` | Use case layer |
| `application/service/` | Application service layer |
| `infrastructure/repository/` | Repository layer |
| `infrastructure/client/` | External service client |

Bạn khai báo package nào cần quét trong `config/dependency.py`:

```python
dependency.scan(
    "my_service.application.usecase",
    "my_service.application.service",
    "my_service.infrastructure.repository",
    "my_service.infrastructure.client",
)
```

Package **bị loại trừ** khỏi DI (class ở đây không bao giờ được đăng ký):

- `domain`, `dto`, `entity`, `vo`, `constant`, `exception`

Bị loại trừ vì chúng là data object, không phải service - inject chúng không có ý nghĩa.

### Ghi đè danh sách loại trừ

Sáu đoạn trên là **mặc định**, không phải luật. Chúng mang từ vựng DDD (`vo` là *value
object*), nên dự án đặt tên khác - hoặc dự án thật sự có service nằm trong package tên
`domain` - phải khai lại:

```python
dependency.exclude_segments("domain", "dto", "entity", "legacy")   # thay the han
dependency.exclude_segments()                                       # quet TAT, khong loai gi
```

| Bạn làm gì | Framework hiểu |
|---|---|
| **không gọi** | dùng mặc định sáu đoạn |
| gọi kèm danh sách | **thay thế** mặc định, không cộng thêm |
| **gọi rỗng** | không loại đoạn nào cả |

⚠ *Không gọi* và *gọi rỗng* là **hai chuyện khác nhau**. Muốn quét tất thì phải gọi rỗng
tường minh; xoá lời gọi đi là quay về mặc định.

Bộ lọc soi **từng đoạn của đường dẫn module**, nên `app.domain.model` bị loại vì có đoạn
`domain`. Nó chỉ chạy khi duyệt **module con**: trỏ `scan()` thẳng vào `app.domain` thì
class trong `__init__.py` của chính package đó **vẫn được đăng ký** - chỉ đích danh thì
coi như bạn cố ý.

### ⛔ `@dataclass` KHÔNG bị loại, và đó là quyết định có chủ đích

Câu hỏi thường gặp: DTO viết bằng `@dataclass` để nhầm trong package được quét thì làm
chết startup, sao framework không tự bỏ qua mọi `@dataclass`?

**Vì `@dataclass` là một dạng service hợp lệ**, không phải một dấu hiệu "đây là dữ liệu":

```python
@dataclass
class PhongService:
    repo: PhongRepository        # inject qua field - chay dung
```

`@dataclass` sinh ra `__init__(self, repo: PhongRepository)`. Đó **chính xác** là
constructor injection, chỉ khác cách viết.

Framework **phân biệt được** (`dataclasses.is_dataclass()`), nhưng cố ý không dùng, vì hai
lý do:

1. **Ranh giới của DI là *dựng được hay không*, không phải *người ta định dùng làm gì*.**
   `Protocol`, `ABC`, `BaseModel` bị loại vì DI **không thể** dựng chúng. `@dataclass` thì
   dựng được, nên loại nó là chuyển sang đoán ý định - thứ framework không đọc được.
2. **Loại nó sẽ hỏng IM LẶNG, ngược chiều hôm nay.** Hôm nay đặt DTO nhầm chỗ thì **nổ lúc
   khởi động kèm tên class** - khó chịu nhưng thấy ngay và sửa trong một phút. Nếu loại,
   một service viết bằng dataclass sẽ **biến mất khỏi DI không một lời nào**, rồi lỗi hiện
   ra muộn hơn ở chỗ khác dưới dạng *"No Implementation Found"* cho một class đang nằm sờ
   sờ trước mắt.

📌 Số đo trên 31 codebase Xime (2026-08-25): **197 `@dataclass` nằm trong vùng được quét,
0 cái có hình dạng bean**. Tức trong thực tế nó luôn là dữ liệu - nhưng đó là bằng chứng
về *thói quen*, không phải về *khả năng*, và framework phải đúng cho cả người dùng ngoài
Xime.

**Ba cách xử lý đúng, theo thứ tự nên dùng:**

| Cách | Khi nào |
|---|---|
| Đặt vào `dto/`, `domain/`... | mặc định - rẻ nhất, không cần khai gì |
| `__all__` trong `__init__.py` liệt kê đúng class DI-managed | package trộn lẫn, không muốn tách thư mục |
| `dependency.exclude_segments(...)` thêm đoạn của mình | cả một tầng là dữ liệu, ví dụ `port` |

### Pydantic `BaseModel` thì BỊ loại, và lý do khác hẳn

`BaseModel` không bao giờ vào DI, cùng nhóm với `Protocol` và `ABC` - **kể cả khi nó nằm
trong package được quét, kể cả khi mọi field đều có giá trị mặc định.**

Không phải vì "nó thường là dữ liệu", mà vì nó **không thể** nhận dependency:

```python
def __init__(self, **data: Any) -> None: ...   # chu ky that cua BaseModel
```

Constructor injection khớp dependency **theo tên tham số**. `**data` không có tên tham số
nào để khớp, nên không có chỗ cắm dây - dù người viết có muốn hay không.

Cần một value object cấu hình làm singleton thì dùng `dependency.configure()`:

```python
class DomainConfig:
    def chinh_sach(self) -> SubscriptionPolicy:
        return SubscriptionPolicy(trial_days=14)

dependency.configure(DomainConfig)
```

---

## 3. Điều kiện đăng ký Class

Một class được đăng ký vào DI container khi **tất cả** điều kiện sau đúng:

1. Không phải subclass của `ABC` hay `Protocol`
2. **Không phải Pydantic `BaseModel`** (xem mục 2 - nó không có chỗ nhận dependency)
3. Tất cả tham số `__init__` có type hint
4. Package của nó nằm trong danh sách scan và không trong danh sách exclude

Nếu class có tham số thiếu type hint, nó bị bỏ qua yên lặng - không phải lỗi. Điều này cho phép class bên thứ ba tồn tại trong package được scan mà không gây vấn đề.

### Ba đường vào DI, không chỉ có `scan()`

`scan()` là đường phổ biến nhất nhưng không phải đường duy nhất, và hai đường còn lại giải
đúng những ca mà `scan()` không giải được:

| Đường | Dùng khi | Framework làm gì |
|---|---|---|
| `dependency.scan("...")` | class nằm trong package theo quy ước | quét, tự lọc theo điều kiện trên |
| `dependency.register(A, B)` | class nằm trong package **bị loại trừ** mà vẫn cần là singleton (domain factory, domain service) | **bỏ qua bốn điều kiện trên** - khai tường minh thì tôn trọng lời khai; vẫn constructor injection bình thường, nên mọi tham số `__init__` phải có type hint |
| `dependency.configure(Cls)` | cần **logic khởi tạo riêng**: đọc cấu hình, dựng từ secret, gọi factory của bên thứ ba | gọi từng public method có return type, mỗi method thành **một singleton mang kiểu đó** |

`configure()` là câu trả lời cho câu hỏi *"tôi có một object muốn tự tay dựng rồi đưa vào
DI thì làm sao"*:

```python
class DomainConfig:
    # moi method public co return type -> mot singleton
    def chinh_sach(self) -> SubscriptionPolicy:
        return SubscriptionPolicy(trial_days=14)          # tu dung theo y minh

    def ma_hoa(self, cfg: AppConfig) -> KeyEncryptionService:
        return AesKeyEncryptionService(cfg.secret_key)     # tham so duoc inject

dependency.configure(DomainConfig)
```

Ba ràng buộc của config class:

- **Không có tham số constructor** - nó phải stateless.
- Tham số của method (ngoài `self`) **được container inject**, nên phải có type hint.
- Method được gọi **đúng một lần**; kết quả là singleton như mọi class khác.

⚠ Chữ *"factory"* ở đây dễ gây hiểu nhầm: nó là **factory method dựng singleton**, không
phải cơ chế sinh instance mới mỗi lần gọi. Xime chỉ có **một scope là singleton** - xem
mục 5.

---

## 4. Interface Binding bằng Protocol

`Protocol` của Python cho phép structural typing - một class thỏa mãn Protocol nếu có đúng method, không cần kế thừa tường minh.

Định nghĩa interface:

```python
from typing import Protocol

class UserRepository(Protocol):
    async def find_by_id(self, user_id: int) -> User | None: ...
    async def save(self, user: User) -> None: ...
```

Viết implementation - **không bắt buộc kế thừa**:

```python
class JpaUserRepository:
    async def find_by_id(self, user_id: int) -> User | None:
        ...
    async def save(self, user: User) -> None:
        ...
```

Khai báo binding tường minh trong `config/dependency.py`:

```python
dependency.bind({
    UserRepository: JpaUserRepository,
})
```

XIME validate lúc startup rằng `JpaUserRepository` implement đủ mọi method được khai báo trong `UserRepository`. Nếu thiếu method, startup thất bại:

```text
Binding Validation Failed
  Protocol: UserRepository
  Implementation: JpaUserRepository
  Missing methods:
    - save
```

**Tại sao cần binding tường minh?**

`Protocol` dùng structural typing - Python không thể biết class có cố ý implement interface hay chỉ tình cờ có cùng method. Binding tường minh làm quyết định kiến trúc rõ ràng trong code. Xem [Interface Binding](../en/core-concepts.md) để biết lý do đầy đủ.

### 4.1 Dynamic binding (nhiều implementation)

Value của binding có thể là một **tuple** implementation thay vì một class. Phần tử đầu là mặc định. Cách này cho phép đổi implementation mà một interface dùng **trên toàn ứng dụng lúc runtime**, mà không phải đụng code consumer.

```python
# config/dependency.py
dependency.bind({
    UserRepository: JpaUserRepository,                            # 1-1 như cũ
    PaymentGateway: (StripeGateway, PaypalGateway, MockGateway),  # phần tử đầu = mặc định
})
```

Tính năng **mặc định tắt**, bật bằng một cờ runtime:

```yaml
# resources/application.yml
xime:
  di:
    dynamic-binding: false   # mặc định; đặt true để bật đổi động lúc runtime
```

| Value binding | Cờ | Hành vi |
| --- | --- | --- |
| một class | bất kỳ | Y hệt trước đây. |
| tuple | **tắt** | Dùng **phần tử đầu**, inject tĩnh y như binding 1-1; các impl còn lại không bao giờ dựng. Bằng đúng kiến trúc cũ. |
| tuple | **bật** | Mọi impl thành singleton eager; consumer nhận một **proxy trong suốt**; một `Switcher` đổi interface toàn cục. |

**Consumer không đổi gì** - cả hai chế độ đều phụ thuộc Protocol như thường:

```python
class CheckoutService:
    def __init__(self, gateway: PaymentGateway):     # không đổi
        self.gateway = gateway

    async def pay(self, amount: int) -> str:
        return await self.gateway.charge(amount)     # không đổi
```

Khi bật cờ, inject một `Switcher` để đổi implementation lúc runtime:

```python
from xime.core.container.switcher import Switcher

class AdminService:
    def __init__(self, switcher: Switcher):
        self.switcher = switcher

    def failover(self):
        self.switcher.use(PaymentGateway, PaypalGateway)  # cả app dùng Paypal
        self.switcher.reset(PaymentGateway)               # một interface về mặc định
        self.switcher.reset()                             # mọi interface về mặc định
```

**Lưu ý:**

- Đổi là **toàn cục**: tráo con trỏ dùng chung nên mọi consumer / request / coroutine thấy implementation mới ở lần gọi kế tiếp; request đang chạy dở cũng bị chuyển giữa chừng. Không có request scope.
- Dùng cho quyết định **mức hệ thống/vận hành**, áp cho mọi request và xảy ra thưa: failover nhà cung cấp, kill-switch / maintenance, đổi nhà cung cấp. Khi việc chọn phụ thuộc **dữ liệu từng request** (quốc gia, tenant, user) và nhiều request cần khác nhau cùng lúc, hãy viết một lớp **router** nhận mọi impl qua DI rồi chọn theo từng lời gọi; đừng nhét `if/case` vào từng implementation.
- **Fail-fast:** khi bật cờ, mọi impl trong tuple phải thỏa Protocol, sai thì startup fail. `Switcher` luôn inject được; khi tắt cờ, `use()`/`reset()` báo lỗi rõ.
- Tuple một phần tử được xử lý như binding 1-1 (không có gì để switch).

---

## 5. Dependency Scope

| Scope | Mô tả | Mặc định |
| --- | --- | --- |
| `Singleton` | Một instance cho toàn bộ vòng đời ứng dụng | Có |
| `Factory` | Instance mới mỗi lần gọi | Không |

Tất cả service, use case và repository là singleton theo mặc định. Factory scope sẽ có thể cấu hình trong phiên bản tương lai.

---

## 6. Fail Fast Validation

XIME validate toàn bộ dependency graph trước khi tạo bất kỳ object nào. Startup thất bại ngay với lỗi mô tả rõ ràng cho:

**Thiếu implementation:**

```text
No Implementation Found
  Interface: UserRepository
  Hint: add dependency.bind({UserRepository: YourImpl}) in config/dependency.py
```

**Implementation mơ hồ** (nhiều candidate, không có binding tường minh):

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

**Thiếu type hint:**

```text
Missing Type Hint
  Class: UserService
  Parameter: repository
  Hint: add a type annotation - def __init__(self, repository: UserRepository)
```

---

## 7. Package Scanning và `__init__.py`

Mặc định, scan một package sẽ tìm tất cả class trong tất cả submodule. Bạn có thể giới hạn class nào được export bằng `__all__`:

```python
# application/usecase/__init__.py
__all__ = ["GetUserUseCase", "CreateUserUseCase"]
```

Khi có `__all__`, chỉ class được liệt kê mới được scan. Không có `__all__` thì scan hết.

---

## 8. Lifecycle Hooks

Class hook vào vòng đời ứng dụng bằng cách **đặt đúng tên method** - không đăng ký gì thêm, không decorator. `PostConstruct` và `PreDestroy` là `Protocol`; framework kiểm bằng `isinstance` lúc startup/shutdown:

```python
class DatabasePool:
    def __init__(self) -> None:
        self._pool = None

    async def post_construct(self) -> None:   # gọi sau khi TẤT CẢ singleton được tạo
        self._pool = await create_pool()

    async def pre_destroy(self) -> None:      # gọi trước khi shutdown
        await self._pool.close()
```

Thứ tự: `post_construct()` chạy theo thứ tự topo (dependency trước, dependent sau); `pre_destroy()` chạy ngược lại. Hai class không phụ thuộc nhau mà vẫn cần thứ tự thì khai `dependency.order([A, B])`.

### Quy tắc quan trọng: mở được đến đâu, tự dọn đến đó

`pre_destroy()` **chỉ được gọi cho instance đã chạy XONG `post_construct()`**. Đây là lựa chọn có chủ đích (chốt 2026-07-30): gọi `pre_destroy` trên một object khởi tạo dở sẽ ném lỗi thứ hai (`AttributeError` vì field chưa tồn tại) và che mất lỗi gốc - đúng lúc bạn cần đọc lỗi gốc nhất.

Hệ quả: nếu `post_construct()` **hỏng ở giữa** - đã mở tài nguyên rồi mới lỗi ở bước sau - thì tài nguyên đó không ai đóng. Trách nhiệm dọn nằm ở chính `post_construct`, nơi duy nhất biết nó đã mở tới đâu:

```python
async def post_construct(self) -> None:
    self._pool = await create_pool()      # bước 1 - mở tài nguyên
    try:
        await self._warm_cache()          # bước 2 - có thể hỏng
    except Exception:
        await self._pool.close()          # dọn bước 1 rồi mới ném tiếp
        raise
```

Mở **nhiều** tài nguyên tuần tự thì `AsyncExitStack` gọn hơn chuỗi try/except lồng nhau:

```python
from contextlib import AsyncExitStack

async def post_construct(self) -> None:
    async with AsyncExitStack() as stack:
        self._pool = await stack.enter_async_context(create_pool())
        self._mq = await stack.enter_async_context(connect_broker())
        await self._warm_cache()          # hỏng ở đây -> stack tự đóng cả hai
        self._stack = stack.pop_all()     # thành công -> giữ lại, KHÔNG đóng

async def pre_destroy(self) -> None:
    await self._stack.aclose()
```

`pop_all()` là mấu chốt: đi hết block mà không lỗi thì quyền đóng được chuyển sang `pre_destroy`; lỗi giữa chừng thì `AsyncExitStack` đóng mọi thứ đã mở, theo thứ tự ngược.

### Hook thứ ba: `run_once()` - chạy MỘT lần cho cả cụm

`post_construct()` chạy ở **mọi tiến trình**. Với một tiến trình thì đó là toàn bộ câu chuyện; với bốn thì *"chạy lúc khởi động"* có **hai** nghĩa, và chúng ngược nhau:

| | Mọi tiến trình | **Một lần cho cả cụm** |
|---|---|---|
| **Chạy một lần rồi thôi** | `post_construct()` | **`run_once()`** |
| **Chạy mãi** | `Adapter.start()` | adapter `scaling="singleton"` |

```python
class KeyRefreshJob:
    async def post_construct(self) -> None:      # MỌI tiến trình, và phải NHẸ
        self._cache = {}

    async def run_once(self) -> None:            # MỘT lần cho cả cụm
        await self._refdata.publish(await self._trust.fetch_keys())
```

Cùng cơ chế với hai hook kia: **đặt đúng tên method**, không decorator, không đăng ký gì. Framework chạy nó ở primary sau khi mọi `post_construct()` đã xong và **trước khi bất cứ adapter nào phục vụ**.

Đúng chỗ cho: migration, lấy khoá ký lần đầu, tiêu thụ vé bootstrap cert. Ba việc đó không được chạy bốn lần trong một cụm bốn tiến trình.

⚠ **`run_once()` phải LẶP LẠI ĐƯỢC**: primary chết giữa chừng thì tiến trình được thăng cấp chạy lại nó. Và nó **cố ý không có cặp huỷ** - ba ca trên đều không có gì để dọn.

⚠ Ứng dụng **một tiến trình** vẫn chạy `run_once()`: nó *là* cả cụm. Không có nhánh nào để quên. Chi tiết: [Đa tiến trình](multi-process.md).

---

## 9. Event Bus

Event bus nội bộ tách biệt các component không nên phụ thuộc trực tiếp vào nhau.
`publish()` hoạt động theo kiểu **fire and forget** - mỗi handler được schedule như một
background task độc lập, publisher trả về ngay mà không chờ handler hoàn thành.

```python
from xime.core.event import EventBus, EventHandler

class UserCreatedEvent:
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id

class NotificationHandler:
    async def handle(self, event: UserCreatedEvent) -> None:
        await send_welcome_email(event.user_id)
```

Publish từ use case - caller không bị block:

```python
class CreateUserUseCase:
    def __init__(self, bus: EventBus, repository: UserRepository) -> None:
        self._bus = bus
        self._repository = repository

    async def execute(self, command: CreateUserCommand) -> User:
        user = await self._repository.save(User(...))
        await self._bus.publish(UserCreatedEvent(user.id))
        # trả về ngay - handler chạy ở background
        return user
```

Nhiều handler cho cùng một event chạy đồng thời. Nếu handler nào raise exception,
lỗi được log lại và không ảnh hưởng đến handler khác hay publisher.

Đăng ký handler tường minh, thường trong `PostConstruct` hook:

```python
event_bus.subscribe(UserCreatedEvent, notification_handler)
event_bus.subscribe(UserCreatedEvent, audit_handler)
```

**Testing** - dùng `drain()` để chờ tất cả handler chạy xong trước khi assert:

```python
await use_case.execute(command)
await event_bus.drain()
assert notification_mock.called
```

### Trần số handler đang bay, và cách nói "đừng bỏ cái này"

`publish()` sinh **một asyncio Task cho mỗi handler** rồi trả về ngay. Không có trần thì mọi đường đi người dùng có `publish` đều cho phép nhân số task theo số request. Mỗi task đang chờ còn **giữ sống chính object event**, nên bộ nhớ tăng theo **kích thước event**, không theo một hằng số overhead cố định.

Từ 0.7.2, số task đang bay có trần, **mặc định 10.000**. Quá trần thì event bị bỏ **nguyên con** (không bao giờ chạy nửa số handler) và được đếm.

#### Từ 0.8: `publish()` nói cho bạn biết chuyện gì đã xảy ra

Tới 0.7.2, `publish()` trả `None` cho **cả ba** tình huống dưới đây, nên bên gọi không có cách nào biết event của mình bị bỏ hay đã được xếp lịch. Đó là một nợ đã khai với luật một giá trị mang một nghĩa, và nó được trả ở 0.8:

```python
from xime.core.event import PublishOutcome

ket_qua = await self._bus.publish(DonHangDaTao(don.id))
if ket_qua is PublishOutcome.DROPPED:
    # Hệ thống đang mất việc - đây là tín hiệu ngược dòng, không phải lỗi lẻ.
    self._metrics.tang("event_bi_bo")
```

| Giá trị | Nghĩa | Bên gọi nên làm gì |
|---|---|---|
| `SCHEDULED` | handler đã xếp lịch chạy nền | không phải làm gì |
| `NO_HANDLERS` | **không ai đăng ký** loại event này | lúc chạy thì vô hại; nhưng nếu bạn tin là có người nghe thì đây là một lỗi nối dây, và đây là chỗ duy nhất nhìn thấy nó |
| `DROPPED` | vượt trần, event bị bỏ **nguyên con** | hãm nhịp phía trên, hoặc nâng trần, hoặc khai `never_drop` |

⚠ **Đừng dùng giá trị này như boolean** - cả ba đều "truthy". So sánh tường minh với thành viên bạn quan tâm.

✅ **Không phá mã cũ**: bỏ qua giá trị trả về thì `publish()` hành xử y hệt trước.

Con số đó là **quyết định thiết kế của app**, không phải cấu hình môi trường - nó phụ thuộc handler của bạn chạy bao lâu và event của bạn to cỡ nào. Vì vậy nó nằm trong **Python**, cạnh routing và DI binding, không nằm trong `application.yml`:

```python
# config/event.py
from xime.core.event import configure_event_bus

configure_event_bus(
    max_pending=50_000,                        # handler nhẹ, event nhỏ
    never_drop=(AuditEvent, PaymentEvent),     # thứ KHÔNG được phép mất
)
```

Hai cách nói "đừng bỏ":

| Khai | Nghĩa |
|---|---|
| `never_drop=(AuditEvent,)` | **Miễn trần cho vài loại**, phần còn lại vẫn có trần. Khớp theo **kiểu chính xác**, giống cách tra handler - lớp con không thừa hưởng quyền miễn |
| `max_pending=None` | **Bỏ trần hoàn toàn**, đúng hành vi trước 0.7.2. Là một lựa chọn hợp lệ, chỉ cần là lựa chọn *có ý thức* |

⚠ `never_drop` **dời** rủi ro chứ không xoá nó: lũ event được miễn vẫn phình vô hạn, và khi vượt trần thì bus ghi một dòng WARNING nói đúng điều đó. Chỉ miễn thứ **không được phép mất**, đừng miễn thứ chỉ "muốn giữ".

Quan sát khi cần chọn lại con số:

```python
event_bus.dropped            # tong so event da bo
event_bus.dropped_by_type()  # bo theo tung loai - loai nao dang that su mat
```

Log nói *vừa có một cái bị bỏ* (có hãm nhịp, không để lũ event thành lũ log); hai số trên nói *đã bỏ bao nhiêu*. Chỉ cái thứ hai dùng được để chỉnh trần.

⛔ **Bên gọi không phân biệt được event bị bỏ với event đã xếp lịch** - cả hai đều trả `None`. Đây là nợ đã biết với nguyên tắc *một giá trị mang đúng một nghĩa* của dự án, cố ý để lại cho 0.8 vì đóng nó là đổi chữ ký công khai. Hệ quả thực dụng: **đừng dùng event bus cho thứ mà bạn phải phát hiện được khi nó mất** - hãy khai nó vào `never_drop`, hoặc đừng đi qua bus.

⚠ Ngoài ra, framework **không tự gọi `drain()` lúc tắt máy**: handler đang chạy bị cắt ngang. Cần chạy nốt thì gọi `drain()` trong `PreDestroy` hook của chính bạn.

---

## 10. Request Context

Dữ liệu theo phạm vi request chạy qua `ContextVar`, không qua tham số hàm hay global state:

```python
from xime.core.context import request_context
```

`request_context` là một kho key-value cho **context async hiện tại** - một dict cho mỗi request, nhận key bất kỳ (trace id, locale, correlation id, feature flag...).

Adapter (middleware) thiết lập context lúc bắt đầu mỗi request. Business code đọc nó:

```python
class AuditService:
    async def log(self, action: str) -> None:
        rid = request_context.get("request_id")
        await self._repository.save_log(rid, action)
```

Danh tính người dùng đi đường riêng, qua `SecurityContext`, chứ không nằm trong kho key-value này:

```python
from xime.core.security import identity

user_id = identity.get()
```

Vì `ContextVar` an toàn với async, mỗi request đồng thời có context được cô lập riêng. Mỗi lần `set()` tạo một dict MỚI thay vì sửa tại chỗ, nên task con sinh ra bằng `asyncio.create_task` giữ được ảnh chụp của mình và không bị task cha dọn context mất.

### Danh tính peer (mTLS)

Với call gRPC qua mTLS đã verify, framework đọc client certificate vào request context và cho truy xuất qua **hai** helper. Chúng trả lời **hai câu hỏi khác nhau**, nên việc đầu tiên là chốt xem mình thật sự cần danh tính nào:

| Helper | Trả về | Nhận diện |
|---|---|---|
| `current_caller()` | Common Name, một chuỗi | **một peer cụ thể** - trên thực tế là một tiến trình, một lần cấp cert |
| `current_peer_sans()` | mọi Subject Alternative Name, một tuple | thứ nơi triển khai đặt vào đó, thường là **một danh tính logic mà nhiều peer dùng chung** |

```python
from xime.core.security import current_caller

caller = current_caller()   # CN đã verify, hoặc None khi không có mTLS
```

Cả hai đều fail-soft: call plaintext hay chỉ TLS một phía sẽ khiến chúng trả `None` và không bao giờ phá request. Framework chỉ cấp cơ chế (ai gọi); authorization - caller được làm gì - vẫn nằm ở ứng dụng. Không giá trị nào bị diễn giải: framework thuật lại đúng thứ cert khai, không hơn. Cả hai giá trị cũng nằm trong request context dưới hai key trung tính `PEER_CN` và `PEER_SANS`, dành cho code đọc thẳng context; key **vắng mặt** khi cert không cấp gì, không bao giờ là có-mà-rỗng.

#### ⛔ CN gọi tên một PEER, không phải một service - chốt trước khi viết allowlist

Nơi triển khai nào chạy nhiều tiến trình sau một service logic thì thường cấp **một cert cho mỗi tiến trình**, và chở danh tính chung, bền hơn, ở SAN. Đó chính là công dụng của SPIFFE ID và các scheme URI khác.

Neo allowlist vào CN trong hoàn cảnh đó thì nó hỏng theo **hai chiều ngược nhau, cả hai đều im lặng**:

| | |
|---|---|
| Một tiến trình mới của service vốn đã được tin | **chặn oan**, mà `PERMISSION_DENIED` nhìn y hệt một cuộc tấn công |
| Cùng CN đó được cấp lại cho chủ khác | **cho qua**, vì danh sách đi theo tấm cert chứ không đi theo danh tính |

Không bên nào ném lỗi, không bên nào ghi log, và cả hai đều trả về một chuỗi hợp lệ. Vậy nên: khớp CN khi ý bạn là *đúng peer này*; khớp một entry SAN khi ý bạn là *service này, tiến trình nào gọi cũng được*.

```python
from xime.core.security import current_peer_sans

LABEL, SCHEME = "URI:", "spiffe://"
workload_id = None
for entry in current_peer_sans() or ():
    value = entry.removeprefix(LABEL)   # một số công cụ thêm tiền tố loại SAN
    if value.startswith(SCHEME):        # NEO ĐẦU chuỗi, đừng bao giờ dùng `in`
        workload_id = value
        break
```

gRPC trả SAN dạng **danh sách phẳng, không gắn nhãn** - tên DNS, địa chỉ IP và URI lẫn vào nhau, không có gì phân biệt - nên việc chọn ra entry mình cần là việc của bạn. Phép khớp phải neo đầu chuỗi: một entry như `https://example.com/?redirect=spiffe://attacker` có chứa scheme của bạn mà không phải định danh thuộc scheme đó, và phép tìm chuỗi con sẽ nhận nó.

`current_peer_sans()` trả `None` khi cert không cấp SAN nào, khi call không qua mTLS, hoặc khi transport không thuật lại được. Ba tình huống, một giá trị - và `current_caller()` là thứ tách chúng ra, vì nó trả lời câu call có qua mTLS hay không.

---

## 11. Multi-Server

Một tiến trình XIME có thể chạy nhiều `WebAdapter` và `GrpcAdapter` cùng lúc - mỗi cái trên một port khác nhau với bộ controller/servicer riêng.

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

Địa chỉ nằm trong `application.yml`, không trong code:

```yaml
process:
  web:
    default: { port: 8086 }
    admin:   { host: 127.0.0.1, port: 8081 }
  grpc:
    default:  { port: 50051 }
    internal: { port: 50052 }
```

⚠ **App một cổng không phải viết khối này** - khoá phẳng `server:` / `grpc.port`
vẫn chạy nguyên. Chỉ khi cần điểm phục vụ **thứ hai** mới cần `process:`. Chi
tiết: [Đa tiến trình](multi-process.md).

**Gán controller cho server** - khai báo class variable `server_id`:

```python
class PublicController:
    prefix = "/api/v1"
    # không có server_id → mặc định "default"

class AdminController:
    prefix = "/admin"
    server_id = "admin"   # chỉ đăng ký vào WebAdapter("admin", ...)
```

**Quy tắc:**

- `server_id` mặc định là `"default"` khi bỏ qua trên cả adapter lẫn controller/servicer.
- ⚠ **ĐỔI Ở 0.8:** adapter **chỉ nhận định danh**. `host` / `port` / `ssl` /
  `path` đã bỏ khỏi constructor và đến từ ô cấu hình - truyền vào là `TypeError`.
- Hai adapter cùng loại với cùng `server_id` → `ValueError` tại `app.use()`.
- Tất cả adapter dùng chung DI container - singleton không bị nhân đôi.
- TLS/mTLS chỉ hỗ trợ cho gRPC adapter `"default"`.
- OpenAPI theo server: `configure_openapi(config, server_id="admin")`.

---

## 12. Thứ tự khởi tạo (`dependency.order`)

Mặc định, `post_construct()` chạy theo thứ tự topological - class được phụ thuộc chạy trước. Khi hai class không có constructor dependency với nhau nhưng `post_construct()` của class này phải chạy xong trước class kia, dùng `dependency.order()`:

```python
# app/config/dependency.py
dependency.order(
    [TrustSelfCertificateLoader, GrpcExternalCredentialsProvider],
    [DatabasePool, UserRepository, UserService],
)
```

Tương đương `@DependsOn` trong Spring Boot, nhưng khai báo tập trung trong config file.

**Cú pháp:** mỗi đối số là một danh sách thứ tự. `[A, B, C]` nghĩa là:

- `A.post_construct()` hoàn thành trước khi `B.post_construct()` bắt đầu
- `B.post_construct()` hoàn thành trước khi `C.post_construct()` bắt đầu

Nhiều danh sách có thể truyền cùng lúc; framework gộp thành một đồ thị thứ tự duy nhất.

**Fail fast khi startup:**

```text
Initialization Order Error
  Classes not found in DI container: UnknownClass
  Every class in dependency.order() must be registered.

Initialization Order Conflict
  A cycle was detected in the combined dependency and order rules:
  ServiceA → ServiceB → ServiceA
```

**Không ảnh hưởng đến:** thứ tự constructor injection. `dependency.order()` chỉ kiểm soát thứ tự gọi `post_construct()` sau khi tất cả singleton đã được tạo.

---

[← Bắt đầu nhanh](getting-started.md) · **2/9 - Khái niệm cốt lõi** · [Cấu hình →](configuration.md)
