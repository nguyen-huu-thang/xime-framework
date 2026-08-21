# Modbus Adapter

[English](../en/modbus.md) | **Tiếng Việt**

[← MQTT Adapter](mqtt.md) · **Modbus Adapter** · [OPC UA Adapter →](opcua.md)

---

Modbus Adapter cho phép XIME nói chuyện **trực tiếp** với PLC, biến tần, đồng hồ đo và thiết bị nhà máy - không cần edge gateway ở giữa. Đây là **mô hình giao tiếp thứ ba** của XIME:

| Mô hình | Adapter | Ai chủ động |
| --- | --- | --- |
| Request/response | web, gRPC, socket, `@rpc` của MQTT | Bên ngoài gọi vào XIME |
| Pub/sub | MQTT `@subscribe` | Thiết bị chủ động đẩy lên |
| **Polling / master** | **modbus** | **XIME chủ động đi đọc thiết bị** |

> **Yêu cầu:** `pip install "xime[modbus]"` (kéo theo `pymodbus>=3.14`).

---

## Vấn đề mà adapter này giải

Modbus **không mang thông tin kiểu**. Mỗi lần đọc chỉ trả về một mảng word 16-bit thô. Muốn có `voltage = 220.5` bạn phải tự làm hết:

1. biết cần đọc hai thanh ghi liền nhau nào,
2. ghép hai word thành bốn byte,
3. đoán đúng thứ tự byte (big/little endian),
4. đoán đúng thứ tự word (nhiều hãng đảo, nhiều hãng không),
5. nhân hệ số scale ghi trong datasheet.

Sai bất kỳ bước nào **không sinh ra lỗi** - nó sinh ra một con số trông rất hợp lý. Đây là nguồn bug số một khi làm việc với PLC, và cũng chính là thứ Device Model của XIME sinh ra để diệt.

---

## Bắt đầu nhanh

### 1. Khai báo Device Model

```python
# domain/devices/inverter.py   (là "DTO" - KHÔNG nằm trong package scan DI)
from xime.adapters.modbus import device, Holding, Input, Coil, Discrete

@device(unit=1)
class Inverter:
    voltage:    float = Holding(modicon=40001, type="float32", scale=0.1)
    current:    float = Holding(2, type="float32")
    setpoint:   int   = Holding(4, type="uint16")
    run_state:  bool  = Coil(0)
    fault_code: int   = Input(9, type="uint16")
    alarm:      bool  = Discrete(3)
```

### 2. Cấu hình thiết bị

```yaml
# resources/application.yml
modbus:
  timeout: 3.0
  word_order: big
  max_gap: 8
  devices:
    inverter_1: { host: 10.0.0.5, port: 502, unit: 1 }
    meter_a:    { host: 10.0.0.6, unit: 3, timeout: 5.0 }
```

### 3. Đọc theo yêu cầu

```python
from xime.adapters.modbus import ModbusClient

class TelemetryService:
    def __init__(self, modbus: ModbusClient) -> None:
        self._modbus = modbus

    async def snapshot(self) -> Inverter:
        return await self._modbus.read(Inverter)

    async def stop(self) -> None:
        await self._modbus.write(Inverter.run_state, False)
```

```python
# config/dependency.py
dependency.register(ModbusClient)
```

### 4. Chạy adapter

```python
# main.py
app = Application()
app.use(WebAdapter()).use(ModbusAdapter("inverter_1"))   # đối số tên `target_id` từ 0.8
app.run()
```

---

## Địa chỉ: hai đường vào tường minh

Datasheet gần như luôn dùng cách đánh số **Modicon** (40001, 30010...), còn giao thức trên dây dùng **offset 0-based**. XIME **không đoán** - hai dạng là hai tham số khác nhau:

```python
Holding(2)              # địa chỉ giao thức, 0-based
Holding(modicon=40003)  # số in trên datasheet -> framework tự trừ, ra 2
```

Lý do tách: nếu một tham số nhận nhập nhèm cả hai, thì trên thiết bị thật sự có hơn 40002 thanh ghi, `Holding(40001)` sẽ đọc **nhầm thanh ghi mà không có lỗi nào báo**.

