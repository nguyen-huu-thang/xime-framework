# Kế hoạch phiên bản 0.7 - "Fieldbus công nghiệp (Modbus TCP + OPC UA)"

> Chốt mốc 2026-06-21. Ban đầu định gộp vào 0.5, sau dời sang **0.7** để 0.5 gọn
> quanh audit + MQTT + file, không phình. 0.7 dành riêng cho hai adapter công
> nghiệp này.
>
> Nguồn gốc: đề xuất của chủ dự án (2026-06-21) - Xime nhắm tới công nghiệp/IIoT
> nên ngoài MQTT cần đọc được PLC/thiết bị nhà máy.

> **Thiết kế đã CHỐT 2026-06-23** (chủ dự án trả lời các câu hỏi mở):
> 1. **Không edge gateway** - Xime giao tiếp **trực tiếp** với PLC/thiết bị ở
>    tầng tiếp xúc. => Hai adapter này CẦN làm (không thể thay bằng MQTT).
> 2. **Modbus: làm CẢ client lẫn server** (Xime giả lập slave).
> 3. **Mô hình: CẢ HAI** - polling theo lịch + đọc theo yêu cầu.
> 4. **OPC UA: hỗ trợ TẤT CẢ mức security** (None / Sign / SignAndEncrypt).
> 5. **Trục chính = Device Model khai báo** (xem mục "Linh hồn 0.7").
> 6. **Phạm vi 0.7 = CẢ Modbus và OPC UA** (không tách OPC UA sang bản sau).
> 7. **Luồng device-driven dùng decorator riêng `@poll`/`@on_change` trong
>    adapter** (adapter tự chạy vòng poll, tái dùng hạ tầng concurrency của MQTT),
>    KHÔNG dựa scheduler starter.

---

## ⚠ CÂU HỎI CẦN HỎI LẠI CHỦ DỰ ÁN TRƯỚC KHI CODE (chưa chốt)

> Chủ dự án (2026-06-23) yêu cầu: KHÔNG tự quyết ba điểm dưới đây. Khi bắt tay code
> 0.7, **hỏi lại chủ dự án trước**, ghi câu trả lời vào doc này rồi mới làm. Đây là
> ghi nhớ có chủ đích, không phải việc tồn đọng bị quên.

1. **Modbus nhiều slave - pool connection theo `host:port` thế nào?**
   Một `ModbusClient` chỉ tới một slave hay quản lý nhiều slave/nhiều host? Cơ chế
   pool/registry connection (giống `mqtt_registry.connection(client_id)`) ra sao,
   key theo `host:port` hay theo tên device?
2. **`ModbusClient.read(device)` - đọc một block tối ưu hay gộp nhiều range rời?**
   Khi một Device Model có các field rải địa chỉ không liền nhau: đọc thành một
   block lớn (đơn giản, có thể đọc thừa) hay gom thành nhiều lệnh đọc range tối ưu
   (phức tạp hơn, ít byte hơn)?
3. **Server (slave) - một datastore chung hay tách theo `unit_id`?**
   Khi Xime giả lập slave phục vụ nhiều unit_id: dùng một datastore chung cho mọi
   unit hay mỗi unit_id một datastore riêng?

---

## Bối cảnh & khác biệt mô hình

Xime nhắm tới **công nghiệp / IIoT** -> cần đọc PLC và thiết bị nhà máy. Hai chuẩn
phổ biến nhất: **Modbus TCP** và **OPC UA**.

**Khác biệt cốt lõi với MQTT (adapter 0.5):** MQTT là pub/sub do thiết bị chủ động
đẩy lên. Modbus/OPC UA thiên về **Xime đóng vai CLIENT/MASTER chủ động đọc** thiết
bị (poll thanh ghi, hoặc subscribe node). Đây là mô hình thứ ba, khác cả RPC lẫn
pub/sub -> thiết kế riêng, KHÔNG ép chung decorator `@subscribe` của MQTT.

---

## Bốn trụ pattern Xime mà 0.7 phải bám (rút từ web/grpc/socket/mqtt)

Soi code thật, mọi adapter/starter Xime đều dựng trên 4 mảnh. 0.7 tái dùng nguyên:

| Mảnh | Tiền lệ trong code | 0.7 tái dùng |
|---|---|---|
| Decorator -> metadata -> scan -> dispatch | `@subscribe`/`@rpc` gắn `_xime_mqtt_info`; `MqttControllerScanner` + `MqttRouteBuilder` | `@poll`/`@on_change`/`@serve`/`@on_write` gắn `_xime_modbus_info` / `_xime_opcua_info` |
| Provider injectable (façade) | `MqttPublisher` ủy thác `MqttConnection` dùng chung theo `client_id` | `ModbusClient` / `OpcuaClient` ủy thác connection dùng chung |
| `configure_*` explicit + registry singleton | `configure_mqtt_controllers()` -> `mqtt_registry` | `configure_modbus_devices()` / `configure_opcua_nodes()` |
| Pydantic config `.resolve()` fail-fast | `MqttConfig.resolve()` thiếu `host` -> nổ lúc startup | `ModbusConfig` / `OpcuaConfig` thiếu endpoint -> nổ |

