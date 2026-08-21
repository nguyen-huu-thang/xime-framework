# Chạy nhiều tiến trình (share_load)

[English](../en/multi-process.md) | **Tiếng Việt**

[← ProcessLink](process-link.md) · **Đa tiến trình** · [Testing →](testing.md)

---

Một tiến trình Python chỉ dùng được một nhân CPU. `share_load()` cho phép chạy
cùng một ứng dụng trên nhiều tiến trình, **không đổi một dòng code nghiệp vụ**.

> **Nguyên lý trung tâm: không id tiến trình nào xuất hiện trong code.**
> `main.py` khai *ứng dụng này CÓ những cửa nào*; cấu hình khai *tiến trình nào
> ĐANG mở cửa nào ở cổng nào*.

---

## Ứng dụng một tiến trình không phải sửa gì

Không gọi `share_load()` thì mọi thứ chạy y hệt hôm nay: `server.port`,
`grpc.port`, đối số trong constructor. Cả phần dưới đây là **thêm**, không phải
**thay**.

---

## `main.py`

```python
from xime.adapters.grpc import GrpcAdapter
from xime.adapters.web import WebAdapter
from xime.core.bootstrap import Application

import config

app = Application()
app.add_config(config)
app.use(WebAdapter()).use(GrpcAdapter("internal")).use(GrpcAdapter("external"))

if __name__ == "__main__":
    app.share_load().run()
```

⭐ **Ba dòng giữa nằm ở MỨC MODULE, không nằm trong `if __name__`.** Tiến trình
con **chạy lại chính file này** để dựng lại ứng dụng, và ở đó `__name__` là
`__mp_main__` nên khối `if` không kích hoạt. Đặt `use()` vào trong khối đó thì
con có một ứng dụng không adapter nào và DI rỗng.

Framework **cưỡng chế** điều này: `app` phải là một biến ở mức module của
`__main__`, không thì `share_load()` nổ kèm khuôn đúng.

### `add_config(config)` là bắt buộc, không phải cho đẹp

```python
# config/__init__.py
from config.dependency import dependency

from config import grpc, scheduler, web   # noqa: F401  - chạy configure_* lúc import

__all__ = ["dependency"]
```

Cơ chế dò cũ tìm package config qua `__main__.__spec__.parent`, mà giá trị đó
**khác ở tiến trình con**. Framework đi tìm sai chỗ rồi **im lặng** dùng một DI
rỗng: con khởi động được, không route nào, và không gì báo.

---

## ⚠ Code ở mức module chạy `N+1` lần

Tiến trình cha cũng chạy lại `main.py`, rồi mới rẽ nhánh ở `share_load()`. Nên
với `N` tiến trình con, mọi thứ nằm ngoài `if __name__ == "__main__":` chạy
**`N+1`** lần.

> **Mức module chỉ để KHAI BÁO, không để LÀM.**

| Ở mức module | |
|---|---|
| `import config`, `app = Application()`, `app.use(...)` | ✅ chưa mở gì cả |
| khai class, hằng số, kiểu dữ liệu | ✅ mỗi tiến trình dựng lại giống hệt nhau |
| **mở kết nối** (DB, Redis, MQTT, kênh gRPC, HTTP session) | ⛔ |
| **đọc/ghi file**, gọi mạng, lấy cert | ⛔ |
| **sinh giá trị không tất định** (`uuid4()`, `time.time()`, `os.getpid()`) | ⛔ |

⭐ **Hai nhóm cấm đó hỏng theo hai kiểu khác hẳn nhau**, và đó là lý do có hai
phép dò chứ không phải một:

| | Hỏng thế nào |
|---|---|
| Kết nối mở ở mức module | **thừa** - `N+1` kết nối thay vì một, nhưng mọi tiến trình vẫn đúng |
| `uuid4()` ở mức module | **sai** - mỗi tiến trình một giá trị khác, mà code đọc nó tin là cả cụm dùng chung |

```python
INSTANCE_ID = uuid4()          # ⛔ bốn tiến trình, bốn id, không ai biết
STARTED_AT  = time.time()      # ⛔ bốn mốc khác nhau
```

⚠ Điều tệ nhất của cả hai: **hôm nay chúng đúng, ngày mai chúng sai, mà code
không đổi.** Một tiến trình thì mọi thứ ở mức module chạy đúng một lần. Thêm
`count: 3` vào `application.yml` là cùng đoạn code đó chạy bốn lần - **thứ đổi
nằm ở file cấu hình, không nằm ở file có lỗi.**

Câu để tự kiểm: *nếu dòng này chạy bốn lần thay vì một, có gì hỏng hoặc lãng phí
không?*

### Phép dò 1 - `share_load()` đo thời gian

`share_load()` là điểm đầu tiên framework giành lại quyền điều khiển sau khi
code mức module chạy xong, nên nó đo được khoảng đó mà không cần biết bên trong
có gì. Quá **3 giây** thì cha kêu **một** dòng, đúng một lần cho cả cụm:

```text
Module-Level Code Is Heavy
  Measured: 6.1s from the first Xime import to share_load()
  Cost    : x5 (parent + 4 worker(s)) = 30.5s spent before serving
  Detail  : module-level code runs once per process. Move connections,
            file reads and network calls into post_construct(), run_once()
            or an adapter - the module level is for DECLARING only.
```

⭐ Con số một mình không nói được gì đáng làm; **phép nhân** mới là thứ khiến
người ta đi sửa.

