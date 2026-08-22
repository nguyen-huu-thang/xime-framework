# Bàn giao cho phiên Windows: nhận kết quả đo uvloop 0.8.1 từ Linux

> | | |
> |---|---|
> | **Trạng thái** | **ĐANG DÙNG** - viết 2026-08-22, chờ phiên Windows nhận |
> | **Thuộc bản** | `0.8.1` (uvloop) |
> | **Thay cái gì** | Là **chiều về** của [`ban-giao-cho-phien-linux-0.8.1.md`](ban-giao-cho-phien-linux-0.8.1.md). Không thay file nào |
> | **Bị thay bởi** | Khi `0.8.1` phát hành xong |
>
> Viết bởi phiên Linux, cho một phiên Windows **chưa từng chạy ở đây, không có bộ
> nhớ, không có lịch sử cuộc trò chuyện**. Cùng một máy, chỉ khác hệ điều hành.
>
> Đọc hết mục 0 trước khi gõ lệnh đầu tiên. Nó ngắn.

## 0. Sáu thứ phải biết trước

| # | |
|---|---|
| 1 | **Đề bài của chuyến này đã làm xong.** Bốn phép đo bắt buộc: ba ĐẠT, phép thứ tư ra một kết quả **đi ngược giả định của chính bản 0.8.1** - xem mục 4 |
| 2 | **Sửa HAI file, cả hai là file test.** Không đụng một dòng mã sản phẩm nào. ⚠ Bản đầu của file này khai *một* - đính chính ở [`kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](../kiem-toan/0.8.1-ket-qua-do-tren-linux.md) mục 6 |
| 3 | ⛔ **KHÔNG đề nghị rollback uvloop.** Khuyến nghị là **GIỮ**, kèm lý do đo được - mục 4.4 |
| 4 | ⭐ **Chuyến này đẻ thêm một thứ ngoài đề bài: framework nay CÓ bộ benchmark.** Chủ dự án yêu cầu giữa chuyến. Xem mục 5 |
| 5 | **Kỳ vọng bộ test KHÁC NHAU theo hệ điều hành**, tiêu chí đạt là **TỔNG 2558**, không phải `passed` - mục 3 |
| 6 | ⛔ **Chủ dự án tự commit, tự tag, tự đẩy PyPI.** Phiên này chuẩn bị tới sát mép rồi dừng |

---

## 1. Nhận mã về

### Hai commit, và vì sao phải là hai

Thư mục Linux được commit thành **hai** commit liền nhau, cố ý:

```text
bd9420d  Nhận bản 0.8.1 từ Windows: uvloop + cảnh báo thiếu thư viện WebSocket
<sau đó>  Đo uvloop trên Linux: ba phép đo đạt, hai test lỗi thời, thêm bộ benchmark
```

Hash của commit thứ hai lấy bằng `git log --oneline -2` - nó là commit **mới
nhất**, ngay trên `bd9420d`.

| Commit | Chứa gì |
|---|---|
| **thứ nhất** | **Đúng bằng thư mục Windows lúc chép**, không thêm không bớt. Nó tồn tại để làm mốc |
| **thứ hai** | **Toàn bộ phần Linux làm thêm.** Đây là commit duy nhất phiên Windows cần soát |

> **`git show HEAD --stat` là danh sách đầy đủ và duy nhất của những gì Linux
> đã làm.** Không phải đọc `git diff` giữa hai repo, không phải đoán file nào từ
> đâu ra - đó chính là lý do tách hai commit.

⚠ Hai repo có **lịch sử git rời nhau** (thư mục Linux là bản chép, không phải
clone). Nên **đừng `git pull`/`git merge`** giữa chúng; cách chuyển vẫn là **chép
đè** như đợt 0.8.0.

### Cạm bẫy khi chép NGƯỢC (Linux -> Windows)

Đợt đi (Windows -> Linux) đã vấp hai thứ, đều do phân vùng NTFS:

| | |
|---|---|
| **Quyền file** | Ổ NTFS mount trên Linux gán **exec bit cho mọi file**. Chép bằng `tar` giữ nguyên nó, và git bên Linux thấy **627 file "thay đổi" mà không có một dòng nội dung nào** (`mode 100644 => 100755`). Chép ngược về Windows thì NTFS bỏ qua quyền POSIX nên **chiều này không dính** |
| **CRLF** | ~300 file `.py` bên này là CRLF, và đó là **trạng thái vốn có** (HEAD Linux trước khi chép đã có 299 file như vậy), **không phải do lần chép sinh ra**. Python trên Linux chạy CRLF bình thường |

⚠ `.gitattributes` bên Windows hiện **rỗng**. Đó là lý do `git status` bên đó
hiện 359 file `M` mà phần lớn chỉ là lật line-ending. Không phải việc của bản
0.8.1, nhưng nó làm `git status` bên Windows khó đọc - biết trước thì đỡ mất thời
gian đi tìm.

---

## 2. Danh sách chính xác những gì Linux đã làm

### 2.1. Sửa code: hai file, cả hai là test

`tests_temp/processes/test_inherited_socket.py` - hàm `test_linux_never_switches`, và
`tests_temp/grpc/test_scanner.py` - hàm `test_fails_fast_on_first_bad_package`
(chi tiết ở mục 6b của báo cáo). Dưới đây nói về cái thứ nhất.

```python
# TRƯỚC (0.8.0, đỏ ngay lần đầu chạy trên Linux)
monkeypatch.setattr(sys, "platform", "linux")
assert worker_loop_factory({("web", "default"): object()}) is None

# SAU
factory = worker_loop_factory({("web", "default"): object()})
assert factory is not asyncio.SelectorEventLoop
assert factory is uvloop_factory()
```

**Vì sao nó đỏ:** 0.8.1 đưa uvloop vào nhánh không-Windows, nên trên Linux
`worker_loop_factory` không còn trả `None`. Câu `is None` là cách diễn đạt của ý
*"không đổi loop"* ở thời **chưa có gì khác để đổi sang**. Ý đồ gốc của test
(*"Linux không bao giờ đổi sang selector"*) vẫn đúng và được giữ nguyên.

⭐⭐ **Vì sao Windows không thể thấy, và đây là phần đáng nhớ nhất của cả chuyến:**
ở Windows `uvloop_factory()` **luôn** trả `None` (không có wheel uvloop và sẽ
không bao giờ có). Nên dù `sys.platform` bị monkeypatch thành `"linux"`, hàm vẫn
trả `None` và test vẫn xanh.

> **Phép đo đó không đo nền tảng được monkeypatch. Nó đo nền tảng thật.** Và nó
> mâu thuẫn trực tiếp với `tests_temp/bootstrap/test_event_loop.py` (ca *"Linux +
> socket kế thừa cũng dùng uvloop"*) - **hai file khoá hai hành vi ngược nhau**,
> mà không ai thấy vì chúng không bao giờ cùng đỏ trên một máy.

Đây là **ca thứ ba** của khuôn *"lỗi máy phát triển không thể thấy về mặt cấu
trúc"*, sau C4 và C5 của kiểm toán 0.8.0. Cùng kết luận cũ: **một lượt chạy bộ
test trên Linux nên là điều kiện phát hành.**

### 2.2. Tài liệu mới

| File | |
|---|---|
| `.claude/docs/kiem-toan/0.8.1-ket-qua-do-tren-linux.md` | **Báo cáo bốn phép đo.** Đọc file này trước |
| `.claude/docs/ghi-chep/benchmark-hieu-nang.md` | **Kết quả benchmark năm tầng** + bài học về cách đo |
| `.claude/docs/ban-giao-cho-phien-windows-0.8.1.md` | File này |

### 2.3. Bộ benchmark mới

`.claude/scripts/benchmark/` - 22 file. Xem mục 5.

### 2.4. Tài liệu sửa

`.claude/CLAUDE.md` (trạng thái + hai khối mới) · `.claude/docs/README.md` (mục
lục) · `.claude/scripts/README.md` (thêm bảng thư mục con).

---

## 3. Nghiệm thu: chạy lại bên Windows thì kỳ vọng gì

```powershell
cd "D:\code\xime\xime framework"
python -m pytest -q
```

| Nền tảng | `passed` | `skipped` | `failed` | **Tổng** |
|---|---|---|---|---|
| **Linux** | **2552** ✅ đo 2026-08-22 | 6 | 0 | **2558** |
| **Windows** | **2534** ✅ đo 2026-08-22 | 24 | 0 | **2558** |

⚠ **Tiêu chí đạt là TỔNG `2558` cộng `0 failed`, không phải `passed`.** Chênh 18
là test bị chặn bởi nền tảng (Windows bỏ qua, Linux chạy): `POSIX permission
bits` 9 · `/dev/shm` 4 · `unix socket` 4 · `chmod 000` 1. Sáu lượt bỏ qua của
Linux thì bỏ qua ở **cả hai** bên vì thiếu S3 (`127.0.0.1:9000`) và MQTT broker
(`127.0.0.1:1883`).

📌 Con số Linux `2552` trước đây là **suy ra**; nay **đã đo**, và khớp.

| Cổng kiểm | Linux đo được |
|---|---|
| `mypy xime/` | **41 lỗi - đúng bằng mốc 0.8.0**, bản vá không thêm cái nào |
| `ruff check xime/` | **sạch** |
| `ruff check .claude/scripts/benchmark/` | **sạch** |
| `ruff check tests_temp/` | **199 lỗi** - xem mục 7.2, **KHÔNG phải của 0.8.1** |

### Bộ test còn xanh khi chạy DƯỚI uvloop thật

Cũng **2552 / 6 / 0**. Cách chạy ở mục 7.3 - ⚠ cách ghi trong file bàn giao chiều
đi **không hoạt động và nó xanh giả**, đọc mục đó trước khi thử.

---

## 4. Kết quả bốn phép đo

Báo cáo đầy đủ:
[`kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](../kiem-toan/0.8.1-ket-qua-do-tren-linux.md).

