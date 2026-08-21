# XIME Framework - Hướng dẫn phiên làm việc

> **File này trả lời đúng một câu: *hôm nay đứng ở đâu, làm gì tiếp*.**
> Nó KHÔNG trả lời *"chuyện gì đã xảy ra"* - câu đó thuộc về `CHANGELOG.md` và
> [`docs/`](docs/README.md). Sắp xếp lại 2026-08-21, từ 1770 dòng xuống còn chừng này.

## Trạng thái

**0.8.0 ĐÃ PHÁT HÀNH ngày 2026-08-21.** Kiểm toán sáu đợt, vá 28 mục, lên PyPI.

| | |
|---|---|
| PyPI | `0.8.0` (bản thứ **14**) |
| Repo phát triển | `a982cae v0.8.0` · tag `v0.8.0`, và **`v0.7.2` đã trả nợ** |
| Repo phát hành | `8a1e376 v0.8.0` · tag `v0.8.0` · hết lệch hai bản |
| Đối chứng | **SHA256 gói trên PyPI khớp từng bit** với gói dựng ở máy này |

Vì `xime` cài **editable** nên mã ở đây có hiệu lực ngay với **31 app** trên máy này.
⚠ Nghĩa là **sửa một dòng ở đây là 31 app nhận ngay**, dù PyPI vẫn đứng ở `0.8.0` - đừng
đọc *"đã phát hành"* thành *"thư mục này đứng yên"*.

✅ **Đợt vá trên Linux ĐÃ đưa về `D:\code\xime` ngày 2026-08-21**: 80 file (61 sửa,
19 mới, **0 xoá**), đối chứng **629/629 file khớp từng byte**. Sổ tay của phiên nhận:
[`docs/ban-giao-cho-phien-windows.md`](docs/ban-giao-cho-phien-windows.md).

### Kỳ vọng bộ test - HAI con số, theo hệ điều hành

| Nền tảng | `passed` | `skipped` | `failed` | **Tổng** |
|---|---|---|---|---|
| **Linux** | **2528** | 6 | 0 | **2534** |
| **Windows** | **2510** | 24 | 0 | **2534** |

⚠⚠ **Đừng dùng MỘT con số `passed` làm tiêu chí đạt.** Nó phụ thuộc hệ điều hành, nên
nhãn *"kỳ vọng 2528"* mang hai giá trị - đúng
[luật 03](../../.claude/rules/03-mot-gia-tri-mot-nghia.md) ở tầng con số nghiệm thu.
**Thứ bất biến giữa hai bên là TỔNG `2534`.**

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
Bật hai dịch vụ đó lên thì Linux ra `2534/0`, Windows ra `2516/18`.

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

## 1. Sau khi phát hành 0.8.0 - còn đúng một việc

| # | Việc |
|---|---|
| 1 | **Một stash từ 2026-06-03** (`stash@{0}`, WIP trên `ba64bd5`, 145 file) vẫn nằm trong repo. Không phải của đợt nào gần đây - dọn hay giữ là quyết định của chủ dự án |

Mọi việc khác của đợt phát hành **đã xong**: `pip install -e .`, commit, tag `v0.8.0`,
tag bù `v0.7.2`, đẩy PyPI, và repo phát hành đã bắt kịp.