Nổ ngay lúc định nghĩa class nếu: truyền cả hai, không truyền gì, hoặc prefix Modicon không khớp vùng (`Coil(modicon=40001)`).

| Vùng | Class | Modicon | Function code đọc | Ghi được |
| --- | --- | --- | --- | --- |
| Coil | `Coil` | 1-9999 | 1 | có (5/15) |
| Discrete Input | `Discrete` | 10001-19999 | 2 | không |
| Input Register | `Input` | 30001-39999 | 4 | không |
| Holding Register | `Holding` | 40001-49999 | 3 | có (6/16) |

Bốn vùng là **bốn không gian địa chỉ tách biệt**: holding 0 và coil 0 là hai ô nhớ không liên quan.

---

## Kiểu dữ liệu và biến đổi giá trị

```python
Holding(0, type="float32", word_order="little", scale=0.1, offset=-40)
```

| Tham số | Ý nghĩa |
| --- | --- |
| `type` | `int16`/`uint16`/`int32`/`uint32`/`int64`/`uint64`/`float32`/`float64`/`string`/`bool` |
| `word_order` | thứ tự word cho kiểu nhiều thanh ghi; override mặc định của `@device` |
| `byte_order` | thứ tự byte **trong** mỗi thanh ghi (spec là big; một số thiết bị đảo) |
| `scale` / `offset` | `giá trị = raw * scale + offset`; encode thì làm ngược lại |
| `count` | số thanh ghi cho `string`, số bit cho coil/discrete nhiều bit |

Field số nguyên khi ghi được **làm tròn**, không cắt cụt - nếu cắt cụt thì 220.5 qua `scale=0.1` quay về thành 220.4.

`string` bắt buộc có `count`: Modbus không gửi độ dài nên framework không thể biết chuỗi kết thúc ở đâu.

---

## Cách framework lập kế hoạch đọc

Modbus chỉ có một lệnh: "đọc N địa chỉ liên tiếp từ X". Model có field rải rác phải được dịch thành nhiều lệnh, và cách dịch **ảnh hưởng tới tính đúng đắn**, không chỉ hiệu năng:

- Đọc một block lớn từ địa chỉ nhỏ nhất tới lớn nhất thì đơn giản, **nhưng** chỉ cần một địa chỉ ở giữa không tồn tại trên thiết bị là slave trả `ILLEGAL DATA ADDRESS` và **hỏng cả lần đọc** - dù mọi field bạn khai đều hợp lệ. Lỗi này rất khó chẩn đoán vì model và cấu hình đều trông đúng.
- Nên XIME gom field theo `max_gap`: các field cách nhau không quá `max_gap` thì chung một lệnh, xa hơn thì tách lệnh.

```yaml
modbus:
  max_gap: 8     # 0 = đọc đúng y các địa chỉ đã khai (an toàn nhất, nhiều lệnh nhất)
```

Framework cũng tự chia khi vượt trần giao thức (125 thanh ghi hoặc 2000 bit mỗi lệnh), và **nổ lúc startup** nếu một field đơn lẻ lớn hơn trần đó (không chia được vì phải decode nguyên khối).

Xem kế hoạch thật lúc debug:

```python
from xime.adapters.modbus import plan_reads, describe_plan, require_device_info

print(describe_plan(plan_reads(require_device_info(Inverter), max_gap=8)))
```

---

## Polling: `@poll` và `@on_change`

```python
# api/modbus/inverter_monitor.py
from xime.adapters.modbus import poll, on_change

class InverterMonitor:
    def __init__(self, alerts: AlertService) -> None:
        self._alerts = alerts

    @poll(Inverter, interval=1.0)
    async def on_sample(self, inverter: Inverter) -> None:
        await self._alerts.record(inverter.voltage)

    @on_change(Inverter.fault_code)
    async def on_fault(self, value: int) -> None:
        await self._alerts.raise_fault(value)

    @on_change(Inverter.voltage, deadband=0.5)
    async def on_voltage(self, value: float) -> None:
        await self._alerts.note(value)
```

