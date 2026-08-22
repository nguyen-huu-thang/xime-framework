# Bàn giao cho phiên Linux: đo uvloop của 0.8.1

> | | |
> |---|---|
> | **Trạng thái** | **ĐANG DÙNG** - viết 2026-08-22, chờ phiên Linux thi hành |
> | **Thuộc bản** | `0.8.1` (uvloop) |
> | **Thay cái gì** | Không thay gì. Là **chiều ngược** của [`ban-giao-cho-phien-windows.md`](ban-giao-cho-phien-windows.md) (đợt 0.8.0, Linux -> Windows) |
> | **Bị thay bởi** | `kiem-toan/0.8.1-ket-qua-do-tren-linux.md` khi phiên Linux đo xong |
>
> Viết bởi phiên Windows, cho một phiên Linux **chưa từng chạy ở đây, không có bộ nhớ,
> không có lịch sử cuộc trò chuyện**. Cùng một máy, chỉ khác hệ điều hành.
>
> Đọc hết mục 0 trước khi gõ lệnh đầu tiên. Nó ngắn.

## 0. Năm thứ phải biết trước

| # | |
|---|---|
| 1 | **Bản vá uvloop của 0.8.1 đã code xong trên Windows và bộ test ở đó xanh.** Việc của phiên này là **ĐO**, không phải đi tìm việc mới |
| 2 | ⭐⭐ **Trên Windows, nhánh uvloop chưa chạy một lần nào.** uvloop không có wheel Windows và sẽ không bao giờ có, nên ở đó `uvloop_factory()` **luôn trả `None`**. 16 test canh bên đó chỉ chứng minh *"đường dây nối đúng"*. **Máy này là nơi tính năng đó chạy lần đầu tiên** |
| 3 | ⚠⚠ **Bộ test xanh KHÔNG chứng minh uvloop hoạt động** - đọc mục 3.1 trước khi báo cáo bất cứ điều gì. Đây là cái bẫy lớn nhất của cả chuyến |
| 4 | **Hai kết cục đều hợp lệ**: bốn phép đo đạt thì **không sửa dòng code nào**, chỉ ghi kết quả rồi trả về Windows. Một phép đo hỏng thì **sửa tại chỗ, ở đây** - vì Windows không tái hiện được |
| 5 | ⛔ **Chủ dự án tự commit, tự tag, tự đẩy PyPI.** Phiên này không làm ba việc đó |

### Bản vá gồm đúng những gì

| File | |
|---|---|
| `xime/core/bootstrap/_loop.py` | **mới** - `uvloop_factory()`, trả `None` khi không import được |
| `xime/core/bootstrap/_supervisor.py` | `worker_loop_factory` tách thành **ba nhánh**: Windows+socket kế thừa -> selector · Windows -> `None` · **Linux/macOS -> `uvloop_factory()`** |
| `xime/core/bootstrap/application.py` | `_log_running_loop()` - log loop **đang chạy thật**, gọi ở đầu `_run_async()` |
| `xime/adapters/web/ws/_availability.py` | **mới** - cảnh báo khi app có route `@ws` mà uvicorn không có thư viện WebSocket nào |
| `xime/adapters/web/_adapter.py` | móc cảnh báo trên vào, **sau** cửa thoát sớm `if not handlers: return` |
| `tests_temp/bootstrap/test_event_loop.py` | **mới**, 16 test |
| `tests_temp/ws/test_ws_availability.py` | **mới**, 8 test |

Thiết kế đầy đủ: [`sap-toi/tang-toc-uvicorn-uvloop.md`](../sap-toi/tang-toc-uvicorn-uvloop.md).
Mục 5 của nó là bốn phép đo; mục 12 là kết quả thi công trên Windows.

---

## 1. Nhận mã

### Bước 0 - Chụp ảnh trạng thái bên này TRƯỚC khi chép đè

⛔ **Đừng bỏ qua bước này.** Thư mục nháp bên Linux là nơi đợt vá 0.8.0 được làm (9
commit). Nếu ở đó còn thứ **chưa từng mang sang Windows** thì chép đè là **mất hẳn**.

```bash
cd <thu-muc-nhap>
git status
git log --oneline -5
git stash list
```

| Thấy gì | Làm gì |
|---|---|
| Sạch, `HEAD` là commit đã có bên Windows | Chép đè thoải mái |
| Có thay đổi chưa commit, hoặc commit lạ | **DỪNG, báo chủ dự án.** Đừng tự quyết bỏ hay giữ |