⚠ **Phép dò này bắt cái ĐẮT, không bắt cái SAI.** Một `uuid4()` mất micro giây
nên nó không bao giờ thấy. Ngưỡng 3 giây cũng không phải con số đẹp: đo hai ứng
dụng thật và lành mạnh ngày 2026-08-20 ra **0,99s** và **1,05s**, nên một ngưỡng
thấp hơn sẽ kêu ở mọi lần khởi động - và một phép dò kêu oan là một phép dò sẽ
bị tắt.

### Phép dò 2 - `xime check module-level`

Bù đúng chỗ phép dò 1 mù. Quét tĩnh `main.py` và mọi module **trong dự án** mà
nó import ở mức module:

```bash
xime check module-level                 # tự tìm app/main.py, main.py, src/main.py
xime check module-level --main app/main.py --root .
```

```text
  app/config/dependency.py:14  uuid.uuid4()   RUN_ID = uuid4()

1 non-deterministic call(s) at module level, across 174 file(s).
```

Nó soi cả ba chỗ dễ quên mà vẫn chạy lúc import: **thân class**
(`class C: ID = uuid4()`), **decorator**, và **giá trị mặc định của tham số**
(`def f(at=time.time())`). Khối `if __name__ == "__main__":` thì không - đó là
khối duy nhất **không** chạy ở tiến trình con.

⭐ **Ba mã thoát, không phải hai:**

| | |
|---|---|
| `0` | sạch |
| `1` | có vi phạm |
| `2` | **chưa kết luận được** - không tìm thấy điểm vào, hoặc có file không parse được |

⚠ Mã `2` tồn tại vì *"không tìm thấy vi phạm"* và *"không đọc được để mà tìm"* là
hai câu trả lời khác nhau. Gộp chúng lại là để một lần chạy trong CI báo xanh
trên một phép kiểm chưa hề chạy.

⚠ **Đây là phép dò theo DANH SÁCH TÊN, nên con số 0 của nó không chứng minh được
gì.** Nó không thấy một hàm của bạn gọi `uuid4()` bên trong, và không thấy một
thư viện bên thứ ba tự sinh giá trị. Hai phép dò **không thay thế nhau**: một
cái đo *hậu quả* mà không biết nguyên nhân, cái kia tìm *nguyên nhân* theo tên
mà không thấy hậu quả.

---

## Một hình dạng cấu hình, hai cách viết

> **`process:` là một khối. `processes:` là nhiều khối có tên. Bên trong hai cái
> giống hệt nhau.**

### Một tiến trình - `process:`

```yaml
process:
  web:
    public:   { host: 0.0.0.0,   port: 8086 }
    admin:    { host: 127.0.0.1, port: 8081 }
  grpc:
    internal: { host: 127.0.0.1, port: 9095 }
```

Một tiến trình, ba cổng. ⭐ **Lặp `use(WebAdapter(...))` là có thêm một server
web** - chuyện đó không liên quan gì tới số tiến trình. `public` và `admin` là id
lập trình viên đặt trong `main.py`, và cấu hình chỉ được nói về những cái tên đó.

### Nhiều tiến trình - `processes:`

```yaml
processes:
  main:
    primary: true
    web:
      public:   { host: 0.0.0.0,   port: 8086, shared: true }
      admin:    { host: 127.0.0.1, port: 8081 }
    grpc:
      internal: { host: 127.0.0.1, port: 9095 }

  api-2:
    web:
      public:   { host: 0.0.0.0,   port: 8086, shared: true }
      admin:    { host: 127.0.0.1, port: 8082 }
    grpc:
      internal: { host: 127.0.0.1, port: 9096 }
```

| | |
|---|---|
| **`web.public` trùng cổng 8086 ở hai khối** | Trùng **đúng ở vị trí `use` mang id `public`**, và cả hai khai `shared: true`. Kernel chia request giữa hai tiến trình |
| **`web.admin` KHÔNG trùng** (8081 và 8082) | Không khai `shared` thì mỗi tiến trình một cổng riêng - hai địa chỉ khác nhau thì không va nhau |

Đi từ một sang nhiều: đổi `process:` thành `processes:`, thụt vào một cấp, đặt
tên, nhân bản khối, thêm `shared` ở cổng muốn dùng chung, và đổi `run()` thành
`share_load().run()`. **Không sửa lại gì bên trong.**

### Khoá của một ô

| Khoá | Cho adapter nào | Ghi chú |
|---|---|---|
| `host` | web, grpc | Để trống thì lấy mặc định của adapter |
| `port` | web, grpc | |
| `path` | socket | Thay cho `host`/`port`; để trống thì suy `<socket.dir>/<id>.sock` |
| `ssl` / `tls` | web / grpc | Để trống thì **kế thừa khối chung** (`server.ssl` / `grpc.tls`) - xem dưới |
| `shared` | web, grpc, socket | **Chỉ ở `processes:`** - xem ngay dưới |

Khoá cấp tiến trình: `primary` (đúng **một** khối khai) và `count`.

### Ba khoá vô nghĩa với một tiến trình, và framework BÁO LỖI

| Khoá | Vì sao lỗi |
|---|---|
| `primary` | Tiến trình duy nhất luôn là primary. Khai một thứ đã đúng sẵn |
| `count` | Không gọi `share_load()` thì không gì sinh con |
| `shared` | Dùng chung một địa chỉ đòi **ít nhất hai tiến trình** - một mình thì không có ai để chia |

Không bỏ qua im lặng: một khoá bị bỏ qua im lặng là chỗ để người ta tin vào thứ
không xảy ra.

### Vì sao `shared` phải khai tường minh

