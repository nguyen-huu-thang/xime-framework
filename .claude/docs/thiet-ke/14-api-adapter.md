# Đổi API adapter một lượt - 0.8

> Bàn 2026-08-19, nối tiếp mục 4 của
> [`10-da-tien-trinh.md`](10-da-tien-trinh.md).
>
> ✅ **ĐÃ THI CÔNG XONG 5/5 PHẦN, 2026-08-20.** Dòng cũ ghi *"chưa có một dòng code
> nào"* hết đúng. Kết quả ở `CHANGELOG.md` mục *Giai đoạn 4*.
>
> ⚠⚠ **Phần 2 lộ ra một chỗ thiết kế CHƯA NÓI TỚI, và chủ dự án đã chốt lời giải
> 2026-08-20** - xem mục **2.5b** ngay dưới 2.5.
>
> ✅ **4b: PHẦN KHAI CHỮ KÝ ĐÃ THI CÔNG 2026-08-20** - bỏ `device=`/`server=` khỏi
> decorator, tham số handler `device`/`server` khớp theo TÊN, `devices_of()` /
> `servers_of()`. Phần **dựng N kết nối** lùi 0.8.1 theo chốt của chủ dự án.
> ⭐ Một chỗ tài liệu chưa nói: **OPC UA dùng chữ `server`, không dùng `device`** -
> xem 4b.7.
>
> ⭐ **0.8 là bản Alpha CUỐI CÙNG** (0.9 đổi sang `4 - Beta`, nơi *"API coi như đã
> chốt"*). Nên mảng này nên làm đủ trong **dòng 0.8.x**.
>
> ⛔ **ĐÍNH CHÍNH 2026-08-19:** bản đầu của banner này viết *"`0.8.1` chỉ được HIỆN THỰC,
> không đổi API"* - **phiên tự suy từ nguyên tắc của 0.7.x, và suy sai**. Chủ dự án nới:
> *"0.8 đang có nhiều phiên bản con nữa mà, vẫn nhiều cơ hội để đổi"*.
>
> ⭐ Lý do nới hợp lý: **0.7.x là dòng đã phát hành, 31 app đang chạy trên nó; 0.8.x là
> dòng đang xây, chưa ai ngoài dự án dùng.** Hai hoàn cảnh khác nhau nên không dùng chung
> một luật - đó là chỗ phiên suy ẩu.
>
> ⚠ Vẫn nên chốt tên và hình dạng sớm, nhưng vì lý do khác: **đổi một cái tên sau khi ba
> adapter đã dùng nó thì phải sửa cả ba**.

## 0. Đọc gì trong hai phút

| | |
|---|---|
| **Mảng này gồm** | **5 phần**. Phần 1 đã chốt 2026-08-19; phần 2-5 chưa bàn |
| **Vì sao phải đổi một lượt** | Xem khối trên. Rải qua nhiều bản là thứ tệ nhất cho 31 app dùng chung một cây mã editable |
| **Chốt lớn nhất tới nay** | **Hai tên cho hai hạng** (`server_id` · `target_id`) cộng **một tên chung ở tầng framework** (`adapter_id`), chứ không phải một tên cho cả sáu |

| Phần | Trạng thái |
|---|---|
| **1. Định danh adapter** | ✅ **CHỐT 2026-08-19** |
| **2. Cấu hình đẩy vào, không để adapter tự kéo ra** | ✅ **CHỐT 2026-08-19** |
| **3. Hạng nhân bản là dữ liệu** | ✅ **CHỐT 2026-08-19** |
| **4. Vòng đời và tín hiệu "đã sẵn sàng"** (trùng **F10**) | ✅ **CHỐT 2026-08-19** |
| 5. Thi công: `SchedulerRunner` thành adapter hạng đơn nhất | ⬜ không cần quyết gì, phụ thuộc phần 3 |

---

## 1. Định danh adapter - ĐÃ CHỐT

### 1.1. Định danh này làm BA việc, không phải một

| # | Việc | Ai dùng |
|---|---|---|
| 1 | **Chống đăng ký trùng** | `application.py:82`, qua `getattr(adapter, "_server_id", None)` |
| 2 | **Tra khối cấu hình** của riêng instance đó | socket: `<socket.dir>/<server_id>.sock` |
| 3 | **Ánh xạ trong `processes:`** | tầng khoá thứ ba: `tiến trình → loại adapter → id` |

Việc 3 là việc **mới của 0.8**, và nó biến chuyện đặt tên từ *"dọn cho đẹp"* thành bắt
buộc.

### 1.2. Hiện trạng đo được (2026-08-19)

Sáu adapter, **bốn tên** ở bề mặt:

| Adapter | Tên đối số | Còn nhận gì |
|---|---|---|
| web | `server_id` | `host`, `port`, `ssl` |
| grpc | `server_id` | `host`, `port` |
| socket | `server_id` | `path` |
| mqtt | **`client_id`** | `path` |
| modbus | **`device`** | `controllers` |
| opcua | **`server`** | `controllers` |

⭐ **Khái niệm chung ĐÃ tồn tại và đã được framework dùng thật**: cả sáu đều gán
`self._server_id` ở cuối constructor, kể cả modbus/opcua vốn không có chữ đó ở bề mặt.
Nên đây **không phải việc phát minh khái niệm mới**, mà là việc nâng một hợp đồng ngầm
lên thành hợp đồng thật.

### 1.3. ⚠ Bốn phát hiện, mỗi cái đổi một phần kết luận

**a. Protocol `Adapter` chưa bao giờ được dùng lúc chạy.**

`application.py:15-16` import `Adapter` **chỉ dưới `if TYPE_CHECKING`**. Nên
`@runtime_checkable` viết trên nó **chưa từng có tác dụng**. Đo thật:

```text
use() chap nhan object khong co start/stop: 2 adapter
isinstance(Rong(), Adapter) = False
```

Một object rỗng đăng ký được **hai lần**, không ai kêu. Còn `isinstance` thì phân biệt
được ngay - **công cụ có sẵn, chỉ là không ai gọi**.

**b. `client_id` của MQTT đã mang HAI nghĩa ngay hôm nay.** `_config.py:151`:

```python
client_id=raw.get("client_id") or client_id,
```

Đối số constructor vừa là **khoá tra**, vừa là **giá trị dự phòng** cho id thật gửi lên
broker. Đúng [luật 03](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md), và nó chưa cắn
ai chỉ vì chưa app nào dùng MQTT.

**c. ⚠ Hai `MqttAdapter` khác id hôm nay là HỎNG THẬT, không phải giới hạn thiết kế.**

`MqttConfig.resolve()` đọc `runtime.get("mqtt")` - **một khối duy nhất, không theo id**.
Nên nếu YAML khai `mqtt.client_id`, hai adapter khác id vẫn nhận **cùng một**
`client_id` và đá nhau trên broker.

> Docstring của `MqttAdapter` giải thích rất kỹ vì sao không được trùng, nhưng chính
> đường đọc cấu hình lại **ép chúng trùng**.

**d. ⭐ `client_id` đã mang hai nghĩa NGƯỢC NHAU trong cùng framework.**

| Chỗ | `client_id` nghĩa là |
|---|---|
| gRPC client SDK: `grpc.clients.<client_id>` | tên của **service đích** (`trust`) |
| MQTT | định danh **phiên của chính ta** trên broker |

Một cái là tên người kia, một cái là tên của mình. Đây là lý do mạnh nhất để MQTT nhường
lại chữ đó.

### 1.4. ✅ CHỐT: hai tên cho hai hạng, cộng một tên chung ở tầng framework

| Tầng | Tên | Đổi gì |
|---|---|---|
| **Protocol `Adapter`** | **`adapter_id`** - thành viên của Protocol | Thay `getattr(_server_id, None)` phòng hờ |
| Constructor hạng **điểm phục vụ** (web, grpc, socket) | **`server_id`** | **Giữ nguyên**, không đổi một chữ |
| Constructor hạng **kết nối ra** (mqtt, modbus, opcua) | **`target_id`** | Thay cả ba: `client_id` · `device` · `server` |

Đổi **ba** adapter chứ không phải sáu, **YAML không phải sửa một chữ**, và tên đọc tự
nhiên ở cả hai phía.

#### Vì sao KHÔNG ép một tên cho cả sáu

Web/grpc/socket **mở cổng đợi người ta gọi vào**; mqtt/modbus/opcua **tự đi kết nối
ra**. Hai hạng có bộ khoá cấu hình khác hẳn nhau (`host`/`port`/`shared` so với
`client_id`/`topics`/thiết bị). Gọi một MQTT client là `server_id` là dán sai nhãn, và
người đọc phải nhớ một ngoại lệ.

⚠ **Cái sai rõ nhất KHÔNG phải *"sáu adapter bốn tên"*** mà là: **ba adapter cùng một
hạng dùng ba tên khác nhau** (`client_id` · `device` · `server`). Đó mới là di sản thật.

#### Vì sao `target_id`

| | |
|---|---|
| **Đúng cả ba** | mqtt tới broker, modbus tới thiết bị, opcua tới OPC UA server - đều là *"đích ta kết nối tới"* |
| **Framework đã dùng chữ này đúng nghĩa đó** | `_channel.py:250`: `target = f"{host}:{port}"` cho gRPC client. Không va tên cứng, mà là **cùng một nghĩa ở cùng một chiều** |
| **Giải phóng `client_id`** | Nó về đúng vai dữ liệu nghiệp vụ, và hết va với `grpc.clients.<client_id>` |

#### Các tên đã cân và loại - đừng đề xuất lại

| Tên | Vì sao loại |
|---|---|
| `device_id` | Đúng modbus/opcua, **sai mqtt** (broker không phải thiết bị) |
| `broker_id` | Ngược lại |
| `peer_id` | **Va thật** với `PEER_CN` / `PEER_SANS` (danh tính mTLS của đầu kia) |
| `link_id` | Đã dùng cho `ProcessLink` |
| `endpoint_id` | `endpoint` đã có nghĩa riêng trong `core/contract` (`ResolvedEndpoint`) |
| `connection_id` | Đúng nghĩa nhưng gợi ý *một kết nối TCP cụ thể*, mà mqtt reconnect thì kết nối đổi còn id thì không |
| `name` | Đúng khuôn `Store`/`RefData` vừa chốt, nhưng quá chung cho một đối số constructor |
| `adapter_id` ở constructor | Nó là tên của tầng framework; lặp lại ở bề mặt thì thừa, vì `web: { default: ... }` đã ngầm nói loại adapter |

### 1.5. ✅ CHỐT: `adapter_id` là thành viên Protocol, `use()` kiểm và nổ ngay

```python
@runtime_checkable
class Adapter(Protocol):
    adapter_id: str
    async def start(self, app: Application) -> None: ...
    async def stop(self) -> None: ...
```

`use()` gọi `isinstance(adapter, Adapter)`; sai thì **nổ ngay tại dòng `app.use(...)`**
trong `main.py` của người dùng.

#### Ba chi tiết kỹ thuật đã đo, đừng đo lại

| | |
|---|---|
| `isinstance` **kiểm được** data member | Đo thật: có `adapter_id` thì `True`, thiếu thì `False` |
| `issubclass` thì **không** | `TypeError: Protocols with non-method members don't support issubclass()`. Nên phải kiểm trên **instance** - mà `use()` vốn nhận instance nên khớp sẵn |
| Nó kiểm **có mặt**, không kiểm **có nghĩa** | Gán `self.adapter_id = None` vẫn qua. Muốn chặt hơn thì `use()` kiểm thêm chuỗi rỗng, nhưng đó là phép kiểm **giá trị**, tách khỏi phép kiểm **hợp đồng** |

#### Vì sao chọn cách này

1. **Nó là điều kiện của phần 2**, không phải tuỳ chọn đi kèm. Framework phải hỏi adapter
   *"anh tên gì"* **trước khi** biết đẩy khối `processes.<proc>.<loại>.<id>` nào vào. Id
   còn mềm thì câu hỏi đó trả về `None`, và lúc đó không có gì để làm ngoài đoán.
2. **Công cụ đã có sẵn và đã đúng** - `@runtime_checkable` viết từ đầu, chỉ chưa ai gọi.
   Đây là **dùng nốt thứ đã có**, không phải thêm cơ chế.
3. **Cùng khuôn với hai thứ vừa chốt**: `Store` và `RefData` quên khai `name` thì không
   vào DI. Adapter quên khai `adapter_id` thì không `use()` được. **Một framework nên có
   một cách hỏng.**

⭐ Được thêm một thứ ngoài dự tính: **`start`/`stop` cũng được kiểm luôn**, nên tầng lỏng
thứ ba (thiếu `start()` thì nổ muộn, trong `asyncio.gather`, **sau khi DI đã dựng xong
toàn bộ singleton**) đóng miễn phí cùng lúc.

⚠ **Cái giá phải khai thật:** đây là **phá tương thích với adapter do người ngoài viết**.
Chấp nhận được vì đúng nguyên tắc chủ dự án chốt 08-16 (*"cứ thay đổi code framework
thoải mái, để code phục vụ thiết kế"*), và 0.8 là bản Alpha cuối được làm việc đó.

### 1.6. Ba lựa chọn đã cân cho 1.5

| | Được | Mất |
|---|---|---|
| **A. Giữ mềm như nay** | Không phá ai | Phần 2 phải mang một nhánh *"adapter không khai id thì sao"* mà nhánh đó **không có câu trả lời đúng**. Và nó đứng cạnh quyết định cấm đối số cổng: đã cấm hai nguồn cho một giá trị thì khó biện minh cho việc để chính **khoá tra** thành tuỳ chọn |
| **B. Protocol + `isinstance`** ← **CHỐT** | Xem 1.5 | Phá tương thích adapter ngoài |
| **C. Lớp nền `BaseAdapter`** | Không quên được vì constructor bắt buộc | **Ép kế thừa.** Framework đã chọn Protocol chứ không ABC làm triết lý ([interface-binding.md](../../rules/interface-binding.md) mục 11), mà adapter lại đúng là chỗ người ngoài viết thêm nhiều nhất |

### 1.7. Kéo theo: tách `client_id` thật ra cấu hình

Sau khi `target_id` nhận vai định danh, `client_id` thật phải về cấu hình, và cấu hình
MQTT phải đọc **theo id** thay vì một khối chung (xem phát hiện **c** ở 1.3):

```yaml
mqtt:
  host: broker.local                                    # dùng chung
  clients:
    default: { client_id: data-svc-1,       topics: [...] }
    sensors: { client_id: data-svc-sensors, topics: [...] }
```

Đây chính là ba việc còn nợ ở
[mục 5.7.4](10-da-tien-trinh.md) mà chủ dự án đã lùi **thi
công** sang 0.8.1. ⚠ Nhưng **hình dạng khoá phải chốt ở 0.8** vì nó là API công khai.

### 1.8. Việc thi công của phần 1

| | |
|---|---|
| `core/bootstrap/adapter.py` | Thêm `adapter_id: str` vào Protocol |
| `core/bootstrap/application.py` | Import `Adapter` **thật** (không chỉ `TYPE_CHECKING`); `use()` gọi `isinstance` rồi mới chống trùng; bỏ `getattr(..., "_server_id", None)` |
| 3 adapter hạng phục vụ | Đổi `self._server_id` thành `self.adapter_id` |
| 3 adapter hạng kết nối ra | Đổi tên đối số sang `target_id`, gán `self.adapter_id` |
| `MqttAdapter` | Tách `client_id` thật ra cấu hình theo 1.7 |
| Test canh | `use()` từ chối object thiếu `adapter_id` · từ chối object thiếu `start`/`stop` · vẫn chống trùng đúng như cũ |

---

## 2. Cấu hình đẩy vào, không để adapter tự kéo ra - ĐÃ CHỐT

### 2.1. Hiện trạng đo được (2026-08-19)

| Adapter | Đọc cấu hình bằng đường nào |
|---|---|
| **web** | `runtime.server.host` / `.port` / `.ssl` - **thuộc tính typed trên `RuntimeConfig`** |
| grpc | `runtime.get("grpc")` -> dict, tự parse |
| socket | `runtime.get("socket")` -> dict |
| mqtt | `runtime.get("mqtt")` -> dict |
| modbus | `runtime.get("modbus")` -> dict |
| opcua | `runtime.get("opcua")` -> dict |

⭐ **Web đi đường khác hẳn năm cái kia**, và chỗ khác nằm sâu hơn tên khoá:
`core/config/runtime.py:70` có `class ServerConfig` với docstring *"Network binding for
the HTTP adapter"*.

> **Core của framework biết về khái niệm "HTTP adapter".** Năm adapter kia không có một
> dòng nào trong core.

⚠ **Một phép dò bắt nhầm, ghi lại để người sau khỏi giật mình:** grep
`get\w*\(["\']server` ra cả `modbus/_config.py` và `opcua/_config.py`, trông như hai
adapter fieldbus đang đọc cấu hình của web. **Không phải** - chúng đọc `modbus.server` và
`opcua.server`, tức khoá con **trong khối của chính chúng**. Phép dò khớp theo **hình
dạng chuỗi**, không theo **ngữ cảnh** - cùng họ với bài học về phép quét secret ở
CLAUDE.md của workspace.

### 2.2. ⭐ CHỐT: phát biểu lại điều 3 cho đúng trọng tâm

Điều 3 của mục 4 tài liệu đa tiến trình viết *"adapter không tự đi tìm cấu hình nữa"*, và
cách tóm tắt thành *"sáu quy ước khoá"* gợi ý **sai** rằng lời giải là thống nhất tên
khoá.

> **Lời giải không phải thống nhất TÊN KHOÁ, mà là adapter THÔI BIẾT về khoá.**

```text
Hôm nay:   adapter  ->  runtime.get("mqtt")  ->  tự parse
Phần 2:    framework đọc processes.<p>.<loại>.<id>  ->  ĐẨY ô đã lọc vào adapter
```

Sau đó *"sáu quy ước khoá"* biến mất khỏi adapter. Chỉ còn **một chỗ duy nhất** biết cách
ánh xạ cặp `(tiến trình, id)` ra cấu hình - và đó chính là điều kiện để `processes:` có
nghĩa.

### 2.3. ✅ CHỐT: khoá YAML cũ GIỮ NGUYÊN

App không gọi `share_load()` vẫn đọc `server.port` / `grpc.port` như cũ (mục 5.4 tài liệu
đa tiến trình). **31 app không phải sửa một dòng YAML.**

> Chỗ đổi là **AI đọc nó**, không phải **nó tên gì**.

### 2.4. ✅ CHỐT: mỗi adapter một kiểu cấu hình RIÊNG (cách 2)

Framework chịu trách nhiệm *"tìm đúng ô"*; adapter chịu trách nhiệm *"hiểu ô đó"*.

| Phương án | |
|---|---|
| ⛔ Một kiểu chung `AdapterConfig` với các trường tuỳ chọn | Đơn giản cho framework, nhưng mỗi adapter phải nhớ trường nào áp cho mình - **hợp đồng hứa nhiều hơn thứ nó giữ**, đúng thứ vừa tránh khi tách `Store` / `CounterStore` |
| ✅ **Mỗi adapter một kiểu riêng, framework chỉ đưa dict đã lọc đúng ô** | Ranh giới sạch, và **framework không phải biết `mqtt` có `topics`** hay `modbus` có thiết bị |

### 2.5. ✅ CHỐT: CẤM `ssl=` trong code, đưa ra cấu hình

Hai lý do cấm **khác nhau**, ghi rõ để sau này không ai suy sai:

| | Lý do cấm |
|---|---|
| `host` / `port` | **Mô tả sự thật** - cha `bind` rồi truyền fd, con không có cách nào tự chọn |
| **`ssl`** | **Ngoại lệ hết lý do tồn tại** - nó sinh ra để phục vụ server phụ cần cert khác, mà server phụ nay có ô cấu hình riêng `processes.<p>.web.<id>` |

⚠ Con **hoàn toàn nạp được** cert, nên đây không phải ràng buộc kỹ thuật. Giữ `ssl=` thì
không hỏng gì - chỉ là hai nguồn cho một giá trị.

⭐ Chỗ nó về **đã được vẽ từ 08-16**: bảng "khoá của một khối điểm phục vụ" ở mục 5.3 đã
liệt kê `ssl` kèm ghi chú *"Hiện đang truyền trong code, đây là chỗ nó nên về"*. Và
[`rules/config-discovery.md`](../../rules/config-discovery.md) đã chốt từ trước rằng TLS web
**không có `configure_web_tls()`** vì đường dẫn cert là việc vận hành.

### 2.5b. ⚠⚠ CHỖ THIẾT KẾ CHƯA NÓI TỚI, chốt 2026-08-20

> Phát hiện lúc thi công phần 2. Hai mục trên **đều đã chốt**, và chúng vênh nhau
> ở đúng một góc hẹp.

| Mục | Nói gì |
|---|---|
| **2.9** | *"Bỏ `host`/`port`/`path` khỏi constructor, nhận ô đã lọc"* - **vô điều kiện** |
| **2.5** | Biện minh cho việc cấm `ssl`: *"server phụ **nay có ô cấu hình riêng** `processes.<p>.web.<id>`"* |
| **9.1 B** của tài liệu đa tiến trình | Lý do cấm đối số: *"cha `bind` rồi truyền fd xuống, **con không có cách nào tự chọn cổng**"* |
| **5.4** của tài liệu đa tiến trình | *"Không gọi `share_load()` -> đọc `server.port` / `grpc.port` **như cũ**"* |

Câu ở 2.5 đúng **dưới `share_load()`**; ngoài nhánh đó thì **không có ô nào cả**.
Nên bỏ đối số làm một app **một tiến trình có server phụ** mất chỗ khai địa chỉ -
và 9.1B không phủ ca đó, vì lý do nó nêu (cha giữ socket) chỉ tồn tại ở nhánh
chia tải.

⭐ **Chỗ dễ lẫn phải nói rõ trước:** *"server phụ"* **không phải** *"tiến trình
phụ"*. Nguyên lý 3 đã tách sẵn - `server_id` là **điểm phục vụ bên trong một tiến
trình** - nên một tiến trình duy nhất vẫn mở được hai cổng HTTP, và chuyện đó độc
lập hoàn toàn với `share_load()`.

### ✅ CHỐT 2026-08-20: MỘT hình dạng, hai cách viết

> **`process:` là một khối. `processes:` là nhiều khối có tên. Bên trong hai cái
> giống hệt nhau.**

```yaml
# một tiến trình, hai cổng HTTP
process:
  web:
    public: { host: 0.0.0.0,   port: 8086 }
    admin:  { host: 127.0.0.1, port: 8081 }

# nhiều tiến trình - BÊN TRONG y hệt
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

Chủ dự án nêu tiêu chí: *"càng giống cái nhiều tiến trình càng tốt. chỗ nào không
dùng thì bỏ đi."* Ba khoá bị bỏ, và **framework báo lỗi** chứ không im lặng:
`primary` · `count` · `shared`.

| Quyết định | |
|---|---|
| Khoá phẳng `server:` / `grpc.port` | **GIỮ**, làm một phép **dịch** thành `process.web.default`. Đo được **58/69** file cấu hình dùng `server:` |
| `ssl` / `tls` | **Vào ô**. Kéo theo **bỏ `grpc.servers.<id>`** - nó là tên thứ ba cho cùng khái niệm, và nó giữ một khoá `port` **chết** (adapter ghi đè vô điều kiện bằng đối số constructor) |
| `share_load()` | **Vẫn là công tắc bên CODE**, không suy ra từ cấu hình. Lý do là nghĩa 1 của luật 01: app phải được **viết** cho nhiều tiến trình trước khi ai được phép bật, và để người vận hành nhân bốn bằng cách sửa YAML là một cách hỏng không có triệu chứng |

⚠ **Cái bẫy một chữ:** `process` và `processes` khác nhau đúng một ký tự, nên
framework bắt **cả hai chiều** - không tổ hợp nào chạy êm mà sai.

⭐ Đo trước khi bỏ đối số: **0/27 app** trong workspace dùng server phụ, nên không
app nào phải sửa. 74 chỗ nhắc tới nằm gọn trong repo này.

### 2.6. ✅ CHỐT: `client_id` và `topics` vào **`processes`**, khối `mqtt:` làm mặc định

> ⛔⭐ **Bản đầu của mục này ĐỀ NGHỊ SAI, giữ lại vết vì nó là một ca đáng học.**
>
> Phiên đề nghị `mqtt.clients.<id>` - **một trục duy nhất, theo adapter id**. Nhưng
> `client_id` phải khác nhau **theo TIẾN TRÌNH**, không phải theo adapter:
>
> > Ba tiến trình cùng chạy `MqttAdapter(target_id="nha-may")` sẽ đọc **cùng một ô**
> > `mqtt.clients.nha-may` và nhận **cùng một `client_id`** - broker chỉ cho một phiên trên
> > mỗi client id nên nó đá phiên cũ ra, ba tiến trình đánh nhau trong vòng lặp reconnect.
>
> **Đúng lỗi vừa phát hiện ở [1.3c](#13--bốn-phát-hiện-mỗi-cái-đổi-một-phần-kết-luận) và
> tưởng là đang đi sửa.**
>
> ⭐ Lời giải đúng **đã có sẵn ở mục 5.7.4 tài liệu đa tiến trình từ 2026-08-16**, và
> phiên bỏ qua nó vì đang nhìn từ phía phần 1 (định danh) thay vì từ phía mô hình chạy.
>
> **Bài học:** khi một mảnh thiết kế cũ đã chạm vào cùng một dữ liệu, **đọc nó trước khi
> đề xuất hình dạng mới** - kể cả khi đang đứng ở một mảng khác. Cùng họ với thói quen rà
> lại danh sách câu treo, nhưng ngược chiều: không phải *"mảnh mới đóng câu cũ nào"* mà là
> ***"mảnh cũ đã trả lời câu mới nào"***.

### Hình dạng chốt

```yaml
mqtt:
  host: broker.local          # mô tả BROKER -> mặc định cho mọi tiến trình
  port: 1883
  tls: { ... }

processes:
  main:
    mqtt:
      nha-may: { client_id: xime-main, topics: ["nha-kinh/A/#"] }
  api-2:
    mqtt:
      nha-may: { client_id: xime-2,    topics: ["nha-kinh/B/#"] }
```

**Ba tầng khoá `tiến trình -> mqtt -> adapter id`**, y hệt web/grpc. Không cần bốn tầng
như Modbus, vì ở đây chia theo **tiến trình máy chủ** chứ không theo thiết bị vật lý.

| Thứ gì | Ở đâu | Vì sao |
|---|---|---|
| `host`, `port`, `tls` | khối `mqtt:` chung | Mô tả **broker**, mọi tiến trình nối cùng chỗ |
| **`client_id`, `topics`** | `processes.<p>.mqtt.<id>` | Đây là thứ **PHẢI** khác nhau giữa các tiến trình |

⚠ **Ô trong `processes` ghi đè được MỌI khoá của `mqtt:`**, không chỉ hai khoá trên. Ca
cần tới: một app nối **hai broker khác nhau** (nhà máy A và nhà máy B) thì `host` cũng
phải theo adapter id.

⭐ Khuôn "chung + ghi đè" này **không phải phát minh** - `opcua` đã hiện thực đúng nó
(`adapters/opcua/_config.py:62-95`): app một server viết thẳng dưới `opcua:`, app nhiều
server lồng trong `opcua.servers.<name>`, hàm `pick()` tra **entry trước, raw sau, rồi
mặc định**, tên lạ thì `StartupException` kèm danh sách tên đã biết.

> Chép logic `pick()` sang mqtt là xong - chỉ khác **tầng ghi đè nằm trong `processes`**,
> không nằm trong khối `mqtt`. **Đừng thiết kế lại.**

⚠ Kéo theo cho phép kiểm số 4 lúc khởi động (mục 6 tài liệu đa tiến trình): với MQTT thì
*"điểm phục vụ không nhân bản được xuất hiện ở hai khối"* đổi thành **hai khối trùng
`client_id`** mới là lỗi. Điều này mục 5.7.4 đã ghi sẵn.

### 2.6b. ✅ CHỐT: `@subscribe` mất một VAI, giữ nguyên chữ ký

> ⚠ Bản đầu của phiên xếp mục này vào nhóm *"đổi chữ ký decorator công khai"*. **Sai** -
> chữ ký không đổi một ký tự. Đọc code mới thấy vấn đề nằm ở chỗ khác.

#### Chuỗi topic trong `@subscribe` đang đi qua HAI đường

```python
@subscribe("nha-kinh/+/nhiet-do", qos=1)
async def on_temp(self, payload: bytes, topic: str) -> None: ...
```

| Vai | Đi tới đâu | Nói gì |
|---|---|---|
| **a. Đăng ký với broker** | `client.subscribe(topic, qos, subscription_identifier=sub_id)` | *"gửi tôi message khớp filter này"* |
| **b. Định tuyến nội bộ** | `dispatcher._by_sub_id[sub_id]` | *"message này thuộc handler nào"* |

⭐ **Chia tải theo topic chỉ cần đổi vai (a).** Vai (b) không dính gì - handler nào xử lý
message nào là chuyện của code, không phải của việc chia tải.

> Nên đây không phải *"chuyển topic từ code sang cấu hình"*. Đó là **tách một giá trị
> đang mang hai nghĩa** - [luật 03](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md) ở
> tầng decorator.

#### Vì sao vai (a) buộc phải rời khỏi code

Chia tải MQTT đã chốt là **chia theo topic** (không dùng shared subscription vì `$share`
phá thứ tự trong một thiết bị). Nghĩa là **cùng một controller, cùng một class, chạy ở
hai tiến trình, nghe hai tập topic khác nhau** - không làm được nếu filter nằm trong
code, vì code chỉ có một bản.

#### ⚠ "Lấy giao" không đơn giản - hai phương án, chốt P2

Cả `@subscribe` lẫn `topics` đều là **filter có ký tự đại diện**, nên giao của chúng
không phải phép giao tập hợp:

```text
@subscribe("nha-kinh/+/nhiet-do")   ∩   topics: ["nha-kinh/A/#"]
                                    =   nha-kinh/A/nhiet-do
```

| | Cách làm | Được | Mất |
|---|---|---|---|
| **P1** | Tính giao hai filter rồi subscribe cái giao | Giữ `subscription_identifier` làm đường tắt định tuyến | Phải viết và kiểm **thuật toán giao hai MQTT filter**, có ca biên khó (`#` ở giữa, `+` chồng `#`). Sai một ca là **nghe thiếu topic mà không gì báo** |
| ✅ **P2** | **Subscribe theo cấu hình; dispatcher khớp topic THẬT với filter trong code** | **Không cần thuật toán giao.** Khớp một topic *cụ thể* với một filter là việc dispatcher **đã có sẵn** (`_match`, vốn dùng cho broker không hỗ trợ subscription id) | Mất đường tắt `sub_id`: khớp filter mỗi message thay vì tra dict |

> Chọn **P2** vì cái mất của nó là một **tối ưu**, còn cái mất của P1 là **tính đúng
> đắn** - mà sai thì im lặng.

⚠ Chi phí thật của P2 nên đo trước khi lo: khớp một filter là duyệt vài đoạn chuỗi, và
mỗi controller thường chỉ vài route. Không phải vòng lặp nóng.

#### Ba câu con - chốt hết 2026-08-19

| | Câu | Chốt |
|---|---|---|
| **1** | Cấu hình **không khai** `topics` thì sao | **Dùng nguyên filter trong code.** App một tiến trình không phải khai gì, chạy y hệt hôm nay |
| **2** | Cấu hình khai topic mà **không route nào** khớp | **Cảnh báo**, không nổ - nghe thừa thì tốn băng thông, không sai |
| **3** | Có route mà **không tiến trình nào** nghe | **Cảnh báo** |

⭐ **Câu 3 là lý do chính đáng nhất để làm phép kiểm này**: nó bắt được thứ mà không có
nó thì **một loại message rơi vào hư không**, hệ thống trông vẫn khoẻ, và không ai biết
cho tới khi có người hỏi *"sao dữ liệu nhà kính B mất?"*.

#### Hệ quả: đây KHÔNG phải thay đổi phá tương thích

`@subscribe` giữ nguyên chữ ký; app không khai `topics` thì hành vi y hệt. Thứ đổi là **ý
nghĩa**: từ *"nghe topic này"* thành *"tôi xử lý được topic này"*.

Vẫn phải khai ở 0.8 (bản Alpha cuối) vì nó là ngữ nghĩa của một decorator công khai -
nhưng nó **không bắt app nào sửa gì**.

### 2.7. ✅ CHỐT: `processes:` và `share_load()` không khớp thì NỔ

Cổng có **hai hình dạng cấu hình**, tuỳ nhánh:

| Nhánh | Cổng khai ở |
|---|---|
| Không `share_load()` (31 app hôm nay) | `server.port`, `grpc.port` |
| Có `share_load()` | `processes.<p>.<loại>.<id>.port` |

Hai nhánh **loại trừ nhau** nên không phải "hai nguồn cho một giá trị" theo nghĩa đã cấm
ở câu cổng. Nhưng người vận hành phải biết mình đang ở nhánh nào, và **sửa nhầm chỗ thì
không gì báo** - đúng cách hỏng đã thấy khi cấm đối số cổng.

> **Có khối `processes:` mà không gọi `share_load()`, hoặc ngược lại -> lỗi khởi động.**

Rẻ, và nó biến một lỗi im lặng thành một dòng chữ.

### 2.8. ✅ CHỐT: GỠ `ServerConfig` KHỎI CORE

`core/config/runtime.py:70-75` khai `host`, `port`, `ssl` với docstring *"Network binding
for the HTTP adapter"*.

> Đây là **cùng khuôn với `PEER_APP_ID`** đã gỡ hôm 2026-08-17 - *"framework không được
> phụ thuộc gì khái niệm ngoài cả"*. Chỉ khác là lần đó core biết về **Xime**, lần này
> core biết về **một adapter cụ thể**.

Bất đối xứng đó **không có lý do thiết kế nào** - nó là di sản của việc web ra đời trước.

#### ⭐ Đo trước khi quyết: KHÔNG PHÁ AI

Quét toàn workspace (framework + 27 app, bỏ `tests_temp`) tìm mọi lời gọi
`runtime.server` / `.server.host` / `.server.port` / `.server.ssl`:

```text
3  .\xime framework\xime\adapters\web\_adapter.py
--- 1 file
```

**Đúng một file, và đó chính là adapter sở hữu nó.** Không app nào gọi. Nên gỡ là chuyện
nội bộ framework, không phải thay đổi phá tương thích với người dùng.

⚠ Khoá **YAML** `server:` thì 25 app vẫn dùng - và nó **giữ nguyên** theo 2.3. Gỡ ở đây
là gỡ **thuộc tính Python trên `RuntimeConfig`**, không phải gỡ khoá YAML.

Sau khi gỡ, core chỉ còn giữ `env` và `logging` - những thứ thật sự của core.

### 2.9. Việc thi công của phần 2

| | |
|---|---|
| `core/config/runtime.py` | Bỏ `ServerConfig` và trường `server` |
| `adapters/web` | Tự dựng kiểu cấu hình của mình từ ô được đẩy vào; bỏ `host`/`port`/`ssl` khỏi constructor |
| `adapters/grpc`, `socket` | Bỏ `host`/`port`/`path` khỏi constructor, nhận ô đã lọc |
| `adapters/mqtt` | Chép khuôn `pick()` của opcua; `client_id`/`topics` đọc từ **`processes.<p>.mqtt.<id>`**, khối `mqtt:` làm mặc định |
| `core/bootstrap` | Một chỗ duy nhất ánh xạ `(tiến trình, loại, id)` -> ô cấu hình, rồi đẩy vào adapter |
| Phép kiểm mới | `processes:` và `share_load()` không khớp -> `StartupException` |
| Test canh | Adapter không còn đọc `runtime.get(...)` trực tiếp · app cũ (không `share_load`) vẫn chạy nguyên |

---

## 3. Hạng nhân bản là dữ liệu - ĐÃ CHỐT

### 3.1. Vấn đề

Lý do chống trùng đang nằm trong **docstring**. `MqttAdapter` viết cả một đoạn giải thích
vì sao hai adapter cùng id sẽ đánh nhau trong vòng lặp reconnect - framework **đọc được
nhưng không dùng được**.

### 3.2. Ba hạng, không phải bốn

| Hạng | Nghĩa | Ai |
|---|---|---|
| **Nhân bản** | N tiến trình chạy N bản giống hệt, kernel chia tải | web, grpc |
| **Phân mảnh** | Mỗi tiến trình một **phần** của việc, không bản nào giống bản nào | modbus, opcua, **mqtt** |
| **Đơn nhất** | Chỉ primary chạy | scheduler |

⚠ Tài liệu đa tiến trình từng ghi *"bốn hạng"* khi mqtt còn được xếp riêng; sau khi mqtt
gộp vào **phân mảnh** thì còn **ba**, nhưng nhãn không được sửa theo - **đã sửa
2026-08-19**. Phần này dựng thẳng trên phân loại đó nên nếu không sửa thì lệch ngay từ
câu đầu.

⭐ **Nhân bản cho *dư thừa*, phân mảnh thì KHÔNG.** Một tiến trình web chết thì ba con
còn lại phục vụ tiếp; một tiến trình modbus chết thì **cụm thiết bị của nó không ai
đọc**. Đó là khác biệt về chất, không phải về mức.

### 3.3. ⚠ Hạng là ĐIỀU KIỆN, không phải nhãn cứng

> *"mqtt nhân bản được **NẾU** mỗi bản có `client_id` riêng"*

Nên một nhãn `"sharded"` **không đủ** - nó phải chở theo *điều kiện gì phải khác nhau
giữa các tiến trình*. Đó là thứ framework cần để chạy **phép kiểm số 4 lúc khởi động**
(mục 6 tài liệu đa tiến trình): hai khối trùng `client_id` thì nổ.

### 3.4. ✅ CHỐT: khai bằng THAM SỐ CLASS (PEP 487), BẮT BUỘC khai

```python
class WebAdapter(Adapter, scaling="replicated"): ...

class MqttAdapter(
    Adapter,
    scaling="sharded",
    unique_per_process=("client_id",),     # giá trị phải KHÁC NHAU
    disjoint_per_process=("topics",),      # tập phải KHÔNG GIAO NHAU
): ...

class ModbusAdapter(
    Adapter,
    scaling="sharded",
    disjoint_per_process=("devices",),
): ...

class SchedulerAdapter(Adapter, scaling="singleton"): ...
```

Ba giá trị của `scaling`: **`replicated`** · **`sharded`** · **`singleton`**.

⚠ **Tên tham số dùng tiếng Anh**, khác bản nháp đầu của phiên (`hang=`,
`khac_nhau_theo=`). Lý do không phải thẩm mỹ: **mọi API công khai của framework đang
dùng tiếng Anh** - `adapter_id`, `target_id`, `server_id`, và `name` / `ttl` / `parts`
của `Store` vừa chốt cùng ngày. Framework làm ra cho người ngoài dùng, nên một tham số
tiếng Việt lọt vào là một ngoại lệ không có lý do.

#### ✅ CHỐT: `scaling` BẮT BUỘC khai, không có mặc định

| Nếu có mặc định | Rủi ro |
|---|---|
| `replicated` | **Nguy**: adapter chưa từng nghĩ tới nhân bản sẽ bị nhân bản, và nó hỏng **im lặng** |
| `singleton` | An toàn, nhưng app chậm mà **không ai biết vì sao** |
| ✅ **Không có mặc định** | Quên khai thì **nổ lúc khởi động**. Đúng khuôn `Store` phải khai `name` |

> Đây là quyết định người viết adapter **phải** đưa ra, và **không giá trị nào đoán hộ
> được**. Cùng lập luận đã dùng cho `adapter_id` ở phần 1.

### 3.5. ✅ CHỐT: HAI phép kiểm khác nhau, hai tên khác nhau

`unique_per_process` và `disjoint_per_process` **không phải một khái niệm viết hai kiểu**
- chúng là hai phép kiểm khác hẳn:

| Tham số | Phép kiểm | Vì sao cần |
|---|---|---|
| **`unique_per_process`** | Giá trị của khoá đó ở hai khối **phải KHÁC NHAU** | Hai tiến trình cùng `client_id` thì broker đá phiên cũ ra, chúng đánh nhau trong vòng lặp reconnect |
| **`disjoint_per_process`** | Tập giá trị ở hai khối **KHÔNG ĐƯỢC GIAO NHAU** | Hai tiến trình cùng nghe một topic thì **mỗi message bị xử lý hai lần**; hai tiến trình cùng đọc một thiết bị Modbus thì tranh nhau kết nối |

#### ⭐⭐ MQTT cần CẢ HAI cùng lúc - và đó là bằng chứng tách đúng

`client_id` phải **khác nhau**; `topics` phải **không giao nhau**. Gộp làm một khái niệm
thì không có cách nào diễn tả cả hai, vì:

> *"khác nhau"* áp cho một **giá trị đơn**; *"không giao nhau"* áp cho một **tập**. Ép
> chung một phép kiểm là hoặc bỏ sót một loại, hoặc viết một phép kiểm mơ hồ mà không ai
> biết nó đang kiểm gì.

⚠ Fieldbus chỉ cần vế thứ hai: thứ phải khác nhau giữa các tiến trình modbus **không
phải một trường của adapter** mà là **tập thực thể nó phụ trách** - đúng bốn tầng khoá
`process -> modbus -> loại -> thực thể` chốt ở mục 5.7.3 tài liệu đa tiến trình.

⛔ **`replicated` và `singleton` KHÔNG được khai hai tham số này** - khai là lỗi khởi
động. Chúng chỉ có nghĩa với `sharded`, và một tham số bị bỏ qua im lặng là chỗ để người
ta tin vào thứ không xảy ra.

### 3.5b. Framework dùng nó vào việc gì

| Hạng | Cha làm gì |
|---|---|
| `replicated` | Sinh ở **mọi** tiến trình khai nó |
| `sharded` | Sinh ở mọi tiến trình khai nó, **cộng hai phép kiểm** ở 3.5 - vi phạm thì **nổ lúc khởi động** |
| `singleton` | **Chỉ `start()` ở primary.** Đây là chỗ `SchedulerRunner` sẽ về (phần 5) |

⭐ Nhờ ô cuối mà **vế "tắt bằng cờ" của mục 2.7 hết cần** - không ai gọi thì không chạy,
không cần cờ nào trong object để mà quên kiểm.

⚠ **Đừng lẫn `scaling="singleton"` với Protocol `RunOnce`** - hai ô khác nhau trong bảng
bốn ô chốt 2026-08-18:

| | Mọi tiến trình | Một lần cho cả cụm |
|---|---|---|
| **Chạy một lần rồi thôi** | `post_construct()` | **`run_once()`** |
| **Chạy mãi** | `Adapter.start()` | **`scaling="singleton"`** |

### 3.5c. ⏭ Còn lại: thăng cấp primary khởi động adapter `singleton` thế nào

DI đã dựng đủ ở mọi tiến trình (chốt 2.7), chỉ là adapter `singleton` **chưa được
`start()`** ở con phụ. Nên thăng cấp = cha bảo con B *"gọi `start()` cho các adapter
singleton của mày"*.

⚠ Nó đụng một thứ đã chốt: docstring `Adapter.start()` hiện nói *"gọi sau khi DI dựng
xong"*, trong khi ở đây `start()` được gọi **sau khi app đã chạy một thời gian**.

> **Chủ dự án chốt 2026-08-19: để [phần 4](#4-vòng-đời-và-tín-hiệu-đã-sẵn-sàng---chưa-bàn)
> trả lời**, cùng câu vòng đời. Đường truyền thì đã có sẵn: `ProcessLink`, kênh nội bộ
> `__xime__`.

### 3.6. Việc thi công của phần 3

| | |
|---|---|
| `core/bootstrap/adapter.py` | `__init_subclass__` nhận `scaling` (**bắt buộc**), `unique_per_process`, `disjoint_per_process`; kiểm giá trị hợp lệ và kiểm `replicated`/`singleton` **không** khai hai tham số sau |
| Sáu adapter | Khai `scaling` đúng hạng của mình |
| `core/bootstrap` | Phép kiểm số 4 đọc `unique_per_process` (**khác nhau**) và `disjoint_per_process` (**không giao nhau**) thay vì đọc docstring |
| Test canh | Quên khai `scaling` -> nổ · sai giá trị -> nổ · hai khối `sharded` **trùng** `unique_per_process` -> nổ · hai khối **giao nhau** ở `disjoint_per_process` -> nổ · `replicated` khai hai tham số kia -> nổ · `singleton` không được start ở tiến trình phụ |

---

## 4. Vòng đời và tín hiệu "đã sẵn sàng" - ĐÃ CHỐT

### 4.1. Vấn đề: `start()` làm HAI việc trong một

```python
async def start(self, app: Application) -> None:
    """Should block until the adapter is stopped."""
```

| Việc | Tính chất |
|---|---|
| **1. Dựng và chiếm tài nguyên** (bind cổng, nối broker, dựng bảng route) | Nhanh, có thể lỗi, lỗi thì **nên sập** |
| **2. Phục vụ** (`serve()`, `wait_for_termination()`) | Chạy suốt vòng đời |

**Không có chỗ nào nói *"xong bước 1"***, trong khi ba việc cùng cần câu đó: cha sinh con
tiếp theo · **F10** cô lập lỗi · `/readyz`.

### 4.2. ✅ CHỐT: tách `start()` + `serve()` (phương án P1)

```python
@runtime_checkable
class Adapter(Protocol):
    adapter_id: str
    async def start(self, app: Application) -> None:   # chiếm tài nguyên, TRẢ VỀ khi xong
    async def serve(self) -> None:                     # phục vụ, CHẶN
    async def stop(self) -> None:
```

#### ⭐⭐ Ba thư viện bên dưới ĐÃ tách sẵn - P1 không ép gì cả

Đo 2026-08-19:

| Adapter | Thư viện đã có |
|---|---|
| gRPC | `await server.start()` (**non-blocking**) rồi `await server.wait_for_termination()` |
| web | `uvicorn.Server` có **`startup()`** và **`main_loop()`** riêng |
| socket | `asyncio.start_unix_server()` (đã bind, trả về ngay) rồi `serve_forever()` |

⭐ gRPC adapter **đã gọi đúng hai bước đó ở hai dòng liền nhau** (`_adapter.py:151-152`) -
chỉ là framework gộp chúng lại sau một `start()` duy nhất.

> P1 **không phải ép một hình dạng mới lên adapter**. Nó là **thôi che giấu** cấu trúc vốn
> đã có ở tầng dưới.

#### Hai phương án đã loại

| | Vì sao loại |
|---|---|
| **P2** - giữ một `start()`, thêm `asyncio.Event` adapter tự `set()` | **Nghĩa vụ không cưỡng chế được**: adapter quên `set()` thì framework đợi mãi. Hỏng đúng khuôn `getattr(adapter, "_server_id", None)` vừa sửa ở phần 1 - một nghĩa vụ ngầm, quên thì **im lặng** |
| **P3** - `start()` thành async generator, `yield` khi sẵn sàng | Lạ, khó đọc, và không thư viện nào bên dưới có hình dạng đó |

### 4.3. ✅ CHỐT: F10 - ba tình huống, ba xử lý

⭐ P1 biến ranh giới *"trước hay sau khi phục vụ"* từ một **mong muốn** (kiểm toán viết
nhưng không hiện thực được ở 0.7 vì `start()` gộp hai giai đoạn) thành thứ **cưỡng chế
được**:

| Lỗi ném ra từ | Nghĩa | Xử lý |
|---|---|---|
| `start()` **lúc khởi động** | Chưa phục vụ được - cổng bị chiếm, cert hỏng, broker từ chối | **SẬP cả tiến trình**, đúng như hôm nay |
| `start()` **lúc thăng cấp** | Không nhận được vai primary | ⭐ **TỪ CHỐI VAI, KHÔNG sập** - xem 4.4 |
| `serve()` | Đã phục vụ rồi mới hỏng | **CÔ LẬP adapter đó**, log `CRITICAL`, báo ra ngoài |

#### Hiện trạng đang sửa

```python
async with asyncio.TaskGroup() as tg:
    for adapter in self._adapters:
        tg.create_task(adapter.start(self))
```

`TaskGroup` có ngữ nghĩa **một task ném lỗi thì mọi task anh em bị hủy**. Với lỗi lúc khởi
động thì đúng; nhưng `start()` chạy suốt vòng đời nên luật đó áp cả lúc đang chạy: **server
gRPC ném một lỗi không bắt được thì web adapter bị hủy theo và tiến trình thoát**. Một app
đang phục vụ HTTP cho người dùng thật tắt vì sự cố ở kênh nội bộ - đúng điều chủ dự án nêu
khi đặt đợt kiểm toán (*"không muốn lỗi framework là sập toàn bộ"*).

#### ✅ CHỐT: framework LUÔN cô lập + LUÔN báo ra ngoài; ai phản ứng là việc tầng trên

Đừng cho framework hai hành vi theo nhánh (có `share_load()` hay không) - khó đoán, và
người viết app phải nhớ mình đang ở nhánh nào.

| Tầng trên | Nghe bằng | Phản ứng |
|---|---|---|
| Cha (có `share_load()`) | **sự kiện qua `ProcessLink`** (xem 4.3b) | Giết và dựng lại con |
| Load balancer | `/readyz` đỏ | Rút khỏi vòng |
| systemd / k8s | `/healthz` đỏ | Restart tiến trình |
| Không ai | - | App im. Đó là lựa chọn của app |

⭐ Cùng nguyên tắc đã dùng hai lần cùng ngày: *"đừng viết bộ cân bằng tải"* và *"systemd
canh cha"* - **framework cấp sự thật, không tự quyết thay tầng trên**.

#### ✅ CHỐT: adapter cuối cùng chết thì tiến trình VẪN SỐNG

Phiên đề nghị *"thoát"*; **chủ dự án bác**: *"tôi vẫn muốn giữ tiến trình sống"*.

Bác đúng, và lý do mạnh hơn lý do phiên đưa ra: **tiến trình còn sống thì `/healthz` còn
trả lời được, log còn đọc được, còn gỡ lỗi được**. Thoát thì mất hết - kể cả khả năng nói
cho người khác biết vì sao mình chết.

### 4.3b. ⭐⭐ Trạng thái adapter đi bằng BUS, KHÔNG nhồi vào nhịp watchdog

Quyết định giữ tiến trình sống lộ ra một câu: **watchdog đo "event loop còn quay", không đo
"còn phục vụ được"**. Một tiến trình mất hết adapter vẫn vỗ đều đặn, và cha thấy nó khoẻ.

Phiên đề nghị nhồi *số adapter còn phục vụ* vào byte `trangThai` của nhịp vỗ. **Chủ dự án
bác**: *"cha con giao tiếp được với nhau mà, việc gì cứ phải cho mỗi watchdog"*.

Bác đúng, và lý do là chính [luật 03](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md) mà
mục này vừa viện dẫn ba lần:

| Cơ chế | Trả lời câu | Hình dạng |
|---|---|---|
| **Watchdog** | *"tôi còn quay không"* | **Nhịp đều đặn**, một câu duy nhất |
| **`ProcessLink`** | *"vừa có chuyện gì xảy ra"* | **Sự kiện**, bao nhiêu thông tin cũng được |

> Nhồi trạng thái vào nhịp vỗ là bắt **một cơ chế trả lời hai câu** - đúng thứ luật 03 cấm,
> và phiên suýt làm ngay sau khi trích dẫn nó.

**Hai lý do kỹ thuật đi kèm, cùng chiều:**

| | |
|---|---|
| **Độ trễ** | Nhịp vỗ 1 giây -> tin adapter chết trễ **tới 1 giây**. Bus thì tức thì |
| **Chiều đẩy** | Nhịp vỗ là **poll** (cha phải đi đọc); bus là **push** (cha được đánh thức) |

#### Hệ quả: nhịp vỗ gọn lại còn ĐÚNG một việc

Byte `trangThai` từng chừa cho tín hiệu **ready** cũng nên đi bằng bus - ready là một **sự
kiện xảy ra một lần**, không phải một đại lượng đo liên tục.

> Khung tin nhịp vỗ còn lại **chỉ `mocVo`**. Đúng bản chất watchdog phần cứng: một mạch đếm,
> một câu hỏi.

⚠ Sửa lại mô tả ở [mục 2.8b](10-da-tien-trinh.md) tài liệu đa tiến
trình - chỗ đó đang ghi khung tin có `trangThai`.

### 4.4. ✅ CHỐT: `start()` lỗi lúc THĂNG CẤP thì từ chối vai, không sập

Ca cụ thể: con B được thăng cấp, gọi `start()` cho `CertRotationJob`, và `start()` **ném
lỗi** vì cert hỏng.

Nếu áp nguyên luật *"lỗi trong `start()` thì sập"* thì con B sập → cha thăng cấp C → C sập →
**đúng domino**. Có `N=3`/`T=60` chặn, nhưng vẫn mất ba tiến trình đang phục vụ vì một cái
cert.

> **Lỗi trong `start()` LÚC KHỞI ĐỘNG thì sập. Lỗi trong `start()` LÚC THĂNG CẤP thì TỪ CHỐI
> VAI PRIMARY, không sập.**

Con B báo cha *"tôi không nhận được vai"*, cha đếm vào bộ đếm domino và thử con khác. **Con B
vẫn phục vụ HTTP bình thường** - nó chỉ không làm primary.

#### ⚠ Bắt buộc kèm CẢNH BÁO - và hôm nay cảnh báo đó chỉ tới được journald

Chủ dự án chốt kèm điều kiện: **phải có cảnh báo**. Nhưng nó vấp đúng chỗ đang hoãn (*"cha
không có mồm"*, mục 2.8c tài liệu đa tiến trình).

Phân biệt cứu vãn phần lớn:

| Chặng | Trạng thái |
|---|---|
| Con báo cha | ✅ **Đã thông** - sự kiện qua `ProcessLink` |
| Con ghi log | ✅ **Đã thông** - `stderr` -> journald |
| **Cha nói ra ngoài** | ⛔ **Đang hoãn** |

> Nên hôm nay cảnh báo **tới được journald, KHÔNG tới được người**. Khai rõ để không ai
> tưởng đã xong.

⭐ **Danh sách thứ chờ *"cha không có mồm"* nay dài gấp đôi:**

| # | Thứ chờ |
|---|---|
| 1 | "Kêu to" khi dừng thăng cấp (chống domino) |
| 2 | `/healthz` tổng |
| 3 | **Cảnh báo khi con từ chối vai primary** (mới 2026-08-19) |
| 4 | **Báo adapter bị cô lập** (mới 2026-08-19) |

Ghi ở đây vì khi mở lại mục 2.8c thì đây là bốn đối tượng phải phục vụ, không phải hai.

### 4.5. Thăng cấp primary khởi động adapter `singleton` (câu C3 của phần 3)

> ✅ **ĐÃ THI CÔNG 2026-08-20.**
>
> ⚠⚠ **Một giả định của mục này SAI, và nó làm thăng cấp vô hiệu cho mọi adapter
> ngoài scheduler.** Câu *"con biết adapter nào là singleton (`scaling`)"* giả
> định adapter đó **có mặt ở con** - và ở giai đoạn 3 thì không:
> `prepare_worker` lọc adapter theo khối cấu hình của tiến trình, còn
> `_reject_singleton_in_many_processes` thì **cấm** khai adapter đơn nhất ở khối
> khác khối primary. Hai luật đúng riêng lẻ; gặp nhau thì con phụ không có
> adapter đó để mà nhận vai, cụm mất job nền vĩnh viễn, và **không gì báo**.
>
> Đã sửa: adapter hạng đơn nhất được **giữ ở mọi tiến trình** và lấy ô cấu hình
> của khối primary (theo cấu trúc chỉ có đúng một ô như vậy).
>
> 📌 `SchedulerRunner` không dính vì nó do **framework** đăng ký, sau
> `prepare_worker` - tức ca duy nhất chạy được hôm nay là ca **đi vòng qua chỗ
> hỏng**. Đúng khuôn *"test đi đường tắt không thấy lỗi ở chỗ nối"*, lần thứ tư
> trong 0.8.

Với P1 thì đơn giản:

```text
cha gửi lệnh "mày là primary" qua kênh __xime__
  -> con gọi start() cho các adapter scaling="singleton"    (nhanh, có thể lỗi -> 4.4)
  -> nếu OK thì đưa serve() vào nhóm task đang chạy
```

Ba mảnh đều đã có sẵn: chỗ gọi `start()` muộn (P1) · đường cha báo con (`ProcessLink`) · con
biết adapter nào là singleton (`scaling`).

⭐ Câu vướng cũ - *docstring `start()` nói "gọi sau khi DI dựng xong"* - **tự tan**: với P1,
`start()` là **chiếm tài nguyên**, và không có gì bắt việc đó phải xảy ra đúng lúc khởi động.

⚠ Chi tiết kỹ thuật: giữ `asyncio.TaskGroup` thì **thêm task vào nhóm đang chạy được**, miễn
gọi từ bên trong một task con của nhóm. Nhưng F10 đổi sang cô lập thì có lẽ không dùng
`TaskGroup` nữa - lúc đó càng dễ.

### 4.6. Việc thi công của phần 4

| | |
|---|---|
| `core/bootstrap/adapter.py` | Thêm `serve()` vào Protocol |
| `core/bootstrap/application.py` | Gọi `start()` tuần tự cho mọi adapter (lỗi -> sập), rồi mới chạy `serve()` song song; thay `TaskGroup` bằng cơ chế **cô lập** |
| Sáu adapter | Tách `start()`/`serve()` - **thư viện bên dưới đã tách sẵn**, chỉ việc dùng đúng |
| `ProcessLink` | Con gửi **sự kiện** khi adapter sẵn sàng / bị cô lập / từ chối vai. ⛔ **Không** nhồi vào nhịp watchdog |
| Test canh | Lỗi `start()` lúc khởi động -> sập · lỗi `serve()` -> chỉ adapter đó chết, anh em sống · lỗi `start()` lúc thăng cấp -> từ chối vai, tiến trình sống · adapter cuối chết -> tiến trình **vẫn sống** |

---

## 4b. Câu E - `@poll` / `@on_change` theo THỰC THỂ - ĐÃ CHỐT

> Chủ dự án ủy quyền 2026-08-19: *"bỏ `device=`, chỗ này bạn hãy tìm hướng phù hợp nhất và
> quyết luôn"*. Phiên quyết sau khi đo code thật; hai phép đo dưới đây quyết định cả hướng.

### 4b.1. ⭐⭐ Phát hiện: đây KHÔNG chỉ là đổi chữ ký decorator

Đo `adapters/modbus/_adapter.py`:

```text
dòng  9: "It owns the connection to ONE named device"
dòng 44: device: str = DEFAULT_DEVICE
dòng 63: self._server_id = device          <- định danh adapter LÀ tên thiết bị
dòng 66: self._connection = modbus_registry.connection(device)
```

> **Mô hình hiện tại là "một adapter = MỘT thực thể".** `device=` trong `@poll` chỉ là cách
> nói *"handler này chỉ chạy ở adapter tên X"* (dòng 102-106: group có `device=None` thì theo
> adapter nào chạy nó, group có tên thì chỉ chạy đúng adapter đó).

⚠ Mô hình đó **mâu thuẫn trực tiếp** với chốt 5.7.3: nếu mỗi thực thể một adapter thì
`app.use(ModbusAdapter(target_id="BT-01"))` nằm trong `main.py` - tức **`main.py` biết tên
thực thể**, đúng thứ nguyên tắc *"loại ở code, thực thể ở cấu hình"* cấm.

### 4b.2. ✅ CHỐT: một adapter = một LOẠI, quản N thực thể

| | Trước | Sau |
|---|---|---|
| `target_id` của Modbus/OPC UA | tên **thực thể** (`BT-01`) | tên **LOẠI** (`bang-tai`) |
| Số kết nối một adapter giữ | 1 | **N** - một cho mỗi thực thể trong khối cấu hình |
| Số vòng poll | 1 nhóm | N nhóm, mỗi thực thể một |
| `main.py` biết gì | tên máy có thật | **chỉ biết loại** |

⭐ Chốt này **khớp ngược lại với phần 3** và giải thích vì sao fieldbus dùng
`disjoint_per_process` chứ không phải `unique_per_process`: một adapter quản một **TẬP**
thiết bị, nên thứ phải rời nhau giữa các tiến trình là **tập**, không phải một giá trị đơn.
Hai chốt tìm ra độc lập rồi gặp nhau.

### 4b.3. ✅ CHỐT: handler nhận tham số tên `device`, khớp THEO TÊN

```python
@poll(Conveyor, interval=0.5)
async def on_sample(self, conveyor: Conveyor, device: str) -> None: ...
```

#### ⭐ Vì sao khớp theo tên, và vì sao KHÔNG cần kiểu mới

Phiên định nghĩ ra một kiểu `DeviceRef` để framework khớp theo type hint. **Đo code thì
thấy không cần**: `@subscribe` giải đúng bài toán này từ lâu, và nó khớp **theo TÊN tham
số**:

```python
# adapters/mqtt/routing/_builder.py:158
if param_name == "topic":
```

```python
@subscribe("sensors/+/temperature")
async def on_temp(self, payload: bytes, topic: str) -> None: ...
```

> **Cùng một bài toán** - *handler chạy nhiều lần, mỗi lần cho một nguồn khác nhau, cần biết
> nguồn nào* - **và framework đã có lời giải.** Dùng lại nó, đừng phát minh kiểu mới.

| | |
|---|---|
| Tham số **tuỳ chọn** | Không khai thì không nhận, y hệt `topic` |
| Kiểu `str` | Không cần `DeviceRef` - một kiểu mới cho một chuỗi là chi phí không mua được gì |
| ⚠ Rủi ro va tên | App có tham số tên `device` với ý khác thì nhận nhầm. Chấp nhận - `topic` đã mang đúng rủi ro đó suốt từ 0.5, và **nhất quán đáng giá hơn** |

### 4b.4. ✅ CHỐT: bỏ `device=` khỏi `@poll` và `@on_change`

Tên thực thể nay đến từ **cấu hình**, không từ code. Ba đường lấy nó:

| Đường | Dùng khi |
|---|---|
| Tham số `device` của handler | `@poll` / `@on_change` - framework điền |
| `modbus.devices_of("bang-tai")` | Code chủ động lặp |
| Dữ liệu (người dùng chọn máy trên màn hình) | Đường nghiệp vụ |

⛔ `modbus.read(X, device="BT-01")` viết cứng là buộc code vào một nhà máy cụ thể - **cấm**,
đúng hệ quả 1 của mục 5.7.3.

### 4b.5. Ca một PLC vẫn không phải sửa gì

Viết tắt ở 5.7.3 vẫn áp: dict phẳng có `host` dưới tên loại thì coi như **một thực thể trùng
tên loại**. Cộng với việc tham số `device` là tuỳ chọn, app một PLC chạy nguyên như cũ.

### 4b.6. Việc thi công

| | |
|---|---|
| `ModbusAdapter` / `OpcuaAdapter` | Đổi từ **một kết nối** sang **N kết nối**; `target_id` mang nghĩa **loại** |
| `_decorators.py` | Bỏ tham số `device=` khỏi `poll()` và `on_change()` |
| Lớp khớp tham số handler | Thêm `device` vào danh sách tên quy ước, **cùng chỗ** `topic` được xử lý |
| `devices_of(loai)` | API mới, trả danh sách thực thể của một loại trong tiến trình này |
| Test canh | Một loại hai thực thể -> handler chạy **hai lần**, `device` khác nhau · handler không khai `device` vẫn chạy · dict phẳng vẫn ra một thực thể |

### 4b.7. ⭐ THI CÔNG 2026-08-20: OPC UA dùng chữ `server`, không dùng `device`

Tài liệu này viết 4b bằng ví dụ Modbus, nên nó để hở câu *"OPC UA thì gọi là gì"*.
Thi công phải trả lời, và câu trả lời **không** phải một tên chung:

| | Nói về | Nên là |
|---|---|---|
| `adapter_id` (phần 1) | **framework** | **một tên chung** cho cả sáu adapter |
| `device` / `server` (4b) | **thứ thật ngoài kia** | **chữ của miền đó** |

Modbus có *thiết bị*, OPC UA có *server*. Ép chung một chữ ở đây là dán sai nhãn -
đúng thứ phần 1 đã bác khi từ chối gộp `server_id` với `target_id`. Nên:

| Modbus | OPC UA |
|---|---|
| tham số handler `device` | tham số handler `server` |
| `ModbusClient.devices_of(loại)` | `OpcuaClient.servers_of(loại)` |
| hằng `DEVICE_PARAM` | hằng `SERVER_PARAM` |

⚠ **Một chỗ căng còn để lại, đáng ghi trước khi ai đó phát hiện lại:** sau 4b thì
`target_id` mang nghĩa **LOẠI**, trong khi *target* thật là thực thể. Tên hơi lệch
nghĩa, nhưng đổi nó là mở lại phần 1 - ghi ra đây, **không tự sửa**.

### 4b.8. ⚠ Tên tham số sai là LỖI KHỞI ĐỘNG, không phải bị bỏ qua

Mục 4b.3 chốt *"khớp theo TÊN"* mà không nói tên sai thì sao. Thi công chọn **nổ**:

> Bỏ qua im lặng nghĩa là người viết đang chờ framework truyền một thứ nó không
> biết là gì, và handler sẽ nổ `TypeError` **giữa một chu kỳ đọc** - xa chỗ sai
> thật cả về thời gian lẫn về stack trace.

Cùng khuôn với chốt *"`scaling` bắt buộc khai"* ở phần 3: tham số bị bỏ qua im lặng
là chỗ để người ta tin vào thứ không xảy ra.

---

## 5. Thi công: `SchedulerRunner` thành adapter hạng đơn nhất

Đo 2026-08-18: `SchedulerRunner` **không phải Adapter**, nó khởi động vòng lặp trong
`post_construct`, tức chạy ở **mọi** tiến trình. Không cần quyết gì thêm, nhưng phụ thuộc
phần 3 (phải có hạng *đơn nhất* trước đã).

⭐ Việc này **tạo ra ca "app có adapter nhưng không cái nào mở cổng"** - xem
[mục 5.5](10-da-tien-trinh.md) của tài liệu đa tiến trình, năm
ca của nhánh supervisor.

---

## 6. Liên quan

- [`10-da-tien-trinh.md`](10-da-tien-trinh.md)
  mục 4 (bảng năm điều) · mục 5.5 (mô hình chạy, **năm ca nhánh supervisor**) · mục 5.7
  (mỗi adapter chia tải một kiểu) · mục 9.2 câu E, 9, 11
- [`../kiem-toan/0.7-bao-mat-ke-hoach-va.md`](../kiem-toan/0.7-bao-mat-ke-hoach-va.md) - **F10**,
  trùng với phần 4
- [`lo-trinh-phien-ban.md`](../lo-trinh-phien-ban.md) - 0.8 là bản Alpha cuối
- [Luật 03](../../../../.claude/rules/03-mot-gia-tri-mot-nghia.md) - phát hiện **b** và **d** ở
  1.3 đều là một tên mang hai nghĩa
