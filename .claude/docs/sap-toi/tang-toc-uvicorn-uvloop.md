# Tăng tốc uvicorn: bật uvloop trên Linux (nhắm 0.8.1+)

> **Trạng thái: ✅ ĐÃ CODE, ĐÃ ĐO TRÊN LINUX, SẴN SÀNG PHÁT HÀNH (2026-08-22).**
> Đây là nội dung duy nhất của `0.8.1`.
>
> ⛔⭐ **Phép đo thứ tư ở mục 5 đã chạy, và nó LẬT MỘT GIẢ ĐỊNH CỦA CHÍNH FILE NÀY:
> uvloop KHÔNG tăng tốc chồng web của Xime, nó làm REST chậm ~10%.** Lãi thật nằm ở
> **kết nối đã mở** (tin nhắn WebSocket 1.11x, loop trần 1.38x), không ở việc xử lý một
> request. **Vẫn giữ uvloop** - lý do và số liệu đầy đủ ở
> [`../kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](../kiem-toan/0.8.1-ket-qua-do-tren-linux.md)
> và [`../ghi-chep/benchmark-hieu-nang.md`](../ghi-chep/benchmark-hieu-nang.md).
>
> 📌 **File này vẫn nằm ở `sap-toi/` dù việc đã xong** - dời nó là quyết định về cấu
> trúc thư mục, thuộc chủ dự án. Đọc nó như **thiết kế đã thi hành**, và đọc mục 5 kèm
> kết quả ở mục 5b.
>
> Fieldbus chia tải, MQTT chia tải và `drain()` **đã tách sang 0.8.2** - xem
> [`../lo-trinh-phien-ban.md`](../lo-trinh-phien-ban.md) mục 0.8.1 và 0.8.2. Lý do tách là
> **tách rủi ro**, đúng lập luận mục 2 dưới đây dùng để tự hoãn khỏi 0.8.0.
>
> ✅ **Lệnh cấm trỏ tới file này ĐÃ GỠ.** Bản cũ cấm mọi tài liệu trỏ tới đây vì thiết kế 0.8.0
> đã đóng và đang thi công bảy giai đoạn; điều kiện gỡ là *"ngày 0.8.0 phát hành xong"*, và
> **0.8.0 đã lên PyPI 2026-08-21**. Nay `lo-trinh-phien-ban.md` và `../README.md` đều trỏ tới.
>
> ⚠ **Một chỗ trong file này đã LỖI THỜI, xem đính chính ở mục 1.2 và 4.3:** nó mô tả **hai**
> đường vào `asyncio.run`, còn code 0.8.0 sau kiểm toán **đã hợp nhất còn một**. Việc số 3 của
> bảng mục 10 vì vậy biến mất.
>
> Mọi số liệu dưới đây đo ngày **2026-08-20** trên máy dev (Windows 11, Python 3.14,
> uvicorn 0.41.0). Số đo là **ảnh chụp**, không phải trạng thái, đo lại trước khi tin.

---

## 0. Một phút

`pip install xime[web]` đã kéo `uvicorn[standard]` từ lâu, nên bốn thư viện tăng tốc **đã nằm
sẵn trên đĩa** ở mọi cài đặt Linux. Nhưng đo ra thì:

| Thư viện | Có tác dụng hôm nay? | Việc phải làm |
|---|---|---|
| `httptools` (parse HTTP, C) | ✅ **có** | không |
| `websockets` (speedups C) | ✅ **có** | không (xem mục 7, một cảnh báo nhỏ) |
| `watchfiles` (Rust) | không dùng được | không (xem mục 8) |
| **`uvloop`** (libuv) | ⛔ **KHÔNG**, dù đã cài | **toàn bộ nội dung file này** |

Nguyên nhân gọn trong một câu: **xime gọi `uvicorn.Server.serve()`, mà `loop_factory` của
uvicorn chỉ được dùng trong `Server.run()`.** Xime tự sở hữu vòng lặp, nên đường cài uvloop của
uvicorn không nằm trên đường đi.

Việc phải làm: khoảng 20 dòng, hai chỗ gọi, không đổi API, 31 app không sửa một chữ.

---

## 1. Bằng chứng, không phải suy luận

### 1.1. uvicorn cài uvloop ở đâu

```python
# site-packages/uvicorn/server.py:74-79
def run(self, sockets: list[socket.socket] | None = None) -> None:
    return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())

async def serve(self, sockets: list[socket.socket] | None = None) -> None:
    with self.capture_signals():
        await self._serve(sockets)          # <- không đụng get_loop_factory()