⭐ Cách rẻ nhất để không phải nghĩ: `git add -A && git commit -m "Moc truoc khi nhan ban tu Windows"`.
Có mốc rồi thì chép đè không mất gì, và `git diff` sau đó hiện đúng phần từ Windows.

### Bước 1 - Chép

Nguồn là `D:\code\xime\xime framework` bên Windows. Chủ dự án chuyển sang bằng cách
đóng gói, hoặc phiên này đọc thẳng nếu phân vùng đó mount được.

```bash
# Nếu ổ D mount được (thường /mnt/d hoặc /media/<user>/...), đây là đường rẻ nhất:
mount | grep -i ntfs        # xem có gì đang mount không
ls /mnt/d/code/xime 2>/dev/null || ls /media/*/code/xime 2>/dev/null
```

Chép **loại trừ** ba thứ, cả ba đều là rác sinh lại được và đều gây nhiễu:

```bash
rsync -av --delete \
  --exclude '__pycache__' --exclude '.pytest_cache' --exclude '*.egg-info' \
  --exclude '.git' \
  "<nguon>/xime framework/" "<thu-muc-nhap>/"
```

⚠ **`--exclude '.git'` cộng `--delete` là an toàn**, vì `--delete` chỉ xoá thứ nằm
trong phạm vi được đồng bộ, mà `.git` đã bị loại khỏi phạm vi đó. Không chắc thì **bỏ
`--delete`** - đợt này không xoá file nào, chỉ thêm và sửa.

⚠ **Nếu chép qua Windows thì `\r\n` có thể lẫn vào.** Kiểm nhanh:

```bash
file xime/core/bootstrap/_loop.py     # "ASCII text" moi dung; "with CRLF" thi phai doi
```

### Bước 2 - Soát

```bash
git status
git diff --stat
```

**Kỳ vọng: 4 file mới, 3 file sửa, 0 file xoá** (danh sách ở mục 0). Ra khác thì dừng
lại xem vì sao trước khi chạy tiếp.

---

## 2. Dựng môi trường, và phép kiểm ĐẦU TIÊN phải chạy

```bash
cd <thu-muc-nhap>
pip install -e ".[dev]"
```

Extra `dev` kéo về `mypy`, `ruff`, `pytest`, và **`uvicorn[standard]` kéo `uvloop`**.

### ⭐ Positive control - chạy TRƯỚC mọi thứ khác

Nếu uvloop không thật sự cài được ở đây thì **cả chuyến này vô nghĩa**: mọi phép đo
sẽ chạy trên loop mặc định và báo "đạt" mà không đo gì cả. Đó là đúng khuôn *"một chốt
chặn không chạy trông y hệt một chốt chặn không có việc để làm"*.

```bash
python -c "
import uvloop, importlib.metadata as m
print('uvloop', m.version('uvloop'))
from xime.core.bootstrap._loop import uvloop_factory
print('uvloop_factory ->', uvloop_factory())
from xime.core.bootstrap._supervisor import worker_loop_factory
print('worker_loop_factory({}) ->', worker_loop_factory({}))
"
```

**Phải thấy cả ba dòng có giá trị thật.** `uvloop_factory -> None` ở đây nghĩa là
uvloop chưa cài được - **dừng lại, sửa môi trường**, đừng chạy tiếp.

---

## 3. Bộ test

```bash
python -m pytest -q
```

| Nền tảng | `passed` | `skipped` | `failed` | **Tổng** |
|---|---|---|---|---|
| **Linux** (chờ phiên này đo) | **2552** dự kiến | 6 | 0 | **2558** |
| Windows (đo thật 2026-08-22) | 2534 | 24 | 0 | **2558** |

⚠ **Tiêu chí đạt là TỔNG `2558` cộng `0 failed`, không phải `passed`.** Chênh 18 là test
bị chặn bởi nền tảng (Windows bỏ qua, Linux chạy): `POSIX permission bits` 9 · `/dev/shm`
4 · `unix socket` 4 · `chmod 000` 1. Sáu lượt bỏ qua của Linux thì bỏ qua ở **cả hai**
bên vì thiếu S3 (`127.0.0.1:9000`) và MQTT broker (`127.0.0.1:1883`).

⚠ Con số Linux `2552` là **suy ra** (2528 của 0.8.0 cộng 24 test mới), **chưa ai đo**.
Ra khác vài đơn vị thì kiểm xem test mới có ca nào phụ thuộc nền tảng không, đừng vội
kết luận bản chép hỏng.

📌 Con số `2534` xuất hiện với **hai nghĩa**: tổng của 0.8.0, và `passed` của Windows ở
0.8.1. Trùng số, khác trục - đúng kiểu nhầm mà con số bàn giao sai của đợt trước đã cắn.