*"Bind thành công"* mang **hai nghĩa**: *tôi độc chiếm cổng này* và *tôi đang
chia cổng với người khác*. Khai nhầm trùng cổng thì Windows báo lỗi ngay, còn
Linux chạy êm (gRPC bật `SO_REUSEPORT` mặc định) và **một nửa request đi vào tiến
trình không ai định gửi tới**.

### TLS: ô trước, khối chung sau

Ô không khai `ssl` / `tls` thì điểm phục vụ **kế thừa khối chung** - web lấy
`server.ssl`, gRPC lấy `grpc.tls`. Đó là một tính chất bảo mật chứ không phải
tiện lợi: một server phụ **âm thầm chạy HTTP** trong khi server chính đã HTTPS là
lỗ hổng không ai để ý, vì nó vẫn trả lời 200. Ở gRPC còn đắt hơn - một endpoint
tụt xuống plaintext **vẫn nhận client không có cert**, nên bên gọi cũ không hề
gãy và không ai biết lớp lọc theo CN của client vừa mất đối tượng để xét.

Muốn một điểm phục vụ cố ý chạy không mã hoá thì khai rỗng, tường minh:

```yaml
process:
  web:
    public:   { port: 8086 }                # kế thừa server.ssl
    internal: { port: 8082, ssl: {} }       # cố ý HTTP thuần
  grpc:
    noi_bo:    { port: 9095 }               # kế thừa grpc.tls
    cong_khai: { port: 9096, tls: {} }      # cố ý plaintext
```

⚠ **Ô thắng khối chung, không phải ngược lại.** Ô khai `tls` gì thì dùng đúng cái
đó; khối chung chỉ lên tiếng khi ô im lặng.

> ⭐ **Bản 0.8 đầu tiên KHÔNG có đường kế thừa cho gRPC**, và đó là một lỗ hổng
> thật: người di trú từ khoá phẳng sang `process:` theo đúng lời tài liệu này thì
> **mất mTLS**, dấu hiệu duy nhất là một dòng WARNING lẫn trong log khởi động.
> `Base Platform/data` báo ngày 2026-08-21, tái hiện được hai chiều. Nay hai
> đường đã hành xử giống nhau.

### Khoá phẳng cũ vẫn chạy nguyên

```yaml
server:
  port: 8086
  ssl: { certfile: ..., keyfile: ... }
```

Đây là **một phép dịch** thành `process.web.default`, không phải một nhánh xử lý
thứ hai - dịch xong thì từ đó trở đi chỉ còn một đường code. App một cổng không
phải sửa gì. Muốn cổng thứ hai thì viết `process:`.

### Viết gọn N tiến trình giống hệt nhau

```yaml
processes:
  main:
    primary: true
    web: { default: { port: 8086, shared: true } }

  workers:
    count: 3          # sinh workers-1, workers-2, workers-3
    web: { default: { port: 8086, shared: true } }
```

⚠ `count` đòi **mọi địa chỉ trong khối phải `shared: true`** - N tiến trình bung
ra từ một khối thì cùng bind một địa chỉ. Framework **không tự sinh dải cổng**:
tự sinh là để lại N cổng không ai đăng ký.

### Cái bẫy một chữ

`process` và `processes` khác nhau đúng một ký tự, nên framework bắt **cả hai
chiều**:

| Cấu hình | Code | |
|---|---|---|
| `process:` | `run()` | ✅ |
| `processes:` | `share_load().run()` | ✅ |
| `processes:` | `run()` | ⛔ *"khai nhiều tiến trình mà không gọi `share_load()`"* |
| `process:` | `share_load().run()` | ⛔ *"`share_load()` cần `processes:`"* |
| Cả hai cùng có | bất kỳ | ⛔ hai nguồn cho một giá trị |

---

## Ba nhánh của `run()`

| Điều kiện | `run()` làm gì |
|---|---|
| không gọi `share_load()` | đơn tiến trình, y hệt hôm nay |
| có `share_load()`, không có `XIME_PROCESS_ID` | **supervisor** |
| có `share_load()`, có `XIME_PROCESS_ID` | **worker** |

Nhánh thứ ba chạy khi cha sinh con, và cũng chạy khi bạn gỡ lỗi một tiến trình
bằng tay:

```bash
XIME_PROCESS_ID=api-2 python -m app.main
```

⚠ **Đừng đặt `XIME_PROCESS_ID` trong môi trường thường trực.** Framework tự đặt
nó khi sinh con; có sẵn trong shell thì `python -m app.main` chạy thành một
worker mồ côi thay vì dựng cả cụm.

---

## Tiến trình cha làm gì

```text
python -m app.main          (không đối số, không env)
│
├─ import config            -> registry được điền
├─ app = Application()      -> object rỗng, chưa mở gì
├─ app.use(...)             -> object adapter, CHƯA start, chưa chiếm cổng
│
└─ share_load().run()
   ├─ kiểm cấu hình
   ├─ DỌN vùng nhớ chung mồ côi của những lần chạy trước đã bị kill -9
   ├─ bind() + listen() những địa chỉ dùng chung (nếu có), chmod 0600 TRƯỚC listen()
   ├─ cấp vùng nhớ chung: RefData · ProcessLink · bảng nhịp watchdog
   ├─ sinh PRIMARY, rồi ĐỢI nó báo run_once() xong
   ├─ sinh những con còn lại
   └─ trông con: chết thì dựng lại và thăng cấp · treo thì giết · Ctrl+C thì tắt cả đàn
      KHÔNG accept() · KHÔNG dựng DI · KHÔNG chạy code nghiệp vụ
```

### Dọn rác lúc khởi động

