# Phân loại tên API còn thiếu tài liệu

> **Trạng thái:** đã phân loại từng mục ngày 2026-10-17; tài liệu song ngữ đạt import/cú pháp, sáu ví dụ đã thực thi; coverage thô 0/317 thiếu ở mỗi ngôn ngữ.
> **Thuộc bản:** worktree sau `2ad5274`, metadata 0.8.3; không đổi __all__.
> **Thay:** phân loại cụ thể cho con số 148/317 EN và 152/317 VN của kiểm toán ngày 2026-10-17.
> **Bị thay bởi:** chưa có.

152 lượt export (148 tên riêng) thiếu ở ít nhất một ngôn ngữ: **94 API/kiểu cấu hình/kết quả, 54 hạ tầng, 4 alias/re-export**. Đây là phân loại theo từng đường export; các tên trùng module vẫn được giữ riêng để có thể đối chiếu đủ số đo. Không xóa tên khỏi __all__ để làm giảm bộ đếm.

API/kiểu cấu hình/kết quả đã có mô tả vai trò, tham số hoặc ví dụ ở [EN](../../../docs/en/api-reference.md) và [VN](../../../docs/vn/api-reference.md). Hạ tầng có từng lý do quản lý trong bảng dưới và trong trang tra cứu, không quảng cáo adapter/scanner/registry như điểm mở rộng ứng dụng ổn định.

