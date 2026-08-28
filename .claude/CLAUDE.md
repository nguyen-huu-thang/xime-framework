# XIME Framework - Hướng dẫn phiên làm việc

> **File này trả lời đúng một câu: *hôm nay đứng ở đâu, làm gì tiếp*.**
> Nó KHÔNG trả lời *"chuyện gì đã xảy ra"* - câu đó thuộc về `CHANGELOG.md` và
> [`docs/`](docs/README.md). Sắp xếp lại 2026-08-21, từ 1770 dòng xuống còn chừng này.

## Trạng thái

✅ **`0.8.2` ĐÃ PHÁT HÀNH 2026-08-26** - bản thứ **16** trên PyPI, đẩy lên 00:51 UTC.

⚠ **Nhánh đã đi XA HƠN `0.8.2` - repo phát triển KHÔNG còn ở đúng bản đã phát hành.**
Có việc chưa phát hành, xem `## [Chưa phát hành]` trong `CHANGELOG.md` và mục
*"Đã vá 2026-08-27"* bên dưới. Mốc nghiệm thu nay là **2667/24/0 = tổng 2691**, không
phải con số `0.8.2` trong bảng dưới đây.

| | |
|---|---|
| PyPI | **`0.8.2`** · wheel `5bfb1212…` (616.365 B) · sdist `8d713106…` (785.488 B) |
| `pyproject` + `__init__` fallback | **`0.8.2`** |
| Repo phát triển | `64ee5d4 v0.8.2`, sạch |
| Repo phát hành | `fd9566e v0.8.2`, sạch |
| ⭐ Đối chứng | **SHA256 gói trên PyPI khớp từng bit** với gói dựng ở máy này, cả `.whl` lẫn `.tar.gz` |
| Nghiệm thu Windows | test **2625/24/0 = tổng 2649** · `ruff check xime/` sạch · `mypy` **49 trước và sau** · `twine check` **PASSED** · **0 rò rỉ** `.claude/`/`tests_temp/`/`pypi_token` · cài wheel vào venv trắng chạy được |

⭐ So với `0.8.1`: **thêm đúng 1 file, bỏ 0** - `xime/core/bootstrap/_orphan.py`
(sdist 294 -> **295**, wheel 247 -> **248**).

⚠ **Định vị đã đổi ở bản này, và nó chạm metadata PyPI:** dòng *"Spring Boot-style developer
experience"* đã **bỏ** khỏi `description`, hai README và `CLAUDE.md`; chữ Spring nay chỉ còn
trong thân README ở một mục nói rõ **mượn gì / cố ý bỏ gì**. `keywords` 4 -> **13**,
`classifiers` 9 -> **17** (đã đối chiếu với 895 classifier chính thức của PyPI - sai một chữ là
bị từ chối lúc upload). Lý do: [`docs/ghi-chep/dac-tinh-python-va-vi-tri-framework.md`](docs/ghi-chep/dac-tinh-python-va-vi-tri-framework.md) mục 4.

⛔ **Đừng chép đè `README.md` sang repo phát hành** - bản bên đó là **được sinh ra**
(`python .claude/scripts/sinh_readme_phat_hanh.py`). Hướng dẫn bước 2 của `pypi_token.py --guide`
vẫn dạy `Copy-Item README.md`, **và nó sai** - xem mục 1 của file này.

⚠ **Endpoint tổng của PyPI trả về bản cũ trong nhiều giờ sau khi đẩy.**
`https://pypi.org/pypi/xime/json` vẫn liệt kê 14 bản và `info.version = 0.8.0` trong khi
`0.8.1` đã lên từ lâu. Đó là **cache**, không phải sự thật. Hỏi thẳng bản cần biết:

```bash
python -c "import urllib.request,json; print(json.load(urllib.request.urlopen('https://pypi.org/pypi/xime/0.8.1/json'))['info']['version'])"
```

⭐ Đây đúng là [luật 03](../../.claude/rules/03-mot-gia-tri-mot-nghia.md) ở tầng phép đo:
*"endpoint tổng không có 0.8.1"* mang **hai** nghĩa - *chưa ai đẩy* và *cache chưa kịp
cập nhật* - và chúng bắt người đọc làm hai việc ngược nhau. Lần này suýt đọc thành nghĩa
thứ nhất.

⚠ **Nhưng lần đẩy `0.8.2` thì endpoint tổng KHÔNG trễ** - hỏi ngay sau khi đẩy đã thấy
đủ 16 bản và `0.8.2`. Nên câu trên đọc là *cache CÓ THỂ trễ*, không phải *luôn trễ*;
cách hỏi thẳng một bản vẫn đúng trong cả hai trường hợp.

⛔⭐ **ĐÃ PUSH LÊN GITHUB 2026-08-26, và repo là CÔNG KHAI** - `origin/main` ở `64ee5d4`,
đo bằng `git ls-remote`. Dòng cũ ghi *"chưa push, và đó là cố ý"* **đã lỗi thời**.
Kéo theo **126 file `.claude/`** nay đọc được công khai, trong đó có
`docs/kiem-toan/0.7-bao-mat.md` (1400 dòng, 24 phát hiện kèm **mức độ và vị trí** trên 31
codebase, A1 còn thủng ở 19 app) và **12 PoC chạy được** ở `scripts/bao-mat/`.
Không có secret nào (đã quét), và PoC chỉ trỏ `localhost:8171` nên hôm nay chưa cắn ai -
nhưng đó đúng loại tài liệu mà tiêu chí của chính chủ dự án xếp là **không công bố**:
*"mô tả CHỖ YẾU kèm mức độ và vị trí"*, khác với *"mô tả THIẾT KẾ"*.
**Quyết định giữ hay lọc thuộc chủ dự án** - phiên nào cũng đừng tự xoá, tự lọc, hay tự
đổi lịch sử repo công khai.

⚠ **Tag thì CHƯA push** - `git ls-remote --tags origin` rỗng. `git push` không đẩy tag nếu
không bảo nó, nên GitHub không có `v0.8.0`/`v0.8.1`/`v0.8.2` nào.

**0.8.0 đã phát hành 2026-08-21**: kiểm toán sáu đợt, vá 28 mục, và **SHA256 gói trên
PyPI khớp từng bit** với gói dựng ở máy này.

Vì `xime` cài **editable** nên mã ở đây có hiệu lực ngay với **31 app** trên máy này -
chúng đã chạy `0.8.1` từ trước lúc phát hành.

✅ **Ba chuyến Linux đã nhận về, cả ba đối chứng từng byte:**

| Chuyến | Kết quả |
|---|---|
| Vá `0.8.0` (2026-08-21) | 80 file · **629/629 khớp**. [`docs/nhap/ban-giao-cho-phien-windows.md`](docs/nhap/ban-giao-cho-phien-windows.md) |
| Đo uvloop `0.8.1` (2026-08-22) | 25 file mới + 5 sửa · **660/660 khớp**. [`docs/nhap/ban-giao-cho-phien-windows-0.8.1.md`](docs/nhap/ban-giao-cho-phien-windows-0.8.1.md) và [`docs/kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](docs/kiem-toan/0.8.1-ket-qua-do-tren-linux.md) |
| ⭐ Chạy thử `0.8.2` (2026-08-25) | **676/676 khớp** khi nhận. Tìm ra **một lỗi thật chưa ai thấy**: dòng log khởi động khai `0 HTTP route(s)` với **mọi** ứng dụng Xime - đã vá + 4 test canh. Kèm một lỗi trong chính bộ benchmark. ⚠ **4 test canh của bản vá đó xanh vô điều kiện trên máy này** - `fastapi 0.135.1` ở đây vẫn dùng hình dạng phẳng, nên đừng thử đối chứng *"gỡ bản vá -> 4 đỏ"* ở Windows (mục 12). [`docs/kiem-toan/0.8.2-ket-qua-do-tren-linux.md`](docs/kiem-toan/0.8.2-ket-qua-do-tren-linux.md) |


### Kỳ vọng bộ test - HAI con số, theo hệ điều hành

| Nền tảng | `passed` | `skipped` | `failed` | **Tổng** |
|---|---|---|---|---|
| **Linux** | **2642** ✅ đo 2026-08-25 | 7 | 0 | **2649** |
| **Windows** | **2625** ✅ đo 2026-08-26 | 24 | 0 | **2649** |

⛔ **Con số `2552 / 2534 / tổng 2558` ở bản trước là của bản ĐÃ PHÁT HÀNH `0.8.1`,
đừng dùng để nghiệm thu nữa** - nhánh chưa phát hành đã đi xa hơn 91 test. Bảng chạy
dồn ở mục dưới mới là thứ theo kịp từng việc.

✅ Con số Windows **trước đây là suy ra, nay ĐÃ ĐO** (2026-08-26): `2625 passed / 24 skipped /
0 failed`, **khớp đúng dự đoán của chuyến Linux**. Đó là một suy luận đúng, nhưng nó chỉ
thành phép đo sau khi có người chạy.

📌 *Lịch sử:* **cộng 24 từ `0.8.0` lên `0.8.1`** (tổng `2534` -> `2558`): **16** của
`tests_temp/bootstrap/test_event_loop.py` (uvloop) và **8** của
`tests_temp/ws/test_ws_availability.py` (cảnh báo thiếu thư viện WebSocket).

> ## ✅⭐ ĐỢT ĐO uvloop 0.8.1 TRÊN LINUX: XONG 2026-08-22
>
> Kết quả đầy đủ: **[`docs/kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](docs/kiem-toan/0.8.1-ket-qua-do-tren-linux.md)**.
> Con số Linux `2552` không còn là suy ra nữa - **đã đo, khớp đúng dự kiến**, và
> bộ test cũng xanh **khi chạy dưới uvloop thật** (2552/6/0).
>
> | | |
> |---|---|
> | Đo 1 TLS · Đo 2 `SO_PEERCRED` · Đo 3 `share_load` socket kế thừa | **ĐẠT** cả ba |
> | Sửa code | **đúng một test lỗi thời**, không đụng mã sản phẩm |
> | mypy | **41 lỗi = đúng mốc 0.8.0**, không thêm cái nào |
>
> ⛔⭐ **Đo 4 lật một giả định của chính bản 0.8.1: uvloop KHÔNG tăng tốc REST
> của Xime, nó làm CHẬM khoảng 10%** (0.91x, dao động dưới 2%, 5/6 ô của ma trận
> sáu hình dạng tải cùng chiều).
>
> ⭐⭐ **Nhưng ranh giới thật KHÔNG phải "REST hay WebSocket" - đã đo trên cùng
> một app Xime:**
>
> | Loại việc | uvloop |
> |---|---|
> | Xử lý request kiểu HTTP (REST 0.91x · **bắt tay WebSocket 0.93x**) | **lỗ ~8-9%** |
> | Truyền trên kết nối đã mở (**tin nhắn WebSocket 1.11x** · loop trần 1.38x) | **lãi 11-38%** |
>
> Bắt tay WebSocket là request HTTP-upgrade nên nó rơi **cùng phía với REST**,
> khác phía với chính những tin nhắn chạy sau nó trên cùng socket đó.
> **Vẫn khuyến nghị GIỮ** - năm adapter còn lại đều sống trên kết nối đã mở.
>
> ⭐ **Ca thứ BA của "lỗi máy phát triển không thể thấy"** (sau C4/C5 của 0.8.0):
> `test_linux_never_switches` khẳng định `worker_loop_factory(...) is None` trên
> Linux. Nó **xanh trên Windows** chỉ vì ở đó `uvloop_factory()` luôn trả `None`,
> nên dù `sys.platform` bị monkeypatch thành `"linux"` thì hàm vẫn trả `None` -
> **phép đo đó không đo nền tảng được monkeypatch, nó đo nền tảng thật**.
>
> ⚠ **Cách chạy bộ test dưới uvloop trong file bàn giao KHÔNG hoạt động và nó
> xanh giả** - `pytest-asyncio` 1.4 không nhận fixture `event_loop_policy` khai
> trong plugin nạp bằng `-p`. Bắt được bằng đối chứng hai chiều; cách chạy được
> ghi ở mục 5.3 của báo cáo.
>
> ## ⭐ BENCHMARK: framework nay CÓ bộ đo hiệu năng
>
> Chủ dự án yêu cầu 2026-08-22, dựng từ phép đo 4 ở trên. Trước đây framework
> **không có benchmark nào**.
>
> | | |
> |---|---|
> | Bộ đo | [`scripts/benchmark/`](scripts/benchmark/README.md) - `python .claude/scripts/benchmark/run_all.py` |
> | Kết quả + cách đọc | [`docs/ghi-chep/benchmark-hieu-nang.md`](docs/ghi-chep/benchmark-hieu-nang.md) |
>
> Năm tầng chồng lên nhau, nên **hiệu số giữa hai dòng là giá của đúng lớp nằm
> giữa chúng**: loop trần -> HTTP (asgi/fastapi/xime) -> lõi (DI, Store, RefData)
> -> cụm nhiều tiến trình -> WebSocket. Ba con số đáng nhớ:
>
> | | |
> |---|---|
> | **Xime = 41% thông lượng của ASGI trần** | FastAPI ở giữa (66%). Giá của DI + controller + middleware |
> | **Cụm mở rộng gần tuyến tính** | 2.00x với 2 tiến trình, **3.88x với 4**, và **N/N tiến trình thật sự nhận việc** |
> | `RefData.read()` nhanh hơn `Store.get()` **~60 lần** | Ranh giới *có nguồn bền vững hay không* trùng với ranh giới hiệu năng |
>
> ⛔ **Luật của bộ đo, và là phần không lỗi thời theo máy: mỗi phép đo phải tự
> khai nó đo được cái gì.** Hai lần trong buổi dựng, một con số trông hợp lý hoá
> ra đang đo **dụng cụ đo** - và hai ca đó cho ra **cùng một hình dạng kết quả**
> trong khi chỉ một cái có giá trị. Nên kết quả có **bốn** nhãn, và
> `CHUA_KET_LUAN_DUOC` **không được gộp vào** `SERVER_BOUND`.