Một tiến trình bị `kill -9` không kịp trả vùng nhớ chung, và trên Linux nó **nằm
lại trong `/dev/shm` tới lần khởi động máy**. Nên cha quét trước khi cấp vùng
mới: tên vùng mang **pid của người tạo**, nên câu *"còn ai giữ cái này không"*
trả lời được bằng một tín hiệu số 0.

Quét cả **ba họ**: `xime-link-` (bus), `xime-ref-` (RefData), `xime-beat-` (nhịp
watchdog).

⚠ Hệ điều hành **tái dùng pid**, nên thỉnh thoảng một vùng rác sống thêm một
vòng vì pid của nó tình cờ trùng một tiến trình đang chạy. Không cố giải chính
xác chuyện đó: giá không xứng với vài megabyte trong RAM.

✅ Xoá tên vùng **không phá** tiến trình đang ánh xạ nó - ánh xạ vẫn sống, chỉ là
không ai attach theo tên được nữa.

### Con chết đi chết lại: hãm luỹ tiến, nhưng không bao giờ bỏ cuộc

Con chết ngay lúc khởi động (cấu hình sai, cổng riêng bị chiếm, migration hỏng)
mà cha dựng lại mỗi giây thì mỗi lần là **import lại toàn bộ cây module** - đo
được khoảng 83 MB RSS và chừng một giây CPU. Đốt trọn một nhân, và dòng log là
một câu `WARNING` giống hệt nhau lặp mãi.

| Lần chết liên tiếp | Chờ trước khi dựng lại |
|---|---|
| 1 | 1 giây |
| 2 | 2 giây |
| 3 | 4 giây |
| ... | gấp đôi dần |
| từ đó | **trần 30 giây** |

Từ **lần thứ 10** thì log lên `CRITICAL`: lặp một `WARNING` giống hệt nhau là
cách chắc nhất để không ai đọc nó nữa.

⭐ **Bộ hãm về 0 khi một con sống được quá 60 giây** - qua được ngưỡng đó là một
con đã phục vụ, không phải một con đang giãy. Không có phép reset này thì một cụm
khoẻ, sau vài lần restart tình cờ trong nhiều tháng, sẽ chờ 30 giây mỗi lần.

✅ **Lời hứa "luôn dựng lại" giữ nguyên.** Đây là hãm nhịp, không phải từ bỏ: một
cụm hỏng vì cấu hình phải tự phục hồi ngay khi cấu hình được sửa.

Cha **không được chết**: con chết thì không ai dựng lại, và `Ctrl+C` không có chỗ
điều phối thứ tự tắt. Nó bắt `SIGINT`, `SIGTERM` (thứ `systemd` gửi) và
`SIGBREAK` trên Windows.

⭐ Lợi ích phụ: **cổng bị chiếm thì cha nổ ngay lúc khởi động**, thay vì bốn con
lần lượt nổ và bạn đọc bốn stack trace giống nhau.

---

## `run_once()` - việc chạy MỘT lần cho cả cụm

Một tiến trình thì *"chạy lúc khởi động"* chỉ có một nghĩa. Bốn tiến trình thì nó
có **hai**, và chúng ngược nhau:

| | Mọi tiến trình | **Một lần cho cả cụm** |
|---|---|---|
| **Chạy một lần rồi thôi** | `post_construct()` | **`run_once()`** |
| **Chạy mãi** | `Adapter.start()` | `scaling="singleton"` |

Trước 0.8 chỉ có cột trái, nên hai loại việc nằm chung `post_construct` - và
trong một cụm bốn tiến trình thì migration chạy bốn lần, email nhắc gửi bốn lần,
con trỏ đồng bộ tiến bốn lần.

```python
class KeyRefreshJob:
    async def post_construct(self) -> None:      # MỌI tiến trình, và phải NHẸ
        self._cache = {}

    async def run_once(self) -> None:            # MỘT lần cho cả cụm
        await self._refdata.publish(await self._trust.fetch_keys())
```

Không decorator, không khai ở `config/` - chỉ là **một tên method quy ước**, cùng
họ với `post_construct` và `pre_destroy`. Framework in ra lúc khởi động danh sách
nó tìm thấy, nên bạn vẫn nhìn được toàn cảnh mà không phải đọc code.

### Cha ĐỢI nó xong rồi mới sinh con tiếp theo

```text
CHA:  sinh PRIMARY
PRIM: attach vùng nhớ -> dựng DI -> post_construct -> RUN_ONCE -> báo cha xong
CHA:  nhận báo xong -> sinh những con còn lại
CON:  attach -> dựng DI -> post_construct -> (BỎ QUA run_once) -> adapter start
```

Đây là chỗ `run_once` khác một job *"chạy một lần"* của scheduler, và khác biệt
nằm ở **thời điểm**: job scheduler nghĩa là *chạy một lần vào một thời điểm*;
`run_once` nghĩa là **chạy một lần, và mọi thứ khác đợi nó**. Migration xong rồi
mới có con thứ hai mở kết nối.

⚠ Primary không báo xong trong 60 giây thì cha **đi tiếp kèm cảnh báo**, không
đứng mãi: một cụm không phục vụ gì tệ hơn một cụm chưa chạy xong migration.

### Hai ràng buộc phải nhớ

| | |
|---|---|
| **`run_once()` phải LẶP LẠI ĐƯỢC** | Primary chết giữa chừng thì con được thăng cấp **chạy lại** nó. Cha chỉ bỏ qua khi nó đã nhận tín hiệu *xong* |
| **Không có cặp huỷ** | `post_construct` có `pre_destroy`; `run_once` **cố ý không**. Lấy khoá, migration, tiêu thụ vé bootstrap - không cái nào có gì để dọn |

⚠ Ứng dụng **một tiến trình** cũng chạy `run_once()`: nó *là* cả cụm. Không có
nhánh nào để quên.

