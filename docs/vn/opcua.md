# OPC UA Adapter

[English](../en/opcua.md) | **Tiếng Việt**

[← Modbus Adapter](modbus.md) · **OPC UA Adapter** · [File Storage →](file-storage.md)

---

OPC UA Adapter cho phép XIME làm **client** (đọc, ghi, subscribe) và **server** (công bố node cho hệ thống khác) của chuẩn công nghiệp hiện đại nhất.

So với Modbus, OPC UA đã mang sẵn kiểu dữ liệu, tên và **subscription thật**. Nên adapter này mỏng hơn ở tầng dữ liệu (không có gì để giải mã) và **không polling** - server chủ động đẩy khi giá trị đổi.

> **Yêu cầu:** `pip install "xime[opcua]"` (kéo theo `asyncua>=2.0`).

---

## Bắt đầu nhanh

### 1. Khai báo Node Model

```python
# domain/nodes/tank.py   (là "DTO" - KHÔNG nằm trong package scan DI)
from xime.adapters.opcua import node_model, Node

@node_model
class Tank:
    level:    float = Node("ns=2;s=Tank.Level")
    setpoint: float = Node("ns=2;s=Tank.Setpoint")
    alarm:    bool  = Node("ns=2;s=Tank.Alarm", writable=False)
```

Model ở đây **không phải để giải mã** (OPC UA đã mang kiểu) mà để **đặt tên** cho NodeId - biến `client.get_node("ns=2;s=Tank.Level")` rải khắp code thành `Tank.level` khai một chỗ.

### 2. Cấu hình

```yaml
# resources/application.yml
opcua:
  endpoint: opc.tcp://10.0.0.6:4840
  security: SignAndEncrypt
  certificate: /etc/xime/opcua-client.der
  private_key: /etc/xime/opcua-client.pem
  application_uri: urn:my-plant:xime:client  # khớp SAN URI trong cert
  username: svc
  password: secret
```

### 3. Đọc và ghi

```python
from xime.adapters.opcua import OpcuaClient

class TankService:
    def __init__(self, opcua: OpcuaClient) -> None:
        self._opcua = opcua

    async def level(self) -> float:
        return await self._opcua.read("ns=2;s=Tank.Level")

    async def snapshot(self) -> Tank:
        return await self._opcua.read_model(Tank)      # MỘT request cho mọi node

    async def set_target(self, value: float) -> None:
        await self._opcua.write(Tank.setpoint, value)
```

```python
# config/dependency.py
dependency.register(OpcuaClient)

# main.py
app.use(OpcuaAdapter())
```

`read_model` gộp mọi node vào **một** request. Điều này quan trọng hơn vẻ ngoài của nó: OPC UA round trip có độ trễ thật, đọc lẻ mười node là nhân độ trễ lên mười lần mà chẳng được gì.

---

## Subscription: `@on_node_change`

```python
# api/opcua/tank_monitor.py
from xime.adapters.opcua import on_node_change

class TankMonitor:
    def __init__(self, alerts: AlertService) -> None:
        self._alerts = alerts

    @on_node_change(Tank.level, deadband=0.5)
    async def level_changed(self, value: float) -> None:
        await self._alerts.record(value)

    @on_node_change(Tank.alarm, initial=True)
    async def alarm_changed(self, value: bool) -> None:
        await self._alerts.set_alarm(value)
```

```python
# config/opcua.py
from xime.adapters.opcua import configure_opcua_nodes
configure_opcua_nodes("api.opcua")

# config/dependency.py
dependency.scan("api.opcua")
```

Những điều cần biết:

- **Không có `interval`.** Server đẩy khi giá trị đổi; `opcua.subscription_period` (mặc định 200ms) chỉ là nhịp mà server gom thông báo.
- **Giá trị đầu tiên chỉ là mốc.** OPC UA gửi giá trị hiện tại ngay khi bạn subscribe. Mặc định XIME **không** coi đó là thay đổi - giống hệt quy tắc của `@on_change` bên Modbus, để handler không kêu ở mọi lần khởi động. Đặt `initial=True` khi handler thật sự muốn biết trạng thái lúc chạy lên.
- **`deadband`** hoạt động y như Modbus: chỉ báo khi giá trị dịch **hơn** deadband.
- **Handler chạy trong task riêng.** `asyncua` giao thông báo qua callback **đồng bộ**; await thẳng trong đó sẽ chặn vòng nhận của thư viện và làm đứng mọi subscription khác.
- **Một handler hỏng không làm dừng subscription.**