```

`get_loop_factory()` xuất hiện **đúng một lần** trong cả `server.py` lẫn `config.py`, ở dòng 75.

### 1.2. Xime đi đường nào

```text
python -m app.main
└─ Application.run()
   ├─ asyncio.run(self._run_async())                              application.py:246   (31 app hôm nay)
   └─ asyncio.run(self._run_async(), loop_factory=worker_loop_factory(sockets))
                                                                  application.py:295   (nhánh share_load)
      └─ WebAdapter.start()
         └─ await self._server.serve(sockets=[...])               _adapter.py:352
```

Cả hai đường đều **không bao giờ gọi `Server.run()`**. Nên `loop="auto"` của uvicorn chưa từng
được đọc.

> ### ⛔ ĐÍNH CHÍNH 2026-08-22: nay chỉ còn MỘT đường vào, không phải hai
>
> Sơ đồ trên đo lúc 0.8.0 đang thi công. Bản 0.8.0 sau kiểm toán **đã hợp nhất**: cả ba nhánh
> của `run()` (đơn tiến trình · supervisor · worker) đều rơi vào `Application._run_worker()`,
> nơi có **đúng một** lời gọi:
>
> ```text
> Application.run()
> ├─ khong share_load  ─┐
> ├─ supervisor        ─┤─→ _run_worker(topology, process_id, sockets)
> └─ worker            ─┘   └─ asyncio.run(self._run_async(),
>                                          loop_factory=worker_loop_factory(sockets))
> ```
>
> Nhánh đơn tiến trình truyền `sockets={}`, và `worker_loop_factory({})` trả `None` - tức đúng
> hành vi hôm nay.
>
> **Hệ quả:** rủi ro *"vá một nửa"* mà mục 4.3 cảnh báo **không còn tồn tại về mặt cấu trúc**,
> chứ không phải được tránh nhờ cẩn thận. Sửa `worker_loop_factory` là phủ hết mọi đường vào,
> và **việc số 3 của bảng mục 10 biến mất**.

⚠ Số dòng có thể trôi: `application.py` đã được sửa trong giai đoạn 3 của 0.8.0 rồi lại sửa
trong đợt kiểm toán. Tìm theo tên (`asyncio.run`, `worker_loop_factory`) chứ đừng tìm theo số.

### 1.3. Vì sao httptools và websockets thì lại chạy

Chúng được chọn ở `config.load()`, mà `load()` nằm **trong** `_serve()`:

```python
# server.py:81-86
async def _serve(self, sockets=None):
    config = self.config
    if not config.loaded:
        config.load()          # <- ở đây "auto" của http/ws mới được phân giải
```

Còn ba file `auto.py` (`loops/`, `protocols/http/`, `protocols/websockets/`) đều chỉ là
`try: import X except ImportError: dùng bản Python thuần`. Hai cái sau đi qua `config.load()`
nên sống; cái đầu đi qua `Server.run()` nên chết.

> ⭐ Đáng nhớ hơn con số: **ba cơ chế trông giống hệt nhau từ ngoài** (cùng một khuôn `auto.py`,
> cùng một cách dò), nhưng một cái nằm ở nhánh code ta không đi qua. Nhìn `pip list` thấy đủ
> bốn gói rồi kết luận "đã bật tăng tốc" là sai, và **không có gì báo**.

---

## 2. Vì sao 0.8.1 chứ không phải 0.8.0

Ba lý do, xếp theo trọng lượng thật:

1. **Tách rủi ro.** 0.8.0 đang thay cả mô hình chạy (supervisor, socket dùng chung, đổi API
   adapter). Nhét thêm một thay đổi vòng lặp vào đó là ngày có sự cố không biết thủ phạm là
   supervisor hay uvloop. Để riêng thì mỗi lần đổi có đúng một nguyên nhân.
2. **Thiết kế 0.8.0 đã đóng và đang thi công theo bảy giai đoạn.** Chèn ngang là đúng thứ bản
   bàn giao 08-19 cảnh báo.
3. **Không vướng luật "0.8 là alpha cuối".** Luật đó nói *0.8.1 chỉ được HIỆN THỰC, không đổi
   API*. Bản vá này **không có bề mặt API nào**: không tham số mới, không khoá YAML mới, không
   `configure_*` mới. Nên hoãn sang 0.8.1 **không khoá mất gì cả**. Đã kiểm điều này trước khi
   quyết, vì nếu có knob thì nó phải chốt ở 0.8.0.

   📌 **Cập nhật 2026-08-22: luật đó đã bị chủ dự án nới 2026-08-19** (*"0.8 đang có nhiều phiên
   bản con nữa mà, vẫn nhiều cơ hội để đổi"*). **Kết luận không đổi** - bản vá này vốn không có
   bề mặt API nào để mà vướng, nên nó đúng ở cả hai bản của luật.

⚠ Điều kiện của lý do 3: **làm tự dò, KHÔNG làm công tắc**. Xem mục 6.1.

---

## 3. Bốn chỗ đã đo là KHÔNG dính

Một thay đổi vòng lặp thường cắn ở bốn chỗ. Đo cả bốn trước khi đề xuất:

| Chỗ hay hỏng | Ở xime | Vì sao không dính |
|---|---|---|
| uvloop + `fork` | ✅ an toàn | Supervisor dùng `multiprocessing.get_context("spawn")` (`_supervisor.py:478`), và **cha không chạy asyncio** (nó là vòng lặp `waitpid` thuần). Mỗi con dựng loop từ đầu |
| Đọc cert phía đối tác | ✅ an toàn | `PEER_CN`/`PEER_SANS` **chỉ** được set ở `adapters/grpc/interceptors/_context.py`. gRPC chạy trên core C riêng, không mượn transport asyncio. **Web không đọc cert dòng nào** |
| Code của 31 app | ✅ an toàn | Không app nào chạm tới việc tạo event loop |
| API công khai | ✅ an toàn | Không đổi gì, xem mục 2 |

📌 Chỗ thứ nhất là may chứ không phải cố ý: thiết kế 0.8 chọn `spawn` vì lý do khác hẳn (truyền
socket và import lại `main.py`), và nó tránh sẵn một cạm bẫy kinh điển của uvloop.

---

## 4. Cách vá

### 4.1. Một module mới, dùng chung cho hai đường vào

Đặt ở `xime/core/bootstrap/_loop.py`. **Đừng** để hàm này trong `_supervisor.py`: đường
`application.py:246` (31 app hôm nay) không đi qua supervisor, và import `_supervisor` từ đó là
kéo cả `multiprocessing` vào một nhánh không cần tới nó.

```python
# xime/core/bootstrap/_loop.py