---

## Thăng cấp primary

Primary chết thì cha **trao vai cho một con đang chạy**, không đợi dựng một tiến
trình mới. Con đó khởi động những adapter hạng đơn nhất của nó và tiếp tục phục
vụ HTTP như trước.

```text
primary chết  ->  waitpid xác nhận đã exit  ->  cha chọn một con còn sống
              ->  gửi "bạn là primary" qua kênh nội bộ
              ->  con start() các adapter singleton  ->  báo lại "đã nhận"
```

### ⛔ Tín hiệu thăng cấp là `waitpid`, không phải health check

Đây là chỗ mô hình cha-con **miễn nhiễm** với một lỗi mà mọi hệ thống bầu chọn
đều phải xử lý: primary treo tạm (GC dài, đĩa chậm, swap) thì một health check
đọc là *"đã chết"*, cụm bầu con B, rồi A tỉnh lại và vẫn tin mình là primary.
**Hai primary cùng chạy job nền.**

Xime chỉ tin `waitpid` - **sự thật của kernel**, không phải suy đoán qua mạng.
Con treo thì cha **giết trước, đợi kernel xác nhận, rồi mới thăng cấp**; A không
thể tỉnh lại vì nó đã chết thật.

### ⭐ Lỗi `start()` lúc thăng cấp thì TỪ CHỐI VAI, không sập

Ca cụ thể: con B được thăng cấp, `start()` của job xoay cert ném lỗi vì cert
hỏng. Áp nguyên luật *"lỗi trong `start()` thì sập"* thì B sập, cha thăng cấp C,
C sập - và bạn mất ba tiến trình **đang phục vụ người dùng thật** vì một cái cert.

> **Lỗi `start()` lúc KHỞI ĐỘNG thì sập. Lỗi `start()` lúc THĂNG CẤP thì từ chối
> vai.** Con B vẫn phục vụ HTTP bình thường; nó chỉ không làm primary.

### Chống domino

Quá **3 lần thăng cấp trong 60 giây** thì cha **thôi cấp vai primary**, kêu to,
và cụm chạy tiếp **không có job nền**.

⚠ **Hai công tắc riêng, đừng nhầm:** *dựng lại con đã chết* thì **vẫn làm**; chỉ
*cấp vai primary* mới dừng. Mất job nền còn hơn mất khả năng phục vụ.

---

## Watchdog - phát hiện con TREO

`waitpid` thấy con **chết**. Nó không thấy con **treo**: một coroutine gọi I/O
đồng bộ, hoặc chạy một vòng lặp CPU dài, sẽ chặn cả event loop - tiến trình vẫn
sống theo kernel, và cụm âm thầm mất một tiến trình.

| | Health check | **Watchdog** |
|---|---|---|
| Chiều | Cha **hỏi**, con **trả lời** | Con **tự chứng minh**, cha chỉ đọc |
| Cha phải dựng gì | Client, timeout, retry | **Không gì** - đọc 8 byte |
| Con bận | Không trả lời được **dù vẫn khoẻ** | Vẫn vỗ được nếu loop còn quay |

Con ghi một mốc thời gian mỗi **1 giây**; im quá **10 giây** thì cha **giết**, và
sentinel của nó nổ ở vòng sau nên đường thăng cấp vẫn đi qua `waitpid`.

⚠ Con **chưa vỗ lần nào** là *đang khởi động*, không phải *treo* - cha cho nó 60
giây. Gộp hai nghĩa đó là giết mọi con ngay lúc chúng vừa sinh ra.

⛔ **Mốc thời gian dùng đồng hồ ĐƠN ĐIỆU (`monotonic`), không phải giờ tường.**
Giờ tường nhảy được: NTP kéo giờ, người vận hành sửa giờ, máy ảo khôi phục ảnh
chụp. Một cú nhảy **tiến 30 giây** làm khoảng-im-lặng của **mọi con đang khoẻ**
vọt lên trên ngưỡng cùng một lúc, nên cha giết cả đàn - rồi chống domino đếm đủ
ba lần thăng cấp và **dừng cấp vai primary vĩnh viễn**. Cả hai đầu của phép đo
(con ghi, cha đọc) phải dùng **cùng một đồng hồ**; chỉ sửa một đầu thì kết quả
là hiệu của hai hệ quy chiếu, ra một con số cỡ giờ epoch.

### Bạn không phải làm gì cả

Không API, không cấu hình. Nhịp vỗ là một task trên **event loop chính** của tiến
trình con, và framework tự dựng nó.

⚠ Chỗ đặt lệnh vỗ là một phần của **hợp đồng**: đặt ở một thread riêng thì nó chỉ
đo *"tiến trình còn tồn tại"* - thứ `waitpid` đã trả lời rồi - và watchdog sẽ
xanh mãi mãi. Framework có test canh đúng điều đó.

### Ai canh CHA: `systemd`

```ini
[Service]
Type=notify
WatchdogSec=30
ExecStart=/usr/bin/python -m app.main
```

Cha gửi `READY=1` khi cụm đã lên và `WATCHDOG=1` mỗi vòng giám sát. Không có
`NOTIFY_SOCKET` (chạy tay, Windows) thì nó **bỏ qua im lặng**.

⭐ Framework không tự viết một tiến trình canh cha, vì câu hỏi kế tiếp sẽ là *"ai
canh nó"*. Nguyên tắc mượn từ phần cứng: **watchdog không nằm trên con CPU nó
canh**.

⚠ Cha treo **không nguy như nghe**: nó không `accept()`, nên con vẫn phục vụ. Thứ
mất là khả năng **tự phục hồi**, và không ai thấy gì cho tới lần đầu có con chết.

