# Nguyên tắc Code - Xime Framework

## Không dùng Annotation cho DI

Không bao giờ dùng `@service`, `@repository`, `@component`, `@inject`, hay `@autowired`.
Loại component được suy luận từ **vị trí thư mục**:

```
application/service/       → tầng service
application/usecase/       → tầng use case
infrastructure/repository/ → tầng repository
infrastructure/client/     → external client
```

---

## Constructor Injection Only

Tất cả dependency được khai báo qua tham số constructor. Framework đọc type hint để tự động xây dựng dependency graph:

```python
class UserService:
    def __init__(
        self,
        transaction: TransactionManager,
        repository: UserRepository,
    ):
        self.transaction = transaction
        self.repository = repository
```

---

## Điều kiện đăng ký Class

Một class chỉ được đăng ký vào DI container khi:

- Không phải `ABC` hay `Protocol`
- **Không phải Pydantic `BaseModel`** (xem ngay dưới)
- Tất cả tham số constructor có type hint (thiếu hint → coi như class đó không đăng kí mà là class ngoài DI)
- Không thuộc package bị loại trừ: `domain`, `dto`, `entity`, `vo`, `constant`, `exception` -
  **mặc định này ghi đè được** bằng `dependency.exclude_segments(...)`, kể cả khai rỗng để
  quét tất

### Pydantic `BaseModel` bị loại, `@dataclass` thì KHÔNG - và ranh giới không phải "cái nào là dữ liệu"

Hai thứ này trông giống nhau (đều hay dùng làm DTO, đều làm chết startup khi để nhầm chỗ)
nhưng framework đối xử ngược nhau, và lý do đáng nhớ hơn quy tắc:

> **Ranh giới của DI là *dựng được hay không*, không phải *người ta định dùng làm gì*.**

| | Vào DI? | Vì sao |
|---|---|---|
| `BaseModel` | ⛔ **Không, chặn ở cửa** | `__init__` của nó là `(self, **data: Any)`. Constructor injection khớp **theo tên tham số**, mà `**data` không có tên nào để khớp - **không có chỗ cắm dây**, dù người viết có muốn hay không |
| `@dataclass` | ✅ **Có** | Nó **sinh ra** `__init__(self, repo: Repo)` - chính xác là constructor injection, chỉ khác cách viết. DI dựng được, nên giữ |

⚠ **Đừng đề xuất loại `@dataclass`.** Framework phân biệt được (`dataclasses.is_dataclass()`)
và cố ý không dùng, vì loại nó sẽ hỏng **im lặng** theo chiều ngược hôm nay: một service viết
bằng dataclass **biến mất khỏi DI không một lời nào**, trong khi hôm nay một dataclass dữ
liệu đặt nhầm chỗ **nổ lúc khởi động kèm tên class**.

⚠ **Và đừng "vá" bằng cách lọc `VAR_KEYWORD` trong `resolve_constructor_hints`.** Đã thử và
loại: `build()` chỉ **kiểm**, dựng thật xảy ra ở `get_all_in_order()`, nên bỏ `**data` khỏi
danh sách dependency chỉ đổi `UnregisteredDependencyException: Any` thành
`ValidationError: field required` - một lỗi **không còn dấu vết nào của DI**, tức khó lần hơn
lỗi cũ. Phải chặn ở `_is_eligible`.

Cần một `BaseModel` làm singleton (value object cấu hình) thì dùng `dependency.configure()`.

### Ghi đè danh sách package bị loại trừ

```python
dependency.exclude_segments("domain", "dto", "legacy")   # thay the han, khong cong them
dependency.exclude_segments()                             # quet TAT, khong loai gi
```

⚠ **Không gọi** và **gọi rỗng** là hai chuyện khác nhau: chưa khai thì state là `None` và
scanner giữ sáu đoạn mặc định; khai rỗng thì không loại đoạn nào. Gộp hai trạng thái đó lại
là một giá trị mang hai nghĩa ([luật 03](../../../.claude/rules/03-mot-gia-tri-mot-nghia.md)),
và nó hỏng theo chiều nguy nhất: mọi app bỗng quét cả `domain/` mà **không có gì báo**. Vì
vậy `orchestrator.py` chuyển tiếp **có điều kiện** - đừng dọn thành lời gọi vô điều kiện.

Bộ lọc chỉ chạy khi duyệt **module con**: trỏ `scan()` thẳng vào `app.domain` thì class trong
`__init__.py` của chính package đó vẫn được đăng ký. Chỉ đích danh thì coi như cố ý.

### Tham số có giá trị mặc định = tham số KHÔNG bắt buộc