def uvloop_factory() -> Any | None:
    """Return uvloop's loop factory when it is installed, otherwise None.

    None means "use whatever asyncio.run would have used", which is exactly the
    behaviour every release before this one had. uvloop ships no Windows wheel
    and never will, so this returns None there by construction, not by policy.

    Trả None nghĩa là "để asyncio.run tự quyết", tức đúng hành vi của mọi bản
    trước đây. uvloop không có wheel Windows và sẽ không bao giờ có, nên trên
    Windows hàm này trả None do bản chất chứ không do một luật nào.
    """
    try:
        import uvloop
    except ImportError:
        return None
    return uvloop.new_event_loop
```

⛔ **Đừng dùng `uvloop.install()`.** Đó là API cũ, sửa chính sách toàn cục của asyncio.
`loop_factory` là đường uvloop khuyến nghị và là đường duy nhất ghép được với `asyncio.run`.
(Kiểm lại trạng thái deprecation của `install()` lúc code.)

### 4.2. Ghép vào `worker_loop_factory`, đừng viết chồng lên nó

`_supervisor.py:424` đã là hàm *"chọn kiểu loop cho tiến trình con"*. Hai điều kiện nằm trên
**hai nền tảng rời nhau** nên ghép là một `if/else`, không có chỗ nào đè nhau:

```python
def worker_loop_factory(sockets: Mapping[tuple[str, str], socket.socket]) -> Any:
    if sys.platform == "win32":
        if not sockets:
            return None
        _log.warning(...)                 # GIỮ NGUYÊN, xem cảnh báo bên dưới
        return asyncio.SelectorEventLoop
    return uvloop_factory()               # Linux, macOS