---

## `/healthz` và `/readyz`

Mặc định **TẮT**. Khai một dòng thì có:

```python
# config/web.py
from xime.adapters.web import configure_health

configure_health()                                  # /healthz và /readyz
configure_health(healthz="/_alive", readyz=None)    # đường dẫn riêng, tắt bớt một
```

Không muốn endpoint thì đọc thẳng dữ liệu: `app.health()` luôn có, không phải
khai gì.

### ⚠ Hai đường dẫn trả lời HAI câu, đừng gộp

| | Câu hỏi | Ai đọc | Đỏ thì họ làm gì |
|---|---|---|---|
| `/healthz` | *"tiến trình này còn dùng được không"* | systemd, k8s | **restart** |
| `/readyz` | *"nhận request mới được không"* | load balancer | **rút khỏi vòng** |

Một adapter hỏng trong khi ba cái còn phục vụ thì LB **nên** rút tiến trình ra,
còn systemd thì **không nên** giết nó - giết là đổi *hỏng một phần* lấy *hỏng
toàn phần*, và mất luôn log.

### ⭐ Con phụ vẫn XANH khi cụm thiếu primary

`/readyz` hỏi *"nhận request mới được không"*, và con phụ **vẫn nhận được**; thứ
cụm mất khi không có primary là **job nền**. Trả lời ngược lại thì LB rút hết con
và cụm chết hoàn toàn vì một job nền không chạy.

Adapter hạng đơn nhất đang chờ ở con phụ nằm ở trạng thái `standby`, và `standby`
**không** làm `ready` đỏ. Thông tin *"cụm đang không có primary"* vẫn thấy được -
ở trường `primary` của chính phản hồi đó.

```json
{
  "alive": true,
  "ready": true,
  "primary": false,
  "adapters": [
    {"id": "default", "kind": "web", "state": "serving"},
    {"id": "default", "kind": "scheduler", "state": "standby"}
  ]
}
```

### ⛔ Hai đường dẫn này KHÔNG xác thực

Cố ý. Chúng phải trả lời được **khi mọi thứ khác đã hỏng**, kể cả khi không lấy
nổi khoá verify - một `/healthz` đòi token là một `/healthz` im lặng đúng lúc cần
nhất. Bù lại, thân phản hồi không mang gì nhạy cảm: không host, không cổng, không
phiên bản, không thông điệp lỗi.

⭐ Hình dạng an toàn nhất ở prod: đặt chúng trên một **server phụ chỉ nghe
`127.0.0.1`**. Người vận hành và systemd tới được, internet thì không.

---

## Adapter chỉ nhận ĐỊNH DANH, địa chỉ đến từ cấu hình

```python
app.use(WebAdapter("admin"))          # ✅ chỉ id
app.use(WebAdapter("admin", 8081))    # ⛔ TypeError - không còn đối số nào khác
```

Ba adapter phục vụ (`web`, `grpc`, `socket`) **bỏ hẳn** `host` / `port` / `ssl` /
`path` khỏi constructor ở 0.8. Hai lý do khác nhau:

| | |
|---|---|
| `host` / `port` / `path` | **Mô tả sự thật** - ở nhánh chia tải thì cha `bind()` rồi truyền socket xuống, nên con **không có cách nào tự chọn cổng**. Một đối số ở đó là lời hứa framework không giữ được |
| `ssl` | **Ngoại lệ hết lý do tồn tại** - nó sinh ra cho server phụ cần cert khác, mà server phụ nay có ô cấu hình riêng |

⭐ Bỏ hẳn đối số thì không cần phép kiểm nào: Python từ chối sẵn ở tầng chữ ký, và
*"người vận hành sửa YAML mà cổng không đổi"* thôi tồn tại.

---

## Mỗi adapter chia tải một kiểu

| Adapter | Cách chia một địa chỉ | Linux | Windows |
|---|---|---|---|
| **web** | cha giữ socket, truyền xuống con | ✅ | ✅ (xem ghi chú) |
| **socket** (unix) | cha giữ socket | ✅ | - |
| **grpc** | `SO_REUSEPORT` | ✅ | ⛔ **báo lỗi lúc khởi động** |
| mqtt, modbus, opcua | **hạng phân mảnh** - làm ở 0.8.1 | - | - |

`grpc.aio` chỉ nhận địa chỉ dạng chuỗi, không có API nhận socket từ ngoài, nên nó
không dùng được đường truyền socket. Windows không có `SO_REUSEPORT`, và framework
**nổ ngay lúc khởi động** thay vì để tiến trình thứ hai chết bằng `WinError 10048`
giữa chừng. Trên Windows thì cho mỗi tiến trình một cổng gRPC riêng - các adapter
khác vẫn chạy đa tiến trình bình thường.

### ⚠ Ghi chú Windows: framework tự đổi kiểu event loop

Tiến trình con nào **kế thừa socket dùng chung** trên Windows sẽ chạy trên
**selector event loop** thay vì proactor mặc định, và framework ghi một dòng
`WARNING` nói rõ.

Lý do: liên kết IOCP thuộc về **socket của kernel**, không thuộc về **handle**.
Tiến trình thứ nhất gắn socket vào IOCP của nó xong thì tiến trình thứ hai không
gắn được nữa - nó khởi động thành công, log *"serving"*, rồi **không nhận nổi một
kết nối nào**. Selector loop `accept()` thẳng nên không vướng.

Cái giá: `select()` trên Windows giới hạn 512 socket, và loop đó không chạy được
subprocess. Chấp nhận được vì Windows là máy dev; prod chạy Linux, nơi `epoll`
không có giới hạn này.