### Biết mình đang xử lý server nào: tham số `server` (0.8)

Bản đối xứng của tham số `device` bên Modbus - đọc
[modbus.md](modbus.md#biết-mình-đang-xử-lý-máy-nào-tham-số-device-08) để hiểu vì sao
tách **loại** khỏi **thực thể**. Ở đây từ vựng là `server` vì đó là chữ của miền OPC
UA:

```python
@on_node_change(Tank.level, deadband=0.5)
async def on_level(self, value: float, server: str) -> None:
    await self._store.save(server, value)
```

```python
for srv in opcua.servers_of("tram-bom"):
    tank = await opcua.read_model(Tank, server=srv)
```

Khớp theo **tên**; tham số thứ hai mang tên khác là **lỗi khởi động**.

⏭ **0.8 mới khai chữ ký**, phần dựng nhiều kết nối làm ở **0.8.1**.
⛔ **`@on_node_change(..., server=...)` đã bị bỏ ở 0.8** - handler chạy cho mọi thực
thể của loại nó.

---

## Bảo mật: đủ ba mức

```yaml
opcua:
  security: SignAndEncrypt     # None | Sign | SignAndEncrypt
  certificate: /etc/xime/opcua-client.der
  private_key: /etc/xime/opcua-client.pem
  application_uri: urn:my-plant:xime:client   # phải khớp SAN URI trong cert
```

| Mức | Nghĩa | Dùng khi |
| --- | --- | --- |
| `None` | không ký, không mã hóa | mạng máy móc cô lập, **không bao giờ** trên mạng định tuyến được |
| `Sign` | có ký: phát hiện được sửa đổi, nhưng nội dung vẫn ở dạng rõ | cần toàn vẹn, không cần bí mật |
| `SignAndEncrypt` | ký và mã hóa | mặc định nên chọn ngoài mạng cô lập |

`Sign` và `SignAndEncrypt` đều cần cert + private key. Thiếu một trong hai thì **nổ lúc startup**, không âm thầm tụt xuống kết nối không bảo vệ - tụt xuống là kết cục tệ nhất cho một tuỳ chọn sinh ra để bảo vệ.

Chính sách cụ thể dùng `Basic256Sha256`. Server đặt ở mức `Sign` vẫn chấp nhận client mang `SignAndEncrypt`: từ chối mức bảo vệ **mạnh hơn** thì vô lý.

### `application_uri` - chỗ hay vấp nhất khi bật bảo mật

Khi bật `Sign` hoặc `SignAndEncrypt`, server đối chiếu URI mà client khai lúc mở session với **URI nằm trong SubjectAltName của cert client**. Lệch nhau là bị từ chối với `BadCertificateUriInvalid`, và thông báo đó không hề nói ra rằng vấn đề nằm ở URI.

Thư viện bên dưới để mặc định URI của chính nó (`urn:example.org:FreeOpcUa:opcua-asyncio`) và **không tự đọc URI từ cert**, nên nếu bạn dùng cert do mình sinh ra thì gần như chắc chắn phải khai:

```yaml
opcua:
  application_uri: urn:my-plant:xime:client   # đúng bằng URI khi sinh cert

  server:
    application_uri: urn:my-plant:xime:server
```

Bỏ trống thì giữ nguyên mặc định của thư viện - chỉ dùng được khi cert cũng mang đúng URI đó, hoặc khi `security: None`.

---

## Server mode: XIME công bố node

```python
# api/opcua/tank_emulator.py
from xime.adapters.opcua import serve_nodes, on_node_write

class TankEmulator:
    @serve_nodes(Tank)
    async def provide(self) -> Tank:
        return Tank(level=self._level)

    @on_node_write(Tank.setpoint)
    async def setpoint_written(self, value: float) -> None:
        self._setpoint = value
```

```yaml
opcua:
  server:
    endpoint: opc.tcp://0.0.0.0:4840/xime
    name: Xime OPC UA Server
    security: None
```

```python
from xime.adapters.opcua import OpcuaServerAdapter, configure_opcua_server

configure_opcua_server("api.opcua")
app.use(OpcuaServerAdapter())
```

Cùng cách chia như server Modbus: **giá trị đẩy theo nhịp**, **lệnh ghi tới qua callback**.

Một quy tắc quan trọng: **node có `@on_node_write` thì CLIENT làm chủ giá trị**, vòng refresh không ghi đè nó. Nếu ghi đè thì framework sẽ đá nhau với người vừa đặt giá trị, và mọi thông báo ghi đều trở nên mơ hồ.

NodeId lấy **nguyên văn** từ model, nên một client dùng chung class model sẽ trỏ đúng các node server này công bố.

> **`namespace` và chỉ số `ns=` trong NodeId là hai thứ RỜI NHAU.** `@node_model(namespace="http://...")` khiến server đăng ký URI đó vào bảng namespace, nhưng node vẫn được tạo tại đúng chỉ số `ns=` ghi trong NodeId. Hai thứ có thể lệch nhau mà không ai báo. Nếu bạn cần node nằm đúng namespace đã đăng ký thì phải tự viết chỉ số tương ứng vào NodeId.

**Kiểu của node phải xác định được lúc khởi động.** Biến OPC UA lấy kiểu dữ liệu từ giá trị lúc tạo và về sau **không nhận giá trị khác kiểu**. XIME lấy kiểu theo thứ tự: `default=` tường minh trước, sau đó tới annotation trong model (`running: bool = Node(...)`). Không có cái nào thì **nổ lúc startup** kèm tên node - chứ không tạo bừa kiểu Double rồi để lần đẩy đầu tiên chết lặng lẽ với `BadTypeMismatch`.

Kiểu nhận biết được: `bool`, `int`, `float`, `str`, `bytes`. Kiểu khác thì khai `default=<giá trị khởi tạo>`.

---

## Xử lý lỗi

| Exception | Nghĩa |
| --- | --- |
| `OpcuaConnectionError` | server không tới được, hoặc session rớt - thử lại có thể được |
| `OpcuaNodeError` | server đã trả lời và từ chối: NodeId lạ, attribute sai, node không đọc/ghi được |

> **Chi tiết đáng biết:** XIME đọc bằng `read_attributes()` chứ **không** dùng `read_values()` của `asyncua`. Hàm sau vứt bỏ StatusCode của từng node, nên gõ sai một NodeId sẽ trả về `None` **im lặng** - trông y hệt một node chưa có giá trị. Kiểm StatusCode biến nó thành lỗi có nêu tên node.

NodeId cũng được kiểm dạng ngay lúc khai báo class: `Node("Tank.Level")` (thiếu `ns=`/`s=`) nổ tại chỗ chứ không đợi `BadNodeId` lúc 3 giờ sáng.

---

## Cấu hình đầy đủ

```yaml
opcua:
  endpoint: opc.tcp://10.0.0.6:4840
  security: SignAndEncrypt
  certificate: /etc/xime/opcua-client.der
  private_key: /etc/xime/opcua-client.pem
  username: svc
  password: secret
  timeout: 4.0
  reconnect_delay: 3.0
  max_concurrency: 16
  subscription_period: 200        # ms
  servers:                        # chỉ khi nói chuyện với nhiều server
    plant_b:
      endpoint: opc.tcp://10.0.0.7:4840
      security: None
  server:                         # chỉ khi chạy OpcuaServerAdapter
    endpoint: opc.tcp://0.0.0.0:4840/xime
    name: Xime OPC UA Server
    security: None
```

App một server viết thẳng dưới `opcua:`; nhiều server thì lồng trong `opcua.servers.<tên>` rồi `app.use(OpcuaAdapter("plant_b"))`. ⚠ Đối số đó tên `target_id` từ 0.8 (trước là `server`).

---

## So sánh nhanh với Modbus

| | Modbus | OPC UA |
| --- | --- | --- |
| Kiểu dữ liệu | không có - framework phải giải mã | có sẵn trong giao thức |
| Địa chỉ | số nguyên theo vùng | NodeId chuỗi |
| Phát hiện thay đổi | XIME poll rồi so sánh | server đẩy (subscription) |
| Bảo mật | không có trong giao thức | None / Sign / SignAndEncrypt |
| Thiết bị hỗ trợ | gần như mọi thứ, kể cả rất cũ | thiết bị và SCADA đời mới |

Cả hai adapter độc lập hoàn toàn, import lười riêng. XIME **không** trừu tượng hóa chúng thành một "fieldbus" chung, vì mô hình dữ liệu khác nhau quá xa.

---

[← Modbus Adapter](modbus.md) · **OPC UA Adapter** · [File Storage →](file-storage.md)
