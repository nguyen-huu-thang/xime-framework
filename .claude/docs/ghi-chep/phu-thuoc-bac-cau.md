# Ba phụ thuộc bắc cầu chưa khai báo (đo 2026-08-17)

> Trạng thái: ✅ **ĐÃ SỬA XONG 2026-08-17**, nằm trong 0.7.1. Test **1516 passed, 11 skipped**.
> Sàn đã đo thật sau khi cài `aiomqtt 2.5.1` + `aioboto3 15.5.0` - xem mục 3 (bản đầu của mục đó
> đã bị **sửa lại**, vì lập luận ban đầu quá cẩn thận một cách không cần thiết).
>
> Xuất phát từ câu hỏi của chủ dự án: *"framework có phụ thuộc gì từ các dự án Xime khác không"*.
> Câu trả lời cho câu đó là **KHÔNG** (xem mục 1). Ba ca dưới đây là thứ tìm ra kèm theo, thuộc
> loại khác hẳn: phụ thuộc vào **thư viện bên ngoài mà không khai báo**.

## 1. Bối cảnh: phép đo gốc

Dựng cây AST toàn bộ `xime/`, liệt kê mọi import ngoài stdlib, tách theo tầng:

| Tầng | Phụ thuộc ngoài |
|---|---|
| **`core/`** | **đúng 2**: `pydantic` (`core/config/runtime.py`) · `yaml` (`core/config/loader.py`) |
| `adapters/` | aiomqtt, asyncua, fastapi, google, grpc, grpc_tools, msgpack, **paho**, pydantic, pymodbus, **starlette**, uvicorn |
| `starters/` | aioboto3, aiosmtplib, apscheduler, **botocore**, jwt, redis, sqlalchemy, **starlette** |

Hai kết luận:

- **Không một import nào trỏ tới dự án Xime khác.** 21 gói đều là thư viện PyPI công khai.
- **Core sạch về giao thức.** Hai phụ thuộc của core đều nằm trong `dependencies` **bắt buộc**
  và đều chỉ ở `core/config/`. Mọi phần còn lại (`container`, `lifecycle`, `event`, `context`,
  `security`, `transaction`, `exception`, `metadata`, `contract`, `bootstrap`) là **stdlib thuần**.
  Không `fastapi`, không `grpc`, không `starlette` trong core.

Lệnh đo lại (chạy từ gốc repo):

```bash
python -c "
import ast, sys, pathlib, collections
std = set(sys.stdlib_module_names)
layers = collections.defaultdict(lambda: collections.defaultdict(set))
for f in pathlib.Path('xime').rglob('*.py'):
    parts = f.parts
    layer = parts[1] if len(parts) > 2 and not parts[1].endswith('.py') else 'xime (goc)'
    try: tree = ast.parse(f.read_text(encoding='utf-8'))
    except Exception: continue
    for n in ast.walk(tree):
        names = [a.name for a in n.names] if isinstance(n, ast.Import) else (
            [n.module] if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module else [])
        for nm in names:
            top = nm.split('.')[0]
            if top not in std and top != 'xime': layers[layer][top].add(str(f))
for L in sorted(layers): print(L, sorted(layers[L]))
"
```

⚠ Dùng AST chứ **không** dùng grep: grep bỏ sót import viết nhiều dòng và import lười trong
thân hàm, mà cả ba ca dưới đây có hai ca là import lười.

## 2. Ba ca, cùng một hình dạng

Framework **import thẳng một thư viện mà `pyproject.toml` không khai**. Chạy được hôm nay chỉ vì
một thư viện đã khai kéo nó về theo.

| Import thẳng | Về được nhờ | Khai trong pyproject | Tránh được không |
|---|---|---|---|
| `paho` (2 chỗ, lười) | `aiomqtt` | Không | **Không** |
| `starlette` (3 file) | `fastapi` | Không | **Có** |
| `botocore` (1 chỗ, lười) | `aioboto3` | Không | Nhiều khả năng không |

**Vì sao đáng sửa:** một phụ thuộc bắc cầu là lời hứa thư viện A đưa cho **chính nó**, không phải
lời hứa A đưa cho ta. `aiomqtt` có toàn quyền đổi backend hoặc siết khoảng phiên bản paho theo nhu
cầu riêng, và không ai coi đó là phá vỡ tương thích với ta - vì ta chưa bao giờ nói mình cần paho.

**Vì sao KHÔNG gấp:** cả ba đang chạy đúng. Đây là chuyển từ *"đúng nhờ may mắn"* sang *"đúng nhờ
được nói ra"*. Lợi ích chỉ hiện ra vào ngày một thư viện thượng nguồn xáo lại phụ thuộc.

### 2.1. `paho` - phải KHAI, không tránh được

