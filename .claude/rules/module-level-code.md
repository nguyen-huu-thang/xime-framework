# Code ở mức module phải nhẹ - luật nội bộ Xime Framework

> Lập **2026-08-19** khi chốt mô hình đa tiến trình của 0.8. Chủ dự án chốt đưa vào `rules/`.
>
> Đây là quy tắc **nội bộ repo này**, không phải luật cắt ngang workspace. Nhưng nó áp cho
> **code ứng dụng viết bằng Xime**, nên phải nói rõ trong tài liệu người dùng nữa.

## 1. Luật

> **Mọi thứ ngoài `if __name__ == "__main__":` chạy `N+1` lần khi app có `N` tiến trình.
> Code ở mức module chỉ được KHAI BÁO, không được LÀM.**

`N+1` chứ không phải `N`: tiến trình cha cũng chạy lại chính `main.py` (mô hình chốt ở
[`../docs/thiet-ke/10-da-tien-trinh.md`](../docs/thiet-ke/10-da-tien-trinh.md)
mục 5.5), rồi mới rẽ nhánh ở `share_load()`.

## 2. Vì sao nó thành luật, không phải lời khuyên

**a. Nó không có triệu chứng.** `client = SomeClient(...)` ở mức module thành `N+1` kết
nối, và **không gì báo**. Không lỗi, không log, không test đỏ. Chỉ là bốn kết nối tới
database thay vì một, và ai đó phát hiện sau vài tháng khi pool cạn.

**b. Hôm nay nó đúng, ngày mai nó sai - mà code không đổi.** App chạy một tiến trình thì
mọi thứ ở mức module chạy đúng một lần. Thêm một dòng `count: 3` vào `application.yml` là
cùng đoạn code đó chạy bốn lần. **Thứ đổi nằm ở file cấu hình, không nằm ở file có lỗi.**

**c. Cha gánh nó mà không dùng.** Cha **không dựng DI, không chạy code nghiệp vụ**, nhưng
nó vẫn chạy hết code mức module. Đo 2026-08-19: cây import của một app điển hình
(`Application` + web + grpc + sqlalchemy) là **83 MB RSS, 721 module**. Thêm một kết nối
mở ở mức module là cha giữ một kết nối nó không bao giờ dùng.

## 3. Được làm gì, không được làm gì

| Ở mức module | |
|---|---|
| `import config` | ✅ Được - nó chỉ ghi vào registry |
| `app = Application()` | ✅ Được - object rỗng, chưa mở gì |
| `app.add_config(config)` | ✅ Được |
| `app.use(WebAdapter())` | ✅ Được - dựng object adapter, **chưa** `start()`, chưa chiếm cổng |
| Khai class, hằng số, kiểu dữ liệu | ✅ Được |
| **Mở kết nối** (DB, Redis, MQTT, gRPC channel, HTTP session) | ⛔ Không |
| **Đọc/ghi file**, mở `shared_memory`, mở LMDB | ⛔ Không |
| **Gọi mạng** (lấy cert, lấy khoá, gọi API) | ⛔ Không |
| **Sinh giá trị không tất định** (`uuid4()`, `time.time()`, `random`) | ⛔ Không - xem 3.1 |
| Tính toán nặng, dựng bảng lớn trong bộ nhớ | ⛔ Không |

### 3.1. ⚠ Giá trị không tất định hỏng theo kiểu khác, và tệ hơn

Kết nối mở ở mức module thì **thừa** - tốn tài nguyên, nhưng mọi tiến trình đều đúng.

Một `uuid4()` ở mức module thì **mỗi tiến trình có một giá trị KHÁC NHAU**, trong khi code
đọc nó tin rằng cả cụm dùng chung một giá trị. Đó không phải lãng phí, đó là **sai**.

```python
INSTANCE_ID = uuid4()          # ⛔ bốn tiến trình, bốn id, không ai biết
STARTED_AT  = time.time()      # ⛔ bốn mốc khác nhau
```

⭐ Đây là cùng khuôn với `hash()` ở [kho nhóm 2](../docs/thiet-ke/13-kho-store-lmdb.md):
Python ngẫu nhiên hoá `hash()` cho mỗi tiến trình, nên chia file theo `hash(key)` hỏng
**hoàn toàn im lặng**. Cả hai đều là *giá trị trông như hằng số nhưng không phải*.

## 4. Hai phép dò

Luật này không tự giữ được - phải có thứ kêu.

