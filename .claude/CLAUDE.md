# XIME Framework - Hướng dẫn phiên làm việc

> **File này trả lời đúng một câu: *hôm nay đứng ở đâu, làm gì tiếp*.**
> Nó KHÔNG trả lời *"chuyện gì đã xảy ra"* - câu đó thuộc về `CHANGELOG.md` và
> [`docs/`](docs/README.md). Sắp xếp lại 2026-08-21, từ 1770 dòng xuống còn chừng này.

## Trạng thái

**`0.8.1` ĐÃ PHÁT HÀNH 2026-08-22.** Commit, tag, và đẩy PyPI đều xong. **SHA256 gói
trên PyPI khớp từng bit** với gói dựng ở máy này, và cài từ PyPI vào venv trắng chạy được.

| | |
|---|---|
| PyPI | **`0.8.1`** - bản thứ **15**, đẩy lên 2026-08-22 07:32 UTC |
| `pyproject` tại chỗ | **`0.8.1`** |
| Repo phát triển | **`d5b5806 v0.8.1`**, tag `v0.8.1`, cây làm việc **sạch** |
| Repo phát hành | **`4ac504f v0.8.1`**, tag `v0.8.1`, cây làm việc **sạch** |

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

📌 **Chưa push lên GitHub, và đó là CỐ Ý** - 2 commit đang chờ. Luật workspace: 9 repo có
remote mang tài liệu nội bộ trong `.claude/`, chủ dự án chốt không push, và việc lọc
trước khi push (nếu có ngày push) thuộc thẩm quyền chủ dự án.

**0.8.0 đã phát hành 2026-08-21**: kiểm toán sáu đợt, vá 28 mục, và **SHA256 gói trên
PyPI khớp từng bit** với gói dựng ở máy này.

Vì `xime` cài **editable** nên mã ở đây có hiệu lực ngay với **31 app** trên máy này -
chúng đã chạy `0.8.1` từ trước lúc phát hành.

✅ **Hai chuyến Linux đã nhận về, cả hai đối chứng từng byte:**

| Chuyến | Kết quả |
|---|---|
| Vá `0.8.0` (2026-08-21) | 80 file · **629/629 khớp**. [`docs/nhap/ban-giao-cho-phien-windows.md`](docs/nhap/ban-giao-cho-phien-windows.md) |
| Đo uvloop `0.8.1` (2026-08-22) | 25 file mới + 5 sửa · **660/660 khớp**. [`docs/nhap/ban-giao-cho-phien-windows-0.8.1.md`](docs/nhap/ban-giao-cho-phien-windows-0.8.1.md) và [`docs/kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](docs/kiem-toan/0.8.1-ket-qua-do-tren-linux.md) |


### Kỳ vọng bộ test - HAI con số, theo hệ điều hành

| Nền tảng | `passed` | `skipped` | `failed` | **Tổng** |
|---|---|---|---|---|
| **Linux** | **2552** ✅ đo 2026-08-22 | 6 | 0 | **2558** |
| **Windows** | **2534** ✅ đo 2026-08-22 | 24 | 0 | **2558** |

⭐ **Cộng 24 kể từ 0.8.0** (tổng `2534` -> `2558`): **16** của
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

Chênh 18 là **test bị chặn bởi nền tảng**, đã đếm từng cái - Windows bỏ qua, Linux chạy:

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

### Đã xong, chờ commit

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

### Đã code 2026-08-22, chờ commit

| # | Việc | Trạng thái |
|---|---|---|
| **1** | **`public_paths` khớp được tiền tố** - `configure_jwt(public_paths=["/api/v1/parts/*"])` | ✅ **XONG** |
| **2** | **Một dòng `INFO` khai trạng thái xác thực** lúc khởi động | ✅ **XONG** |

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

#### Việc 2 - đo được, không phải suy đoán

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
| **Nhận diện trên đường công khai** (mục 3 báo cáo `linh-kien`) | ⛔ **BÁC VĨNH VIỄN - chủ dự án chốt 2026-08-22**, kèm câu dặn *"đừng app nào đề nghị nữa"*. Lý do quyết định **không phải ba câu thiết kế tôi nêu**, mà là một chỗ cả tôi lẫn người báo bỏ sót: **một trang gọi máy chủ qua nhiều đường**, nên phần riêng của người đăng nhập lấy từ một đường CÓ xác thực, không cần nhét danh tính vào đường công khai. Ca sử dụng tự giải được bằng thứ đã có. Đầy đủ: mục [Bốn thứ đừng đề xuất lại](#bốn-thứ-đừng-đề-xuất-lại) |
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

# Bốn thứ đừng đề xuất lại

Mỗi cái đã bị bác kèm lý do; danh sách đầy đủ nằm trong từng file thiết kế
(`docs/thiet-ke/10` mục 8 có **19 hướng**, `docs/thiet-ke/11` mục 11 có **19 hướng**).

| | Vì sao |
|---|---|
| **TLS mức 2 cho web adapter** | Không tránh được việc private key chạm đĩa, tức không giải quyết được vấn đề nó sinh ra để giải quyết. Cần thì làm **mức 1.5** - mục 4.0 [`docs/thiet-ke/07-tls-web-adapter.md`](docs/thiet-ke/07-tls-web-adapter.md) |
| **Hook SQLAlchemy chặn sửa entity ngoài transaction** | Phải trả phí runtime cho mọi lời đọc, trái nguyên tắc minimal magic. Bù bằng quy tắc tài liệu - [`rules/transaction.md`](rules/transaction.md) |
| **`LifecycleManager` gọi `pre_destroy()` khi `post_construct()` ném lỗi** | Dọn object khởi tạo dở sẽ **che lỗi gốc**. Chủ dự án chốt 2026-07-30: giữ nguyên |
| ⛔ **Nhận diện danh tính trên đường công khai** | **Chủ dự án chốt 2026-08-22, và dặn thẳng: *"đừng app nào đề nghị nữa"*.** Đường trong `public_paths` **không nhìn token, chấm hết**. Lý do ở mục ngay dưới - nó không phải "hoãn vì ít khách" |

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

# Hai bài học đắt nhất, để ở đây vì chúng sẽ lặp

**1. Viết ít nhất một test đi đúng con đường TÀI LIỆU hướng dẫn**, không phải con đường
tiện nhất cho test. Ba lỗi mức Cao của 0.7.0 và hai lỗi của 0.8 giai đoạn 1 đều nằm ở chỗ
nối, và **không test nào bắt được** vì test luôn đi đường tắt mà người dùng thật không có.

**2. *"Không test nào đỏ"* có BA nghĩa, không phải hai:** test thiếu · phép đo nhắm sai ·
**hoặc bản vá không làm việc mà lời giải thích của nó nói**. Nghĩa thứ ba dễ bỏ qua nhất,
vì code vẫn đúng. Cách duy nhất tách được là **đối chứng**: gỡ bản vá ra rồi đếm test đỏ,
và đếm **treo** thành một kết cục riêng chứ đừng gộp vào *đỏ*.