Nếu một tham số constructor **có default** mà không thứ gì trong container cấp
được kiểu của nó, framework **bỏ tham số đó ra khỏi kế hoạch dựng** và để Python
dùng giá trị mặc định. Không báo lỗi.

```python
class ModbusClient:
    def __init__(self, device: str = "default") -> None: ...

dependency.register(ModbusClient)     # OK, device = "default"
```

**Vì sao cần quy tắc này:** container đọc MỌI annotation là một dependency, nên
trước đây chữ ký trên không đăng ký nổi - startup chết với
`UnregisteredDependencyException: Dependency: str`, dù chẳng DI container nào
cấp `str` bao giờ. Đúng lỗi đã xảy ra với `ModbusClient`/`OpcuaClient` ở 0.7.0
(xem `docs/kiem-toan/0.7-truoc-phat-hanh.md` mục C2).

Tương đương `@Autowired(required=false)` của Spring.

**Fail-fast vẫn giữ nguyên ở chỗ quan trọng:** tham số **không** có default mà
thiếu implementation thì startup vẫn nổ - đó là đa số áp đảo dependency thật.

**Đánh đổi đã cân nhắc và chấp nhận:** tham số `Protocol` có default mà thiếu
binding giờ nhận default thay vì nổ. Chọn quy tắc thống nhất (chứ không tách
riêng Protocol) để nó gói được trong một câu người đọc nhớ nổi.

Hiện thực: `XimeContainer._drop_unsatisfiable_optional_deps()`. Áp cho cả tham số
constructor và tham số của factory method trong `dependency.configure(...)`.
Test canh: `tests_temp/DI/test_08_optional_dependencies.py`.

### Thiếu type hint = class thường, KHÔNG phải lỗi

**Đây là thiết kế có chủ đích, không phải bug.**

Nếu một tham số constructor thiếu type hint, framework **bỏ qua tham số đó** - class vẫn được đưa vào resolved map nhưng với dep rỗng. Tham số đó sẽ không được inject.

```python
class Helper:
    def do_something(self): ...

class MyService:
    def __init__(self, helper):  # thiếu type hint → helper không được inject
        self.helper = helper
```

Lý do thiết kế:
- Type hint là **tín hiệu opt-in** cho DI. Không có hint = developer không muốn framework quản lý dep đó.
- Cho phép class "lai" tồn tại trong cùng package được scan mà không cần tách riêng.
- Nhất quán với triết lý Python: **Explicit is better than implicit** - chỉ inject những gì được khai báo rõ ràng.

Áp dụng cho cả `scan()` lẫn `register()`:

```python
# scan(): class bị SKIP hoàn toàn nếu có ít nhất một param thiếu hint
# register(): class được đưa vào DI nhưng param thiếu hint → không inject → TypeError lúc get()

# Nếu muốn class vào DI, bắt buộc phải có đủ type hint cho mọi dep cần inject:
class MyService:
    def __init__(self, helper: Helper):  # có hint → inject đúng
        self.helper = helper
```

> **Ghi chú cho người review:** Nếu thấy class trong scan package nhận về instance thiếu dep, hãy kiểm tra type hint trước khi báo lỗi framework.

---

## Quét Package

Cấu hình trong `config/dependency.py`:

```python
dependency.scan(
    "application.service",
    "application.usecase",
    "infrastructure.repository",
    "infrastructure.client",
)
```

Quy tắc `__init__.py`:

- Không có `__all__` → scan toàn bộ package
- Có `__all__` → chỉ scan các class được export

```python
__all__ = ["UserService", "AuthService"]
```

---

## Đăng ký Thủ công (Manual Registration)

Hai cơ chế để đưa class vào DI mà không cần auto-scan package, dùng trong `config/dependency.py`.

### 1. `dependency.register()` - Class đơn giản, framework tự inject

Dùng cho domain service, domain factory, hoặc bất kỳ class nào trong package bị loại trừ nhưng vẫn cần là singleton.

```python
from domain.sharedkernel.factory import IdFactory
from domain.sharedkernel.service import IdService
from domain.authentication.factory import CredentialAuthenticationFactory

dependency.register(
    IdFactory,
    IdService,
    CredentialAuthenticationFactory,
)
```

Framework áp dụng constructor injection như bình thường - đọc type hint, resolve dependency, tạo singleton. Mọi tham số `__init__` phải có type hint; thiếu hint → startup thất bại.

### 2. `dependency.configure()` - Config class với factory method (Option B)

Dùng khi cần logic khởi tạo tùy chỉnh: đọc config YAML, tạo object từ secret, gọi factory method tĩnh, v.v.

```python
class DomainConfig:
    def credential_factory(self) -> CredentialAuthenticationFactory:
        return CredentialAuthenticationFactory()

    def key_encryption_service(self, app_config: AppConfig) -> KeyEncryptionService:
        # Đọc secret từ config để khởi tạo
        return AesKeyEncryptionService(app_config.secret_key)

dependency.configure(DomainConfig)
```

