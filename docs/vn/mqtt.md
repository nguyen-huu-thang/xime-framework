# MQTT Adapter

[English](../en/mqtt.md) | **Tiếng Việt**

[← Socket Adapter](socket-adapter.md) · **MQTT Adapter** · [Modbus Adapter →](modbus.md)

---

MQTT Adapter bổ sung transport **message-driven** cho XIME, phục vụ thiết bị IoT / embedded. Khác các adapter HTTP, gRPC, Socket (request/response), MQTT là **publish/subscribe**: adapter subscribe các topic filter mà controller khai báo rồi dispatch từng message đến. Trên nền pub/sub, adapter còn hỗ trợ **RPC over MQTT v5** (request/reply qua `ResponseTopic` + `CorrelationData`).

```text
Thiết bị / cảm biến ──publish──►  MQTT Broker  ──deliver──►  XIME (@subscribe / @rpc)
XIME (MqttPublisher) ──────────► MQTT Broker  ──────────►  Thiết bị
```

> **Yêu cầu:** broker MQTT **v5** (vd Mosquitto, EMQX, HiveMQ). Cài extra trước: `pip install "xime[mqtt]"` (kéo theo `aiomqtt`). MQTT v5 là bắt buộc cho RPC (`ResponseTopic` / `CorrelationData`) và cho định tuyến bằng Subscription Identifier mô tả bên dưới.

---

## Khi nào dùng

| Dùng MQTT | Dùng gRPC / HTTP / Socket |
| --- | --- |
| Thiết bị IoT / embedded, telemetry | RPC giữa các service |
| Fan-out pub/sub, nhiều publisher | Request/response điểm-điểm |
| Kết nối chập chờn, gián đoạn | Mạng nội bộ ổn định |
| Thiết bị nhẹ sau broker | Client trình duyệt / API public |

---

## Bắt đầu nhanh

### 1. Viết controller

Controller là class thường; `@subscribe` đánh dấu handler fire-and-forget, `@rpc` đánh dấu handler request/reply.

```python
# api/mqtt/sensor_controller.py
from pydantic import BaseModel
from xime.adapters.mqtt import subscribe, rpc

class CalibrateRequest(BaseModel):
    sensor_id: str
    offset: float

class CalibrateResponse(BaseModel):
    ok: bool

class SensorController:
    def __init__(self, ingest: IngestService) -> None:
        self._ingest = ingest

    @subscribe("sensors/+/temperature", qos=1)
    async def on_temperature(self, payload: bytes, topic: str) -> None:
        await self._ingest.record(topic, payload)

    @rpc("sensors/calibrate")
    async def calibrate(self, request: CalibrateRequest) -> CalibrateResponse:
        return await self._ingest.calibrate(request)
```

### 2. Đăng ký package

```python
# config/mqtt.py
from xime.adapters.mqtt import configure_mqtt_controllers

configure_mqtt_controllers("api.mqtt")
```

Nhớ thêm `api.mqtt` vào `dependency.scan(...)` trong `config/dependency.py` để DI container tạo instance controller.

### 3. Thêm adapter (và publisher nếu cần publish)

```python
# main.py
from xime import Application
from xime.adapters.mqtt import MqttAdapter

app = Application()
app.use(MqttAdapter())     # client_id "default"; đọc block mqtt: trong application.yml
app.run()
```

```python
# config/dependency.py — chỉ khi business code cần publish
from xime.adapters.mqtt import MqttPublisher

dependency.register(MqttPublisher)
```

---

## Các loại handler

### `@subscribe` — fire-and-forget (pub/sub)

Handler nhận message **thô**; framework KHÔNG tự deserialize payload (nhất quán với `StorageService` / `CacheService`: cấp cơ chế, không áp policy). Chỉ khai báo tham số bạn cần - khớp **theo tên**, tất cả tùy chọn:

