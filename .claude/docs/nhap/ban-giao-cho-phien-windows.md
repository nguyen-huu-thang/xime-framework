# Bàn giao cho phiên Windows: nhận bản vá Linux rồi phát hành 0.8.0

> Viết ngày **2026-08-21** bởi phiên Linux, cho một phiên Windows **chưa từng
> chạy ở đây, không có bộ nhớ, không có lịch sử cuộc trò chuyện**.
>
> Đọc hết mục 0 trước khi gõ lệnh đầu tiên. Nó ngắn.

## 0. Bốn thứ phải biết trước

| # | |
|---|---|
| 1 | **Framework `0.8.0` đã code xong, đã kiểm toán SÁU đợt, đã vá 28 mục. Chưa phát hành.** Việc của phiên này là *nhận bản vá về, kiểm lần cuối, rồi phát hành* - **không phải** đi tìm việc mới |
| 2 | **Bản vá làm trên Linux vì có hai lớp lỗi Windows KHÔNG THỂ thấy** (mục 4). Điều đó nghĩa là: đừng ngạc nhiên nếu `git diff` có thứ trông như "sửa cái đang chạy tốt" |
| 3 | ⛔ **Chủ dự án tự commit, tự tag, tự đẩy PyPI.** Phiên này chuẩn bị mọi thứ tới sát mép rồi **dừng lại**, không làm hộ ba việc đó |
| 4 | ⭐ **Kỳ vọng bộ test KHÁC NHAU theo hệ điều hành**: Linux `2528 passed / 6 skipped`, Windows `2510 passed / 24 skipped`, **tổng `2534` ở cả hai**. Xem mục 3 |

⚠⚠ **Đừng tin con số `2518`** nếu gặp nó ở bất kỳ tài liệu cũ nào. Nó ghi giữa
chừng một commit, trước khi file test cuối của chính commit đó xong. HEAD sạch đo
lại là **2520**; cộng 8 test canh của đợt 6 thành **2528**.

⚠⚠ **Và `2528` cũng KHÔNG phải một con số toàn cầu** - nó là con số của **Linux**.
Bản trước của tài liệu này dặn *"ra khác là có chuyện"*, mà trên Windows ra khác lại
là **đúng**. Đo thật ngày 2026-08-21:

| Nền tảng | `passed` | `skipped` | `failed` | **Tổng** |
|---|---|---|---|---|
| Linux | 2528 | 6 | 0 | **2534** |
| Windows | 2510 | 24 | 0 | **2534** |

**Tiêu chí đạt là TỔNG `2534` cộng `0 failed`**, không phải `passed`. Chênh 18 là test
bị chặn bởi nền tảng (`POSIX permission bits`, `/dev/shm`, `unix socket`); còn 6 lượt bỏ
qua của Linux thì bỏ qua ở **cả hai** bên vì thiếu S3 và MQTT broker.

📌 Một nhãn mang hai giá trị tuỳ hệ điều hành là đúng
[luật 03](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md) ở tầng con số nghiệm thu -
cùng khuôn với con số `2518` mà chính tài liệu này đã bắt được một lần.

---

## 1. Trình tự - chủ dự án chốt, làm đúng thứ tự này

Điểm quan trọng nhất của trình tự này: **commit bản CŨ trước khi chép đè**. Nhờ
vậy `git diff` sau đó hiện **đúng** phần từ Linux, không lẫn với bất cứ thứ gì
đang dở trong thư mục làm việc.

```text
  1. commit bản CŨ  ->  2. chép đè  ->  3. soát diff  ->  4. chạy test
                                                              |
                     6. chủ dự án commit + tag + PyPI  <-  5. dựng gói
```

### Bước 1 - Commit bản cũ (chủ dự án làm)

```powershell
cd "D:\code\xime\xime framework"
git status                # xem còn gì đang dở
git add -A
git commit -m "Moc truoc khi nhan ban va tu Linux"
```

Nếu `git status` đã sạch thì bỏ qua bước này - đã có sẵn một mốc rồi.

⭐ Ghi lại mã commit này. Nó là thứ để `git diff <ma-commit> HEAD` về sau.

### Bước 2 - Chép đè

```powershell
# Xem trước, KHÔNG ghi gì
robocopy "D:\code\xime\_tu-linux\xime framework" "D:\code\xime\xime framework" /E /L /NJH /NJS

# Chép thật
robocopy "D:\code\xime\_tu-linux\xime framework" "D:\code\xime\xime framework" /E
```

⛔⛔ **KHÔNG dùng `/MIR` và KHÔNG dùng `/PURGE`.** Hai cờ đó xoá ở đích mọi thứ
không có ở nguồn, mà bản chép **không chứa `.git`** (nó bị loại có chủ đích). Dùng
chúng là **xoá sạch lịch sử git**.

`/PURGE` cũng không cần: đợt này **không xoá file nào**, chỉ thêm và sửa.

### Bước 3 - Soát

```powershell
git status
git diff --stat
```

Kỳ vọng, đo từ chính mốc `dd0192c` mà máy Windows đang giữ:

| | |
|---|---|
| File **mới** | **19** (14 từ chín commit vá, 5 từ đợt tài liệu cuối) |
| File **sửa** | **61** |
| File **xoá** | **0** |

⭐ Dòng cuối là dòng đáng kiểm nhất: nó xác nhận `/PURGE` không cần thiết, và
rằng bản chép không làm mất gì.

### Bước 4 - Chạy test. Đây là phép kiểm quan trọng nhất của cả phiên

```powershell
python -m pytest -q
```

**Kỳ vọng: Linux `2528 passed / 6 skipped`, Windows `2510 passed / 24 skipped`.
Ở cả hai: `0 failed` và tổng `2534`.**

### Bước 5 - Dựng gói phát hành

```powershell
cd "D:\code\xime framework\upload"
# đồng bộ từ repo phát triển (chỉ thứ cần đóng gói)
python -m build
python -m twine check dist/*
```

⚠ Repo phát hành đang ở `a3fcad8 v0.7.1` - **lệch hai bản**. Đây là **nợ thật**,
khác với "lệch bình thường trong lúc làm dở", và nó thuộc thẩm quyền chủ dự án.

### Bước 6 - Phát hành (CHỦ DỰ ÁN, không phải phiên)

```powershell
cd "D:\code\xime\xime framework"
pip install -e .          # de xime.__version__ theo kip 0.8.0
git add -A
git commit -F <file-thong-diep>
git tag v0.8.0
python pypi_token.py --upload "D:/code/xime framework/upload/dist"
```

Nợ cũ đi kèm, chủ dự án quyết: **tag `v0.7.2` còn thiếu** · **repo `upload` còn ở
`v0.7.1`** · **một stash từ 2026-06-03** (145 file) nằm trong repo.

---

## 2. Vì sao `xime.__version__` vẫn nói `0.7.2` sau khi chép

Nó đọc `importlib.metadata`, tức trả lời câu *"lần cuối ai chạy `pip install -e`"*,
**không phải** *"mã đang chạy là bản nào"*. Cài editable thì mã nạp thẳng từ repo
(luôn mới) còn metadata đóng băng.

Hỏi code, đừng hỏi số:

```python
from xime.core.refdata import RefData                    # co -> ma la 0.8
from xime.adapters.grpc._adapter import GrpcAdapter
GrpcAdapter.resolve_tls                                  # co -> da nhan ban va dot 6
```

---

## 3. Nếu bộ test không ra đúng tổng 2534

Đây là chỗ đáng dừng lại đọc, vì phần lớn khả năng **không phải bản chép hỏng**.

| Triệu chứng | Nhiều khả năng là |
|---|---|
| **Vùng đa tiến trình đỏ** (`tests_temp/processes`, `link`, `refdata`) | ⭐ **Báo ngay, đừng tự sửa.** Bản vá C4 (`xime/core/_mp.py`) ép ngữ cảnh `spawn`. Trên Windows `spawn` vốn đã là mặc định nên đó **phải là thay đổi rỗng** - đây là **suy luận từ tài liệu CPython, không phải phép đo**, vì phiên Linux không chạy được Windows. Nếu nó đỏ thì suy luận đó sai |
| **Đỏ vài test quyền file** (`lmdb`, `socket`) | Windows không có mode POSIX. Kiểm xem chúng có `skipif` không - kỳ vọng là **skip**, không phải **fail** |
| **Số chênh đúng 8** | Thiếu file `tests_temp/grpc/test_ke_thua_tls.py` - bản chép sót |
| **Số chênh 10** | Bản chép là bản CŨ (2518 là con số sai của tài liệu cũ; 2520 là HEAD trước đợt 6) |
| **Lỗi `import` một tên không tồn tại** | Bản chép lẫn file cũ và mới. Chép lại từ đầu |

⚠ Trước khi nghi bản chép, hãy chạy `python -m pytest tests_temp/grpc/test_ke_thua_tls.py -q`
- 8 test, chạy trong 0,03 giây, và nó chỉ xanh khi bản vá đợt 6 đã về đủ.

---

## 4. Hai lớp lỗi mà máy Windows KHÔNG THỂ nhìn thấy

Đây là bài học đắt nhất của cả đợt, và nó áp cho **mọi bản sau**, không riêng 0.8.

| | |
|---|---|
| **C4** | `ProcessLink` tạo semaphore bằng ngữ cảnh `multiprocessing` **mặc định**, `Supervisor` sinh con bằng **`spawn`**. Windows **chỉ có** `spawn` nên hai vế trùng nhau **một cách tình cờ**; Linux mặc định `fork` nên chúng lệch. Đo được: **26 test đỏ trên Linux, 0 đỏ trên Windows, cùng một mã nguồn** |
| **C5** | `SocketAdapter.assign_slot()` đọc một thuộc tính không tồn tại. Test socket **tự bỏ qua trên Windows**; `mypy` là thứ duy nhất tìm ra, và `mypy` chỉ được thêm vào extra `dev` trong chính đợt này |