**Quy tắc config class:**
- Mỗi public method có return type annotation → tạo một singleton với kiểu đó
- Tham số của method (trừ `self`) → được inject bởi container khi startup
- Config class **không được có tham số constructor** - phải stateless
- Tham số method là Protocol → phải có `dependency.bind(...)` tương ứng

Framework gọi method một lần, lưu kết quả là singleton, inject vào mọi nơi phụ thuộc kiểu đó.

### Tổng thể `config/dependency.py`

```python
# Auto-scan các tầng thông thường
dependency.scan(
    "application.service",
    "application.usecase",
    "infrastructure.repository",
    "infrastructure.client",
)

# Interface binding
dependency.bind({
    UserRepository: JpaUserRepository,
    KeyEncryptionService: AesKeyEncryptionService,
})

# Thủ công: domain class đơn giản (framework tự inject)
dependency.register(
    IdFactory,
    IdService,
)

# Thủ công: class cần logic khởi tạo tùy chỉnh
dependency.configure(DomainConfig)
```

---

## Interface Binding

Interface được định nghĩa bằng `Protocol` (không phải `ABC`). Implementation là class thông thường, không bắt buộc kế thừa Protocol.

Binding được khai báo tường minh trong `config/dependency.py`:

```python
dependency.bind({
    UserRepository: JpaUserRepository,
    CacheService: RedisCacheService,
})
```

Khi startup, framework validate implementation thỏa mãn Protocol - thiếu method → startup thất bại.

Không binding + nhiều candidate → **startup thất bại**.

> Chi tiết đầy đủ: `rules/interface-binding.md`

---

## Phạm vi Dependency (Scope)

**Xime chỉ có MỘT scope: singleton, dựng eager lúc khởi động.** Không có prototype,
không có request/session scope trong container. Đây là quyết định có chủ đích (chủ dự
án chốt 2026-08-20), không phải chỗ còn thiếu.

⚠ **Bản trước của mục này ghi `Factory - một instance mới mỗi lần gọi`. Câu đó SAI so
với code, đừng tin lại.** `FactoryEntry` (`core/container/config_loader.py`) là *factory
method của config class*: nó được gọi **đúng một lần** rồi cache thành singleton như mọi
class khác - `Registry.get()` luôn trả từ `_instances`. Chữ "factory" mang hai nghĩa
trong cùng repo, nên gặp nó ở đâu thì kiểm nghĩa trước.

### Vì sao chỉ có singleton

Container dựng **toàn bộ** đồ thị lúc khởi động theo thứ tự topo. Đó chính là cơ chế
sinh ra lời hứa Fail Fast ở mục dưới: thiếu binding, thiếu type hint, circular
dependency, Protocol không thoả - tất cả nổ lúc startup, không nổ lúc chạy nghiệp vụ.

> **Eager singleton là ĐIỀU KIỆN để có fail-fast toàn đồ thị.** Mọi scope lazy đều đục
> một lỗ vào đó: object chưa dựng thì lỗi trong constructor của nó không thể lộ ra lúc
> khởi động.

Nhiều DI Python khác (`dependency-injector`, `punq`, `injector`) mặc định transient được
vì chúng **không kiểm gì lúc khởi động cả**. Xime chọn cực ngược lại, có ý thức.

### Cần một instance mới thì làm thế nào

> **DI giữ NGƯỜI TẠO, không giữ CÁI ĐƯỢC TẠO.**

Singleton mang **hành vi**, data class mang **trạng thái**, và khi cần bản mới thì
singleton tự cấp. Ba thứ đó phủ hết mọi ca đã gặp trong 31 codebase.

| Khuôn | Bản chuẩn chép được |
|---|---|
| Singleton giữ phần dùng chung, method trả bản mới | `AsyncSessionFactory` (`starters/sqlalchemy/session.py`): singleton, `create()` trả `AsyncSession` mới mỗi transaction |
| Phần biến thiên đi bằng **tham số method**, không bằng nhiều instance | `ModbusClient.read(model, device=...)`: một client, nhiều thiết bị |
| Object tạo ra **tự quản vòng đời** bằng `async with` / `close()` | `MtlsChannelFactory.channel(target)` ở 22 app |

### ⛔ Đừng thêm prototype scope - bốn lý do, đã rà 2026-08-20

1. **Không có ca thật.** `@Scope` xuất hiện **0 lần** trong `src/` của 7 repo Java Spring
   Boot ở workspace này. Quét 31 codebase Python ra 26 class `*Factory`, và tất cả đều
   là singleton cấp object mới - không cái nào cần một scope.
