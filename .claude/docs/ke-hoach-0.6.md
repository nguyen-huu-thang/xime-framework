# Kế hoạch 0.6 - Thay `dependency-injector` + Dynamic Interface Binding

> Tạo 2026-06-23. Trạng thái: **Việc 1 đã thiết kế chi tiết, sẵn sàng code.
> Việc 2 để khung trống, thiết kế chi tiết sau (dự kiến vài hôm nữa).**
> Liên quan: lộ trình `lo-trinh-phien-ban.md` (mục 0.6), phân tích nền
> `wishlist-tinh-nang.md` (phần "Core DI / Interface Binding").

Bản 0.6 gồm hai việc đụng cùng một lớp `core/container/registry.py`:

1. **Việc 1** - Thay thư viện `dependency-injector` bằng registry singleton tự
   viết. Refactor nội bộ, không đổi API người dùng. **Làm trước.**
2. **Việc 2** - Dynamic interface binding (`bind_many` / `switcher`). Cần thiết
   kế chi tiết. **Để sau, có thể tràn sang 0.8.**

Khuyến nghị thực thi: hoàn tất + phát hành được Việc 1 độc lập (bản sạch một
dependency), rồi mới mở Việc 2.

---

## VIỆC 1 - Thay `dependency-injector` bằng registry tự viết

### 1.1 Mục tiêu

- Bỏ hẳn dependency `dependency-injector`, tự viết lớp lưu/dựng singleton trong
  `xime/core/container/registry.py`.
- **Không đổi API public** (`XimeContainer`, `DependencyRegistry.register/get`)
  để 1050+ test hiện có pass mà không phải sửa.
- **Giữ tối đa mọi lợi thế của thư viện**; ở những điểm Xime vốn không tận dụng
  được Cython thì phải nhanh hơn (xem 1.4).

### 1.2 Hiện trạng - thư viện đang cho gì, "phí" nằm đâu

Registry hiện chỉ dùng đúng 3 primitive của `dependency-injector`:

| Primitive | Vai trò | Lợi thế thật | Phí trong ngữ cảnh Xime |
| --- | --- | --- | --- |
| `DynamicContainer` | namespace để `setattr` provider theo tên string | - | mỗi class phải sinh tên unique bằng **md5 + regex** (`_unique_name`); `get()` phải `getattr` theo string |
| `providers.Object` | bọc instance dựng sẵn | trả thẳng | thêm 1 lớp wrapper + 1 lần gọi |
| `providers.Singleton` | lazy + cache + thread-safe lock | lazy, cache, khóa chống init 2 lần | core Cython nhanh, NHƯNG Xime eager-build hết lúc startup rồi giữ reference qua constructor injection, KHÔNG gọi `get()` mỗi request -> ưu thế tốc độ Cython gần như không phát huy; mỗi `get()` vẫn trả phí check `__last_overriding`/async/lock |

Các tính năng đặc sản của thư viện (`@inject`/`Provide`, `DeclarativeContainer`,
`Configuration`, `Resource`, `Factory`, `Selector`) **không** được dùng. Toàn bộ
logic DI thật (scan, phân giải type hint, dựng graph, phát hiện cycle, topo sort)
đã tự viết trong `core/container/` (scanner, resolver, graph, validator).

Kết luận: lợi thế Cython gần như vô dụng với Xime vì runtime không gọi provider,
trong khi thư viện áp một khoản phí startup thật (md5+regex mỗi class) và một lớp
gián tiếp mỗi `get()`.

### 1.3 Thiết kế registry mới

Dùng `type` làm key trực tiếp (bỏ tên string + md5 + regex). Bốn cấu trúc:

```python
_MISSING = object()  # sentinel để cache an toàn cả giá trị None

class DependencyRegistry:
    def __init__(self) -> None:
        self._instances: dict[type, object] = {}        # cache singleton đã dựng (gồm cả Object)
        self._plan: dict[type, dict[str, type]] = {}    # cls -> {param_name: dep_type}
        self._factory: dict[type, Callable] = {}        # cls -> constructor HOẶC bound factory method
        self._building: set[type] = set()               # guard đệ quy (phòng vệ, graph đã validate acyclic)
        self._lock = threading.RLock()                  # chỉ chạm khi cache miss
```