| # | Phép đo | Kết quả |
|---|---|---|
| 1 | Bắt tay TLS thật qua web adapter | **ĐẠT** - TLSv1.3 trọn vẹn, 20/20 request 200, log xác nhận `uvloop.Loop` + `(HTTPS)` |
| 2 | `SO_PEERCRED` của socket adapter | **ĐẠT** - uvloop trả `uvloop.loop.PseudoSocket` (khác `TransportSocket` của loop mặc định) nhưng proxy `getsockopt` đủ; đối chứng âm (sai uid -> `False`) cũng đúng |
| 3 | `share_load()` với socket kế thừa | **ĐẠT** - cụm 3 tiến trình, cả ba log `uvloop.Loop`, và **cả ba thật sự trả lời** (đếm pid: 60/31/29 trên 120 request) |
| 4 | Lãi thật | **Lật một giả định của bản 0.8.1** - đọc ngay dưới |

### 4.4. ⛔⭐ uvloop KHÔNG tăng tốc REST của Xime, nó làm chậm ~10%

Và **ranh giới thật không phải "REST hay WebSocket"** - đo trên **cùng một app Xime**:

| Loại việc | uvloop / loop mặc định |
|---|---|
| Xử lý một request kiểu HTTP: REST **0.91x** · **bắt tay WebSocket 0.93x** | **lỗ ~8-9%** |
| Truyền trên kết nối đã mở: **tin nhắn WebSocket 1.11x** · loop trần **1.38x** | **lãi 11-38%** |