> ⭐⭐ **Không phải test yếu. Điều kiện gây lỗi không tồn tại trên máy phát triển.**
> Một lượt chạy bộ test **trên Linux** nên là điều kiện phát hành từ nay.

---

## 5. Đợt 6 có gì, tóm tắt đủ để soát diff

Năm đợt đầu là framework **tự soi**. Đợt 6 do `Base Platform/data` báo sau khi họ
di trú thật sang khối `process:`, và **cả hai lỗ đều do chính 0.8 sinh ra**.

### C6 - gRPC tụt xuống PLAINTEXT khi di trú sang `process:`

Đường khoá phẳng chép `grpc.tls` vào ô cấu hình; đường `process:` thì **không**,
và adapter gRPC **không có đường lui**. Nên đổi cách khai địa chỉ - không đụng một
chữ vào khối `grpc:` - là **mất mTLS**.

Đo được hai chiều, cùng một `application.yml`, cùng cert:

```text
TRUOC:  grpc default: ... 9795 (PLAINTEXT)  + WARNING
SAU:    grpc default: ... 9795 (mTLS)
```

Sửa: `GrpcAdapter.resolve_tls()`, cùng khuôn `WebAdapter.resolve_tls()` sẵn có.

⚠ **App dùng khoá phẳng không đổi hành vi một bit nào.** Có một test đối chứng
dương khoá đúng điều đó - nó đỏ nghĩa là bản vá vừa động vào app đang chạy tốt.

### C7 - Adapter không bao giờ nói nó đã lên, chỉ nói ở đâu nó KHÔNG chạy

gRPC có đúng 2 lệnh log, **cả hai là `warning`**; socket có **0**. Nên một cụm
gRPC **khoẻ** sinh log **giống hệt** một cụm gRPC **hỏng**.

Sửa: cả ba adapter ghi một dòng `INFO` lúc bind xong, **chế độ bảo mật nằm cùng
dòng với địa chỉ**:

```text
INFO | web default: process main serving on 0.0.0.0:8086 (HTTPS+mTLS)
INFO | grpc default: process main serving on 0.0.0.0:9095 (mTLS)
INFO | socket default: process main serving on /run/x.sock (0600, any uid)
```

⚠ **Đây là thay đổi người dùng nhìn thấy.** Ai đang lọc log theo chuỗi cũ sẽ thấy
dòng web dài thêm một cụm `(HTTP)`. Cố ý, và đã ghi vào `CHANGELOG.md`.

Chi tiết đầy đủ, phép đo, test canh:
[`kiem-toan/0.8-kiem-toan-toan-dien.md`](../kiem-toan/0.8-kiem-toan-toan-dien.md)
mục **ĐỢT 6** · báo cáo gốc:
[`bao-cao-van-de-tu-repo-ngoai/`](../bao-cao-van-de-tu-repo-ngoai/README.md).

---

## 6. Chín commit của đợt Linux - lịch sử KHÔNG đi theo bản chép

`.git` cố ý không nằm trong bản chép, nên **thông điệp commit của đợt Linux sẽ
biến mất**. Chúng đã được xuất nguyên văn ra
[`kiem-toan/0.8-nhat-ky-va-tren-linux.md`](../kiem-toan/0.8-nhat-ky-va-tren-linux.md)
(415 dòng) - đó là nơi giữ **lý do** của từng bản vá.

Mốc gốc bên Linux là `dd0192c` (*"0.8.0 như nhận từ Windows, chưa vá gì"*), rồi
chín commit vá. Bên Windows tất cả sẽ gộp thành **một** commit phát hành, và đó là
điều bình thường - lịch sử chi tiết nằm ở file nhật ký.

---

## 7. Việc KHÔNG thuộc phiên này

| Việc | Vì sao |
|---|---|
| `Base Platform\data` | Chủ dự án đang làm thêm bên Linux. Nó **không đổi một byte nào** trong đợt vá framework. Đừng chép |
| Vá A1 fail-open JWT cho 19 app | Lỗ nằm trong `config/jwt.py` **của từng app**, framework không với tới. Vá `saas-foundation/template` **trước** - 18 app kia là nợ đứng yên, template là nợ đang sinh thêm |
| Mười một mục `0.8-cho-do-tren-linux.md` chưa chạy như một thủ tục riêng | Chúng đã được **vá**, nhưng L-02 tới L-04 và L-06 tới L-12 chưa chạy như một lượt đo độc lập. **"Đã vá" không đọc thành "đã đo"** |
| `0.8.1` (fieldbus chia tải, MQTT chia tải, `drain()` lúc tắt) | Bản sau |

---

## 8. Dọn dẹp sau cùng

Chỉ làm **sau khi** bộ test ra đúng tổng 2534 với 0 failed, và chủ dự án đã commit:

```powershell
Remove-Item -Recurse -Force "D:\code\xime\_tu-linux"
```

⚠ Đừng xoá trước. Chừng nào chưa có commit thì đó là **bản sao duy nhất** của đợt
vá - bên Linux có thể đã bị dọn.