2. ⭐ **Ca "nặng" nhất lại là ca prototype làm HỎNG.** `MtlsChannelFactory.channel()` trả
   kênh gRPC **phải được đóng**. Prototype là scope duy nhất container **không bao giờ
   gọi `pre_destroy`** (tài liệu Spring nói thẳng: *"the container does not manage the
   complete lifecycle of a prototype bean"*). Biến nó thành prototype là biến một dòng
   docstring nhắc đóng thành chỗ rò rỉ kết nối không ai đếm được.
3. ⭐ **Prototype không loại bỏ được singleton, nó chỉ chen vào giữa.** Mọi ca "cần object
   mới" trong thực tế đều kèm một **trạng thái dùng chung phải sống lâu hơn** các object
   đó: credentials (`MtlsChannelFactory._creds`, dựng lại mỗi lần cert xoay), pool, cấu
   hình, danh sách customizer. Nên vẫn phải có một singleton bên cạnh - mà đã có nó rồi
   thì để nó cấp luôn object mới là xong. Kiểm `WebClient.Builder` của Spring Boot (bean
   prototype thật, hiếm hoi) bằng quy luật này thì ra đúng cấu trúc đó: cấu hình chung là
   danh sách customizer, phần riêng là builder. **Cùng cấu trúc, khác cái tên** - Spring
   chỉ giấu factory đi.
4. **Cạm bẫy của nó hỏng IM LẶNG.** Inject prototype vào một singleton thì nó chỉ dựng
   đúng một lần (vì singleton chỉ dựng một lần), tức bạn khai prototype và nhận singleton.
   Không exception, không cảnh báo, không test đỏ.

> **Prototype là scope duy nhất mà container không quản lý gì cả.** So với `new`, nó cho
> đúng một thứ: tự động điền tham số constructor. Nó không phải một vòng đời, và gọi nó
> là "scope" khiến người ta tưởng container đang làm gì đó cho mình.

### Điều kiện kích hoạt, và hình dạng bắt buộc nếu có ngày thêm

Mở lại câu hỏi này khi có **ít nhất hai ca thật** rơi đúng vào giao *"object có trạng
thái riêng mỗi lần dùng **và** cần nhiều dependency từ container"*. Tính tới 2026-08-20:
**0 ca**, ở cả framework lẫn 31 app.

Ngày đó, thiết kế phải **tốt hơn Spring ở đúng chỗ Spring sai**:

- Lấy qua marker `Provider[T]`, và **inject trần `T` phải NỔ lúc khởi động** kèm câu chỉ
  đường. Khi đó cạm bẫy số 4 ở trên **không tồn tại về mặt cấu trúc**, chứ không phải
  "có tài liệu cảnh báo".
- Validator vẫn kiểm **đồ thị** của lớp transient (deps đủ, Protocol thoả), chỉ bỏ bước
  dựng. Bỏ luôn cả kiểm là mất nốt phần fail-fast còn giữ được.
- Khai thẳng trong docstring: **`pre_destroy` KHÔNG chạy** cho instance transient. Object
  giữ tài nguyên thì dùng `async with`, đừng dùng transient.
- ⛔ Không làm scoped proxy kiểu `proxyMode=TARGET_CLASS`: với prototype nó dựng instance
  mới ở **từng lời gọi method**, nên object có trạng thái mất sạch trạng thái giữa hai
  lời gọi, và mất im lặng.

### Request/Session: đã có, và cố ý nằm NGOÀI container

Trạng thái theo request đi bằng **ContextVar**: `core/context/` (`request_context`),
`core/security/context.py`, và `_current_session` của `starters/sqlalchemy/session.py`.
Rẻ hơn một scope, và không đụng vào lượt validate lúc khởi động.

---

## Fail Fast

Startup **phải thất bại ngay** với thông báo lỗi rõ ràng khi:

- Interface không có implementation nào được đăng ký
- Interface có nhiều implementation nhưng không có binding tường minh
- Dependency graph có circular dependency

Ví dụ thông báo lỗi:

```text
Missing Type Hint
  Class: UserService
  Parameter: repository
```

```text
No Implementation Found
  Interface: UserRepository
```

```text
Multiple Implementations Found
  Interface: UserRepository
  Candidates: JpaUserRepository, RedisUserRepository
```

```text
Circular dependency detected:
  UserService → AuthService → TokenService → UserService
```

---

## Cấu hình Hai Tầng

**Framework config** - dành cho Developer, viết Python (`config/dependency.py`, `config/routing.py`, …):
cấu hình DI scanning, bindings, lifecycle, routing.

**Runtime config** - dành cho Operator, viết YAML (`resources/application.yml`, `application-{env}.yml`):
host, port, secrets, database, Redis.