```python
# config/modbus.py
from xime.adapters.modbus import configure_modbus_devices
configure_modbus_devices("api.modbus")

# config/dependency.py
dependency.scan("api.modbus")
```

Những điều cần biết:

- **Gom nhóm:** adapter chạy một vòng lặp cho mỗi cặp `(model, interval)`. Hai handler cùng model và cùng nhịp **không** gây hai lần đọc.
- **`@on_change` không tự đọc**: nó quan sát giá trị mà vòng poll đã lấy về. Nếu model được poll ở nhiều nhịp, watch bám vào vòng **nhanh nhất**.
- **Lần đọc đầu chỉ là mốc**: `@on_change` không bắn ở chu kỳ đầu tiên. Bắn ở đó nghĩa là mọi handler đều kêu lúc khởi động - đó là nhiễu, không phải tin tức.
- **`deadband` cho giá trị analog**: không có nó thì nhiễu đo ở chữ số cuối làm handler float bắn gần như mỗi chu kỳ. Chỉ báo khi giá trị dịch **hơn** `deadband`.
- **Nhịp không trôi**: adapter trừ thời gian chu kỳ khỏi lần sleep kế tiếp, nên `interval=1.0` vẫn là mỗi giây dù thiết bị trả lời chậm.
- **Lỗi không làm dừng vòng**: một chu kỳ đọc hỏng được log rồi chạy tiếp. Thiết bị nhà máy rớt mạng là chuyện thường; một lần đọc hỏng không được giết luôn việc giám sát của cả ca.
- **Giới hạn đồng thời**: handler chạy trong task có `max_concurrency` (mặc định 16), áp backpressure lên vòng poll khi đầy.

### Biết mình đang xử lý máy nào: tham số `device` (0.8)

Một adapter phục vụ một **loại** thiết bị (`bang-tai`) và giữ **nhiều thực thể** của
loại đó (`BT-01`, `BT-02`), nên handler chạy một lần cho **mỗi thực thể**. Muốn biết
lời gọi này thuộc máy nào thì khai thêm một tham số **tên `device`**:

```python
@poll(Conveyor, interval=1.0)
async def on_sample(self, conveyor: Conveyor, device: str) -> None:
    await self._store.save(device, conveyor.speed)

@on_change(Conveyor.fault_code)
async def on_fault(self, value: int, device: str) -> None:
    await self._alerts.raise_fault(device, value)
```

Khớp theo **tên**, đúng quy ước `topic` của `@subscribe`. Không khai thì handler giữ
nguyên một tham số như cũ; khai một tham số thứ hai mang **tên khác** là **lỗi khởi
động**, không phải một tham số bị bỏ qua im lặng.

Lấy danh sách thực thể bằng `devices_of`:

```python
for dev in modbus.devices_of("bang-tai"):
    trang_thai = await modbus.read(Conveyor, device=dev)
```

⚠ **Tên thực thể không bao giờ là hằng trong code nghiệp vụ.** Viết cứng
`device="BT-01"` là buộc code vào một nhà máy cụ thể; tên đến từ tham số handler, từ
`devices_of(...)`, hoặc từ dữ liệu người dùng chọn.

⏭ **0.8 mới khai chữ ký**; phần dựng nhiều kết nối cho một loại làm ở **0.8.1**. Hôm
nay một adapter giữ đúng một thực thể trùng tên loại, nên code viết theo vòng lặp trên
chạy đúng ở cả hai bản và không phải sửa gì.

⛔ **`@poll(..., device=...)` và `@on_change(..., device=...)` đã bị bỏ ở 0.8.** Việc
chọn máy nào không còn nằm ở decorator - handler chạy cho mọi thực thể của loại nó.

---

## Slave mode: XIME giả lập thiết bị

```python
# api/modbus/plc_emulator.py
from xime.adapters.modbus import serve, on_write

class PlcEmulator:
    @serve(Inverter)
    async def provide(self) -> Inverter:
        return Inverter(voltage=self._voltage, run_state=self._running)

    @on_write(Inverter.run_state)
    async def handle_command(self, value: bool) -> None:
        self._running = value
```