Chỉ tới đây thì vẫn là "bọc thư viện". Giá trị thật nằm ở mảnh thứ 5.

---

## Linh hồn 0.7: Device Model khai báo (tương đương DTO/Contract của fieldbus)

Điểm đau lớn nhất khi dùng `pymodbus`/`asyncua` thô KHÔNG phải kết nối, mà là
**giải mã thanh ghi**: đọc holding register 40001-40002 rồi tự ghép 2 word thành
`float32`, đoán big-endian hay word-swap, scale `value/10`, map bit. Đây là chỗ
sai nhiều nhất và lặp ở mọi project.

gRPC code-first của Xime đã giải đúng bài này cho proto qua `codefirst/_marshal.py`
+ `_model.py`. **0.7 làm y hệt cho thanh ghi/node.** Một class Device Model là
"single source of truth", dùng được cho CẢ client đọc, client ghi, server expose,
subscribe - giống `core/contract/` dùng chung cho socket lẫn gRPC.

```python
# domain/devices/inverter.py  (là "DTO" - KHÔNG nằm trong package scan DI)
from xime.adapters.modbus import device, Holding, Coil, Input

@device(unit=1)                       # slave / unit id
class Inverter:
    voltage:    float = Holding(40001, type="float32", word_order="big", scale=0.1)
    current:    float = Holding(40003, type="float32")
    run_state:  bool  = Coil(1)
    fault_code: int   = Input(30010, type="uint16")
```

Field descriptor (`Holding`/`Coil`/`Input`/`Discrete`) mang: address, kiểu
(`int16/uint16/int32/uint32/float32/float64/bool/string`), `word_order`/
`byte_order` (override mặc định toàn cục), `scale`/`offset`, `count` (string/array).
Codec (`modbus/_codec.py`) lo encode/decode hai chiều. Đây là tầng "framework làm
nhiều việc".

OPC UA dùng khái niệm tương đương nhưng key là NodeId thay vì address:

```python
from xime.adapters.opcua import node_model, Node

@node_model
class Tank:
    level:    float = Node("ns=2;s=Tank.Level")
    setpoint: float = Node("ns=2;s=Tank.Setpoint")
```

---

## Nhóm 1 - Modbus TCP

Thư viện `pymodbus` (`AsyncModbusTcpClient`, `StartAsyncTcpServer`). Import lười,
extra `xime[modbus]`. Thư mục `xime/adapters/modbus/`.

### 1a. Client - đọc theo yêu cầu (provider injectable)

```python
class TelemetryService:
    def __init__(self, modbus: ModbusClient):     # façade, giống MqttPublisher
        self._modbus = modbus
    async def snapshot(self) -> Inverter:
        return await self._modbus.read(Inverter)              # đọc block + decode
    async def stop(self) -> None:
        await self._modbus.write(Inverter.run_state, False)   # ghi 1 field, encode
```

### 1b. Client - polling (decorator controller, adapter tự chạy vòng lặp)

```python
class InverterMonitor:                # package: configure_modbus_devices() + dependency.scan()
    def __init__(self, alerts: AlertService): ...
    @poll(Inverter, interval=1.0)               # adapter poll mỗi 1s, decode sẵn
    async def on_sample(self, dev: Inverter) -> None: ...
    @on_change(Inverter.fault_code)             # chỉ gọi khi GIÁ TRỊ ĐỔI (framework so sánh)
    async def on_fault(self, code: int) -> None: ...
```

Vòng poll TÁI DÙNG hạ tầng concurrency/backpressure của MQTT adapter (semaphore +
bounded task set + done-callback). KHÔNG dùng scheduler starter (chốt 2026-06-23).
Change-detect: adapter giữ snapshot giá trị trước, so sánh để fire `@on_change`.

### 1c. Server (slave) - Xime giả lập thiết bị

Cùng Device Model, đảo chiều: framework giữ register file (datastore của
`pymodbus`), map field <-> address, gọi handler khi master đọc/ghi.

```python
class PlcEmulator:
    @serve(Inverter)                            # expose Inverter làm slave
    async def provide(self) -> Inverter: ...        # framework hỏi giá trị khi master đọc
    @on_write(Inverter.run_state)               # master ghi coil -> gọi handler
    async def handle_cmd(self, value: bool) -> None: ...
```

### Runtime config (`modbus.*`)