### 3.1. ⚠⚠ Bộ test xanh KHÔNG chứng minh uvloop hoạt động

**Đây là điều quan trọng nhất của cả tài liệu này.**

`pytest-asyncio` **tự dựng event loop của nó**. Nó không đi qua `Application.run()`, nên
nó không chạm `worker_loop_factory` một lần nào. Nghĩa là:

> 2552 test xanh trên Linux chứng minh **bản vá không phá gì**. Nó **không** chứng minh
> một dòng nào về việc app chạy được dưới uvloop.

Báo cáo *"test xanh nên uvloop ổn"* là kết luận sai, và nó là kiểu sai khó bắt vì con số
trông rất thuyết phục. Bốn phép đo ở mục 5 tồn tại **chính vì** chỗ này.

### 3.2. Tuỳ chọn: chạy lại bộ test DƯỚI uvloop

Nếu làm được thì đây là phép đo mạnh nhất của cả chuyến - nó phủ TLS, `SO_PEERCRED` và
mọi thứ đi qua transport asyncio, trong một lượt.

> ⛔⭐ **ĐÍNH CHÍNH 2026-08-22, sau khi chuyến này chạy xong: công thức bản đầu
> KHÔNG hoạt động, và nó XANH GIẢ.** Nó dựng một fixture `event_loop_policy`
> trong plugin nạp bằng `-p`; `pytest-asyncio` 1.4 **đã định nghĩa sẵn fixture
> cùng tên của chính nó**, và fixture của plugin **không đè được**. Chạy ra
> `2552 passed` trông rất thuyết phục trong khi **không một test nào chạy dưới
> uvloop**.
>
> ⚠ Và lời đoán nguyên nhân ở bản đầu (*"Python 3.14 deprecate policy"*) cũng
> sai: máy đó là **3.13.5**. Đoán đúng là có chuyện, **đoán sai chỗ** - tin lời
> đoán đó thì đi sửa nhầm chỗ. Chi tiết:
> [`kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](../kiem-toan/0.8.1-ket-qua-do-tren-linux.md)
> mục 5.3.

**Cách chạy được** - đặt policy toàn cục ngay lúc import plugin, để chính fixture
mặc định của `pytest-asyncio` nhặt lên:

```bash
cat > /tmp/plugin_uvloop.py <<'EOF'
import asyncio
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
EOF
PYTHONPATH=/tmp python -m pytest -q -p plugin_uvloop
```

⛔ **Kiểm bằng đối chứng HAI CHIỀU trước khi tin bất kỳ con số nào**: một test in
ra `type(asyncio.get_running_loop())` phải cho `uvloop.Loop` **khi có** plugin và
selector **khi không có**. Thiếu đối chứng thì hai lượt cho **cùng một con số**,
nên **không có gì trong kết quả tự tố cáo** - đúng
[luật 03](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md) mục 4b: *"pass"*
gộp cả **đã kiểm chứng, sạch** lẫn **phép đo không hề chạy**.

**Không chạy được thì bỏ qua, ghi lại là "không chạy được vì X"** rồi đi tiếp mục
5. Đừng đốt thời gian ở đây - mục 5 mới là thứ bắt buộc.

---

## 4. `mypy` - phép kiểm Windows chưa từng chạy

```bash
python -m mypy xime/
```

**Mốc so sánh: 41 lỗi ở 0.8.0.** Bản vá không được thêm lỗi nào.

⭐ Đây là công cụ **duy nhất** tìm ra C5 (`SocketAdapter.assign_slot()` ném
`AttributeError`) ở đợt kiểm toán 0.8. Nó chưa bao giờ chạy trên máy Windows vì `mypy`
được khai trong extra `dev` mà chưa cài ở đó.

```bash
python -m ruff check xime/ tests_temp/
```

---

## 5. BỐN PHÉP ĐO - phần bắt buộc, chúng chặn phát hành 0.8.1

Mỗi phép đo có một câu hỏi và một cách trả lời **bằng tiến trình thật**, không bằng
test. Ghi kết quả theo khuôn ở mục 7.

### Đo 1 - Bắt tay TLS thật qua web adapter 🔴 rủi ro cao nhất

**Vì sao:** uvloop có **hiện thực SSL riêng**, và đây là chỗ nó lệch khỏi stdlib nhiều
nhất. Web adapter đẩy thẳng `ssl_*` xuống uvicorn.

```bash
# 1. Cert tự ký (bộ test đã có sẵn khuôn ở tests_temp/web/test_tls.py)
cd /tmp && mkdir -p tls && cd tls
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 1 -nodes -subj "/CN=localhost"

# 2. Dựng một app tối thiểu có server.ssl trỏ vào hai file trên, rồi chạy
#    (khuôn app: <thu-muc-nhap>/tests_temp/processes/sample_one/)

# 3. Xác nhận LOG nói uvloop, rồi bắt tay thật
curl -vk https://127.0.0.1:<port>/...
```

| Đạt khi | |
|---|---|
| Log khởi động | `event loop: uvloop.Loop` **và** `web default: ... (HTTPS)` |
| `curl -vk` | bắt tay xong, có phản hồi HTTP |

⚠ **Phải thấy dòng `uvloop.Loop` trước khi tin kết quả curl.** Không có nó thì phép đo
đang chạy trên loop mặc định và không đo gì cả.

### Đo 2 - `SO_PEERCRED` của socket adapter 🟡

**Vì sao:** `xime/adapters/socket/_peercred.py` gọi `writer.get_extra_info("socket")`
rồi `getsockopt`. uvloop trả về một `TransportSocket` **bọc** chứ không phải socket
trần. Về lý thuyết nó proxy đủ, nhưng đó là suy luận, không phải phép đo.

```bash
# Chạy socket adapter thật rồi nối vào bằng một client, xem peer uid/pid có đọc được không.
# Khuôn: tests_temp/socket/test_socket.py (2 test này Windows bỏ qua, Linux chạy)
```

| Đạt khi | `uid`/`pid` của client đọc ra **đúng**, không `None`, không ném |

### Đo 3 - `share_load()` với socket kế thừa từ cha 🟡

**Vì sao:** `create_server(sock=...)` dưới uvloop, trên một socket đã `bind` và `listen`
ở **tiến trình khác**. Cùng họ với cái bẫy `WinError 87` của Windows.

```bash
# Dựng cấu hình có khối processes: với count >= 2, chạy app thật,
# rồi bắn request nhiều lần xem CẢ HAI tiến trình đều trả lời.
```

| Đạt khi | Mọi tiến trình con log `event loop: uvloop.Loop` **và** cùng phục vụ được trên một cổng |

⚠ **Cách hỏng cần phòng đúng là cách hỏng của `WinError 87`**: con thứ hai khởi động
**thành công**, log *"serving"*, rồi **không nhận nổi một kết nối nào**. Nên đo bằng
cách bắn nhiều request và đếm xem có bao nhiêu tiến trình thật sự trả lời, đừng đo bằng
việc "nó khởi động được".

### Đo 4 - Lãi thật 🟢 không chặn, nhưng quyết định có giữ hay không

**Vì sao:** uvloop thường cho 1,5 tới 2 lần thông lượng ở tải nhiều kết nối nhỏ. Nếu app
chặn ở Postgres thì phần lãi teo lại gần hết. **Đo trước, rồi hẵng kết luận.**

Không có công tắc bật/tắt uvloop (đó là quyết định thiết kế, xem mục 6.1 của tài liệu
gốc), nên so sánh bằng cách **tạm** cho `uvloop_factory()` trả `None`:

```bash
# Lượt A: nguyên bản (uvloop)
# Lượt B: sửa TẠM xime/core/bootstrap/_loop.py cho `uvloop_factory` return None ngay đầu hàm
# Cùng một app, cùng một lệnh bắn tải:
hey  -n 20000 -c 100 http://127.0.0.1:<port>/...     # hoac: wrk, ab, oha
```

⛔ **Khôi phục `_loop.py` sau khi đo.** Đừng commit bản sửa tạm.

Ghi lại **cả hai** con số cộng tên công cụ và tham số. Một con số không có đối chứng thì
không nói lên gì.

---

## 6. Hai kết cục, cả hai đều hợp lệ

```text
Bốn phép đo đạt  ->  KHÔNG sửa dòng code nào  ->  ghi kết quả  ->  trả về Windows
Một phép đo hỏng ->  sửa TẠI ĐÂY               ->  đo lại      ->  ghi cả hai lượt
```

**Nhánh thứ hai là lý do chuyến này tồn tại.** Windows không tái hiện được lỗi uvloop về
mặt cấu trúc, nên sửa ở đây là đúng chỗ, không phải việc phát sinh ngoài kế hoạch.

⚠ Nếu phải sửa, **đừng thêm công tắc bật/tắt uvloop** như một cách né. Mục 6.1 của tài
liệu gốc đã loại phương án đó kèm ba lý do. Hỏng ở đâu thì vá đúng chỗ đó, hoặc thu hẹp
phạm vi uvloop cho **một adapter cụ thể** kèm lý do đo được.

⚠ Và nếu một phép đo hỏng theo kiểu không vá nổi thì **báo chủ dự án, đừng tự quyết
rollback cả bản vá** - đó là quyết định về sản phẩm.

---

## 7. Ghi kết quả vào đâu

Tạo **một file mới** trong chính repo này, để khi thư mục được đóng gói mang về Windows
thì nó đi theo:

```text
<thu-muc-nhap>/.claude/docs/kiem-toan/0.8.1-ket-qua-do-tren-linux.md
```

Khuôn tối thiểu - đừng bỏ cột nào:

```markdown
# Kết quả đo uvloop 0.8.1 trên Linux

Đo ngày <ngày>. Python <bản>, uvloop <bản>, uvicorn <bản>, distro <tên>.

## Positive control
uvloop_factory() -> <giá trị thật>

## Bộ test
<passed> passed / <skipped> skipped / <failed> failed  (tổng <n>)
mypy: <n> lỗi (mốc 0.8.0 là 41)
ruff: <sạch hay không>

## Bốn phép đo
| # | Phép đo | Kết quả | Bằng chứng |
|---|---|---|---|
| 1 | Bắt tay TLS | ĐẠT / HỎNG / CHƯA KẾT LUẬN ĐƯỢC | <log, lệnh, đầu ra> |
| 2 | SO_PEERCRED | ... | ... |
| 3 | share_load socket kế thừa | ... | ... |
| 4 | Lãi thật | A=<số> B=<số> | <công cụ, tham số> |

## Có sửa code không
<không / có: liệt kê file và lý do>

## Thứ phiên Windows cần biết
<mọi thứ bất ngờ, kể cả thứ trông vô hại>
```

⭐ **Ba kết cục, không phải hai**: `ĐẠT` · `HỎNG` · **`CHƯA KẾT LUẬN ĐƯỢC`** (không dựng
được môi trường, thiếu công cụ, không tái hiện được). Gộp ô thứ ba vào `ĐẠT` là báo xanh
cho một phép kiểm chưa hề chạy - đúng thứ [luật 03](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md)
mục 4b cấm, và repo này đã cắn nó một lần với `ShardValueGuard`.

⚠ **Ghi cả thứ trông vô hại.** Đợt 0.8.0, phần giá trị nhất của sổ đo Linux không phải
kết quả các phép đo mà là hai lỗi *"máy phát triển không thể thấy"* tìm ra dọc đường.

---

## 8. Trả về Windows

Không cần làm gì đặc biệt: chủ dự án đóng gói thư mục này rồi chuyển sang ổ D. Chỉ cần
bảo đảm hai điều:

| | |
|---|---|
| File kết quả đã nằm trong repo | `.claude/docs/kiem-toan/0.8.1-ket-qua-do-tren-linux.md` |
| Nếu có sửa code | `git status` sạch hoặc đã commit, để phiên Windows `git diff` ra đúng phần từ đây |

**Việc còn lại sau chuyến này** (phiên Windows + chủ dự án làm): cập nhật `CHANGELOG.md`,
`pip install -e .`, commit, tag `v0.8.1`, đồng bộ repo phát hành
`D:\code\xime framework\upload`, `python -m build`, `twine check`, rồi đẩy PyPI.

⛔ **Đừng làm hộ commit/tag/PyPI.** Chủ dự án tự làm.

---

## 9. Liên quan

- [`sap-toi/tang-toc-uvicorn-uvloop.md`](../sap-toi/tang-toc-uvicorn-uvloop.md) - thiết kế
  đầy đủ. Mục 5 là bốn phép đo (bản gốc, chi tiết hơn ở phần *vì sao*), mục 12 là kết
  quả thi công trên Windows và bốn đối chứng.
- [`ban-giao-cho-phien-windows.md`](ban-giao-cho-phien-windows.md) - chiều ngược, đợt
  0.8.0. Đọc mục 4 của nó để hiểu vì sao *"có những lớp lỗi máy phát triển không thể
  nhìn thấy"* là một ràng buộc cấu trúc chứ không phải chuyện test yếu.
- [`kiem-toan/0.8-cho-do-tren-linux.md`](../kiem-toan/0.8-cho-do-tren-linux.md) - sổ đo của
  đợt trước, dùng làm khuôn cho file kết quả.
- [`../CLAUDE.md`](../../CLAUDE.md) - trạng thái hiện tại, bảng kỳ vọng test, việc đang chờ.