**`register()`** - giữ nguyên chữ ký, chỉ lập "plan", chưa dựng (giữ tính lazy):

```python
def register(self, resolved, graph, instances=None, factory_entries=None):
    factory_map = {e.provided_type: e.factory_fn for e in (factory_entries or [])}

    # Instance dựng sẵn -> nạp thẳng vào cache (thay providers.Object)
    self._instances.update(instances or {})

    for cls, deps in resolved.items():
        if cls in self._instances:
            continue                       # không ghi đè Object/override bằng singleton scan
        self._plan[cls] = deps
        self._factory[cls] = factory_map.get(cls, cls)  # factory method nếu có, else constructor
```

Tham số `graph` không còn cần để sắp thứ tự (đệ quy lazy tự lo) nhưng **giữ
nguyên trong chữ ký** để tương thích caller `__init__.py`. Bỏ `hashlib`, `re`.

**`get()`** - đường nóng: đúng 1 dict lookup, không lock, không wrapper:

```python
def get(self, cls):
    obj = self._instances.get(cls, _MISSING)
    if obj is not _MISSING:
        return obj                          # cache hit: 1 lookup, zero overhead
    if cls not in self._factory:
        raise KeyError(
            f"No provider registered for '{cls.__name__}'. "
            "Make sure the class is in a scanned package."
        )
    with self._lock:                        # chỉ tới đây khi miss (gần như chỉ lúc startup)
        return self._instantiate(cls)
```

**`_instantiate()`** - đệ quy resolve; vì eager build đi theo topo order nên mỗi
dep luôn là cache hit, không đệ quy sâu:

```python
def _instantiate(self, cls):
    obj = self._instances.get(cls, _MISSING)
    if obj is not _MISSING:                  # double-checked sau khi vào lock
        return obj
    if cls in self._building:
        raise RuntimeError(f"Circular dependency while building {cls.__name__}")
    self._building.add(cls)
    try:
        kwargs = {
            param: self._instantiate(dep)
            for param, dep in self._plan[cls].items()
            if dep in self._factory or dep in self._instances
        }
        instance = self._factory[cls](**kwargs)
        self._instances[cls] = instance
        return instance
    finally:
        self._building.discard(cls)
```

### 1.4 Đối chiếu - giữ tối đa lợi thế của `dependency-injector`

| Lợi thế thư viện | Cách bản tự viết giữ / vượt |
| --- | --- |
| Lazy init | `register()` chỉ lập plan; chỉ dựng khi `get()` lần đầu. Giữ nguyên. |
| Cache singleton | dict `_instances`, cùng instance mọi lần. Lookup nhanh hơn vì bỏ lớp provider. |
| Thread-safe (chống init 2 lần) | `RLock` + double-checked locking: chỉ khóa khi cache miss; đường nóng cache hit KHÔNG chạm lock -> giữ an toàn đa luồng mà runtime zero phí (thư viện vẫn kiểm tra trên mỗi call). |
| Object provider | nạp instance thẳng vào cache dict, bỏ 1 lớp wrapper. |
| Factory method (`configure`) | `_factory[cls]` trỏ bound method thay constructor, xử lý y hệt. |
| Eager build O(n) | `get_all_in_order()` đi đúng topo order sẵn có -> mỗi dep đã cache -> `_instantiate` chỉ là chuỗi dict lookup, không recompute. |
| Tốc độ vi mô (Cython) | Xime không gọi provider mỗi request nên ưu thế này vốn vô dụng; bù lại bản mới bỏ md5+regex mỗi class lúc startup và bỏ `getattr` theo string -> startup nhanh hơn. |

Điểm mấu chốt: đường nóng runtime của Xime là `get()` sau khi đã warm -> bản dict
cho cache hit bằng đúng một `dict.get`, không thể nhanh hơn; còn
`dependency-injector` luôn đi qua `Provider.__call__`. Lock chỉ ở đường lạnh
(startup), nên không đánh đổi tốc độ lấy an toàn.

### 1.5 Phạm vi thay đổi

**Code (1 file lõi):**

- `xime/core/container/registry.py` - viết lại thân, bỏ `import dependency_injector`,
  `hashlib`, `re`. Giữ chữ ký `register()` / `get()`.

**Cấu hình (CHỜ chủ dự án đồng ý trước khi sửa):**