```

⛔⛔ **Không được đụng nhánh Windows.** Nó tồn tại vì `WinError 87` (liên kết IOCP thuộc về
socket của kernel, không thuộc handle), và cách hỏng của nó là **con thứ hai khởi động thành
công, log "serving", rồi không nhận nổi một kết nối nào**. Đọc docstring của chính hàm đó trước
khi sửa một ký tự.

### 4.3. ~~Đường vào thứ hai~~ - ⛔ HẾT ĐÚNG 2026-08-22

> **Không còn đường vào thứ hai.** Xem đính chính ở mục 1.2: 0.8.0 đã hợp nhất cả ba nhánh về
> `Application._run_worker()`, nên sửa `worker_loop_factory` (mục 4.2) là xong.
>
> Giữ nguyên vết gạch thay vì xoá, vì nỗi lo bên dưới **từng đúng** và người đọc cần thấy nó đã
> được đóng bằng cách nào - bằng **cấu trúc code**, không bằng kỷ luật.

~~`application.py:246` (nhánh không `share_load`) cũng phải sửa, và **đây mới là đường 31 app
đang đi**~~:

```python
asyncio.run(self._run_async(), loop_factory=uvloop_factory())
```

`asyncio.run(..., loop_factory=)` có từ **Python 3.12**, đúng bằng `requires-python` của gói.
Không phải thêm lớp tương thích nào. **Câu này vẫn đúng** - nó là điều kiện cho mục 4.2.

~~⚠ **Sửa một chỗ quên chỗ kia là dạng lỗi tệ nhất ở đây**: `share_load()` nhanh còn chạy thường
thì không, hoặc ngược lại, và **không gì báo**. Phải có test canh **cả hai** đường vào cùng gọi
`uvloop_factory()`.~~

⭐ **Test canh vẫn phải có, nhưng canh thứ khác**: nay là *"cả ba nhánh của `run()` đều đi qua
`worker_loop_factory`"*. Ngày ai đó thêm một `asyncio.run` thứ hai thì test đó đỏ - đúng thứ
lời cảnh báo cũ muốn phòng.

### 4.4. Log KẾT QUẢ, không log Ý ĐỊNH

Trong `_run_async()`, ngay sau khi loop đã chạy:

```python
loop = asyncio.get_running_loop()
_log.info("event loop: %s.%s", type(loop).__module__, type(loop).__qualname__)
```

> ⭐ Log thứ **đang chạy thật**, đừng log *"đã bật uvloop"* dựa trên việc import thành công.
> Cả sự cố này lẫn `xime.__version__` đứng ở `0.6.3` suốt hai bản đều cùng một khuôn: **một giá
> trị khai ý định bị đọc như một giá trị khai sự thật**. Dòng log trên là câu trả lời cho
> *"hôm nay có uvloop không"* mà không ai phải đi đọc code.

Đây cũng là lý do bản vá này **bắt buộc** kèm dòng log: không có nó thì ta vừa thay một thứ im
lặng bằng một thứ im lặng khác.

---

## 5. Bốn phép đo BẮT BUỘC trên Linux trước khi phát hành

Không cái nào là *"đừng làm"*, tất cả là *"đo đi"*. Nhưng chưa đo thì chưa được đóng mục này.

| # | Đo gì | Vì sao |
|---|---|---|
| **1** | **Bắt tay TLS thật** qua web adapter (`server.ssl` đủ `certfile`/`keyfile`/`ca_certs`) | uvloop có hiện thực SSL **riêng**, đây là chỗ nó lệch khỏi stdlib nhiều nhất. Web adapter đẩy thẳng `ssl_*` xuống uvicorn |
| **2** | **`SO_PEERCRED`** của socket adapter | `adapters/socket/_peercred.py:36` gọi `writer.get_extra_info("socket")` rồi `getsockopt`. uvloop trả về một `TransportSocket` bọc chứ không phải socket trần. Về lý thuyết nó proxy đủ, nhưng đây là chỗ đáng đo chứ không đáng tin |
| **3** | **`share_load()` với socket kế thừa từ cha** | `create_server(sock=...)` dưới uvloop, trên socket đã `bind` và `listen` sẵn ở tiến trình khác. Cùng họ với cái bẫy `WinError 87`, khả năng cao là chạy tốt, nhưng "khả năng cao" không phải một phép đo |
| **4** | **Lãi thật**, không phải lãi trên giấy | uvloop thường cho 1,5 tới 2 lần thông lượng ở tải nhiều kết nối nhỏ. Nếu app chặn ở Postgres thì phần lãi teo lại gần hết. **Đo trước, rồi hẵng quyết có giữ hay không** |

📌 Phép đo 4 nên đi cùng chuyến với đợt đo `Store`/LMDB trên VPS Linux, vì cả hai cùng cần một
môi trường mà máy dev không có.

---

## 5b. ✅ Kết quả bốn phép đo (Linux, 2026-08-22)

Debian 13, Python 3.13.5, uvloop 0.22.1, uvicorn 0.52.4, 16 CPU. Báo cáo đầy đủ:
[`../kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](../kiem-toan/0.8.1-ket-qua-do-tren-linux.md).

| # | Phép đo | Kết quả |
|---|---|---|
| 1 | Bắt tay TLS thật | **ĐẠT** - TLSv1.3 trọn vẹn, 20/20 request 200, log xác nhận `uvloop.Loop` + `(HTTPS)`. Nỗi lo *"uvloop có hiện thực SSL riêng"* là có thật, và nó chạy đúng |
| 2 | `SO_PEERCRED` | **ĐẠT** - uvloop trả `uvloop.loop.PseudoSocket` (**khác hẳn** `TransportSocket` của loop mặc định) nhưng proxy `getsockopt` đủ. Có **đối chứng âm**: uid sai -> `False` |
| 3 | `share_load()` socket kế thừa | **ĐẠT** - cụm 3 tiến trình, cả ba log `uvloop.Loop`, và **cả ba thật sự trả lời** (đếm pid: 60/31/29 trên 120 request). Đo bằng *ai trả lời*, không bằng *nó khởi động được* |
| 4 | Lãi thật | ⛔ **Lật giả định** - xem dưới |