⭐ **Bắt tay WebSocket là một request HTTP-upgrade, và nó rơi cùng phía với
REST** - khác phía với chính những tin nhắn chạy sau nó **trên cùng cái socket
đó**. Đó là bằng chứng mạnh nhất rằng trục phân chia là **loại việc**, không phải
giao thức.

**Đây không phải nhiễu:** dao động trong mỗi nhánh dưới 2%, hai lượt chạy đầy đủ
cách nhau một tiếng cho cùng kết quả, và một ma trận sáu hình dạng tải
(keepalive/không × c=10/100/400) cho **5/6 ô cùng chiều**.

### ⭐ Vẫn khuyến nghị GIỮ uvloop, ba lý do

1. **Chi phí bằng 0 khi không dùng tới**: không có uvloop thì `uvloop_factory()`
   trả `None` và app chạy y hệt mọi bản trước 0.8.1.
2. **REST không phải cả framework, và điều này ĐO ĐƯỢC chứ không phải suy luận**:
   tầng 5 cho **1.11x** trên chính app đó. Xime có sáu adapter; socket adapter,
   gRPC streaming, MQTT, fieldbus, WebSocket đều sống trên **kết nối đã mở** -
   đúng phía uvloop lãi.
3. **Hiệu suất trên mỗi %CPU luôn thắng** (1.31x-1.64x ở loop trần). Trên VPS
   tính tiền theo CPU thì đó là chỉ số đáng giá hơn thông lượng đỉnh.