- `pyproject.toml` - bỏ dòng `dependency-injector>=4.41.0`.

**Tài liệu (sửa câu chữ nhắc tên thư viện):**

- `xime/core/container/__init__.py` (docstring bước 7 "Register providers into
  python-dependency-injector").
- `CLAUDE.md` gốc (dòng mô tả `container/` và mục thư viện nền tảng).
- `xime framework/CLAUDE.md`, `.claude/CLAUDE.md` (ghi chú DI container).
- `README.md` / `README-vn.md` (mục "Why not dependency-injector").
- `docs/{en,vn}/contributing.md`, `docs/{en,vn}/core-concepts.md`,
  `docs/{en,vn}/architecture.md`.
- `.claude/docs/lo-trinh-phien-ban.md` (đánh dấu 0.6 Việc 1 done).

### 1.6 Test & benchmark

- **Hồi quy:** chạy toàn bộ `pytest tests_temp/` - giữ 1051 passed / 4 skipped.
  Trọng tâm `tests_temp/DI/` (đặc biệt `test_05_manual_registration.py` ca
  `ServiceWithoutHint` phải vẫn raise `TypeError` lúc `get()` vì param thiếu hint
  không được inject) và `tests_temp/bootstrap/`.
- **Test mới cho registry:** singleton trả cùng instance; Object instance trả
  nguyên (kể cả giá trị `None`); factory method được gọi đúng; `get()` class lạ
  raise `KeyError`; nhiều coroutine cùng `get()` một class chưa warm chỉ tạo 1
  instance (đua lock).
- **Micro-benchmark đối chiếu:** script dựng N=500 class giả, đo (a) thời gian
  build/eager, (b) throughput `get()` warm; so bản cũ vs mới. Kỳ vọng: build
  nhanh hơn (bỏ md5+regex), `get()` warm ngang hoặc nhanh hơn.

### 1.7 Rủi ro & rollback

- Rủi ro thấp: thay đổi cô lập 1 file, API không đổi, test phủ dày.
- Soi kỹ thứ tự ưu tiên instance/override (không để singleton scan ghi đè
  `register_instance`) - xử lý bằng `if cls in self._instances: continue`.
- Rollback: revert đúng 1 commit (registry + pyproject), không lan ra service nào.

### 1.8 Ước lượng

Khoảng nửa ngày đến một ngày: ~60-90 phút viết lại registry, ~1-2h test mới +
benchmark, còn lại dọn docs và chạy full suite.

### 1.9 Checklist Việc 1

- [x] Viết lại `registry.py` theo thiết kế 1.3 (bỏ `dependency_injector`,
      `hashlib`, `re`; giữ chữ ký `register()` / `get()`).
- [x] Thêm guard đệ quy `_building` + sentinel `_MISSING` + `RLock`
      double-checked.
- [x] Giữ quy tắc không ghi đè instance/override bằng singleton scan.
- [x] Chạy `pytest tests_temp/` - 1062 passed / 4 skipped (1051 cũ + 11 test
      mới), không sửa test cũ.
- [x] Viết test mới cho registry (`tests_temp/DI/test_06_registry.py`: singleton,
      Object=None, factory method, KeyError, đua lock đồng thời).
- [x] Viết micro-benchmark đối chiếu (`tests_temp/DI/benchmark_registry.py`):
      N=500, build ~8.4x nhanh hơn, warm get() ~2.07x nhanh hơn backend cũ.
- [x] Gỡ `dependency-injector` khỏi `pyproject.toml`, cài lại môi trường sạch,
      chạy lại full suite.
- [x] Dọn tài liệu nhắc tên thư viện (mục 1.5).
- [x] Cập nhật `lo-trinh-phien-ban.md`: 0.6 Việc 1 = done.
- [ ] Bump version + CHANGELOG (theo quy ước bản trước) - **chờ chốt phát hành**.

---

## VIỆC 2 - Dynamic Interface Binding (đổi implementation lúc runtime)

> Thiết kế **CHỐT 2026-06-23**. Hướng do chủ dự án định: **mở rộng chính `bind`
> hiện có**, KHÔNG thêm `bind_many`, KHÔNG thêm handle `Switchable`; không phá
> kiến trúc cũ. Code sau (dự kiến vài hôm nữa). Nền phân tích cũ ở
> `wishlist-tinh-nang.md` (mục "Dynamic interface binding") - lưu ý API ở đó đã bị
> thay bằng thiết kế dưới đây.

### 2.1 Nguyên tắc nền (chủ dự án chốt)

- **KHÔNG tạo API mới** ngoài một class `Switcher`. `bind` cũ giữ nguyên chữ ký,
  chỉ **mở rộng kiểu của value**.
- **Dự án cũ không phải sửa gì** - mọi interface cũ đều 1 impl, hành vi y hệt dù
  bật hay tắt tính năng.
- **Mở rộng chính từ điển binding hiện tại**: value là một class (1 impl, như cũ)
  HOẶC một **tuple nhiều class** (>=2 impl). **Phần tử đầu tuple = mặc định.**
- **Bật/tắt bằng một cờ ở runtime config (YAML), mặc định TẮT.**

### 2.2 Bốn quyết định đã chốt

| # | Quyết định | Chọn |
| --- | --- | --- |
| Q1 | Consumer thấy impl đổi động qua đâu | **Proxy trong suốt** (consumer giữ nguyên code) |
| Q2 | Phạm vi đổi | **Chỉ global** (không request-scope, không ContextVar) |
| Q3 | Vòng đời các impl | **Eager** - khi bật cờ, mọi impl trong tuple là singleton dựng lúc startup |
| Q4 | `switcher.reset` | **Cả hai dạng**: `reset(Interface)` cho một, `reset()` cho tất cả |

Cấu trúc lưu trữ: vẫn là `dict` binding cũ, value = `type` (1 impl) hoặc
`tuple[type, ...]` (nhiều impl). Không có cấu trúc dữ liệu mới.

### 2.3 Cách hoạt động chi tiết

**a) Khai báo - mở rộng `bind`, không thêm method.**

