# Kế hoạch phiên bản 0.7 - "Fieldbus công nghiệp (Modbus TCP + OPC UA)"

> Chốt mốc 2026-06-21. Ban đầu định gộp vào 0.5, sau dời sang **0.7** để 0.5 gọn
> quanh audit + MQTT + file, không phình. 0.7 dành riêng cho hai adapter công
> nghiệp này.
>
> Nguồn gốc: đề xuất của chủ dự án (2026-06-21) - Xime nhắm tới công nghiệp/IIoT
> nên ngoài MQTT cần đọc được PLC/thiết bị nhà máy.
>
> Lưu ý lịch: cụm 0.6/0.8 đang dành cho thay `dependency-injector` + dynamic
> interface binding (xem `wishlist-tinh-nang.md`). 0.7 chèn fieldbus vào giữa.
> Thứ tự thực tế có thể đổi khi tới - đây chỉ là mốc đã ghi nhận.

---

## Bối cảnh & khác biệt mô hình

Xime nhắm tới **công nghiệp / IIoT** -> cần đọc PLC và thiết bị nhà máy. Hai chuẩn
phổ biến nhất: **Modbus TCP** và **OPC UA**.

**Khác biệt cốt lõi với MQTT (adapter 0.5):** MQTT là pub/sub do thiết bị chủ động
đẩy lên. Modbus/OPC UA thiên về **Xime đóng vai CLIENT/MASTER chủ động đọc** thiết
bị (poll thanh ghi, hoặc subscribe node). Đây là mô hình thứ ba, khác cả RPC lẫn
pub/sub -> thiết kế riêng, KHÔNG ép chung decorator `@subscribe` của MQTT.

**Cảnh báo phạm vi:** đây là hai mảng lớn. Đề xuất làm **Modbus TCP trước** (đơn
giản hơn), OPC UA cân nhắc tách tiếp nếu ngân sách hết. Cần chốt khi bắt tay.

---

## Nhóm 1 - Modbus TCP

- Thư viện: `pymodbus` (có async client `AsyncModbusTcpClient`). Import lười,
  extra `xime[modbus]`.
- Vai trò: Xime là **master/client**, kết nối tới slave (PLC/cảm biến) qua TCP,
  đọc/ghi thanh ghi (coils, discrete inputs, holding/input registers).
- Mô hình hoạt động (câu hỏi mở - chọn một hoặc nhiều):
  - **Polling theo lịch:** đọc thanh ghi định kỳ -> tích hợp `scheduler` starter
    đã có (job interval gọi đọc Modbus, đẩy kết quả qua event bus / publish MQTT).
  - **Đọc theo yêu cầu:** cấp `ModbusClient` (singleton DI) cho service tự gọi
    `await client.read_holding_registers(...)` khi cần.
- Đề xuất phạm vi: cấp **client provider** (vòng đời connect/`pre_destroy` đóng) +
  helper map thanh ghi -> giá trị (kiểu dữ liệu Modbus thô: int16/uint16/float32
  big/little-endian, word order). Việc poll định kỳ để app tự ghép với `scheduler`.
- Runtime config (`modbus.*`): `host`, `port` (mặc định 502), `unit_id`/slave id,
  `timeout`, retry. Thiếu `host` -> fail-fast.
- Câu hỏi mở: có cần adapter Modbus **server** (Xime giả lập slave) không, hay chỉ
  client? Nhiều slave/nhiều thiết bị quản lý thế nào (pool connection theo host)?
  Decode kiểu dữ liệu (endian, word swap) framework lo tới đâu?

## Nhóm 2 - OPC UA

- Thư viện: `asyncua` (async thuần). Import lười, extra `xime[opcua]`.
- Vai trò: Xime là **client** kết nối tới OPC UA server (trên PLC/SCADA), đọc node
  hoặc **subscribe** thay đổi giá trị (OPC UA có cơ chế subscription/monitored item
  - gần pub/sub nhưng do client tạo đăng ký).
- Đề xuất phạm vi: client provider (connect/`pre_destroy`) + hai kiểu dùng:
  - đọc node theo yêu cầu (`await client.get_node(nodeid).read_value()`),
  - subscribe node -> callback dispatch tới handler (cân nhắc decorator
    `@on_node_change(nodeid)` tương tự `@subscribe`).
- Bảo mật: OPC UA có security policy + chứng chỉ riêng (Sign/SignAndEncrypt) -
  phức tạp hơn TLS thường. Câu hỏi mở: hỗ trợ tới mức nào (None/Sign/
  SignAndEncrypt), quản lý cert client ra sao.
- Runtime config (`opcua.*`): `endpoint` URL, security policy, cert/key path,
  `username`/`password` hoặc anonymous.

## Nhóm 3 - Định vị thư mục

- Đề xuất gom họ industrial: `xime/adapters/modbus/`, `xime/adapters/opcua/`
  (mỗi cái một adapter độc lập, import lười riêng). Chưa cần trừu tượng hóa chung
  "fieldbus" sớm - hai giao thức này khác nhau nhiều về data model.

## Nhóm 4 - Test

- Modbus: dùng server giả lập của `pymodbus` (`StartAsyncTcpServer` trong test)
  hoặc mock client -> assert đọc/ghi đúng địa chỉ + decode kiểu dữ liệu.
- OPC UA: `asyncua` có server in-process -> dựng server test với vài node, client
  đọc/subscribe, assert giá trị. Hoặc mock nếu nặng.

---

## Quyết định kiến trúc cần chốt TRƯỚC khi đầu tư

> Điểm quan trọng nhất, quyết định có nên làm hai adapter này trong framework hay không:

Nếu kiến trúc có **edge gateway** phía trước (gateway nói Modbus/OPC UA trực tiếp
với PLC rồi đẩy MQTT/HTTP lên Xime) thì **có thể KHÔNG cần** Modbus/OPC UA trong
chính framework - MQTT (0.5) là đủ. Chỉ làm hai adapter này khi Xime chạy thẳng ở
tầng tiếp xúc thiết bị (không có gateway trung gian). Chủ dự án cần chốt điều này
trước khi tới 0.7.