> ✅ **CẢ HAI ĐÃ HIỆN THỰC ngày 2026-08-20** (giai đoạn 7 của 0.8):
> `xime/_startup.py` và `xime/cli/_module_level.py`, **83 test** ở
> `tests_temp/module_level/`. Tài liệu người dùng: `docs/{vn,en}/multi-process.md`.
>
> ⚠ **Ba chỗ bản hiện thực lệch khỏi mục này, đọc trước khi sửa:**
>
> | | Mục này viết | Đã làm |
> |---|---|---|
> | **Ngưỡng** | *"đề nghị 1 giây"* | **3 giây** - xem 4.1b |
> | **Thân class** | *"không phải trong hàm hay class body"* | **CÓ quét** thân class - xem 4.2b |
> | **`secrets.token_hex()`** | khai là chỗ mù | **đã bắt được** (`secrets.*` nằm trong danh sách) |

### 4.1. `share_load()` đo thời gian từ lúc import

`share_load()` là điểm đầu tiên framework giành lại quyền điều khiển sau khi code mức
module chạy xong. Nó ghi mốc lúc `xime` được import lần đầu, rồi so:

```text
[CẢNH BÁO] Code ở mức module chạy mất 2,4 giây trước khi tới share_load().
           Thời gian này nhân với số tiến trình. Xem rules/module-level-code.md
```

Bắt được cả ba nhóm nặng nhất (kết nối, đọc file, gọi mạng) mà **không cần biết chúng là
gì** - chỉ cần biết chúng chậm.

⚠ Giới hạn phải khai: một kết nối tới `localhost` có thể mất **vài mili giây**, nằm dưới
mọi ngưỡng hợp lý. Phép dò này bắt cái đắt, không bắt cái sai.

### 4.1b. ⚠ Ngưỡng 1 giây ĐO RA LÀ SAI - đã nâng lên 3 giây

Đo ngày 2026-08-20, cùng máy dev, cache đã ấm:

| Đo | Kết quả |
|---|---|
| Riêng import của framework (`xime` -> `+web` -> `+grpc` -> `+sqlalchemy`) | **1,08s** tổng, trong đó **0,75s** nằm SAU mốc |
| `linh-kien-dien-tu` (`xime` + web + `app.config`) | **0,996s** |
| `shop-hoa-qua-tang`, ba lần chạy | **1,057s · 1,033s · 1,059s** |

> **Cả hai ứng dụng thật và lành mạnh đều vượt ngưỡng 1 giây.** Một phép dò kêu
> oan là một phép dò sẽ bị tắt, nên ngưỡng lấy ~3x số đo đó: `3.0`.

⭐ Điều đáng nhớ hơn con số: **cửa sổ này bị chi phối bởi IMPORT, không phải bởi
"làm việc"** - khoảng một nửa là framework, nửa còn lại là cây import của chính
app. Nghĩa là phép dò 1 **không bao giờ** là phép dò chính; nó là lưới bắt thứ
thật sự bất thường.

⛔ **Đường đã cân nhắc và loại: trừ đi thời gian import.** Bọc `__import__` để đo
rồi trừ ra thì **trừ đúng thứ cần bắt** - một kết nối mở trong thân
`config/dependency.py` được tính là "thời gian import" theo đúng nghĩa đen của
phép đo đó. Lời giải làm hỏng chính bài toán.

⛔ **Không có công tắc tắt, và không có khoá cấu hình.** Nó là cảnh báo, không
chặn ai; thêm một knob cho một dòng WARNING là thêm bề mặt API ở bản alpha cuối.

### 4.2. Quét tĩnh hàm không tất định ở mức module

Bù đúng chỗ 4.1 mù. Quét AST của `main.py` và các module nó import ở mức module, tìm lời
gọi `uuid4`, `time.time`, `random.*`, `datetime.now` **ở thân module** (không phải trong
hàm hay class body).

⚠ **Đây là phép dò theo danh sách tên, nên con số 0 của nó không chứng minh được gì** -
đúng bài học đã ghi ở CLAUDE.md workspace về phép quét secret. Nó bắt được bốn cái tên
phổ biến, không bắt được `secrets.token_hex()` hay một hàm tự viết gọi vào chúng.

⭐ Vì vậy **hai phép dò không thay thế nhau**: một cái đo *hậu quả* (chậm) mà không biết
nguyên nhân, một cái tìm *nguyên nhân* theo tên mà không thấy hậu quả. Bỏ cái nào cũng
thủng theo hướng riêng.

### 4.2b. Bản hiện thực: `xime check module-level`

```bash
xime check module-level                 # tự tìm app/main.py, main.py, src/main.py
xime check module-level --main app/main.py --root .
```