```python
# config/dependency.py
dependency.bind({
    UserRepository: JpaUserRepository,                            # 1 impl, y hệt cũ
    PaymentGateway: (StripeGateway, PaypalGateway, MockGateway),  # nhiều impl, đầu = mặc định
})
```

**b) Cờ runtime config (mặc định tắt).**

```yaml
# resources/application.yml
xime:
  di:
    dynamic-binding: false     # mặc định; bật = true
```

Ba nhánh hành vi:

| value | cờ | Hành vi |
| --- | --- | --- |
| `type` (1 impl) | bất kỳ | Y hệt hiện tại (cờ không liên quan). |
| `tuple` | **TẮT** | Dùng **phần tử đầu**, inject tĩnh y như `bind` 1-1; các impl còn lại **bỏ qua hoàn toàn** (không dựng). ⇒ hành vi == kiến trúc cũ. |
| `tuple` | **BẬT** | Kích hoạt đổi động: inject **proxy** thay impl cụ thể. |

**c) Consumer KHÔNG đổi code** (cả khi bật lẫn tắt):

```python
class CheckoutService:
    def __init__(self, gateway: PaymentGateway):     # như code cũ
        self.gateway = gateway
    async def pay(self, amount):
        return await self.gateway.charge(amount)     # như code cũ
```

**d) Proxy trong suốt (Q1).** Khi cờ bật + value là tuple, framework inject một
proxy implement Interface (một proxy singleton cho mỗi interface) thay cho impl cụ
thể. Mọi truy cập forward tới impl hiện hành đọc từ con trỏ global:

```text
self.gateway.charge(x)
  → _DynamicProxy(PaymentGateway).__getattr__("charge")
  → registry.get(_current[PaymentGateway]).charge(x)
```

Method async forward tự nhiên (proxy trả bound method của impl, `await` như
thường). **Cần kiểm lúc code:** `__getattr__` không bắt dunder gọi qua cú pháp
đặc biệt (`async with`, `for`, `len()`...) và `isinstance(proxy, Interface)` sẽ
sai - liệt kê và forward thủ công nếu service thực tế cần (đa số chỉ gọi method
thường nên thường không vướng).

**e) `Switcher` - API mới duy nhất (injectable).**

```python
class AdminService:
    def __init__(self, switcher: Switcher):
        self.switcher = switcher

    def failover(self):
        self.switcher.use(PaymentGateway, PaypalGateway)  # cả app dùng Paypal
        self.switcher.reset(PaymentGateway)               # một interface về mặc định
        self.switcher.reset()                             # MỌI interface về mặc định
```