### Adapter phân mảnh (mqtt, modbus, opcua)

Ba adapter này **không nhân bản được bằng cách nhân đôi kết nối**: hai tiến trình
cùng poll một PLC là nhân đôi tải lên thiết bị thật, và hai client MQTT cùng
`client_id` thì broker đá phiên cũ ra. Mỗi tiến trình phải giữ một **phần khác
nhau**, và hình dạng cấu hình cho việc đó làm ở **0.8.1**. Tới lúc đó, ứng dụng
dùng chúng thì chạy một tiến trình.

---

## Bốn phép kiểm lúc khởi động

Cả bốn chạy trong **một tiến trình**, không cần phối hợp, vì mọi tiến trình đọc
cùng một file.

| # | Kiểm | Kết cục |
|---|---|---|
| 1 | Không khối nào `primary: true`, hoặc có hai | **lỗi** |
| 2 | Tên trong cấu hình mà `main.py` không khai | **lỗi** - chắc chắn gõ sai |
| 3 | Adapter khai trong `main.py` mà khối này không có | **bỏ qua** + một dòng `WARNING` |
| 4 | Một địa chỉ dùng ở hai khối mà không khai `shared` | **lỗi** |

### Đọc log khởi động: mỗi điểm phục vụ để lại một dòng, kèm chế độ bảo mật

Mỗi adapter bind xong ghi **một dòng `INFO`** nói nó lên ở đâu và **đang chạy chế
độ nào**:

```text
INFO | web default: process main serving on 0.0.0.0:8086 (HTTPS+mTLS)
INFO | grpc default: process main serving on 0.0.0.0:9095 (mTLS)
INFO | socket default: process main serving on /run/x.sock (0600, any uid)
```

Chế độ nằm **cùng dòng** với địa chỉ chứ không tách thành cảnh báo riêng, vì
người vận hành đọc log khởi động để trả lời *"cái gì đã lên"* - họ thấy dòng này
**mỗi lần**, ở đúng chỗ đang tìm. Bắt người ta nhận ra **sự vắng mặt** của một
cảnh báo là một phép đo không ai làm được.

| Adapter | Chế độ có thể thấy |
|---|---|
| `web` | `HTTP` · `HTTPS` · `HTTPS+mTLS` |
| `grpc` | `PLAINTEXT` · `TLS` · `mTLS` |
| `socket` | quyền file + `any uid` hoặc danh sách uid được phép |

⚠ Dòng của `socket` nói `any uid` khi `allowed_uids` để trống - lúc đó **quyền
file là chốt chặn duy nhất**, và câu đó đáng hiện ra thay vì phải suy từ chỗ
trống.

> ⭐ **Trước bản này, gRPC chỉ log khi có chuyện, và `socket` không log gì cả.**
> Nghĩa là một cụm gRPC **khoẻ** sinh ra log **giống hệt** một cụm gRPC **hỏng**:
> trạng thái tốt không để lại dấu vết nào để đối chiếu. Báo từ `Base Platform/data`
> ngày 2026-08-21, cùng đợt với lỗ TLS ở trên - và hai chuyện **cộng hưởng**, vì
> khi mọi thứ log nói về gRPC đều là cảnh báo thì không có mốc dương nào để so.

Kèm ba phép kiểm nữa quanh chuyện *bật nhầm nhánh*:

- `processes:` có mà không gọi `share_load()` -> lỗi.
- `share_load()` mà không có `processes:` -> lỗi.
- `share_load()` mà không adapter nào -> lỗi.

⭐ Phép kiểm 2 bắt được thứ mô hình cũ không bắt được: gõ `web: publik` thay vì
`public` thì hôm nay là một server im lặng không có controller nào.

---

## ⚠ Nhiều MÁY (Docker, k8s) - "cụm" ở đây nghĩa là gì

Mọi thứ trên trang này nói về **nhóm tiến trình bên trong MỘT máy**: cha sinh con
bằng `multiprocessing`, trông chúng bằng `waitpid`, và chia bộ nhớ bằng
`shared_memory`. Cả ba dừng ở ranh giới một máy - **một container cũng là một
máy**.

⭐ Đó **không phải một giới hạn tạm thời**, nó là cơ chế: một vùng `shared_memory`
và một file LMDB không bắc qua máy được, và một thứ bắc qua được thì đã là một
công nghệ khác.

Chạy `N` bản sao (k8s Deployment, Docker Compose `scale`, nhiều VPS) là hoàn toàn
bình thường - chỉ cần đọc đúng bảng này:

| | Phạm vi thật |
|---|---|
| `share_load()`, `count:`, thăng cấp primary, watchdog | **mỗi máy một cụm riêng** |
| `RefData`, `Store`, `ProcessLink` | **mỗi máy một bản riêng** |
| `run_once()`, adapter `scaling="singleton"` | **mỗi máy một lần** |
| `CacheService` (Redis) | **dùng chung giữa các máy** |

### ⛔ Cái bẫy: `run_once()` chạy MỖI MÁY một lần

`run_once()` khai là *"một lần cho cả cụm"*, và với ba pod thì *"cụm"* là **ba
cụm**, không phải một.

```text
1 máy, count: 4        ->  run_once() chạy 1 lần
3 pod, mỗi pod count: 4 ->  run_once() chạy 3 lần, song song
```

⚠ Nên **đừng đặt migration cơ sở dữ liệu vào `run_once()` nếu bạn chạy nhiều bản
sao**. Framework không có cách nào ngăn - nó không biết pod kia tồn tại.