```yaml
modbus:
  server:
    host: 0.0.0.0
    port: 5020
```

```python
from xime.adapters.modbus import ModbusServerAdapter, configure_modbus_server

configure_modbus_server("api.modbus")
app.use(ModbusServerAdapter())
```

Hai cơ chế khác nhau, có lý do:

- **Công bố giá trị là đẩy theo nhịp.** Framework gọi `@serve` mỗi `refresh` giây rồi lưu kết quả. Nếu hỏi handler lúc master đọc thì code nghiệp vụ chạy ngay trong đường phản hồi giao thức - handler chậm sẽ làm nghẽn.
- **Nhận lệnh ghi là hook.** Không có thời điểm nào khác để biết master vừa ghi.

Các điểm khác:

- **Mỗi `@device(unit=N)` là một thiết bị riêng.** Một tiến trình XIME đóng vai nhiều thiết bị sau một cổng, giống gateway RTU.
- **Địa chỉ ngoài vùng khai báo cố ý để trống** - master đọc sẽ nhận `ILLEGAL DATA ADDRESS` thay vì một số 0 trông có vẻ hợp lệ.
- `refresh_once()` là public: đẩy cập nhật ngay khi có thay đổi quan trọng thay vì chờ nhịp sau.

---

## Xử lý lỗi

Ba nhóm lỗi tách riêng vì cách phản ứng khác nhau:

| Exception | Nghĩa | Nên làm gì |
| --- | --- | --- |
| `ModbusConnectionError` | không tới được thiết bị (dây, switch, firewall, thiết bị đang khởi động lại) | thử lại sau thường có tác dụng |
| `ModbusDeviceError` | thiết bị đã trả lời, và đó là lời từ chối | thử lại **cùng** yêu cầu vẫn hỏng - sai yêu cầu hoặc sai model |
| `ModbusCodecError` | byte về đủ nhưng model không hiểu được | luôn là lỗi code/model |

`ModbusDeviceError` giữ `code` thô và diễn giải nó thành lời trong message, vì bản thân con số không nói lên điều gì trong log:

```text
Modbus exception 2: ILLEGAL DATA ADDRESS - the address (or part of the range)
does not exist on this device (reading holding 5000+1)
```

---

## Cấu hình đầy đủ

```yaml
modbus:
  # Mặc định dùng chung cho mọi device; từng device override được.
  timeout: 3.0
  byte_order: big
  word_order: big
  reconnect_delay: 3.0
  max_concurrency: 16
  max_gap: 8
  devices:
    inverter_1:
      host: 10.0.0.5
      port: 502
      unit: 1
    meter_a:
      host: 10.0.0.6
      port: 502
      unit: 3
      timeout: 5.0
  server:              # chỉ khi chạy ModbusServerAdapter
    host: 0.0.0.0
    port: 5020
```

Thiết bị được đánh địa chỉ bằng **tên logic**, đúng khuôn `client_id` của MQTT và `server_id` của gRPC/web. Đổi dây trong nhà máy chỉ phải sửa YAML, không sửa code.

---

## Cạm bẫy

- **`app.use(ModbusAdapter(...))` là bắt buộc**, kể cả khi chỉ đọc theo yêu cầu - adapter là bên sở hữu kết nối. Không đăng ký adapter thì `ModbusClient` báo lỗi ngay chứ không treo.
- **`unit` trong `@device` là mặc định của model.** Ba biến tần giống hệt ở unit 1, 2, 3 thì dùng chung model và truyền `unit=` lúc gọi `read`/`write`, đừng kế thừa model ba lần.
- **Trùng địa chỉ trong cùng vùng bị từ chối lúc định nghĩa class** - gần như luôn là lỗi copy-paste, để im thì hai thuộc tính luôn ra cùng giá trị.
- **`pymodbus` dưới 3.14 không chạy được**: `pymodbus.payload.BinaryPayloadDecoder` đã bị xóa và tham số slave đổi tên thành `device_id`.

---

[← MQTT Adapter](mqtt.md) · **Modbus Adapter** · [OPC UA Adapter →](opcua.md)