- `use(Interface, Impl)`: validate `Impl` thuộc tuple của `Interface` (lỗi nếu
  không thuộc / `Interface` không phải tuple / cờ đang tắt) → gán
  `_current[Interface] = Impl`.
- `reset(Interface)`: `_current[Interface] = tuple[0]`.
- `reset()`: đưa **mọi** interface về `tuple[0]`.

**f) Vòng đời (Q3 eager).** Khi cờ bật, **mọi** impl trong tuple được đăng ký
singleton, dựng lúc startup, chạy `PostConstruct`; `PreDestroy` lúc shutdown. Đổi
con trỏ KHÔNG đụng lifecycle - mọi impl luôn sống suốt vòng đời app. (Cờ tắt: chỉ
phần tử đầu được đăng ký, các impl phụ không dựng.)

**g) Thread / async safety (Q2 chỉ global).** `_current[Interface] = Impl` là gán
dict - atomic trong CPython (GIL), đọc atomic, **không cần lock**. Không có
ContextVar, không request-scope.

**h) Validate fail-fast** (chỉ khi cờ bật + value tuple):

- **Mọi** impl trong tuple phải thỏa Protocol Interface (mở rộng
  `validator._check_bindings` để duyệt tuple). Sai một cái → startup fail.
- Value tuple là binding tường minh → **không** đụng rule multiple-candidate (rule
  đó chỉ bắn khi Protocol không có binding; ở đây đã có).
- Tuple một phần tử → xử lý như 1 impl (không có gì để switch).

### 2.4 Phạm vi thay đổi dự kiến

- **`core/config/binding.py`** - `bind` chấp nhận value `type | tuple[type, ...]`;
  lưu nguyên trong dict cũ; property `bindings` trả cả dạng tuple. **Không thêm
  method mới.**
- **Nơi đọc runtime config** (vd `core/config/runtime.py`) - đọc cờ
  `xime.di.dynamic-binding` (mặc định `False`), truyền vào pipeline build.
- **`core/container/proxy.py`** (file mới, nhỏ) - `_DynamicProxy` giữ `interface`
  cùng tham chiếu state; `__getattr__` forward tới `registry.get(_current[interface])`.
- **`core/container/switcher.py`** (file mới) - `Switcher` với `use(interface, impl)`
  / `reset(interface)` / `reset()`; validate `impl` thuộc tuple. Đăng ký singleton
  (qua `register_instance`) để inject được.
- **`core/container/registry.py` hoặc state riêng** - `_current: dict[type, type]`
  (khởi tạo = `tuple[0]`) + bảng tuple gốc cho mỗi interface. Cân nhắc tách lớp
  `DynamicBindingState` để registry singleton không phình.
- **`core/container/resolver.py`** - khi value của interface là tuple:
  cờ tắt → resolve thành `tuple[0]` (như binding 1-1 cũ); cờ bật → resolve thành
  **proxy** của interface (đăng ký proxy như một instance cho key interface).
- **`core/container/validator.py`** - mở rộng `_check_bindings` duyệt mọi impl
  trong tuple (cờ bật) phải thỏa Protocol.
- **`__init__.py` (XimeContainer)** - nhận cờ + binding dạng tuple; cờ bật → đăng
  ký mọi impl tuple làm singleton (eager + lifecycle) + đăng ký proxy + `Switcher`;
  cờ tắt → chỉ phần tử đầu.
- **Bootstrap (`orchestrator.py`)** - lấy cờ từ `RuntimeConfig`, truyền vào
  `container.build()`.
- **`core/context/`** - KHÔNG đụng (chỉ global, không request-scope).
- **Teardown** - không đổi; mọi impl là singleton thường, đổi con trỏ không
  tạo/hủy instance.

### 2.5 Checklist Việc 2

> **ĐÃ CODE XONG 2026-06-23.** Toàn bộ mục dưới hoàn tất; full suite **1084
> passed / 4 skipped** (1062 cũ + 22 test mới `tests_temp/DI/test_07_dynamic_binding.py`).