```yaml
modbus:
  host: 10.0.0.5          # client: bắt buộc, thiếu -> fail-fast
  port: 502
  unit_id: 1
  timeout: 3.0
  byte_order: big         # mặc định toàn cục
  word_order: big         # field có thể override
  reconnect_delay: 3.0
  max_concurrency: 16     # cho luồng @poll
  server:                 # chỉ khi bật slave
    listen: 0.0.0.0:5020
```

> Ba câu hỏi mở của nhóm Modbus (pool connection nhiều slave, chiến lược đọc
> block/range, datastore server theo unit_id) đã gom lên mục "⚠ CÂU HỎI CẦN HỎI
> LẠI CHỦ DỰ ÁN TRƯỚC KHI CODE" ở đầu doc - hỏi chủ dự án trước khi làm.

## Nhóm 2 - OPC UA

Thư viện `asyncua` (async thuần). Import lười, extra `xime[opcua]`. Thư mục
`xime/adapters/opcua/` + `_security.py`.

### 2a. Client - đọc + subscribe

```python
class TankService:
    def __init__(self, opcua: OpcuaClient): ...
    async def level(self) -> float:
        return await self._opcua.read("ns=2;s=Tank.Level")
    async def read_model(self) -> Tank:
        return await self._opcua.read_model(Tank)

class TankMonitor:
    @on_node_change("ns=2;s=Tank.Level", deadband=0.5)   # monitored item, framework tạo subscription
    async def changed(self, value: float) -> None: ...
```

`@on_node_change` = OPC UA subscription/monitored item; adapter tạo subscription,
nhận callback, dispatch tới handler (giống `@subscribe` nhưng do client tạo đăng ký).

### 2b. Server - Xime đóng vai OPC UA server

Khai báo node map (`@node_model`), framework dựng namespace + sync giá trị, handler
nhận write.

### 2c. Security - tất cả mức (chốt làm hết)

```yaml
opcua:
  endpoint: opc.tcp://10.0.0.6:4840   # thiếu -> fail-fast
  security: SignAndEncrypt            # None | Sign | SignAndEncrypt
  certificate: /etc/xime/opcua-client.der
  private_key: /etc/xime/opcua-client.pem
  username: svc                       # hoặc anonymous
  password: secret
```

`_security.py` map config -> `asyncua` security policy + load cert/key, fail-fast
khi `Sign`/`SignAndEncrypt` mà thiếu cert.

## Nhóm 3 - Định vị thư mục

Hai adapter ĐỘC LẬP, import lười riêng, KHÔNG trừu tượng hóa chung "fieldbus" sớm
(data model khác nhau quá nhiều - address vs NodeId, register types vs OPC types).
Device Model của mỗi adapter tự định nghĩa, không ép chung base class.

```text
xime/adapters/modbus/
  __init__.py            # export device/Holding/Coil/Input, @poll/@on_change/@serve/@on_write,
                         #   ModbusClient, ModbusAdapter, configure_modbus_devices
  _adapter.py            # lifecycle start/stop, vòng poll (tái dùng pattern mqtt), server slave
  _client.py             # ModbusClient façade (provider injectable)
  _server.py             # slave datastore + map field <-> address
  _decorators.py         # @poll @on_change @serve @on_write -> _xime_modbus_info
  _model.py              # @device + field descriptors
  _codec.py              # encode/decode register <-> giá trị typed (endian/word/scale)
  _config.py             # ModbusConfig.resolve() + modbus_registry
  _runtime.py            # ModbusConnection dùng chung (như MqttConnection)
  routing/_scanner.py _builder.py

xime/adapters/opcua/
  ... tương tự + _security.py (None/Sign/SignAndEncrypt, cert/key)
```

## Nhóm 4 - Test

- Modbus: server giả lập `pymodbus` (`StartAsyncTcpServer` in-process) -> client
  đọc/ghi, assert decode đúng (int16/uint16/int32/float32, big/little, word swap,
  scale). Test `@poll` + `@on_change` bằng datastore thay đổi giá trị.
- Modbus server: dựng slave Xime, một client `pymodbus` ngoài đọc/ghi, assert map.
- OPC UA: `asyncua` server in-process với vài node -> client đọc/subscribe, assert.
  Test security None trước; Sign/SignAndEncrypt cần cert -> guard-skip nếu thiếu
  (giống MQTT/S3 integration test).

## Thứ tự code đề xuất

1. `modbus/_model.py` + `_codec.py` + test codec thuần (không cần network) - nền.
2. `modbus/_config.py` + `_runtime.py` + `_client.py` (on-demand) + test với
   `StartAsyncTcpServer`.
3. `modbus/_adapter.py` vòng `@poll`/`@on_change` + scanner/builder (mượn mqtt).
4. `modbus/_server.py` slave + `@serve`/`@on_write`.
5. `opcua/` lặp lại cấu trúc: model -> client read/subscribe -> server -> security.
6. extras `xime[modbus]`/`xime[opcua]` trong `pyproject.toml`, docs, CHANGELOG,
   bump `0.7.0`.