### ⛔ Phép đo 4: ranh giới không phải giao thức, mà là LOẠI VIỆC

Đo trên **cùng một app Xime**, dao động dưới 2%, hai lượt cách nhau một tiếng cho cùng
kết quả, ma trận sáu hình dạng tải cho 5/6 ô cùng chiều:

| Loại việc | uvloop / loop mặc định |
|---|---|
| Xử lý một request kiểu HTTP: REST **0.91x** · **bắt tay WebSocket 0.93x** | **lỗ ~8-9%** |
| Truyền trên kết nối đã mở: **tin nhắn WebSocket 1.11x** · echo TCP trần **1.38x** | **lãi 11-38%** |

⭐ **Bắt tay WebSocket là một request HTTP-upgrade, và nó rơi cùng phía với REST** -
khác phía với chính những tin nhắn chạy sau nó **trên cùng cái socket đó**. Đó là bằng
chứng mạnh nhất rằng trục phân chia là loại việc, không phải giao thức.

uvloop tăng tốc tầng loop/transport nhưng có **chi phí cố định mỗi callback**; khi app
kẹt ở công việc mức Python thì phần lãi không có chỗ hiện ra còn chi phí vẫn phải trả.

📌 Kết luận thực dụng: thêm một tiến trình cho **+100%** thông lượng, uvloop cho
**-10%**. Nút điều chỉnh có ích của một app Xime điển hình là `count:`, không phải event
loop. ⚠ Điều đó **không** làm mục 6 dưới đây sai - xem ba lý do giữ uvloop trong báo cáo.

⏳ **Chưa đo, nên chưa mở rộng kết luận**: gRPC streaming · socket adapter dưới tải ·
MQTT · phản hồi lớn nhiều KB · app có I/O database thật.

## 6. Ranh giới: thứ cố ý KHÔNG làm

### 6.1. Mặc định BẬT khi có mặt, nhưng KHÔNG bắt buộc phải có

Chữ "mặc định" ở đây có hai nghĩa, và chỉ một nghĩa được chọn:

| Cách hiểu | Chọn? | |
|---|---|---|
| **Có uvloop thì dùng, không có thì chạy như cũ** | ✅ | Không ai phải khai gì. Trên Linux, `pip install xime[web]` vốn đã kéo uvloop về, nên thực tế là **bật ở mọi cài đặt chuẩn** |
| Bắt buộc phải có uvloop trên Linux, thiếu thì nổ lúc khởi động | ⛔ | Phá người cài `uvicorn` trần, và đổi một thứ đang chạy được thành một thứ từ chối chạy. Không đáng, vì bản vá này là **tối ưu**, không phải sửa lỗi |

Nói cách khác: uvloop là **mặc định của nền tảng Linux**, không phải **điều kiện bắt buộc**.
Thiếu nó thì app chạy đúng như hôm nay, chỉ chậm hơn.

### ⛔ Không làm công tắc

Có uvloop thì dùng, không có thì thôi. Muốn tắt thì `pip uninstall uvloop`.

Ba lý do: (a) thêm khoá cấu hình là thêm bề mặt API, mà mục 2 vừa dựa vào việc **không có** bề
mặt nào để hoãn sang 0.8.1; (b) theo câu phân loại ở `rules/config-discovery.md`
(*"người vận hành có ĐỦ THÔNG TIN để chọn giá trị này không?"*) thì cái này **lấn cả hai bên**,
người vận hành biết mình chạy nền tảng nào, nhưng *uvloop có an toàn cho app này không* lại phụ
thuộc code của app; (c) một công tắc chưa ai cần là một nhánh code chưa ai chạy.

Ngày có người thật cần tắt uvloop mà không gỡ gói được thì thêm khoá YAML, thuần cộng thêm, làm
ở 0.8.2 cũng không muộn.

### 6.2. ⛔ Không tự cài uvloop thành phụ thuộc riêng

`uvicorn[standard]` đã khai `uvloop>=0.15.1` kèm marker
`sys_platform != 'win32' and sys_platform != 'cygwin' and platform_python_implementation != 'PyPy'`.
Khai lại trong `pyproject.toml` của xime là dựng một sàn thứ hai phải bảo trì, và nó sẽ lệch với
sàn của uvicorn vào một ngày không ai để ý. **Để uvicorn quyết phiên bản uvloop**, cùng lý do
`botocore` được khai không phiên bản ở extra `s3`.

### 6.3. ⛔ Không kỳ vọng Windows