- [x] `bind` chấp nhận value `tuple` (binding.py) + property giữ nguyên dạng tuple.
- [x] Đọc cờ `xime.di.dynamic-binding` (mặc định false), truyền vào `build()` qua
      `XimeContainer.dynamic_binding(enabled)` (orchestrator đọc từ `RuntimeConfig`).
- [x] `DynamicProxy.__getattr__` forward tới impl hiện hành. Dùng `__slots__`;
      chặn tên hook lifecycle (`post_construct`/`pre_destroy`) để proxy KHÔNG bị
      `isinstance(proxy, PostConstruct/PreDestroy)` nhận nhầm (tránh chạy hook 2 lần).
- [x] `Switcher`: `use` / `reset(Interface)` / `reset()` + validate impl thuộc
      tuple; đăng ký singleton (luôn đăng ký - xem ghi chú 2.7).
- [x] State `_current` + mặc định = `tuple[0]`; gán atomic, không lock (ở `Switcher`).
- [x] Chuẩn hóa binding: tuple + cờ tắt → phần tử đầu; tuple + cờ bật → proxy.
      Làm trong `_prepare_dynamic_binding()` ở `build()`, **không sửa resolver.py**
      (xem ghi chú 2.7).
- [x] Cờ bật → đăng ký mọi impl tuple làm singleton (eager + PostConstruct/
      PreDestroy); cờ tắt → KHÔNG auto-register (impl phụ không dựng; phần tử đầu
      do app scan/register như binding cổ điển - xem ghi chú 2.7).
- [x] Validator: mọi impl trong tuple thỏa Protocol (cờ bật) - mở rộng
      `_check_bindings` duyệt tuple.
- [x] Test: **cờ tắt == hành vi cũ** (tuple dùng phần tử đầu, impl phụ không dựng);
      cờ bật + `use` đổi cho mọi consumer; `reset(Interface)` + `reset()` toàn bộ;
      `use` impl ngoài tuple → lỗi; `use` khi cờ tắt → lỗi rõ; startup fail nếu impl
      tuple không thỏa Protocol; proxy không bị nhận là lifecycle component; đầu-cuối
      cờ YAML qua orchestrator; **consumer code cũ không đổi vẫn chạy cả hai chế độ**.
- [x] Cập nhật `rules/interface-binding.md` (value tuple + cờ + proxy + `Switcher`
      + hướng dẫn dùng ở 2.6) và docs.
- [x] Cập nhật `lo-trinh-phien-ban.md`: 0.6 Việc 2 = done.

### 2.7 Ghi chú thực thi (chênh so với thiết kế gốc, vẫn đúng nguyên tắc)

Ba điểm hiện thực khác mô tả ban đầu, đều theo hướng đơn giản/an toàn hơn và
KHÔNG đổi hành vi người dùng:

1. **Không sửa `resolver.py`.** Thay vì cho resolver hiểu tuple, việc chuẩn hóa
   binding dồn hết vào `_prepare_dynamic_binding()` (mục mới trong
   `core/container/__init__.py`): tách `singles`/`tuples`, sinh `resolver_bindings`
   (map Protocol→impl thuần, resolver cũ ăn nguyên không đổi) và
   `validation_bindings`. Resolver giữ nguyên 100%, ít điểm chạm hơn.
2. **`Switcher` LUÔN được đăng ký** (cả khi cờ tắt), nhưng ở trạng thái disabled:
   `use()/reset()` ném `SwitcherError` "Dynamic binding is disabled" nói rõ cách
   bật. Lý do: để "use khi cờ tắt → lỗi rõ" có chỗ phát sinh (nếu chỉ đăng ký khi
   bật thì consumer inject `Switcher` lúc tắt sẽ fail mơ hồ ở startup). Dùng
   `setdefault` nên không đè override test.
3. **Cờ tắt KHÔNG auto-register phần tử đầu.** Tuple-cờ-tắt ≡ `bind({Interface:
   first})` y hệt mọi mặt: app tự `scan`/`register` impl đầu như binding cổ điển
   (đúng tinh thần "== kiến trúc cũ"). Chỉ khi cờ BẬT framework mới tự đăng ký +
   eager-build MỌI impl trong tuple (vì lúc đó nó toàn quyền quản lý chúng). Tuple
   một phần tử `(A,)` quy về single binding (không có gì để switch).

