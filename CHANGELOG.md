# Changelog

Tất cả thay đổi đáng chú ý của Xime Framework được ghi ở đây.

Định dạng theo [Keep a Changelog](https://keepachangelog.com/), phiên bản theo
[Semantic Versioning](https://semver.org/lang/vi/).

## [0.8.2] - 2026-08-26

Báo cáo từ repo **ngoài**, đọc và xử lý 2026-08-22 và 2026-08-23. Nguyên văn:
[`.claude/docs/bao-cao-van-de-tu-repo-ngoai/`](.claude/docs/bao-cao-van-de-tu-repo-ngoai/README.md).

Mục đầu tiên dưới đây thì **không** đến từ repo ngoài: nó do phiên Linux tìm ra khi chạy
thử bản này trước lúc phát hành. Nhật ký:
[`.claude/docs/kiem-toan/0.8.2-ket-qua-do-tren-linux.md`](.claude/docs/kiem-toan/0.8.2-ket-qua-do-tren-linux.md).

### Sửa - dòng log khởi động đếm **0 HTTP route** với mọi ứng dụng Xime

Tìm ra trên Linux ngày 2026-08-25 khi chạy một app thật, không phải bằng đọc code.
App có `/ping` và `/pid`, gọi thật trả `200`, mà dòng log khai:

```text
web default: configure_jwt() not called - no middleware installed, 0 HTTP route(s)
```

Nguyên nhân: **`app.routes` không phải một danh sách phẳng.** Từ `fastapi 0.141`,
`include_router()` nhét vào đúng **một object bọc** (`_IncludedRouter`) giữ router gốc,
thay vì trải từng route ra như các bản trước. Object đó không có `methods`, không có
`include_in_schema`, nên phép đếm phẳng bỏ qua nó và trả `0`.

⚠ Mà **mọi controller của Xime đều đăng ký qua `include_router`**, nên con số này là `0`
với **mọi ứng dụng** - kể cả ứng dụng đang phục vụ ba chục route. Ứng dụng duy nhất ra số
khác `0` là ứng dụng gắn route thẳng vào `FastAPI`, tức đường không ai đi.

⭐⭐ Chỗ đáng nhớ hơn bản vá: **dòng log này chính là bản vá A1**, và nó vừa qua hai vòng
sửa vì cùng một loại lỗi. Vòng một in *"N route(s) open to anyone"* - một kết luận không
có bằng chứng. Vòng hai sửa chữ. Vòng này thì **chữ đã đúng mà con số thì sai**, và nó sai
theo hướng tệ nhất có thể: `0` là con số **duy nhất** khiến người đọc kết luận *"chưa có
route nào, chưa cần lo"*.

⭐ **14 test canh đã có đều xanh y nguyên khi lỗi còn nguyên** - chúng gắn route bằng
`app.add_api_route()`, đường tiện cho test mà không ứng dụng nào đi. Đúng bài học số 1 của
repo: *viết ít nhất một test đi đúng con đường tài liệu hướng dẫn*. Lớp
`TestDemRouteDiXuyenQuaIncludeRouter` (4 test) là con đường đó, và nó canh **cả hai
chiều** - đếm được route qua router lồng nhau, **và** không đếm bừa route hạ tầng.

Phép đếm nay đi xuyên qua lớp bọc bằng **duck typing trên `original_router`**, không bắt
theo tên lớp riêng tư: tên đổi thì con số về `0` **trong im lặng**, đúng thứ bản vá này
sinh ra để xoá. Cả hai hình dạng đều đếm được, vì `pyproject` nhận `fastapi>=0.133.0` và
khoảng đó có cả hai.

Đối chứng hai chiều: gỡ bản vá -> **4 đỏ** (và 14 test cũ **xanh**, đúng như dự đoán) ·
bản vá đếm bừa (mất phép lọc `include_in_schema`) -> **6 đỏ**.

### Thêm - `public_health_paths()` nay là API công khai của `xime.adapters.web`

Hàm đã có từ 0.8.0 và docstring của chính nó ghi *"middleware JWT cho chúng đi qua"*, nhưng
nó **thiếu ở `__all__`**, nên ứng dụng không có đường công khai nào gọi tới. Hậu quả: một
`/healthz` đòi token, tức một `/healthz` im lặng **đúng vào lúc app không lấy nổi khoá verify**
- lúc người ta cần nó trả lời nhất.

Đo lại trên **28 repo** thì phạm vi rộng hơn báo cáo: **8 repo đang gọi nó từ module riêng tư
`xime.adapters.web._health` trong CODE SẢN PHẨM**, và đó là lời import riêng tư **duy nhất**
nằm ngoài thư mục test của cả 28 repo. Cửa đã có người đi qua từ lâu; việc còn lại chỉ là
chọn giữa *một cửa được đỡ* và *8 repo bám vào ruột framework*.

⭐ **Nó KHÔNG chỉ phục vụ middleware xác thực**, và đây là chỗ lật lại lý do phản đối duy nhất
mà báo cáo nêu (*"export nó là hợp thức hoá middleware JWT tự viết, đúng thứ A1 đang cố xoá"*).
Một repo dùng nó cho **hàng rào IP** - chỗ dùng đó không dính gì tới JWT và **không biến mất**
khi repo chuyển sang `configure_jwt`. Ghi log truy cập, hãm nhịp, đếm số đo cũng vậy.

Kèm hai thứ trước nay không tài liệu nào nói:

- **Dùng `configure_jwt` thì ĐỪNG gọi hàm này** - framework tự cộng đường sức khoẻ vào
  `public_paths` trước khi gắn middleware. Chép tay lần nữa là dựng một bản sao sẽ lệch vào
  ngày luật khớp đường dẫn đổi.
- **Phải gọi SAU `configure_health()`.** Nó đọc sổ đăng ký tại thời điểm được gọi, nên gọi
  sớm thì nhận tuple **rỗng** - mà rỗng ở đây trông y hệt *"app này không bật endpoint sức
  khoẻ"*. Hàng rào chặn mất `/healthz` và **không có gì báo**, vì middleware từ chối rất gọn.

Test canh đi thành **cặp** và chạy đúng con đường tài liệu hướng dẫn (`from xime.adapters.web
import public_health_paths`, không phải `._health`): đường sức khoẻ **qua được** hàng rào ·
đường nghiệp vụ **không qua** · và quên `configure_health()` thì `/healthz` **bị chính hàng
rào của mình chặn**. Ba đối chứng, đều đỏ đúng chỗ: bỏ tên khỏi `__all__` → 1 đỏ · bỏ lời
import → cả file lỗi · hàng rào cho qua tất → 2 đỏ.

⚠ Đây là **tên công khai mới**, mà `0.9` sang Beta nơi API coi như đã chốt - nên nó phải nằm
trong dòng `0.8.x`, không lùi được.

### Sửa - tài liệu hướng dẫn nay khớp với bản hiện tại, không còn khuôn của bản cũ

Bài `getting-started` viết cho một bản cũ và **không chạy được**: rút nguyên văn 9 khối code
của nó rồi chạy như bài dặn thì chết ở `ModuleNotFoundError: No module named 'application'`.
Đã viết lại cả hai ngôn ngữ theo đúng bố cục mà **`xime init` sinh ra**, rồi rút code từ bản
mới ra chạy lại để nghiệm thu: `GET /users/1` trả `{"id":1,"name":"Alice",...}`, `/docs` trả
200.

Ba thứ bài cũ dạy sai so với bản hiện tại:

- **Khuôn `main.py`.** Bài cũ đặt `app.use(...)` **trong** `if __name__`. Ngày chạy nhiều
  tiến trình, con **chạy lại chính file đó** và ở đó `__name__` là `__mp_main__`, nên khối
  `if` không kích hoạt và con lên với **không adapter nào, DI rỗng**. Nay `Application()`,
  `add_config()`, `use()` nằm ở mức module, chỉ `run()` ở trong khối.
- **`add_config(config)` và gói `config/__init__.py`** hoàn toàn vắng mặt trong bài cũ, dù cơ
  chế tự dò của bản cũ **hỏng ở tiến trình con** (nó tìm qua `__main__.__spec__.parent`) rồi
  im lặng rơi xuống một DI rỗng.
- **Vị trí `resources/`.** Bài cũ để `app/resources/application.yml`, mà framework tìm
  `resources/application.yml` **tương đối với thư mục chạy lệnh**. Để nhầm thì file bị **bỏ
  qua không một lời nào** - app vẫn khởi động, chạy bằng giá trị mặc định. Đo được vì đổi cổng
  trong file mà tiến trình vẫn bám cổng cũ.

Kèm dọn cho **toàn bộ** tài liệu, không riêng bài mở đầu:

- **10 đoạn `main.py`** ở `mqtt`, `modbus`, `socket-adapter`, `grpc-codefirst`,
  `core-concepts` gọi `app.run()` **ngoài** `if __name__` và thiếu `add_config`. Nay 0 đoạn
  còn như vậy trong toàn bộ `docs/`.
- **60 đường dẫn module** thiếu tiền tố gói nghiệp vụ, ở 22 file.
- **10 chỗ** còn gọi file cấu hình routing là `config/routing.py`; khuôn hiện hành là
  `config/web.py`, nay thống nhất.
- Bài mở đầu trước nay **chưa nhắc `xime init` một lần nào**, nên người mới dựng tay 9 file
  trong khi một lệnh là xong.

📌 `xime init` thì **vẫn chạy tốt** và luôn đúng - đã kiểm: sinh dự án, `python main.py`,
`GET /ping` trả `{"status":"ok"}`, `/docs` trả 200. Lỗi chỉ nằm ở bài viết tay.

### Sửa - một cảnh báo tiếng Anh của framework lẫn một chữ tiếng Việt

`_HUONG_DAN` trong `xime/adapters/web/ws/_availability.py` in
`(hoặc: pip install "uvicorn[standard]")` giữa một câu tiếng Anh. Đây là chuỗi **người dùng
thấy**, không phải chú thích, và mọi dòng log khác của framework đều tiếng Anh. Đổi thành
`(or: ...)`.

### Sửa - bài hướng dẫn `getting-started` không chạy được, nay chạy được đầu-cuối

Rút nguyên văn 9 khối code của bài rồi chạy `python -m app.main` như bài dặn: nó chết ngay ở
`ModuleNotFoundError: No module named 'application'`. Hai lớp lỗi, sửa xong thì bài chạy thật
- `GET /users/1` trả `{"id":1,"name":"Alice",...}` và `/docs` trả 200.

- **12 đường dẫn module thiếu tiền tố `app.`** ở mỗi bản ngôn ngữ. Bài khai bố cục
  `app/domain/user.py` và lệnh chạy `python -m app.main` từ gốc dự án, nhưng các import lại
  viết `from domain.user import User`, và `dependency.scan("application.usecase")`,
  `configure_controllers("api.rest")` cũng thiếu tiền tố. Hỏng **ồn ào**, chết ngay.
- ⚠ **`application.yml` bị đặt sai chỗ, và chỗ này hỏng IM LẶNG.** Bài để nó ở
  `app/resources/`, nhưng framework tìm `resources/application.yml` theo đường dẫn **tương
  đối với thư mục chạy lệnh**. Để nhầm thì file **bị bỏ qua không một lời nào**: app vẫn khởi
  động, chạy bằng giá trị mặc định của framework. Đo được vì đổi cổng trong file mà tiến
  trình vẫn bám cổng cũ.
- Bài nay có mục trỏ sang **`xime init`**, thứ trước đây nó không nhắc một lần nào - người
  mới dựng tay 9 file trong khi một lệnh là xong. Kèm cảnh báo rằng `xime init` sinh ra một
  **bố cục khác** (`main.py` và `config/` ở gốc, code trong package mang tên dự án), nên đừng
  trộn hai bố cục.

📌 `xime init` thì **chạy tốt**, đã kiểm: sinh dự án, `python main.py`, `GET /ping` trả
`{"status":"ok"}`, `/docs` trả 200. Lỗi chỉ nằm ở bài hướng dẫn viết tay.

### Sửa - Pydantic `BaseModel` không còn làm chết startup khi để trong package được quét

Đặt một DTO viết bằng `BaseModel` cạnh controller là đủ để `dependency.scan()` nhận nó
làm ứng viên DI, rồi startup chết với:

```text
Unregistered Dependency
  Class     : TaoPhongRequest
  Dependency: Any
  Hint      : add the package containing 'Any' to dependency.scan()
```

Câu gợi ý còn chỉ sai đường: `Any` không nằm trong package nào để mà thêm.

⭐ **Chính bài hướng dẫn getting-started rơi vào đây.** Nó khai
`class UserResponse(BaseModel)` trong `api/rest/user_controller.py` rồi
`dependency.scan("api.rest")` - đo lại trên bản trước khi vá thì nó chết đúng câu trên.
Tức bài "hello world" của framework **không chạy được**, và điều đó chưa ai phát hiện vì
mọi app thật đều sớm học được cách xếp DTO vào `dto/`.

Nguyên nhân là hai hàm cùng file, cách nhau 40 dòng, trả lời ngược nhau về **cùng một
class**: `get_init_parameters()` lọc `VAR_KEYWORD` nên nó thấy *"không có tham số nào"*
và cho class đi qua cửa; `resolve_constructor_hints()` không lọc nên nó đọc `**data: Any`
thành một dependency tên `data`. Framework **nhận class đó vì nó không có tham số nào,
rồi chết vì đòi một tham số**.

Nay `BaseModel` nằm cùng nhóm với `Protocol` và `ABC` - **thứ DI về mặt cấu trúc không
dựng được** - và bị loại ngay ở cửa. Lý do là cấu trúc chứ không phải quy ước: constructor
injection khớp dependency **theo tên tham số**, mà `**data` không có tên nào để khớp.

- ⛔ **`@dataclass` cố ý KHÔNG bị loại.** Nó sinh ra `__init__(self, repo: Repo)`, tức là
  một cách viết service hợp lệ, và DI dựng được nó. Ranh giới của DI là *dựng được hay
  không*, không phải *người ta định dùng làm gì*. Loại nó còn hỏng **im lặng** theo chiều
  ngược hôm nay: một service viết bằng dataclass sẽ biến mất khỏi DI mà không có lời nào,
  trong khi hôm nay một dataclass dữ liệu đặt nhầm chỗ **nổ lúc khởi động kèm tên class**.
  Đo trên 31 codebase: 197 `@dataclass` trong vùng được quét, **0** cái có hình dạng bean.
- ⛔ **Đường đã cân nhắc và loại: lọc `VAR_KEYWORD` trong `resolve_constructor_hints`.**
  Chạy mô phỏng đầu-cuối thì nó chỉ đổi `UnregisteredDependencyException: Any` thành
  `ValidationError: field required` - vì `build()` chỉ kiểm, còn dựng thật xảy ra ở
  `get_all_in_order()`. Lỗi mới không còn dấu vết nào của DI nên **khó lần hơn lỗi cũ**.
- `dependency.register(MotBaseModel)` vẫn lọt và vẫn nổ như trước: `register()` bỏ qua
  phép xét tư cách, và khai tường minh thì tôn trọng lời khai.

### Thêm - `dependency.exclude_segments(...)`: app tự khai danh sách package bị loại

Scanner vẫn bỏ qua mọi module có đoạn đường dẫn là `domain`, `dto`, `entity`, `vo`,
`constant`, `exception`. Sáu đoạn đó là **mặc định, không phải luật** - chúng mang từ vựng
DDD (`vo` là *value object*), nên một dự án đặt tên khác, hoặc một dự án thật sự giữ
service trong package tên `domain`, trước nay bị framework **nuốt im lặng**: không lỗi,
không cảnh báo, class chỉ đơn giản không có mặt.

```python
dependency.exclude_segments("domain", "dto", "legacy")   # thay the han
dependency.exclude_segments()                             # quet TAT, khong loai gi
```

- **Thay thế, không cộng thêm.** Một lời gọi khai trọn danh sách; gọi nhiều lần thì lần
  cuối thắng.
- ⚠ **Không gọi** và **gọi rỗng** là hai chuyện khác nhau: không gọi thì dùng sáu đoạn mặc
  định, gọi rỗng thì không loại đoạn nào. Trạng thái *chưa khai* mang giá trị `None` chứ
  không phải danh sách rỗng - gộp hai thứ đó là một giá trị mang hai nghĩa, và nó sẽ hỏng
  im lặng theo chiều nguy hiểm nhất (mọi app bỗng quét cả `domain/` mà không có gì báo).
- `PackageScanner` đã nhận sẵn tham số này từ lâu nhưng **chưa ai truyền một lần nào** -
  bản này chỉ nối nó ra tới `dependency`, không đổi hành vi mặc định của bất kỳ app nào.
- Bộ lọc vẫn chỉ chạy khi duyệt **module con**: trỏ `scan()` thẳng vào `app.domain` thì
  class trong `__init__.py` của chính package đó vẫn được đăng ký. Chỉ đích danh thì coi
  như cố ý.

### Sửa - con không còn sống sót sau khi cha bị giết cứng

Cha đã bắt `SIGINT` / `SIGTERM` / `SIGBREAK` từ 0.8.0 để tắt cả đàn theo thứ tự, và
docstring của chính nó gọi con mồ côi là kết cục tệ nhất:

> *"cha chết ngay còn con sống tiếp mồ côi - vẫn giữ cổng, vẫn phục vụ, và không ai
> dựng lại chúng nữa. Đúng thứ tệ nhất: hệ thống trông như đã tắt mà thực ra chưa."*

Nhưng bắt tín hiệu chỉ che được cái chết **lịch sự** của cha. `SIGKILL`,
`Stop-Process -Force`, `taskkill /F`, cha sập vì lỗi của chính nó, kernel giết cha vì
hết RAM - **không đường nào trong bốn đường đó bắt được**, và con sống tiếp.

Nay con tự canh cha bằng `multiprocessing.parent_process()` - hạ tầng có sẵn của thư
viện chuẩn, hoạt động trên cả hai nền tảng bằng hai cơ chế khác nhau (Linux: một đầu
ống thừa kế; Windows: `HANDLE` tới tiến trình cha). **Không thêm vùng nhớ chung nào,
không thêm khoá cấu hình nào, không thêm tên công khai nào.**

- Con đi bằng **đúng tín hiệu mà một lần tắt bình thường dùng**, nên nó tắt theo cùng
  một đường code và cùng một thứ tự dọn. Huỷ task chính thì cũng dọn đúng, nhưng
  uvicorn in nguyên một traceback mức `ERROR` ngay dưới dòng `CRITICAL` vừa in - và
  một traceback ở đó đọc như *"tắt hỏng"* trong khi nó đang tắt đúng. Đo trên cụm 3
  tiến trình thật: huỷ task ra **3 traceback**, gửi tín hiệu ra **0**.
- ⚠ Hai nền tảng dùng hai lệnh khác nhau và **đổi chỗ chúng thì hỏng im lặng**: POSIX
  phải `os.kill(getpid(), SIGTERM)` vì `raise_signal()` gửi cho *thread đang gọi* nên
  không ngắt `epoll_wait` của thread chính; Windows phải `raise_signal()` vì ở đó
  `os.kill()` gọi thẳng `TerminateProcess`, tức mất sạch phần dọn êm.
- Tắt êm quá **15 giây** (loop đã treo) thì thoát cứng bằng mã **3**. Con mồ côi mà
  loop treo là ca tệ nhất trong các ca tệ - giữ cổng và không phục vụ nổi ai - nên
  việc duy nhất còn đáng làm là trả lại cổng.
- Không canh khi **không có cha**: chạy tay một tiến trình, chạy trong test, chạy dưới
  một trình giám sát khác. Đó là đường vào hợp lệ, không phải lỗi.

⭐⭐ **Vì sao nó nặng hơn là "thừa vài tiến trình": con mồ côi VÔ HÌNH với cả hai phép
dò mà người ta sẽ dùng, và cả hai đều trả lời theo hướng TRẤN AN.** Lọc tiến trình theo
`app.main` ra *"1 tiến trình, đúng như mong đợi"* - vì `spawn` khiến dòng lệnh của con
là `python -c "from multiprocessing.spawn import spawn_main; ..."`, không mang tên
module nào. `netstat` thì gán socket cho PID **người tạo**, nên nó chỉ vào xác của cha
và người đọc kết luận *"chỉ là bản ghi cũ"*. Cộng lại: một cụm đang phục vụ **mã cũ**
trong khi bạn tin mình vừa khởi động lại nó. Phiên báo lỗi mất **bốn vòng gỡ lỗi** vào
hư không trước khi thấy.

📌 Đo đầu-cuối trên Windows 11, cụm 3 tiến trình chia chung cổng: `Stop-Process -Force`
lên cha thì cả ba con thoát, cổng được trả, 0 traceback.

### Sửa - log lúc con chết nay khai AI GIẾT, không chỉ khai mã thoát

`supervisor: api-3 exited with code -15 - restarting` đúng nhưng mang **hai nghĩa dẫn
tới hai việc ngược nhau**: *"watchdog của tôi vừa giết nó vì nó treo"* là chuyện nội bộ
đã xử lý xong, còn *"ai đó bên ngoài giết nó"* là một tiến trình khác đang can thiệp vào
cụm này. Người đọc log không có cách nào tách ra.

```text
... exited with code -15 (my watchdog killed it: event loop blocked for 12.3s) - restarting
... exited with code -15 (NOT me - another multiprocessing parent terminated it; ...) - restarting
```

⛔ **Và trên Windows `-15` KHÔNG phải `SIGTERM` từ bên ngoài** - chỗ này đã làm một phiên
mất nửa buổi. CPython (`multiprocessing/popen_spawn_win32.py::wait`) đọc
`GetExitCodeProcess`, và nếu mã đúng bằng hằng `TERMINATE = 0x10000` thì nó **đổi thành**
`-signal.SIGTERM`. Mà `0x10000` chỉ do chính `multiprocessing` ghi ra:

| Ai giết | Mã thoát Python thấy |
|---|---|
| `multiprocessing` (`terminate()`/`kill()`) | `-15` |
| `taskkill /F` | `1` |
| `Stop-Process -Force` (`Process.Kill()` của .NET) | `4294967295` |

Nên trên Windows, `-15` ở một con mà **cha này không giết** là bằng chứng rằng **một cụm
cũ chưa tắt hẳn** đang giết con của cụm mới - tức triệu chứng của đúng lỗi vừa vá ở trên.
Trên POSIX thì `-N` đúng nghĩa đen là tín hiệu `N`, không có phép đổi nào.

⚠ Lời khai bị **xoá khi con được sinh lại**: không xoá thì lần chết sau bị gán lý do của
lần trước - một dòng log đúng cú pháp và sai sự thật, loại khó phát hiện nhất.

### Thêm - `public_paths` mở được cả một nhánh bằng đuôi `/*`

⚠ **ĐỔI HÀNH VI, không phải thuần cộng thêm.** Ký tự `*` trong một mục `public_paths`
trước đây là một ký tự bình thường, nay mang nghĩa. URL hầu như không bao giờ chứa `*`
thật, nhưng đây là đổi ngữ nghĩa của một giá trị cấu hình **đã phát hành**.

```python
configure_jwt(JwtMiddlewareConfig(
    public_paths=["/auth/login", "/health", "/api/v1/parts/*"],
))
```

`/api/v1/parts/*` mở `/api/v1/parts` (gốc nhánh) và mọi đường dưới nó.

- ⛔ **Khớp theo ĐOẠN đường dẫn, không phải theo chuỗi.** `/api/v1/parts/*` **không bao
  giờ** chạm `/api/v1/partsecret` hay `/api/v1/parts-admin`. `startswith` trần thì có, và
  đó là một **lớp lỗ hổng** hỏng theo chiều **chặt sang lỏng** - chiều không sinh lỗi,
  không sinh test đỏ, không sinh dòng log nào.
- **Dấu `*` ở vị trí khác là lỗi lúc khởi động**, không phải mục bị bỏ qua: `/api/*/parts`,
  `/api/**`, `/parts*` đều bị từ chối. Bỏ qua thì mục đó khớp **không gì cả**, mà người
  viết đọc cấu hình của mình như một mẫu - nó im lặng không phải mẫu.
- `/*` bị từ chối kèm thông báo riêng: nó không phải một cấu hình của middleware mà là
  **sự vắng mặt** của middleware. Service công khai hoàn toàn thì đừng gọi `configure_jwt()`.
- Nổ ngay tại `configure_jwt()` chứ không đợi `build_app()`, để dấu vết trỏ vào
  `config/jwt.py` của ứng dụng thay vì vào lòng framework.

⭐ **Ba chỗ khác cũng đọc `public_paths` và mỗi chỗ từng tự chép luật khớp** - registrar
WebSocket, trình dựng OpenAPI, và phép thêm đường sức khoẻ. Nay cả ba gọi **cùng một
hàm**. Vá mỗi middleware là dựng lại đúng lỗi vừa đi sửa ở C8: một luật, nhiều bản chép
tay, và bản nào trôi thì không gì đỏ - ổ khoá trên Swagger bắt đầu nói khác middleware,
route `@ws` dưới một nhánh công khai vẫn đòi token.

Trung tính, và bằng chứng không đến từ app nào: Spring Security `/public/**`, Django,
Express, ASP.NET - không hệ nào bắt liệt kê chính xác. Chỗ hụt là **tham số đường dẫn**,
và tập đường sinh ra từ một tham số là **vô hạn**.

### Thêm - log khởi động khai app này có xác thực hay không

Đo được, không phải suy đoán: hai app Xime tối giản khác nhau **đúng một chỗ** (có gọi
`configure_jwt()` hay không) sinh ra log khởi động `diff` ra **0 dòng khác biệt**. Cả hai
báo *"startup complete"*, không cái nào nhắc tới xác thực - trong khi một cái phục vụ dữ
liệu cho bất kỳ ai.

```text
INFO | web default: JWT middleware active (aud=phongkham, 1 public path(s), 31 HTTP route(s))
INFO | web default: configure_jwt() not called - 3 custom middleware installed, 31 HTTP route(s)
INFO | web default: configure_jwt() not called - no middleware installed, 31 HTTP route(s)
```

- Phát ra trong `lifespan`, **sau** khi controller đăng ký xong - đếm sớm hơn là báo một
  con số luôn bằng số route hạ tầng.
- Đếm **bề mặt API của ứng dụng**: `/docs`, `/openapi.json`, `/healthz` khai
  `include_in_schema=False` nên không tính. Chúng cũng mở thật, nhưng một con số người
  viết không map được về code của mình thì không nói cho họ điều gì.
- `aud` để trống thì in `aud=not enforced`, không in `aud=None` - đây là dòng người vận
  hành đọc, không phải `repr` của một dataclass.

⛔⛔ **Dòng này KHAI THỨ ĐO ĐƯỢC và không bao giờ kết luận vượt quá**, và luật đó mua bằng
một lỗi thật trong chính đợt này. Bản đầu in *"no JWT middleware - N HTTP route(s) open to
anyone"*: nó đo **một** sự kiện (`configure_jwt()` có được gọi không) rồi in ra **hai** kết
luận không có bằng chứng nào đỡ. Phiên `Service ngang` khởi động thật bốn repo và đo lại
toàn workspace:

| | Số repo |
|---|---|
| Cài xác thực bằng `configure_middleware` - câu cũ kết luận **SAI** | **23** |
| Dùng `configure_jwt` - câu cũ kết luận đúng | **0** |

`curl` không token vào các repo đó trả **401**. Xác thực đang chạy; câu cũ **sai 100% số
lần nó in ra**.

⭐ Vì sao nặng hơn chuyện chữ nghĩa: *một phép dò kêu oan là một phép dò sẽ bị tắt*. Khi
cùng một câu xuất hiện dưới 23 ứng dụng khoẻ mạnh thì ứng dụng thật sự fail-open in ra một
dòng không ai còn đọc - **đúng thứ dòng log này sinh ra để chặn**. Cùng hình dạng với
**C7** ở adapter gRPC (*cụm khoẻ và cụm hỏng sinh log giống nhau*), khác ở chỗ lần này hai
bên giống nhau vì **chữ quá rộng** chứ không vì thiếu log.

Nay số middleware do ứng dụng tự cài được **in ra chứ không được diễn giải**:
`configure_middleware` cũng là đường cài nén, log, request id, nên suy từ một con số khác 0
ra *"app này có xác thực"* là đúng vì lý do tình cờ. Người đọc biết ứng dụng của mình cài
gì; framework thì không. Hình dạng fail-open thật là dòng thứ ba - không gọi `configure_jwt`
**và** không middleware nào - và nó tự nói ra mà không cần ai kết luận hộ.

⛔ **Là `INFO` có chủ ý, không phải cảnh báo.** Service công khai hoàn toàn là hợp lệ và
không hiếm, mà framework không phân biệt được `/healthz` với `/api/v1/benh-an/{ma}`.

⭐ Nó vá đúng thứ làm **A1** sống lâu - A1 không phải chuyện thiếu một phép kiểm (`0.7.2`
đã thêm), mà là chuyện **trạng thái "không có xác thực" trông giống hệt trạng thái "có xác
thực"**. Đặt `configure_jwt()` sau một `if` là quay lại A1 nguyên vẹn, và trước bản này
framework không nói gì.

### Sửa - `xime check config` tố oan khoá hợp lệ (C8)

Báo về từ phiên giữ **ví dụ gRPC + Socket**. Khối `socket` khai `complete=True` -
giấy phép để `check config` tố khoá lạ - nhưng danh sách khoá của nó chỉ có 3
trong khi adapter đọc 8. Một `application.yml` chép **nguyên văn ví dụ trong tài
liệu chính thức** bị chính công cụ kiểm của framework báo lỗi.

⭐ **Framework đo lại thì phạm vi rộng gấp đôi báo cáo, và sai theo CẢ HAI chiều:**

| | |
|---|---|
| Khối `socket` thiếu 6 khoá | `dir` `owner` `group` `session_timeout` `max_chunk_size` `recv_queue_size` |
| ...và **thừa 1** | khai `socket.path`, một khoá **không đường nào đọc** - path đến từ `process.socket.<id>.path`. Người dùng viết nó, `check config` báo CLEAN, adapter bind chỗ khác hẳn |
| Khối `lmdb` thiếu 2 khoá | `file_mode`, `dir_mode` - hai khoá có **7 test** riêng |

Đo hai chiều trên đúng YAML người báo dùng: **4 lỗi trước, CLEAN sau**. Người báo
chỉ thấy 2/4 vì repo họ không dùng `lmdb`.

⚠ Chiều **thừa** hỏng im lặng hơn chiều **thiếu**: thiếu khoá thì có tiếng kêu,
thừa khoá thì không.

- Thêm **test canh tầng KHOÁ** (`tests_temp/cli_config/test_spec.py`). Phép dò có
  sẵn chỉ canh **tên khối**, và nó mù hoàn toàn với tầng dưới nó - đúng chỗ cả hai
  lỗi lọt qua. Canh **cả hai chiều**, kèm đối chứng.
- ⭐ Test cũ `test_a_hand_written_block_keeps_its_keys` **xanh suốt thời gian đó**:
  nó so bản mô tả với một bản chép của chính bản mô tả. **Một phép kiểm chỉ đối
  chiếu được khi hai vế có nguồn KHÁC nhau.**

### Sửa - gợi ý của lỗi thiếu đăng ký dẫn sai đường (C9)

Báo về từ phiên giữ **`Application Layer/dental`**. Lớp nhận một bảng `RefData` qua
constructor mà container chưa có nó thì nhận gợi ý *"add the package containing 'X'
to dependency.scan()"* - và `scan()` **không bao giờ** với tới `RefData`.

> Một gợi ý SAI đắt hơn là không có gợi ý: người đọc làm theo, không có gì đổi, còn
> nguyên nhân thật thì vẫn nằm im.

⭐ Đo lại thì có **hai** registry nằm ngoài `scan()` chứ không phải một: bảng
`RefData` (`configure_refdata`) và handler `ProcessLink` (`configure_link`).

- `UnregisteredDependencyException` nhận `hint=` tuỳ chọn; `_hint_for()` chỉ đúng
  registry thật. Lớp thường vẫn dùng gợi ý mặc định - **không ai bị đổi lấy một
  cảnh báo sai**.

### Tài liệu - scheduler và đa tiến trình: nói ra thứ trước nay chỉ đúng trong im lặng

`docs/{vn,en}/starters.md` mục Scheduler **không hề nói** rằng scheduler chỉ chạy ở tiến
trình primary. Bảng *"chỉ primary"* có trong tài liệu nhưng đó là bảng của `RefData`, không
phải của scheduler - người viết một job đẩy số đo đọc đúng mục Scheduler và không gặp cảnh
báo nào, rồi mất số đo của ba phần tư cụm mà không có dấu hiệu gì.

Nay mục đó có thêm hai phần: hành vi (`singleton`, `standby`, **không khoá cấu hình nào đổi
được**) và một mục trả lời thẳng câu *"nhưng job của tôi cần chạy ở từng tiến trình"* - kèm
phép kiểm để tự loại, hai loại việc thật sự phải chạy theo tiến trình (**cả hai ở ngoài
scheduler**), và một adapter `scaling="replicated"` chép được cho ai thật sự cần.

⭐ Kết luận đáng ghi hơn cả bản vá tài liệu: rà hết thì **0 ca nghiệp vụ** cần hẹn giờ theo
tiến trình, và đó là **hệ quả cấu trúc chứ không phải may mắn** - nghiệp vụ chạm dữ liệu của
khách, mà dữ liệu của khách không bao giờ nằm riêng trong bộ nhớ một tiến trình. Nên *một job
nghiệp vụ cần chạy riêng từng tiến trình là một job đã vi phạm luật 01 từ trước*.

⛔ **Không thêm trường phạm vi vào `IntervalJob`/`CronJob`**, và đây là quyết định chứ không
phải hoãn: cửa đó hỏng theo chiều **im lặng** - khai nhầm cho một job gửi email nhắc là gửi
bốn lần, không exception, không test đỏ.


## [0.8.1] - 2026-08-22

Bản nhỏ, một chủ đề: **bật uvloop trên Linux**, cộng một cảnh báo phụ về thư viện
WebSocket. Không đổi một khoá cấu hình nào, không thêm tên công khai nào.

⚠ **Đo trên Linux xong mới phát hành.** Đây là bản đầu tiên áp quy tắc đó, và lý do
là ba ca thật ở mục cuối.

### Thêm - uvloop được dùng thật trên Linux và macOS

`pip install "xime[web]"` vốn đã kéo `uvicorn[standard]`, nên **uvloop nằm sẵn trên
đĩa ở mọi cài đặt Linux từ nhiều bản trước - và chưa bao giờ chạy một lần nào**. Xime
gọi `Server.serve()`, trong khi `loop_factory` chỉ được đọc trong `Server.run()`.

> Nhìn `pip list` thấy đủ bốn gói tăng tốc rồi kết luận *"đã bật"* là sai, và **không
> có gì báo**. Không log, không cảnh báo, không khác biệt nào quan sát được từ bên
> ngoài trừ khi đem đi đo.

- Thêm `xime/core/bootstrap/_loop.py` với `uvloop_factory()`: trả hàm dựng loop của
  uvloop nếu import được, `None` nếu không. Không dùng `uvloop.install()` (nó đặt
  policy toàn cục, đụng vào tiến trình của người khác).
- `worker_loop_factory()` tách thành **ba nhánh thật** thay vì gộp hai câu hỏi vào
  một điều kiện:

  | Nền tảng | Loop |
  |---|---|
  | Windows **có** socket kế thừa | `SelectorEventLoop` - **giữ nguyên từng chữ**, xem dưới |
  | Windows không socket kế thừa | mặc định (proactor) |
  | Linux / macOS | **uvloop** nếu có, ngược lại mặc định |

- `Application._run_async()` nay log **loop đang chạy thật** ở mức `INFO`:

  ```text
  INFO | xime.bootstrap | event loop: uvloop.Loop
  ```

  Trước đây không có cách nào biết mình đang chạy trên loop nào mà không mở mã ra đọc.

**Chi phí bằng 0 khi không có uvloop**: `uvloop_factory()` trả `None` và app chạy y hệt
mọi bản trước. Không có công tắc bật/tắt - người vận hành không có đủ thông tin để
chọn, mà chính người viết framework cũng phải đo mới biết.

### Thêm - cảnh báo khi có route `@ws` mà không có thư viện WebSocket

`uvicorn/protocols/websockets/auto.py` đặt `AutoWebSocketsProtocol = None` khi thiếu
**cả** `websockets` lẫn `wsproto`. Khi đó mọi route `@ws` **chết lặng**: bắt tay không
thành, và không một dòng log nào của Xime giải thích vì sao.

`xime/adapters/web/ws/_availability.py` hỏi thẳng `AutoWebSocketsProtocol` - thứ uvicorn
thật sự dùng - thay vì tự liệt kê tên gói, và **chỉ kêu khi app thật sự có route `@ws`**.
Cảnh báo, không nổ: `xime[web]` vốn đã kéo về đủ, nên đây là đường cài không chuẩn chứ
không phải lỗi cấu hình đáng chặn khởi động.

### ⛔⭐ Đo được: uvloop KHÔNG tăng tốc REST, và ranh giới không phải giao thức

Phép đo lãi thật **lật một giả định của chính bản này**. Đo trên **cùng một app Xime**,
dao động dưới 2%, hai lượt cách nhau một tiếng cho cùng kết quả, ma trận sáu hình dạng
tải cho 5/6 ô cùng chiều:

| Loại việc | uvloop / loop mặc định |
|---|---|
| Xử lý một request kiểu HTTP: REST **0.91x** · **bắt tay WebSocket 0.93x** | **lỗ ~8-9%** |
| Truyền trên kết nối đã mở: **tin nhắn WebSocket 1.11x** · echo TCP trần **1.38x** | **lãi 11-38%** |

⭐ **Bắt tay WebSocket là một request HTTP-upgrade, và nó rơi cùng phía với REST** -
khác phía với chính những tin nhắn chạy sau nó **trên cùng cái socket đó**. Trục phân
chia là **loại việc**, không phải giao thức.

**Vẫn giữ uvloop**, ba lý do: chi phí bằng 0 khi vắng mặt · REST không phải cả framework
(năm adapter còn lại đều sống trên kết nối đã mở) · hiệu suất trên mỗi %CPU luôn thắng
(1.31x-1.64x), và đó là chỉ số đáng giá hơn thông lượng đỉnh trên máy tính tiền theo CPU.

📌 Kết luận thực dụng: thêm một tiến trình cho **+100%** thông lượng, uvloop cho
**-10%**. Nút điều chỉnh có ích của một app Xime điển hình là `count:`, không phải
event loop.

### Nội bộ - framework nay có bộ benchmark

Trước bản này **không có benchmark nào**. `.claude/scripts/benchmark/` đo năm tầng
chồng lên nhau, nên **hiệu số giữa hai dòng là giá của đúng lớp nằm giữa chúng**: loop
trần -> HTTP (asgi/fastapi/xime) -> lõi (DI, Store, RefData) -> cụm nhiều tiến trình ->
WebSocket.

| | |
|---|---|
| **Xime = 41% thông lượng của ASGI trần** | FastAPI ở giữa (66%). Giá của DI + controller + middleware |
| **Cụm mở rộng gần tuyến tính** | 2.00x với 2 tiến trình, **3.88x với 4**, và **N/N tiến trình thật sự nhận việc** |
| **`RefData.read()` nhanh hơn `Store.get()` ~60 lần** | Ranh giới *có nguồn bền vững hay không* trùng với ranh giới hiệu năng |

Không nằm trong gói phát hành (`.claude/` đã bị loại khỏi sdist).

### Tài liệu

- **Trang mới [Event loop](docs/vn/event-loop.md)** (vn + en): loop nào đang chạy và
  cách hỏi chính ứng dụng, Xime chọn loop thế nào trên từng nền tảng, số đo lãi/lỗ ở
  trên, và vì sao **không có công tắc bật tắt** - người vận hành không có đủ thông tin
  để chọn, mà chính người viết framework cũng phải đo mới biết.
- **[WebSocket](docs/vn/websocket.md) thêm mục "Cần cài gì"**: trang này trước nay
  không nói một chữ nào về thư viện cần có, trong khi bản này vừa thêm một cảnh báo về
  đúng chuyện đó. Nay có cả chuỗi cảnh báo thật để người gặp nó tra được.

### Sửa - hai test khoá sai thứ chúng hứa khoá

Không đụng một dòng mã sản phẩm nào.

- `test_linux_never_switches` khẳng định `worker_loop_factory(...) is None` trên Linux.
  Đó là cách diễn đạt của ý *"không đổi loop"* ở thời **chưa có gì khác để đổi sang**.
- `test_fails_fast_on_first_bad_package` đặt một package **hợp lệ** sau package lỗi rồi
  chỉ khẳng định *"có ném `ImportError`"* - câu đó đúng **cả khi** scanner gom hết lỗi
  rồi mới ném, tức nó không phân biệt được fail-fast với fail-late.

### ⭐ Ca thứ ba của "lỗi máy phát triển không thể thấy"

`test_linux_never_switches` **xanh trên Windows kể cả sau khi bản vá làm nó sai**, vì ở
đó `uvloop_factory()` luôn trả `None` - nên dù `sys.platform` bị monkeypatch thành
`"linux"`, hàm vẫn trả `None`.

> **Phép đo đó không đo nền tảng được monkeypatch. Nó đo nền tảng thật.**

Nó còn **mâu thuẫn trực tiếp** với `tests_temp/bootstrap/test_event_loop.py`, mà không
ai thấy vì hai file **không bao giờ cùng đỏ trên một máy**. Sau C4 (ngữ cảnh
`multiprocessing`) và C5 (`mypy`) của 0.8.0, đây là ca thứ ba, ba cơ chế khác nhau,
cùng một hình dạng: **điều kiện gây lỗi không tồn tại trên máy phát triển.**

### Nghiệm thu

| | `passed` | `skipped` | **Tổng** |
|---|---|---|---|
| Linux (Debian 13, Python 3.13.5) | 2552 | 6 | **2558** |
| Linux **chạy dưới uvloop thật** | 2552 | 6 | **2558** |
| Windows (Python 3.14) | 2534 | 24 | **2558** |

`mypy xime/` **41 lỗi = đúng mốc 0.8.0** · `ruff check xime/` sạch. Chênh 18 giữa hai
nền tảng là test bị chặn bởi nền tảng; **tiêu chí đạt là TỔNG 2558 cộng 0 failed, không
phải `passed`**.

## [0.8.0] - 2026-08-20

Thi công theo bảy giai đoạn của `.claude/docs/ke-hoach-code-0.8-2026-08-19.md`,
cộng một giai đoạn thứ tám phát sinh giữa chừng (trình tạo cấu hình). Thiết kế
đóng ngày 2026-08-19; phần dưới ghi những gì đã CODE, không phải những gì đã
thiết kế.

⭐ **Bản ALPHA CUỐI.** 0.9 chuyển sang `4 - Beta`, nơi API coi như đã chốt - nên
mảng "đổi API adapter một lượt" phải làm đủ ở đây, và mọi tên công khai sinh ra
ở bản này là tên phải sống tiếp.

### Kiểm toán toàn diện (2026-08-21) - 26 mục đã vá, hai trong đó chỉ Linux thấy được

Bốn đợt đọc từng dòng ~11.000 dòng mã mới và sửa, cộng một đợt **chạy thật trên
Linux** - hệ điều hành mà bản này sẽ chạy trong production, trong khi máy phát
triển là Windows. Toàn bộ ghi ở `.claude/docs/kiem-toan/0.8-kiem-toan-toan-dien.md`.

#### ⛔⛔ C4 - toàn bộ tính năng đa tiến trình KHÔNG CHẠY trên Linux

```text
RuntimeError: A SemLock created in a fork context is being shared with a process
in a spawn context. This is not supported.
```

`ProcessLink` tạo semaphore bằng ngữ cảnh `multiprocessing` **mặc định**, còn
`Supervisor` sinh con bằng **`spawn`**. Ngữ cảnh mặc định khác nhau theo hệ điều
hành: Windows chỉ có `spawn` nên hai vế trùng nhau **một cách tình cờ**; Linux
mặc định `fork` (và `forkserver` từ Python 3.14), nên chúng lệch.

Đo được: **26 test đỏ** trên Linux, **0 đỏ** trên Windows, cùng một mã nguồn.

⭐ **Không phép đo nào trên Windows có thể phát hiện điều này** - điều kiện gây
lỗi không tồn tại ở đó.

Vá bằng **một nguồn sự thật**: `xime/core/_mp.py` giữ `MP_CONTEXT`, và cả
`core/link` lẫn `core/bootstrap` cùng đọc từ đó. Gốc của lỗi không phải chọn sai
ngữ cảnh mà là **hai chỗ cùng quyết định một thứ mà không biết nhau**. Test canh
đi thành cặp: không ai tạo nguyên thủy bằng ngữ cảnh mặc định · đúng **một** lời
gọi `get_context` trong toàn bộ `xime/`.

#### ⛔ C5 - `SocketAdapter.assign_slot()` ném `AttributeError`

Nó đọc `self._path_override`, mà **không nơi nào trong repo gán thuộc tính đó** -
tàn dư của API trước 0.8, khi `__init__` còn nhận `path`. `assign_slot()` là
đường **bắt buộc đi qua** khi chạy đa tiến trình, nên mọi ứng dụng dùng
`SocketAdapter` với `share_load()` sập lúc khởi động.

Bốn lớp lẽ ra bắt được mà không lớp nào bắt: test socket **tự bỏ qua trên
Windows** · test cụm dùng web adapter · ba đợt đọc mã thấy một `if` trông hợp lý
· `mypy` **không nằm trong extra `dev`** cho tới chính đợt này.

### Đợt 5 (2026-08-21) - hai lỗi do REPO NGOÀI báo, cả hai là lỗ của 0.8

Bốn đợt trên là **tự soi**. Hai mục dưới đây do `Base Platform/data` báo sau khi
họ di trú thật sang khối `process:`, và cả hai là **lỗ do chính 0.8 sinh ra** -
không phải nợ cũ. Báo cáo gốc giữ nguyên ở
`.claude/docs/bao-cao-van-de-tu-repo-ngoai/`.

#### ⛔ C6 - gRPC tụt xuống PLAINTEXT khi di trú sang khối `process:`

Đường khoá phẳng chép `grpc.tls` vào ô cấu hình (`_FLAT_SOURCES`); đường
`process:` / `processes:` thì **không**, và adapter gRPC **không có đường lui**.
Nên đổi cách khai địa chỉ - không đụng một chữ vào khối `grpc:` - là **mất mTLS**.

Đo được hai chiều, cùng một `application.yml`, cùng cert:

```text
TRƯỚC:  grpc default: ... 9795 (PLAINTEXT)  + WARNING
SAU:    grpc default: ... 9795 (mTLS)
```

Ba tính chất khiến nó đắt hơn một lỗi cấu hình thường: nó **đi đúng đường tài
liệu chỉ** · nó hỏng theo chiều **an toàn -> kém an toàn** (không test nào đỏ,
service vẫn lên, client cũ **vẫn gọi được** vì plaintext nhận cả bên không cert)
· và dấu hiệu duy nhất là một dòng WARNING lẫn giữa vài chục dòng khởi động.

⭐ **gRPC là một trong ba adapter, và là cái duy nhất hỏng**: `web` kế thừa
`server.ssl`, `socket` luôn đọc `permission`/`allowed_uids` từ khối chung. Nên
đây là **sót**, không phải một lựa chọn thiết kế - và chính docstring của web đã
lập luận đúng chuyện này, chỉ là gRPC không có hành vi đó.

Sửa: `GrpcAdapter.resolve_tls()`, cùng khuôn `WebAdapter.resolve_tls()`. Ô thắng
khối chung; muốn plaintext thì khai `tls: {}` tường minh, đúng khuôn `ssl: {}`.

⚠ **App dùng khoá phẳng không đổi hành vi một chút nào** - đường phẳng chỉ chép
`tls` vào ô *khi `grpc.tls` có mặt*, nên khi nó vắng thì đường lui cũng đọc ra
`None`. Có test đối chứng dương khoá đúng điều đó.

#### ⚠ C7 - adapter không bao giờ nói nó đã lên, chỉ nói ở đâu nó KHÔNG chạy

`grpc/_adapter.py` có đúng **2 lệnh log, cả hai là `warning`**; `socket/_adapter.py`
có **0**. Nghĩa là một cụm gRPC **khoẻ** sinh ra log **giống hệt** một cụm gRPC
**hỏng** - trạng thái tốt không để lại dấu vết nào để đối chiếu.

Nó **cộng hưởng** với C6: khi mọi thứ log nói về gRPC đều là cảnh báo thì không
có mốc dương nào để so, nên một endpoint tụt xuống plaintext lại càng khó thấy.

Sửa: cả ba adapter ghi một dòng `INFO` lúc bind xong, **chế độ bảo mật nằm cùng
dòng với địa chỉ**:

```text
INFO | web default: process main serving on 0.0.0.0:8086 (HTTPS+mTLS)
INFO | grpc default: process main serving on 0.0.0.0:9095 (mTLS)
INFO | socket default: process main serving on /run/x.sock (0600, any uid)
```

Đặt chế độ cùng dòng chứ không tách thành cảnh báo riêng có một cái lợi mà một
dòng WARNING không có: người đọc thấy nó **mỗi lần**, ở đúng chỗ họ đang tìm, thay
vì phải nhận ra **sự vắng mặt** của một cảnh báo.

⚠ Dòng của `socket` nói `any uid` khi `allowed_uids` rỗng - lúc đó quyền file là
chốt chặn **duy nhất**, và đó là thứ trước nay phải suy từ chỗ trống.

#### ⚠ Một con số bàn giao sai, tìm ra nhờ chính đợt này

`.claude/CLAUDE.md` ghi kỳ vọng **2518 passed** cho phiên Windows. Đo lại HEAD
sạch: **2520 passed / 6 skipped**. Con số cũ ghi giữa chừng commit `1821106`,
trước khi file test cuối của commit đó xong - **đúng lúc viết, rồi repo đi tiếp**.
Nó sẽ khiến phiên Windows đi tìm một lỗi không tồn tại. Sau đợt 5: **2528 passed
/ 6 skipped**.

### Đã thêm

- **`PublishOutcome`** cho `EventBus.publish()`: `SCHEDULED` / `NO_HANDLERS` /
  `DROPPED`. Trả nợ luật *một giá trị mang một nghĩa* khai từ 0.7.2 và hẹn tới
  0.8 vì đóng nó là **đổi chữ ký công khai** - mà 0.8 là bản alpha cuối. Bỏ qua
  giá trị trả về thì hành vi y như trước.
- **`lmdb.file_mode` / `lmdb.dir_mode`** (mặc định `0600` / `0700`).
- **`Block.init_keys`** trong bản mô tả cấu hình: khoá mà `xime init` **mở sẵn**
  dù framework có mặc định riêng.
- **`xime/core/_mp.py`**: `MP_CONTEXT` và `view_of`, nền đa tiến trình dùng
  chung, chỉ phụ thuộc thư viện chuẩn.
- **`xime/core/config/_mode.py`**: `parse_mode` dùng chung cho `localfs` và
  `lmdb` - trước đó mỗi bên một bản.

### Đã sửa

| | |
|---|---|
| **Kho LMDB world-readable** | Tệp và thư mục kho ra `0644`/`0755`, trong khi kho giữ hãm nhịp đăng nhập và thử thách passkey, và đường dẫn tài liệu khuyên dùng là `/dev/shm` (mode `1777`). **Ba** chỗ tạo tệp chứ không phải một. Kho tạo bởi bản cũ được **hạ quyền khi mở lại**, một chiều |
| **Unix socket dùng chung hở trong cửa sổ khởi động** | Cha `bind()` rồi `listen()` mà không `chmod`, trong khi cửa sổ tới lúc con chặt quyền **có thể dài 60 giây** và `allowed_uids` mặc định rỗng. Nay `chmod 0600` **trước** `listen()` |
| **Thăng cấp primary không chạm `RefDataArena`** | Cờ *"tôi có phải primary"* nằm ở hai chỗ, chỉ một chỗ được cập nhật, mà `publish()` hỏi đúng cái không được cập nhật - primary **mới** không bao giờ cập nhật được khoá JWT nữa |
| **Watchdog dùng đồng hồ nhảy được** | Giờ tường nhảy tiến 30 giây làm cha **giết mọi con đang khoẻ** cùng lúc, rồi chống domino **dừng cấp vai primary vĩnh viễn**. Cả hai đầu nay dùng `monotonic` |
| **Cảnh báo "kênh sắp đầy" đo sai đại lượng** | Đếm hộp thư **đến** rồi in câu về **bảng ghi**. Sai cả hai chiều, và không một test nào chạm tới hàm đó |
| **`sweep_orphans()` không ai gọi** | Docstring xếp nó là lớp che `kill -9` **duy nhất**, và không đường khởi động nào gọi. Nay chạy trong `run_supervisor()`, và phủ **cả ba** họ vùng nhớ thay vì một |
| **Cờ `stale` của `RefData` chỉ nhìn thấy từ tiến trình đã hỏng** | Nay nằm trong header vùng nhớ chung, mọi tiến trình đọc được. Dùng 2 byte đệm sẵn có nên **tổng kích thước không đổi** |
| **`_check_parts` xoá thư mục bảng tại chỗ** | Đổi `parts` là sự kiện lúc triển khai, tức đúng lúc N tiến trình cùng chạy đoạn đó, và `ignore_errors=True` nuốt mọi va chạm. Nay `os.rename` nguyên tử rồi mới xoá |
| **Không có hãm khi con chết liên tục** | Mỗi giây một lần `spawn` (~83 MB RSS, ~1 giây CPU mỗi lần). Nay 1s, 2s, 4s... trần 30s, reset khi con sống quá 60s, `CRITICAL` từ lần thứ 10. Lời hứa "luôn dựng lại" giữ nguyên |
| **`xime init <tên>` sinh dự án không chạy được** | `config`, `resources`, `xime` và tên trùng thư viện chuẩn nay bị **từ chối**; khoá trùng trong danh sách file nay **nổ** thay vì đè im lặng |
| **`xime check config` mù với tên KHỐI gõ sai** | `serber:` cho `clean` trong khi `server.porrt` bắt được. Nay gợi ý khi tên lạ gần giống tên đã biết, im khi không giống |
| **Khối `process:` không có trong bản mô tả cấu hình** | Phép dò trôi dạt mù về mặt cấu trúc với hình dạng `read(SINGLE_KEY)` |
| **Dự án `xime init` nghe `0.0.0.0` không một chữ giải thích** | Nay `host: "127.0.0.1"` kèm giải thích. Mặc định framework **không đổi** |
| **`read_payload` không ép trần** | Trường độ dài nằm trong vùng nhớ chung; bóp méo nó đọc ra 2.104 byte từ một dòng 64 byte |
| **`ProcessLink.create` kiểm `index` sau khi đã cấp vùng nhớ** | Một `index` sai để lại rác trong `/dev/shm`; Windows tự dọn, Linux thì không |
| **Dải cổng không được kiểm** | `port: 99999` đi lọt tới `bind()` rồi nổ bằng `OSError` thô |
| **`ask()` lúc hết giờ đọc một dòng có thể đã bị tái dùng** | Nay so số thứ tự trước khi tin; không phân biệt được thì trả `NoAnswer`, không trả `NoOwner` |
| **`mypy` và `ruff` được cấu hình mà không được khai** | `[tool.ruff]` và `[tool.mypy]` có trong `pyproject.toml`, không tool nào nằm trong extra nào. Phép kiểm ngược tìm thêm `twine` và `build` cũng vậy |
| **`redis.from_url` không khai `decode_responses`** | `CacheService.get()` hứa `bytes \| None`; bật giải mã thì nó trả `str` - cùng chữ ký, hai kiểu |

### Chất lượng mã

`mypy` từ **74 xuống 41** lỗi, **không thêm một dòng `# type: ignore` nào** - bốn
nguyên nhân gốc được sửa cho đúng sự thật: `SharedMemory.buf` thu hẹp một lần ở
chỗ nhận · lớp protobuf sinh lúc chạy khai là `Any` thay vì `type` ·
`Application.get(cls: type[_T]) -> _T` thay vì `-> object` (gỡ được **8 dòng
`# type: ignore[assignment]`** mà chữ ký cũ ép người gọi phải viết) · bốn chỗ
thiếu chú thích biến.

⚠ 41 lỗi còn lại **cố ý không dập tắt**: chúng là ma sát với stub thư viện ngoài,
`Adapter` Protocol cố ý không khai `scaling`, và mã nội soi kiểu. C5 được tìm ra
bởi đúng loại `attr-defined` - dập tắt cả loại là bịt đúng cái vừa trả tiền.

### Rà trước phát hành (2026-08-20) - bảy phát hiện, ba trong đó chặn phát hành

Một lượt rà toàn bộ trước khi đóng bản, theo mười nhóm: số hiệu bản · test và
lint · đóng gói · phụ thuộc · ba script kiểm tài liệu · bề mặt API công khai ·
bốn app thật · `xime init` đầu-cuối · tài liệu · rác còn sót.

⭐ **Ba lỗi nặng nhất đều nằm ở chỗ CÔNG CỤ ĐO nói dối**, không nằm ở logic - và
cả ba đều lọt qua 2376 test đang xanh.

#### ⛔ A. Dự án do `xime init` sinh ra KHÔNG khởi động được

```text
StartupException: Web Endpoint Without A Port
  Config: process.web.default
```

Trước 0.8, khối `server:` và khối `grpc:` đều **tuỳ chọn**: vắng mặt thì
`WebServerConfig()` cho `0.0.0.0:8080`, `GrpcServerConfig()` cho `:50051`, và
ứng dụng chạy - docstring của lớp sau nói thẳng *"All fields have sensible
defaults so the block is optional."* Phép **dịch khoá phẳng** của 0.8 làm rơi
mất phần đó.

Trình tạo thì cố ý để `server:` ở dạng chú thích, đúng theo luật chia đã chốt
(*"chú thích những gì framework mặc định ĐƯỢC"*). Hai quyết định đúng riêng lẻ,
gặp nhau thì `xime init x && cd x && python main.py` chết ngay lúc khởi động.

⭐⭐ **Vì sao 100 test của giai đoạn 8 không thấy: test đầu-cuối GHI THÊM một
khối `server:` vào `application.yml` trước khi chạy**, để ghim một cổng trống.
Nó chứng minh được việc nối dây, và mù hoàn toàn với câu hỏi *"file vừa xuất ra
có chạy được không"* - vì nó sửa chính cái file đang cần đo.

Vá ở `_FLAT_DEFAULT_PORTS` (`core/bootstrap/_processes.py`), **chỉ trên đường
khoá phẳng**: vắng `server:` nghĩa là *"cho tôi mặc định"* - hợp đồng cũ; còn
viết `process: web: { default: {} }` nghĩa là *"tôi đang mô tả topology"*, và ở
đó một ô thiếu địa chỉ nhiều khả năng là gõ nhầm (`porrt:`) - khoá lạ hiện chưa
bị từ chối, nên chính thông báo lỗi đó là thứ duy nhất bắt được nó.

Đo bán kính: **0/27 app** trong workspace bị ảnh hưởng (tất cả đều đã khai
`server:`). Nó cắn **người dùng ngoài** và cắn chính trình tạo.

Kèm hai test đo **đúng file trình tạo xuất ra**, không thêm một dòng nào; đối
chứng gỡ bản vá ra thì **cả hai đỏ**.

#### ⛔ B. `xime config --print` chưa từng tồn tại

```text
xime: error: unrecognized arguments: --print
```

Được nhắc ở **19 chỗ**: tài liệu vn/en, cả hai README, README của dự án do
`xime init` sinh, một thông báo lỗi lúc chạy của starter lmdb, và **header của
mọi `application.yml` đã sinh ra** - tức những file nằm trên đĩa người dùng và
không bao giờ được sửa lại.

Vì thế nhận `--print` (hành động mặc định) thay vì gỡ chữ đó khỏi tài liệu; loại
trừ lẫn nhau với `--example`, vì hai cờ hỏi hai file khác nhau.

⭐ Kèm phép dò mới, và nó là phần đáng giữ hơn bản vá: `tests_temp/cli_docs/`
**chạy mọi dòng lệnh `xime ...` viết trong khối code của tài liệu qua chính
parser của CLI**. Không phép dò nào có sẵn bắt được lỗi này -
`check_doc_imports.py` chỉ soi dòng `from xime... import`, còn 100 test của
giai đoạn 8 gọi `main([...])` bằng đối số **do test tự chọn**. Đúng bài học
0.7.0: *đi đúng con đường TÀI LIỆU hướng dẫn* - ở đây theo nghĩa đen nhất, chính
những ký tự người đọc sẽ gõ lại.

⚠ Bản đầu của phép dò soi cả nháy đơn ngược trong văn xuôi và **kêu oan 15/16
lần** (ô bảng, câu văn nhắc tên lệnh). Đã siết về đúng phạm vi nó khai. Nó vẫn
tìm ra một dòng lỗi thời thật: bảng "việc cần đóng góp" của `contributing.md`
còn liệt kê `xime new my-service` như việc chưa ai làm.

#### ⛔ C. `check_dep_advisories.py` in `SACH` trong khi pip-audit KHÔNG chạy

Bước 1b của hướng dẫn phát hành. Phanh dò cũ:

```python
if "pip_audit" not in output and proc.returncode not in (0, 1):
```

**Nó hỏng đúng ở ca nó sinh ra để bắt**: thiếu pip-audit thì Python in
`No module named pip_audit`, tức chính thông báo lỗi **chứa chuỗi `pip_audit`**,
điều kiện thành `False`, và script rơi xuống nhánh `SACH`.

Đo 2026-08-20: **pip-audit không được cài trên máy này**, và script vẫn in
`SACH - khong advisory nao tren bo san dang khai` kèm mã thoát 0.

Nay **ba kết cục** (luật 03 mục 4b): `SACH` (0) · `CHUA KET LUAN DUOC` (2) ·
`CON MUC CHUA XU LY` (1), và cái đầu chỉ in khi thấy **mốc dương tính**
`No known vulnerabilities found` trong đầu ra của pip-audit.

⭐⭐ Nguyên nhân sâu hơn bản vá: **công cụ của bước 1b không được khai ở đâu
cả** - hướng dẫn phát hành phụ thuộc vào một chương trình mà không file nào nói
là cần, nên nó biến mất khỏi máy lúc nào không ai biết. Nay `pip-audit>=2.7` nằm
trong extra `dev`.

Kèm `_warn_about_stale_accepted()`: danh sách `ACCEPTED` tự khai là *"quyết định
có thời hạn"* nhưng trước đây chỉ được in ra **khi có gì đó khớp** - nghĩa là
đúng lúc nó hết hạn thì nó biến mất khỏi màn hình. Đọc ngược lại: càng sạch thì
càng không ai đọc lại nó.

#### ⚠ D. Số hiệu bản còn ở 0.7.2

`pyproject.toml`, giá trị dự phòng trong `xime/__init__.py`, và tiêu đề
`## [Chưa phát hành]` của chính file này. Đã nâng 0.8.0.

⚠ `xime.__version__` đọc từ metadata distribution, **đóng băng tại lần
`pip install -e .` cuối** - nên nó còn báo `0.7.2` cho tới khi cài lại. Đây là
cơ chế đã biết, không phải lỗi mới.

#### ⚠ E. `LayoutMismatch` là một tên mang hai nghĩa

`xime.core.link` và `xime.core.refdata` cùng xuất khẩu tên đó cho **hai lớp khác
nhau**:

```text
xime.core.link     xuất  LayoutMismatch  ->  lớp A
xime.core.refdata  xuất  LayoutMismatch  ->  lớp B

import cả hai trong một file: cái sau che cái trước, im lặng.
```

Sau hai dòng import đó `except LayoutMismatch:` bắt đúng một trong hai, cái còn
lại đi xuyên qua. Không lỗi lúc import, không cảnh báo. Luật 03 ở tầng **từ vựng**.

⚠ Khối minh hoạ trên cố ý **không viết dạng `from ... import ...`**: hai lớp đó nay mang
tên khác (`LinkLayoutMismatch` / `RefDataLayoutMismatch`), nên một dòng import thật ở đây
sẽ làm `check_doc_imports.py` kêu mãi mãi về một API đã được sửa. Phép dò kêu oan là phép
dò sẽ bị tắt.

Và cùng lúc một chỗ hỏng thứ hai: **cả hai kế thừa thẳng `Exception`**, nên
`except XimeException:` - lưới cuối mà framework dạy người dùng bắt - không bắt
được chúng, `except LinkError:` / `except RefDataError:` cũng không.

Nay là `LinkLayoutMismatch(LinkError)` và `RefDataLayoutMismatch(RefDataError)`,
cả hai dưới `XimeException`. `LinkError` chuyển sang module lá
`core/link/_errors.py` để `_layout.py` lấy được lớp nền mà không tạo vòng import.

Kèm `tests_temp/api_surface/` canh cả hai bất biến: không hai package công khai
nào xuất cùng một tên cho hai thứ khác nhau · mọi ngoại lệ xuất khẩu đều nằm
dưới `XimeException` **và** dưới lớp nền của chính package nó. Đối chứng: **2 đỏ**.

#### ⚠ F. 1.063 dấu gạch dài trong toàn repo

Luật văn phong của chủ dự án cấm dấu gạch ngang dài trong **mọi** văn bản, kể cả
comment code. Đếm ra:

| Vùng | Số dấu |
|---|---|
| `docs/` + hai README | **287** trên 29 file, trong đó **34 nằm bên trong khối code** |
| `xime/**/*.py` | **350** trên 117 file (137 chú thích · 196 docstring · **11 chuỗi thông điệp**) |
| `tests_temp/**/*.py` + `.claude/` + `CLAUDE.md` | **418** |
| `pyproject.toml` | **8** |

Tài liệu của 0.8 thì sạch từ đầu (**0 dấu**) - toàn bộ số trên là văn bản của các
bản trước.

⚠ Phép quét đầu tiên bằng `grep` với escape unicode trả về **0** và **con số đó
sai**; Python đếm ra 287. Đúng bài học đã ghi: *con số 0 của một phép dò hỏng
trông y hệt một repo sạch*, nên phải có đối chứng.

⚠ Phép kiểm thứ hai tôi dùng để tự trấn an **cũng nhắm sai**: nó ghép cặp dòng
từ `git diff -U0` (312 dòng cũ với 644 dòng mới) nên so những dòng không liên
quan. Phép đo đúng là đưa thẳng cho `ast`: **400/400 khối code Python trong tài
liệu vẫn phân tích được**, và **0 dòng nào từng bắt đầu bằng dấu gạch dài** nên
rủi ro ăn mất thụt lề chưa bao giờ tồn tại. Đã gói thành
`.claude/scripts/check_doc_code.py`.

⭐ Với mã nguồn thì phân loại trước khi quét, bằng `tokenize` + `ast`: chỉ **11**
trong 350 dấu nằm ngoài chú thích và docstring, và cả 11 đều là thông điệp log
hoặc lỗi (`"Modbus device '%s' at %s:%s - %d poll group(s)"`). Không test nào
khoá cứng chúng. Nghiệm thu là **2412 test chạy lại sau khi quét**, cộng
`ast.parse` trên toàn bộ `xime/` và `tests_temp/`, cộng `tomllib` trên
`pyproject.toml`.

#### ℹ G. `ruff check xime/` không bao giờ xanh

Ba cảnh báo `UP046` (dùng cú pháp type parameter PEP 695 thay `Generic[T]`) ở
`CrudRepository`, `Store`, `RefData`. **Cố ý không sửa** - cả ba là lớp nền công
khai người dùng kế thừa và nhận cấu hình bằng tham số class; đổi cỗ máy dựng lớp
của chúng để lấy về một cú pháp mới hơn thì không người dùng nào được lợi.

Nhưng để nó đỏ mãi cũng sai: **một phép dò không bao giờ xanh là một phép dò
không ai còn đọc** - ba dòng quen thuộc dạy người ta lướt qua, và dòng thứ tư sẽ
lướt cùng. Nay nằm trong `ignore` **kèm lý do và điều kiện xét lại**.

#### Những gì đã kiểm và SẠCH

| Nhóm | Kết quả |
|---|---|
| Đóng gói | `twine check` PASSED · sdist 288 mục / 671 KB, **không rò rỉ** `.claude/`, `tests_temp/`, `pypi_token` · wheel 0 file `.pyc` |
| Cài venv trắng | cài từ **sdist** rồi import cả bốn package mới: chạy |
| Bốn app thật | data **388** · linh-kien **295** · crm **53**, tất cả xanh trên cây mã editable |
| Ba script tài liệu | `check_doc_imports` 344 tên / 44 file ALL OK · `check_doc_register` 0 fail · `find_reexport_gap` 3 file, đều là re-export riêng tư có chủ đích |
| Tài liệu vn/en | số mục khớp từng cặp cho cả sáu tài liệu của 0.8 |
| Rác giàn đối chứng | không còn mutation nào sót trong `xime/` |
| `xime init` đầu-cuối | `check config` CLEAN · `check module-level` CLEAN trên dự án vừa sinh |

### Giai đoạn 8 - Trình tạo cấu hình: `xime init` · `config` · `check config` (2026-08-20)

Chủ dự án đề xuất giữa lúc đang bàn chỗ đặt `lmdb.path`: **một công cụ sinh file
cấu hình, mặc định nằm ở công cụ chứ không ở framework, tạo hết nhưng phần lớn
để dạng chú thích để người vận hành gỡ ra và sửa.**

⭐ Ý đó **giải luôn câu đang mở**. Framework không đoán được `lmdb.path` vì nhiều
service dùng chung một máy; **trình tạo thì đoán được, vì nó biết tên dự án lúc
tạo**. Cả cái thang phân giải bốn bậc từng bàn (`$RUNTIME_DIRECTORY` -> băm
đường dẫn -> temp) biến mất.

#### ⚠ Một nửa đề xuất bị chỉnh, và repo này có bằng chứng cả hai chiều

Đề xuất ở dạng mạnh - *"mặc định nằm ở tool tạo, không phải framework"* - là
nguy:

| Ca thật trong chính repo này | Kết cục |
|---|---|
| 0.7.1 đổi **bốn hành vi** (`save_upload` trần 32 MiB, `stream_object` ép tải xuống...) | tới **cả 31 app** ngay, vì chúng là **mặc định của framework** |
| **A1 fail-open JWT** | **19 app vẫn thủng**, vì lỗ nằm trong `config/jwt.py` **của họ** |

> Giá trị nào rời khỏi framework thì hành vi của app **đóng băng ở phiên bản nó
> được tạo**.

**Luật chia đã chốt:**

> **Chú thích những gì framework mặc định ĐƯỢC. Ghi thẳng chỉ những gì nó KHÔNG
> mặc định được.**

Đọc file là biết ngay: dòng không chú thích = thứ deployment này thật sự đã
quyết; dòng chú thích = tài liệu, và nó có cũ đi cũng không cắn ai vì nó trơ.

#### ⭐ Ranh giới "framework được đoán tới đâu", phát biểu lại cho đúng

Framework **đã** mặc định `server.port: 8080` trong khi `lmdb.path` thì từ chối.
Nghe như bất nhất, nhưng không:

| Trùng nhau thì | Ví dụ | Mặc định được? |
|---|---|---|
| **Hỏng ỒN ÀO** | hai app cùng cổng 8080 -> `EADDRINUSE`, chết lúc khởi động | ✅ |
| **Hỏng IM LẶNG** | hai app cùng `lmdb.path` -> dùng chung bảng hãm nhịp, không lỗi, không log | ⛔ |

> **Framework được phép đoán khi đoán sai thì có tiếng động. Không được phép khi
> đoán sai thì im lặng.**

#### Thêm

- **`xime config --print`** - in toàn bộ bề mặt cấu hình ra stdout, **không ghi
  gì**. ⭐ Mảnh giá trị cao nhất và rủi ro gần bằng 0: nó phục vụ được **cả 31
  ứng dụng đang có ngay hôm nay**, trong khi `xime init` chỉ giúp app mới.
- **`xime check config`** - đối chiếu `application.yml` của app với bề mặt đó.
  Bắt **khoá gõ sai**, thứ hôm nay là một server im lặng không có route nào.
- **`xime init <ten>`** - cây thư mục + file cơ bản. Sinh **ít** có chủ ý:
  `main.py`, `config/`, một controller mẫu, hai file cấu hình, `pyproject.toml`,
  `.gitignore`, `README.md`.
- `xime/cli/_config_spec.py` - **một** bản mô tả, ba lệnh dùng chung.
- `docs/{vn,en}/cli.md`.

#### ⭐⭐ Bản mô tả tự nó cũng già đi, nên nó có hai lớp chống

Một bản mô tả viết tay là **một ảnh chụp** - đúng loài lỗi mà file cấu hình sinh
sẵn mắc phải, chỉ lùi lên một tầng.

| Lớp | Làm gì |
|---|---|
| **Suy từ pydantic** | `server`, `grpc`, `logging` đã có model, nên đọc thẳng `model_fields`: mặc định **không thể lệch** với code đọc chúng |
| **Test canh** | quét `runtime.get("<khối>")` trong `xime/`; thiếu ở bản mô tả là **test đỏ** |

⭐ Kèm một **test đối chứng cho chính phép quét**: nó phải tìm thấy ít nhất 5
khối, vì con số 0 của một phép quét hỏng trông y hệt một framework sạch.

#### ⚠⚠ `complete` - công tắc chống kêu oan, và nó trả nợ ngay lượt chạy đầu

Chỉ khối tự khai đã liệt kê **đủ** khoá mới được `check config` báo *"khoá lạ"*.

Lượt chạy đầu tiên trên `data-service` tố `grpc.clients` và `grpc.internal`.
**Cả hai đều hợp lệ** - `grpc:` còn mang cả cấu hình client SDK, do một module
khác đọc. Đã hạ `complete` của `grpc` và thêm khối `cors` còn thiếu.

⭐ **Hiệu chuẩn trên 30 file cấu hình thật của workspace: 29 file sạch**, và file
duy nhất kêu là một app **Java Spring Boot** (`server.ssl.key-store`), không
phải cấu hình Xime.

#### ⭐⭐ Một lỗi trong code sinh ra, một chẩn đoán sai của chính tôi

**Lỗi thật:** trình tạo gọi `configure_routing`, một hàm **không tồn tại**. Nó
trông y hệt một hàm hợp lệ, và chỉ lần khởi động thật mới nói. Đúng khuôn 0.7.0
- ba lỗi mức Cao của bản đó đều nằm ở **chỗ nối**.

⚠⚠ **Và một bài không có trong kế hoạch: phép đo đầu tiên của tôi cũng sai.**
Sau khi sửa `configure_routing`, tôi liệt kê route bằng `adapter.build_app(app)`
và thấy `/ping` vắng mặt, rồi kết luận *"`configure_controllers` phải nhận
module chứ không nhận package"*. Kết luận đó **sai**: `build_app()` không chạy
`lifespan`, mà route được đăng ký **chính trong lifespan**. *"Không có route"* là
triệu chứng của **công cụ đo**, không phải của code sinh ra.

📌 Cái sai thật là **đổi hai biến cùng lúc** (dạng module + cách đo) rồi gán công
cho biến sai. **Đối chứng bắt được**: gỡ bản "sửa" đó ra thì **không test nào
đỏ**, vì nó chưa bao giờ sửa gì cả. Đã trả về dạng package - nó còn hợp hơn cho
một dự án sinh sẵn, vì thêm một file controller là có route mà không phải sửa
`config/web.py`.

Nay có một test khởi động dự án vừa sinh bằng **tiến trình thật**, cổng thật,
một lời gọi HTTP thật; cộng hai test bắt nó qua được **chính hai lệnh kiểm của
framework**; cộng ba test soi **hình dạng `main.py` bằng AST** - vì `use()` đặt
nhầm vào `if __name__` chạy hoàn hảo với một tiến trình và chỉ hỏng khi có
`share_load()`, thứ test khởi động cũng không thấy.

#### Đổi

- **Kho LMDB in một dòng lúc khởi động**: đường dẫn · **RAM hay đĩa** · chỗ trống
  · `total_max`. Câu *"kho ở `/dev/shm/x`"* mang **hai nghĩa** (mất khi reboot /
  sống qua reboot) mà trước nay không gì tách ra - luật 03.
  ⭐ **BA kết cục, không phải hai**: Linux đọc `/proc/mounts` nên biết chắc;
  Windows thì **không biết**, và trả `False` ở đó là nói dối vì một ổ đĩa RAM
  trông y hệt ổ thật với mọi API Python.
- ⛔ **`total_max` vượt dung lượng trống của hệ tệp nay CHẶN KHỞI ĐỘNG.** Trên
  tmpfs trang nhớ **không đuổi ra được**, mà VPS thường không có swap - nên lời
  hứa đó không vỡ bằng *chậm đi* mà bằng **OOM kill cả tiến trình**. Bắt luôn ca
  Docker cấp `/dev/shm` mặc định 64 MB.
  ⚠ *"Không đo được"* **không** bị đối xử như *"không đủ chỗ"*.
- `docs/{vn,en}/store.md`: thêm mục đặt kho trên tmpfs, kèm khuôn systemd
  (`RuntimeDirectoryPreserve=restart` là dòng dễ quên nhất) và cảnh báo `/tmp`
  **không chắc là RAM**.

#### ⛔ Đã thử rồi bỏ: đổi khối `lmdb:` thành `store:`

Bản đầu của giai đoạn này đổi tên khối vì *"`Store` là khái niệm, `lmdb` là
backend"*. Chủ dự án chỉ ra chỗ hỏng, và đo lại thì đúng:

- `store:` đứng cạnh `storage:` (kho file/blob) trong cùng file YAML, **khác
  nhau hai chữ cái mà là hai hệ thống con không liên quan gì nhau**. Tệ hơn bẫy
  `process`/`processes`: hai cái kia là cùng một khái niệm ở hai số lượng.
- `storage:` tách `storage.local` / `storage.s3` **vì nó có Protocol và nhiều
  backend**. `Store` thì **cố ý không có Protocol, một backend duy nhất** - buổi
  08-19 đã bỏ Protocol đi. Không có tầng khái niệm nào để lơ lửng bên trên.
- **`redis:` đã là một khối mang tên backend cho một kho KV khác.** `lmdb:` nhất
  quán với nó.

📌 Lý do bản đầu sai không phải là chọn nhầm tên, mà là **áp khuôn của `storage`
lên một thứ không cùng hình dạng với `storage`**.

#### ⭐ Redis Ở LẠI, và ranh giới ba chiều được viết ra (chốt 2026-08-20)

Câu hỏi của chủ dự án: `starters/cache` và `starters/redis` có trùng nhau không,
có nên xoá không, và *"nếu cần Redis thật thì nó ở tầng ứng dụng thôi đúng
không"*.

Đo trước: `cache` là **Protocol**, `redis` là **backend** - đúng khuôn `storage`,
không trùng nhau; và `CacheService` có **đúng một** chỗ dùng thật trong 31
codebase (`TrustKeyL2Cache` của data-service).

✅ **Chủ dự án chốt: giữ cả hai.** *"Không phải lúc nào cũng dùng LMDB được."*

⭐⭐ Và lý do đó có một cơ chế cụ thể đằng sau: **`Store` đóng đúng MỘT TẦNG của
một lỗ hổng, không đóng cả cái lỗ.**

| Hãm nhịp đăng nhập giữ ở đâu | Hạn mức thật bị nhân theo |
|---|---|
| RAM tiến trình | **số tiến trình** |
| `Store` (LMDB) | **số máy** |
| Redis | không nhân |

⚠ **Chia shard không cứu được tầng còn lại**: shard cắt theo `org_id`, còn hãm
nhịp khoá theo **IP hoặc tên đăng nhập** - hai trục khác nhau, và người **chưa
đăng nhập được thì chưa có `org_id`** để mà định tuyến.

⭐ Ca này hoá ra **chính là điều kiện mà mục 2.7 tự viết ra** hồi 08-19
(*"lập luận trên đứng khi định tuyến theo shard"*), nên nó **không mở lại** chốt
*"phạm vi một máy"*. Ranh giới giữ hai quyết định tương thích:

> **Mọi thứ framework tự cấp - `RefData`, `Store`, `ProcessLink` - là MỘT MÁY,
> luôn luôn. Cần nhiều máy cùng thấy thì đó là lựa chọn của ứng dụng, và nó đi
> qua `CacheService`.**

Đã ghi: bảng chọn ba chiều ở `docs/{vn,en}/starters.md` · cùng ranh giới trong
docstring `CacheService` · mục **2.7b** của tài liệu cache · khối `redis` trong
bản mô tả cấu hình nay có **khoá thật** (`url` bắt buộc, `max_connections`).

⚠ Kèm hai dòng **vừa thành lỗi thời vì chính quyết định này**, đã sửa: tài liệu
cache mở đầu bằng *"muốn bỏ Redis"*, và tài liệu bus dựa một lập luận vào câu đó.

📌 Con số *"đúng một chỗ dùng"* là lý do câu hỏi được đặt ra, và nó **không** phải
lý do để xoá: thứ quyết định là **việc mà không cái nào khác làm được**, không
phải số người đang dùng hôm nay.

#### ⚠⚠ Đính chính phạm vi: "một máy" là chính sách của XIME, không phải của FRAMEWORK

Chủ dự án chỉnh cùng ngày, và nó đổi trọng tâm của cả mục trên: *"cái phạm vi 1
máy là cho **dự án của tôi** thôi. Tôi làm framework cho mọi người dùng thì tôi
phải làm nhiều trường hợp hơn... họ có thể nhiều máy, Docker, k8s các kiểu."*

Đọc lại nguyên văn chốt 08-19 thì nó vốn đã nói vậy: *"nhiều máy **TÔI** đã chia
shard"*. Bản ghi khi đó tổng quát hoá chữ *"tôi"* thành một điều kiện thiết kế
của framework - và đó là chỗ sai.

| Câu | Là loại gì | Áp cho ai |
|---|---|---|
| *"`RefData`, `Store`, `ProcessLink` chỉ trong một máy"* | **sự thật của CƠ CHẾ** - bộ nhớ chung và file cục bộ không bắc qua máy | **mọi người dùng framework** |
| *"chúng tôi không cần kho liên máy vì đã chia shard"* | **chính sách TRIỂN KHAI của Xime Platform** | **chỉ Xime** |

⭐ Trộn hai câu đó là đúng khuôn `PEER_APP_ID` đã phải gỡ ở 0.7.1: **framework
mang khái niệm của một người dùng cụ thể vào trong nó.**

⛔⭐ **Và nó lộ ra một cái bẫy thật cho người dùng ngoài:** `run_once()` khai là
*"MỘT lần cho cả cụm"*, nhưng *"cụm"* = **nhóm tiến trình của một `share_load()`,
tức một máy**. Ba pod k8s là **ba lần**, chạy song song.

```text
1 máy, count: 4        ->  run_once() chạy 1 lần
3 pod, mỗi pod count: 4 ->  run_once() chạy 3 lần
```

Ai đặt migration cơ sở dữ liệu vào đó rồi lên k8s sẽ có ba lần migrate đồng thời,
và framework **không có cách nào ngăn** - nó không biết pod kia tồn tại. Đã ghi
cảnh báo vào docstring `RunOnce` và một mục mới ở `docs/{vn,en}/multi-process.md`.

⭐ Trọng tâm của Redis cũng đổi theo: nó **không** phải thứ giữ lại cho một ca
hẹp, nó là **câu trả lời của framework cho cả một lớp triển khai**. `Store` là
đường nhanh của một máy; `CacheService` là đường chung của nhiều máy.

#### Kiểm chứng

| | |
|---|---|
| Bộ test | **2376 passed, 14 skipped** (sau GĐ7: 2250) - **+126** |
| Đối chứng | **34/34 đỏ** sau khi bịt bốn lỗ hổng lượt đầu |
| Bốn app thật | `data` 388 · `linh-kien` 295 · `shop` 192 · `crm` 53 |
| `check config` trên 30 file thật | 29 sạch; file còn lại là app Java |
| `check_doc_imports` | 344 tên / 44 file ALL OK |

### Giai đoạn 7 - Hai phép dò, tài liệu, đo thật (2026-08-20)

Giai đoạn cuối của 0.8. Sáu giai đoạn trước dựng cơ chế; giai đoạn này dựng thứ
**canh** một luật mà cơ chế không tự giữ được.

Luật *"code ở mức module phải nhẹ"* (`rules/module-level-code.md`) chốt ngày
2026-08-19 nhưng chưa có gì cưỡng chế. Nó là luật khó giữ nhất của 0.8 vì cả hai
cách vi phạm đều **không có triệu chứng**, và vì **hôm nay chúng đúng, ngày mai
chúng sai, mà code không đổi**: thêm `count: 3` vào `application.yml` là cùng
đoạn code đó chạy bốn lần - thứ đổi nằm ở file cấu hình, không nằm ở file có lỗi.

#### Thêm

- **`xime/_startup.py`** - mốc thời gian của lần import Xime đầu tiên, và phép
  dò thứ nhất. `share_load()` đóng băng số đo tại đúng thời điểm code mức module
  vừa chạy xong; cha kêu **một** dòng nếu vượt trần, sau khi đã cấu hình logging
  và đã biết cụm có bao nhiêu tiến trình.
- **`xime check module-level`** (`xime/cli/_module_level.py`) - phép dò thứ hai.
  Quét tĩnh `main.py` và mọi module **trong dự án** mà nó import ở mức module,
  tìm lời gọi không tất định.
- **`docs/{vn,en}/multi-process.md`** - mục *"Code ở mức module chạy `N+1` lần"*:
  bảng được/không được, hai kiểu hỏng, và cả hai phép dò.

#### ⭐ Vì sao là HAI phép dò, không phải một

Hai nhóm bị cấm hỏng theo hai kiểu khác hẳn nhau, và không phép dò nào bắt được
cả hai:

| | Hỏng thế nào | Ai bắt |
|---|---|---|
| Kết nối mở ở mức module | **thừa** - `N+1` kết nối, mọi tiến trình vẫn đúng | phép dò 1 (nó **chậm**) |
| `uuid4()` ở mức module | **sai** - mỗi tiến trình một giá trị, mà code đọc nó tin là dùng chung | phép dò 2 (nó **nhanh**, phép dò 1 mù) |

> Một cái đo **hậu quả** mà không biết nguyên nhân; cái kia tìm **nguyên nhân**
> theo tên mà không thấy hậu quả. Bỏ cái nào cũng thủng theo hướng riêng.

#### ⚠⚠ Ngưỡng 1 giây của kế hoạch ĐO RA LÀ SAI

Kế hoạch thi công đề nghị **1 giây**. Đo ngày 2026-08-20, cùng máy dev, cache ấm:

| Đo | Kết quả |
|---|---|
| Riêng import framework (`xime` -> `+web` -> `+grpc` -> `+sqlalchemy`) | **1,08s**, trong đó **0,75s** nằm SAU mốc |
| `linh-kien-dien-tu` (`xime` + web + `app.config`) | **0,996s** |
| `shop-hoa-qua-tang`, ba lần chạy | **1,057s · 1,033s · 1,059s** |

> **Cả hai ứng dụng thật và lành mạnh đều vượt ngưỡng đề nghị.** Một phép dò kêu
> oan là một phép dò sẽ bị tắt, nên ngưỡng lấy ~3x số đo đó: **3,0 giây**.

⭐ Điều đáng nhớ hơn con số: **cửa sổ này bị chi phối bởi IMPORT chứ không phải
bởi "làm việc"** - khoảng một nửa là framework, nửa còn lại là cây import của
chính app. Nghĩa là phép dò 1 **không bao giờ** là phép dò chính; nó là lưới bắt
thứ thật sự bất thường, và tài liệu phải nói thẳng điều đó.

⛔ **Một đường đã cân nhắc rồi loại: trừ đi thời gian import.** Bọc `__import__`
để đo rồi trừ ra thì **trừ đúng thứ cần bắt** - một kết nối mở trong thân
`config/dependency.py` được tính là *"thời gian import"* theo đúng nghĩa đen của
phép đo đó. Lời giải làm hỏng chính bài toán.

#### ⭐ Thông báo mang PHÉP NHÂN, không chỉ mang con số

```text
Module-Level Code Is Heavy
  Measured: 6.1s from the first Xime import to share_load()
  Cost    : x5 (parent + 4 worker(s)) = 30.5s spent before serving
```

*"6,1 giây"* nghe như chuyện nhỏ; *"×5 = 30,5 giây trước khi phục vụ"* mới là thứ
khiến người ta đi sửa. Hệ số là `N+1` vì **cha cũng chạy lại `main.py`**.

Kèm ba chi tiết cố ý, đừng gỡ:

| | |
|---|---|
| Đo ở `share_load()`, **kêu** ở `run()` | Lúc `share_load()` chưa cấu hình logging (cảnh báo rơi vào hư không) và chưa biết `N` (mất phép nhân) |
| Chỉ nhánh supervisor kêu | Con cũng gánh chi phí đó, nhưng kêu ở mỗi con là nhân bản chính cái cảnh báo, và người đọc log học được cách bỏ qua nó |
| Không có công tắc tắt, không có khoá cấu hình | Nó là cảnh báo chứ không chặn ai; thêm một knob cho một dòng WARNING là thêm bề mặt API ở bản **alpha cuối** |

#### ⭐ Phép dò 2: BA mã thoát, không phải hai

`0` sạch · `1` có vi phạm · `2` **chưa kết luận được** (không tìm thấy điểm vào,
hoặc có file không parse được).

⚠ *"Không tìm thấy vi phạm"* và *"không đọc được để mà tìm"* là hai câu trả lời
khác nhau. Gộp chúng lại là để một lần chạy trong CI báo xanh trên một phép kiểm
**chưa hề chạy** - đúng lỗi `ShardValueGuard` của `identity` đã vấp, và cùng
khuôn với việc đếm **TREO** riêng ở giàn đối chứng.

Kết quả cũng in **số file đã quét**, vì đó là thứ duy nhất phân biệt *"sạch"* với
*"chạy nhầm thư mục"* khi cả hai in ra `CLEAN`.

#### ⚠ Ba chỗ rộng hơn câu chữ của luật, và mỗi chỗ một lý do

| | Luật viết | Đã làm |
|---|---|---|
| **Thân class** | *"không phải trong hàm hay class body"* | **CÓ quét** - thân class chạy lúc import y như thân module, và `class M(BaseModel): ts = datetime.now()` là ca thật |
| **`secrets.token_hex()`** | khai là chỗ mù | **bắt được** - `secrets.*` nằm trong danh sách, đóng nó tốn một dòng |
| **Decorator, giá trị mặc định của tham số** | không nhắc | **CÓ quét** - `def f(at=time.time())` được tính đúng một lần, lúc định nghĩa |

Và hai chỗ **cố ý KHÔNG kêu**, cả hai cùng module với thứ bị theo dõi:
`uuid3`/`uuid5` **tất định** theo `(namespace, name)`; `random.seed` thì ngược
chiều - nó **làm cho** mọi thứ sau đó tất định.

#### ⭐ Đối chứng: 26 bản vá, **3 chỗ ban đầu không đỏ**

Cả ba là lỗ hổng thật, và hai trong ba là **lỗ hổng của chính bản hiện thực**,
không phải chỉ của bộ test:

| Chỗ hở | Là gì |
|---|---|
| Đoán tên trần khi không có import nào | Test cũ dùng `from mylib import uuid4` - vẫn **có** alias, nên nó không đo được nhánh *"không alias"*. Bịt bằng một object của app **trùng tên với module stdlib** (`time = Clock()`), thứ phải KHÔNG bị kêu |
| ⭐⭐ **`_is_main_guard` trong bước tìm import là MÃ CHẾT** | Hàm chỉ nhìn **tầng ngoài cùng**, mà `if`/`try` là `ast.If`/`ast.Try` chứ không phải `ast.Import` - nên phép kiểm không bao giờ chạy. Hệ quả thật: **`try: import x except ImportError:` ở mức module không được đi theo**, cả một nhánh cây import biến mất khỏi phạm vi quét, và kết quả vẫn in `CLEAN` |
| Chống trùng lúc lấy khỏi hàng đợi | Không phải chuyện *"treo"* như tưởng: `a` và `b` cùng import `c` thì `c` vào hàng đợi **hai lần trước khi được lấy ra**, bị quét hai lần, và **một vi phạm được đếm hai lần** |

⭐⭐ Chỗ thứ hai đáng nhớ nhất, và nó là **khuôn ngược** của lỗi quen thuộc: mọi
lần trước, phép kiểm đúng mà **chỗ dùng** nó bị bỏ quên. Lần này **chỗ dùng có
sẵn** mà phép kiểm nằm ở tầng không bao giờ với tới dữ liệu - nhìn code thì thấy
một dòng phòng thủ tử tế, chạy thì nó chưa từng chạy. Chỉ đối chứng mới phân biệt
được hai thứ đó.

📌 Chỗ thứ ba dạy lại bài của giai đoạn 6 theo chiều khác: tôi dựng mutation kỳ
vọng nó **treo**, và nó **xanh** - vì `seen.add()` vẫn còn nên vòng lặp vẫn kết
thúc. Cái hỏng thật không phải *hang* mà là *đếm hai lần*, và nếu tin vào kỳ vọng
ban đầu thì lỗ hổng đó ở lại.

Sau khi bịt: **26/26 đỏ**.

#### Kiểm chứng

| | |
|---|---|
| Bộ test | **2250 passed, 14 skipped** (sau GĐ6: 2167) - **+83** test ở `tests_temp/module_level/` |
| Bốn app thật | `data` 388 · `linh-kien` 295 · `shop` 192 · `crm` 53 |
| Ba script kiểm chứng | `check_doc_imports` 344 tên / 42 file ALL OK · `check_doc_register` 0 fail · `find_reexport_gap` không thêm chỗ hở nào |
| `ruff check xime/` | không thêm loại cảnh báo nào |
| Phép dò 2 chạy trên chính bốn app | `linh-kien` 174 file · `shop` 207 · `crm` 147 · `data` 1, **cả bốn CLEAN** |

⚠ `data` quét được **đúng 1 file** vì `main.py` của nó đặt `use()` trong khối
`if __name__` và không import module nội bộ nào ở mức module. Kết quả `CLEAN` đó
**đúng**, nhưng con số 1 mới là thứ đáng đọc - và đó chính là lý do số file quét
được phải nằm trong output.

#### ⏭ Còn nợ có ý thức

**Hai phép đo LMDB** của mục 6.2 tài liệu kho nhóm 2 (`writemap` trên ổ thật ·
chi phí `sync` theo nhịp ghi) **chưa làm** - chúng đòi một VPS Linux, và máy này
là Windows. Không chặn gì: đó là hai phép đo để chỉnh tham số vận hành, không
phải quyết định thiết kế.

### Giai đoạn 6 - `RunOnce`, thăng cấp primary, watchdog, sức khoẻ (2026-08-20)

Giai đoạn 3 dựng được một cụm; giai đoạn này làm nó **sống sót**. Ba việc mà một
cụm không có thì chỉ là *"vài tiến trình chạy cạnh nhau"*: một chỗ cho công việc
chạy **một lần cho cả cụm**, một đường **trao lại vai** khi primary chết, và một
cách nhìn thấy con **treo** - thứ `waitpid` mù hoàn toàn.

Thiết kế: `.claude/docs/da-tien-trinh-main-va-cau-hinh-2026-08-16.md` mục 2.8,
2.8b, 2.8c, 2.9 và `.claude/docs/doi-api-adapter-2026-08-19.md` mục 4.3-4.5.
Tài liệu người dùng: `docs/{vn,en}/multi-process.md` và `core-concepts.md`.

Test: **2167 passed, 14 skipped** (sau giai đoạn 5: 2063) - **104 test mới**.
Cộng bốn app thật: `data` 388 · `linh-kien` 295 · `shop` 192 · `crm` 53.

**Không phá app nào**: 31 app hiện tại không khai `run_once()` nào, không gọi
`configure_health()`, và nhánh một tiến trình đi qua đúng những dòng cũ.

#### Added

- **`RunOnce`** (`xime.core.lifecycle`) - Protocol với tên method quy ước
  `run_once()`, cùng họ `post_construct`/`pre_destroy`. **Không decorator, không
  khai ở `config/`**. Chỉ primary chạy; framework in ra danh sách nó tìm thấy.
- **Cha ĐỢI primary báo `run_once()` xong rồi mới sinh những con còn lại.** Đây
  là chỗ `run_once` khác một job một-lần của scheduler: không phải *chạy một lần
  vào một thời điểm*, mà **chạy một lần, và mọi thứ khác đợi nó**.
- **`ProcessLink` nay được nối vào vòng đời ứng dụng** - việc cộng thêm từ giai
  đoạn 5. Cha cấp kênh trước khi sinh con, con attach, DI giữ nó, và framework
  **luôn** tạo kênh nội bộ `__xime__`.
- **`ProcessLink.announce_sync()` / `drain_sync()`** - bề mặt đồng bộ cho tiến
  trình gốc, thứ `waitpid`, đọc bộ nhớ, ngủ, và **không có event loop**.
- **`ProcessLink.create(index=...)`** - người cấp chọn ô của chính mình. Cha giữ
  ô **cuối** (`N`), con giữ `0..N-1` theo thứ tự cấu hình.
- **Watchdog** (`xime/core/bootstrap/_watchdog.py`) - con vỗ mỗi **1 giây** trên
  **task của event loop chính**; im quá **10 giây** thì cha **giết**.
- **`sd_notify`** - cha gửi `READY=1` và `WATCHDOG=1` qua `NOTIFY_SOCKET`. Không
  có thì **bỏ qua im lặng**.
- **Thăng cấp primary** - primary chết thì cha trao vai cho một con đang chạy;
  con đó khởi động adapter hạng đơn nhất và tiếp tục phục vụ. Chống domino
  **`N=3` / `T=60`**.
- **`Application.health()`** và **`configure_health()`** - phương án **B+**: dữ
  liệu luôn có, endpoint **mặc định TẮT**.

#### Quyết định đáng nhớ

- ⛔ **Tín hiệu thăng cấp là `waitpid`, không phải health check.** Đây là chỗ mô
  hình cha-con miễn nhiễm với ca *"hai primary"*: một primary treo tạm bị health
  check đọc là chết, cụm bầu người mới, rồi nó tỉnh lại. Xime **giết trước, đợi
  kernel xác nhận, rồi mới thăng cấp** - nó không thể tỉnh lại.
- ⭐ **Lỗi `start()` lúc THĂNG CẤP thì từ chối vai, không sập.** Sập là mất một
  tiến trình đang phục vụ người dùng thật vì một cái cert, và làm thế ba lần
  liên tiếp chính là domino.
- ⭐ **Hai công tắc riêng cho chống domino**: *dựng lại con đã chết* **vẫn làm**,
  chỉ *cấp vai primary* mới dừng. Mất job nền còn hơn mất khả năng phục vụ.
- **Cha quyết ai là primary, cấu hình chỉ nói ai BẮT ĐẦU với vai đó** - qua
  `SharedHandle.primary`. Thiếu trường này thì một primary đã chết, được dựng
  lại, quay về **vẫn tin mình là primary** trong khi cha đã trao vai cho người
  khác: hai primary cùng chạy job nền, và không gì báo.
- **`/readyz` của con phụ VẪN XANH khi cụm thiếu primary.** Nó vẫn nhận request
  được; thứ mất là job nền. Trả lời ngược lại thì LB rút hết con và cụm chết
  hoàn toàn vì một job nền không chạy.
- ⛔ **Hai đường dẫn sức khoẻ không xác thực**, cố ý: chúng phải trả lời được khi
  mọi thứ khác đã hỏng, kể cả khi không lấy nổi khoá verify. Bù lại thân phản hồi
  không mang gì nhạy cảm.
- **`run_once()` không có cặp huỷ**, cố ý. Ba ca thật đều không có gì để dọn, và
  thêm một hook chỉ để cho cân xứng là thêm thứ không ai dùng.

#### ⚠ Ba chỗ THI CÔNG ĐỤNG VÀO THIẾT KẾ

**1. Nhịp vỗ KHÔNG đi bằng `ProcessLink`, dù thiết kế nói nó *"đi chung chuyến"*.**

Ý đó đúng ở tầng khái niệm - cả hai đều là vùng ghi riêng cho từng tiến trình
trong bộ nhớ chung. Nhưng nhịp vỗ không được là một **dòng tin** của bus, và lý
do là số học: nhịp 1 giây × 4 tiến trình đổ vào một vòng 256 dòng thì nó vòng lại
sau **một phút**, và vì không ai đọc nhịp của người khác nên mỗi lần vòng lại
**cộng vào `missed`** - chỉ số chẩn đoán chính của bus.

> Nhịp vỗ là một **đại lượng bị ghi đè**, không phải một **sự kiện**. Bus chở sự
> kiện; đại lượng thì ở một ô riêng.

Nên nó là một vùng nhớ chung riêng, `16 + 8×N` byte cho cả cụm.

**2. Thêm `STARTUP_GRACE_SECONDS`, một hằng số thiết kế không chốt.**

Thiết kế nói `NEVER` nghĩa là *"đang khởi động"*, và đúng - nhưng nó không nói
**khi nào thì đang-khởi-động thôi là một lời bào chữa**. Không có ngưỡng này thì
một con treo **trước nhịp vỗ đầu tiên** (kẹt trong `post_construct`, chờ một kết
nối không bao giờ mở) sống mãi mãi và cha không bao giờ biết - đúng cái lỗ mà
watchdog sinh ra để bịt, chỉ dịch sớm hơn mười giây. Đặt 60 giây, rộng gấp sáu
ngưỡng im lặng, vì hai giai đoạn không cùng cỡ.

**3. Adapter hạng đơn nhất do ỨNG DỤNG khai từng biến mất khỏi con phụ.**

Phát hiện lúc thi công, và nó làm **thăng cấp vô hiệu** cho mọi adapter ngoài
scheduler. `prepare_worker` lọc adapter theo khối cấu hình của tiến trình, mà
`_reject_singleton_in_many_processes` lại **cấm** khai adapter đơn nhất ở khối
khác khối primary. Hai luật đúng riêng lẻ, gặp nhau thì con phụ không có adapter
đó để mà nhận vai: cụm mất job nền vĩnh viễn, và không gì báo.

Thiết kế mục 4.5 viết *"con biết adapter nào là singleton (`scaling`)"* - câu đó
**giả định nó có mặt ở con**, và giai đoạn 3 thì không. Nay adapter đơn nhất được
giữ ở mọi tiến trình và lấy ô cấu hình của khối primary (theo cấu trúc chỉ có
đúng một ô như vậy).

📌 Scheduler không dính vì nó do **framework** đăng ký, sau `prepare_worker` - tức
ca duy nhất chạy được hôm nay là ca đi vòng qua chỗ hỏng.

#### ⭐ Đối chứng: 24 bản vá gỡ ra, **7 chỗ ban đầu không đỏ**

Sáu chỗ xanh và **một chỗ TREO** - ba kết cục chứ không hai, và treo phải được
đếm riêng vì nó nói một chuyện khác hẳn (*công cụ đo đang lừa mình*), đúng luật 03
ở tầng công cụ.

| Chỗ hở | Loại | Đã bịt bằng |
|---|---|---|
| Cha **không đợi** `run_once()` xong | lỗ hổng | `Migration.run_once` nay **chậm có chủ ý** (1 giây) + so mốc `post_construct` của con khác với mốc `run_once` xong |
| ⭐⭐ **HAI PRIMARY** - con dựng lại quay về với vai cũ | lỗ hổng | đếm **số lần adapter đơn nhất khởi động**: đúng thì 2, sai thì 3 |
| Đường dẫn sức khoẻ không còn công khai với JWT | lỗ hổng | test đi qua `_add_jwt_middleware` và soi `public_paths` thật |
| Đường báo tin ném lỗi ra ngoài | lỗ hổng | bus giả luôn ném, và **năm** lời gọi `report_*` phải im |
| Con không báo *"đã sẵn sàng"* | lỗ hổng | đếm dòng `is serving` trong log của **cha** |
| Con không báo adapter bị cô lập | lỗ hổng | thêm `BreakableAdapter` hạng nhân bản: `serve()` ném lỗi theo lệnh |
| Cha lấy ô 0 của bus | **TREO** | xem ngay dưới |

⭐⭐ **Ca hai primary là chỗ đáng nhớ nhất, và nó hỏng hoàn toàn im lặng.** Cấu
hình nói `main: primary: true`. Nếu con đọc vai từ **cấu hình** thì `main` chết,
cha thăng cấp `api-2`, rồi `main` được dựng lại và quay về **vẫn tin mình là
primary** - hai tiến trình cùng chạy job nền, không lỗi nào phát ra.

> Test cũ hỏi *"có ai đó nhận vai không"* - và bản sai **cũng nhận vai**, chỉ là
> nhận thừa một người. Câu hỏi đúng là **"có ĐÚNG một người không"**.

⭐ **Ca cha-lấy-ô-0 dạy một chuyện khác: đo bằng cụm thật thì nó TREO, không ĐỎ.**
Mỗi lần boot cụm với bản vá bị gỡ tốn thêm 60 giây chờ `_await_run_once` hết hạn,
nên cả file test vượt hạn của giàn đối chứng. Bất biến ấy nay được đo **thẳng ở
tầng đơn vị** (`test_shared_allocation.py`), còn cụm thật vẫn giữ vai đo *đoạn
nối*.

📌 Bản thân lỗi đó cũng chỉ lộ khi chạy thật: `ProcessLink.create()` mặc định
`index=0`, nên cha và con thứ nhất dùng chung **một vùng ghi và một cái chuông**.
Cha đọc tin của con, con không bao giờ thấy lệnh của cha, và **cả hai đều im
lặng**.

⚠ Và giàn đối chứng để lại một mutation trong repo khi bị giết giữa chừng - đúng
cái đã cắn ở giai đoạn 5. Phép kiểm `grep "DOI CHUNG"` sau mỗi lần chạy không
phải chuyện thừa.

#### Kiểm thử

**Không mock**, đúng `rules/background-tasks.md` mục 4. Chia hai vai có chủ ý:

| | Đo gì |
|---|---|
| `tests_temp/watchdog/` | **quyết định** - tất định, mili giây |
| `tests_temp/processes/test_cluster_lifecycle.py` | **đoạn nối** - tiến trình thật, chậm |

Hai phép đo không thay nhau được: một cái đúng logic mà dây không nối thì cụm vẫn
hỏng - và ba giai đoạn trước đã dạy đúng bài đó ba lần.

⭐ Test canh đáng nhớ nhất: **chặn event loop thì nhịp vỗ phải ĐỨNG**. Chỗ đặt
lệnh vỗ là một phần của hợp đồng, không phải chi tiết hiện thực - chuyển nó sang
một thread thì watchdog xanh mãi mãi và không gì báo.

---

### Giai đoạn 5 - `RefData` (2026-08-20)

**Dữ liệu tham chiếu dùng chung giữa các tiến trình**: khoá verify JWT, danh bạ
app, cấu hình đã phân giải - thứ **có nguồn bền vững**, đọc rất nhiều, ghi rất
hiếm, và mỗi lần ghi là **thay trọn gói**. Trước đây bốn tiến trình là bốn lần
gọi Trust lúc khởi động, bốn bản trong RAM, và bốn thời điểm xoay khoá khác nhau.

Thiết kế: `.claude/docs/kho-nhom-1-snapshot-2026-08-18.md`.
Tài liệu người dùng: `docs/{vn,en}/refdata.md`.

Test: **2063 passed, 14 skipped** (sau giai đoạn 4: 1985) - **78 test mới**.
**Không phá app nào** - `core/refdata/` là code mới, và phần nối vào bootstrap
chỉ THÊM một bước, không đổi hành vi nào đang có.

#### Added

- **`xime.core.refdata`** - `RefData[T]`, `configure_refdata()`, `RefDataArena`,
  `RefDataStats`, và năm lớp lỗi.
- **Hai bản đổi con trỏ.** Người ghi dựng trọn bản mới vào ô **không ai đang
  đọc**, ghi độ dài và số đoạn, đổi con trỏ (1 byte, nguyên tử), rồi mới tăng
  số đời.
- **Cache L1 khoá bằng SỐ ĐỜI.** Đường thường lệ - chạy 99,99% số lần - là
  **một phép so số nguyên**: không đọc bộ nhớ chung, không decode, không copy.
  `decode()` chạy một lần cho mỗi lần **publish**, không phải mỗi lần **đọc**.
- **`read()` trả `None` = CHƯA SẴN SÀNG**, tách hẳn khỏi *giá trị rỗng*.
  `read_or_fail()` là cặp `find()` / `find_or_fail()` của `CrudRepository`.
- **`wait_ready(timeout)`** - chờ là một lời gọi **riêng**, ở tầng khởi động.
  `timeout` bắt buộc, không có mặc định vô hạn.
- **`publish()` chỉ primary**; tiến trình khác gọi thì **nổ**.
- **Ba lớp chống vượt trần**: cảnh báo ở 80% · `publish()` ném và **giữ nguyên
  bản cũ** · `stats().stale`.
- **`stats().served_generation`** - số đời **tiến trình này** đang phục vụ, tách
  khỏi `generation` (bản mới nhất cả cụm có). Chênh nhau là **tín hiệu duy nhất**
  cho thấy một tiến trình phục vụ bản cũ.
- **Mỗi bảng một vùng nhớ RIÊNG** - *"các bảng nên không liên quan gì đến nhau,
  kể cả bộ nhớ"*. Tổng RAM bằng nhau ở cả hai cách nên không mất gì.
- **Cấu hình bằng THAM SỐ CLASS** (`name`, `max_bytes`), cùng quy ước `Store`.
- **`xime/core/bootstrap/_shared.py`** - cha cấp vùng nhớ **trước khi sinh con**
  và trao `SharedHandle` xuống; con attach. Tiến trình đơn thì tự cấp và tự là
  primary, nên **31 app hiện tại không phải sửa một dòng**.

#### Quyết định đáng nhớ

- ⭐ **Bất biến của `publish` là MỘT CÂU, không phải sáu bước:** *mọi thứ mô tả
  bản mới phải hiện ra TRƯỚC khi số đời tăng*. Thiết kế liệt kê bảy bước nhưng
  không nói `so_doan` đứng ở đâu (trường đó ra đời cùng ngày, sau danh sách
  bước). Phát biểu lại thành một bất biến thì chỗ trống tự đóng.
- ⭐ **Hai ô A/B là tối ưu, `read()` chép ra trước khi decode mới là thứ đóng
  cửa sổ.** Thiết kế mục 4.3 đã nói *"hai bản A/B không tự né được ca này"*; thi
  công xác nhận: gỡ hai ô ra thì mọi test tính đúng đắn vẫn xanh, chỉ test canh
  hình dạng đỏ. Đừng đọc hai ô như lớp bảo vệ chính.
- **Arena vẫn được đăng ký vào DI kể cả khi không khai bảng nào.** Một arena
  **rỗng** không cấp một byte nào, nhưng nó **biết nói**: app `scan` vào package
  chứa bảng mà quên `configure_refdata()` sẽ nổ với câu *"bảng X chưa bao giờ
  được cấp vùng nhớ"* thay vì *"Unregistered Dependency: RefDataArena"*.
- **`wait_ready` hỏi lại theo nhịp**, không chờ một tín hiệu qua bus. Chi tiết và
  lý do ở mục dưới.
- **`SharedHandle` đi bằng ĐỐI SỐ, không bằng biến môi trường.** `XIME_PROCESS_ID`
  cần có mặt trước mọi lệnh import; mã lần chạy thì chỉ cần lúc **attach**. Đối
  số chở được thứ không phải chuỗi (semaphore của bus, giai đoạn 6) và **vắng
  mặt mang đúng một nghĩa**: không có cha.
- **Chỉ số tiến trình lấy theo thứ tự khai trong cấu hình**, không theo thứ tự
  sinh - nên một con được dựng lại **giữ nguyên** chỉ số của nó, và `nguoi_ghi`
  không bao giờ trỏ vào một tiến trình đã chết.

#### ⚠ Một chỗ LỆCH KHỎI THIẾT KẾ, và lý do

Mục 5.4 của thiết kế chốt cơ chế chờ *"nào cái kia ghi xong báo tôi đã xong thì
đọc lại"* - tức một tín hiệu qua `ProcessLink`. Thi công làm `wait_ready()`
**hỏi lại theo nhịp 10 ms** thay vào đó, và đây là lý do:

> **Bus chưa được nối vào vòng đời ứng dụng.** Giai đoạn 2 dựng `ProcessLink`
> chạy được và có 90 test, nhưng nó vẫn là một thư viện đứng riêng: không cha
> nào cấp kênh, không DI nào giữ nó. Việc nối đó thuộc giai đoạn 6 (thăng cấp
> primary, F10 báo trạng thái) và **đáng có đối chứng riêng của nó**.

Cái mất là **độ trễ tối đa một nhịp**, trên một lời gọi chỉ chạy ở tầng khởi
động. Cái được là `wait_ready` **không phụ thuộc thứ tự khởi động của bất cứ
thành phần nào khác** - một chốt chặn không nên dựa vào một thứ có thể chưa kịp
chạy. Thêm đường đánh thức qua bus ở giai đoạn 6 là chuyện thuần cộng thêm,
không đổi API.

📌 Thiết kế cũng đã tự nói *"các lần publish SAU lần đầu thì không cần bus: đọc
`so_doi` là biết"* - phần bus chỉ phục vụ ca chờ lần đầu.

#### ⭐ Đối chứng: 19 bản vá gỡ ra, 7 chỗ ban đầu KHÔNG có test nào đỏ

Ba chỗ là **lỗ hổng thật** trong bộ test, ba chỗ là **phép đo nhắm sai** - và
phân biệt được hai loại đó chỉ có một cách: chạy đối chứng.

| Chỗ hở | Đã bịt bằng |
|---|---|
| Giá trị **falsy** (danh sách rỗng) bị nhầm thành *chưa sẵn sàng* | Test publish `[]` rồi đòi `read() == []`. Bản cũ chỉ đo `KeySet({})`, mà một dataclass thì **truthy**, nên `if not value: return None` đi qua lọt |
| Dùng bảng sau khi arena đã đóng | `RefDataClosedError` + test. ⚠ **Lý do ban đầu ghi trong code là SAI** - xem dưới |
| `configure_refdata()` một mình đưa bảng vào DI | Test dựng `Application` với `BindingConfig()` **rỗng**. Mọi test cũ đều `scan` cả package nên không phân biệt được đường nào đưa bảng vào |
| Hai ô A/B | Đã có test canh (`test_the_two_slots_alternate`), harness chỉ **chạy sai file** - cùng khuôn *"tìm cái đúng thì không đếm được cái sai"* |
| Chép trước khi verify | Test tất định: người ghi đè lên ô đang đọc **ngay trong lòng `decode`** |
| Thứ tự ghi số đời | Test tất định, xem mục ngay dưới |
| **Cả đoạn nối vào supervisor** | Một test **cụm hai tiến trình thật**: primary publish, tiến trình kia đọc được qua vùng nhớ **cha cấp**. Xem mục ngay dưới |

⭐⭐ **Chỗ đáng nhớ nhất: một cửa sổ vài nanosecond KHÔNG đo được bằng cách chạy
đua.** Đảo hai lệnh ghi liền nhau (số đời trước con trỏ) thì test hai tiến trình
chạy **7.674 lượt đọc qua 40 đời** vẫn xanh - cửa sổ quá hẹp để trúng. Phải dựng
lại **đúng thời điểm đó**: do thám `write_generation`, và soi vùng nhớ ngay
trước khi nó chạy. Hai phép đo giữ hai vai khác nhau, không thay nhau được:

| | Đo gì |
|---|---|
| Test đua (`test_multiprocess.py`) | cửa sổ **rộng**, dưới tải thật |
| Do thám tất định (`TestPublishOrder`) | cửa sổ **hẹp nhất**, một lệnh ghi |

⚠ **Một lý do viết trong code hoá ra SAI, và chỉ đối chứng mới lộ ra.** Docstring
của `release()` ghi nó tồn tại để tránh `BufferError` khi `SharedMemory.close()`
gặp view chưa thả. Gỡ nó ra thì **không test nào đỏ** - đo thật thì `close()`
chạy êm, vì `self._view` là **buffer của chính `SharedMemory`** chứ không phải
một **lát cắt**, và chỉ lát cắt mới tính là export. Lý do thật là **thông báo
lỗi**: không buông thì lời gọi sau khi tắt cho một `ValueError: operation
forbidden on released memoryview`. Đã sửa docstring và thêm lớp lỗi riêng.

#### ⚠⚠ Lỗ hổng lớn nhất: cả đoạn nối vào supervisor KHÔNG có test nào

Ba bản vá của phần bootstrap - cha cấp vùng nhớ, `SharedHandle` truyền xuống,
con attach - gỡ ra thì **không test nào đỏ**. Lý do đúng khuôn đã cắn hai lần
trong 0.8, và nó đáng ghi lại vì nó **sẽ lặp**:

> Bộ test của `RefData` hoặc chạy **một tiến trình**, hoặc **tự dựng arena bằng
> tay** rồi `attach` bằng tay. Cả hai đều đi vòng qua chính đoạn nối đang cần
> đo - và cả hai đều trông như đang đo nó.

Đã bịt bằng một test **cụm hai tiến trình thật** (`tests_temp/processes`): app
mẫu khai một bảng, primary publish qua HTTP, rồi cả hai tiến trình phải đọc ra
cùng một bản với cùng số đời. Chạy lại đối chứng thì cả ba đều đỏ, cộng một bản
vá thứ tư (chỉ số tiến trình lấy theo **thứ tự khai trong cấu hình**, không theo
thứ tự sinh).

#### Kiểm thử

**Không mock**, đúng luật `rules/background-tasks.md` mục 4. Bốn ca bắt buộc của
thiết kế chạy bằng **tiến trình thật** (`spawn`), và test đi **thành cặp** ở mọi
chỗ tách một giá trị làm hai (`None` / rỗng · phải nổ / phải chạy · phải cảnh
báo / phải im). Cộng một module đi **đúng con đường tài liệu hướng dẫn**
(`configure_refdata` -> `Application` -> DI), vì bài học 0.7.0 và giai đoạn 1
đều nói cùng một chuyện: lỗi nằm ở **chỗ nối**, và test đi đường tắt không thấy.

---

### Giai đoạn 4 - Đổi API adapter (2026-08-20) - **5/5 phần + 4b**

Mảng này cố ý làm **một lượt**: đổi API rải rác qua nhiều bản là thứ tệ nhất cho
31 app dùng chung một cây mã editable. Thiết kế:
`.claude/docs/doi-api-adapter-2026-08-19.md`.

Test: **1985 passed, 14 skipped** (sau giai đoạn 3: 1928).

⚠⚠ **Đây là thay đổi PHÁ TƯƠNG THÍCH với adapter do người ngoài viết.** Chấp
nhận được vì 0.8 là bản **Alpha cuối** - sau đó 0.9 sang Beta nơi API coi như đã
chốt.

#### Added

- **`Adapter` là Protocol thật, và `use()` kiểm nó.** ⭐ `@runtime_checkable`
  viết từ đầu nhưng **chưa từng có tác dụng**: `Adapter` chỉ được import dưới
  `TYPE_CHECKING`, nên một object rỗng đăng ký được **hai lần** và không ai kêu.
  Công cụ có sẵn, chỉ là không ai gọi. Nhờ vậy tầng lỏng thứ ba đóng miễn phí
  cùng lúc: thiếu `start()` trước đây nổ **sau khi DI đã dựng xong toàn bộ
  singleton**, nay nổ ở đúng dòng `app.use(...)`.
- **`adapter_id`** thay `_server_id` - một tên ở tầng framework, làm ba việc:
  chống trùng · tra khối cấu hình · tầng khoá thứ ba trong `processes:`.
- **`scaling=` bắt buộc, khai bằng tham số class** (PEP 487), cùng khuôn
  `Store(name=..., ttl=...)`. Ba hạng: `replicated` · `sharded` · `singleton`.
  Kèm `unique_per_process=` và `disjoint_per_process=`.
- **`serve()`** trong Protocol - `start()` chiếm tài nguyên rồi **trả về**,
  `serve()` phục vụ và **chặn**.
- **`SchedulerAdapter`** - scheduler thành adapter hạng đơn nhất.
- **`WebServerConfig`** ở `xime.adapters.web` - nhà mới của khối `server:`.

#### Changed

- ⛔ **Ba adapter kết nối RA đổi tên đối số sang `target_id`** (`client_id` ·
  `device` · `server`). ⚠ Cái sai thật **không phải** *"sáu adapter bốn tên"* mà
  là **ba adapter cùng một hạng dùng ba tên khác nhau**. Web/grpc/socket giữ
  `server_id`, **không đổi một chữ** - ép một tên cho cả sáu là dán sai nhãn.
  ⭐ Lý do mạnh nhất để MQTT nhường chữ `client_id`: nó đã mang **hai nghĩa ngược
  nhau** trong cùng framework - ở gRPC client SDK (`grpc.clients.<client_id>`)
  đó là tên **service đích**, ở MQTT là tên **của chính ta**.
- ⛔ **Bỏ `asyncio.TaskGroup` khỏi vòng chạy adapter.** Ngữ nghĩa của nó là *"một
  task ném lỗi thì mọi task anh em bị huỷ"* - đúng cho lỗi lúc khởi động, nhưng
  `serve()` chạy suốt vòng đời nên luật đó áp cả lúc đang chạy: **một lỗi không
  bắt được ở server gRPC kéo web adapter chết theo và tiến trình thoát**, trong
  khi nó đang phục vụ người dùng thật. Nay `serve()` hỏng thì **chỉ adapter đó bị
  cô lập**, log `CRITICAL`, anh em chạy tiếp.
- ✅ **Adapter cuối cùng chết thì tiến trình VẪN SỐNG.** Còn sống thì `/healthz`
  còn trả lời được, log còn đọc được, còn gỡ lỗi được. Thoát là mất hết, kể cả
  khả năng nói cho người khác biết vì sao mình chết.
- ⚠⚠ **`SchedulerRunner` KHÔNG còn chạy ở mọi tiến trình.** Trước 0.8 nó khởi
  động vòng lặp lịch trong `post_construct`, tức job nhắc email gửi **bốn lần**
  trong một cụm bốn tiến trình. Chỗ sai nằm ở **bảng bốn ô**: việc *"chạy mãi,
  một lần cho cả cụm"* đang ở nhà của việc *"chạy một lần, ở mọi tiến trình"*.
  Nay nó là adapter `scaling="singleton"`, và framework chỉ `start()` nó ở
  primary - **không cần cờ nào trong object để mà quên kiểm**.
- ⛔ **`ServerConfig` và `ServerTlsConfig` RỜI core.** `core/config/runtime.py`
  từng có `class ServerConfig` với docstring *"Network binding for the HTTP
  adapter"* - **core biết về một adapter cụ thể**, trong khi năm adapter kia
  không có một dòng nào ở đó. Cùng khuôn `PEER_APP_ID` đã gỡ 2026-08-17. Nhà mới:
  `from xime.adapters.web import ServerTlsConfig`.
  ⚠ **Khoá YAML `server:` giữ nguyên từng chữ** - gỡ ở đây là gỡ **thuộc tính
  Python trên `RuntimeConfig`**, và đo trước khi quyết cho thấy **đúng một file**
  trong cả framework lẫn 27 app đọc `runtime.server`: chính adapter sở hữu nó.
- ⚠ **Một hệ quả đổi hành vi phải đọc:** `runtime.get("server.host")` nay trả
  `None` khi YAML không khai, thay vì `"0.0.0.0"`. Mặc định trước đây lọt vào
  `get()` vì `server:` là một model **có kiểu trên `RuntimeConfig`**; nay nó là
  một khoá thường. Mặc định sống ở `WebServerConfig.from_runtime(runtime)`.
- **Phép kiểm số 4 lúc khởi động đọc DỮ LIỆU, không đọc docstring.** Hai khối
  `sharded` trùng `unique_per_process` -> nổ; giao nhau ở `disjoint_per_process`
  -> nổ. Trước đó lý do chống trùng nằm trong docstring của `MqttAdapter`:
  framework **đọc được nhưng không dùng được**.

#### Quyết định đáng nhớ

- **`scaling` không có mặc định.** Mặc định `replicated` là **nguy** (một adapter
  chưa từng nghĩ tới nhân bản bị nhân bản, hỏng **im lặng**); mặc định
  `singleton` thì app chậm mà không ai biết vì sao. Đúng khuôn `Store` phải khai
  `name`.
- ⭐ **Lớp con của một adapter đã khai thì KẾ THỪA** - `class TestWeb(WebAdapter)`
  không phải nhắc lại `replicated`. Bắt buộc chỉ áp cho adapter **mới**, đúng ca
  luật sinh ra để chặn; ép khai lại chỉ dạy người ta chép một dòng cho qua.
- ⭐ **Ba thư viện bên dưới ĐÃ tách sẵn `start`/`serve`** - gRPC có `start()` +
  `wait_for_termination()`, uvicorn có `startup()` + `main_loop()`, asyncio có
  `start_unix_server()` + `serve_forever()`. gRPC adapter thậm chí **đã gọi đúng
  hai bước đó ở hai dòng liền nhau**. Framework chỉ đang **thôi che giấu** cấu
  trúc vốn có, không ép hình dạng mới.
- ⚠ `scaling`, `unique_per_process`, `disjoint_per_process` **cố ý không khai ở
  thân Protocol**. Khai ở đó là đưa chúng vào `__protocol_attrs__`, tức
  `isinstance` bắt đầu đòi cả ba - và một adapter thiếu `scaling` bị báo là *"sai
  hình dạng"* thay vì *"quên khai hạng"*. Hai bệnh khác nhau thì phải hai phép
  kiểm khác nhau.
- **mqtt / modbus / opcua từ chối `share_load()`** bằng một câu nói rõ lý do -
  chúng thuộc hạng phân mảnh, thi công ở 0.8.1. Nói ra ở **adapter** chứ không ở
  core: core không được biết `mqtt` là gì.
- `ModbusServerAdapter` và `OpcuaServerAdapter` khai **`singleton`** - thiết kế
  không nhắc tới chúng, nhưng chúng giữ **trạng thái thanh ghi trong tiến trình**,
  nên hai bản phục vụ chung một cổng là hai bộ giá trị khác nhau trả lời xen kẽ.

#### Đối chứng: 16 bản vá, 2 chỗ ban đầu không có test nào đỏ

Cả hai là hai phép kiểm phân mảnh mới (`unique_per_process` và
`disjoint_per_process`) - đã bịt bằng bốn test **đi thành cặp** (trùng -> nổ,
khác -> qua; giao nhau -> nổ, rời nhau -> qua).

⚠ Một test cũng tìm ra một lỗi thật: adapter do framework tự đăng ký **bám vào
container vừa bị dọn**, nên `start/stop/start` lần hai nổ *"StartupOrchestrator
has not started"* - và nó nổ ở **lần thứ hai**, đúng khuôn *"test xanh lần đầu,
đỏ lần thứ hai"*.

#### Phần 2 - một hình dạng cấu hình cho cả một lẫn nhiều tiến trình

> **`process:` là một khối. `processes:` là nhiều khối có tên. Bên trong hai cái
> giống hệt nhau.**

Chủ dự án chốt 2026-08-20 sau khi phần 2 lộ ra một chỗ **thiết kế chưa nói tới**:
mục 2.9 bảo bỏ `host`/`port`/`ssl`/`path` khỏi constructor, và mục 2.5 biện minh
bằng câu *"server phụ nay có ô cấu hình riêng `processes.<p>.web.<id>`"* - câu đó
**chỉ đúng dưới `share_load()`**. Ngoài nhánh đó thì một app một tiến trình có
server phụ **không còn chỗ nào khai địa chỉ**.

⭐ Chỗ dễ lẫn đã làm rõ trong lúc bàn: **"server phụ" KHÔNG phải "tiến trình
phụ"**. `server_id` là điểm phục vụ **bên trong** một tiến trình, nên một tiến
trình duy nhất vẫn mở được hai cổng HTTP - chuyện đó độc lập hoàn toàn với
`share_load()`.

```yaml
# một tiến trình, hai cổng
process:
  web:
    public: { host: 0.0.0.0,   port: 8086 }
    admin:  { host: 127.0.0.1, port: 8081 }

# nhiều tiến trình - BÊN TRONG y hệt, chỉ thêm một cấp và một cái tên
processes:
  main:
    primary: true
    web:
      public: { host: 0.0.0.0,   port: 8086, shared: true }
      admin:  { host: 127.0.0.1, port: 8081 }
  api-2:
    web:
      public: { host: 0.0.0.0,   port: 8086, shared: true }
      admin:  { host: 127.0.0.1, port: 8082 }
```

##### Added

- **Khoá `process:`** - một khối, cho app một tiến trình. Nội dung **byte-identical**
  với một khối của `processes:`, nên đi từ một sang nhiều là *thêm một cấp và một
  cái tên*, không phải học hình dạng thứ hai.
- **Ba khoá vô nghĩa với một tiến trình là LỖI**, không phải bỏ qua: `primary`
  (tiến trình duy nhất luôn là primary), `count` (không gì sinh con), `shared`
  (dùng chung một địa chỉ đòi **ít nhất hai** tiến trình). ⚠ Kiểm **sự có mặt
  của khoá**, không kiểm giá trị - `shared: false` cũng bị từ chối, vì cho nó
  qua là dạy người đọc rằng khoá đó có ý nghĩa ở đây.
- **Phép dịch khoá phẳng** `server:` / `grpc.port` -> `process.web.default` /
  `process.grpc.default`. ⭐ Đo được **58/69** file cấu hình trong workspace dùng
  `server:`, nên đây là hiện thực đông nhất - và nó là **một phép dịch**, không
  phải một nhánh xử lý thứ hai: dịch xong thì từ đó trở đi chỉ còn một đường
  code, và khoá phẳng **không thể trôi lệch** vì nó chỉ diễn tả nổi một điểm
  phục vụ mỗi loại.
- **`AdapterSlot.where`** - một chỗ duy nhất sinh chuỗi vị trí cho thông báo lỗi,
  vì hai nhánh có hai tiền tố khác nhau và một thông báo sai tiền tố dẫn người
  đọc tới nhầm khoá.

##### Changed

- ⛔ **`host` / `port` / `ssl` / `path` BỎ HẲN khỏi constructor** của web, gRPC và
  socket. Không cần phép kiểm nào nữa - Python từ chối ở tầng chữ ký, và chốt
  chặn *"cấm đối số cổng"* dựng ở giai đoạn 3 nay là **mã chết**.
  ⭐ Đo trước khi làm: **0/27 app** trong workspace dùng server phụ, nên không app
  nào phải sửa. 74 chỗ nhắc tới nằm gọn trong repo này (28 test, 36 tài liệu, 10
  code framework).
- **Mọi adapter LUÔN nhận một ô**, ở cả ba nhánh của `run()`. Nhờ vậy trong
  adapter không còn nhánh *"có ô thì đọc ô, không thì tự đi tìm khoá"*.
- **`grpc.servers.<id>` biến mất.** Nó là cái tên thứ ba cho cùng một khái niệm,
  và nó giữ một khoá `port` **chết**: adapter đọc khối đó xong **ghi đè vô điều
  kiện** bằng đối số constructor, nên người vận hành sửa `grpc.servers.<id>.port`
  thì cổng **không đổi**, không một dòng cảnh báo. `tls` của nó về ô.
- **TLS kế thừa `server.ssl` khi ô không khai** - giữ nguyên tính chất bảo mật
  cũ. Muốn một điểm phục vụ cố ý chạy HTTP thuần thì khai `ssl: {}`, đúng chỗ
  `ssl=ServerTlsConfig()` cũ chuyển tới.
- **Chốt 0.8.1 cho hạng phân mảnh chuyển từ ADAPTER sang FRAMEWORK.** Trước đó
  mqtt/modbus/opcua tự ném trong `assign_slot()`; từ khi mọi adapter luôn nhận
  một ô thì cách đó **chặn luôn nhánh một tiến trình**, nơi chúng chạy hoàn toàn
  bình thường. Thứ phải chặn là *chia tải*, không phải *nhận cấu hình*.
- **Thứ tự import trong khuôn `main.py`**: `from xime...` trước, `import config`
  sau. ⭐ Không chỉ là thẩm mỹ - `xime` là thư viện bên thứ ba, `config` là code
  của app, nên đó đúng là thứ tự isort/ruff chuẩn; khuôn cũ đang ngược quy ước.

##### Ba phép kiểm mới quanh cái bẫy một chữ

`process` và `processes` khác nhau **đúng một ký tự**, nên framework bắt cả hai
chiều: `processes:` mà không `share_load()` -> lỗi · `process:` mà có
`share_load()` -> lỗi · khai cả hai -> lỗi. **Không tổ hợp nào chạy êm mà sai.**

##### ⚠ Một lỗi thật, và nó chỉ lộ ra ở tiến trình con

`share_load()` **không chạy ở tiến trình con** (khối `if __name__` không kích
hoạt ở đó), nên cờ phải đặt lại trong `run_as_worker()`. Thiếu dòng đó thì con
đọc cấu hình bằng nhánh một-tiến-trình và **từ chối chính khối `processes:` mà
cha vừa dùng để sinh ra nó** - một tiến trình con nổ vì cấu hình đúng.

##### Đổi hành vi phải đọc

`runtime.get("server.host")` nay trả `None` khi YAML không khai, thay vì
`"0.0.0.0"`. Mặc định trước đây lọt vào `get()` vì `server:` là một model **có
kiểu trên `RuntimeConfig`**; nay nó là một khoá thường. Mặc định sống ở
`WebServerConfig.from_runtime(runtime)`.

#### Phần 4b - fieldbus: một adapter = một LOẠI, N thực thể (khai chữ ký)

Thiết kế 5.7.3 tách **loại** khỏi **thực thể**, và chỗ tách đó đụng thẳng vào API
công khai:

| | Ai biết | Ở đâu |
|---|---|---|
| **Loại** (`bang-tai`) | **Code** - controller viết cho một loại máy | `main.py` |
| **Thực thể** (`BT-01`) | **Cấu hình** - nhà máy có bao nhiêu máy | `application.yml` |

⏭ **Chủ dự án đã lùi THI CÔNG fieldbus sang 0.8.1**, nên ở đây chỉ khai **chữ ký**.
Nhưng khai là bắt buộc: 0.8 là bản **Alpha cuối**, và 0.8.x không được đổi một dòng
API công khai nào.

##### Removed

- ⛔ **`@poll(..., device=...)` và `@on_change(..., device=...)`** - việc chọn máy nào
  không còn nằm ở decorator. Handler chạy một lần cho **mỗi thực thể** của loại nó.
- ⛔ **`@on_node_change(..., server=...)`** của OPC UA - cùng lý do.
- **Trục `device` biến khỏi `PollGroup`.** Trước đây hai handler cùng model, cùng nhịp
  nhưng khác `device` tách thành hai vòng đọc; nay chúng dùng một vòng.

##### Added

- **Tham số handler `device` (Modbus) / `server` (OPC UA)**, khớp theo **TÊN** đúng
  quy ước `topic` của `@subscribe`:

  ```python
  @poll(Conveyor, interval=1.0)
  async def on_sample(self, conveyor: Conveyor, device: str) -> None: ...
  ```

  Không khai thì handler giữ nguyên một tham số như cũ. ⚠ Một tham số thứ hai mang
  **tên khác** là **lỗi khởi động**, không phải một tham số bị bỏ qua im lặng - bỏ qua
  im lặng thì người viết chờ framework truyền một thứ nó không biết là gì, và handler
  nổ `TypeError` giữa một chu kỳ đọc, xa chỗ sai thật.
- **`ModbusClient.devices_of(kind)` / `OpcuaClient.servers_of(kind)`** - danh sách thực
  thể của một loại mà **tiến trình này** giữ:

  ```python
  for dev in modbus.devices_of("bang-tai"):
      trang_thai = await modbus.read(Conveyor, device=dev)
  ```

  ⭐ Đây là đường **duy nhất** đúng để lấy tên thực thể trong code nghiệp vụ (đường kia
  là dữ liệu người dùng chọn). Viết cứng `device="BT-01"` là buộc code vào một nhà máy.
- **Hằng `DEVICE_PARAM` / `SERVER_PARAM`** thay vì chuỗi rải rác - tên tham số là một
  phần hợp đồng công khai, nên nó phải có đúng một chỗ định nghĩa.

##### ⭐ Vì sao HAI tên chứ không phải một

Phần 1 chốt `adapter_id` là **một tên chung cho mọi adapter**, nên phản xạ tự nhiên là
ép `devices_of`/`servers_of` về một chữ. **Ngược lại mới đúng**, và ranh giới là:

> `adapter_id` nói về **framework** - một tên chung là đúng.
> `device`/`server` nói về **thứ thật ngoài kia** - Modbus có thiết bị, OPC UA có
> server. Ép chung một chữ là dán sai nhãn, đúng thứ phần 1 đã bác khi từ chối gộp
> `server_id` với `target_id`.

##### Tương thích

- **Rỗng mang đúng một nghĩa.** `devices_of` trả `[]` nghĩa là *tiến trình này không
  giữ loại đó* - ca thường lệ của mô hình phân mảnh, không phải lỗi. Nó **không** mang
  nghĩa *"chưa biết"*: câu trả lời có từ lúc `app.use()`, trước cả khi kết nối lên, vì
  adapter nhận tên ngay trong `__init__`.
- **Code viết theo vòng lặp `devices_of` chạy đúng ở cả 0.8 và 0.8.1.** Hôm nay một
  adapter giữ đúng một thực thể trùng tên loại - đúng dạng viết tắt thiết kế đã chốt
  (*"giá trị dưới tên loại là dict phẳng có `host` thì coi như một thực thể trùng tên
  loại"*), nên không phải sửa gì khi 0.8.1 tới.
- **Không app nào phải sửa**: chưa app nào trong workspace dùng Modbus/OPC UA thật.

Đối chứng 6 bản vá của 4b: **6/6 đỏ**.

#### Còn lại - đã lùi sang 0.8.1

| | |
|---|---|
| Dựng **N kết nối** cho một loại | Cấu hình bốn tầng `process → modbus → loại → thực thể`; hôm nay một adapter một thực thể |
| `mqtt.clients.<id>` | `client_id` và `topics` vào `processes.<p>.mqtt.<id>`. ⭐ Không có API nào phải khai ở 0.8: `@subscribe` **mất một vai, giữ nguyên chữ ký** |

### Giai đoạn 3 - Cấu hình, `share_load()`, supervisor (2026-08-20)

**Xương sống của 0.8.** Từ đây một ứng dụng chạy được trên nhiều tiến trình mà
**không đổi một dòng code nghiệp vụ**: `main.py` khai *ứng dụng này CÓ những cửa
nào*, khối `processes:` khai *tiến trình nào ĐANG mở cửa nào ở cổng nào*.

Thiết kế: `.claude/docs/da-tien-trinh-main-va-cau-hinh-2026-08-16.md`.
Tài liệu người dùng: `docs/{vn,en}/multi-process.md`.

Tiêu chí nghiệm thu **đã đạt**: một app thật chạy **hai tiến trình phục vụ HTTP
trên cùng một cổng**, đo bằng hai pid khác nhau trả lời trên một cổng, và cha
không nằm trong số đó.

Test: **1928 passed, 14 skipped** (sau giai đoạn 2: 1842) - **86 test mới**, trong
đó **7 ca chạy tiến trình thật** bằng `subprocess` (cha là `__main__` của chính
nó nên không mô phỏng được trong pytest).

**Ứng dụng không gọi `share_load()` chạy y hệt hôm nay** - cả giai đoạn này là
**thêm**, không phải **thay**.

#### Added

- **`Application.add_config(module)`** - chỉ thẳng vào package `config/`. ⭐ Đây
  là **điều kiện cần**, không phải cải tiến: cơ chế dò cũ tìm package qua
  `__main__.__spec__.parent`, mà giá trị đó **khác ở tiến trình con** - framework
  tìm sai chỗ rồi **im lặng** rơi xuống một `BindingConfig()` rỗng. Con khởi động
  được, DI rỗng, không route nào, và không gì báo.
- **`Application.share_load()`** - ba nhánh của `run()`, mỗi nhánh do một điều
  kiện **quan sát được** quyết định: không gọi -> đơn tiến trình · gọi + không có
  `XIME_PROCESS_ID` -> supervisor · gọi + có -> worker. Nhánh ba cũng là đường
  gỡ lỗi tay: `XIME_PROCESS_ID=api-2 python -m app.main`.
- **Khối `processes:`** - ba tầng khoá `tiến trình -> loại adapter -> id`, với
  `host` / `port` / `path` / `shared` / `primary`, và `count: N` sinh
  `<tên>-1..N` theo id **xác định**.
- **Supervisor** - cha bind những địa chỉ dùng chung (nếu có), sinh con bằng
  `multiprocessing` với `spawn`, trông con, dựng lại con chết, và tắt cả đàn
  theo `SIGINT` / `SIGTERM` / `SIGBREAK`. **Không bao giờ `accept()`, không dựng
  DI, không chạy code nghiệp vụ.**
- **`AdapterSlot`** - framework **đẩy** ô cấu hình đã lọc vào adapter, thay vì
  adapter tự đi kéo ra. Kèm `adapter_kind` và `share_port_by` khai trên class.
- **Bốn phép kiểm lúc khởi động** (mục 6 của thiết kế) cộng ba phép kiểm quanh
  chuyện *bật nhầm nhánh*: `processes:` mà không `share_load()`, `share_load()`
  mà không `processes:`, và `share_load()` mà không adapter nào.

#### Changed

- ⛔ **Cấm đối số cổng dưới `share_load()`.** `WebAdapter("admin", host, port)`
  thành lỗi khởi động. Không phải chuyện gọn gàng: cha `bind()` rồi truyền socket
  xuống, nên **con không có cách nào tự chọn cổng** - đối số ở đó là lời hứa
  framework không giữ được.
- ⚠ **Phép kiểm *"server phụ bắt buộc có cổng"* chuyển từ `__init__` xuống
  `start()`** (web và grpc). Bắt buộc, vì khuôn `main.py` chốt của 0.8 là
  `app.use(GrpcAdapter("internal"))` **không đối số** - và `share_load()` được
  gọi SAU `use()`, nên lúc dựng object framework chưa biết cổng sẽ đến từ đâu.
  App đơn tiến trình không mất gì: thiếu cổng vẫn nổ lúc khởi động, cùng câu
  chữ, chỉ muộn hơn vài dòng. Ba test trong `test_multi_server.py` đã sửa theo.
- **`SocketAdapter` không xoá file socket khi nó chỉ mượn socket của cha.** Xoá
  là cướp chỗ của anh em còn sống, **im lặng**: tiến trình kia vẫn `accept()`
  trên một inode không còn tên, không ai gọi tới được, không lỗi nào phát ra.
- **`GrpcAdapter` khai `SO_REUSEPORT` tường minh** ở nhánh `share_load()` (bật
  khi `shared: true`, **tắt** khi không). Bản vá cho chỗ *"bind thành công"* mang
  hai nghĩa: gRPC C-core bật cờ này mặc định trên Linux, nên khai nhầm trùng cổng
  thì Windows báo lỗi ngay còn Linux chạy êm với một nửa request đi nhầm chỗ.
- `Application` **nhớ lại** `application.yml` cho tới `stop()`, vì `run()` cần
  cấu hình trước `start()`. Đọc hai lần vô hại về hiệu năng nhưng mở một khe:
  file đổi giữa hai lần đọc là cha và con nhìn thấy hai cấu hình khác nhau.

#### ⚠⚠ Một dòng THIẾT KẾ SAI, phát hiện bằng phép đo

Bảng ở mục 5.7.1 của thiết kế ghi **Windows ✅** cho web nhờ `WSADuplicateSocket`.
Handle thì chuyển qua được thật, nhưng `asyncio` mặc định trên Windows là
**proactor**, và ở đó lần `accept()` đầu tiên gọi `CreateIoCompletionPort`:

```text
OSError: [WinError 87] The parameter is incorrect
```

> **Liên kết IOCP thuộc về SOCKET của kernel, không thuộc về HANDLE.** Tiến trình
> thứ nhất gắn socket vào IOCP của nó xong thì tiến trình thứ hai không gắn được
> vào IOCP của mình nữa, dù nó cầm một handle hợp lệ.

⭐ Cách hỏng của nó là kiểu tệ nhất: con thứ hai khởi động **thành công**, log
*"serving"*, rồi **không nhận nổi một kết nối nào**. Cụm mất một nửa năng lực
trong khi mọi request đều 200 và không có gì đỏ.

⛔ `sock.share(os.getpid())` + `fromshare()` - **đúng cách uvicorn làm** ở chế độ
nhiều worker - **không cứu được**; đã đo cả hai đường, cùng một lỗi. Thứ cứu được
là **selector event loop**: nó `accept()` thẳng, không đụng IOCP.

**Bản vá:** tiến trình con nào kế thừa socket dùng chung trên Windows thì chạy
trên selector loop, kèm một dòng `WARNING`. Cái giá là `select()` giới hạn 512
socket và loop đó không chạy được subprocess - chấp nhận được vì Windows là máy
dev, còn prod là Linux. Đổi lại giữ được thứ đắt hơn: **dev chạy giống prod**.

#### Quyết định đáng nhớ

- **Cha không được chết.** Con chết thì không ai dựng lại, `Ctrl+C` không có chỗ
  điều phối thứ tự tắt. Kèm một lợi ích phụ đáng kể: **cổng bị chiếm thì cha nổ
  ngay lúc khởi động**, thay vì bốn con lần lượt nổ với bốn stack trace giống hệt.
- **Con chạy lại chính `main.py`** thay vì một entry point riêng của framework.
  Hai đường khởi động là hai chỗ để trôi lệch, và loại lệch đó **không có triệu
  chứng**: ai đó thêm một `configure_middleware()` vào `main.py`, cha có, con
  không, và ba tiến trình phục vụ thiếu một middleware xác thực mà không gì báo.
- **`app` phải là biến ở mức module của `__main__`**, và framework **cưỡng chế**
  điều đó bằng một thông báo kèm khuôn đúng. Đặt `use()` trong `if __name__` thì
  con có một ứng dụng không adapter nào - cách hỏng đó không có triệu chứng, ở
  đây nó thành một dòng chữ.
- **Adapter khai trong `main.py` mà KHÔNG khối nào nhắc tới -> lỗi**, khác hẳn
  *khối này không có* (đó là cách lọc hợp lệ, và là ma trận thưa mà fieldbus
  cần). Không ai cố ý khai một cửa rồi không mở nó ở đâu cả.
- **mqtt / modbus / opcua từ chối `share_load()` bằng một câu nói rõ lý do.**
  Chúng thuộc hạng **phân mảnh**, thi công ở 0.8.1. Nói ra ở adapter chứ không ở
  core - core không được biết `mqtt` là gì.
- **`shared` khai tường minh**, vì *"bind thành công"* mang hai nghĩa.
- **Ca 5 (một khối) vẫn dựng supervisor đầy đủ.** Tự bỏ supervisor ở con số 1 thì
  hạ `count` từ 4 xuống 1 lúc gỡ lỗi là app **mất khả năng tự dựng lại khi chết**
  mà không gì báo. Muốn một tiến trình không có cha thì đã có đường rẻ hơn: đừng
  gọi `share_load()`.

#### Đối chứng: 24 bản vá, 3 chỗ ban đầu không có test nào đỏ

Đã bịt cả ba. ⭐⭐ Test bịt chỗ hở thứ nhất **tìm ra hai lỗi thật ngay lần chạy
đầu**, và cả hai thuộc loại *không có triệu chứng*:

1. `_respawn` log **`"- restarting"` rồi không restart** khi đang tắt máy. Một
   dòng log mang hai nghĩa, nói dối **đúng lúc** người ta đọc log để hiểu vì sao
   cụm tắt. Ca thật: tín hiệu dừng tới cả nhóm tiến trình nên con chết **trước**
   khi cha kịp vào bước tắt.
2. `_shutdown` **không log gì** khi không còn con nào - nên một lần tắt tử tế và
   một cái chết đột ngột để lại **cùng một** dấu vết.

⚠ Hai chỗ hở kia đáng nhớ vì cách bịt chúng: *"cổng được trả lại"* **không** chứng
minh cha tắt tử tế (tín hiệu tới thẳng cả nhóm nên con chết kiểu gì cũng chết) -
phải đo **mã thoát 0** và **dòng log**; và *"dict kết quả có một mục"* **không**
chứng minh cha bind một lần - dict dùng địa chỉ làm khoá nên nó luôn ra một mục dù
bind ba lần, phải **đếm số lần `bind`**.

#### Chưa có ở giai đoạn này

Thăng cấp primary · watchdog cho con treo · `RunOnce` · scheduler thành adapter
đơn nhất · chống domino `N`/`T` · nâng cấp code không downtime. Tất cả thuộc
giai đoạn 6.

⚠ **Đáng đọc trước khi bật tiến trình thứ hai:** cho tới khi scheduler thành
adapter đơn nhất, **mọi job nền chạy ở mọi tiến trình**. Job dọn dẹp thì chỉ
thừa; job gửi email nhắc hoặc tiến con trỏ đồng bộ thì **sai**.

### Giai đoạn 2 - `ProcessLink` (2026-08-20)

**Bus liên tiến trình trên bộ nhớ chung**: chở **tín hiệu, lệnh và câu hỏi** giữa
các tiến trình của cùng một ứng dụng. Ca dùng gốc: người dùng bấm *"dừng băng tải
BT-02"* trên web, request rơi vào tiến trình `main`, mà dây Modbus tới BT-02 nằm
ở tiến trình `line-2` - đó là một **lệnh**, ghi vào database không làm nó dừng.

Thiết kế: `.claude/docs/bus-lien-tien-trinh-2026-08-18.md`.
Tài liệu người dùng: `docs/{vn,en}/process-link.md`.

Test: **1842 passed, 14 skipped** (sau giai đoạn 1: 1752) - **90 test mới**.
**Không phá app nào** - `core/link/` là code mới, không sửa một dòng nào của
phần đã có.

⚠⚠ **KHÔNG phải `EventBus`.** Hai thứ không dùng chung một dòng code nào, và gọi
nhầm thì **không có triệu chứng**: tin không bao giờ ra khỏi tiến trình, không
lỗi, không log. Tên cố ý không chung gốc từ - `link.ask()` và
`event_bus.publish()` không thể gõ nhầm thành nhau.

#### Added

- **`xime.core.link`** - `ProcessLink`, `ChannelSpec`, `configure_link()`,
  `@on_request` / `@on_announce`, và bốn kết cục `Done` / `NoOwner` / `NoAnswer`
  / `Failed`.
- **Mỗi kênh một vùng nhớ chung, chia N VÙNG GHI RIÊNG** - không có tranh chấp
  ghi, và thứ tự trong một người gửi được giữ nguyên.
- **Semaphore là CHUÔNG, bitmap "ai chưa đọc" là SỰ THẬT.** Bitmap xếp thành dãy
  liền nhau nên một tiến trình thức dậy chỉ đọc dãy của riêng nó rồi so với 0 -
  một phép so, không phải quét cả bảng.
- **Định tuyến bằng kênh + khoá, lọc ở bên nhận**, và `key` nằm ở header nên bên
  nhận lọc mà **chưa chạm payload**. Không có tên tiến trình ở bất cứ đâu.
- **Kênh nội bộ `__xime__`** framework **luôn** tạo, không phụ thuộc ứng dụng
  khai gì - cha sẽ dùng nó làm kênh điều khiển ở giai đoạn 3.
- **`stats()` trả về số liệu CỦA CẢ CỤM**, `dump()` tách riêng cho gỡ lỗi.
- **`sweep_orphans()`** dọn vùng nhớ của những lần chạy trước (Linux).

#### Quyết định đáng nhớ

- **at-most-once: hạ bit TRƯỚC khi làm.** Chết giữa chừng thì tin mất, thay vì
  được làm lại. Ứng dụng cần chắc thì tự thêm hàng đợi bền vững.
- **Đầy thì vòng lại và ĐÈ**, kèm **đếm `missed`** cho người chưa đọc. Nhờ vậy
  một tiến trình treo **tự chịu hậu quả**, không nghẽn ai.
- **Handler chạy TUẦN TỰ theo kênh.** `create_task` cho từng tin là vứt bỏ thứ
  tự vừa xây: `bật`/`tắt`/`bật` chạy song song thì trạng thái cuối là *cái nào
  thắng cuộc đua*. Muốn song song thì **tách kênh**, không tách task.
- **Một kênh một handler.** Nhiều handler thì phải trả lời *"ai được nhận"*, mà
  câu đó phụ thuộc thứ chỉ biết lúc chạy.
- **`Failed` mang tên lỗi, KHÔNG mang traceback** - người hỏi ở tiến trình khác
  không debug được bằng traceback của tiến trình kia. Traceback đầy đủ log tại
  nơi lỗi xảy ra.
- **Payload vượt trần nổ ngay lúc gửi**, không trả về một kết cục: đó là bug của
  người viết app, và trả về một kết cục là mời người ta `except` rồi bỏ qua.

#### ⚠⚠ Một chỗ THIẾT KẾ ĐÃ ĐỔI lúc thi công (chủ dự án chốt 2026-08-20)

Bản thiết kế 08-18 (mục 4.1) ghi thứ tự ghi là *"bật bit chưa-đọc, rồi đặt
`da_ghi_xong` **sau cùng**"*, và gọi thứ tự đó là **bắt buộc**. Sau khi đo, chủ
dự án chốt **đảo lại**: hoàn tất trước, bật bit sau. Tài liệu thiết kế đã sửa,
bản cũ giữ ở mục 4.1b.

**Bất biến mới, và là thứ đáng nhớ hơn cả thứ tự sáu bước:**

> **Một bit chưa-đọc chỉ được bật khi dòng nó trỏ tới ĐÃ HOÀN TẤT.**

Lý do nằm ở chỗ **người đọc chỉ tìm thấy một dòng qua BIT của nó** - bitmap là
danh sách việc phải làm, `da_ghi_xong` chỉ là phép kiểm sau đó. Cả hai thứ tự
đều chặn được *"đọc dòng nửa vời"* (lý do duy nhất bản cũ đưa ra), và ở ca
thường lệ chúng cho kết quả **giống hệt nhau**. Chỗ khác nhau là thứ để lại khi
người ghi **chết đúng khoảng giữa**:

```text
BẢN CŨ  - chết giữa bật-bit và hoàn-tất
  B quét 5 vòng, bit còn lại: [0]        -> CÒN TREO
  A vòng lại đè lên dòng đó -> missed của B = 1
  ⚠ B bị tính là LỠ MỘT TIN, mà tin đó chưa bao giờ hoàn tất

BẢN MỚI - chết giữa hoàn-tất và bật-bit
  B quét 5 vòng, bit còn lại: []          -> đã sạch
  A vòng lại đè lên dòng đó -> missed của B = 0
  -> tin mất (at-most-once, ĐÃ được thiết kế khai nhận)
```

Bit treo vì vòng đọc làm đúng như mục 4.2 bảo - thấy cờ 0 thì *"bỏ qua vòng này,
xem lại sau"* - mà bước hạ bit nằm **sau** bước kiểm cờ. Hậu quả nặng nhất không
phải một bit thừa mà là **`missed` đếm sai vĩnh viễn**: đó là chỉ số chẩn đoán
chính của bus, thứ trả lời *"có tiến trình nào đang treo không"*.

> Nói gọn: cả hai thứ tự đều có một cửa sổ chết cỡ vài chục nanosecond. Chọn cửa
> sổ mà hậu quả **đã được thiết kế chấp nhận** (mất tin), thay vì cửa sổ tạo ra
> một trạng thái **vĩnh viễn và im lặng** mà không ai dọn.

Cùng bản vá đó ở đầu kia vòng đời một dòng: `_claim_row` **hạ bit của người chưa
đọc trước khi mở dòng ra ghi đè**. Ở ca thường lệ nó thừa (bước sau bật lại
ngay); nó chỉ có giá trị khi người ghi chết sau khi đã mở dòng.

⛔ **Một đường thứ ba đã cân và loại**: giữ thứ tự cũ nhưng cho vòng đọc hạ bit
ngay cả khi cờ chưa hoàn tất. Bit hết treo, nhưng nó hạ nhầm bit của một dòng
**đang được ghi hợp lệ** - biến một ca hiếm thành **mất tin ở ca thường lệ**.

⚠ Cả hai đều có test canh trong `test_write_protocol.py`, soi trạng thái **ngay
tại thời điểm** `set_bit` và `write_payload` được gọi. Không có chúng thì ai đó
"dọn cho gọn" sẽ đảo lại và **mọi test chức năng vẫn xanh**.

#### ⭐ Đối chứng: 12 bản vá gỡ ra, 3 chỗ ban đầu KHÔNG có test nào đỏ

Ba chỗ đó đều là bản vá bảo vệ ca *"người ghi chết đúng khoảng giữa"* - thứ
không mô phỏng được bằng cách giết tiến trình thật, nhưng **đo được bằng cách
quan sát trạng thái ngay tại thời điểm đó**. Đã thêm `test_write_protocol.py`;
chạy lại đối chứng thì cả ba đều đỏ.

> Không có chúng thì ai đó "dọn cho gọn" sẽ đảo thứ tự, mọi test vẫn xanh, và
> một tiến trình chết giữa chừng để lại một bit không bao giờ hạ được.

#### Kiểm thử

**Không mock**, đúng luật `rules/background-tasks.md` mục 4: bus toàn bộ là
chuyện đua, mock đi thì test xanh mà không chứng minh được gì. Năm ca bắt buộc
của thiết kế đều chạy bằng **tiến trình thật** (`spawn`), cộng chiều ngược -
**con hỏi cha** - để chốt rằng cha **không** nằm trên đường đi.

---

### Giai đoạn 1 - `Store` trên LMDB (2026-08-20)

**Kho liên tiến trình cho trạng thái KHÔNG có nguồn bền vững**: hãm nhịp, thử
thách passkey, chống lặp webhook. Thứ mà nhiều tiến trình của **một máy** phải
thống nhất, sai nếu giữ trong bộ nhớ một tiến trình, và ứng dụng vẫn chạy đúng
khi nó rỗng sau lúc máy khởi động lại.

Thiết kế: `.claude/docs/kho-nhom-2-store-2026-08-19.md`.
Tài liệu người dùng: `docs/{vn,en}/store.md`.

Test: **1752 passed, 11 skipped** (0.7.2: 1624) - **128 test mới**. Kèm bốn app
thật vẫn xanh: `data-service` **388**, `linh-kien-dien-tu` **295**. **Không phá
app nào** - toàn bộ là code mới, không sửa một dòng nào của phần đã có.

#### Added

- **Starter `xime.starters.lmdb`**, extra **`xime[lmdb]`**, import lười đúng
  khuôn `redis`/`s3`/`mail`/`mqtt`.
- **Ba lớp nền**: `Store` (bytes) · `CounterStore` (int, có `incr` nguyên tử) ·
  `Store[T]` (kiểu của app, tự viết `encode`/`decode`). Tách theo kiểu chứ không
  bắt mọi bảng viết `Store[int]` vì **`incr` chỉ có nghĩa với số** - đặt nó lên
  một `Store` chung là hợp đồng hứa thứ nó không giữ được cho mọi kiểu khác.
- **Cấu hình đi bằng THAM SỐ CLASS (PEP 487)**:
  `class HamNhip(CounterStore, name="...", ttl=900, parts=4)`. Cấu hình không
  bao giờ thành thuộc tính trong thân class nên **không thể va tên** với thứ app
  viết thêm, và `mypy` kiểm được kwargs.
- **Vào DI bằng `dependency.scan("xime.starters.lmdb")` + `scan` package của
  app**, không có `configure_lmdb`. ⚠ Đây là chỗ **không nhất quán có lý do**:
  `RefData` và `ProcessLink` (giai đoạn 2, 5) **phải** có `configure_*` vì cha
  cần biết danh sách trước khi con dựng DI để cấp vùng nhớ chung; mở một file
  LMDB thì không cần cấp phát gì.
- **Năm phép**: `get` · `set` · `delete` · `set_if_absent` (nguyên tử) ·
  `incr` (nguyên tử, chỉ `CounterStore`).
- **`StoreCleanupJob`** - job dọn bản ghi hết hạn, xếp lịch bằng
  `configure_scheduler` như mọi job khác.
- **Ba ngoại lệ**: `StoreError` · `StoreUnavailableError` · `StoreFullError`.
- **Ba khoá cấu hình vận hành**: `lmdb.path` · `lmdb.map_size` · `lmdb.total_max`.

#### Quyết định đáng nhớ

- ⛔ **Phạm vi là MỘT máy, luôn luôn.** Nhiều máy đã giải bằng chia shard.
- **TTL lưu MỐC TUYỆT ĐỐI**: mọi lần **ghi** đặt lại hạn, **đọc** không đụng tới.
  Nếu đọc mà gia hạn thì **mọi lần đọc thành một lần GHI** - phá đúng ưu thế đã
  chọn LMDB vì nó. Cùng lý do đó, kho **không đuổi theo LRU**.
- **Mặc định 1 giờ, vô hạn phải khai `ttl=NEVER`.** An toàn theo mặc định, thoát
  ra phải viết rõ. ⚠ `ttl=NEVER` (không hết hạn) **khác** `ttl=None` ở lời gọi
  (dùng mặc định của bảng) - hai tình huống, hai giá trị.
- **Chia file theo `crc32(key) % parts`**, KHÔNG BAO GIỜ `hash()`: Python ngẫu
  nhiên hoá `hash()` theo từng tiến trình (đo được: 4 tiến trình, 4 giá trị khác
  nhau cho cùng một chuỗi), nên bốn tiến trình sẽ tính ra bốn file khác nhau cho
  cùng một khoá và **không gì báo**.
- ⛔ **`parts` cố định suốt đời kho**, không suy từ số tiến trình. Đổi nó thì mọi
  khoá nằm sai file - framework phát hiện qua file `.parts` rồi **xoá bảng và tạo
  lại**, kèm log. Mất cache một lần, đổi lấy việc không bao giờ chạy trên một kho
  lạc chỗ.
- **Lỗi kho báo bằng NGOẠI LỆ**, không phải kết cục thứ ba trong kiểu trả về: với
  `incr`/`set_if_absent` thì ngoại lệ là **fail-closed tự nhiên**, còn quên một
  nhánh của kiểu trả về là **fail-open im lặng** - hãm nhịp hoá ra cho qua tất.
- **`lmdb.path` KHÔNG có mặc định.** Máy này chạy 31 codebase Xime cạnh nhau, và
  khác bus (tên vùng nhớ mang mã ngẫu nhiên mỗi lần chạy), kho **cố ý sống qua
  lần restart** nên tên phải ổn định - một mặc định ổn định vì vậy sẽ là CÙNG MỘT
  thư mục cho mọi app trên máy.
- **Sàn `lmdb>=1.7.5`** chọn theo tiêu chí nói ra được: bản đầu tiên có wheel
  dựng sẵn cho **đủ dải Python của gói** (cp312/313/314). Đã cài **đúng ở sàn**
  rồi chạy lại 114/114 test, theo bước 1b của hướng dẫn phát hành.

#### ⭐ Một lỗi do phép ĐỐI CHỨNG tìm ra, không do đọc lại code

Vòng lặp theo lô của job dọn ban đầu viết *"chạy tới khi không còn gì hết hạn"*.
Đó **không phải một lối ra đảm bảo**: `_delete_batch` nuốt một giao dịch ghi hỏng
rồi trả 0, trong khi lần quét sau vẫn báo đúng những khoá đó là hết hạn - nên một
kho không ghi được sẽ quay vòng đó **mãi mãi, đốt trọn một nhân, im lặng**.

Nó lộ ra khi gỡ thử một phép kiểm để xem test nào đỏ: bộ test **không đỏ mà
TREO**, một tiến trình pytest quay 100% CPU trong ba phút. Nay mỗi vòng phải xoá
được ít nhất một khoá, nếu không thì dừng kèm cảnh báo.

⚠ Và đối chứng còn chỉ ra một chỗ thứ hai: gỡ phép kiểm hết hạn trong lúc quét ra
thì **không test nào đỏ**, vì lớp thứ hai (kiểm lại trong giao dịch ghi) vẫn giữ
đúng dữ liệu. Cái hỏng nằm ở **TÍN HIỆU** chứ không ở dữ liệu - job kêu "dừng
sớm" trên một kho hoàn toàn khoẻ, mỗi mười phút. Đã thêm test canh, vì **phép dò
kêu oan là phép dò sẽ bị tắt**.

#### ⭐⭐ Và một lỗi thứ hai, do TEST ĐI ĐÚNG ĐƯỜNG TÀI LIỆU tìm ra

128 test đầu tiên đều dựng `LmdbEnvironment(runtime)` rồi `MyTable(env)` **bằng
tay** - nhanh, gọn, và **không tiến trình thật nào làm vậy**. Người dùng thật gõ
`dependency.scan("xime.starters.lmdb")` rồi để DI dựng.

Lần đầu viết một test đi qua DI thật, **cả 12 test đỏ ngay**: `LmdbConfig` nằm
trong `__all__`, mà `__all__` của một package starter **không chỉ là danh sách
export - nó là danh sách DI scanner đăng ký**. `LmdbConfig` là dataclass có
trường đầu `path: str`, nên container đi tìm binding cho `str` và **mọi app scan
starter này sẽ chết lúc khởi động** với `Unregistered Dependency: str`.

Đây **đúng khuôn phát hiện C2 của kiểm toán 0.7.0** (`dependency.register(ModbusClient)`
chết ngay tại dòng lệnh tài liệu bảo gõ), và cũng đúng bài học rút ra từ nó:

> Với mỗi tính năng, viết ít nhất một test đi **đúng con đường tài liệu hướng
> dẫn**, không phải con đường tiện nhất cho test.

Đã sửa (`LmdbConfig` và ba lớp ngoại lệ ra khỏi `__all__`, re-export bằng dạng
alias trùng tên của PEP 484) và thêm test canh **chốt chính xác** tập class mà
scanner được phép đăng ký, kèm vế đối chứng rằng chúng vẫn import được.

---

## [0.7.2] - 2026-08-18

**JWT: khóa xoay theo `kid`, và trả nợ trung tính.**

Starter JWT mô hình hóa JWT như *"một chuỗi ký bằng MỘT khóa cố định"*. Không có
gì của dự án nào lọt vào nó - mọi trường đều chuẩn RFC, chỉ đổi tên. Vấn đề là
**những thứ KHÔNG có**: framework **ký** kèm `kid` nhưng **không có một dòng nào
verify theo `kid`**, nên mọi triển khai có xoay khóa buộc phải viết lại cả
middleware - tức viết lại chính phần verify mà không ai muốn đụng.

Chi tiết + phép đo: `.claude/docs/jwt-keyset-va-trung-tinh-2026-08-18.md`.

Test: **1553 passed, 11 skipped** (0.7.1: 1516). **Không phá app nào đang chạy.**

⬆ Sau F1 + F3 + F14 + F15 + F17 trong cùng ngày: **1624 passed, 11 skipped**.

### Added

⚠ Phép đo: `grep -rn "kid" xime/starters/jwt/` trước bản này ra **đúng một dòng**, ở
`_signer.py` lúc KÝ. Phía verify không có gì. Và **21/21 repo dùng framework đã tự
viết lại** middleware JWT - 413 dòng mỗi repo.

- **`JwtKeyProvider`** - Protocol một method, `keys(kid) -> Sequence[KeyContext]`,
  đăng ký bằng `configure_jwt(config, key_provider=YourClass)`. Cùng khuôn
  `configure_grpc_tls(provider=...)`: truyền một CLASS, framework lấy từ DI.
  `keys()` **bắt buộc đọc bộ nhớ, không bao giờ gọi mạng**; framework không lấy,
  không hẹn giờ, không cache - **giữ khóa luôn mới hoàn toàn là việc của app**.
  Nhận `kid` là **chuỗi của RFC 7515**, không phải kiểu dữ liệu nào của framework.
- **Middleware verify theo `kid`**: đọc header bằng `get_unverified_header` (không
  cần khóa), hỏi provider, thử lần lượt các khóa ứng viên. Nhiều ứng viên là bình
  thường trong lúc xoay khóa gối đầu, và đó là thứ làm cho nó liền mạch.
- **`JwtMiddlewareConfig` phơi ba knob PyJWT vốn có mà config giấu đi**:
  `algorithms` (danh sách trắng - **trần** chứ không phải phép chọn, khóa nào khai
  thuật toán ngoài danh sách thì bị từ chối trước khi kiểm chữ ký), `leeway`
  (dung sai đồng hồ cho `exp`/`nbf`/`iat` - thiếu nó thì hai máy lệch vài giây
  sinh **401 chập chờn**), `require` (⚠ `exp` chỉ được kiểm khi claim **tồn tại**,
  nên token không mang `exp` mặc định **không bao giờ hết hạn**).
- **`sign()` nhận `headers=`.** Trước đây `kid` là header **duy nhất** app đặt
  được, trong khi payload thì mở toang - nên `typ: "at+jwt"` của RFC 9068 không
  khai nổi. Ba tên bị **từ chối** chứ không gộp: `alg` (PyJWT cho header ghi đè
  tham số `algorithm`, đo được, nên nó âm thầm mâu thuẫn với
  `KeyContext.algorithm`), `b64` (bật chế độ detached payload), `kid` (phải gọi
  tên đúng khóa đã ký, mà chỉ `KeyContext.key_id` biết đó là khóa nào).

### Fixed

- ⛔ **`configure_jwt()` không có nguồn khóa nào nay NỔ lúc khởi động.**
  `key_context` từ bắt buộc thành tùy chọn, và phải có **đúng một** trong
  `key_context` / `key_provider` - không có cái nào, hoặc có cả hai, đều là
  `StartupException`. Từ chối *"không có cái nào"* là toàn bộ mục đích: trước đây
  app không lấy được khóa lúc khởi động chỉ đơn giản là **không gọi `configure_jwt`**
  và lên mà **không có middleware xác thực nào**, tự báo là khỏe trong khi mọi
  endpoint đều mở. **Không phá app nào đang chạy**: `key_context` vốn bắt buộc nên
  trạng thái "không có gì" trước nay không tồn tại được.
- **Middleware nhận `verifier` từ ngoài thay vì tự dựng `PyJwtTokenVerifier()`.**
  `JwtTokenVerifier` là điểm mở rộng **có tài liệu từ 0.2** - docstring của nó nêu
  đích danh JWKS endpoint và authorization server bên ngoài - nhưng middleware do
  adapter dựng chứ không do DI dựng, nên `dependency.bind({JwtTokenVerifier: ...})`
  **không bao giờ tới được nó**. Không có gì hỏng; phép thay thế chỉ đơn giản là
  không có tác dụng, và **không test nào tồn tại để bắt được**. Nay khai tường
  minh qua `configure_jwt(config, verifier=YourClass)`.
- **`key_id=""` không còn đóng dấu `kid: ""` vào token thật.** `is not None` cho
  chuỗi rỗng lọt qua. Tệ hơn cả không có `kid`: bên verify tra `""` không thấy gì
  rồi từ chối, trong khi token vẫn **trông như đã gọi tên khóa** - người gỡ lỗi
  bắt đầu từ chỗ sai.

### Notes

- **Không có gì phá vỡ.** Mọi mục đều là mở một ô mới hoặc chuyển tiếp thêm tham
  số; app đang dùng một khóa tĩnh chạy y như cũ.
- `verify()` nhận thêm ba tham số keyword. Về lý thuyết đó là đổi Protocol
  `JwtTokenVerifier`; thực tế **không có implementation nào của bên thứ ba được
  biết tới**. Tới knob thứ tư thì nên gom chúng vào một object options thay vì
  liệt kê tiếp - đã ghi vào docstring.
- **Không nằm trong đợt này**, vẫn còn nợ: xác thực WebSocket (F1) và JWT cho
  gRPC. Cả hai là **bề mặt mới**, không phải sửa chữa.
- Cảnh báo *"ký mà không có `kid`"* **không làm được**: `sign()` nhận khóa theo
  từng lời gọi nên lúc khởi động framework chưa biết gì, còn cảnh báo mỗi lần gọi
  thì thành rác log. Chuyển thành tài liệu trong docstring của `PyJwtTokenSigner`.

---

**Tài liệu: README hết khai sai về WebSocket.**

### Fixed

- `README.md` và `README-vn.md` vẫn viết *"WebSocket support is partial"* /
  *"WebSocket đang hoàn thiện"*, và mục "cần cộng đồng giúp" vẫn liệt
  *"completing WebSocket support"*. README là **trang đích trên PyPI**, nên đó
  là thứ người ngoài đọc trước tiên.
- ⚠ Kèm một chỗ trôi lệch giữa hai bản: `README-vn.md` mô tả gRPC adapter thiếu
  **server streaming có kiểu** - tính năng chính của 0.7.1 - trong khi bản tiếng
  Anh có. Hai trang đích nói hai chuyện khác nhau về cùng một bản.
- Thêm `docs/{vn,en}/websocket.md` vào bảng tài liệu của cả hai README.

**WebSocket: có đường đăng ký route, và có xác thực (F1).**

⚠ **Đổi API công khai trong một bản patch.** Chủ dự án chốt làm ngay vì **chưa
app nào dùng WebSocket**, nên hôm nay đổi là miễn phí; đợi tới lúc có app chat
thì không.

Trước bản này `WebSocketHandler` là một lớp nền **không có đường gắn vào ứng
dụng** - không `@ws`, không `add_api_websocket_route` ở đâu trong `xime/`, và
chính docstring của nó viết *"routing API sẽ được thiết kế sau"*. Cộng với việc
`JwtAuthMiddleware` cho mọi scope không phải `http` đi thẳng, một route WebSocket
tự dựng bằng tay nhận **mọi** kết nối, kể cả không có token.

### Added

- **`@ws("/path")`** - decorator cấp lớp, đánh dấu một `WebSocketHandler`. Lớp
  được DI dựng như mọi controller và quét từ cùng danh sách gói.
- **Xác thực bắt tay bằng subprotocol.** Trình duyệt không đặt được header trên
  `new WebSocket(...)`, nên token đi trong `Sec-WebSocket-Protocol` - cách chuẩn
  của ngành (Kubernetes, Firebase), và khác query string nó **không lọt vào log
  proxy, lịch sử trình duyệt hay `Referer`**.

```js
new WebSocket(url, ["xime.bearer." + token, "xime"]);
```

- **`JwtAuthenticator`** - phần verify tách khỏi `JwtAuthMiddleware` để HTTP và
  WebSocket dùng **chung một** định nghĩa "token hợp lệ".
- **`close_on_token_expiry`** (mặc định **BẬT**) - đóng kết nối khi token mở nó
  hết hạn. Thiếu nó thì thu hồi token **không cắt được** phiên WebSocket.
- **`JWT_CLAIMS` nay export được** từ `xime.starters.jwt`. Script
  `check_doc_imports.py` bắt được: tài liệu bảo người đọc tra claim, mà hằng số
  đó chỉ nằm trong `_middleware`.
- Tài liệu mới: `docs/{vn,en}/websocket.md`.

### Changed

- Đã gọi `configure_jwt()` thì **mọi** đường `@ws` đòi token hợp lệ, trừ đường
  nằm trong `public_paths` - **cùng danh sách với HTTP**, vì *"đường này mở"* nên
  mang một nghĩa trong một ứng dụng chứ không phải hai.
- `on_connect` mặc định nay accept kèm **vọng lại subprotocol đã thoả thuận**,
  và không bao giờ vọng lại entry chở token.
- Có route `@ws` mà **chưa** gọi `configure_jwt()` thì WARNING lúc khởi động nêu
  tên từng handler. Hành vi không đổi; thứ chấm dứt là sự im lặng.

⭐ **Xác thực chạy ở lớp ĐĂNG KÝ ROUTE, không nằm trong `on_connect`** - khác đề
xuất của kiểm toán, và đây là phần đáng đọc nhất. Đặt trong `on_connect` thì nó
là một mặc định mà lớp con xoá đi chỉ bằng cách override method đó, mà đó lại là
method đầu tiên ai cũng override. Có test canh: handler tự gọi `accept()` và
không gọi `super()` **vẫn không tới được**.

⚠ **Kiểm `Origin` cố ý KHÔNG làm.** Trình duyệt không áp CORS lên bắt tay
WebSocket, nên *Cross-Site WebSocket Hijacking* là rủi ro thật - **nhưng chỉ khi
xác thực dựa vào cookie**. Token đi bằng subprotocol thì trang của kẻ tấn công
**không có token** để đưa vào; rủi ro bị đóng ở gốc. Ngày nào thêm đường xác
thực bằng cookie thì kiểm `Origin` thành **bắt buộc** - đã ghi trong tài liệu.

31 test mới đi thành **cặp**; đối chứng gỡ phép kiểm ra **5 đỏ**.

**EventBus: trần số handler đang bay, và cách khai thứ không được bỏ (F15).**

`publish()` sinh một asyncio Task cho mỗi handler rồi trả về ngay, không trần.
Đo trên code cũ: 50.000 `publish` x 2 handler ra **100.000 task đang chờ**; và
20.000 event x payload 1 KB giữ **36 MB** - vì `_pending` giữ tham chiếu mạnh
tới task, task giữ coroutine, coroutine giữ **chính object event**. Bộ nhớ vì
vậy tăng theo **kích thước event**, không theo một hằng số overhead.

Đo thêm: task nền sao chép contextvars lúc tạo, nên handler chạy với
`identity`/`permissions` của người gửi request kể cả sau `clear_security()`.
Không phải lỗi (audit handler cần đúng thứ đó), nhưng cộng lại thì **task tồn
đọng cũng là quyền hạn tồn đọng**.

### Added

- **`configure_event_bus(max_pending=..., never_drop=(...))`** trong
  `xime.core.event`. Đây là **framework config, viết bằng Python** trong
  `config/*.py` - **không** có khoá nào trong `application.yml`, vì chọn con số
  này đòi hỏi biết handler chạy bao lâu, event to cỡ nào, và event nào không
  được phép mất; người vận hành không biết ba thứ đó.
- **`EventBus.dropped` / `EventBus.dropped_by_type()`** - log nói *vừa bỏ một
  cái*, hai số này nói *đã bỏ bao nhiêu*. Chỉ cái sau dùng được để chỉnh trần.

### Changed

- Quá `max_pending` (**mặc định 10.000**) thì event bị bỏ **nguyên con** - hoặc
  chạy hết handler, hoặc không handler nào. Nửa event là trạng thái không ai
  thiết kế cho, mà lại không nhìn thấy được từ bên ngoài.
- Log WARNING **có hãm nhịp** (lần đầu + mỗi 1.000 lần bỏ), nêu tên loại event
  và cả hai cách sửa.

Hai cách nói "đừng bỏ cái này":

| Khai | Nghĩa |
|---|---|
| `never_drop=(AuditEvent,)` | Miễn trần cho vài loại. **Khớp kiểu chính xác**, giống cách tra handler - lớp con không thừa hưởng |
| `max_pending=None` | Bỏ trần hoàn toàn, đúng hành vi trước 0.7.2 |

⚠ `never_drop` **dời** rủi ro chứ không xoá: lũ event được miễn vẫn phình vô
hạn, nên vượt trần thì bus ghi WARNING nói đúng điều đó (bộ đếm hãm nhịp
**riêng** - dùng chung với bộ đếm bỏ thì `0 % 1000 == 0` khiến nó kêu ở mọi lần
publish, có test canh).

⛔ **Nợ luật 03 khai ra, cố ý chưa trả:** bên gọi không phân biệt được event bị
bỏ với event đã xếp lịch - cả hai trả `None`. Đóng nó là đổi chữ ký công khai
nên để **0.8**. Hệ quả đã ghi vào tài liệu: **đừng dùng event bus cho thứ mà mất
là phải phát hiện được.**

⚠ Ghi nhận, chưa làm: framework **không tự gọi `drain()` lúc tắt máy**, nên
handler đang chạy bị cắt ngang. Tài liệu nay bảo người dùng gọi trong
`PreDestroy`; sửa cho tử tế thuộc 0.8 vì chạm vòng đời adapter.

16 test đi thành **cặp** (phải bỏ / phải không bỏ). Đối chứng: gỡ phép kiểm ra
**8 đỏ / 8 xanh**, và 8 xanh đúng là nhóm "phải không bỏ".

**MQTT RPC: nói ra được reply đi đâu, và kêu khi nó đi chỗ khác (F17).**

MQTT v5 cho **bên gọi** đặt `ResponseTopic`, còn adapter publish reply bằng
credential broker của **dịch vụ**. Trên broker có ACL theo client, bên gọi vì
vậy chạm được topic mà ACL của nó cấm - nó mượn quyền của ta (*confused
deputy*). Bên gọi cũng điều khiển hoàn toàn `CorrelationData`, và bytes đó được
chép nguyên xi vào reply.

Chủ dự án chốt: **cảnh báo, không chặn.**

### Added

- **`mqtt.rpc.reply_topics`** - danh sách **topic filter MQTT** (không phải tiền
  tố chuỗi) mà reply RPC được phép rơi vào. Không khai thì hành vi y hệt trước.

```yaml
mqtt:
  rpc:
    reply_topics: [nhamay/reply/#, devices/+/reply]
```

| Cấu hình | Hành vi |
|---|---|
| Không khai | Như cũ. **Một** WARNING lúc khởi động, chỉ khi client có `@rpc` |
| Khai, reply khớp | Im lặng |
| Khai, reply không khớp | **Vẫn gửi**, kèm WARNING nêu tên topic |

⚠ Dùng filter chứ không dùng tiền tố vì adapter này vốn đã bắt người dùng nghĩ
bằng filter ở `@subscribe`; thêm hệ so khớp thứ hai trong cùng một adapter là tự
tạo bẫy. Cũng vì vậy khoá **không** mang tên `reply_prefix` như kiểm toán đề
xuất: `nhamay/reply/` đọc như một tiền tố hợp lý nhưng là filter thì nó khớp
**không gì cả**.

Bốn chi tiết cố ý, đừng gỡ:

- Kiểm **trước** khi gọi handler, để dòng log vẫn xuất hiện khi handler ném lỗi.
- Cảnh báo **khử trùng lặp + chặn trần 64 topic**, để bên gọi không biến một
  cảnh báo thành lũ log bằng cách đổi topic.
- Filter sai cú pháp **nổ lúc khởi động**: filter không bao giờ khớp thì mọi
  reply đều thành cảnh báo, và cảnh báo kêu oan là cảnh báo sẽ bị tắt.
- Cảnh báo khởi động chỉ kêu khi client **thực sự có `@rpc`**.

Test đi **thành cặp ở cả hai tầng** (phải kêu / phải im), vì bản hiện thực "luôn
kêu" cũng qua được nếu chỉ kiểm một vế. Đối chứng: gỡ phép kiểm ra **4 đỏ**,
nhóm "phải im" vẫn xanh.

⚠ Phòng thủ chiều sâu, **không thay thế ACL broker**.

**Khóa lưu trữ: từ chối gạch ngược và NUL ở MỌI backend (F14).**

`validate_object_key` dùng `PurePosixPath`, mà với nó `\` chỉ là ký tự thường -
nên một khóa kiểu Windows đi lọt cả ba phép kiểm rồi mang **ba** nghĩa khác nhau:
traversal trên local Windows, tên file thật trên local Linux, khóa thật trên S3.
Docstring của chính hàm đó hứa *"đổi backend không đổi tập key hợp lệ"*, và lời
hứa đó đang sai.

NUL thì thuộc loại khác và nặng hơn: `Path.exists()` trả **`False`** (câu trả lời
sai đội lốt câu trả lời đúng - dấu hiệu 3 của luật 03), còn `open()` ném
**`ValueError`** trần chứ không phải `StorageError`, tức rò kiểu ngoại lệ qua
biên API công khai.

### Changed

- `validate_object_key` từ chối thêm `\` và `\x00`. `StorageError` như mọi phép
  kiểm khác, thông điệp nói rõ ký tự vi phạm.

⚠ **Đây là siết đầu vào**, nên về lý là phá tương thích với ai đang ghi khóa chứa
`\` lên S3. Đo trước khi làm: `data-service` là nơi duy nhất gọi tầng storage và
`ObjectKeyPolicy` của nó đã tự chuẩn hoá `filename.replace("\\", "/")` từ trước,
nên **không app nào phải sửa**. Chưa app nào dùng starter `s3`.

- Test đi **thành cặp** ở cả hai backend, dùng **chung một danh sách**
  `UNSAFE_KEYS` (test S3 `import` từ test local chứ không chép tay): một test bắt
  4 khóa xấu phải bị từ chối, một test bắt `a..b/c` và ba khóa thường **vẫn phải
  nhận**. Vế sau không thừa - chỉ có vế đầu thì cách sửa sai *"từ chối mọi thứ có
  dấu chấm"* cũng qua được. Đối chứng: gỡ hai dòng vá thì **5 test đỏ**.

**Sàn dependency: nâng 10 mốc, sửa 3 mốc SAI, thêm một phép kiểm cố định (F3).**

`pip-audit` trên đúng tổ hợp sàn ta khai ra **26 CVE ở 3 gói** - trong khi chú
thích ngay trên nó viết *"mỗi mốc đều đã CÀI THỬ chứ không phỏng đoán"*. Câu đó
không sai: nó trả lời *"sàn có CHẠY không"*, còn `pip-audit` hỏi *"sàn có AN TOÀN
không"*. Hai câu khác nhau, và chỉ câu đầu từng được kiểm.

Test trên **24 sàn ghim thật**: **1553 passed, 11 skipped**. Rồi chạy lại trên
môi trường mới nhất: 1553 passed, cộng `data-service` 388 và `linh-kien-dien-tu`
295 - hai app thật, để chắc bước nhảy starlette 0.x -> 1.x không phá gì.

### Changed

Sàn nâng vì **advisory**:

| Gói | Trước | Sau |
| --- | --- | --- |
| `pyjwt` | `>=2.8` | `>=2.13` |
| `python-multipart` | `>=0.0.7` | `>=0.0.31` |
| `starlette` | *không khai* | `>=1.3.1` |
| `fastapi` | `>=0.110.1` | `>=0.133.0` |
| `msgpack` | `>=1.0` | `>=1.2.1` |
| `aiosmtplib` | `>=3.0` | `>=5.1.1` |
| `protobuf` | `>=4.25` | `>=6.33.5` |
| `cryptography` (dev) | `>=42` | `>=50.0.0` |
| `pytest` (dev) | `>=8.0` | `>=9.0.3` |

⭐ **`starlette` nay được khai TRỰC TIẾP dù xime không import gì từ nó** (mọi ký
hiệu cần đều được fastapi tái xuất - xem 2026-08-17). Khai để **ràng buộc
resolver**, và nó cần thiết vì đề xuất ban đầu *"nâng fastapi để kéo starlette"*
**không chạy được**: mọi bản fastapi từ 0.115 tới 0.132 đều khai
`starlette>=0.40.0` với một **nắp trên di chuyển**, còn cận dưới thì đứng yên.
Lái một phụ thuộc bắc cầu bằng sàn của phụ thuộc trực tiếp chỉ đi được tới **cận
dưới của nó**, mà cận dưới đó không phải của mình. Advisory của starlette lại chỉ
vá trong nhánh 1.x, không backport về 0.x.

Sàn sửa vì **khai SAI**, tìm ra nhờ cài ở đúng sàn rồi chạy test:

| Gói | Trước | Sau | Sai thế nào |
| --- | --- | --- | --- |
| `sqlalchemy[asyncio]` | `>=2.0` | `>=2.0.38` | Lệch **38 bản patch**, sai từ ngày viết. Hai bức tường: `import sqlalchemy` chết trên Python 3.13+, và starter truyền `pool_size` cho `NullPool` |
| `aiomqtt` | `>=2.0` | `>=2.1.0` | **Mâu thuẫn với `paho-mqtt>=2.1` cùng extra** - `pip install xime[mqtt]` ở đúng sàn là bất khả thi |
| `pytest-asyncio` (dev) | `>=0.23` | `>=1.3.0` | Nổ `INTERNALERROR` với pytest 9, dù metadata khai tương thích |

### Added

- **`.claude/scripts/check_dep_advisories.py`** - soi advisory của **bộ sàn khai
  trong `pyproject.toml`**, không phải của môi trường đang chạy. Đọc sàn thẳng từ
  file (không giữ bản sao thứ hai sẽ trôi lệch), có danh sách **CHẤP NHẬN kèm lý
  do**, thoát mã 1 nếu còn mục chưa xử. Thêm vào hướng dẫn phát hành thành
  **bước 1b**.

### Notes

- ⚠ **Một advisory được CHẤP NHẬN, không vá được**: `apscheduler` PYSEC-2026-282 /
  CVE-2026-31072 (RCE qua `JSONSerializer`/`CBORSerializer`). Dải ảnh hưởng
  `4.0.0a1..4.0.0a6` **không có bản vá**, mà `4.0.0a6` là bản mới nhất tồn tại.
  Xime không dính ở cấu hình mặc định - `AsyncScheduler()` không tham số dựng
  `MemoryDataStore` + `LocalEventBroker`, không cái nào dùng serializer. **Nhưng
  sự an toàn đó thuộc về CÁCH NỐI DÂY MẶC ĐỊNH, không thuộc về thư viện**: app tự
  cấu hình kho dữ liệu ngoài thì **có** dính, và không có gì cảnh báo nó.
- **Bốn sàn không kiểm chứng được trên Python 3.14** (bản mới nhất ta tuyên bố hỗ
  trợ): `pydantic 2.5`, `grpcio 1.60`, `grpcio-tools 1.60`, `asyncpg 0.29` - đều
  không build nổi. Giữ nguyên cho người dùng Python cũ, và ghi chú tại chỗ.
- ⭐ Bài học đắt nhất, đáng nhớ hơn mọi con số ở trên: **sàn là `>=`, nên pip mặc
  định cài bản MỚI NHẤT. Một sàn sai vì vậy hoàn toàn vô hình - cho tới ngày có
  người ghim xuống, và khi đó nó đã thành vấn đề của họ.**

## [0.7.1] - 2026-08-03

**Server streaming cho bản ghi có kiểu, và đợt vá bảo mật thứ nhất.**

Hai phần độc lập nhau đi chung một bản:

1. **`@stream` + `yield`** - server streaming của **DTO**, không phải byte. Trước
   bản này framework chỉ stream được byte qua wrapper `*Chunk` (tải file), nên
   một feed kiểu `rpc Watch(Req) returns (stream Event)` không phơi được ở
   server và không tiêu thụ được ở client. Yêu cầu đến từ phiên data-service +
   user-service (`.claude/docs/yeu-cau-server-stream-kieu-du-lieu-2026-08-02.md`).
2. **Đợt 2 của kế hoạch vá bảo mật** (`.claude/docs/ke-hoach-va-bao-mat-2026-08-01.md`):
   F2, F4, F5, F6, F7, F8, F11, F12, F13, F16. Mọi mục đều tái hiện được bằng
   PoC trước khi vá và chạy lại PoC sau khi vá.

Bổ sung 2026-08-04: hai **lỗi đua** - một khi tắt scheduler (phát hiện qua vướng
mắc của phiên `user-locator`), một khi công bố file trong localfs trên Windows
(phát hiện vì một test đỏ ~10% số lần chạy). Xem mục Fixed.

Bổ sung 2026-08-17: **gỡ phụ thuộc khái niệm** (`current_app_id` → `current_peer_sans`,
BREAKING) và **khai ba phụ thuộc bắc cầu**. Xem hai mục cuối.

Test: **1516 passed, 11 skipped**. Số skip tăng từ 7 lên 11 **không phải vì có
test bị tắt**: hai extra `mqtt` và `s3` trước nay chưa từng được cài trên máy
này, nên vài module bị skip cả gói và đếm là **một** skip; cài rồi thì chúng được
thu thập thành từng test, phần cần broker/MinIO mới skip lẻ. Đổi lại **2 test giờ
chạy thật** thay vì bị bỏ qua. Đã chạy thêm bộ test của bốn ứng dụng thật
(data-service 347, linh-kien-dien-tu 295, shop 166, crm 53).

### Added

- **Server streaming có kiểu.** Handler viết `async def ... -> AsyncIterator[Model]`
  với `yield`; proto sinh ra `rpc X(Req) returns (stream Resp)` **không wrapper**,
  nên peer Java đọc `.proto` là hiểu. Client SDK sinh
  `def x(self, req) -> AsyncIterator[Resp]`. Ba dạng khai sai (`@command` có
  `yield`; vừa `DownloadStream` vừa `yield`; thiếu annotation `AsyncIterator[...]`)
  đều báo lỗi lúc **khởi động**. Dạng byte (`DownloadStream`) giữ nguyên.
- **`grpc.clients.<id>.stream_deadline_ms`** - deadline riêng cho call
  server-streaming, mặc định `0` (không giới hạn).
- **`grpc.clients.<id>.keepalive.*`** (client) và **`grpc.keepalive.*`** (server) -
  ping HTTP/2 cho kết nối dài, mặc định TẮT. Bật ở client thì server phải nới
  `min_ping_interval_without_data_ms`, nếu không server trả GOAWAY
  `too_many_pings`.
- **`storage.local.file_mode` / `dir_mode`** cho backend localfs (mặc định
  `0600`/`0700`). Viết dạng chuỗi có nháy: YAML đọc `0600` không nháy thành số
  600 hệ mười.

### Fixed

- **localfs: hai lần ghi đồng thời cùng một key thất bại trên Windows.** `os.replace`
  công bố file tạm là nguyên tử trên POSIX, nhưng trên Windows `MoveFileEx` báo
  `ERROR_ACCESS_DENIED` khi file **đích** đang được ai đó mở - kể cả khoảng rất
  ngắn mà một lần công bố đồng thời cùng key đang giữ nó. Đo được **~10% lần chạy
  đỏ**. Nay công bố qua `_publish()` có **retry giới hạn** (5 lần, backoff từ 5ms)
  rồi **ném lại**: va chạm tạm thời hết sau vài mili giây, còn nguyên nhân vĩnh
  viễn (đích read-only, có người giữ file mở lâu) vẫn lộ ra thành `PermissionError`
  chứ không bị nuốt. POSIX không đổi gì - lần thử đầu luôn thành công.
  Có **cặp test** canh cả hai nhánh; chỉ canh một nhánh thì cách sửa sai "nuốt mọi
  `PermissionError`" cũng qua được. Chỉ `Base Platform/data` dùng backend này.
- **Lỗi đua khi tắt scheduler - chạm mọi ứng dụng có job nền.** `SchedulerRunner`
  phóng vòng lặp bằng `asyncio.create_task(run_until_stopped())`, hàm này trả về
  **trước khi vòng lặp kịp chạy**. Ứng dụng tắt ngay sau đó thì
  `AsyncScheduler.stop()` **im lặng không làm gì** (nó chỉ có tác dụng khi trạng
  thái đã là `started`), rồi `__aexit__` dọn kho dữ liệu dưới chân một task chưa
  khởi động -> `RuntimeError: The scheduler has not been initialized yet`. Nay
  dùng `start_in_background()` của chính APScheduler, hàm chỉ trả về khi vòng lặp
  đã báo `started`. Không phải nâng dependency (`apscheduler>=4.0.0a6` đã có).
  ⚠ Đây **không** phải giới hạn của môi trường test như báo cáo ban đầu: tái hiện
  được bằng `asyncio.run()` thuần. Tiến trình chạy lâu chỉ che nó đi vì `start`
  và `stop` cách nhau đủ xa. Chi tiết:
  `.claude/docs/loi-dua-scheduler-2026-08-04.md`.
- **F2 - XSS lưu trữ qua cặp upload/download.** `save_upload` lấy content type
  từ **tên file** thay vì header `Content-Type` của phần multipart (do kẻ gọi
  điều khiển, và backend S3 trả lại y nguyên lúc tải về). `stream_object` luôn
  gắn `X-Content-Type-Options: nosniff` và ép `Content-Disposition: attachment`
  cho mọi kiểu ngoài danh sách hiển thị-an-toàn.
- **F8 - tên file có dấu làm hỏng phản hồi.** `Content-Disposition` dựng theo
  RFC 6266 (`filename=` ASCII + `filename*=UTF-8''...`). Trước đây tải file tên
  `Hóa đơn.pdf` là **HTTP 500**, và dấu nháy trong tên thoát được khỏi tham số.
- **F13 - localfs.** Tên file tạm dùng `uuid4()` thay `os.getpid()`: hai upload
  cùng key trong cùng tiến trình từng ghi chung một file tạm rồi công bố kết quả
  lai (lỗi toàn vẹn dữ liệu). `put()` nay đi chung đường staging nguyên tử với
  `put_stream()`. File tạo với quyền `0600`, thư mục `0700`.
- **F12 - metadata lỗi gRPC.** Exception **chưa map** báo `xime-error:
  InternalError` thay vì tên class nội bộ thật (`_safe_details()` vốn đã che
  `str(exc)` vì cùng lý do). Exception đã map giữ nguyên tên như cũ.

### Changed

- **F4 - `configure_cors` fail-fast.** Khởi động thất bại khi `allow_origins`
  (hoặc `allow_methods`/`allow_headers`/`expose_headers`) là **chuỗi** thay vì
  danh sách, và khi `allow_origins: ["*"]` đi cùng `allow_credentials: true`.
  Ca thứ hai KHÔNG được trình duyệt chặn như chú thích cũ nói: Starlette phản
  chiếu đúng origin của người gọi.
- **F5 - `repr(RuntimeConfig)` che secret.** Khoá có tên chứa
  `secret/password/token/key/credential` in ra `***`. `get()` không đổi.
- **F7 - thiếu file profile thì cảnh báo.** `XIME_ENV=production` mà không có
  `application-production.yml` nay ghi WARNING thay vì im lặng chạy bằng
  `application.yml`.
- **F6 - nói ra khi đang chạy chế độ không an toàn** (log một lần lúc khởi
  động, không đổi mặc định): gRPC server plaintext hoặc TLS-không-mTLS, OPC UA
  `security=None` (cả client lẫn server), MQTT không TLS (nặng hơn khi có kèm
  tài khoản/mật khẩu), socket adapter không đọc được SO_PEERCRED.
- **F11 - `configure_jwt()` không đặt `audience`** thì cảnh báo lúc khởi động.
- **F16 - `save_upload` có trần mặc định 32 MiB** (trước đây không giới hạn).
  Muốn bỏ trần thì truyền `max_bytes=None` tường minh.

### ⚠ Đổi hành vi, đọc trước khi nâng cấp

| Đổi gì | Ảnh hưởng ai |
| --- | --- |
| `stream_object` ép tải xuống với kiểu ngoài danh sách an toàn | App phục vụ **SVG**, HTML, JSON... theo kiểu hiển thị tại chỗ. Ảnh PNG/JPEG/GIF/WebP, PDF, MP4, text/plain vẫn inline. `image/svg+xml` cố ý KHÔNG nằm trong danh sách: SVG chạy được script |
| `save_upload` bỏ qua `Content-Type` của client | App dựa vào giá trị đó phải truyền `content_type=` tường minh |
| `save_upload` mặc định trần 32 MiB | App cho tải file lớn hơn phải khai `max_bytes` |
| `configure_cors` nổ với cấu hình sai kiểu | App đang khai `cors.allow_origins` dạng chuỗi sẽ không khởi động được - đó là mục đích |
| Deadline của server-streaming đổi sang `stream_deadline_ms` (mặc định 0) | Luồng tải file trước đây bị `deadline_ms` cắt thì nay không còn bị. Muốn giữ giới hạn thì khai `stream_deadline_ms` |
| `xime-error` của lỗi chưa map thành `InternalError` | Client nào so khớp `RemoteCallError.code` với tên class nội bộ (không nên có) |
| ⛔ **`current_app_id()` / `PEER_APP_ID` bị GỠ HẲN** | Xem mục "Gỡ phụ thuộc khái niệm" ngay dưới. Thay bằng `current_peer_sans()` / `PEER_SANS` |

### ⛔ BREAKING - Gỡ phụ thuộc khái niệm khỏi framework (2026-08-17)

**Framework không còn biết quy ước định danh của bất kỳ nền tảng nào.**

Bản 0.6.3 thêm `current_app_id()`, và cùng với nó là hai hằng số đóng cứng trong
`adapters/grpc/interceptors/_context.py`: một **scheme URI riêng của Xime
Platform** và **độ dài định danh 33 ký tự** (hệ quả của việc một service khác
chọn KSUID 24 byte + Base62 pad trái). Không hằng số nào trong hai cái đó là
khái niệm phổ quát, nên chúng không thuộc về một framework dùng chung.

| Gỡ | Thay bằng |
| --- | --- |
| `current_app_id() -> str \| None` | `current_peer_sans() -> tuple[str, ...] \| None` |
| `PEER_APP_ID` (`"peer_app_id"`) | `PEER_SANS` (`"peer_sans"`) |

`PEER_CN` và `current_caller()` **không đổi** - CN là khái niệm chuẩn X.509.

**Cách chuyển:** trước đây framework lọc SAN hộ bạn rồi trả **một** giá trị đã cắt
scheme. Nay nó trả **mọi** entry SAN, thô, và việc khớp là của bạn:

```python
# trước
app_id = current_app_id()

# sau - bạn khai scheme của mình, framework không cần biết nó tồn tại
LABEL, SCHEME = "URI:", "your-scheme://"

def _app_id() -> str | None:
    for entry in current_peer_sans() or ():
        value = entry.removeprefix(LABEL)   # nhãn loại SAN nếu transport có thêm
        if value.startswith(SCHEME):        # NEO ĐẦU chuỗi, đừng dùng find()
            return value[len(SCHEME):]
    return None
```

⚠ **Hai chi tiết trong đoạn trên đều đã cắn thật, đừng lược bỏ:**

- **Cắt nhãn `LABEL` trước khi so.** Bản cũ của framework so bằng `find()` nên chấp được cả dạng
  `URI:your-scheme://...` mà một số công cụ in ra. Nay framework trả **nguyên văn**, nên nếu bạn
  chỉ `startswith(SCHEME)` thì entry có nhãn **rơi im lặng thành `None`**, tức bị hiểu thành
  "không có định danh". Phiên `data-service` phát hiện đúng chỗ này khi chuyển đổi.
- **Nhưng đừng thay bằng `find()`.** Tìm chuỗi con ở bất kỳ đâu sẽ nhận cả
  `https://example.com/?redirect=your-scheme://attacker` - entry đó *chứa* scheme của bạn mà
  không *thuộc* scheme của bạn. Cắt nhãn rồi neo đầu là dạng an toàn cả hai chiều.

**Ba thứ được thêm chứ không mất đi:**

- Entry SAN của **mọi** scheme nay đến được tay bạn. Trước đây `spiffe://...` bị
  vứt, dù đó là chuẩn công nghiệp cho định danh workload và cert nào cũng hay có.
- Không còn phép kiểm độ dài âm thầm vứt giá trị. Trước đây một định danh sai độ
  dài trả về `None` **giống hệt** "cert không có entry nào", nên bên gọi không
  phân biệt được *"không có"* với *"có mà tôi bỏ"*.
- `PEER_SANS` **vắng mặt** khi cert không cấp SAN nào, chứ không phải có mặt với
  tuple rỗng. Câu *"lời gọi có qua mTLS không"* đã do `PEER_CN` trả lời.

⚠ Framework **không** thay bằng một khoá cấu hình cho scheme. Đó là lựa chọn có
chủ đích: không khai gì thì không có gì xảy ra, nên không tồn tại một mặc định lạ
nào để ai đó phải ngạc nhiên. Nơi triển khai nào cần quy ước riêng thì quy ước đó
sống ở nơi triển khai.

### Changed - khai báo phụ thuộc bắc cầu (2026-08-17)

Framework import thẳng ba thư viện mà `pyproject.toml` không khai; chúng về được
chỉ vì một thư viện đã khai kéo theo. Một phụ thuộc bắc cầu là lời hứa thư viện
kia đưa cho **chính nó**, không phải cho ta.

- **`starlette` không còn là phụ thuộc trực tiếp.** Bốn chỗ import đổi sang lấy
  từ `fastapi` (cùng một object, FastAPI xuất lại nguyên vẹn): `Request`,
  `JSONResponse`, `WebSocketDisconnect`, `CORSMiddleware`.
- **`paho-mqtt>=2.1` khai vào extra `mqtt`.** Không tránh được: `aiomqtt` 2.x
  không có lớp `Properties` riêng, mà MQTT v5 cần nó cho SubscriptionIdentifier
  và CorrelationData. Sàn 2.1 trùng khớp ràng buộc `aiomqtt` vốn đã đòi nên không
  siết thêm gì.
- **`botocore` khai vào extra `s3`, cố ý KHÔNG có phiên bản.** `aiobotocore` ghim
  botocore vào một dải ~16 bản patch và dải đó dịch theo mỗi bản mới của nó, nên
  mọi sàn ta viết hoặc vô nghĩa hôm nay hoặc thành xung đột resolver ngày mai.
- **`types-aiobotocore-s3` khai vào extra `dev`** (import dưới `TYPE_CHECKING`).

## [0.7.0] - 2026-07-30

**Fieldbus công nghiệp: adapter Modbus TCP và OPC UA.** Xime nhắm tới công
nghiệp / IIoT, và MQTT (0.5) chỉ nói chuyện được với thiết bị **đã biết nói
MQTT**. Máy móc thật trong nhà máy - PLC, biến tần, đồng hồ đo - nói hai giao
thức khác. Chủ dự án đã chốt **không dùng edge gateway**, nên hai adapter này
là con đường duy nhất tới tầng tiếp xúc.

Đây là **mô hình giao tiếp thứ ba** của framework: web/gRPC/socket là
request/response, MQTT là pub/sub, còn ở đây **framework là bên chủ động** đi
đọc thiết bị theo nhịp. Vì vậy có decorator riêng (`@poll`/`@on_change`) chứ
không tái dùng `@subscribe`.

Tương thích ngược hoàn toàn: không có gì thay đổi với ứng dụng không dùng hai
extra mới. Test: **1454 passed, 5 skipped** (+231 test so với 0.6.3).

Bản này cũng mang theo kết quả một đợt **kiểm toán toàn bộ mã nguồn trước khi
đẩy lên PyPI** - xem hai mục `Fixed` và `Changed` bên dưới. Mọi lỗi trong đó đều
được tái hiện bằng thực nghiệm trước khi vá, và đều có từ các bản **đã phát hành**
(0.6.3 trở về trước).

### Added

- **Adapter Modbus TCP** (`xime/adapters/modbus/`, extra `xime[modbus]`).

  - **Device Model khai báo** - trục chính của cả bản này. Modbus **không mang
    thông tin kiểu**: mỗi lần đọc chỉ trả về mảng word 16-bit thô, và việc ghép
    hai word thành `float32` (đúng thứ tự byte, đúng thứ tự word, đúng hệ số
    scale) là nguồn bug số một khi làm việc với PLC - sai bước nào cũng ra một
    con số trông rất hợp lý chứ không ra lỗi. `@device(unit=...)` +
    `Holding/Input/Coil/Discrete` khai kiến thức đó một lần, dùng cho cả bốn
    chiều: client đọc, client ghi, polling, và làm slave.
  - **Địa chỉ có hai đường vào tường minh, không bao giờ đoán**: `Holding(2)` là
    địa chỉ giao thức 0-based, `Holding(modicon=40003)` là số in trên datasheet.
    Nếu một tham số nhận nhập nhèm cả hai thì trên thiết bị có hơn 40002 thanh
    ghi, `Holding(40001)` sẽ đọc nhầm thanh ghi **mà không có lỗi nào báo**.
  - **Lập kế hoạch đọc theo `max_gap`** (`_planner.py`) - đây là chuyện **đúng
    sai**, không phải tối ưu: đọc một block lớn từ địa chỉ nhỏ nhất tới lớn nhất
    thì chỉ cần một địa chỉ ở giữa không tồn tại là slave trả
    `ILLEGAL DATA ADDRESS` và hỏng **cả** lần đọc, dù mọi field khai đều hợp lệ.
    Planner gom field gần nhau, tách field xa nhau, tự chia khi vượt trần giao
    thức (125 thanh ghi / 2000 bit), và nổ lúc startup nếu một field đơn lẻ lớn
    hơn trần đó.
  - **`@poll` / `@on_change`** + `ModbusAdapter`: một vòng lặp cho mỗi cặp
    `(model, interval)` nên hai handler cùng model, cùng nhịp không gây hai lần
    đọc; `@on_change` quan sát giá trị vòng poll đã lấy (bám vòng **nhanh
    nhất**) chứ không tự gửi lệnh; lần đọc đầu chỉ là **mốc** (bắn ở đó nghĩa là
    mọi handler kêu lúc khởi động - nhiễu, không phải tin tức); `deadband` lọc
    nhiễu đo cho giá trị analog; nhịp không trôi (trừ thời gian chu kỳ khỏi lần
    sleep sau); một chu kỳ lỗi được log rồi chạy tiếp.
  - **Chế độ slave** (`ModbusServerAdapter`, `@serve` / `@on_write`): mỗi
    `@device(unit=N)` là một `SimDevice` riêng nên một tiến trình đóng vai nhiều
    thiết bị sau một cổng. Giá trị **đẩy theo nhịp** (hỏi handler lúc master đọc
    sẽ để code nghiệp vụ chạy trong đường phản hồi giao thức), lệnh ghi tới qua
    **hook**. Địa chỉ ngoài vùng khai báo cố ý để trống -> master nhận
    `ILLEGAL DATA ADDRESS` thay vì một số 0 trông có vẻ hợp lệ.
  - **Thiết bị đánh địa chỉ bằng TÊN LOGIC** (`modbus.devices.<tên>`), đúng
    khuôn `client_id` của MQTT và `server_id` của gRPC/web.
  - Ba nhóm exception tách riêng vì cách phản ứng khác nhau:
    `ModbusConnectionError` (thử lại được) / `ModbusDeviceError` (thiết bị từ
    chối, thử lại vô ích - kèm diễn giải mã lỗi thành lời) / `ModbusCodecError`.

- **Adapter OPC UA** (`xime/adapters/opcua/`, extra `xime[opcua]`).

  - **Node Model** (`@node_model` + `Node("ns=2;s=Tank.Level")`) - ở đây model
    **không phải để giải mã** (OPC UA đã mang kiểu) mà để **đặt tên** cho
    NodeId. NodeId được kiểm dạng ngay lúc định nghĩa class.
  - **`OpcuaClient`**: `read` / `read_node` / `read_model` / `write` /
    `write_model`. `read_model` gộp mọi node vào **một** request - OPC UA round
    trip có độ trễ thật, đọc lẻ mười node là nhân độ trễ lên mười lần.
  - **`@on_node_change` + `OpcuaAdapter`**: subscription thật, không polling.
    Giá trị đầu tiên chỉ là **mốc** (mặc định `initial=False`) để giống hệt quy
    tắc `@on_change` của Modbus; `deadband` dùng chung một hàm so sánh với
    Modbus nên hai adapter hành xử giống nhau. Handler chạy trong task riêng vì
    `asyncua` giao thông báo qua callback **đồng bộ** - await thẳng trong đó sẽ
    chặn vòng nhận của thư viện.
  - **Bảo mật đủ ba mức** None / Sign / SignAndEncrypt (`Basic256Sha256`).
    Thiếu cert khi chọn Sign/SignAndEncrypt thì **nổ lúc startup**, không âm
    thầm tụt xuống kết nối không bảo vệ. Server đặt ở mức `Sign` vẫn nhận client
    mang `SignAndEncrypt`. Có **`application_uri`** cho cả client lẫn server: ở
    hai mức bảo mật này, server đối chiếu URI client khai lúc mở session với URI
    trong SubjectAltName của cert, mà `asyncua` để mặc định URI của chính nó và
    không tự đọc từ cert - thiếu tuỳ chọn này thì cert tự sinh gần như chắc chắn
    bị từ chối với `BadCertificateUriInvalid`, một thông báo không hề nhắc tới URI.
  - **Kiểu của node phía server suy từ annotation trong model.** Biến OPC UA lấy
    kiểu dữ liệu từ giá trị lúc tạo và về sau không nhận giá trị khác kiểu, nên
    `running: bool = Node(...)` phải tạo ra node kiểu Boolean chứ không phải
    Double. Không suy được kiểu và cũng không có `default=` thì **nổ lúc khởi
    động kèm tên node**, chứ không đoán rồi để lần đẩy đầu tiên chết lặng lẽ
    trong `BadTypeMismatch`.
  - **Chế độ server** (`OpcuaServerAdapter`, `@serve_nodes` / `@on_node_write`):
    cùng cách chia như server Modbus. Node có `@on_node_write` thì **client làm
    chủ giá trị**, vòng refresh không ghi đè - nếu ghi đè thì framework đá nhau
    với người vừa đặt giá trị và mọi thông báo ghi đều mơ hồ.

- **`encode_field(..., allow_read_only=True)`** trong codec Modbus: ở vai
  **slave**, input register và discrete input chính là thứ phải công bố, trong
  khi ở vai client thì tuyệt đối không được ghi. Cờ tường minh thay vì đổi tạm
  thuộc tính của field.

- **Tài liệu**: `docs/{vn,en}/modbus.md` và `docs/{vn,en}/opcua.md`.

### Fixed

Những lỗi dưới đây có từ các bản **đã phát hành** (0.6.3 trở về trước), tìm ra
trong đợt kiểm toán trước khi đẩy PyPI. Mỗi lỗi đều được tái hiện bằng thực
nghiệm trước khi vá, và đều có test canh.

- **Web app không cài extra `[jwt]` sập lúc khởi động** (có từ **0.2.0**, còn
  nguyên ở cả 10 bản đã lên PyPI). `WebAdapter` đọc registry JWT ở **mọi** lần
  khởi động chỉ để xem `configure_jwt()` có được gọi hay không, mà import
  submodule đó lại kéo theo `__init__` của package, vốn `import jwt` ở mức
  module. Hệ quả: `pip install xime[web]` rồi chạy một app **không hề đụng tới
  JWT** vẫn chết với `ModuleNotFoundError: No module named 'jwt'`. PyJWT nay
  được nạp lười (`starters/jwt/_pyjwt.py`); app thật sự gọi `configure_jwt()`
  thì adapter dò PyJWT **ngay lúc khởi động** chứ không đợi request đầu tiên
  mang token.

- **`Application.use()` chỉ chặn được trùng adapter ở ba trong sáu loại.** Chốt
  chặn đọc thuộc tính `_server_id`, mà `MqttAdapter` đặt tên định danh của mình
  là `_client_id` (Modbus/OPC UA mới thêm ở bản này cũng vậy). Đăng ký hai
  adapter cho cùng một `client_id` được chấp nhận im lặng - trong khi broker MQTT
  chỉ cho **một** phiên trên mỗi client id và đá phiên cũ ra, nên hai adapter
  đánh nhau trong vòng lặp reconnect. Cả sáu loại adapter nay đều được chặn.

- **Scheme `Bearer` nay không phân biệt hoa thường** (RFC 7235). Client gửi
  `bearer <token>` từng nhận 401 kèm thông báo "Missing authorization token" -
  nói header không có trong khi nó nằm ngay đó.

- **`__all__` không còn phá `mypy --strict` của người dùng.** Gói ship `py.typed`
  và khai classifier `Typing :: Typed`, nhưng `__all__` bị dùng để điều khiển DI
  scanner nên chính những dòng import mà tài liệu hướng dẫn lại bị báo "does not
  explicitly export attribute". Đã đánh dấu re-export theo chuẩn PEP 484 - cơ
  chế DI **không đổi một chút nào**.

- **Import thiếu extra nay nói rõ phải cài gì.** `xime.adapters.grpc`,
  `xime.starters.sqlalchemy` và `xime.starters.jwt` từng ném
  `ModuleNotFoundError` trần. Riêng `No module named 'jwt'` còn dẫn người dùng
  đi sai đường rất tệ: trên PyPI có một package tên đúng là `jwt`, khác hẳn
  PyJWT, nên `pip install jwt` cài nhầm thư viện rồi hỏng theo cách khó lần ra.

- **Tài liệu nêu API không tồn tại.** Toàn bộ mục JWT trong `docs/*/starters.md`
  mô tả một API khác hẳn thực tế (`JwtConfig`, `JwtSigner`, `JwtVerifier`,
  `configure_jwt_middleware` - không cái nào tồn tại), và bốn chỗ khác trỏ
  `xime.config` / `xime.lifecycle` / `xime.event` / `xime.context` thay vì
  `xime.core.*`. Đã viết lại theo API thật; nay **cả 343 dòng import trong toàn
  bộ tài liệu đều chạy được**, có script kiểm chứng.

- Lỗi lúc đóng socket server không còn bị nuốt im lặng (nay `logger.debug` kèm
  traceback), khớp với cách mọi adapter khác xử lý teardown.

### Changed

- **Tham số constructor có giá trị mặc định nay là tham số KHÔNG bắt buộc.**
  Container đọc mọi annotation là một dependency, nên trước đây một chữ ký hoàn
  toàn bình thường lại không đăng ký nổi:

  ```python
  class ModbusClient:
      def __init__(self, device: str = "default") -> None: ...

  dependency.register(ModbusClient)
  # cũ: UnregisteredDependencyException - Dependency: str
  # mới: OK, device = "default"
  ```

  Không thứ gì trong một DI container cấp `str` bao giờ, mà developer đã tuyên bố
  tham số đó không bắt buộc bằng cách cho nó giá trị mặc định. Tương đương
  `@Autowired(required=false)` của Spring. Áp cho cả tham số của factory method
  trong `dependency.configure(...)`.

  **Fail-fast vẫn nguyên ở chỗ quan trọng:** tham số **không** có mặc định mà
  thiếu implementation thì startup vẫn nổ - đó là đa số áp đảo dependency thật.
  **Đánh đổi đã cân nhắc:** tham số `Protocol` có mặc định mà thiếu binding giờ
  nhận mặc định thay vì nổ.

- **Thứ tự dựng singleton nay xác định giữa các lần chạy.** `DependencyGraph`
  duyệt theo thứ tự khai báo thay vì duyệt `set` của type - thứ tự duyệt `set`
  phụ thuộc `id()` nên đổi theo từng process, khiến thứ tự chạy `post_construct()`
  giữa các singleton **độc lập với nhau** đổi theo từng lần chạy. Order nào cũng
  hợp lệ, nhưng một bug phụ thuộc order sẽ chỉ tái hiện thỉnh thoảng.

- **Hai server adapter (Modbus, OPC UA) nay chặn trên số handler ghi chạy đồng
  thời** (`max_concurrency`, mặc định 16) và **từ chối `refresh <= 0`**. Master
  ghi nhanh hơn handler nói chuyện với database rất nhiều; trước đây mỗi lệnh ghi
  sinh một task không giới hạn. Phía master đã có chặn trên này từ đầu.

- **Extra `[web]` kéo thêm `python-multipart`.** Helper upload file có tài liệu
  (`save_upload`) cần nó, mà FastAPI chỉ đưa gói này vào extra `standard` của
  chính nó - `pip install xime[web]` không có, nên upload chết lúc chạy với
  "Form data requires python-multipart to be installed".

- **Floor dependency nay là con số đã cài thử, không phải phỏng đoán.**
  `fastapi>=0.110.1` (0.110.0 ghim starlette 0.36.3, `TestClient` của nó gọi
  `httpx.Client(app=...)` - đã bị xoá ở httpx 0.28, nên mọi test app tự viết cho
  route của mình đều chết `TypeError`), `pydantic>=2.5` (2.0-2.4 ra trước Python
  3.12, chính là mốc `requires-python` của Xime, nên không interpreter được hỗ
  trợ nào cài nổi), `pyyaml>=6.0.1` (6.0 không build được trên CPython hiện
  đại). Đã chạy **full suite với đúng bộ floor này**.

- **sdist chỉ còn mã nguồn và tài liệu**: 400 file / 620 KB xuống 230 file /
  354 KB. Trước đây gói phát hành nuốt cả `.claude/` (39 file tài liệu chiến
  lược nội bộ + đường dẫn máy cá nhân) và `tests_temp/` (130 file), vì hatchling
  mặc định đóng gói **mọi thứ không bị `.gitignore` che**. Nay khai whitelist
  neo vào gốc dự án, nên thư mục mới thêm vào repo mặc định nằm ngoài gói.

### Notes

Bốn chỗ API của `pymodbus` đã đổi so với thiết kế 2026-06-23, đều đã xác minh
trên `pymodbus 3.14.0` trước khi viết code (chi tiết:
`.claude/docs/ke-hoach-0.7.md`):

- `pymodbus.payload` (`BinaryPayloadDecoder`/`Builder`) **đã bị xóa** - thay
  bằng classmethod `ModbusClientMixin.convert_from_registers/to_registers`. Vì
  là classmethod nên codec **unit-test được hoàn toàn không cần network**.
- Tham số slave nay tên là **`device_id`** (keyword-only).
- `convert_*` chỉ có `word_order`, **không có `byte_order`** - Xime tự cài đặt
  phần hoán byte trong từng thanh ghi (`swap_bytes`).
- `ModbusServerContext`/`ModbusDeviceContext` **đã deprecated, sẽ xóa ở
  pymodbus v4** - phần slave viết thẳng theo `SimData`/`SimDevice` ngay từ đầu.
  `SimDevice.id` map đúng vào `unit_id`.

Với `asyncua`, framework đọc bằng `read_attributes()` chứ **không** dùng
`read_values()`: hàm sau vứt bỏ StatusCode của từng node, nên gõ sai một NodeId
trả về `None` **im lặng**, trông y hệt một node chưa có giá trị.

Floor phiên bản: `pymodbus>=3.14`, `asyncua>=2.0`. Classifier vẫn
`Development Status :: 3 - Alpha` (0.7 còn thêm tính năng lớn).

## [0.6.3] - 2026-07-29

Bản vá tương thích ngược hoàn toàn, tập trung **gỡ chặn cho các app đang chạy
trên platform**. Ba việc chính: **`PEER_APP_ID`** (cert mTLS của tiến trình
thuộc một app nay mang định danh app trong SAN, framework đọc ra và đặt vào
`request_context` để service phía sau phân giải được Subject loại APPLICATION),
**TLS cho web adapter** (platform cố ý không có gateway, không có nó thì app
Python không phục vụ được Internet) và **khối chỉ đọc `read_only()`** (usecase
không ghi thôi phải bọc transaction). Kèm hai điểm hardening ghi nhận từ kiểm
toán 0.6 và vá metadata gói. Test: **1223 passed, 5 skipped** (+98 test so với
0.6.2; skip thứ 5 là ca phân quyền file chỉ chạy trên POSIX).

### Added

- **Khối chỉ đọc `read_only()`** - trước bản này mọi truy cập database, kể cả một
  câu `SELECT`, đều phải nằm trong `async with self.transaction():` vì
  `AsyncSessionFactory.current()` ném `RuntimeError` khi ngoài transaction. Hệ quả
  là service chỉ đọc vẫn phải nhận `TransactionManager`, và `async with
  self.transaction():` xuất hiện dày đến mức không còn mang thông tin gì - nhìn nó
  không biết được chỗ nào thật sự có ghi.
- **`ReadOnlyManager` / `ReadOnlyContext`** (`core/transaction/readonly.py`,
  export ở `xime.core.transaction`) - Protocol cho khối chỉ đọc, **cùng cấp** với
  `TransactionManager` chứ không phải method của nó:

  ```python
  async with self.read_only():
      product = await self.products.find_or_fail(product_id)
  ```

  Tách thành binding riêng để về sau trỏ đường đọc sang **read replica** / mức
  isolation khác / decorator cache chỉ bằng một dòng `bind`, không sửa code
  nghiệp vụ. Là method của `TransactionManager` thì nó dính chặt vào engine của
  đường ghi.
- **`SqlAlchemyReadOnlyManager` / `SqlAlchemyReadOnlyContext`**
  (`starters/sqlalchemy/readonly.py`) - implementation, bind cạnh
  `TransactionManager`. Bốn đặc điểm:
  - **Không bao giờ commit.** Thoát khối là hủy, dù thành công hay lỗi. Nên lỡ
    sửa entity trong khối chỉ đọc thì thay đổi không xuống được database. Framework
    **không báo lỗi** ca này - xem mục Ranh giới bên dưới.
  - **Lồng nhau thì mượn session đang chạy** và thoát ra không làm gì. Nhờ vậy một
    service chỉ đọc ghép được vào usecase có ghi mà không mở connection thứ hai,
    và không đóng nhầm session của transaction bao ngoài.
  - **`expunge_all()` trước `rollback()`** để entity còn dùng được sau khi ra khỏi
    khối. Rollback làm expire mọi object trong session, đọc thuộc tính sau đó sẽ
    ném `DetachedInstanceError` - kiểm chứng bằng cách xóa đúng dòng đó, hai test
    chuyển đỏ. Quan hệ chưa eager-load thì vẫn lỗi, y như async SQLAlchemy thường.
  - **Không gọi `begin()` tường minh**, để SQLAlchemy autobegin: khối không đọc gì
    thì không lấy connection nào khỏi pool (đo bằng `pool.checkedout()` trong test).
  - **Ranh giới đã chốt:** framework **không chặn** việc sửa entity đọc được từ
    khối chỉ đọc - thay đổi bị bỏ đi im lặng, không lỗi, không log. Chặn được thì
    phải hook SQLAlchemy event và trả phí runtime cho mọi lời đọc, trái nguyên tắc
    minimal magic; bù bằng quy tắc tài liệu (entity đọc trong `read_only()` chỉ để
    **trả về hoặc render**, muốn sửa thì mở `transaction()` và **load lại**).
  - **Tương thích ngược:** đường transaction cũ không đổi một dòng nào; chỗ duy
    nhất bị nới là `AsyncSessionFactory.current()` (nay khối chỉ đọc cũng đặt được
    session vào ContextVar), còn `RuntimeError` khi gọi repository ngoài mọi khối
    thì giữ nguyên. App không bind `ReadOnlyManager` chạy y như cũ - có test boot
    `Application` thật cho cả hai trường hợp.
- **`FakeReadOnlyManager`** (`xime.testing`) - bản no-op đối xứng với
  `FakeTransactionManager`, cho test không cần database.

- **TLS/HTTPS cho web adapter** - trước bản này `uvicorn.Config` được dựng không
  tham số ssl nào nên mọi app Xime chỉ chạy HTTP thuần. Kiến trúc platform cố ý
  không có gateway/reverse proxy, mỗi service tự kết thúc TLS.
  - **`ServerTlsConfig`** (`core/config/runtime.py`, export ở `xime.core.config`
    và `xime.adapters.web`) - khối `server.ssl` trong `application.yml`:
    `certfile`, `keyfile`, `keyfile_password`, `ca_certs`, `cert_reqs`,
    `ciphers`. **Để trống = HTTP thuần, hành vi cũ y nguyên.**
  - **`cert_reqs` dùng chữ** (`"none"` / `"optional"` / `"required"`) thay vì số
    `ssl.CERT_*`: operator đọc `cert_reqs: required` trong YAML là hiểu, đọc
    `cert_reqs: 2` thì không. Framework map sang hằng stdlib; sai chính tả bị
    Pydantic từ chối ngay.
  - **Fail-fast khi cấu hình sai.** uvicorn báo lỗi không thể debug cho cert khai
    nửa vời: thiếu `keyfile` ra `SSLError: [SSL] PEM lib`, thiếu `certfile` ra
    `AssertionError` **rỗng message**. Nay `_tls_kwargs()` kiểm trước và ném
    `StartupException` nêu key + đường dẫn + `server_id`: khai một nửa, file
    không tồn tại, không phải file thường, hoặc **tồn tại mà không đọc được**
    (certbot ghi `privkey.pem` chỉ cho root - lỗi hay gặp nhất khi triển khai).
    Không bao giờ im lặng rơi về HTTP: server tưởng HTTPS mà thật ra HTTP là lỗ
    hổng bảo mật.
  - **Chỉ forward option thực sự được cấu hình.** uvicorn đặt mặc định
    `ssl_cert_reqs = CERT_NONE` và `ssl_ciphers` là chuỗi khác rỗng, nên truyền
    `None` không phải "dùng mặc định" mà ghi đè mất (kiểm chứng:
    `ssl_cert_reqs=None` ném `ValueError: None is not a valid VerifyMode`).
  - **Multi-server: `WebAdapter(..., ssl=ServerTlsConfig(...))`**, để trống thì
    **kế thừa `server.ssl`**. Kế thừa là có chủ đích - server phụ âm thầm chạy
    HTTP khi server chính đã HTTPS là lỗ hổng không ai để ý; muốn tắt thì truyền
    `ssl=ServerTlsConfig()` tường minh.
  - Cert phải là cert **CA công cộng** (certbot...). Cert do CA nội bộ Trust cấp
    là để service nhận diện nhau qua mTLS, trình duyệt không tin.
  - Test `tests_temp/web/test_tls.py` (29 pass + 1 skip), gồm một ca **gọi HTTPS
    thật** vào uvicorn đang chạy với client tin đúng cert tự ký. Thiết kế, phần
    đã bỏ và hướng nâng cấp: `.claude/docs/tls-cho-web-adapter.md`.

- **`PEER_APP_ID` - định danh APPLICATION đọc từ SAN của client cert.** Một app
  có nhiều tiến trình, mỗi tiến trình một cert riêng (CN riêng) nhưng chung một
  định danh app; cert mang định danh đó dưới dạng SAN URI `xime-app://<Base62 33
  ký tự>`. Framework nay trích ra và lưu cạnh `PEER_CN`:
  - **`current_app_id()`** (`core/security/peer.py`) - trả định danh app của
    caller hoặc `None`, đối xứng `current_caller()`. Export ở `xime.core.security`
    cùng hằng `PEER_APP_ID`.
  - **`_read_peer_app_id()`** (`adapters/grpc/interceptors/_context.py`) - đọc
    property `x509_subject_alternative_name` của `auth_context()`. Khác CN, SAN
    là property **nhiều giá trị** (cert thường còn mang DNS, IP, spiffe) nên
    duyệt mọi entry, bỏ qua entry không liên quan. Chấp nhận cả URI trần lẫn dạng
    có tiền tố loại (`URI:xime-app://...`) bằng cách tìm chuỗi con thay vì so đầu
    chuỗi. Lưu **phần sau scheme** - đúng dạng platform dùng ở REST path và JWT
    `sub`, consumer không phải tự cắt.
  - **Fail-soft tuyệt đối** như `PEER_CN`: không mTLS, thiếu entry, giá trị không
    decode được UTF-8, hay định danh sai độ dài đều trả `None` chứ không ném. Một
    cert lạ không bao giờ được phép làm hỏng request. Entry hỏng bị bỏ qua chứ
    không che mất entry hợp lệ đứng sau.
  - **Ranh giới giữ nguyên:** framework chỉ cấp sự thật thô, không giải mã Base62,
    không kiểm app có tồn tại, không kiểm quyền - authorization vẫn ở ứng dụng.
  - `_set_peer_cn` đổi tên thành `_set_peer_identity` (hàm nội bộ) và set cả hai
    key trong một chỗ, nên hai đường gọi unary/streaming không phải sửa riêng.
    **Hành vi `PEER_CN` không đổi** - có service đang dựa vào nó.

### Fixed

- **Cờ `xime.di.dynamic-binding` ép kiểu chặt** (B1, ghi nhận khi kiểm toán 0.6).
  Trước đây đọc bằng `bool(runtime.get(...))`, trong khi mọi cờ khác đi qua model
  Pydantic. Hệ quả: operator viết `dynamic-binding: "false"` (chuỗi có nháy trong
  YAML) sẽ **bật nhầm** tính năng, vì `bool("false")` là `True`. Thêm
  **`RuntimeConfig.get_bool(key, default)`** dùng lại chính bộ parse boolean của
  Pydantic (`true/false`, `yes/no`, `on/off`, `1/0`, không phân biệt hoa thường)
  và ném `StartupException` nêu rõ key + giá trị khi gặp thứ không phải boolean -
  cờ sai phải nổ lúc startup, không hành xử tuỳ tiện về sau. `get()` giữ nguyên
  hành vi trả giá trị thô.
- **Metadata gói `pyproject.toml`**: thêm classifier `Typing :: Typed` (repo vẫn
  ship `xime/py.typed` mà chưa khai báo) và chuyển license sang PEP 639
  (`license = "MIT"` + `license-files`, thay dạng bảng `{ file = "LICENSE" }`) để
  PyPI hiện tag license. Kèm `requires = ["hatchling>=1.27"]` vì bản cũ hơn không
  hiểu metadata PEP 639. Wheel dựng thử xác nhận `License-Expression: MIT` +
  `License-File: LICENSE`.

### Documentation

- **Caveat thứ tự `post_construct` của `DynamicProxy`** (B2, ghi nhận khi kiểm
  toán 0.6). Khi bật dynamic binding, consumer phụ thuộc proxy chứ không phụ thuộc
  impl, nên dependency graph không có cạnh consumer -> impl và thứ tự
  `post_construct` giữa hai bên là không xác định. Mọi `post_construct` vẫn chạy
  đủ lúc startup nên request sau đó không ảnh hưởng; rủi ro duy nhất là consumer
  gọi vào impl ngay trong `post_construct` của chính nó. Đã ghi vào docstring kèm
  hướng xử lý (làm lười lúc dùng lần đầu). Không đổi code.
- **Tài liệu transaction viết lại** (`docs/{vn,en}/transaction.md`,
  `.claude/rules/transaction.md`) - mục "API tương lai" trước đây hứa
  `transaction.read_only()`; nay đã hiện thực nhưng **dưới dạng manager riêng cùng
  cấp**, các mục đó được sửa cho khớp và bổ sung phần cảnh báo "đọc ngoài
  transaction thì đừng sửa".

## [0.6.2] - 2026-06-30

Thêm **starter `mail`** - gửi email qua SMTP theo đúng khuôn mẫu starter sẵn có
(`storage`/`cache`): một Protocol `MailService` + backend `SmtpMailService`, app
bind trong `config/dependency.py`. Tương thích ngược hoàn toàn. Test starter:
17 passed.

### Added

- **Starter `mail` (`xime.starters.mail`)** - gửi email bất đồng bộ qua SMTP:
  - **`MailService` (Protocol)** - contract trung lập: `async def send(message:
    EmailMessage) -> None`. Logic đồng bộ (await tới khi gửi xong, thành công ->
    return, thất bại -> raise `MailSendError`, có timeout nội bộ) - dùng cho email
    bảo mật (OTP, reset mật khẩu). Gửi nền là việc của app (tự bọc
    `asyncio.create_task(...)`), starter không ôm hàng đợi.
  - **`SmtpMailService` (backend)** - hiện thực qua **`aiosmtplib`** (async, không
    chặn event loop; extra `xime[mail]`, import lười). Đọc `mail.from` và
    `mail.smtp.*` (`host` bắt buộc -> `ValueError` fail-fast; `port` mặc định 587,
    `timeout` 10s, `use_tls` true) từ `RuntimeConfig`. Mỗi `send()` mở một kết nối
    SMTP mới rồi đóng (bền hơn pool cho lượng email giao dịch/OTP). Tự chọn
    STARTTLS (587) hoặc TLS ngầm (465) theo cổng.
  - **`EmailMessage`** - value object `@dataclass(frozen=True, slots=True)`: `to`,
    `subject`, `html`, `text`, `cc`, `reply_to`, `sender` (override `mail.from`).
    Validate lúc tạo: `to` không rỗng và có ít nhất một trong `html`/`text`. Có cả
    hai -> `multipart/alternative`.
  - **Exception** `MailError` (base) + `MailSendError` (gửi thất bại: SMTP từ
    chối, timeout, mất kết nối; giữ lỗi gốc ở `__cause__`) - mẫu
    `storage._exceptions`.
  - Dùng: `dependency.scan("xime.starters.mail")` +
    `dependency.bind({ MailService: SmtpMailService })`.

### Fixed

Hardening sau kiểm toán toàn diện 0.6.2 (chi tiết: `.claude/docs/kiem-toan-0.6.md`).
Không có lỗi gãy chức năng; toàn bộ là nhất quán / hardening nhỏ. Test: 1125 passed,
4 skipped.

- **`EmailMessage.to`/`cc` thật sự bất biến**: `__post_init__` snapshot sang
  `tuple` nên mutate list gốc của caller không ảnh hưởng message frozen (trước
  đây `frozen=True` chỉ chặn gán lại, không chặn `msg.to.append(...)`).
- **Mail SMTP `username`/`password` dùng `is not None`** thay falsy-check: chuỗi
  rỗng cấu hình tường minh vẫn truyền tới server; chỉ giá trị thật sự vắng mới bỏ
  qua xác thực.
- **Version fallback đồng bộ**: `xime.__version__` fallback `0.6.1` -> `0.6.2`;
  generator SDK gRPC (`_codegen.py`) nay ủy quyền `xime.__version__` để chỉ còn
  một literal version duy nhất (trước trả lệch `"0.5.0"`).
- **Error message middleware marker sang tiếng Anh** cho nhất quán; xóa sentinel
  `_NO_DEFAULT` thừa; bỏ tạo `DynamicProxy` thừa khi interface đã có override.

## [0.6.1] - 2026-06-29

Bản vá nhỏ cho web adapter: middleware tự viết lấy được dependency từ DI container
và runtime config qua marker, nên **app không phải subclass `WebAdapter`** nữa;
thêm helper CORS hạng nhất. Bổ sung `CrudRepository` cho starter SQLAlchemy để app
hết phải tự viết base repository. Tương thích ngược hoàn toàn, không đổi API cũ.
Toàn bộ test: 1101 passed, 4 skipped.

### Added

- **`CrudRepository[T]` (starter SQLAlchemy)** - lớp repository nền generic cho
  sẵn CRUD chung như `JpaRepository`/`CrudRepository` của Spring Data:
  `find` · `find_or_fail` · `find_all` · `exists` · `count` · `save` · `save_all`
  · `delete`. App chỉ cần `class CategoryRepository(CrudRepository[Category]):
  model = Category` rồi viết thêm query đặc thù bằng `select()` - hết lặp lại
  `BaseRepository` ở mỗi dự án. `model` khai báo dạng abstract property nên chính
  `CrudRepository` là abstract (`inspect.isabstract` = True) -> DI scanner bỏ qua
  lớp nền; chỉ subclass concrete (đã set `model`) mới thành singleton, không sinh
  singleton thừa. Mọi method đọc session đang hoạt động qua `AsyncSessionFactory`
  nên phải gọi trong `async with self.transaction():`. `find_or_fail` ném
  `EntityNotFoundError` (lỗi runtime cục bộ của starter) khi không có bản ghi.
- **Middleware lấy dependency từ DI / runtime config (web adapter)** - hai marker
  `Inject(SomeType)` và `FromConfig("a.b", default)` dùng làm giá trị option khi
  gọi `configure_middleware(...)`. Framework phân giải marker lúc `build_app`
  (sau khi DI container đã dựng): `Inject` lấy singleton từ container,
  `FromConfig` đọc `RuntimeConfig` theo dot-notation (thiếu thì về default). Nhờ
  vậy middleware tự viết (vd JWT middleware cần auth/user/blacklist service) khai
  báo gọn trong `config/web.py`, **không phải subclass `WebAdapter`** để tự gọi
  `xime_app.get(...)`. Giá trị không phải marker giữ nguyên (tương thích ngược).
- **`configure_cors(...)`** - helper hạng nhất bật CORS cho web adapter theo
  pattern `configure_*`. Tham số để trống tự đọc từ `RuntimeConfig` khóa
  `cors.<tên>` (qua `FromConfig`), thiếu nốt thì về mặc định Starlette - Operator
  chỉnh CORS qua `application.yml` mà không đụng code. CORS đăng ký như user
  middleware nên nằm ngoài JwtAuth (preflight OPTIONS xử lý trước xác thực).

## [0.6.0] - 2026-06-23

Bản DI: **tự viết lớp lưu/dựng singleton** (gỡ hẳn thư viện `dependency-injector`)
và **dynamic interface binding** (một interface bind nhiều implementation, đổi
được lúc runtime). Không đổi API người dùng đang dùng; dự án cũ chạy nguyên không
phải sửa. Toàn bộ test: 1084 passed, 4 skipped.

### Added

- **Dynamic interface binding** - `bind` nay chấp nhận value là **tuple nhiều
  implementation** (phần tử đầu = mặc định) bên cạnh value một class như cũ.
  Bật/tắt bằng cờ runtime `xime.di.dynamic-binding` trong `application.yml` (mặc
  định **tắt**). Khi tắt, tuple hành xử y hệt bind phần tử đầu (impl phụ không
  dựng) - bằng đúng kiến trúc cũ. Khi bật: mọi impl là singleton eager (chạy
  `PostConstruct`/`PreDestroy`), consumer nhận một **proxy trong suốt**
  (`DynamicProxy`) nên giữ nguyên code, và một **`Switcher`** (inject được) đổi
  implementation **toàn cục** lúc runtime qua `use(Interface, Impl)` /
  `reset(Interface)` / `reset()`. Validate fail-fast: mọi impl trong tuple phải
  thỏa Protocol. `Switcher` luôn inject được; khi cờ tắt, `use/reset` báo lỗi rõ.

### Changed

- **Gỡ phụ thuộc `dependency-injector`** - lớp lưu/dựng singleton ở
  `core/container/registry.py` viết lại bằng dict thuần (key là chính class) +
  `RLock` double-checked locking. API public (`XimeContainer`,
  `DependencyRegistry.register/get`) không đổi. Lý do: Xime eager-build mọi
  singleton lúc startup rồi giữ reference qua constructor injection, không gọi
  provider mỗi request - nên ưu thế Cython của thư viện không phát huy, trong khi
  vẫn tốn phí sinh tên (md5 + regex) mỗi class và một lớp gián tiếp mỗi `get()`.
  Bản tự viết bỏ cả hai: `get()` warm là đúng một `dict.get`, lock chỉ chạm khi
  cache miss (gần như chỉ lúc startup). Benchmark đối chiếu: build ~8x, warm
  `get()` ~2x nhanh hơn backend cũ. Đã gỡ `dependency-injector` khỏi
  `pyproject.toml` - Xime không còn phụ thuộc thư viện DI bên thứ ba nào.
- Bump version `0.5.0` -> `0.6.0`.

## [0.5.0] - 2026-06-22

Bản kiểm toán toàn diện + hai mảng tính năng mới: **adapter MQTT** (messaging/IoT)
và **làm việc với file** (storage starter + streaming web). Toàn bộ test: 1051
passed, 4 skipped (2 skip là test tích hợp MQTT/S3 - chạy khi có broker/MinIO).
Chi tiết kiểm toán: `.claude/docs/kiem-toan-0.5.md`.

### Added

- **Adapter MQTT** (`pip install xime[mqtt]`, `aiomqtt` import lười): pub/sub
  một chiều (`@subscribe`) + **RPC over MQTT v5** (`@rpc`, qua `ResponseTopic` +
  `CorrelationData`). `MqttPublisher` (DI singleton) để publish; auto-reconnect +
  re-subscribe; xử lý message giới hạn đồng thời (`max_concurrency`, backpressure);
  định tuyến bằng **MQTT v5 Subscription Identifier** để filter chồng lấn không
  double-dispatch; teardown `request_context`/`clear_security()` nhất quán mọi adapter.
- **Starter `storage`** (Protocol `StorageService`): hai dạng truy cập song song
  - `put`/`get` (bytes) cho object nhỏ và `put_stream`/`open_stream` (stream) cho
  object lớn; `delete`/`exists`/`stat`/`url`. Value là bytes thô, framework không
  áp đặt định dạng. Key được chuẩn hóa chung (từ chối rỗng/tuyệt đối/`..`) cho mọi
  backend.
- **Backend `localfs`** (`LocalFileStorage`): lưu file dưới `storage.local.root`,
  chống path traversal 3 lớp, ghi nguyên tử (`.part` + `os.replace`), stream qua
  `asyncio.to_thread` (không cần `aiofiles`).
- **Backend `s3`** (`pip install xime[s3]`, `aioboto3` import lười): `S3ClientProvider`
  (vòng đời client ở `post_construct`/`pre_destroy`) + `S3FileStorage` (multipart
  upload, ranged GET, presigned `url()`); tương thích MinIO (`addressing_style`).
- **Streaming file ở web adapter** (`xime.adapters.web.files`): `stream_object`
  (HTTP Range 200/206/416, `Content-Range`, `ETag`, đọc lười không nạp hết RAM) và
  `save_upload` (đọc `UploadFile` theo chunk -> `put_stream`, giới hạn `max_bytes`
  -> 413).
- **JWT `audience`/`issuer`** (`JwtMiddlewareConfig`): ép khớp `aud`/`iss` khi cấu
  hình; middleware phơi toàn bộ claim qua `request_context[JWT_CLAIMS]` để app
  authorize tiếp.

### Fixed

- **Context bleeding ở web HTTP middleware** (dental-clinic #001): chuyển
  `RequestContextMiddleware` và `JwtAuthMiddleware` từ `BaseHTTPMiddleware` sang
  **pure-ASGI middleware** -> set/clear `ContextVar` cùng context với handler, hết
  rò identity giữa các request.
- **JWT từ chối token có claim `aud`**: trước đây `jwt.decode` không truyền
  `audience` khiến PyJWT reject mọi token mang `aud` (401). Nay đặt
  `verify_aud=False` khi chưa cấu hình audience và ép khớp khi có.
- **`MqttPublisher` treo vô hạn** khi không adapter nào phục vụ client_id: nay
  fail-fast `RuntimeError` rõ ràng.
- **HTTP Range sai cú pháp trả 416**: nay bỏ qua header rác và phục vụ full 200
  (đúng RFC 7233); chỉ 416 cho range hợp lệ-nhưng-không-thoả.
- **Scanner nuốt lỗi import thật của submodule**: nay re-raise lỗi import thật
  (thiếu dependency, circular...), chỉ bỏ qua khi module thực sự vắng.
- **`get_protocol_methods` bỏ dunder**: nay giữ dunder mang ý nghĩa contract
  (`__call__`, `__aenter__`, `__aexit__`...) để binding validation đầy đủ hơn.
- **MQTT `#`/`+` cấp đầu khớp `$SYS`**: nay không khớp topic hệ thống `$...`.
- **Socket `STREAM_START` payload hỏng làm rớt connection**: nay gửi frame ERROR.
- **`XimeGrpcChannel` task đóng channel nền có thể bị GC**: nay giữ strong-ref.
- **OpenAPI `public_paths` không chuẩn hóa trailing slash** như JWT middleware:
  nay đồng nhất.
- **MQTT RPC: lỗi gửi reply che lỗi gốc**: nay reply lỗi là best-effort, luôn
  giữ lỗi nghiệp vụ gốc trong log.

### Changed

- **`scheduler` extra**: `apscheduler>=3.6` -> `apscheduler>=4.0.0a6` cho khớp code
  dùng API v4 (`AsyncScheduler`/`run_until_stopped`/`add_schedule`); `>=3.6` cho
  phép cài 3.x stable thiếu API v4 -> `ImportError` lúc chạy.
- Thêm extra `s3`, `mqtt`; gộp vào `all`.
- Bump version `0.4.0` -> `0.5.0`.

## [0.4.0] - 2026-06-20

Bản cross-cutting + starters: thêm danh tính peer mTLS cho gRPC và hai starter
còn thiếu (`cache`, `redis`). Không đụng lõi DI. Toàn bộ test: 929 passed,
2 skipped.

### Added

- **Danh tính peer mTLS cho gRPC -> request_context**: `RequestContextInterceptor`
  nay đọc Common Name của client certificate đã verify (qua `auth_context()`) và
  lưu vào `request_context` dưới key trung tính `peer_cn`. **Fail-soft**: không
  mTLS / không có CN / lỗi đọc -> không set key, request vẫn chạy. Thêm helper
  `current_caller()` (`xime.core.security`) trả CN thô; authorization vẫn ở app.
- **Starter `cache`**: Protocol `CacheService` (`get`/`set`/`delete`/`exists`),
  value là `bytes` thô (framework không áp đặt serialize), TTL theo giây,
  `None` = không hết hạn. Tách hoàn toàn khỏi backend.
- **Starter `redis`** (`pip install xime[redis]`): `RedisClientProvider` (đọc
  `redis.url` + `redis.max_connections` từ `application.yml`, `pre_destroy` đóng
  connection pool) và `RedisCacheService` (implement `CacheService`). `redis`
  được import lười để module vẫn import được khi chưa cài extra.

### Changed

- Bump version `0.3.0` -> `0.4.0`.

## [0.3.0] - 2026-06-19

Bản hardening: vá bug đã xác nhận, tăng an toàn mặc định và khép kín mảng gRPC
client. Không thêm tính năng lớn. Toàn bộ test: 899 passed, 2 skipped.

### Added

- **Retry policy cho gRPC client (`grpc.clients.<id>.retry`)**: `GrpcRetryConfig`
  với `enabled` / `max_attempts` / `initial_backoff_ms` / `max_backoff_ms` /
  `backoff_multiplier` / `retryable_status`. Tắt mặc định; chỉ retry call UNARY
  (stream không replay được an toàn); mặc định chỉ retry `UNAVAILABLE`; backoff
  mũ có cap; mỗi lần thử có deadline riêng.
- **`tls.server_id` cho gRPC client**: chọn certificate provider theo `server_id`
  trong thiết lập multi-server (mặc định `"default"`).

### Fixed

- **gRPC client cert rotation không thread-safe** (backlog #7): thêm
  `threading.Lock` quanh đoạn check-and-replace trong
  `XimeGrpcChannel._dynamic_channel()` để hai luồng song song không cùng dựng
  channel rồi rò một cái.
- **`wire_dynamic_certificates()` hardcode `server_id="default"`** (backlog #8):
  giờ tra provider theo `server_id` của từng channel.
- **Endpoint gRPC code-first viết `def` thay vì `async def`** (backlog #9): nay
  fail fast bằng `StartupException` lúc startup (kể cả `async def` có `yield`),
  thay vì crash `TypeError` lúc RPC đầu tiên.
- **Interceptor lỗi gRPC abort hai lần** (notification/data note #2): re-raise
  `grpc.aio.AbortError` như terminal để không abort lần hai khi interceptor/
  handler bên trong đã abort.
- **Interceptor lỗi để lộ `str(exc)` ra client** (notification/data note #1a):
  lỗi chưa map nay trả message chung `"Internal server error"`; lỗi đã map vẫn
  giữ message có chủ đích.

### Changed

- Bump version `0.2.0` -> `0.3.0`.

## [0.2.0] - 2026-06-14

Bản hoàn thiện đầu tiên: core (DI / lifecycle / config / context / event bus /
security / transaction), các adapter (web, gRPC code-first + client SDK + mTLS
động, socket) và các starter (sqlalchemy, jwt, scheduler).

[0.6.1]: https://github.com/nguyen-huu-thang/xime-framework/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/nguyen-huu-thang/xime-framework/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/nguyen-huu-thang/xime-framework/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/nguyen-huu-thang/xime-framework/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/nguyen-huu-thang/xime-framework/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/nguyen-huu-thang/xime-framework/releases/tag/v0.2.0