| Tham số | Kiểu | Giá trị |
| --- | --- | --- |
| `payload` | `bytes` | body thô của message |
| `topic` | `str` | topic cụ thể message đến |
| `message` | `Any` | object message gốc của `aiomqtt` |

```python
@subscribe("alerts/#", qos=1)
async def on_alert(self, payload: bytes, topic: str) -> None:
    ...
```

### `@rpc` — request/reply over MQTT v5

Handler nhận một Pydantic **request** model và trả về một Pydantic **response** model. Adapter decode payload request là JSON, gọi handler, rồi publish response (JSON) ra `ResponseTopic` của request kèm đúng `CorrelationData`. Nếu khai báo thêm tham số `topic: str` thì cũng được inject.

```python
@rpc("svc/echo")
async def echo(self, request: EchoRequest) -> EchoResponse:
    return EchoResponse(text=request.text.upper())
```

Bên gọi publish request kèm property `ResponseTopic` + `CorrelationData` (MQTT v5) và subscribe topic reply đó. Không có `ResponseTopic` thì handler vẫn chạy nhưng không gửi reply.

### ⚠ Reply topic do BÊN GỌI đặt, nhưng TA là người publish

Đây là đúng chuẩn MQTT v5, và nó có một hệ quả cần biết: adapter publish reply bằng **credential broker của chính dịch vụ này**, tới topic **bên gọi chỉ định**. Trên broker có phân quyền theo client (ACL), bên gọi vì vậy chạm được tới topic mà ACL của **nó** cấm - nó mượn quyền của ta. Bên gọi cũng điều khiển hoàn toàn `CorrelationData`, và chuỗi bytes đó được chép nguyên xi vào reply.

Khai `mqtt.rpc.reply_topics` để nói ra nơi reply *được phép* rơi vào:

```yaml
mqtt:
  host: broker.local
  rpc:
    reply_topics:
      - nhamay/reply/#
      - devices/+/reply
```

Chúng là **topic filter MQTT** (giống `@subscribe`), không phải tiền tố chuỗi - nên `nhamay/reply/#` khớp mọi cấp bên dưới, còn `nhamay/reply/` thì không khớp gì cả.

Hành vi (chốt 2026-08-18): **cảnh báo, không chặn.**

| Cấu hình | Điều gì xảy ra |
|---|---|
| Không khai `reply_topics` | Giữ nguyên hành vi cũ. **Một** dòng WARNING lúc khởi động, chỉ khi client này thực sự có `@rpc` |
| Có khai, reply khớp | Im lặng |
| Có khai, reply **không** khớp | Reply **vẫn được gửi**, kèm một dòng WARNING nêu tên topic |

Cảnh báo theo từng topic được **khử trùng lặp và chặn trần** (64 topic khác nhau), để bên gọi không biến một cảnh báo thành lũ log bằng cách đổi topic mỗi lần. Filter sai cú pháp thì **nổ lúc khởi động**: một filter không bao giờ khớp sẽ biến mọi reply thành cảnh báo, mà cảnh báo kêu oan là cảnh báo sẽ bị tắt.

⚠ Đây là lớp phòng thủ chiều sâu, **không thay thế ACL của broker**. Chốt chặn thật nằm ở broker.

Validate lúc startup (fail-fast): handler phải `async def`; topic filter hợp lệ; `qos` là 0/1/2; request/response của `@rpc` phải là `BaseModel`; không khai cùng một filter chính xác hai lần (xem *Filter chồng lấn* bên dưới).

---

## Publish

Inject `MqttPublisher` rồi gọi `publish`:

```python
from xime.adapters.mqtt import MqttPublisher

class AlertService:
    def __init__(self, publisher: MqttPublisher) -> None:
        self._publisher = publisher

    async def raise_alert(self) -> None:
        await self._publisher.publish("alerts/fire", b"1", qos=1, retain=True)
```