uvloop 0.22.1 (bản mới nhất lúc đo) có wheel `cp310` tới `cp314` nhưng **chỉ** cho
`manylinux`/`musllinux` và macOS. Không có wheel Windows, và đây không phải hạn chế tạm thời.

⚠ Hệ quả phải khai, không xoá được: **máy dev sẽ không bao giờ chạy nhánh mà prod chạy.** Đó là
cái giá thật của bản vá này. Bù bằng bốn phép đo ở mục 5, không bù bằng niềm tin.

### 6.4. ⛔ Đừng mong uvloop giúp gRPC

`grpcio` chạy trên core C riêng, không dùng transport của asyncio. Phần hưởng lợi là **web,
socket adapter, MQTT** và mọi thứ đi qua transport asyncio.

---

## 7. Việc phụ, cùng họ: cảnh báo khi thiếu thư viện WebSocket

Nhỏ hơn nhiều, nhưng cùng gốc (extra của uvicorn) nên ghi chung.

`protocols/websockets/auto.py` đặt `AutoWebSocketsProtocol = None` khi **không có cả**
`websockets` lẫn `wsproto`. Lúc đó mọi route `@ws` (mới có từ 0.7.2) **chết lặng**: bắt tay
không thành, không có dòng log nào của xime giải thích vì sao.

`xime[web]` kéo `uvicorn[standard]` nên phủ được đường cài chuẩn. Đường **không** phủ được: ai
cài `uvicorn` trần rồi cài `xime` không kèm extra.

Đề xuất: lúc khởi động, **nếu và chỉ nếu** app có ít nhất một route `@ws`, kiểm
`AutoWebSocketsProtocol is not None`, thiếu thì WARNING kèm câu lệnh cài. Cùng khuôn cảnh báo
F17 của 0.7.2 (chỉ kêu khi thực sự có `@rpc`).

⚠ Giữ điều kiện *"chỉ khi có `@ws`"*. Kêu ở mọi app là một cảnh báo giả cho đa số, mà
**phép dò kêu oan là phép dò sẽ bị tắt**.

---

## 8. `watchfiles`: cài mà không dùng, và cứ để vậy

`watchfiles` chỉ phục vụ `--reload` của uvicorn CLI. Xime vào bằng `python -m app.main` nên
không bao giờ chạm tới nó.

**Không gỡ.** Nó đi kèm `uvicorn[standard]` như một khối; tách ra là phải tự khai lại từng gói
con của extra đó, tức nhận về đúng gánh nặng mục 6.2 vừa từ chối. Vài trăm KB trên đĩa rẻ hơn
một danh sách phụ thuộc phải bảo trì.

---

## 9. Cách tự kiểm sau khi vá

```python
# trong một handler bất kỳ, hoặc một PostConstruct
import asyncio
print(type(asyncio.get_running_loop()))
# uvloop:  <class 'uvloop.Loop'>
# asyncio: <class 'asyncio.unix_events._UnixSelectorEventLoop'>
```

Trước khi vá, kiểm rằng phát hiện ở mục 1 vẫn còn đúng (đừng tin file này, nó là ảnh chụp):

```bash
grep -rn "get_loop_factory" "$(python -c 'import uvicorn,os;print(os.path.dirname(uvicorn.__file__))')"
# chỉ được ra server.py:75 (trong run()) và config.py (định nghĩa)
```

Kiểm ba thư viện kia có đang thật sự được chọn không:

```python
from uvicorn.protocols.http.auto import AutoHTTPProtocol
from uvicorn.protocols.websockets.auto import AutoWebSocketsProtocol
print(AutoHTTPProtocol.__module__)        # ...httptools_impl  hay  ...h11_impl
print(AutoWebSocketsProtocol)             # None = mọi route @ws sẽ chết lặng
```

---

## 10. Việc phải làm, gom lại