⚠ **Đừng tin bảng trên, kiểm bằng lệnh** - lý do ở mục [Trạng thái](#trạng-thái).

```bash
python -c "import urllib.request,json; print(sorted(json.load(urllib.request.urlopen('https://pypi.org/pypi/xime/json'))['releases']))"
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
| Trình tự nhận bản vá và phát hành | [`docs/ban-giao-cho-phien-windows.md`](docs/ban-giao-cho-phien-windows.md) |
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

## 3. 0.8.1 - hiện thực

> ⭐⭐ **0.8 là bản ALPHA CUỐI CÙNG.** 0.9 đổi sang `4 - Beta` nơi API coi như đã chốt.
>
> ⛔ **Đính chính 2026-08-21:** mục này trước ghi *"`0.8.1` chỉ được hiện thực, không
> đổi API"* - câu đó **mâu thuẫn với `docs/lo-trinh-phien-ban.md` dòng 58**, nơi chính
> câu ấy đã bị gạch bỏ kèm lời chủ dự án nới ngày 2026-08-19: *"0.8 đang có nhiều phiên
> bản con nữa mà, vẫn nhiều cơ hội để đổi"*. Luật *"0.7.x không đổi API"* **không suy
> sang 0.8.x**: 0.7.x là dòng đã phát hành có 31 app chạy trên nó, 0.8.x là dòng đang
> xây. Leader phát hiện mâu thuẫn này ngày 2026-08-21; nay đã sửa.
>
> Dù vậy tên và chữ ký của fieldbus/MQTT **đã khai xong ở 0.8** như dự định, nên 0.8.1
> trên thực tế chỉ còn phần hiện thực.

| Việc | Ghi chú |
|---|---|
| **Fieldbus chia tải** | Tách **loại** (`bang-tai`, code biết) khỏi **thực thể** (`BT-01`, cấu hình biết); `@poll`/`@on_change` chạy một lần **mỗi thực thể**. Chữ ký đã khai ở 0.8 (phần 4b) |
| **MQTT chia tải** | Chia **theo topic**, không dùng shared subscription; `client_id` + `topics` vào `processes.<p>.mqtt.<id>` |
| ~~**Nợ luật 03 của `EventBus`**~~ | ✅ **ĐÃ TRẢ ở 0.8** (2026-08-21): `publish()` trả `PublishOutcome` với ba giá trị `SCHEDULED` / `NO_HANDLERS` / `DROPPED`. Chủ dự án chốt trả ở bản này vì 0.8 là chuyến cuối trước khi API đóng |
| **`drain()` lúc tắt máy** | Framework không bao giờ tự gọi, nên handler đang chạy bị cắt ngang. Tài liệu nay bảo người dùng tự gọi trong `PreDestroy`; sửa tử tế thì chạm vòng đời adapter |

⏭ **Hoãn có ý thức, đã ghi lý do:** *cha không có mồm* (mục 2.8c tài liệu đa tiến trình -
cha không dựng DI nên không có đường báo ra ngoài) · *supervisor trông tiến trình ngoài* ·
*tắt êm*.

## 4. Cần máy khác mới làm được

| Việc | Cần gì |
|---|---|
| **Hai phép đo LMDB** (mục 6.2 [`docs/thiet-ke/13-kho-store-lmdb.md`](docs/thiet-ke/13-kho-store-lmdb.md)) | **VPS Linux** - máy này là Windows. Không chặn gì: chúng để chỉnh tham số vận hành, không phải quyết định thiết kế |

## 5. Ngoài framework

| Việc | Ở đâu |
|---|---|
| Đợt 0 + A2 (CORS regex) + A4 của kiểm toán bảo mật | **Repo app.** Đợt 0 chờ chủ dự án quyết A6 (chỗ để secret) |
| Dựng trang **xime-framework.org** | `D:\code\xime framework\website`, Next.js xuất tĩnh, ưu tiên SEO. Mở từ 2026-08-01 |

---

# Ba thứ đừng đề xuất lại

Mỗi cái đã bị bác kèm lý do; danh sách đầy đủ nằm trong từng file thiết kế
(`docs/thiet-ke/10` mục 8 có **19 hướng**, `docs/thiet-ke/11` mục 11 có **19 hướng**).

| | Vì sao |
|---|---|
| **TLS mức 2 cho web adapter** | Không tránh được việc private key chạm đĩa, tức không giải quyết được vấn đề nó sinh ra để giải quyết. Cần thì làm **mức 1.5** - mục 4.0 [`docs/thiet-ke/07-tls-web-adapter.md`](docs/thiet-ke/07-tls-web-adapter.md) |
| **Hook SQLAlchemy chặn sửa entity ngoài transaction** | Phải trả phí runtime cho mọi lời đọc, trái nguyên tắc minimal magic. Bù bằng quy tắc tài liệu - [`rules/transaction.md`](rules/transaction.md) |
| **`LifecycleManager` gọi `pre_destroy()` khi `post_construct()` ném lỗi** | Dọn object khởi tạo dở sẽ **che lỗi gốc**. Chủ dự án chốt 2026-07-30: giữ nguyên |

# Hai bài học đắt nhất, để ở đây vì chúng sẽ lặp

**1. Viết ít nhất một test đi đúng con đường TÀI LIỆU hướng dẫn**, không phải con đường
tiện nhất cho test. Ba lỗi mức Cao của 0.7.0 và hai lỗi của 0.8 giai đoạn 1 đều nằm ở chỗ
nối, và **không test nào bắt được** vì test luôn đi đường tắt mà người dùng thật không có.

**2. *"Không test nào đỏ"* có BA nghĩa, không phải hai:** test thiếu · phép đo nhắm sai ·
**hoặc bản vá không làm việc mà lời giải thích của nó nói**. Nghĩa thứ ba dễ bỏ qua nhất,
vì code vẫn đúng. Cách duy nhất tách được là **đối chứng**: gỡ bản vá ra rồi đếm test đỏ,
và đếm **treo** thành một kết cục riêng chứ đừng gộp vào *đỏ*.