| Module | Tên | Thiếu trước vá | Phân loại | Lý do/cách dùng |
|---|---|---|---|---|
| `xime` | `__version__` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Phiên bản package đang cài; không xác định commit của checkout phát triển. |
| `xime.adapters.grpc` | `configure_grpc_interceptors` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Đăng ký các instance interceptor trước startup; interceptor context/lỗi của framework vẫn bao ngoài. |
| `xime.adapters.grpc.client` | `ClientGenResult` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Kết quả sinh SDK: file written và skipped_methods; kiểm phần bị bỏ trước khi giao SDK. |
| `xime.adapters.grpc.client` | `GrpcClientConfig` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Cấu hình grpc.clients.<id>: host/port đích, deadline, TLS và keepalive; khai qua YAML. |
| `xime.adapters.grpc.client` | `GrpcClientTlsConfig` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | TLS chiều gọi ra: CA, cert/key client và xoay động; bật TLS không tự chọn danh tính. |
| `xime.adapters.grpc.client` | `GrpcKeepaliveConfig` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Chính sách ping HTTP/2 chiều gọi ra; time_ms=0 tắt ping; chọn chu kỳ mà phía đích cho phép. |
| `xime.adapters.grpc.client` | `SdkRuntime` | en, vn | Hạ tầng framework | Ruột SDK sinh tự động: nạp descriptor và marshal; dùng client có kiểu đã sinh thay vì tự dựng runtime. |
| `xime.adapters.grpc.client` | `generate_client_sdk` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Sinh SDK có kiểu từ thư mục proto; ghi vào out_dir; metadata package đặt tên distribution được sinh. |
| `xime.adapters.grpc.codefirst` | `CodeFirstConfig` | en, vn | Hạ tầng framework | Bản ghi do configure_grpc_codefirst quản lý: package, output và lock; không phải service để inject. |
| `xime.adapters.grpc.codefirst` | `codefirst_registry` | en, vn | Hạ tầng framework | Kho đăng ký cho CLI/adapter; ghi bằng configure_grpc_codefirst, không đổi sau startup. |
| `xime.adapters.grpc.codefirst` | `build_proto_files` | en, vn | Hạ tầng framework | Pipeline sinh proto với LockFile; CLI quản lý tính nhất quán lock/output; ưu tiên xime grpc generate/check. |
| `xime.adapters.grpc.codefirst` | `GenerateResult` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Kết quả sinh code-first gồm written và protoc_outputs; đọc khi gọi generator từ công cụ. |
| `xime.adapters.grpc.codefirst` | `CheckResult` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Kết quả kiểm code-first: up_to_date, stale, missing; output cũ/thiếu cần sinh lại. |
| `xime.adapters.grpc.codefirst` | `ProtoInt64` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Marker Annotated chọn protobuf int64; đổi biểu diễn wire, không tự giới hạn int của Python. |
| `xime.adapters.grpc.codefirst` | `ProtoUInt32` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Marker Annotated chọn protobuf uint32 không dấu; chọn độ rộng đúng hợp đồng bên ngoài. |
| `xime.adapters.grpc.codefirst` | `ProtoSInt32` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Marker Annotated chọn sint32 mã zig-zag, phù hợp số có dấu gần 0. |
| `xime.adapters.grpc.codefirst` | `ProtoSInt64` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Marker Annotated chọn sint64 mã zig-zag; giữ tương thích số field và kiểu wire đã phát hành. |
| `xime.adapters.grpc.interceptors` | `configure_grpc_interceptors` | en, vn | Alias hoặc re-export tương đương | Re-export của xime.adapters.grpc.configure_grpc_interceptors; cùng đăng ký/thứ tự, không tạo chuỗi interceptor thứ hai. |
| `xime.adapters.grpc.interceptors` | `grpc_interceptor_registry` | en, vn | Hạ tầng framework | Kho bootstrap cho interceptor/ánh xạ lỗi; dùng hàm configure công khai, không reset khi service chạy. |
| `xime.adapters.grpc.interceptors` | `RequestContextInterceptor` | en, vn | Hạ tầng framework | Vòng đời request context gRPC có sẵn; adapter tự gắn, thêm lại sẽ xử lý context hai lần. |
| `xime.adapters.grpc.routing` | `grpc_service_registry` | en, vn | Hạ tầng framework | Binding/package để GrpcAdapter đọc; đăng ký qua configure_grpc, không tự giữ registry thứ hai. |
| `xime.adapters.grpc.tls` | `grpc_tls_registry` | en, vn | Hạ tầng framework | Đăng ký provider chứng thư qua configure_grpc_tls; không phải kho cert cho code nghiệp vụ. |
| `xime.adapters.modbus` | `Area` | vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Enum COIL, DISCRETE, HOLDING, INPUT; mỗi vùng có không gian địa chỉ riêng, không gộp lệnh xuyên vùng. |
| `xime.adapters.modbus` | `DataType` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Enum kiểu scalar Modbus cho field/codec; độ rộng register quyết định số ô đọc/ghi. |
| `xime.adapters.modbus` | `DeviceInfo` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Metadata thiết bị đã decorate: class, unit, field và byte/word order; lấy bằng get_device_info. |
| `xime.adapters.modbus` | `ModbusField` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Descriptor phía sau Holding/Input/Coil/Discrete; dùng các khai báo này để chọn rõ vùng địa chỉ. |
| `xime.adapters.modbus` | `get_device_info` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Đọc metadata thiết bị từ class hoặc instance; trả None nếu chưa decorate. |
| `xime.adapters.modbus` | `ModbusConnection` | en, vn | Hạ tầng framework | Holder kết nối pymodbus do adapter quản lý; inject ModbusClient để thao tác, không tự mở kết nối thứ hai. |
| `xime.adapters.modbus` | `ModbusConfig` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Cấu hình client đã phân giải từ modbus.devices.<id>: host, unit, timeout và byte/word order. |
| `xime.adapters.modbus` | `ModbusServerConfig` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Cấu hình host/port của modbus.server; override listener vẫn thuộc topology process. |
| `xime.adapters.modbus` | `modbus_registry` | en, vn | Hạ tầng framework | Đăng ký thiết bị/server được đọc lúc startup; khai qua configure_modbus. |
| `xime.adapters.modbus` | `DEFAULT_DEVICE` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | ID đích Modbus mặc định default; là tên cấu hình, không phải địa chỉ unit vật lý. |
| `xime.adapters.modbus` | `decode_field` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Giải một field từ register/bit thô theo order, scale và offset trong DeviceInfo. |
| `xime.adapters.modbus` | `encode_field` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Mã hóa field thành register/bit; vùng chỉ đọc chặn ghi trừ override tường minh phía server. |
| `xime.adapters.modbus` | `decode_device` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Dựng giá trị thiết bị từ payload địa chỉ/giá trị theo vùng; payload phải đủ field đã khai. |
| `xime.adapters.modbus` | `ModbusError` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Lỗi gốc thao tác Modbus; bắt lỗi kết nối/codec cụ thể khi cách phục hồi khác nhau. |
| `xime.adapters.modbus` | `ReadCommand` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Một mục kế hoạch đọc (area, address, count); một lệnh không trải qua hai vùng địa chỉ. |
| `xime.adapters.modbus.routing` | `ModbusControllerScanner` | en, vn | Hạ tầng framework | Tìm controller Modbus đã decorate lúc startup; khai package cần quét, không gọi từ handler. |
| `xime.adapters.modbus.routing` | `ModbusRouteBuilder` | en, vn | Hạ tầng framework | Gắn handler với instance DI và dựng nhóm poll; startup của adapter quản lý bước này. |
| `xime.adapters.modbus.routing` | `PollGroup` | en, vn | Hạ tầng framework | Model, chu kỳ và handler của một vòng poll; routing tạo ra, không phải hợp đồng scheduler nghiệp vụ. |
| `xime.adapters.modbus.routing` | `ResolvedPoll` | en, vn | Hạ tầng framework | Callback poll đã gắn controller; khai bằng decorator, không tự dựng bản ghi routing. |
| `xime.adapters.modbus.routing` | `ResolvedChangeWatch` | en, vn | Hạ tầng framework | Bản ghi callback/deadband đã phân giải; sinh từ khai báo on_change. |
| `xime.adapters.mqtt` | `MqttConnection` | en, vn | Hạ tầng framework | Holder client aiomqtt với reconnect/vòng đời do adapter quản lý; dùng MqttPublisher để gửi. |
| `xime.adapters.mqtt` | `MqttConfig` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Cấu hình broker trong mqtt: credential, client ID, keepalive; model không tự kết nối. |
| `xime.adapters.mqtt` | `mqtt_registry` | en, vn | Hạ tầng framework | Trạng thái đăng ký chung cho adapter/publisher; dùng configure_mqtt, không đổi khi đang kết nối. |
| `xime.adapters.mqtt.routing` | `MqttRouteBuilder` | en, vn | Hạ tầng framework | Dựng bảng dispatch MQTT sau DI; adapter startup quản lý kiểm tra và subscribe. |
| `xime.adapters.mqtt.routing` | `ResolvedMqttRoute` | en, vn | Hạ tầng framework | Handler đã bind cùng topic, subscription và model RPC; do route builder tạo. |
| `xime.adapters.mqtt.routing` | `MqttControllerScanner` | en, vn | Hạ tầng framework | Quét package controller đã khai; dùng configure_mqtt thay vì scanner trong request. |
| `xime.adapters.opcua` | `OpcuaNode` | en, vn | Alias hoặc re-export tương đương | Descriptor cũng export dưới tên Node; dùng Node khi khai node model; hai tên cùng một hiện thực. |
| `xime.adapters.opcua` | `NodeModelInfo` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Metadata node model: class, descriptor và namespace server tùy chọn; lấy bằng các hàm metadata. |
| `xime.adapters.opcua` | `get_node_model_info` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Trả metadata node hoặc None nếu class/instance không phải node model. |
| `xime.adapters.opcua` | `require_node_model_info` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Trả metadata node hoặc báo lỗi có hướng sửa nếu model chưa decorate. |
| `xime.adapters.opcua` | `OpcuaConnection` | en, vn | Hạ tầng framework | Holder kết nối asyncua do adapter quản lý; inject OpcuaClient thay vì tự mở session được quản lý khác. |
| `xime.adapters.opcua` | `OpcuaConfig` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Cấu hình endpoint/security đã phân giải từ opcua.servers.<id>; đường dẫn cert thuộc cấu hình server được chọn. |
| `xime.adapters.opcua` | `OpcuaServerConfig` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Endpoint, tên và security của opcua.server; chế độ None không mã hóa vẫn được hỗ trợ khi chọn tường minh. |
| `xime.adapters.opcua` | `opcua_registry` | en, vn | Hạ tầng framework | Đăng ký node/server để adapter đọc; dùng configure_opcua khi nạp config. |
| `xime.adapters.opcua` | `DEFAULT_SERVER` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | ID đích OPC UA mặc định default; chọn một cấu hình server có tên. |
| `xime.adapters.opcua` | `SECURITY_MODES` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Các tên hỗ trợ: None, Sign, SignAndEncrypt; dùng normalize_mode để kiểm chuỗi đầu vào. |
| `xime.adapters.opcua` | `normalize_mode` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Chuẩn hóa mode bảo mật không phân biệt hoa/thường; tên lạ bị từ chối thay vì ngầm chọn None. |
| `xime.adapters.opcua` | `build_security_string` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Dựng tham số security cho asyncua từ mode và đường dẫn cert/key; trả None ở chế độ không bảo mật. |
| `xime.adapters.opcua` | `OpcuaError` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Lỗi gốc thao tác OPC UA; dùng lỗi cụ thể hơn để quyết định retry hoặc sửa dữ liệu. |
| `xime.adapters.socket` | `ClientUpload` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Context manager do SocketClient.upload trả về; write các chunk rồi finish để nhận đáp án, không tự dựng. |
| `xime.adapters.socket` | `SocketServerConfig` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Đường dẫn Unix socket, quyền/owner POSIX, danh sách UID và timeout; chỉ dùng POSIX. |
| `xime.adapters.socket.routing` | `ResolvedEndpoint` | en, vn | Hạ tầng framework | Bản ghi dispatch socket gồm model request/response và tham số stream; sinh từ decorator endpoint. |
| `xime.adapters.socket.routing` | `SocketEndpointBuilder` | en, vn | Hạ tầng framework | Bind khai báo endpoint socket vào object DI lúc startup; không phải điểm mở rộng service. |
| `xime.adapters.web` | `ServerTlsConfig` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Cert/key TLS HTTP, CA client và cipher; không khai cert/key là chủ ý dùng HTTP. |
| `xime.adapters.web` | `WebServerConfig` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Mặc định listener webserver, SSL/reload và management; server là alias tương thích. |
| `xime.adapters.web` | `TlsReloadResult` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Kết quả tổng gồm outcome, workers, missing_workers; dùng succeeded: cần ACK thành công không rỗng và không thiếu worker. |
| `xime.adapters.web` | `TlsWorkerResult` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Kết quả từng worker và certificate_fingerprint; fingerprint hash byte file, không phải DER chuẩn hóa hay xác minh hostname/hạn cert. |
| `xime.adapters.web` | `BEARER_SUBPROTOCOL_PREFIX` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Prefix token WebSocket xime.bearer.; đề nghị thêm subprotocol ứng dụng thật và không vọng lại entry chứa token. |
| `xime.adapters.web` | `WS_UNAUTHORIZED` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Mã đóng WebSocket khi xác thực thất bại 3000; middleware JWT HTTP không xác thực scope WebSocket. |
| `xime.adapters.web.files` | `DEFAULT_MAX_BYTES` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Trần upload mặc định 32 MiB của save_upload; truyền max_bytes tường minh khi route cần giới hạn khác. |
| `xime.adapters.web.openapi` | `ApiKey` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Metadata scheme API key của OpenAPI (name, location, scheme_name); mô tả credential, không tự xác thực request. |
| `xime.adapters.web.openapi` | `SecurityScheme` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Protocol khai báo security OpenAPI; hiện thực cấp metadata schema, không phải logic phân quyền. |
| `xime.adapters.web.ws` | `BEARER_SUBPROTOCOL_PREFIX` | en, vn | Alias hoặc re-export tương đương | Prefix token WebSocket xime.bearer.; đề nghị thêm subprotocol ứng dụng thật và không vọng lại entry chứa token. Cùng tên được re-export ở xime.adapters.web. |
| `xime.adapters.web.ws` | `WS_UNAUTHORIZED` | en, vn | Alias hoặc re-export tương đương | Mã đóng WebSocket khi xác thực thất bại 3000; middleware JWT HTTP không xác thực scope WebSocket. Cùng tên được re-export ở xime.adapters.web. |
| `xime.core.bootstrap` | `StartupOrchestrator` | en, vn | Hạ tầng framework | Pipeline bootstrap DI/vòng đời/primary do Application sở hữu; không tự khởi chạy orchestrator thứ hai. |
| `xime.core.config` | `YamlConfigLoader` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | load() đọc application.yml và overlay được chọn; không trộn biến profile với environments trong một file. |
| `xime.core.config` | `detect_env` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Đọc XIME_ENV trước APP_ENV, trả None nếu chưa đặt; chúng chọn file profile, không chọn nhánh local/server. |
| `xime.core.config` | `LoggingConfig` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Mặc định root log: enabled, level, format, datefmt; bootstrap tôn trọng app đã cấu hình handler. |
| `xime.core.container` | `XimeContainer` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | API scan/bind/build/get cấp thấp cho tích hợp/kiểm thử; service thông thường dùng Application và constructor injection. |
| `xime.core.contract` | `ENDPOINT_ATTR` | en, vn | Hạ tầng framework | Thuộc tính metadata dành riêng cho decorator/scanner endpoint; không tự ghi bằng tay. |
| `xime.core.contract` | `EndpointInfo` | en, vn | Hạ tầng framework | Tên/loại endpoint được decorator command/upload/download gắn vào; scanner đọc bản ghi này. |
| `xime.core.contract` | `EndpointKind` | en, vn | Hạ tầng framework | Enum khai báo trung tính giao thức trong metadata endpoint; dùng decorator thay vì ghép metadata thủ công. |
| `xime.core.contract` | `ControllerScanner` | en, vn | Hạ tầng framework | Tìm controller contract trong package cho startup gRPC/socket; framework quản lý thứ tự quét và đăng ký. |
| `xime.core.event` | `EventBusConfig` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Chính sách áp lực event trong một tiến trình: max_pending, never_drop; khai bằng configure_event_bus trước startup. |
| `xime.core.event` | `event_bus_registry` | en, vn | Hạ tầng framework | Kho cấu hình event bus lúc bootstrap; ghi qua configure_event_bus. |
| `xime.core.exception` | `XimeException` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Lỗi gốc framework; ưu tiên lớp con cụ thể khi chọn cách phục hồi. |
| `xime.core.exception` | `StartupException` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Ứng dụng không thể khởi động an toàn; sửa cấu hình/đồ thị được báo trước khi phục vụ. |
| `xime.core.exception` | `MissingTypeHintException` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Không phân giải được type hint constructor; bảo đảm type import được và sửa forward reference. |
| `xime.core.exception` | `MissingImplementationException` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Protocol chưa có hiện thực đăng ký; quét package hiện thực và khai binding tường minh. |
| `xime.core.exception` | `MissingBindingException` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Có một ứng viên phù hợp cấu trúc nhưng chưa bind; khai binding Protocol để giữ kiểm tra fail-fast. |
| `xime.core.exception` | `UnregisteredDependencyException` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Dependency concrete chưa được quét/cấp; đăng ký type đó thay vì bỏ qua DI. |
| `xime.core.exception` | `MultipleImplementationException` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Có nhiều ứng viên nhưng chưa chọn tường minh; khai binding hoặc dynamic binding đúng cấu hình. |
| `xime.core.exception` | `CircularDependencyException` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Chu trình dependency constructor; tách chu trình đồ thị thay vì trì hoãn bằng biến global ẩn. |
| `xime.core.exception` | `BindingValidationException` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Hiện thực được chọn thiếu method của Protocol; sửa hiện thực hoặc binding. |
| `xime.core.exception` | `InvalidOrderRuleException` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | dependency.order trỏ tới class chưa đăng ký; đăng ký class hoặc bỏ luật cũ. |
| `xime.core.exception` | `OrderRuleCycleException` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Thứ tự startup tường minh tạo chu trình; bỏ các ràng buộc thứ tự xung đột. |
| `xime.core.exception` | `SecurityException` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Lỗi gốc bảo mật runtime; adapter ánh xạ lỗi xác thực/phân quyền cụ thể theo giao thức. |
| `xime.core.exception` | `AuthorizationException` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Danh tính đã xác thực thiếu quyền yêu cầu; trả từ chối truy cập, không lặp lại xác thực. |
| `xime.core.exception` | `SocketException` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Lỗi gốc runtime/giao thức Unix socket; vẫn yêu cầu nền tảng POSIX. |
| `xime.core.exception` | `ProtocolError` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Frame socket sai giao thức; sửa client protocol, không coi là lỗi kiểm dữ liệu nghiệp vụ. |
| `xime.core.exception` | `EndpointNotFound` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Tên endpoint socket chưa đăng ký; đồng bộ tên hợp đồng client/server. |
| `xime.core.exception` | `SessionTimeout` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Session stream socket vượt timeout nhàn rỗi; chỉ retry nếu thao tác cho phép lặp an toàn. |
| `xime.core.exception` | `SocketCommandError` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Client nhận frame ERROR với code/message từ server; xử lý theo code, không công khai chi tiết nội bộ. |
| `xime.core.lifecycle` | `RunOnce` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Protocol lifecycle async run_once: primary chạy một lần mỗi cụm trước khi phục vụ; việc định kỳ thuộc scheduler. |
| `xime.core.lifecycle` | `LifecycleManager` | en, vn | Hạ tầng framework | Sắp PostConstruct/PreDestroy cho instance đăng ký; Application quản lý để tránh chạy hook hai lần. |
| `xime.core.link` | `LinkError` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Thao tác ProcessLink sai: kênh lạ, payload quá cỡ hoặc dùng sau đóng; sửa caller/cấu hình. |
| `xime.core.link` | `LinkLayoutMismatch` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Bố cục vùng nhớ bus khác khuôn của tiến trình; không đọc byte bằng layout sai. |
| `xime.core.link` | `link_registry` | en, vn | Hạ tầng framework | Đăng ký kênh/handler lúc startup; khai qua configure_link, không đổi tùy tiện lúc chạy. |
| `xime.core.link` | `INTERNAL_CHANNEL` | en, vn | Hạ tầng framework | Kênh điều khiển __xime__ dành riêng; kênh ứng dụng không được dùng lại tên này. |
| `xime.core.link` | `BoundHandler` | en, vn | Hạ tầng framework | Bản ghi callback ProcessLink đã bind DI; framework thu từ method on_request/on_announce. |
| `xime.core.link` | `collect` | vn | Hạ tầng framework | Thu handler từ instance DI đã dựng; startup quản lý kiểm trùng kênh và gắn vào bus. |
| `xime.core.link` | `Outcome` | vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Union kết quả ProcessLink.ask: Done, NoOwner, NoAnswer, Failed; xử lý tường minh cả bốn. |
| `xime.core.link` | `LinkMessage` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Bản ghi quan sát channel/key/payload/sender; payload là byte ứng dụng, không phải danh tính tin cậy. |
| `xime.core.link` | `LinkStats` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Ảnh chụp gần đúng từ link.stats(), gồm số liệu từng kênh; quan sát không thay đồng bộ. |
| `xime.core.link` | `ChannelStats` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Dung lượng/mức dùng, tuổi dòng chưa đọc và số liệu reader của kênh; dùng chẩn đoán vận hành. |
| `xime.core.link` | `ReaderStats` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | process_index, unread, missed theo reader; phục hồi tin mất tùy nghiệp vụ ứng dụng. |
| `xime.core.link` | `RawRow` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Dòng gỡ lỗi từ link.dump(channel); có thể chứa payload nhạy cảm, không công khai dump. |
| `xime.core.link` | `sweep_orphans` | en, vn | Hạ tầng framework | Dọn vùng nhớ lần chạy có tiến trình gốc đã chết; framework startup quản lý, không phải API dọn nghiệp vụ định kỳ. |
| `xime.core.metadata` | `resolve_constructor_hints` | en, vn | Hạ tầng framework | Helper reflection phân giải type DI; tên không phân giải được là lỗi startup, không phải dữ liệu nghiệp vụ thiếu. |
| `xime.core.metadata` | `get_init_parameters` | en, vn | Hạ tầng framework | Đọc tên tham số constructor để kiểm DI; framework dùng phát hiện thiếu hint. |
| `xime.core.metadata` | `is_protocol` | en, vn | Hạ tầng framework | Nhận diện khai báo Protocol cho DI; class hiện thực theo cấu trúc vẫn được dựng. |
| `xime.core.metadata` | `is_abstract` | en, vn | Hạ tầng framework | Đọc trạng thái abstract khi quét; không phải kiểm quyền hay năng lực nghiệp vụ. |
| `xime.core.metadata` | `get_protocol_methods` | en, vn | Hạ tầng framework | Lấy tên method Protocol để kiểm binding; khai binding tường minh, không sửa tập method. |
| `xime.core.refdata` | `RefDataArena` | en, vn | Hạ tầng framework | Sở hữu block vùng nhớ và quyền ghi primary của một lần chạy; Application tạo/gắn/đóng arena. |
| `xime.core.refdata` | `RefDataLayout` | en, vn | Hạ tầng framework | Tính offset byte từ max_bytes; chi tiết bố cục vùng nhớ, không phải định dạng lưu trữ app. |
| `xime.core.refdata` | `RefDataStats` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Quan sát gần đúng từ table.stats(): generation, served_generation, stale, fill_ratio; dùng read() để lấy dữ liệu thật. |
| `xime.core.refdata` | `TableSpec` | en, vn | Hạ tầng framework | Tên/dung lượng bảng trích trước DI; khai bảng bằng configure_refdata thay vì tự dựng spec. |
| `xime.core.refdata` | `refdata_registry` | en, vn | Hạ tầng framework | Đăng ký bảng lúc bootstrap; điểm vào cấu hình là configure_refdata. |
| `xime.core.refdata` | `specs_of` | en, vn | Hạ tầng framework | Trích TableSpec từ class RefData đã đăng ký; Application dùng để dựng vùng nhớ. |
| `xime.core.refdata` | `block_name` | en, vn | Hạ tầng framework | Sinh tên vùng nhớ từ cặp lần chạy/bảng; không phải định danh bền vững của ứng dụng. |
| `xime.core.refdata` | `new_run_id` | en, vn | Hạ tầng framework | Mã lần chạy bộ cấp phát từ PID và phần ngẫu nhiên; framework quản lý vòng đời. |
| `xime.core.refdata` | `DEFAULT_MAX_BYTES` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Dung lượng bảng RefData mặc định 65536 byte; đổi max_bytes khi khai class bảng nếu cần. |
| `xime.core.refdata` | `MAX_SPINS` | en, vn | Hạ tầng framework | Trần lặp đọc snapshot RefData, hiện 100; cơ chế nội bộ, không phải khóa YAML để chỉnh. |
| `xime.core.refdata` | `RefDataLayoutMismatch` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Layout bảng dùng chung không khớp tiến trình; đồng bộ lần chạy/phiên bản, không đọc byte không tương thích. |
| `xime.core.refdata` | `RefDataClosedError` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Truy cập bảng sau khi arena đóng; sửa quyền sở hữu vòng đời, không mở lại vùng nhớ từ handler. |
| `xime.core.refdata` | `RefDataError` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Lỗi gốc kho tham chiếu dùng chung; phân biệt lỗi vòng đời/layout với số liệu quan sát cũ. |
| `xime.core.refdata` | `RefDataTornError` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Không lấy được snapshot nhất quán sau số lần thử có trần; caller retry theo chính sách khả dụng. |
| `xime.core.security` | `credential_type` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Slot bảo mật theo task với get/set; mô tả loại credential đã xác thực, được dọn ở biên request. |
| `xime.core.security` | `permissions` | vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Slot quyền theo task; AuthorizationManager quyết định ngữ nghĩa quyền, slot này chỉ giữ dữ liệu. |
| `xime.core.security` | `authenticate` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Đặt field bảo mật sau xác minh; field bỏ qua giữ nguyên, None tường minh xóa field; hàm không tự xác minh credential. |
| `xime.core.security` | `clear_security` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Xóa mọi field bảo mật của task hiện tại; code transport tự viết phải gọi trong finally. |
| `xime.core.security` | `CredentialType` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Enum tiện ích PASSWORD, TOKEN, API_KEY, OAUTH2, CERTIFICATE; ứng dụng có thể dùng enum riêng. |
| `xime.core.shared` | `MP_CONTEXT` | en, vn | Hạ tầng framework | Context multiprocessing chung của framework; không thay hoặc trộn chiến lược tạo tiến trình. |
| `xime.core.shared` | `ghi_o` | en, vn | Hạ tầng framework | Hàm ghi bản ghi vùng nhớ tránh cửa sổ zero-fill của pack_into; để framework quản lý ghi layout. |
| `xime.core.shared` | `view_of` | en, vn | Hạ tầng framework | Helper thu block thành memoryview; không giữ view sau khi block đóng. |
| `xime.core.transaction` | `ReadOnlyContext` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Protocol context manager async do ReadOnlyManager trả về; mượn session bao ngoài mà không commit/đóng nó. |
| `xime.starters.lmdb` | `DEFAULT_TTL` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | TTL mặc định Store LMDB là 3600 giây; khai TTL class tường minh khi thời hạn nghiệp vụ khác. |
| `xime.starters.lmdb` | `store_registry` | en, vn | Hạ tầng framework | Theo dõi instance Store trong tiến trình cho cleanup; đăng ký theo lúc dựng và vòng đời Store. |
| `xime.starters.mail` | `SmtpMailService` | en, vn | API ứng dụng hoặc kiểu cấu hình/kết quả | Backend SMTP của MailService dùng YAML mail; scan/bind service; mỗi lần gửi dùng aiosmtplib, không có pool kết nối lúc startup. |
| `xime.starters.sqlalchemy` | `AsyncEngineProvider` | en, vn | Hạ tầng framework | Engine SQLAlchemy và dispose do DI quản lý; inject dịch vụ session/transaction thay vì tạo thêm provider. |

Các phần mở rộng tài liệu theo nhu cầu như deployment/observability vẫn là backlog riêng; không coi việc phủ tên API là hoàn tất mọi đề xuất tài liệu cũ.