⚠⚠ **Hai con số `2534` trong bảng này KHÔNG cùng nghĩa, và đây đúng là kiểu nhầm repo
này hay dính:** `2534` cũ là **TỔNG của 0.8.0**; `2534` mới là **`passed` của Windows ở
0.8.1**. Trùng số, khác trục. Nghiệm thu thì so **tổng 2558**, đừng so `passed`.

⛔ Con số **2528 / 2510 / tổng 2534** là của **0.8.0**, đừng dùng để nghiệm thu nữa.

✅ Con số Linux **trước đây là suy ra, nay ĐÃ ĐO** (2026-08-22) và **khớp đúng dự
kiến**. Đó là một suy luận đúng, nhưng nó chỉ thành phép đo sau khi có người chạy.

⚠⚠ **Đừng dùng MỘT con số `passed` làm tiêu chí đạt.** Nó phụ thuộc hệ điều hành, nên
một nhãn kiểu *"kỳ vọng 2534"* mang hai giá trị - đúng
[luật 03](../../.claude/rules/03-mot-gia-tri-mot-nghia.md) ở tầng con số nghiệm thu.
**Thứ bất biến giữa hai bên là TỔNG `2558`, cộng `0 failed`.**

⚠⚠ **`2558` là mốc của bản ĐÃ PHÁT HÀNH `0.8.1`. Nhánh chưa phát hành đã đi xa hơn
- đừng dùng `2558` để nghiệm thu một cây làm việc đang có việc dở.** Tổng chạy dồn:

| Sau việc gì | Tổng | Windows `passed` |
|---|---|---|
| `0.8.1` phát hành | 2558 | 2534 |
| C8 + C9 | 2564 | 2540 |
| `public_paths` tiền tố + dòng log xác thực | 2595 | 2571 |
| sửa chữ dòng log (hậu kiểm 2026-08-23) | 2602 | 2578 |
| con mồ côi + log "ai giết" | 2617 | 2593 |
| `BaseModel` ra khỏi DI + `exclude_segments` | 2636 | 2612 |
| tài liệu hướng dẫn khớp lại bản hiện tại (`cli_docs` tự sinh thêm 4) | 2640 | 2616 |
| **export `public_health_paths`** | **2645** | **2621** |
| **vá phép đếm route HTTP** (chuyến Linux 2026-08-25) | **2649** | **2625** |
| công tắc `xime.dev`, A4 (2026-08-27) | 2682 | 2658 |
| **access log theo `xime.dev`** (2026-08-28) | **2691** | **2667** |

📌 Con số này lỗi thời mỗi lần thêm test, đúng như mọi con số khác trong file. Phép
kiểm không lỗi thời vẫn là: **chạy trước, chạy sau, so trên CÙNG một máy.**

⭐ **Chênh lệch nay đi HAI chiều, không còn một chiều như trước** (đo 2026-08-25):

| Chiều | Số | |
|---|---|---|
| Windows bỏ qua, Linux chạy | **18** | bảng ngay dưới |
| **Linux bỏ qua, Windows chạy** | **1** | `processes/test_orphan_guard.py:222` - *"chỉ đúng trên Windows"*, có từ `0.8.2` |

Phép tính đúng vì vậy là `Windows + 18 - 1 = Linux`, không phải `+ 18`.

Mười tám test Windows bỏ qua, đã đếm từng cái:

| Tệp | Số | Lý do bỏ qua |
|---|---|---|
| `lmdb/test_file_mode.py` | 7 | POSIX permission bits only |
| `link/test_cleanup.py` | 3 | `/dev/shm` chỉ có trên Linux |
| `storage/test_local_storage.py` | 2 | POSIX permission bits only |
| `socket/test_socket.py` | 2 | Linux Unix sockets + msgpack |
| `processes/test_socket_mode.py` | 2 | unix socket only |
| `web/test_tls.py` | 1 | `chmod 000` không chặn đọc trên Windows |
| `link/test_va_kiem_toan_08.py` | 1 | `/dev/shm` only |

📌 **Sáu lượt bỏ qua của Linux KHÔNG phải chuyện nền tảng** - chúng bỏ qua ở **cả hai**
bên vì thiếu dịch vụ ngoài: `storage/test_s3_integration.py` (4, không có S3 ở
`127.0.0.1:9000`) và `mqtt/test_integration.py` (2, không có broker ở `127.0.0.1:1883`).
Bật hai dịch vụ đó lên thì Linux ra `2558/0`, Windows ra `2540/18`.

⛔ Con số **2518** ở bản trước **SAI** - nó ghi giữa chừng commit `1821106`, trước khi
file test cuối của chính commit đó xong. HEAD sạch đo lại là **2520**; cộng 8 test canh
của đợt 6 thành 2528. Đừng tin lại con số cũ.

### Kiểm toán 0.8: 28 mục đã vá, hai trong đó Windows KHÔNG THỂ thấy

| | |
|---|---|
| **C4** | Ngữ cảnh `multiprocessing` lệch nhau → **toàn bộ đa tiến trình chết trên Linux**. 26 test đỏ ở đó, 0 đỏ trên Windows |
| **C5** | `SocketAdapter.assign_slot()` ném `AttributeError` - `mypy` là thứ duy nhất tìm ra |

⭐⭐ **Bài học phải nhớ cho mọi bản sau: có những lớp lỗi mà máy phát triển
KHÔNG THỂ nhìn thấy về mặt cấu trúc.** Không phải test yếu - điều kiện gây lỗi không
tồn tại trên Windows. Một lượt chạy bộ test **trên Linux** nên là điều kiện phát hành.

Báo cáo: [`docs/kiem-toan/0.8-kiem-toan-toan-dien.md`](docs/kiem-toan/0.8-kiem-toan-toan-dien.md)
· sổ đo: [`docs/kiem-toan/0.8-cho-do-tren-linux.md`](docs/kiem-toan/0.8-cho-do-tren-linux.md)

### ⛔ Đợt 6 (2026-08-21): hai lỗ do REPO NGOÀI báo, cả hai do chính 0.8 sinh ra

Năm đợt trên là **tự soi**. Đợt này do `Base Platform/data` báo sau khi họ di trú thật
sang khối `process:`. Báo cáo gốc:
[`docs/bao-cao-van-de-tu-repo-ngoai/`](docs/bao-cao-van-de-tu-repo-ngoai/README.md).

| | |
|---|---|
| **C6** 🔴 | **gRPC tụt xuống PLAINTEXT khi di trú sang `process:`.** Đường phẳng chép `grpc.tls` vào ô, đường `process:` thì không, và adapter **không có đường lui**. Đổi cách khai địa chỉ - không đụng khối `grpc:` - là **mất mTLS**, và client cũ **vẫn gọi được** nên không gì gãy |
| **C7** 🟡 | **Không adapter nào có mốc dương trong log.** gRPC có đúng 2 lệnh log, cả hai là `warning`; socket có 0. Cụm gRPC **khoẻ** sinh log **giống hệt** cụm gRPC **hỏng** |

⭐ **Hai lỗi che nhau**: khi mọi thứ log nói về gRPC đều là cảnh báo thì không có mốc
dương nào để so, nên C6 lại càng khó thấy. C7 tự xếp mức thấp, nhưng ghép với C6 thì không.

⭐ **Framework đo lại rộng hơn báo cáo ở CẢ HAI mục** - có **ba** adapter chứ không phải
hai, và gRPC là cái **duy nhất** lệch (`socket` cũng kế thừa khối chung). Tức là **sót**,
không phải lựa chọn thiết kế.

⚠ **Bài học về chỗ mù**: cả hai nằm ở **ranh giới giữa hai cách khai cấu hình**, nơi mỗi
bên đều đúng khi xét riêng. Năm đợt tự soi đọc từng dòng của từng bên và không thấy - phải
có người **di trú thật** mới lộ ra.

⚠⚠ **Đừng tin bảng trạng thái ở trên, kiểm bằng lệnh.** Cùng một khuôn lỗi đã lặp
**năm lần** ở repo này: *"chưa push PyPI"* · *"0.7.0 chưa commit"* · *"0.7.1 đã phát
hành"* · *"pyproject = 0.7.2"* · *"0.8.0 chưa phát hành"*. Mỗi lần đều đúng lúc viết
rồi bị bỏ quên, và lần thứ năm sống được đúng bốn ngày.

```bash
python -c "import urllib.request,json; print(sorted(json.load(urllib.request.urlopen('https://pypi.org/pypi/xime/json'))['releases']))"
grep '^version' pyproject.toml
git tag -l | sort -V | tail -3
pytest -q
```

## Ba thư mục, đừng nhầm

| Thư mục | Là gì |
| --- | --- |
| `d:\code\xime\xime framework` | **repo PHÁT TRIỂN** (chỗ này): code, `tests_temp/`, `.claude/`, két token `pypi_token.py`. Remote GitHub `nguyen-huu-thang/xime-framework` |
| `D:\code\xime framework\upload` | **repo PHÁT HÀNH**: chỉ thứ đóng gói. Build + upload PyPI ở đây. Repo git riêng, **không có remote** |
| `D:\code\xime framework\website` | **trang xime-framework.org** (Next.js xuất tĩnh). Không dính gì tới gói PyPI |

**Repo phát hành CHỈ được đồng bộ khi có bản mới để phát hành** - nó giữ đúng bản đã lên
PyPI, nên nó lệch với repo phát triển trong lúc làm dở là **bình thường**, không phải nợ.
Đừng đồng bộ giữa chừng. Lệnh upload:

```bash
python pypi_token.py --upload "D:/code/xime framework/upload/dist"
python pypi_token.py --guide     # hướng dẫn phát hành 8 bước
```

⚠ **Chủ dự án tự đẩy PyPI, tự commit, tự tag. Đừng làm hộ.**

## ⚠ `xime.__version__` trả lời câu "lần cuối ai CÀI LẠI gói"

Không phải câu *"mã đang chạy là bản nào"*. `xime/__init__.py` đọc
`importlib.metadata.version("xime")`, chỉ fallback sang hằng số trong mã khi metadata
vắng. Cài editable thì **mã nạp thẳng từ repo (luôn mới), còn metadata đóng băng tại lần
`pip install -e` cuối**. Nó từng đứng ở `0.6.3` suốt hai bản.

Đó là một giá trị mang hai nghĩa, đúng
[luật 03](../../.claude/rules/03-mot-gia-tri-mot-nghia.md). **Cách kiểm đúng là hỏi code,
đừng hỏi số:**

```python
from xime.core.refdata import RefData     # co -> ma la 0.8
from xime.starters.jwt import JwtKeyProvider   # co -> ma tu 0.7.2 tro len
from xime.core.contract import stream          # co -> ma tu 0.7.1 tro len
```

⏳ Còn treo, thẩm quyền thuộc chủ dự án: **đổi thứ tự ưu tiên của `__version__`** - đó là
đổi một giá trị công khai mà 31 codebase đọc được.

## Nhóm chat

| Chỗ | Dùng khi |
| --- | --- |
| `D:\temp\xime\nhom-chat\CHAT-CHUNG.md` | **loa** - sắp đổi thứ nhiều người dùng, lỗi cắt ngang nhiều repo. **Dùng nhiều nhất** ở repo này |
| `D:\temp\xime\nhom-chat\leader-framework\framework-gui-leader.md` | file **tôi ghi**, leader đọc |
| `.../leader-framework/leader-gui-framework.md` | file **leader ghi**, tôi đọc. Đừng sửa |

**Luật: chỉ ghi vào file mang tên mình, tin mới nhất trên cùng, lấy giờ bằng
`Get-Date -Format "HH:mm"`.** Cần kênh riêng với repo khác thì **xin leader mở**, đừng tự
tạo. Bối cảnh: [`docs/ghi-chep/lam-viec-voi-nhom.md`](docs/ghi-chep/lam-viec-voi-nhom.md).

⚠ **Ranh giới chủ dự án dặn 2026-08-04:** sửa lỗi / nâng cấp lặt vặt thì **phối hợp với
leader**; **quyết định cấu trúc, đổi cấu trúc, hoặc thứ ảnh hưởng lớn tới framework thì
HỎI CHỦ DỰ ÁN TRƯỚC**.