✅ Cần *"một lần cho toàn hệ thống"* thì đó là bài toán khác, và nó cần một khoá
mà **mọi máy cùng thấy**: `CacheService` + `SET NX`, khoá advisory của database,
hoặc một Job riêng chạy trước Deployment. Bảng chọn: [Starters](starters.md).

### Cổng và bộ cân bằng tải

Trong một máy, framework **tự chia** một cổng cho N tiến trình (cha giữ socket,
hoặc `SO_REUSEPORT`). Giữa các máy thì đó là việc của tầng ngoài - k8s Service,
nginx, hay bất cứ thứ gì bạn đang dùng. Framework không đụng vào, và cố ý:
*đừng viết bộ cân bằng tải*.

---

## Những gì chưa có ở 0.8

| | |
|---|---|
| **Nâng cấp code không downtime** | Cha giữ socket nên đổi code của cha đòi restart cha, và restart cha là đứt kết nối. Đường ra đã biết (`exec` bản mới kế thừa fd, như nginx), chưa làm |
| **Cha nói ra ngoài** | Cha ghi log, nhưng nó chưa có một đường báo động hay một `/healthz` tổng cho cả cụm. Cảnh báo *"một con từ chối vai primary"* hôm nay tới được journald, **không tới được người** |
| **Tắt êm** | Con đang xử lý dở một request thì vẫn bị `terminate()` sau thời gian ân hạn |
| **Chia tải fieldbus và MQTT** | Chữ ký đã chốt ở 0.8, thi công ở **0.8.1** |

⚠ Dòng thứ hai là chỗ dễ tin nhầm nhất: mọi thứ ở trên **đã báo đúng** vào log
của cha, nên `journalctl -u app` thấy hết. Thứ chưa có là đường đẩy chúng tới một
hệ thống giám sát.

---

## Viết adapter của riêng bạn

Hợp đồng đổi ở 0.8, và `app.use(...)` **kiểm ngay tại dòng đó**:

```python
from xime.core.bootstrap.adapter import Adapter

class MyAdapter(Adapter, scaling="replicated"):
    adapter_kind = "my"                      # khoá tầng hai trong processes:

    def __init__(self, server_id: str = "default") -> None:
        self.adapter_id = server_id

    async def start(self, app) -> None:      # chiếm tài nguyên, TRẢ VỀ khi xong
        ...

    async def serve(self) -> None:           # phục vụ, CHẶN tới khi bị dừng
        ...

    async def stop(self) -> None:            # phải idempotent
        ...
```

### Vì sao tách `start()` khỏi `serve()`

`start()` gộp hai việc thì **không có chỗ nào nói *"xong bước chiếm tài
nguyên"***, trong khi ba việc cùng cần câu đó: cha biết khi nào sinh con tiếp
theo · phân biệt lỗi *"chưa phục vụ được"* với lỗi *"đang phục vụ thì hỏng"* ·
và `/readyz`.

⭐ Nó **không ép hình dạng mới**: gRPC đã có `start()` + `wait_for_termination()`,
uvicorn đã có `startup()` + `main_loop()`, asyncio đã có `start_unix_server()` +
`serve_forever()`. Framework chỉ thôi che giấu cấu trúc vốn có.

| Lỗi ném ra từ | Framework làm gì |
|---|---|
| `start()` | **Sập cả tiến trình** - chưa phục vụ được thì đi tiếp là vô nghĩa |
| `serve()` | **Cô lập adapter đó**, log `CRITICAL`, anh em chạy tiếp |

✅ **Adapter cuối cùng chết thì tiến trình vẫn sống.** Còn sống thì `/healthz`
còn trả lời được, log còn đọc được, còn gỡ lỗi được.

### `scaling` bắt buộc khai

| Giá trị | Nghĩa | Framework làm gì |
|---|---|---|
| `"replicated"` | N bản giống hệt, kernel chia tải | Chạy ở **mọi** tiến trình khai nó |
| `"sharded"` | Mỗi bản một **phần** việc | Chạy ở mọi tiến trình khai nó, **cộng hai phép kiểm** dưới |
| `"singleton"` | Chỉ primary chạy | `start()` **chỉ ở primary** |

Không có mặc định. Mặc định `replicated` là **nguy** - một adapter chưa từng nghĩ
tới nhân bản bị nhân bản, và nó hỏng **im lặng**; mặc định `singleton` thì app
chậm mà không ai biết vì sao. ⭐ Lớp con của một adapter đã khai thì **kế thừa**.

Hạng phân mảnh khai thêm *điều kiện gì phải khác nhau giữa các tiến trình*:

```python
class MqttAdapter(
    Adapter,
    scaling="sharded",
    unique_per_process=("client_id",),    # giá trị phải KHÁC NHAU
    disjoint_per_process=("topics",),     # tập phải KHÔNG GIAO NHAU
): ...
```

⭐ Hai phép kiểm **khác hẳn nhau**, và MQTT cần cả hai cùng lúc: *"khác nhau"* áp
cho một **giá trị đơn**, *"không giao nhau"* áp cho một **tập**. Framework chạy
chúng lúc khởi động, đọc từ khối `processes:`.

---

## Liên quan

- [Store](store.md) - đưa trạng thái ra khỏi bộ nhớ tiến trình.
- [ProcessLink](process-link.md) - gửi lệnh và câu hỏi giữa các tiến trình.
- [RefData](refdata.md) - một bản dùng chung cho dữ liệu có nguồn bền vững.
- [Cấu hình](configuration.md) - hai tầng config, và ranh giới của chúng.

---

[← ProcessLink](process-link.md) · **Đa tiến trình** · [Testing →](testing.md)