⛔ **Đừng thêm công tắc bật/tắt uvloop** để "cho người dùng tự chọn". Mục 6.1 của
[`sap-toi/tang-toc-uvicorn-uvloop.md`](../sap-toi/tang-toc-uvicorn-uvloop.md) đã loại
phương án đó, và số liệu này không đổi được lý do: người vận hành không có đủ
thông tin để chọn, mà chính người viết framework cũng phải đo mới biết.

⏳ **Còn phải đo trước khi mở rộng kết luận**: gRPC streaming · socket adapter
dưới tải · MQTT · phản hồi lớn nhiều KB · app có I/O database thật.

---

## 5. ⭐ Thứ ngoài đề bài: framework nay có bộ benchmark

Chủ dự án yêu cầu giữa chuyến, dựng từ phép đo 4. **Trước đây framework không có
benchmark nào.**

```powershell
python .claude\scripts\benchmark\run_all.py             # cả năm tầng
python .claude\scripts\benchmark\run_all.py http scale  # chỉ vài tầng
```

⚠ **Tầng 2 và 4 cần `ab` (ApacheBench)**, không có sẵn trên Windows. Thiếu nó thì
hai tầng đó **tự khai là bỏ qua**, không im lặng cho ra bảng thiếu dòng. Tầng 1, 3
và 5 chạy được ở mọi nơi, nhưng **tầng 1 và 5 trên Windows chỉ đo được một nhánh**
(không có uvloop) nên chúng mất phần so sánh - đó là bản chất, không phải lỗi.

| Tầng | File | Đo gì |
|---|---|---|
| 1 | `bench_loop.py` | echo TCP trần, Stream API và Protocol API |
| 2 | `bench_http.py` | ASGI trần -> FastAPI -> Xime WebAdapter |
| 3 | `bench_core.py` | khởi động, DI, Store LMDB, RefData |
| 4 | `bench_scale.py` | cụm N tiến trình chung một cổng |
| 5 | `bench_ws.py` | WebSocket: tin nhắn trên kết nối sống lâu, và bắt tay |

### Ba con số đáng nhớ

| | |
|---|---|
| **Xime = 41% thông lượng của ASGI trần** | FastAPI ở giữa (66%). Đó là giá của DI + controller class-based + middleware |
| **Cụm mở rộng gần tuyến tính** | **2.00x** với 2 tiến trình, **3.88x** với 4, và **N/N tiến trình thật sự nhận việc** |
| **`RefData.read()` nhanh hơn `Store.get()` ~60 lần** | Ranh giới *có nguồn bền vững hay không* hoá ra **trùng** với ranh giới hiệu năng |

Số đo lõi khác: `import xime` **140 ms** (+web 257, +grpc 303) · `DI.get()` **13,7
triệu op/s** · `Store` LMDB set 54,8k / get 74,3k / **get-miss 88k** / incr 50,3k ·
`RefData.read()` **4,6 triệu op/s** / publish 19,6k.

📌 Một kết luận thực dụng: thêm một tiến trình cho **+100%** thông lượng, uvloop
cho **-10%**. Với app Xime điển hình, nút điều chỉnh có ích là `count:`, không
phải event loop.

### ⛔ Luật của bộ đo - phần không lỗi thời theo máy

**Hai lần** trong buổi dựng, một phép đo cho ra con số **trông hoàn toàn hợp lý**
trong khi nó đang đo **dụng cụ đo**:

| Ca | Nhìn thấy | Sự thật |
|---|---|---|
| `ab` bắn vào app Xime | uvloop = loop thường | **hợp lệ** - app 100% CPU, `ab` 36% |
| client Python bắn echo server | uvloop = loop thường | **vô hiệu** - server mới 24.8% CPU |

**Hai ca cho ra cùng một hình dạng kết quả, chỉ một trong hai có giá trị.** Nên
mọi dòng kết quả mang một nhãn, và có **BỐN** nhãn: `SERVER_BOUND` (tin được) ·
`CLIENT_BOUND` (**vứt dòng đó đi**) · `CHUA_KET_LUAN_DUOC` · `MOT_LUONG`.