| # | Việc | Ghi chú |
|---|---|---|
| ~~1~~ | ✅ **XONG 2026-08-22** - `xime/core/bootstrap/_loop.py` + `uvloop_factory()` | Module mới, tránh kéo `multiprocessing` vào nhánh thường |
| ~~2~~ | ✅ **XONG 2026-08-22** - ghép vào `worker_loop_factory` (`_supervisor.py`), tách thành **ba nhánh thật** | ⛔ Nhánh Windows selector **giữ nguyên từng chữ**, có 4 test đối chứng dương canh |
| ~~3~~ | ~~Sửa `asyncio.run` ở nhánh **không** `share_load`~~ | ⛔ **HẾT ĐÚNG 2026-08-22** - 0.8.0 đã hợp nhất còn một đường vào. Xem 1.2 và 4.3 |
| ~~4~~ | ✅ **XONG 2026-08-22** - `Application._log_running_loop()` | Đo thật: `INFO | xime.bootstrap | event loop: asyncio.windows_events.ProactorEventLoop`, in **trước** dòng của web adapter |
| ~~5~~ | ✅ **XONG 2026-08-22** - `tests_temp/bootstrap/test_event_loop.py`, **16 test** | Bốn đối chứng đều đỏ đúng chỗ - xem mục 12 |
| 6 | Bốn phép đo trên Linux | Mục 5. Chưa đo thì chưa đóng |
| ~~7~~ | ✅ **XONG 2026-08-22** - `xime/adapters/web/ws/_availability.py`, 8 test | Chủ dự án yêu cầu làm luôn. ⚠ **Máy này không thiếu gì** (`websockets 16.0` có, `httptools` đang chạy) - đây là cảnh báo cho **người dùng framework** cài `uvicorn` trần |
| 8 | `CHANGELOG.md` | ✅ Phần `lo-trinh-phien-ban.md` + con trỏ **đã làm 2026-08-22** (điều kiện *"sau khi 0.8.0 phát hành"* đã thoả). Còn lại `CHANGELOG.md`, làm lúc phát hành |

---

## 12. Kết quả thi công 2026-08-22 (phần làm được trên Windows)

Việc **1, 2, 4, 5, 7 đã xong**; chỉ còn việc 6 (bốn phép đo Linux) và việc 8
(`CHANGELOG.md` lúc phát hành).

| Nghiệm thu | |
|---|---|
| Bộ test đầy đủ | **2534 passed / 24 skipped / 0 failed** (223s) - kỳ vọng Windows cũ **2510** cộng **16** (uvloop) cộng **8** (việc 7) |
| `ruff check xime/` | sạch (một lỗi thứ tự import đã sửa) |
| `mypy` | ⏳ **chưa chạy** - khai trong extra `dev` nhưng **chưa cài trên máy này**. Đây là công cụ **duy nhất** tìm ra C5 ở đợt kiểm toán 0.8 |
| Chạy thật một tiến trình | `INFO | xime.bootstrap | event loop: asyncio.windows_events.ProactorEventLoop`, in **trước** dòng của web adapter |

### ⭐ Bốn đối chứng - và cái thứ tư tìm ra một lỗ hổng thật

Chạy đúng thủ tục *"gỡ bản vá ra rồi đếm test đỏ"*, vì **"không test nào đỏ" có ba
nghĩa** và chỉ đối chứng mới tách được chúng:

| Gỡ ra thứ gì | Test đỏ |
|---|---|
| Đường uvloop (nhánh Linux trả thẳng `None`) | **3** |
| Quay về điều kiện gộp của 0.8.0 (`!= "win32" or not sockets`) | **3** |
| Bỏ `loop_factory=` khỏi `asyncio.run` | **2** |
| Xoá dòng `self._log_running_loop()` khỏi `_run_async()` | ⛔ **0**, rồi **1** sau khi vá |

⭐ **Dòng cuối là phần đáng đọc nhất.** Bản test đầu có 15 ca, tất cả xanh, và **vẫn
xanh nguyên khi gỡ hẳn lời gọi log ra khỏi vòng đời**. Nguyên nhân: chúng kiểm
`_log_running_loop()` bằng cách **gọi thẳng nó**, tức canh **hàm** chứ không canh **việc
hàm được gọi**.

> Một phép đo nhắm vào thứ mình vừa viết thì gần như luôn xanh. Chỉ có đối chứng mới
> phân biệt được *"đã canh"* với *"tưởng là đã canh"*.

Vá bằng `test_vong_doi_that_co_log_loop`: chạy `_run_async()` thật rồi đọc log.
⚠ Phải huỷ task bằng tay - `_serve_adapters()` kết thúc bằng `asyncio.sleep(inf)` **có
chủ đích** (adapter cuối chết thì tiến trình vẫn ở lại để `/healthz` còn trả lời được),
nên `await` thẳng là treo. Lần chạy đầu đã treo đúng như vậy.

### ⚠ Thứ Windows KHÔNG chứng minh được

**Không phép đo nào ở trên chạm vào uvloop.** Trên máy này `uvloop_factory()` luôn trả
`None`, nên 16 test kia chỉ chứng minh **đường dây nối đúng**: nhánh nào gọi tới đâu, ai
không được gọi. Nhánh uvloop thật sự **chưa chạy một lần nào**.

Bốn phép đo ở mục 5 vì vậy **chặn phát hành 0.8.1**, khác hẳn hai phép đo LMDB (chỉ để
chỉnh tham số vận hành).

### Kỳ vọng test sau bản vá - HAI con số, theo hệ điều hành