Publisher không giữ kết nối riêng - nó ủy thác cho client sống mà `MqttAdapter` sở hữu. Publish trước khi adapter kết nối sẽ **chờ** tới khi kết nối (hoặc hết `timeout` tùy chọn). Framework không áp định dạng payload: truyền `bytes` thô (hoặc `str`); tự encode JSON/protobuf.

> **Publisher bám vào client_id `"default"`.** Nếu chạy adapter với id khác (`MqttAdapter("sensors")`) mà inject `MqttPublisher` thường, publish sẽ raise `RuntimeError` rõ ràng thay vì treo vô hạn. Chạy adapter với id mặc định để publisher hoạt động.

---

## Cấu hình — `application.yml`

```yaml
mqtt:
  host: broker.local        # bắt buộc - thiếu là fail-fast lúc startup
  port: 1883
  username: svc             # tùy chọn
  password: secret          # tùy chọn
  client_id: data-service   # tùy chọn - mặc định lấy id của adapter
  keepalive: 60
  default_qos: 0
  max_concurrency: 16       # số handler xử lý đồng thời (xem Thứ tự)
  reconnect_delay: 3.0      # giây giữa các lần reconnect
  tls:                      # tùy chọn
    ca_certs: /etc/ssl/ca.pem
    certfile: /etc/ssl/client.pem
    keyfile:  /etc/ssl/client.key
  lwt:                      # tùy chọn - Last Will & Testament
    topic: status/data-service
    payload: offline
    qos: 1
    retain: true
```

---

## Thứ tự message & đồng thời

Mỗi message được dispatch trong một task giới hạn đồng thời. Với `max_concurrency > 1`, message được xử lý **đồng thời** nên **không** đảm bảo thứ tự per-topic. Đặt `max_concurrency: 1` để xử lý tuần tự đúng thứ tự (throughput thấp hơn). Khi đầy giới hạn, vòng lặp nhận message sẽ backpressure.

---

## Filter chồng lấn & Subscription Identifier

Adapter gán cho mỗi route một **MQTT v5 Subscription Identifier** duy nhất và subscribe kèm id đó; mỗi lần giao, broker báo subscription nào khớp nên dispatcher route đúng (các) handler. Nhờ vậy filter **chồng lấn** (vd `sensors/#` và `sensors/+/temp`) mỗi cái chỉ kích một lần - không double-dispatch.

Vì subscribe lại **cùng một filter chính xác** khiến broker *thay thế* subscription cũ (chỉ id cuối sống), hai handler trên một filter **trùng khít** bị từ chối lúc startup. Hãy dùng filter phân biệt/chồng lấn - dispatcher fan-out tới mọi route khớp - hoặc gộp handler.

Wildcard ở cấp đầu (`#` / `+`) không khớp topic hệ thống của broker (`$SYS/...`), theo spec MQTT.

---

## Khả năng phục hồi

Khi mất kết nối, adapter tự reconnect và **re-subscribe** toàn bộ topic (chu kỳ = `reconnect_delay`). Task handler đang chạy bị hủy lúc tắt; kết nối được đóng sạch.

---

## Error Mapping (RPC)

Map exception nghiệp vụ sang mã lỗi trả về bên gọi trên reply topic:

```python
# config/mqtt.py
from xime.adapters.mqtt import configure_mqtt_error_mappings

configure_mqtt_error_mappings({
    NotFoundException:   "NOT_FOUND",
    ValidationException: "INVALID_ARGUMENT",
})
```

Khi RPC lỗi, adapter publish `{"error": {"code": ..., "message": ...}}` ra `ResponseTopic`. Lỗi chưa map thành `INTERNAL` với message chung, không lộ chi tiết nội bộ - giống chính sách lỗi của gRPC / Socket. Handler lỗi được log và không bao giờ làm dừng vòng dispatch.

---

## Cài đặt

```bash
pip install "xime[mqtt]"   # thêm aiomqtt (kéo theo paho-mqtt)
```

---

[← Socket Adapter](socket-adapter.md) · **MQTT Adapter** · [Modbus Adapter →](modbus.md)