⚠ **Gộp `CHUA_KET_LUAN_DUOC` vào `SERVER_BOUND` là báo xanh cho một phép đo chưa
hề chạy** - đúng thứ [luật 03](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md)
mục 4b cấm, và repo này đã cắn nó một lần với `ShardValueGuard`.

---

## 6. Thứ Linux kiểm thêm, ngoài bốn phép đo

Không có gì hỏng, ghi lại để khỏi ai đi kiểm lần nữa:

| Kiểm gì | Kết quả |
|---|---|
| **C1 của kiểm toán 0.8** (quyền file kho LMDB) | **ĐẠT** - đo thật: mọi file `0600` **dù umask là 0002** |
| **C2 của kiểm toán 0.8** (chmod socket unix trước `listen()`) | **ĐẠT** - code còn nguyên, `tests_temp/processes/test_socket_mode.py` + `lmdb/test_file_mode.py` **10/10 xanh** |
| **`xime init`** | **ĐẠT** - 12 file, `pip`-free, chạy được, trả `{"status":"ok"}`, và `host` nay là `127.0.0.1` (mục **T13** của kiểm toán 0.8 **đã vá**) |
| **Cảnh báo thiếu thư viện WebSocket** (`_availability.py`, mới ở 0.8.1) | **Nhánh im ĐÚNG** - app có route `@ws` và có `websockets` thì nó không kêu. Nhánh kêu đã có 8 test canh |
| **Route `@ws` chạy thật dưới uvloop** | **ĐẠT** - echo đúng, 7.500 tin/giây trên một kết nối, 200 kết nối đồng thời trong 0,12s |

⭐ **C1 và C2 là hai bản vá mà Windows KHÔNG THỂ nghiệm thu** (quyền POSIX). Nay
đã đo được và chúng **sống sót qua chuyến đi Windows về** - đó là thứ đáng biết,
vì một chuyến chép đè là đúng chỗ để một bản vá lặng lẽ biến mất.

---

## 7. ⚠ Ba chỗ file bàn giao CHIỀU ĐI nói sai, đã đo lại

Ghi ra vì file đó vẫn nằm trong repo và phiên sau sẽ đọc nó.

### 7.1. Python không phải 3.14

Bàn giao đoán *"Python ở đây là 3.14, nơi `asyncio` policy đã bị deprecate"*. Máy
này là **3.13.5** (venv `~/.venvs/xime`, Debian 13). Lời đoán đó dẫn tới một cảnh
báo đúng về triệu chứng nhưng **sai về nguyên nhân** - xem 7.3.

### 7.2. `ruff check tests_temp/` chưa bao giờ sạch

Mục 4 của bàn giao bảo chạy `ruff check xime/ tests_temp/`, hàm ý cả hai phải
sạch. Vế đầu sạch; vế sau thì:

| Đo trên | Số lỗi |
|---|---|
| Linux, HEAD trước khi chép (đối chứng bằng `git stash`) | **199** |
| Linux, sau khi chép bản 0.8.1 | **199** |
| **Bản Windows `D:\code\xime\xime framework`** | **201** |

Phân loại: `E701` 75 · `I001` 72 · `F401` 28 · `UP017` 8 · `E402` 5 · `F841` 4 ·
lẻ tẻ. **113 cái tự sửa được** bằng `ruff --fix`.

**Linux cố ý KHÔNG sửa**: nó đụng khoảng 150 file test và sẽ nhấn chìm phần thay
đổi thật của 0.8.1 khi đọc `git diff`. Đề nghị: **một commit riêng**, chủ dự án
quyết thời điểm.

⚠ Câu *"ruff sạch"* trong `.claude/CLAUDE.md` đúng cho `xime/`, **không** đúng cho
`tests_temp/`. Nên sửa cho khớp phạm vi.

### 7.3. ⚠⚠ Cách chạy bộ test dưới uvloop trong bàn giao KHÔNG hoạt động, và nó XANH GIẢ

Mục 3.2 của bàn giao cho một plugin dựng fixture `event_loop_policy`. Chạy nó ra
**2552 passed**, trông rất thuyết phục. **Nó không chạy dưới uvloop.**

Bắt được bằng một test đối chứng in ra loop đang chạy thật bên trong pytest:

```text
CÓ plugin    -> asyncio.unix_events._UnixSelectorEventLoop   <- đáng lẽ phải là uvloop
KHÔNG plugin -> asyncio.unix_events._UnixSelectorEventLoop
```