## Đọc gì

| Muốn biết | Đọc |
|---|---|
| **Bản đồ toàn bộ tài liệu** | [`docs/README.md`](docs/README.md) |
| Việc X làm ở bản nào | [`docs/lo-trinh-phien-ban.md`](docs/lo-trinh-phien-ban.md) |
| Framework LÀ GÌ | [`docs/thiet-ke/01-tong-quan.md`](docs/thiet-ke/01-tong-quan.md) |
| **Sửa mảng X thì dễ phá chỗ nào** | [`docs/thiet-ke/01-tong-quan.md`](docs/thiet-ke/01-tong-quan.md) mục 16 |
| Kiến trúc cho người ngoài đọc | [`../CLAUDE.md`](../CLAUDE.md) |

**Luật code của repo này** - đọc trước khi sửa:

| | |
|---|---|
| [`rules/coding.md`](rules/coding.md) | DI, constructor injection, điều kiện đăng ký class, fail fast |
| [`rules/transaction.md`](rules/transaction.md) | `async with self.transaction()`, khối chỉ đọc `read_only()` |
| [`rules/interface-binding.md`](rules/interface-binding.md) | `Protocol` + `bind` tường minh, dynamic binding |
| [`rules/config-discovery.md`](rules/config-discovery.md) | `configure_*` gọi tường minh, **không auto-scan config** |
| [`rules/module-level-code.md`](rules/module-level-code.md) | Mức module chỉ **KHAI BÁO**, không **LÀM** - mọi thứ ngoài `if __name__` chạy **`N+1`** lần |
| [`rules/background-tasks.md`](rules/background-tasks.md) | `create_task` chưa chạy dòng nào; **mock không mang ngữ nghĩa của thứ nó thay thế** |

---

# Việc đang chờ

## 1. ✅ Phát hành `0.8.1` - XONG 2026-08-22

Không còn việc gì ở mục này. Giữ lại phần đối chứng vì lần sau phát hành sẽ chạy y hệt.

| Bước | Kết quả |
|---|---|
| Repo phát triển | commit `d5b5806`, tag `v0.8.1`, cây làm việc sạch |
| Repo phát hành | mã 291 file khớp từng byte, README **sinh bằng script**, commit `4ac504f`, tag `v0.8.1` |
| Gói | `twine check` PASSED · sdist 294 mục · wheel 247 mục · **0 rò rỉ** `.claude/` `tests_temp/` `pypi_token.py` |
| So với `0.8.0` trên PyPI | **thêm đúng 4 file, bỏ 0**: `docs/{vn,en}/event-loop.md` · `xime/core/bootstrap/_loop.py` · `xime/adapters/web/ws/_availability.py` |
| Đẩy PyPI | **SHA256 khớp từng bit** cả `.whl` lẫn `.tar.gz` |
| Cài từ PyPI vào venv trắng | chạy được, `__version__ = 0.8.1`, cả hai module mới có mặt |
| Trang PyPI | huy hiệu `pypi/v` có · dòng *Event loop* có · **0 liên kết tương đối còn sót** |

### ⛔ Hai chỗ `pypi_token.py --guide` nói SAI - nó viết trước khi có trình sinh README

**Chỗ nguy hiểm:** bước 2 bảo `Copy-Item "$src/README.md" "$dst/README.md"`. README của
repo phát hành là bản **được SINH RA** (huy hiệu `pypi/v` + mọi liên kết tương đối đổi
thành URL GitHub tuyệt đối). Chép đè là mất cả hai, và `](LICENSE)` trên PyPI trỏ vào hư
không. Đợt này đã sinh bằng script:

```bash
python .claude/scripts/sinh_readme_phat_hanh.py          # ghi
python .claude/scripts/sinh_readme_phat_hanh.py --kiem   # chỉ so
```

**Chỗ vô hại:** nó bảo chép `README-vn.md` - file đó **không còn** trong danh sách trắng
sdist. Bỏ qua.

⏳ Sửa `--guide` cho khớp thực tế là việc còn mở, thuộc chủ dự án (`pypi_token.py` là két
token, không ai khác nên đụng vào).

### 1b. Nợ cũ, không thuộc `0.8.1`

| # | Việc |
|---|---|
| 1 | **Một stash từ 2026-06-03** (`stash@{0}`, WIP trên `ba64bd5`, 145 file). Không phải của đợt nào gần đây - dọn hay giữ là quyết định của chủ dự án |
| 2 | **197 lỗi `ruff` trong `tests_temp/`**, có từ trước `0.8.1` (Linux đo HEAD của chính nó: 199 trước và sau khi chép). **113 cái tự sửa được**. Nên là **một commit riêng** vì nó đụng ~150 file test |
| 3 | `.gitattributes` **rỗng**, nên `git status` phồng lên vì lật line-ending. Không phải việc của `0.8.1` |