| Nền tảng | `passed` | `skipped` | **Tổng** |
|---|---|---|---|
| Linux | **2552** (dự kiến: 2528 + 24) | 6 | **2558** |
| Windows | **2534** (đo thật) | 24 | **2558** |

⚠ Con số Linux là **dự kiến, chưa đo** - 24 test mới không có ca nào phụ thuộc nền tảng,
nhưng đó là suy luận chứ không phải phép đo. **Thứ bất biến giữa hai bên là tổng 2558**,
không phải `passed`.

⚠⚠ **`2534` xuất hiện hai lần với hai nghĩa khác nhau**: nó là **tổng của 0.8.0**, và
cũng là **`passed` của Windows ở 0.8.1**. Trùng số, khác trục - đúng kiểu nhầm mà con số
bàn giao sai của đợt trước đã cắn.

### Việc 7 đã làm gì, và một hiểu nhầm đáng ghi lại

Chủ dự án đọc mục 7 rồi bảo *"bạn hãy cài và làm giúp tôi"* - hiểu là **máy này đang
thiếu thư viện**. Kiểm bằng lệnh thì không: `websockets 16.0` có mặt, và
`AutoHTTPProtocol` đang là `httptools_impl` chứ không phải `h11`.

> Việc 7 **không phải cài gì cả**. Nó là **thêm một cảnh báo cho người dùng framework**
> nào cài `uvicorn` trần rồi cài `xime` không kèm extra - lúc đó `xime[web]` không kéo
> `uvicorn[standard]` về, và mọi route `@ws` của họ chết lặng.

📌 Hiểu nhầm này tự nó là bằng chứng cho lý do việc 7 tồn tại: **trạng thái "có hay
không có thư viện WebSocket" hôm nay không nói ra ở đâu cả**, nên ngay cả người viết ra
mục này cũng phải chạy lệnh mới biết.

**Hiện thực:** `xime/adapters/web/ws/_availability.py`, móc vào
`_register_websocket_handlers` **sau** cửa thoát sớm `if not handlers: return` - đó
chính là chỗ hiện thực điều kiện *"chỉ kêu khi thật sự có `@ws`"*, và nó là **cấu trúc**
chứ không phải một `if` thêm vào.

| Quyết định | |
|---|---|
| Hỏi `AutoWebSocketsProtocol`, **không** thử `import websockets` | Đó là thứ uvicorn thật sự dùng, và nó chấp cả `websockets` lẫn `wsproto`. Tự liệt kê tên gói là dựng danh sách thứ hai phải bảo trì |
| Không import được module đó thì **coi như thiếu** | Không kết luận được là *"có"* thì đừng im lặng cho qua |
| **Cảnh báo, không nổ** | Nổ lúc khởi động là biến app đang chạy thành app từ chối chạy, vì một thư viện mà đường cài chuẩn vốn đã kéo về |
| Trả `bool` thay vì `None` | Để test khẳng định được **cả hai** nhánh |

**Ba đối chứng, đều đỏ đúng chỗ:**

| Gỡ ra thứ gì | Test đỏ |
|---|---|
| Lời gọi cảnh báo trong adapter | **2** |
| Phép kiểm bên trong (thành *"luôn kêu"*) | **1** - `test_du_thi_im` |
| Chuyển lời gọi lên **trước** cửa thoát sớm | **1** - `test_canh_bao_nam_sau_cua_thoat_som` |

⭐ Nhóm test thứ ba (`TestNoiVaoDuongKhoiDong`) sinh ra **vì bài học của việc 5 trong
cùng bản này**: ở đó 15 test kiểm một hàm bằng cách gọi thẳng nó, và vẫn xanh nguyên khi
lời gọi bị gỡ khỏi vòng đời. Lần này viết luôn phần canh *"hàm có được gọi không"*, thay
vì đợi đối chứng dạy lại.

## 11. Liên quan

- `rules/module-level-code.md` - cùng họ: thứ chạy đúng ở một tiến trình hoặc một nền tảng,
  hỏng hoặc vắng mặt ở nền tảng khác mà không có triệu chứng.
- `rules/config-discovery.md` - câu phân loại dùng ở mục 6.1.
- [Luật 03 của workspace](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md) - *"đã cài
  uvloop"* và *"đang chạy uvloop"* là hai sự thật khác nhau bị đọc như một. Mục 4.4 là cách
  tách chúng.
- `docs/thiet-ke/10-da-tien-trinh.md` mục 5.5 - mô hình chạy, lý do dùng `spawn`
  (chỗ tình cờ cứu ta khỏi cạm bẫy uvloop cộng fork).
- `docs/thiet-ke/07-tls-web-adapter.md` - khối `server.ssl`, thứ phép đo số 1 phải chạy qua.