Hai lượt **giống hệt nhau**, tức plugin không có tác dụng gì. Nguyên nhân:
`pytest-asyncio` 1.4 **định nghĩa sẵn fixture `event_loop_policy` của chính nó**,
và fixture khai trong một plugin nạp bằng `-p` **không đè được** fixture đó. Không
liên quan gì tới Python 3.14.

**Cách chạy được**, ngắn hơn bản cũ - đặt policy toàn cục lúc import plugin, để
chính fixture mặc định của `pytest-asyncio` nhặt lên:

```python
# plugin_uvloop.py
import asyncio
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
```

```bash
PYTHONPATH=<thu-muc-chua-plugin> python -m pytest -q -p plugin_uvloop
```

⚠ **Kiểm bằng đối chứng hai chiều trước khi tin**: có plugin -> `uvloop.Loop`
(xanh), không plugin -> selector (đỏ).

> ⭐ **Bài học, lần thứ ba ở repo này: một phép đo xanh mà không có đối chứng thì
> không phân biệt được *"đã kiểm chứng, sạch"* với *"phép đo không hề chạy"*.** Ở
> đây con số 2552 **giống hệt nhau ở cả hai lượt**, nên không có gì trong kết quả
> tự tố cáo.

⚠ Cách này **không dùng được trên Windows** (không có uvloop), nên nó là một phép
kiểm **chỉ Linux chạy được** - thêm một mục vào danh sách đó.

---

## 8. Việc còn lại

### 8.1. Chủ dự án làm, đừng làm hộ

| |
|---|
| `CHANGELOG.md` cho `0.8.1` |
| `pip install -e .` để `xime.__version__` theo kịp |
| commit · tag `v0.8.1` |
| Đồng bộ repo phát hành `D:\code\xime framework\upload`, `python -m build`, `twine check`, đẩy PyPI |

### 8.2. Chờ chủ dự án quyết

| | |
|---|---|
| **199+2 lỗi ruff của `tests_temp/`** | Dọn thành một commit riêng hay để đó - mục 7.2 |
| **Sửa mục 3.2 của `ban-giao-cho-phien-linux-0.8.1.md`** | Cách chạy trong đó không hoạt động - mục 7.3 |
| **Nợ cũ chưa trả** | Một stash từ 2026-06-03 (145 file) còn nằm trong repo Windows |

### 8.3. Đề nghị cho lần phát hành sau

> **Một lượt chạy bộ test trên Linux nên là điều kiện phát hành.**

Lý do nay có **ba** ca thật chứ không phải hai: C4 (ngữ cảnh `multiprocessing`
làm chết toàn bộ đa tiến trình trên Linux, 0 đỏ trên Windows) · C5
(`SocketAdapter.assign_slot()` ném `AttributeError`, chỉ `mypy` tìm ra) · và nay
`test_linux_never_switches`. Ba ca, ba cơ chế khác nhau, cùng một hình dạng: **điều
kiện gây lỗi không tồn tại trên máy phát triển.**

---

## 9. Liên quan

- [`kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](../kiem-toan/0.8.1-ket-qua-do-tren-linux.md) - báo cáo bốn phép đo, đọc trước.
- [`ghi-chep/benchmark-hieu-nang.md`](../ghi-chep/benchmark-hieu-nang.md) - benchmark năm tầng, và mục 7 là bài học về **cách đo**.
- [`../scripts/benchmark/README.md`](../../scripts/benchmark/README.md) - cách chạy, bốn nhãn, chỗ dễ vấp.
- [`ban-giao-cho-phien-linux-0.8.1.md`](ban-giao-cho-phien-linux-0.8.1.md) - đề bài của chuyến này. ⚠ Ba chỗ nó nói sai đã ghi ở mục 7.
- [`ban-giao-cho-phien-windows.md`](ban-giao-cho-phien-windows.md) - chiều về của đợt **0.8.0**. Mục 4 của nó giải thích vì sao *"có những lớp lỗi máy phát triển không thể nhìn thấy"* là ràng buộc cấu trúc chứ không phải chuyện test yếu.
- [`sap-toi/tang-toc-uvicorn-uvloop.md`](../sap-toi/tang-toc-uvicorn-uvloop.md) - thiết kế uvloop; mục 6.1 vì sao không có công tắc.