Tên class proxy là `DynamicProxy` (không gạch dưới như `_DynamicProxy` ở bản nháp),
đặt ở `core/container/proxy.py`. `Switcher` + `SwitcherError` ở
`core/container/switcher.py`.

### 2.6 Hướng dẫn dùng - khi nào switcher toàn cục, khi nào router theo request

Tính năng này **chỉ toàn cục** (Q2). `switcher.use()` đổi con trỏ dùng chung cho
cả tiến trình, nên **mọi consumer / mọi request / mọi coroutine** thấy impl mới ở
lần gọi kế tiếp - kể cả request đang xử lý dở cũng bị chuyển giữa chừng (đúng bản
chất "toàn cục", không phải bug).

**Nguyên tắc chọn:** dùng switcher khi việc đổi là **quyết định mức hệ thống/vận
hành, áp cho mọi request, xảy ra thưa**. KHÔNG dùng khi việc chọn impl **phụ thuộc
dữ liệu của từng request** (và nhiều request cần khác nhau cùng lúc).

**Phù hợp (toàn cục):**

- Failover nhà cung cấp khi cổng chính chết (thanh toán/SMS/email -> dự phòng).
- Kill-switch / fallback khi quá tải: đổi impl "thật" sang "noop/đơn giản", rồi `reset()`.
- Đổi nhà cung cấp theo vận hành/hợp đồng; đổi feed dữ liệu khi nguồn chính hỏng.
- Maintenance mode (vd `StorageService` sang read-only tạm).
- Staging/test: gạt sang `MockGateway` cho cả hệ thống.

**KHÔNG phù hợp (phụ thuộc từng request) - đừng dùng switcher:**

- Chọn cổng thanh toán theo quốc gia/thẻ của từng đơn (VN -> VNPay, US -> Stripe) cùng lúc.
- Multi-tenant: mỗi tenant một backend, đồng thời.
- A/B testing per-user; chọn kênh noti theo preference từng user.
- Chọn thuật toán theo input (loại file, kích cỡ, ngôn ngữ).

Nhóm này phải **chọn bằng code theo dữ liệu**, đặt ở một lớp **selector/router**
nhận mọi impl qua DI - KHÔNG nhét `if/case` vào từng class implements (mỗi impl sẽ
phải biết về các impl khác, phá tách bạch):

```python
class PaymentRouter:
    def __init__(self, stripe: StripeGateway, vnpay: VnpayGateway, paypal: PaypalGateway):
        self._by_country = {"US": stripe, "VN": vnpay}
        self._default = paypal

    def for_order(self, order) -> PaymentGateway:
        return self._by_country.get(order.country, self._default)


class CheckoutService:
    def __init__(self, router: PaymentRouter):
        self.router = router

    async def pay(self, order):
        gateway = self.router.for_order(order)   # chọn theo dữ liệu request
        await gateway.charge(order.amount)
```

Router an toàn per-request vì không có state toàn cục bị đổi - mỗi lời gọi tự chọn
theo dữ liệu của nó. (`if/case` chỉ nằm *trong* một impl khi đó là biến thể nội bộ
của chính impl, không phải chọn giữa các impl.)

> **Đối chiếu Spring Boot:** Spring không có sẵn "switcher đổi impl toàn cục lúc
> runtime" (bean singleton tạo lúc startup); gần nhất là `@RefreshScope` của Spring
> Cloud (tái tạo bean khi refresh config, nặng hơn, không phải swap con trỏ). Phần
> router theo request thì Spring làm tự nhiên qua inject `Map<String, Interface>`
> (mọi bean impl, key = bean name) - chính là pattern `PaymentRouter` trên. Cơ chế
> holder + swap của Xime tự viết trong Spring được, nhưng việc framework hóa kèm
> proxy trong suốt (consumer giữ nguyên code) là phần Xime thêm giá trị.

---

## Thứ tự thực thi tổng

1. [x] Việc 1 - thay registry (mục 1.9) -> phát hành được độc lập. **Xong 2026-06-23.**
2. [x] Việc 2 - thiết kế (mục 2.3 -> 2.6) + code (mục 2.5, ghi chú 2.7).
   **Xong 2026-06-23.** Còn lại chung với Việc 1: bump version + CHANGELOG khi
   chốt phát hành 0.6.