**BA mã thoát, không phải hai:** `0` sạch · `1` có vi phạm · `2` **chưa kết luận
được** (không tìm thấy điểm vào, hoặc có file không parse được). Gộp mã 2 vào 0
là để một lần chạy trong CI báo xanh trên một phép kiểm chưa hề chạy - đúng lỗi
`ShardValueGuard` của `identity` đã vấp.

⚠ **Quét CẢ THÂN CLASS, rộng hơn câu chữ ở 4.2.** Thân class chạy lúc import y
như thân module, nên `class C: ID = uuid4()` hỏng đúng kiểu luật này nói tới -
và `class M(BaseModel): ts: datetime = datetime.now()` là ca thật. Cũng quét
**decorator** và **giá trị mặc định của tham số**, hai chỗ khác cũng chạy lúc
import. **Thân hàm và thân method thì không.**

Danh sách tên rộng hơn 4.2 một chút, và mỗi chỗ mở rộng đều có lý do:

| Thêm | Vì sao |
|---|---|
| `secrets.*` | 4.2 khai đây là chỗ mù. Đóng nó tốn đúng một dòng |
| `os.getpid` | Ca kinh điển của *"trông như hằng số mà không phải"* |
| `os.urandom` · `uuid.uuid1` | Cùng họ |
| `time.monotonic` · `perf_counter` · `*_ns` | Cùng họ với `time.time` |

Và hai chỗ **cố ý KHÔNG kêu**, cả hai đều cùng module với thứ bị theo dõi:

| Không kêu | Vì sao |
|---|---|
| `uuid.uuid3` · `uuid.uuid5` | **Tất định** theo `(namespace, name)` |
| `random.seed` | Ngược chiều: nó **làm cho** mọi thứ sau đó tất định |

⚠ Phạm vi: `main.py` và mọi module **nằm trong `--root`**, đệ quy, gồm cả
`__init__.py` của mọi package cha (import `app.config.x` **chạy `app/__init__.py`**
trước) **và** import nằm trong khối lồng nhau ở mức module (`try: import x except
ImportError:` là khuôn phổ biến cho phụ thuộc tuỳ chọn, và `x` vẫn chạy lúc
import). Thư viện bên ngoài - kể cả chính `xime` - không bị quét: chúng gọi
`time.time()` ở khắp nơi, và đó không phải thứ người dùng sửa được.

⭐ Hai chỗ trên là **lỗ hổng thật do đối chứng tìm ra**, không phải tính năng
nghĩ ra từ đầu. Chỗ thứ hai đáng nhớ: phép kiểm `if __name__` trong bước tìm
import từng là **mã chết** - nó chỉ nhìn tầng ngoài cùng, mà `try` là `ast.Try`
chứ không phải `ast.Import`, nên nó chưa từng chạy. Nhìn code thì thấy một dòng
phòng thủ tử tế; chạy thì cả một nhánh cây import biến mất khỏi phạm vi quét, và
kết quả vẫn in `CLEAN`.

⛔ **Không có cú pháp tắt theo dòng** (`# xime: allow-...`). Nó là một lệnh chạy
tay chứ không phải một cổng chặn, nên chưa cần; và một cú pháp tắt là một API
công khai mới ở bản alpha cuối. Ngày nó kêu oan thật thì thêm sau.

## 5. Ranh giới: luật này KHÔNG cấm app có trạng thái toàn cục

Nó cấm **làm việc** ở mức module, không cấm **khai báo**. Một registry rỗng, một dict hằng
số, một class - tất cả đều ổn, vì mỗi tiến trình dựng lại chúng giống hệt nhau.

> Câu để tự kiểm: **nếu dòng này chạy bốn lần thay vì một, có gì hỏng hoặc lãng phí
> không?** Không thì để yên.

## 6. Liên quan

- [`background-tasks.md`](background-tasks.md) - cùng họ: thứ trông vô hại ở một tiến
  trình, hỏng khi có tiến trình thứ hai hoặc khi thời gian vào cuộc.
- [`../docs/thiet-ke/10-da-tien-trinh.md`](../docs/thiet-ke/10-da-tien-trinh.md)
  mục 5.5 (mô hình chạy, vì sao là `N+1`) và 5.5b (số đo 83 MB).
- [Luật 01 của workspace](../../../.claude/rules/01-song-song-hoa-va-shard.md) nghĩa 1 -
  *mọi trạng thái phải ra khỏi bộ nhớ tiến trình*. Luật này là một mảnh cụ thể của nó,
  ở đúng chỗ trạng thái hay lọt vào mà không ai để ý.