Chuỗi thật: `xime[mqtt]` -> `aiomqtt` -> `paho-mqtt`. Nhưng `pyproject.toml` chỉ khai mắt xích đầu.

Hai chỗ import, đều lười trong thân hàm:

- `adapters/mqtt/_adapter.py:260-261` - dựng `Properties(PacketTypes.SUBSCRIBE)` cho Subscription Identifier
- `adapters/mqtt/_dispatcher.py:171-172` - dựng `Properties(PacketTypes.PUBLISH)` cho CorrelationData của reply RPC

**Không tránh được:** `aiomqtt` 2.x **không có lớp `Properties` của riêng nó**, mà MQTT v5 thì bắt
buộc phải có Properties cho hai thứ trên.

⚠ **Điểm sâu hơn một tầng, đừng bỏ qua khi sửa:** framework đang **với tay QUA `aiomqtt` để chạm
vào kiểu dữ liệu của paho**, rồi đưa chính object đó ngược lại cho `aiomqtt`. Nghĩa là hợp đồng
thật giữa hai bên gồm một câu chưa ai viết ra: *"anh phải nhận đúng lớp `Properties` của paho"*.
Ngày `aiomqtt` bọc kiểu đó lại bằng lớp của riêng nó, code này gãy **dù `paho` vẫn còn trên máy**.
Khai thêm dependency **không** chữa được vế này; nó chỉ chữa vế "paho biến mất".

⚠ **Gãy MUỘN:** import nằm trong thân hàm nên nếu paho vắng mặt thì app **khởi động bình thường**,
kết nối MQTT **thành công**, rồi nổ `ImportError` đúng lần `subscribe` đầu tiên. Ngược hẳn triết lý
fail-fast của framework. Bản thân việc import lười **không sai** và đừng đi gỡ - nó là thứ giữ cho
module vẫn import được khi không cài extra `[mqtt]`. Thứ sai là **cái được import lười lại không có
tên trong danh sách phụ thuộc**.

**Cách sửa:**

```toml
mqtt = [ "aiomqtt>=2.0", "paho-mqtt>=?" ]
```

### 2.2. `botocore` - phải KHAI, không tránh được

`starters/s3/_client.py:83` - `from botocore.config import Config as BotoConfig`, lười trong thân
hàm. `aioboto3` không có bản tương đương.

```toml
s3 = [ "aioboto3>=12", "botocore>=?" ]
```

### 2.3. `starlette` - TRÁNH ĐƯỢC, đổi nguồn import là xong

Mọi object đang dùng đều được FastAPI **xuất lại nguyên vẹn** (chúng *chính là* object của
starlette, fastapi chỉ re-export). Nên đổi nguồn import thì phụ thuộc trực tiếp biến mất,
**không phải khai thêm gì**, và **không có thay đổi hành vi nào** vì cùng một object.

| File | Hiện tại | Đổi thành |
|---|---|---|
| `starters/jwt/_middleware.py:3-4` | `from starlette.requests import Request`<br>`from starlette.responses import JSONResponse` | `from fastapi import Request`<br>`from fastapi.responses import JSONResponse` |
| `adapters/web/ws/_handler.py:6` | `from starlette.websockets import WebSocketDisconnect` | `from fastapi import WebSocketDisconnect` |
| `adapters/web/_cors.py:70` | `from starlette.middleware.cors import CORSMiddleware` | `from fastapi.middleware.cors import CORSMiddleware` (**giữ nguyên khối try/except đã có**) |
| `adapters/web/_config.py:30` | **docstring ví dụ** dạy người dùng import từ starlette | sửa ví dụ sang fastapi |

⚠ Dòng cuối không phải import thật mà là **docstring**. Vẫn phải sửa, vì lý do khác: nó đang
**dạy người dùng framework** import từ một gói mà framework không khai.

**Hướng thay thế (cũng hợp lý, đã cân nhắc và không chọn):** khai thẳng `starlette` vào extra
`web`. Thành thật hơn về việc code đang dùng gì. Không chọn vì `CLAUDE.md` của repo khai **FastAPI**
là thư viện nền và **không** khai starlette - thêm `starlette` vào metadata công khai là tuyên bố
một phụ thuộc mà framework về khái niệm không có. Đánh đổi của hướng đã chọn: dựa vào việc FastAPI
tiếp tục re-export, chuyện gần như chắc chắn vì đó là API công khai của họ.

## 3. Sàn phiên bản: đã đo, và lập luận ban đầu của mục này đã được sửa

⚠ **Bản đầu của mục này (viết sáng 2026-08-17) kết luận rằng ca 2.1 và 2.2 phải chờ F3 vì
"không đo được sàn". Kết luận đó SAI, và giữ vết ở đây vì cái sai đáng đọc.**