⚠ **Đừng tin bảng trên, kiểm bằng lệnh** - lý do ở mục [Trạng thái](#trạng-thái).

```bash
# Hoi THANG ban can biet - endpoint tong bi cache nhieu gio sau khi day
python -c "import urllib.request,json; print(json.load(urllib.request.urlopen('https://pypi.org/pypi/xime/0.8.1/json'))['info']['version'])"
grep '^version' pyproject.toml
git tag -l | sort -V | tail -3
git stash list
```


### Lịch sử đợt kiểm toán 0.8 - KHÔNG ở file này

File này trả lời *"hôm nay đứng ở đâu"*. Chuyện đã xảy ra nằm ở:

| Muốn biết | Đọc |
|---|---|
| 28 phát hiện, phép đo, bản vá, đối chứng | [`docs/kiem-toan/0.8-kiem-toan-toan-dien.md`](docs/kiem-toan/0.8-kiem-toan-toan-dien.md) |
| 12 mục chỉ đo được trên Linux, kèm kết quả | [`docs/kiem-toan/0.8-cho-do-tren-linux.md`](docs/kiem-toan/0.8-cho-do-tren-linux.md) |
| Chín commit của đợt Linux, nguyên văn lý do | [`docs/kiem-toan/0.8-nhat-ky-va-tren-linux.md`](docs/kiem-toan/0.8-nhat-ky-va-tren-linux.md) |
| Trình tự nhận bản vá và phát hành | [`docs/nhap/ban-giao-cho-phien-windows.md`](docs/nhap/ban-giao-cho-phien-windows.md) |
| Rà đóng gói trước phát hành | [`docs/kiem-toan/0.8-truoc-phat-hanh.md`](docs/kiem-toan/0.8-truoc-phat-hanh.md) |

### Sinh lại README của repo phát hành

Hai bản README khác nhau ở **hai quy tắc máy móc** (huy hiệu PyPI · liên kết tương đối
thành URL GitHub tuyệt đối). Đừng sửa tay - bản `0.7.2` đã trôi vì sửa tay, nó còn dấu
gạch dài mà repo này bỏ từ lâu và thiếu năm mục tài liệu của 0.8.

```bash
python .claude/scripts/sinh_readme_phat_hanh.py          # ghi
python .claude/scripts/sinh_readme_phat_hanh.py --kiem   # chỉ so
```

⚠ **PyPI chỉ hiển thị ĐÚNG MỘT README** - cái khai ở `[project] readme`. Không có mô tả
đa ngôn ngữ. Bản tiếng Việt tới được người đọc **chỉ qua đường dẫn** trong dòng chuyển
ngôn ngữ, nên đừng bỏ dòng đó đi. Vì vậy `/README-vn.md` cũng đã bị gỡ khỏi danh sách
trắng sdist: một mục khai mà không bao giờ xảy ra thì tệ hơn là không khai.


## 2. ⚠ A1 fail-open JWT - gốc đã lấp, 19 app vẫn thủng

Framework đã lấp khoảng trống ở **0.7.2** (`JwtKeyProvider`, verify theo `kid`,
`configure_jwt()` không có nguồn khoá thì **nổ lúc khởi động**). Chi tiết:
[`docs/ghi-chep/jwt-keyset-va-trung-tinh.md`](docs/ghi-chep/jwt-keyset-va-trung-tinh.md).

⚠⚠ **Đừng đọc "A1 xong" thành "A1 đã an toàn".** Lỗ hổng nằm trong `config/jwt.py` **của
từng app** (không lấy được khoá -> không gọi `configure_middleware`), mà framework không
với tới đó. Bản vá **không sửa app nào cả** - nó **xoá lý do tồn tại** của lỗ: trước đây
họ phải chọn giữa *"có sẵn chuỗi PEM lúc khởi động"* và *"không có middleware nào"*; nay
có ô thứ ba.

**Vá `saas-foundation/template` TRƯỚC** - 18 app kia là nợ đứng yên, template là nợ **đang
sinh thêm**. Migration chỉ là xoá `TrustJwtAuthMiddleware` (105 dòng mã verify chép tay),
giữ nguyên `TrustKeyProvider` + `JwtKeySet`.

⚠ Chỗ họ phải quyết khi chuyển: `JwtKeySet.resolve(kid)` hiện làm *"theo kid nếu có, ngược
lại **thử tất cả**"*. Framework nay không suy diễn khi `kid` vắng - nó gọi `keys(None)` và
tin câu trả lời. *"Thử tất cả"* biến `kid` từ phép định tuyến thành thứ trang trí.

## 3. 0.8.1 - **uvloop trên Linux, và CHỈ có nó**

> ✅ **Chủ dự án chốt 2026-08-22: tách 0.8.1 và 0.8.2.** Nguyên văn: *"tôi giờ chỉ cần
> tăng tốc uvloop, mấy cái fieldbus + MQTT + drain() tôi cũng chưa cần bây giờ."*

Thiết kế **đã đủ để code, không cần thêm vòng thiết kế nào**:
[`docs/sap-toi/tang-toc-uvicorn-uvloop.md`](docs/sap-toi/tang-toc-uvicorn-uvloop.md).

**Vấn đề:** `pip install xime[web]` kéo `uvicorn[standard]`, nên uvloop **đã nằm sẵn
trên đĩa ở mọi cài đặt Linux** - và **chưa bao giờ chạy**. Xime gọi `Server.serve()`,
còn `loop_factory` chỉ được đọc trong `Server.run()`. Nhìn `pip list` thấy đủ bốn gói
tăng tốc rồi kết luận *"đã bật"* là sai, và **không gì báo**.

| # | Việc | |
|---|---|---|
| 1 | `xime/core/bootstrap/_loop.py` + `uvloop_factory()` | ✅ **XONG 2026-08-22** |
| 2 | Ghép vào `worker_loop_factory`, tách **ba nhánh thật**. ⛔ nhánh Windows selector (`WinError 87`) giữ nguyên từng chữ | ✅ **XONG** |
| 4 | Log **loop đang chạy thật** trong `_run_async()` | ✅ **XONG** |
| 5 | Test canh - `tests_temp/bootstrap/test_event_loop.py`, **16 test** | ✅ **XONG** |
| 6 | **Bốn phép đo trên Linux** | ✅ **XONG 2026-08-22** - ba ĐẠT, phép thứ tư lật một giả định. [`docs/kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](docs/kiem-toan/0.8.1-ket-qua-do-tren-linux.md) |
| 7 | WARNING khi có route `@ws` mà thiếu thư viện WS (việc phụ, không thuộc uvloop) | ✅ **XONG 2026-08-22** - `ws/_availability.py`, 8 test, 3 đối chứng |
| 8 | `CHANGELOG.md` + `pyproject` lên `0.8.1` | ✅ **XONG 2026-08-22** |

**Nghiệm thu Windows** (đo lại 2026-08-22 sau khi nhận bản vá Linux): **2534 passed /
24 skipped / 0 failed = tổng 2558** · `ruff check xime/` và `.claude/scripts/benchmark/`
**sạch** · chạy thật một tiến trình in `event loop: asyncio.windows_events.ProactorEventLoop`.

**Nghiệm thu Linux:** **2552 / 6 / 0 = tổng 2558**, và **cũng 2552/6/0 khi chạy dưới
uvloop thật** · `mypy xime/` **41 lỗi = đúng mốc 0.8.0**, bản vá không thêm cái nào.

⚠ `ruff check tests_temp/` ra **197 lỗi** và **luôn như vậy từ trước** (Linux đo HEAD
của chính nó: 199, trước và sau khi chép đều thế). **Không phải nợ của 0.8.1** - câu
*"ruff sạch"* ở repo này đúng cho `xime/`, không đúng cho `tests_temp/`. Dọn hay không
là quyết định của chủ dự án, và nên là **một commit riêng** vì nó đụng ~150 file test.

⭐ **Bốn đối chứng, và cái thứ tư tìm ra lỗ hổng thật:** gỡ đường uvloop -> 3 đỏ · quay
về điều kiện gộp của 0.8.0 -> 3 đỏ · bỏ `loop_factory=` -> 2 đỏ · **xoá lời gọi log ->
0 đỏ**. Bản test đầu canh **hàm** chứ không canh **việc hàm được gọi**; đã vá bằng một
test chạy vòng đời thật. Chi tiết: mục 12 của
[`docs/sap-toi/tang-toc-uvicorn-uvloop.md`](docs/sap-toi/tang-toc-uvicorn-uvloop.md).

⛔ **Việc số 3 của tài liệu (sửa đường vào thứ hai) KHÔNG còn tồn tại** - 0.8.0 đã hợp
nhất cả ba nhánh `run()` về `Application._run_worker()`, nơi có đúng một `asyncio.run`.
Rủi ro *"vá một nửa"* nay không tồn tại **về mặt cấu trúc**.

⚠⚠ **Linux là để CHẠY THỬ LẦN ĐẦU, không phải nghiệm thu** - và chuyến 2026-08-22 đã
chứng minh câu đó bằng một ca thật. uvloop không có wheel Windows, nên ở đây
`uvloop_factory()` **luôn trả `None`** và nhánh mới **không chạy một lần nào**; bộ test
Windows chỉ chứng minh được **không hồi quy**.

⭐⭐ **Ca thứ BA của "lỗi máy phát triển không thể thấy"** (sau C4/C5 của 0.8.0):
`test_linux_never_switches` khoá `worker_loop_factory(...) is None` trên Linux và
**xanh trên Windows** kể cả sau bản vá - vì ở đây `uvloop_factory()` trả `None` nên dù
`sys.platform` bị monkeypatch thành `"linux"` thì hàm vẫn trả `None`. **Phép đo đó không
đo nền tảng được monkeypatch, nó đo nền tảng thật.** Nó còn **mâu thuẫn trực tiếp** với
`tests_temp/bootstrap/test_event_loop.py`, mà không ai thấy vì hai file **không bao giờ
cùng đỏ trên một máy**.

> **Đề nghị cho mọi bản sau: một lượt chạy bộ test trên Linux là điều kiện phát hành.**
> Nay có ba ca thật, ba cơ chế khác nhau, cùng một hình dạng.

⛔ **Không làm công tắc**, không khai `uvloop` thành phụ thuộc riêng, không mong nó giúp
gRPC (`grpcio` chạy trên core C riêng).

## 3b. `0.8.2` - ba báo cáo từ repo ngoài

> ✅ **Chủ dự án chốt 2026-08-22**, sau khi đọc [ba báo cáo từ repo ngoài](docs/bao-cao-van-de-tu-repo-ngoai/README.md)
> và [phần trả lời](docs/bao-cao-van-de-tu-repo-ngoai/tra-loi-2026-08-22.md).
> Fieldbus + MQTT + `drain()` **lùi lại**, xem mục 3c.

⛔⭐ **Cách làm chủ dự án dặn, áp cho cả bản này và về sau:**

> *"Tôi muốn vá dần dần, nhiều lần commit vá. Rồi commit `v0.8.2` sau cùng. Không việc
> gì phải dồn hết vào bản commit `v0.8.2`."*

Nghĩa là **mỗi việc xong thì giao ngay một lần**, không gom lại chờ ngày phát hành.
Commit mang số hiệu bản là commit **cuối cùng** và chỉ nâng số - không phải cái chở
toàn bộ nội dung. Hệ quả cho phiên: xong một mục thì dừng, báo, để chủ dự án commit,
rồi mới sang mục kế.

### Đã vá, commit `07de5a2`

| # | Việc | Trạng thái |
|---|---|---|
| **C8** | `xime check config` tố oan khoá hợp lệ - khối `socket` thiếu 6 khoá **và thừa 1** (`socket.path` không đường nào đọc), khối `lmdb` thiếu `file_mode`/`dir_mode`. Kèm **test canh tầng khoá** canh cả hai chiều | ✅ **XONG 2026-08-22** |
| **C9** | Gợi ý lỗi thiếu đăng ký dẫn sai đường - `RefData` và handler `ProcessLink` **không bao giờ** tới được bằng `dependency.scan()` | ✅ **XONG 2026-08-22** |

Đo: **2540 passed / 24 skipped / 0 failed = tổng 2564** (`2558 + 6` test mới) ·
`ruff check xime/` sạch · `mypy` **49 lỗi trước và sau bản vá, không thêm cái nào**.

> ⚠⚠ **`mypy` NAY CÀI ĐƯỢC TRÊN MÁY NÀY** (chủ dự án duyệt 2026-08-22), nhưng con số
> của nó **KHÔNG so được với mốc 41 ghi ở mục 1 và mục 3**.
>
> | | |
> |---|---|
> | Linux, chuyến `0.8.1` | **41 lỗi** |
> | Windows, `mypy 2.3.1`, **cùng một HEAD** | **49 lỗi** |
>
> Chênh 8 là **phiên bản mypy khác**, không phải code khác - đo bằng cách stash bản vá
> rồi chạy lại trên HEAD sạch: **49 trước, 49 sau**.
>
> ⭐ Nên *"mypy 41 lỗi"* là một tiêu chí nghiệm thu **không bất biến** - nó phụ thuộc
> phiên bản công cụ, đúng như *"kỳ vọng 2534"* phụ thuộc hệ điều hành. Phép kiểm dùng
> được là **so trước/sau trên CÙNG một máy, CÙNG một mypy**, không phải so với một con
> số ghi trong tài liệu.

### Đã vá 2026-08-23, commit `548c731` - con mồ côi và log "ai giết"

Báo cáo thứ hai trong ngày, từ `Service ngang/kho` sau lượt e2e thật đầu tiên. Ba mục,
và **đo lại thì mục 3 là triệu chứng của mục 1** - họ báo rời nhau, hoá ra một lỗi.

| # | Việc | Trạng thái |
|---|---|---|
| **1** | **Con tự đi khi cha chết** - `xime/core/bootstrap/_orphan.py`, cắm ở `ClusterMember.listen()` | ✅ **XONG** |
| **3** | Log lúc con chết khai **ai giết**, không chỉ khai mã thoát | ✅ **XONG** |
| 2 | 401 lạnh máy đếm theo tiến trình | ⛔ **KHÔNG phải lỗi framework** - xem dưới |

**Đo:** **2593 passed / 24 skipped / 0 failed = tổng 2617** (`2602 + 15` test mới) ·
`ruff check xime/` sạch.

#### ⭐⭐ Vì sao đây là VÁ LỖI chứ không phải thêm tính năng

`_supervisor.py` đã khai con mồ côi là kết cục tệ nhất, **trong docstring của chính nó**:

> *"cha chết ngay còn con sống tiếp mồ côi - vẫn giữ cổng, vẫn phục vụ, và không ai dựng
> lại chúng nữa. Đúng thứ tệ nhất: hệ thống trông như đã tắt mà thực ra chưa."*

Nhưng lớp phòng thủ ở đó là **bắt tín hiệu**, nên nó chỉ che cái chết *lịch sự* của cha.
`SIGKILL` / `Stop-Process -Force` / cha sập / OOM - **không đường nào bắt được**. Tức
framework đã tự đặt ra một bất biến rồi chỉ giữ được một nửa. Bản vá không thêm khoá cấu
hình nào, không thêm tên công khai nào; nó **khôi phục một lời hứa đã có**.

⭐ Cơ chế là **thư viện chuẩn**: `multiprocessing.parent_process()` mang sentinel của cha,
`join()` chặn tới đúng lúc cha thoát. Linux là đầu ống thừa kế, Windows là `HANDLE` tới
tiến trình cha. Đo thật trên cụm 3 tiến trình chia chung cổng: `-Force` lên cha thì cả ba
con thoát, cổng được trả, **0 traceback**.

⛔ **KHÔNG làm thứ họ đề nghị chính** (thêm `--xime-process=api-2` vào dòng lệnh con): đó
là **tính năng** (bề mặt công khai mới ở bản alpha cuối, và dòng lệnh con do
`multiprocessing.spawn` sinh nên đổi nó là vá vào ruột CPython), **và nó vá triệu chứng**.
Câu hỏi đúng không phải *"làm sao tìm con mồ côi"* mà là *"vì sao có con mồ côi"*.

#### ⛔ Hai nền tảng, hai lệnh, đổi chỗ thì hỏng IM LẶNG

| | Dùng gì | Vì sao không dùng cái kia |
|---|---|---|
| POSIX | `os.kill(getpid(), SIGTERM)` | `raise_signal()` gửi cho **thread đang gọi**, nên không ngắt `epoll_wait` của thread chính - handler uvicorn có thể không chạy tới lúc hết hạn |
| Windows | `signal.raise_signal(SIGTERM)` | `os.kill()` ở đây gọi thẳng `TerminateProcess`, tức **mất sạch phần dọn êm** |

⚠ Test vì vậy **bắt cả hai đường rồi mới khẳng định đường nào phải chạy**. Vá một đường là
dựng lại đúng cái bẫy đã cắn **ba lần** ở repo này: một phép đo xanh vì nó không bao giờ
chạy nhánh của nền tảng kia (`test_linux_never_switches` của 0.8.1 là ca gần nhất).

#### ⭐ `-15` trên Windows: quy được trách nhiệm, và nó chỉ ngược về mục 1

Người báo để ngỏ giữa *watchdog của framework* và *công cụ chạy lệnh của họ*. Mã thoát
trả lời dứt khoát: CPython (`popen_spawn_win32.py::wait`) đổi `TERMINATE = 0x10000` thành
`-signal.SIGTERM`, mà `0x10000` **chỉ do `multiprocessing` ghi**. `taskkill /F` ghi `1`,
`Stop-Process -Force` ghi `0xFFFFFFFF`. Còn ba chỗ giết con trong framework thì **đều log
trước khi giết**, và nhánh `_shutdown` in *"during shutdown"* chứ không phải *"restarting"*.

> ⇒ Kẻ giết là **một tiến trình `multiprocessing` khác** - một cụm cũ chưa tắt hẳn. Tức
> **mục 3 là triệu chứng của mục 1**, và bản vá mục 1 xoá luôn nó.

#### ⛔ Mục 2 (401 lạnh máy) KHÔNG phải lỗi framework

Bộ khoá verify của họ đang là trạng thái **riêng từng tiến trình**. Đường đúng đã có từ
0.8.0: primary lấy khoá trong `run_once()`, cất ở `RefData`, làm tươi bằng job đơn nhất.

⭐ Điểm mấu chốt: **cha ĐỢI `run_once()` xong rồi mới sinh con tiếp theo**
(`_supervisor.py::run`). Nên khoá nằm trong `RefData` **trước khi con thứ hai ra đời** -
không con nào có cửa sổ lạnh, kể cả con đầu. Con số *"8 lần gọi liên tiếp"* của họ không
phải ngưỡng đáng ghi vào tài liệu framework; nó là **giá của việc chưa làm M5**, và ghi nó
vào tài liệu chung sẽ **dạy sai cho 20 repo còn lại**.

⛔ Không nhận đề nghị *"nạp khoá ở `post_construct`"*: hook đó chạy ở **mọi** tiến trình,
tức N lời gọi mạng cho một thứ cả cụm dùng chung - đúng thứ `run_once` sinh ra để thay.

📌 Tài liệu người dùng: `docs/{vn,en}/multi-process.md` mục *"Cha chết thì con đi theo -
và vì sao bạn không tìm thấy con mồ côi"* (kèm hai lệnh dò đúng cho ai đang gỡ cụm chạy
bản cũ, và bảng mã thoát Windows).

### Đã vá 2026-08-25, commit `4219a56` - `BaseModel` ra khỏi DI và `exclude_segments`

Không đến từ báo cáo nào. Chủ dự án đưa `nha-tro/backend/framework-notes/ghi-chu-framework.md`
(viết 2026-07-04) ra rà lại xem mục nào framework đã vá mà ghi chú còn ghi. Rà ra **5 mục,
3 đã hết đúng**, và một mục hoá ra là lỗi thật chưa ai vá.

| # | Việc | Trạng thái |
|---|---|---|
| **B** | `BaseModel` không còn vào DI - `type_utils.is_pydantic_model()` + `scanner._is_eligible` | ✅ **XONG** |
| **A** | `dependency.exclude_segments(...)` - app ghi đè danh sách package bị loại | ✅ **XONG** |
| **C-E** | Tài liệu: vì sao `@dataclass` không bị loại · `configure()` · log mức module | ✅ **XONG** |
| - | Đính chính 13 file `ghi-chu-framework.md` bên app | ✅ **XONG** |

**Đo:** **2612 passed / 24 skipped / 0 failed = tổng 2636** (`2617 + 19` test mới) ·
`ruff check xime/` sạch · `mypy` **49 lỗi trước và sau, không thêm cái nào**.

#### ⭐⭐ Hai hàm cùng file trả lời ngược nhau về cùng một class

`get_init_parameters()` lọc `VAR_KEYWORD` nên với một `BaseModel` nó trả `[]` - *"không có
tham số nào, singleton không đối số, hợp lệ"* - và cho class đi qua cửa.
`resolve_constructor_hints()` cách đó 40 dòng **không lọc**, nên nó đọc `**data: Any` thành
`{'data': Any}`. **Framework nhận class đó VÌ nó không có tham số nào, rồi chết vì đòi một
tham số.** `config_loader.py:75` cũng lọc, tức bộ lọc đúng có mặt ở **hai trong ba** chỗ
cần nó - cùng hình dạng **C6** (một luật, nhiều bản chép tay, hụt đúng một chỗ).

#### ⭐⭐ Bài getting-started KHÔNG CHẠY ĐƯỢC - và lý do BaseModel chỉ là lớp thứ ba

Rút nguyên văn 9 khối code của bài rồi chạy `python -m app.main` như bài dặn. Nó chết
**trước cả** chỗ `BaseModel`, ở `ModuleNotFoundError: No module named 'application'`.

| Lớp | Lỗi | Kiểu hỏng |
|---|---|---|
| 1 | **12 đường dẫn module thiếu tiền tố `app.`** mỗi bản ngôn ngữ - bài khai `app/domain/user.py` và chạy `python -m app.main`, nhưng import viết `from domain.user import User` | ồn ào, chết ngay |
| 2 | **`application.yml` để ở `app/resources/`** trong khi framework tìm `resources/application.yml` **tương đối với thư mục chạy lệnh** | ⚠ **IM LẶNG** - app khởi động, chạy bằng mặc định, không gì báo. Đo được vì đổi cổng trong file mà tiến trình vẫn bám cổng cũ |
| 3 | `UserResponse(BaseModel)` trong `api/rest/` bị scan | ồn ào |

Sửa cả ba rồi dựng lại từ bản đã sửa: **`GET /users/1` trả `{"id":1,"name":"Alice",...}`,
`/docs` trả 200.**

⭐ **`xime init` thì chạy tốt** (đã kiểm: `python main.py`, `/ping` trả `{"status":"ok"}`,
`/docs` 200). Lỗi chỉ nằm ở bài viết tay - và bài **chưa từng nhắc `xime init` một lần nào**,
nên người mới dựng tay 9 file trong khi một lệnh là xong. Nay có mục trỏ sang.

#### ✅ Ba bố cục cùng tồn tại - ĐÃ THỐNG NHẤT về khuôn của `xime init`

Chủ dự án chốt 2026-08-25: *"sửa các bài hướng dẫn sao cho nó khớp với phiên bản hiện tại;
cái đó trước viết cho các phiên bản cũ, lâu lắm rồi."*

`getting-started` **viết lại hoàn toàn** cả hai ngôn ngữ theo bố cục `xime init` sinh ra
(`main.py` + `config/` + `resources/` ở gốc, code nghiệp vụ trong gói mang tên dự án). Rút
code từ bản mới ra chạy để nghiệm thu, **cả VN lẫn EN**: `GET /users/1` trả
`{"id":1,"name":"Alice",...}`, `/docs` 200.

Ba thứ bài cũ dạy sai so với bản hiện tại, và cả ba đều là **khuôn của bản trước 0.8**:

| | Bài cũ | Hậu quả |
|---|---|---|
| `main.py` | `use()` **trong** `if __name__` | con chạy lại file đó với `__name__ == "__mp_main__"`, khối `if` không nổ -> **không adapter nào, DI rỗng** |
| `add_config` + `config/__init__.py` | **không nhắc một chữ** | cơ chế tự dò cũ tìm qua `__main__.__spec__.parent`, giá trị đó khác ở tiến trình con -> im lặng rơi xuống DI rỗng |
| `resources/` | trong `app/` | framework tìm **tương đối thư mục chạy lệnh** -> file bị bỏ qua **im lặng**, app chạy bằng mặc định |

Dọn thêm cho toàn bộ `docs/`, không riêng bài mở đầu: **10 đoạn `main.py`** gọi `run()` ngoài
`if __name__` (nay 0) · **60 đường dẫn module** thiếu tiền tố gói ở 22 file · **10 chỗ** gọi
`config/routing.py` trong khi khuôn hiện hành là `config/web.py`.

⭐ **Bộ test tự kiểm tài liệu, và tôi không biết cho tới lúc con số nhảy.** Tổng test tăng
`2612 -> 2614 -> 2616` mà tôi không thêm test nào, hoá ra
`tests_temp/cli_docs/test_documented_commands.py` **sinh một test cho mỗi lệnh `xime ...`
xuất hiện trong khối code của tài liệu**. Thêm `xime init` và `xime config --print` vào bài là
thêm hai test - và chúng **pass**, tức lệnh viết vào tài liệu là lệnh có thật.

⭐ Kèm một lỗi tìm được nhờ phép quét tiếng Việt trong bản EN: `_HUONG_DAN` ở
`ws/_availability.py` in `(hoặc: pip install ...)` **giữa một câu tiếng Anh**. Đó là chuỗi
người dùng thấy, không phải chú thích. Tài liệu chỉ trích lại đúng nó, nên **lỗi ở code**.

#### Bối cảnh: ba bố cục đã từng cùng tồn tại

| Nguồn | Bố cục | Chạy được? |
|---|---|---|
| `xime init` | `main.py` + `config/` ở gốc, code trong package tên dự án | ✅ |
| `getting-started.md` | mọi thứ trong `app/`, `resources/` ở gốc | ✅ **sau khi vá** |
| 31 codebase Xime | như trên | ✅ |
| **Các bài docs khác** (routing, websocket, modbus, opcua, mqtt, testing, starters, configuration, core-concepts) | `scan("application.usecase")`, `configure_controllers("api.rest")` - **không tiền tố**, tức khớp `xime init` chứ không khớp getting-started | - |

**~52 dòng ở 22 file** đang theo bố cục của `xime init`. Tôi **KHÔNG tự sửa** chúng: chúng là
đoạn minh hoạ rời không khai cây thư mục, nên không sai - nhưng người đọc đi từ
getting-started sang routing.md sẽ thấy hai kiểu đường dẫn. Thống nhất về một bố cục là
**quyết định cấu trúc**, thuộc chủ dự án.

#### ⭐⭐ Bối cảnh: BaseModel



Đo lại trên bản trước khi vá: `docs/{vn,en}/getting-started.md` khai
`class UserResponse(BaseModel)` trong `api/rest/user_controller.py` rồi
`dependency.scan("api.rest")` - dựng đúng hình đó thì startup chết với
`UnregisteredDependencyException: Any`.

> **Bài "hello world" của framework hỏng, và không ai phát hiện** vì mọi app thật đều
> sớm học được cách xếp DTO vào `dto/` rồi không bao giờ quay lại đọc bài hướng dẫn.

Đây là bằng chứng mạnh nhất rằng nó là **lỗi**, không phải lựa chọn thiết kế: chính tài
liệu chính thức bảo người ta làm một việc mà framework từ chối.

#### ⛔ Bản vá đầu tôi đề xuất SAI, và mô phỏng đầu-cuối là thứ bắt được

Đề xuất đầu là lọc `VAR_KEYWORD` trong `resolve_constructor_hints`. Chạy thử trọn đường thì
nó chỉ đổi `UnregisteredDependencyException: Any` thành `ValidationError: field required` -
vì `build()` chỉ **kiểm**, còn dựng thật xảy ra ở `orchestrator.py:126` (`get_all_in_order()`).
Bỏ `**data` khỏi danh sách dependency chỉ khiến container yên tâm gọi `Model()` không đối số.

⭐ Lỗi mới **tệ hơn lỗi cũ**: nó không còn một chữ nào dính tới DI, nên người đọc đi tìm dữ
liệu sai thay vì tìm class đặt nhầm chỗ. Đúng nghĩa thứ ba của *"không test nào đỏ"* -
**bản vá không làm việc mà lời giải thích của nó nói**.

#### ⛔ `@dataclass` KHÔNG bị loại - chốt, và lý do đã vào tài liệu

Framework **phân biệt được** (`is_dataclass()`, kèm bẫy: nó trả `True` cho class thường
**kế thừa** từ dataclass, phải hỏi `"__dataclass_fields__" in cls.__dict__`). Cố ý không dùng:

- `@dataclass class PhongService: repo: PhongRepository` sinh ra `__init__(self, repo: ...)` -
  **chính xác** là constructor injection. Ranh giới của DI là *dựng được hay không*, không
  phải *người ta định dùng làm gì*.
- Loại nó hỏng **im lặng**: service viết bằng dataclass biến mất khỏi DI không một lời nào.
  Hôm nay đặt nhầm chỗ thì **nổ lúc khởi động kèm tên class**.
- Đo AST trên 31 codebase: **197 `@dataclass` trong vùng được quét, 0 cái hình dạng bean**.
  ⚠ Đó là bằng chứng về **thói quen của Xime**, không phải về **khả năng của Python** - và
  framework phải đúng cho người ngoài.

#### ⭐ Đối chứng 4 bắt được một lỗ hổng test, lần thứ ba trong một tháng

Bản đầu của lớp `TestOrchestratorChuyenTiepDungHaiTrangThai` **chép lại** nhánh
`if ... is not None` rồi kiểm bản chép. Xoá nhánh thật trong `orchestrator.py` thì **19/19
vẫn xanh**. Đã sửa thành chạy `StartupOrchestrator` thật với package thật trên đĩa; nay xoá
nhánh ra là **2 đỏ**.

Bốn đối chứng, đều đỏ đúng chỗ: gỡ lọc `BaseModel` → **3 đỏ** · cắt dây container→scanner →
**2 đỏ** · gộp `None` với `()` → **2 đỏ** · xoá nhánh orchestrator → **2 đỏ**.

#### `exclude_segments`: mối nối đã có sẵn, chưa ai truyền một lần nào

`PackageScanner.__init__` nhận `excluded_segments` từ lâu, nhưng `build()` gọi
`PackageScanner()` trắng và không chỗ nào trong repo - kể cả `tests_temp/` - truyền tham số
đó. **Mã chết.** Bản này chỉ nối nó ra tới `dependency`, không đổi hành vi mặc định của app nào.

⚠ **`None` (chưa khai) phải giữ khác `()` (khai rỗng).** Gộp lại thì mọi app trên đời bỗng
quét cả `domain/` mà không có gì báo. Vì vậy orchestrator chuyển tiếp **có điều kiện** - đừng
"dọn cho gọn" thành lời gọi vô điều kiện.

⚠ Đây là **API công khai mới**, mà `0.9` sang Beta nơi API coi như đã chốt → **phải nằm trong
`0.8.x`**, không lùi được.

#### Ba mục của ghi chú `nha-tro` hoá ra đã hết đúng từ lâu

| Ghi chú nói | Sự thật |
|---|---|
| param có default kiểu nguyên thủy vẫn fail | ✅ vá ở `0.7.0`. ⛔ Cách né họ ghi (*bỏ annotation*) nay **phản tác dụng** - class thiếu type hint bị scanner bỏ qua hoàn toàn |
| thiếu `register_instance` / `register_factory` | ⚠ `dependency.configure()` làm đủ, **có từ 2026-06-03** - trước ghi chú một tháng |
| mọi truy vấn kể cả ĐỌC phải bọc transaction | ✅ hết đúng từ `0.6.3` (`ReadOnlyManager`), và chính repo đó đã dùng ở nhiều chỗ |

⭐ **Phát hiện phụ, và nó giải thích cả ba:** `dependency.configure()` **chưa từng nằm trong
tài liệu người dùng, một dòng nào** - chỉ có ở `rules/coding.md` nội bộ. Nay có mục riêng ở
`docs/{vn,en}/core-concepts.md`.

#### Log ở mức module: không phải "bị nuốt", mà mất một nửa

| Mức gọi lúc import | Kết quả |
|---|---|
| `DEBUG` / `INFO` | **mất hẳn** |
| `WARNING` trở lên | **hiện, nhưng thô** - qua `logging.lastResort`, không mức, không mốc giờ, không theo `logging.format` |

⭐ Người viết thấy cảnh báo của mình **có hiện** nên kết luận logging đang chạy, rồi
`logger.info` cùng file thì mất và họ đi tìm lý do ở chỗ khác. ⛔ **Không cấu hình logging
sớm hơn**: mức và định dạng đọc từ `application.yml` chưa nạp lúc đó, và nó hợp thức hoá đúng
thứ `rules/module-level-code.md` đã cấm.

#### 13 bản chép, không phải 3

Chủ dự án nhắc 3 repo; đo ra **13 file `ghi-chu-framework.md` giống hệt nhau** (cùng md5).
Tất cả nay mang khối **⛔ ĐÍNH CHÍNH - phiên `xime framework` ghi 2026-08-25** ở đầu, thân
file giữ nguyên văn vì mỗi mục đều đúng vào lúc viết.

### Đã vá 2026-08-28 - access log của uvicorn treo vào `xime.dev`

⚠ **ĐỔI HÀNH VI** thứ hai theo cùng một công tắc. Chủ dự án hỏi *"fastAPI có request là
nó có log, cho lên prod thì phải tắt cái log này đi chứ nhỉ... nó cũng có làm gì đâu"*,
rồi chốt hai điều: **tắt**, và **dùng biến đã có** thay vì đẻ khoá mới. Kèm một ranh
giới: *"cái log request thôi, log khởi động là phải có"*.

**Đo:** **2667 passed / 24 skipped / 0 failed = tổng 2691** (`2682 + 9` test mới) ·
`ruff check xime/` sạch · `mypy` **49 trước và sau** · bốn trình kiểm tài liệu OK
(`check_doc_coverage` giữ nguyên 143/311, đã so bằng `git stash`).

| Đổi gì | |
|---|---|
| `uvicorn.Config(..., access_log=dev)` | `dev` lấy từ `_dev_mode(app)` sẵn có, không thêm khoá cấu hình nào |
| Nhãn trong dòng `serving on` | `[access log on]` / `[access log off - set xime.dev: true]` |

#### ⭐⭐ Chỗ dễ canh nhầm: protocol KHÔNG đọc `config.access_log`

`h11_impl.py:56` và `httptools_impl.py:61` đều viết:

```python
self.access_log = self.access_logger.hasHandlers()
```

Thứ quyết định có in hay không là **logger `uvicorn.access` còn handler nào không**, và
`Config.configure_logging()` mới là chỗ gỡ handler (`access_log is False` -> `handlers =
[]` + `propagate = False`). Một bộ test chỉ canh `config.access_log` là canh **một
trường mà không ai hỏi tới**: ngày uvicorn đổi cách nối hai thứ đó, test vẫn xanh trong
khi mọi request lại in một dòng. Nên `TestCongTacPhaiToiDUOC_LOGGER` canh tầng dưới.

Cùng họ với bài học đã trả giá ở đợt uvloop `0.8.1` và dòng log xác thực - **canh hàm
không phải canh việc hàm có tác dụng**.

#### ⚠ Access log biến mất là hỏng IM LẶNG, khác hẳn `/docs`

`/docs` mất thì còn một mã **404** để lần. Access log mất thì không có gì cả: không lỗi,
không mã, chỉ một màn hình trống mà người ta rất dễ đọc thành *"app không nhận được
request nào"*. Đó là lý do dòng khởi động **phải** khai, và là lý do nhãn nằm ngay trong
dòng `serving on` chứ không phải một dòng riêng dễ bị cuộn qua.

`TestTatAccessLogKHONGDungToiLogKhoiDong` khoá đúng ranh giới chủ dự án vạch: hai thứ đi
qua **hai logger khác nhau**, nên ngày nào có người "dọn cho gọn" bằng cách hạ mức log
toàn cục thì nó đỏ.

#### Con số, và giới hạn của chúng

Đo bằng đúng `AccessFormatter` của uvicorn, không phải formatter tự chế:

| | µs/dòng | phần của một request |
|---|---|---|
| tắt (một phép `if`) | 0,04 | ~0% |
| format thuần, không ghi đi đâu | 20 | 9% |
| ghi ra FILE (như `systemd`/`nohup`) | **31** | **~14%** |
| ghi ra FILE, có màu | 34 | 15% |

Mốc so sánh 227 µs/request lấy từ `bench_http` của `0.8.1` (4.396 req/s).

⚠ **Phép đo micro này không phải phép đo đầu-cuối.** Nó đo đúng chi phí một lời gọi
`logger.info` trên code path thật, và **giả định** phần còn lại của request không đổi -
hợp lý vì cả hai nhánh chạy cùng một mã, nhưng nó không phải `ab` bắn vào server thật.
Chủ dự án dừng phép đo đầu-cuối giữa chừng (*"không có phải đo. tôi muốn tắt nó"*), nên
con số 14% đọc là **bậc độ lớn**, không phải một kết quả benchmark đã nghiệm thu.

✅ Phần **đã** chạy thật là hành vi: app Xime thật, hai nhánh khác nhau đúng một biến
`XIME_ENV` - nhánh prod ra **0 dòng** access log, nhánh dev ra 6 dòng cho 6 request, và
log khởi động **giống hệt nhau ở cả hai**.

### Đã vá 2026-08-27 - `xime.dev`, MỘT công tắc cho mọi bề mặt chỉ dành cho dev

⚠ **ĐỔI HÀNH VI**, không phải thuần cộng thêm: `/docs`, `/redoc`, `/openapi.json` nay
**mặc định TẮT**. Chỉ mở khi ứng dụng khai `xime: dev: true` trong `application.yml`.

Chủ dự án hỏi *"mấy cái cho bản dev, lên prod thì phải tắt đi chứ nhỉ"*, rồi chốt hai
điều khi tôi đưa phương án: **đổi luôn mặc định thành TẮT**, và **một công tắc cho tất
cả** chứ không phải một cờ riêng cho OpenAPI.

**Đo:** **2658 passed / 24 skipped / 0 failed = tổng 2682** (`2649 + 33` test mới) ·
`ruff check xime/` sạch · `mypy` **49 trước và sau** · bốn trình kiểm tài liệu OK.

| Thêm gì | |
|---|---|
| `xime/core/config/_dev.py` | `is_dev_mode()` + hằng `DEV_KEY` - **tên công khai mới** |
| `xime.dev` trong sổ cấu hình | `xime check config` không tố oan (đúng lỗi **C8**), `xime config --print` in kèm giải thích |
| `init_keys` cho `xime init` | dự án mới sinh ra có `dev: true` trong `application.yml` (gitignore), `.example` thì không |
| Một dòng log khởi động | `API docs off - set xime.dev: true` / `API docs EXPOSED at ... (xime.dev is on)` |

#### ⭐⭐ Vì sao là công tắc theo MÔI TRƯỜNG, không phải cờ trong `OpenApiConfig`

Giấu `/docs` sau middleware JWT nghe như đường thay thế và **không dùng được**: Swagger
UI là trang mở bằng trình duyệt, mà trình duyệt không gắn header `Authorization` khi gõ
URL. Đo trên cấu hình thật của `gym`: giữ ba đường trong `public_paths` -> **200**, xoá
-> **401**.

> Lựa chọn thật chưa bao giờ là *"công khai hay sau đăng nhập"*, nó là *"dev hay
> production"*. Và theo phép phân loại của `rules/config-discovery.md` thì đó là câu
> **người vận hành** trả lời, nên nó thuộc YAML chứ không thuộc một hàm `configure_*`.

⭐ Hệ quả kéo theo, đáng nhớ hơn bản vá: **24 repo đều mở `/docs` công khai không phải
vì ai đó cẩu thả** - cách duy nhất để dùng được nó là mở nó ra. Một lỗ hổng mà mọi
người đều rơi vào thì nguyên nhân nằm ở thứ họ được cho, không ở kỷ luật của họ.

⛔ **Không suy ra từ tên profile.** `XIME_ENV` chọn *file* nào được nạp, còn tên profile
do app tự đặt (`local`, `sandbox`, `qa`, `dev-mirror-of-prod`). Suy từ tên thì framework
phải giữ một danh sách tên "được coi là dev", và danh sách đó sai với mọi người không
dùng đúng từ vựng của nó - im lặng, theo cả hai chiều.

⛔ **`is_dev_mode` fail-closed**: thứ gì không phải `RuntimeConfig` thật thì trả `False`.
Giá trị không phải boolean nhận dạng được thì **nổ lúc khởi động** chứ không đoán.

#### ⛔ `swagger_ui_title` từng mở lại được `/docs` sau lưng công tắc

Nhánh tiêu đề riêng đọc `config.docs_url or "/docs"`. Chữ `or` đó **vô hại suốt thời
gian tài liệu mặc định BẬT**, và thành lỗ hổng đúng vào ngày mặc định đổi thành TẮT -
một trường **trang trí** vô hiệu hoá một lựa chọn bảo mật, trên máy production, trong im
lặng. Nay bất biến ấy chở bằng một tuple để **mypy nhìn thấy được**, không phải một lời
hứa trong chú thích.

`configure_openapi` **chưa từng có một test nào** - đó là lý do chữ `or` sống được. Nay
có 33 test, và **cả sáu mảnh của bản vá đều đã đối chứng**: gỡ công tắc -> 11 đỏ · gỡ
phép kiểm tiêu đề riêng -> 2 · bỏ lời gọi log trong `lifespan` -> 1 · bỏ cảnh báo -> 1 ·
bỏ luật `openapi_url=None` -> 2 · bỏ fail-closed -> 1.

#### Phần NGOÀI repo này (đã làm, đã ghi tài liệu tại chỗ)

Chủ dự án nhờ vá thẳng thay vì để từng repo tự làm. Không có gì trong repo framework,
ghi ở đây để phiên sau biết chuyện gì đã xảy ra ở tầng ứng dụng:

| Mục | Kết quả |
|---|---|
| **A4** | 24 `application.yml` được thêm công tắc, 24 `.example` được thêm dạng chú thích. ⛔ **Ba dòng `/docs` trong `public_paths` GIỮ NGUYÊN** - xoá là 401 |
| **A1** | 10 app đổi từ fail-open sang **ném `StartupException`**; 24/24 `config/jwt.py` nay fail-closed, kiểm chứng lúc chạy |
| **A2** | `dental` + `Base Platform/data`; nay **48 file có regex, 0 file lọt địa chỉ công cộng** |
| **A3** | 6 app `Monolithic` nhận secret riêng (trước dùng chung một chuỗi) |
| **A5** | ⬜ **không làm** - hơn 800 route phải phân loại, tức quyết định nghiệp vụ |
| **Java** | 4 service Base phơi springdoc - **A4 chưa từng đếm chúng**, đã báo leader |

26 repo có `.claude/docs/va-bao-mat-2026-08-27.md` + con trỏ trong `CLAUDE.md`.

### Đã code 2026-08-25, chờ commit - export `public_health_paths`

Báo cáo từ `nha-tro`:
[`bao-cao-van-de-tu-repo-ngoai/nha-tro-public-health-paths-khong-export-2026-08-25.md`](docs/bao-cao-van-de-tu-repo-ngoai/nha-tro-public-health-paths-khong-export-2026-08-25.md).
Hàm có từ `0.8.0`, docstring tự khai *"middleware JWT cho chúng đi qua"*, nhưng **thiếu ở
`__all__`** nên app không có đường công khai gọi tới. Hậu quả: `/healthz` đòi token, tức
một `/healthz` **im lặng đúng lúc app không lấy nổi khoá verify**.

**Đo:** **2621 passed / 24 skipped / 0 failed = tổng 2645** (`2640 + 5` test mới) ·
`ruff check xime/` sạch · `mypy` **49 lỗi trước và sau, không thêm cái nào**.

#### ⭐⭐ Đo lại LẬT lý do phản đối, không chỉ nới con số

Báo cáo cố ý không xin gì - nó đưa hai đường và **tự ghi luôn lý do phản đối** đường thứ
nhất: *export nó là hợp thức hoá middleware JWT tự viết, đúng thứ bản vá A1 đang cố xoá*.
Lập luận đó nghe rất đúng, và nó **sai về mặt sự kiện**: `admin/backend/app/config/network.py`
gọi hàm này cho một **hàng rào IP**.

> Chỗ dùng đó không dính gì tới JWT, và **không biến mất** khi repo chuyển sang
> `configure_jwt`. Ghi log truy cập, hãm nhịp, đếm số đo cũng cùng nhóm.

Nên đường thứ hai (*không export, đổi docstring thành "chi tiết nội bộ của `configure_jwt`"*)
sẽ ghi một **câu sai** vào tài liệu. Chỉ còn một đường đi được.

| Đo trên 28 repo | |
|---|---|
| Gọi `public_health_paths` từ module riêng tư, **trong code sản phẩm** | **8 repo** - `admin` (2 file), `linh-kien-dien-tu`, `nha-hang`, `crm`, `giao-viec`, `kho`, `nhan-su-cham-cong`, `so-thu-chi` |
| Lời import riêng tư khác nằm ngoài thư mục `test/` | **0** |

⭐ Con số thứ hai là thứ khiến quyết định dễ: mọi lời import riêng tư còn lại
(`JwtAuthMiddleware`, `registry`, `ErrorMappingInterceptor`...) đều nằm trong **test**, mà
test thò tay vào ruột là chuyện khác hẳn. Đây là **rò rỉ duy nhất trong code sản phẩm của
cả workspace** - cửa đã có người đi qua từ lâu, việc còn lại chỉ là chọn giữa *một cửa được
đỡ* và *8 repo bám vào ruột framework*.

📌 Tiền lệ đúng dạng này đã có: `JWT_CLAIMS` export ở `0.7.2`, lý do ghi ngay trong
`starters/jwt/__init__.py` - *"chỉ người ta vào một module có tên bắt đầu bằng dấu gạch
dưới là bảo họ thò tay vào ruột của mình"*.

#### Hai thứ chưa tài liệu nào nói, nay có

| | |
|---|---|
| **Dùng `configure_jwt` thì ĐỪNG gọi** | Framework tự cộng đường sức khoẻ vào `public_paths` trước khi gắn middleware. Chép tay lần nữa là dựng một bản sao sẽ lệch vào ngày luật khớp đường dẫn đổi |
| **Phải gọi SAU `configure_health()`** | Nó đọc sổ đăng ký tại thời điểm được gọi, nên gọi sớm nhận tuple **rỗng** - mà rỗng trông y hệt *"app này không bật endpoint sức khoẻ"*. Hàng rào chặn mất `/healthz` và **không có gì báo**, vì middleware từ chối rất gọn gàng. `admin` phải tự phát hiện chuyện này |

#### Test đi đúng con đường tài liệu hướng dẫn

`tests_temp/watchdog/test_health_endpoint.py` nay lấy hàm qua **`from xime.adapters.web
import public_health_paths`**, không qua `._health`. Lấy đường riêng tư thì bộ test vẫn
xanh kể cả ngày cái tên rơi khỏi `__all__` - tức nó canh **hàm**, không canh **thứ người
dùng chạm tới**. Cùng bài học đã trả giá ở đợt uvloop `0.8.1` và ở dòng log xác thực.

Ba test mới chạy một **hàng rào IP thật** (không phải middleware xác thực - cố ý, để bộ
test tự nói ra lý do phản đối kia không đứng vững): đường sức khoẻ **qua được** · đường
nghiệp vụ **không qua** · quên `configure_health()` thì `/healthz` **bị chính hàng rào của
mình chặn**.

**Ba đối chứng, đều đỏ đúng chỗ:** bỏ tên khỏi `__all__` → **1 đỏ** · bỏ lời import khỏi
`__init__` → **cả file lỗi** · hàng rào cho qua tất → **2 đỏ**.

⚠ Tên công khai mới, mà `0.9` sang Beta nơi API coi như đã chốt → **phải nằm trong `0.8.x`**,
không lùi được.

### Đã vá 2026-08-22, commit `d2294c6` (sửa chữ ở `d1328e2`)

| # | Việc | Trạng thái |
|---|---|---|
| **1** | **`public_paths` khớp được tiền tố** - `configure_jwt(public_paths=["/api/v1/parts/*"])` | ✅ **XONG** |
| **2** | **Một dòng `INFO` khai trạng thái xác thực** lúc khởi động | ✅ **XONG** · ⚠ **bản đầu SAI CHỮ, đã sửa 2026-08-23** - xem mục dưới |

Đo sau cả hai: **2571 passed / 24 skipped / 0 failed = tổng 2595** (`2564 + 31` test
mới) · `ruff check xime/` sạch · `mypy` **49 lỗi, đúng mốc máy này**.

⭐⭐ **Một lỗ hổng test do đối chứng tìm ra, đáng nhớ hơn cả hai tính năng:** bản test đầu
của việc 2 gọi thẳng `_log_auth_state`, nên **xoá lời gọi trong `lifespan` thì 0 test
đỏ** - nó canh **hàm**, không canh **việc hàm được gọi**. Cùng khuôn đã trả giá ở đợt
uvloop `0.8.1`, và lần này nó lặp lại **trong cùng tuần**. Đã vá bằng một test dựng app
thật rồi chạy `lifespan`.

⭐ **Việc 1 rộng hơn dự kiến:** có **ba chỗ khác** cũng đọc `public_paths` và mỗi chỗ tự
chép luật khớp - registrar WebSocket, trình dựng OpenAPI, phép thêm đường sức khoẻ. Sửa
mỗi middleware là dựng lại đúng lỗi vừa vá ở C8 (một luật, nhiều bản chép tay). Nay cả
ba gọi cùng một hàm.

#### ⛔ Việc 1 - ba ràng buộc, không phải lời nhắc

1. **Không `startswith` trần.** `/api/v1/parts/*` khớp `/api/v1/partsecret` là một **lớp
   lỗ hổng**, và nó hỏng theo chiều **chặt sang lỏng** nên không gì báo. Khớp theo **đoạn
   đường dẫn**: chuẩn hoá tiền tố cho kết thúc bằng `/`, xử lý riêng đường gốc.
   Mã tham khảo đã chạy thật: `linh-kien-dien-tu/backend/app/api/rest/TrustJwtAuthMiddleware.py`
   (`_split_public` / `_is_public`), và bản gọn hơn ở `nhan-su-cham-cong`.
2. **Đây là ĐỔI HÀNH VI, không phải thuần cộng thêm.** Ký tự `*` trong một đường dẫn đang
   có sẽ đổi nghĩa. URL hiếm khi mang `*` thật, nhưng `public_paths` là giá trị cấu hình
   **đã phát hành** - CHANGELOG phải ghi đúng loại.
3. **Test đi thành cặp.** Đường trong tiền tố phải **mở** và đường chỉ *giống* tiền tố
   phải **đóng**. Chỉ có vế đầu thì cách sửa sai *"mở tất"* cũng qua được.

Bằng chứng trung tính (không dựa vào app Xime nào): Spring Security `/public/**`, Django,
Express, ASP.NET - **không hệ nào** bắt liệt kê chính xác. Chỗ hụt là **tham số đường
dẫn**, và tập đường sinh ra từ một tham số là **VÔ HẠN**.

⚠ Lập luận *"framework tự va vào qua route `/docs`"* trong báo cáo gốc **không đứng
vững** - `/docs`, `/openapi.json`, `/redoc` là tập **hữu hạn**, liệt kê hết được, và
`docs/vn/starters.md:277` đã bảo làm đúng thế. Đừng trích lại nó như lý do.

#### ⛔⛔ Việc 2 - hậu kiểm 2026-08-23: bản đầu SAI, đã sửa chữ

**Bản ship đầu tiên của dòng log kết luận sai 100% số lần nó in ra.** Phiên `Service ngang`
báo về ngay hôm sau, và họ đúng - framework đo lại xác nhận từng con số.

Câu cũ: `no JWT middleware - N HTTP route(s) open to anyone`. Nó đo **một** sự kiện
(`configure_jwt()` có được gọi không) rồi in ra **hai** kết luận không có bằng chứng nào đỡ.

| | Số repo |
|---|---|
| Cài xác thực bằng `configure_middleware` - câu cũ kết luận **SAI** | **23** |
| Dùng `configure_jwt` - câu cũ kết luận đúng | **0** |

Họ khởi động thật bốn repo với Trust + Postgres, `curl` không token ra **401**. Tôi dựng lại
một app tối giản và thấy cùng một tiến trình in `open to anyone` rồi trả `401` cho request
không token - hai câu tự mâu thuẫn trong cùng một log.

⭐⭐ **Vì sao nặng hơn chuyện chữ nghĩa, và đây là phần đáng nhớ:** dòng log này **là** bản
vá A1. Một phép dò kêu oan là một phép dò sẽ bị tắt - khi cùng một câu xuất hiện dưới 23
ứng dụng khoẻ mạnh thì ứng dụng thật sự fail-open in ra một dòng **không ai còn đọc**. Bản
vá vẫn nằm trong code nhưng hết tác dụng với người đọc, tức **đúng thứ nó sinh ra để chặn**.
Cùng hình dạng **C7** (cụm khoẻ và cụm hỏng sinh log giống nhau), khác ở chỗ lần này hai
bên giống nhau vì **chữ quá rộng** chứ không vì thiếu log.

⚠ Và nó lặp lại đúng lý do tôi đã dùng để **bác** phương án 6a của `dental` hôm trước. Bác
đúng, rồi tự dựng lại cùng cái bẫy ở chỗ khác.

**Chữ hiện tại - khai thứ đo được, không kết luận:**

```text
web default: JWT middleware active (aud=phongkham, 1 public path(s), 31 HTTP route(s))
web default: configure_jwt() not called - 3 custom middleware installed, 31 HTTP route(s)
web default: configure_jwt() not called - no middleware installed, 31 HTTP route(s)
```

⛔ **Số middleware được IN RA, không được diễn giải.** `configure_middleware` cũng là đường
cài nén, log, request id - suy từ con số khác 0 ra *"có xác thực"* là **đúng vì lý do tình
cờ**. Chính người báo tự phanh chỗ này, và phanh đúng. Hình dạng fail-open thật là dòng thứ
ba, và nó tự nói ra mà không cần ai kết luận hộ.

⭐ **Phạm vi tôi đo RỘNG HƠN báo cáo ở một chỗ và HẸP HƠN ở chỗ khác** - lần đầu có vế thứ
hai: họ nhấn vào `open to anyone`, nhưng `no JWT middleware` **cũng sai** với người cài
middleware JWT của chính họ, nên sửa cả câu chứ không sửa nửa câu. Ngược lại họ đoán `socket`
adapter có thể dính - **không**: grep cho thấy chỉ `web/_adapter.py` đọc `jwt_registry`.

**Đo:** `tests_temp/web/` **49 passed / 1 skipped**, riêng bộ test dòng log **8 -> 14 test**.
Hai đối chứng: quay về chữ cũ -> **8 đỏ** (cả 6 test của lớp mới) · gộp middleware của mọi
server thay vì theo `server_id` -> **1 đỏ**, đúng test canh chuyện đó.

📌 Tài liệu người dùng: `docs/{vn,en}/starters.md` mục *"Dòng log khởi động về xác thực - và
điều nó KHÔNG nói"*. Viết cho phiên app đọc khi họ thấy dòng lạ, và nói thẳng câu quan trọng
nhất: **`configure_jwt() not called` là một phép đo, không phải một lời phán xét.**

#### Việc 2 - bối cảnh ban đầu, giữ vì lý do vẫn đúng

Dựng hai app Xime tối giản khác nhau đúng một chỗ (`configure_jwt()` gọi hay không), rồi
`diff` log khởi động: **0 dòng khác biệt**. App bảo vệ dữ liệu và app mở toang mọi
endpoint sinh log **giống hệt nhau**, cả hai đều báo *"startup complete"*.

Đây là **C7 ở một adapter khác** - lỗ hổng *trạng thái tốt không có dấu vết* mà framework
đã nhận cho gRPC. Và nó vá đúng thứ làm **A1** sống lâu: sau `0.7.2` đường rơi vào A1
**hẹp lại nhưng chưa đóng** - đặt `configure_jwt()` sau một `if` là quay lại A1 nguyên
vẹn, và framework không nói gì.

⛔ **Phương án cảnh báo (mục 6a của báo cáo `dental`) đã BÁC:** framework không biết route
nào *đáng lẽ* phải có xác thực, nên nó sẽ kêu oan với mọi service công khai hợp lệ - và
*một phép dò kêu oan là một phép dò sẽ bị tắt*.

### Đã trả lời, KHÔNG làm

| Việc | Vì sao |
|---|---|
| **Nhận diện trên đường công khai** (mục 3 báo cáo `linh-kien`) | ⛔ **BÁC VĨNH VIỄN - chủ dự án chốt 2026-08-22**, kèm câu dặn *"đừng app nào đề nghị nữa"*. Lý do quyết định **không phải ba câu thiết kế tôi nêu**, mà là một chỗ cả tôi lẫn người báo bỏ sót: **một trang gọi máy chủ qua nhiều đường**, nên phần riêng của người đăng nhập lấy từ một đường CÓ xác thực, không cần nhét danh tính vào đường công khai. Ca sử dụng tự giải được bằng thứ đã có. Đầy đủ: mục [Năm thứ đừng đề xuất lại](#năm-thứ-đừng-đề-xuất-lại) |
| **Sửa tài liệu về `configure_jwt` chỉ verify 1 khoá** (mục 6 báo cáo `linh-kien`) | **Không phải nợ của framework.** `docs/vn/starters.md` mục 177-206 đã mô tả đầy đủ `key_provider` + tra khoá theo `kid`. Chỗ lỗi thời nằm trong **comment của 19 repo app** |

## 3c. Lùi lại - fieldbus + MQTT + `drain()`

> ⏭ **Chủ dự án lùi 2026-08-22.** Không gắn số hiệu bản nữa: *"cho nó là làm trong bản
> nào đó `0.8.x` đi, không nói rõ."*

| Việc | Còn thiếu gì |
|---|---|
| **Fieldbus chia tải** | Cấu hình bốn tầng `process -> modbus -> loại -> thực thể` · `@poll`/`@on_change` chạy một lần **mỗi thực thể** · log khi bỏ qua adapter · chiều ghi qua `ProcessLink`. **Chữ ký đã khai xong ở 0.8** |
| **MQTT chia tải** | Topic filter phải **đến từ cấu hình**, `@subscribe` còn là bảng định tuyến · cảnh báo route không ai nghe. **Metadata `unique_per_process`/`disjoint_per_process` đã có** |
| **`drain()` lúc tắt máy** | Framework không bao giờ tự gọi. Sửa tử tế thì chạm vòng đời adapter |
| ~~**Nợ luật 03 của `EventBus`**~~ | ✅ **ĐÃ TRẢ ở 0.8**: `publish()` trả `PublishOutcome` ba giá trị |

⚠ **Hạn chót vẫn còn nguyên và vẫn cứng: phải nằm trong dòng `0.8.x`.** Cả ba đổi khoá
cấu hình, tức đổi API công khai, mà **`0.9` sang Beta nơi API coi như đã chốt**. Lùi được
là vì `0.8.x` còn nhiều bản con, không phải vì hạn chót nới ra.

⭐ Vì sao lùi được mà không mất gì: **chưa app nào dùng Modbus/OPC UA/MQTT thật**, trong
khi chuyến Linux của chúng nặng hơn hẳn vì cả ba đều là mảng **đa tiến trình**. Cùng lý
do đã tách `0.8.1` khỏi `0.8.2` lần trước.

⏭ **Hoãn có ý thức, chủ dự án xác nhận lại 2026-08-22** (*"mấy thứ bạn gợi ý hoãn tôi
cũng thực sự muốn hoãn"*): *cha không có mồm* (mục 2.8c - cha không dựng DI nên không có
đường báo ra ngoài) · *supervisor trông tiến trình ngoài* · *tắt êm*. Cả ba **không phải
API** nên thêm ở bản nào cũng được.

## 4. Cần máy khác mới làm được

| Việc | Cần gì |
|---|---|
| **Hai phép đo LMDB** (mục 6.2 [`docs/thiet-ke/13-kho-store-lmdb.md`](docs/thiet-ke/13-kho-store-lmdb.md)) | **VPS Linux** - máy này là Windows. Không chặn gì: chúng để chỉnh tham số vận hành, không phải quyết định thiết kế |
| ~~**Bốn phép đo uvloop của 0.8.1**~~ | ✅ **XONG 2026-08-22** trên máy Linux của chính chủ dự án (Debian 13, Python 3.13.5), không cần VPS. [`docs/kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](docs/kiem-toan/0.8.1-ket-qua-do-tren-linux.md) |
| ⏳ **Phần đo còn thiếu của benchmark** | **Máy Linux.** gRPC streaming · socket adapter dưới tải · MQTT · phản hồi lớn nhiều KB · app có I/O database thật. **Không chặn gì** - kết luận uvloop cho 0.8.1 đã đủ cơ sở; đây là để mở rộng phạm vi kết luận |

## 5. Ngoài framework

| Việc | Ở đâu |
|---|---|
| Đợt 0 + A2 (CORS regex) + A4 của kiểm toán bảo mật | **Repo app.** Đợt 0 chờ chủ dự án quyết A6 (chỗ để secret) |
| Dựng trang **xime-framework.org** | `D:\code\xime framework\website`, Next.js xuất tĩnh, ưu tiên SEO. Mở từ 2026-08-01 |

---

# Năm thứ đừng đề xuất lại

Mỗi cái đã bị bác kèm lý do; danh sách đầy đủ nằm trong từng file thiết kế
(`docs/thiet-ke/10` mục 8 có **19 hướng**, `docs/thiet-ke/11` mục 11 có **19 hướng**).

| | Vì sao |
|---|---|
| **TLS mức 2 cho web adapter** | Không tránh được việc private key chạm đĩa, tức không giải quyết được vấn đề nó sinh ra để giải quyết. Cần thì làm **mức 1.5** - mục 4.0 [`docs/thiet-ke/07-tls-web-adapter.md`](docs/thiet-ke/07-tls-web-adapter.md) |
| **Hook SQLAlchemy chặn sửa entity ngoài transaction** | Phải trả phí runtime cho mọi lời đọc, trái nguyên tắc minimal magic. Bù bằng quy tắc tài liệu - [`rules/transaction.md`](rules/transaction.md) |
| **`LifecycleManager` gọi `pre_destroy()` khi `post_construct()` ném lỗi** | Dọn object khởi tạo dở sẽ **che lỗi gốc**. Chủ dự án chốt 2026-07-30: giữ nguyên |
| ⛔ **Nhận diện danh tính trên đường công khai** | **Chủ dự án chốt 2026-08-22, và dặn thẳng: *"đừng app nào đề nghị nữa"*.** Đường trong `public_paths` **không nhìn token, chấm hết**. Lý do ở mục ngay dưới - nó không phải "hoãn vì ít khách" |
| ⛔ **Job scheduler chạy riêng từng tiến trình** | **Chốt 2026-08-23.** Scheduler là adapter hạng `singleton`, chỉ chạy ở primary, và không có khoá cấu hình nào đổi được. Rà hết thì **0 ca nghiệp vụ** cần chạy theo tiến trình, và đó là hệ quả cấu trúc chứ không phải may - xem mục ngay dưới |

## ⛔ Vì sao đường công khai KHÔNG nhận diện - chốt vĩnh viễn 2026-08-22

Đề nghị đến từ phiên `linh-kien-dien-tu`: trang xem sản phẩm là công khai, nhưng nhân
viên đang đăng nhập mở đúng trang đó thì đáng lẽ phải thấy cả bản `DRAFT` của mình. Hôm
nay lớp chặn bỏ qua token trên đường công khai nên handler không biết ai đang hỏi.

Chủ dự án bác, và **lập luận quyết định là một chỗ cả người báo lẫn phiên framework đều
bỏ sót**:

> **Một trang gọi máy chủ qua NHIỀU đường, không phải một API duy nhất.**

Nên trang sản phẩm cứ gọi **hai** chỗ: catalog lấy từ đường công khai, còn phần riêng
của người đăng nhập (bản `DRAFT`) lấy từ một đường **có xác thực**. Không cần nhét danh
tính vào đường công khai để giải bài toán đó. Ca sử dụng sinh ra đề nghị này **tự giải
được bằng thứ đã có**, và giải sạch hơn.

### Ba chỗ hụt còn lại cũng tan theo, vì chúng thuộc FRONTEND

Phiên framework nêu ba câu thiết kế chưa có lời giải, trong đó nặng nhất là *"token hết
hạn thì handler thấy gì"* - nó gộp *không có token* với *token chết* thành cùng một
`identity = None`, tức vi phạm [luật 03](../../.claude/rules/03-mot-gia-tri-mot-nghia.md).
Chủ dự án chỉ ra câu đó **đặt sai tầng**:

| Việc | Thuộc về |
|---|---|
| Biết access token **sắp** hết hạn và xin cấp mới **trước khi** hết | **Frontend** |
| Refresh token sắp hết hạn thì xin xoay **ngay khi** vào trang | **Frontend** |
| Cả hai đã chết, hỏng | **Từ chối phục vụ.** Coi như chưa đăng nhập, là khách vãng lai - và đó là kết quả ĐÚNG |
| Biết mình có đang đăng nhập không, để hiện nút | **Frontend tự biết**, không phải hỏi endpoint công khai |

Nguyên văn: *"khách cứ vào app, bất kể đường nào thì token hết hạn thì đổi token đi...
còn mà hết hạn, hỏng thì chịu. từ chối phục vụ. ở frontend phải biết được mình có đăng
nhập không để hiện nút."*

⭐ Nói cách khác: **trạng thái ba mặt (không token / token tốt / token chết) là trạng
thái của TRÌNH DUYỆT, và trình duyệt là bên duy nhất biết đủ để xử lý nó.** Đẩy nó xuống
lớp chặn của máy chủ là bắt máy chủ trả lời một câu mà nó không có dữ liệu để trả lời -
rồi sinh ra đúng cái vi phạm luật 03 mà phiên framework đã nhìn thấy.

⚠ Điều kiện đi kèm, chủ dự án khai rõ: cách này đòi **frontend động**. Trang tĩnh chỉ có
HTML thì không làm được - và đó là giới hạn chấp nhận, không phải chỗ cần vá.

### Hai hệ quả để phiên sau khỏi đào lại

1. **Đây KHÔNG phải "hoãn tới khi có khách thứ hai".** Bản phân tích trước có ghi vậy;
   câu đó **hết đúng** từ 2026-08-22. Ca sử dụng gốc giải được bằng kiến trúc sẵn có,
   nên thêm khách cũng không đổi kết luận.
2. **`public_paths` chở đúng MỘT ý định, không phải hai.** Bản phân tích trước đóng khung
   nó thành *"một danh sách chở hai ý định"* rồi kết luận lời giải là hai danh sách. Sai
   tiền đề: *"đường này không cần danh tính"* và *"đường này không được nhận diện"* là
   **cùng một câu** khi phần biết-mình-là-ai nằm ở frontend. Không có luật 03 nào bị vi
   phạm ở đây, nên không có gì phải tách.

## ⛔ Vì sao scheduler KHÔNG chạy theo tiến trình - chốt 2026-08-23

Chủ dự án hỏi: *"liệu có tồn tại logic nghiệp vụ nào mà hẹn giờ lại riêng cho từng
tiến trình không... nếu có thì liệu có phải thiếu sót không hay vẫn giải được bằng
liên lạc đa tiến trình."*

Rà hết thì **0 ca nghiệp vụ**, và điều đáng ghi lại không phải con số mà là **lý do
nó bằng 0**:

> Nghiệp vụ theo định nghĩa là chạm dữ liệu của khách, mà dữ liệu của khách **không
> bao giờ** nằm riêng trong bộ nhớ một tiến trình - [luật 01](../../.claude/rules/01-song-song-hoa-va-shard.md)
> nghĩa 1 cấm đúng điều đó. Nó nằm ở DB, ở `RefData`, ở `Store`, tức mọi tiến trình
> với tới như nhau. Đã vậy thì chạy job ở bốn nơi không cho thêm gì.

⭐ **Hệ quả dùng được làm phép kiểm, đưa cho phiên app khi họ hỏi:**

> **Một job nghiệp vụ mà *cần* chạy riêng từng tiến trình là một job đang phụ thuộc
> vào thứ chỉ tiến trình đó có. Tức nó đã vi phạm luật 01 từ trước, và bản vá đúng
> không phải cho nó chạy N lần mà là đẩy cái trạng thái kia ra ngoài.**

### Hai loại việc thật sự phải chạy theo tiến trình, và cả hai ở ngoài scheduler

| Loại | Nhà của nó |
|---|---|
| **Quan trắc số đo của chính tiến trình** | Đây là khe hở duy nhất còn lại, vì luật 01 cho phép đúng hai thứ ở lại trong RAM: *số đo* và *bản sao đọc có nguồn bền vững* - vế sau nay là `RefData` nên tự khép. Nhưng cụm **dùng chung một socket**, nên một lượt scrape rơi ngẫu nhiên vào một tiến trình: **không gộp thì con số vô nghĩa dù có bao nhiêu scheduler**. Lời giải là gom qua `ProcessLink` rồi đẩy một lần |
| **Thiết bị một tiến trình độc quyền giữ** (Modbus, OPC UA, tập topic MQTT) | Nghiệp vụ thật, nhưng thuộc adapter hạng `sharded` với cơ chế riêng (`@poll`, `@on_change` chạy một lần **mỗi thực thể**) - xem mục 3c |

### Thiếu sót không? Về hành vi thì không, về API thì có một chỗ phải biết

**Đường thoát tồn tại và không tốn gì:** một adapter `scaling="replicated"` mà `serve()`
là vòng lặp `sleep` thì chạy ở mọi tiến trình. Đó chính là thứ `SchedulerAdapter` đang
là, khác đúng một chữ `scaling`. Ví dụ chép được nằm trong `docs/{vn,en}/starters.md`.

⚠ **`CronJob`/`IntervalJob` không có trường phạm vi, và `SchedulerAdapter` khai
`scaling` ở tầng lớp.** Thêm một trường phạm vi là **đổi API công khai**, mà `0.9` sang
Beta nơi API coi như đã chốt - nên nếu bao giờ muốn để ngỏ cửa đó thì nó phải nằm trong
`0.8.x`, không lùi được.

⛔ **Khuyến nghị đã chốt: đừng thêm.** Không phải vì *"chưa ai cần"* mà vì cửa đó **hỏng
theo chiều im lặng**: khai nhầm `per_process` cho một job gửi email nhắc là gửi bốn lần,
không exception, không test đỏ - đúng hạng *"chạy hai lần thì SAI"* của luật 01. Một cửa
như vậy phải rất đáng mới đáng mở, mà ca duy nhất còn lại (số đo) đã có lời giải sạch hơn.

### `ProcessLink` giải được gì

| Chiều | |
|---|---|
| primary tick rồi phát lệnh cho mọi tiến trình làm việc cục bộ | **giải sạch**, job vẫn `singleton` |
| mọi tiến trình gửi số đo về gộp lại | **giải sạch**, và ở ca metrics đây là cách **đúng** chứ không phải cách thay thế |
| việc phải chạy được **khi primary đã chết** | ⛔ không, vì lệnh đi qua chính thứ vừa chết. Đó là lý do watchdog nằm ở **tiến trình cha** |


# Hai bài học đắt nhất, để ở đây vì chúng sẽ lặp

**1. Viết ít nhất một test đi đúng con đường TÀI LIỆU hướng dẫn**, không phải con đường
tiện nhất cho test. Ba lỗi mức Cao của 0.7.0 và hai lỗi của 0.8 giai đoạn 1 đều nằm ở chỗ
nối, và **không test nào bắt được** vì test luôn đi đường tắt mà người dùng thật không có.

**2. *"Không test nào đỏ"* có BA nghĩa, không phải hai:** test thiếu · phép đo nhắm sai ·
**hoặc bản vá không làm việc mà lời giải thích của nó nói**. Nghĩa thứ ba dễ bỏ qua nhất,
vì code vẫn đúng. Cách duy nhất tách được là **đối chứng**: gỡ bản vá ra rồi đếm test đỏ,
và đếm **treo** thành một kết cục riêng chứ đừng gộp vào *đỏ*.