Lý lẽ ban đầu dựa vào luật của chính `pyproject.toml` dòng 52 (*"Mỗi mốc dưới đây đều đã CÀI THỬ
chứ không phỏng đoán"*), cộng với sự thật là cả `aiomqtt` lẫn `paho-mqtt` đều **chưa cài** trên
máy này. Cả hai tiền đề đều đúng. Kết luận vẫn sai, vì nó **bỏ qua một phân biệt**:

| | Ta đang làm gì | Rủi ro |
| --- | --- | --- |
| **F3** | **NÂNG** sàn lên bản mới hơn bản đang chạy | Thật. Phải cài thử, chạy hết test |
| **Ca 2.1 / 2.2** | **KHAI RA** một thứ đã có mặt sẵn | Bằng 0, **nếu** sàn không chặt hơn ràng buộc đã tồn tại |

> **Một sàn trùng khớp (hoặc lỏng hơn) ràng buộc mà một dependency ĐÃ KHAI vốn đã đòi thì không
> thể làm gãy môi trường nào đang chạy được.** Nó không thêm ràng buộc mới nào vào bài toán
> resolver.

### Số đo thật (2026-08-17, sau khi cài `aiomqtt 2.5.1` + `aioboto3 15.5.0`)

```text
aiomqtt 2.5.1     requires  paho-mqtt<3.0.0,>=2.1.0
aiobotocore 2.25.1 requires botocore<1.40.62,>=1.40.46
```

**`paho-mqtt>=2.1`** - trùng khớp đúng ràng buộc `aiomqtt` đã đòi. Khai xong không siết thêm gì.

**`botocore` khai TÊN TRẦN, không phiên bản** - và đây là chỗ số đo **đổi cả cách sửa**:
`aiobotocore` ghim botocore vào một dải **đúng 16 bản patch**, và dải đó dịch theo mỗi lần
aiobotocore ra bản mới. Mọi sàn số ta viết ở đây hoặc vô nghĩa hôm nay hoặc thành **xung đột
resolver** ngày mai, trong khi `botocore.config.Config` đã ổn định nhiều năm. Nên lời khai thành
thật nhất là *"chúng tôi import thứ này"*, còn phiên bản để aiobotocore quyết.

📌 Bài học chung: **luật "phải cài thử" là luật về việc ĐỔI một ràng buộc, không phải về việc
KHAI RA một ràng buộc đã tồn tại.** Áp nó vào ca thứ hai thì nó biến từ phanh an toàn thành phanh
tay kéo suốt.

## 4. Mục nhỏ cùng họ

`types_aiobotocore_s3` (`starters/s3/_client.py:8`) nằm dưới `TYPE_CHECKING` nên **không ảnh hưởng
lúc chạy**, nhưng nó cũng không có trong extra `dev` - chạy `mypy` trên chính `xime/` sẽ thiếu
stub. Một dòng, gộp luôn khi làm ca 2.2.

## 5. Xếp bản

Cả ba **không đổi API công khai**: đổi nguồn import là chuyện nội bộ, thêm dependency vào một extra
không phải đổi API. Nên **không vướng nguyên tắc "mọi thay đổi API gom vào 0.8"** và làm được ở
0.7.x.

| Ca | Trạng thái | Ghi chú |
|---|---|---|
| 2.3 starlette | ✅ **XONG** | 4 chỗ đổi sang `fastapi`. `starlette` đã biến khỏi danh sách phụ thuộc trực tiếp (kiểm bằng AST scan) |
| 2.1 paho | ✅ **XONG** | `paho-mqtt>=2.1` |
| 2.2 botocore (+ mục 4) | ✅ **XONG** | `botocore` tên trần + `types-aiobotocore-s3>=2.13` vào `dev` |

**Cả ba nằm trong 0.7.1.** Không mục nào đổi API công khai nên không vướng nguyên tắc chia bản.

⚠ **Tác dụng phụ của việc cài hai extra, đã ghi vào CHANGELOG:** mốc test đổi từ
**1516 passed / 7 skipped** sang **1516 passed / 11 skipped**. Số skip tăng **không phải vì có
test bị tắt** - trước đây vài module MQTT/S3 bị skip **cả gói** và đếm là *một* skip; cài rồi thì
chúng được thu thập thành từng test, chỉ phần cần broker/MinIO mới skip lẻ. Đổi lại **2 test giờ
chạy thật**.

## 6. Liên quan

- `../kiem-toan/0.7-bao-mat-ke-hoach-va.md` đợt 4 - F3 nâng sàn dependency, cùng điều kiện thi công
- `../CLAUDE.md` mục "Việc đang chờ làm ở repo này" - bảng 0.7.x
- ⚠ **Không liên quan tới trục "phụ thuộc khái niệm"** (`xime-app://`, độ dài 33 trong
  `adapters/grpc/interceptors/_context.py`). Đó là vấn đề khác hẳn và nặng hơn, đang chờ chủ dự án.
