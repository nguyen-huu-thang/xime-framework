# Tra cứu API và quyền quản lý vòng đời

[Mục lục tài liệu](../README.md) · [English](../en/api-reference.md)

Trang này bổ sung cho các hướng dẫn theo công việc. Các tên export trước đây chưa có mục tra cứu ở ít nhất một ngôn ngữ được phân biệt thành API ứng dụng, alias và hạ tầng framework. Việc export không tự cam kết một điểm mở rộng ổn định. Scanner, builder, registry và phần ruột adapter thuộc bootstrap; cấu hình adapter qua hàm configure và decorator controller đã được hướng dẫn.

Kiểu cấu hình/kết quả mô tả giá trị đọc từ YAML hoặc do thao tác trả về. Có chữ ký constructor không có nghĩa ứng dụng cần tự dựng mọi kiểu. Hạ tầng được ghi để hiểu ai quản lý và cách chẩn đoán, không để khuyến nghị gọi từ request handler. Transport/starter tùy chọn vẫn cần extra cài đặt tương ứng.

## `xime`

Hướng dẫn: [core-concepts.md](core-concepts.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `__version__` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Phiên bản package đang cài; không xác định commit của checkout phát triển. | — |

## `xime.adapters.grpc`

Hướng dẫn: [grpc-codefirst.md](grpc-codefirst.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `configure_grpc_interceptors` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Đăng ký các instance interceptor trước startup; interceptor context/lỗi của framework vẫn bao ngoài. | `(interceptors: 'list[grpc.aio.ServerInterceptor]') -> 'None'` |

## `xime.adapters.grpc.client`

Hướng dẫn: [grpc-client.md](grpc-client.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `ClientGenResult` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Kết quả sinh SDK: file written và skipped_methods; kiểm phần bị bỏ trước khi giao SDK. | `ClientGenResult(written: 'list[str]' = ..., skipped_methods: 'list[str]' = ...) -> None` |
| `GrpcClientConfig` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Cấu hình grpc.clients.<id>: host/port đích, deadline, TLS và keepalive; khai qua YAML. | — |
| `GrpcClientTlsConfig` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. TLS chiều gọi ra: CA, cert/key client và xoay động; bật TLS không tự chọn danh tính. | `GrpcClientTlsConfig(*, enabled: bool = False, dynamic: bool = False, ca_file: str \| None = None, cert_file: str \| None = None, key_file: str \| None = None, server_id: str = 'default') -> None` |
| `GrpcKeepaliveConfig` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Chính sách ping HTTP/2 chiều gọi ra; time_ms=0 tắt ping; chọn chu kỳ mà phía đích cho phép. | `GrpcKeepaliveConfig(*, time_ms: int = 0, timeout_ms: int = 20000, permit_without_calls: bool = False) -> None` |
| `SdkRuntime` | **Hạ tầng framework**. Ruột SDK sinh tự động: nạp descriptor và marshal; dùng client có kiểu đã sinh thay vì tự dựng runtime. | — |
| `generate_client_sdk` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Sinh SDK có kiểu từ thư mục proto; ghi vào out_dir; metadata package đặt tên distribution được sinh. | `(proto_dir: 'str', out_dir: 'str', package: 'str \| None' = None, package_version: 'str' = '0.1.0') -> 'ClientGenResult'` |

## `xime.adapters.grpc.codefirst`

Hướng dẫn: [grpc-codefirst.md](grpc-codefirst.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `CodeFirstConfig` | **Hạ tầng framework**. Bản ghi do configure_grpc_codefirst quản lý: package, output và lock; không phải service để inject. | — |
| `codefirst_registry` | **Hạ tầng framework**. Kho đăng ký cho CLI/adapter; ghi bằng configure_grpc_codefirst, không đổi sau startup. | — |
| `build_proto_files` | **Hạ tầng framework**. Pipeline sinh proto với LockFile; CLI quản lý tính nhất quán lock/output; ưu tiên xime grpc generate/check. | — |
| `GenerateResult` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Kết quả sinh code-first gồm written và protoc_outputs; đọc khi gọi generator từ công cụ. | `GenerateResult(written: 'list[str]' = ..., protoc_outputs: 'list[str]' = ...) -> None` |
| `CheckResult` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Kết quả kiểm code-first: up_to_date, stale, missing; output cũ/thiếu cần sinh lại. | `CheckResult(up_to_date: 'bool', stale: 'list[str]' = ..., missing: 'list[str]' = ...) -> None` |
| `ProtoInt64` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Marker Annotated chọn protobuf int64; đổi biểu diễn wire, không tự giới hạn int của Python. | `ProtoInt64()` |
| `ProtoUInt32` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Marker Annotated chọn protobuf uint32 không dấu; chọn độ rộng đúng hợp đồng bên ngoài. | `ProtoUInt32()` |
| `ProtoSInt32` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Marker Annotated chọn sint32 mã zig-zag, phù hợp số có dấu gần 0. | `ProtoSInt32()` |
| `ProtoSInt64` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Marker Annotated chọn sint64 mã zig-zag; giữ tương thích số field và kiểu wire đã phát hành. | `ProtoSInt64()` |

## `xime.adapters.grpc.interceptors`

Hướng dẫn: [grpc-codefirst.md](grpc-codefirst.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `configure_grpc_interceptors` | **Alias hoặc re-export tương đương**. Re-export của xime.adapters.grpc.configure_grpc_interceptors; cùng đăng ký/thứ tự, không tạo chuỗi interceptor thứ hai. | `(interceptors: 'list[grpc.aio.ServerInterceptor]') -> 'None'` |
| `grpc_interceptor_registry` | **Hạ tầng framework**. Kho bootstrap cho interceptor/ánh xạ lỗi; dùng hàm configure công khai, không reset khi service chạy. | — |
| `RequestContextInterceptor` | **Hạ tầng framework**. Vòng đời request context gRPC có sẵn; adapter tự gắn, thêm lại sẽ xử lý context hai lần. | — |

## `xime.adapters.grpc.routing`

Hướng dẫn: [grpc-codefirst.md](grpc-codefirst.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `grpc_service_registry` | **Hạ tầng framework**. Binding/package để GrpcAdapter đọc; đăng ký qua configure_grpc, không tự giữ registry thứ hai. | — |

## `xime.adapters.grpc.tls`

Hướng dẫn: [grpc-codefirst.md](grpc-codefirst.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `grpc_tls_registry` | **Hạ tầng framework**. Đăng ký provider chứng thư qua configure_grpc_tls; không phải kho cert cho code nghiệp vụ. | — |

## `xime.adapters.modbus`

Hướng dẫn: [modbus.md](modbus.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `Area` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Enum COIL, DISCRETE, HOLDING, INPUT; mỗi vùng có không gian địa chỉ riêng, không gộp lệnh xuyên vùng. | — |
| `DataType` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Enum kiểu scalar Modbus cho field/codec; độ rộng register quyết định số ô đọc/ghi. | — |
| `DeviceInfo` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Metadata thiết bị đã decorate: class, unit, field và byte/word order; lấy bằng get_device_info. | `DeviceInfo(cls: 'type', unit: 'int', fields: 'dict[str, ModbusField]', byte_order: 'ByteOrder', word_order: 'WordOrder') -> 'None'` |
| `ModbusField` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Descriptor phía sau Holding/Input/Coil/Discrete; dùng các khai báo này để chọn rõ vùng địa chỉ. | — |
| `get_device_info` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Đọc metadata thiết bị từ class hoặc instance; trả None nếu chưa decorate. | `(target: 'Any') -> 'DeviceInfo \| None'` |
| `ModbusConnection` | **Hạ tầng framework**. Holder kết nối pymodbus do adapter quản lý; inject ModbusClient để thao tác, không tự mở kết nối thứ hai. | — |
| `ModbusConfig` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Cấu hình client đã phân giải từ modbus.devices.<id>: host, unit, timeout và byte/word order. | — |
| `ModbusServerConfig` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Cấu hình host/port của modbus.server; override listener vẫn thuộc topology process. | `ModbusServerConfig(*, host: str = '0.0.0.0', port: int = 5020) -> None` |
| `modbus_registry` | **Hạ tầng framework**. Đăng ký thiết bị/server được đọc lúc startup; khai qua configure_modbus. | — |
| `DEFAULT_DEVICE` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. ID đích Modbus mặc định default; là tên cấu hình, không phải địa chỉ unit vật lý. | — |
| `decode_field` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Giải một field từ register/bit thô theo order, scale và offset trong DeviceInfo. | `(field: 'ModbusField', info: 'DeviceInfo', raw: 'Any') -> 'Any'` |
| `encode_field` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Mã hóa field thành register/bit; vùng chỉ đọc chặn ghi trừ override tường minh phía server. | `(field: 'ModbusField', info: 'DeviceInfo', value: 'Any', *, allow_read_only: 'bool' = False) -> 'list[Any]'` |
| `decode_device` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Dựng giá trị thiết bị từ payload địa chỉ/giá trị theo vùng; payload phải đủ field đã khai. | `(info: 'DeviceInfo', payloads: 'dict[Area, dict[int, Any]]') -> 'Any'` |
| `ModbusError` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Lỗi gốc thao tác Modbus; bắt lỗi kết nối/codec cụ thể khi cách phục hồi khác nhau. | — |
| `ReadCommand` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Một mục kế hoạch đọc (area, address, count); một lệnh không trải qua hai vùng địa chỉ. | `ReadCommand(area: 'Area', address: 'int', count: 'int') -> None` |

## `xime.adapters.modbus.routing`

Hướng dẫn: [modbus.md](modbus.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `ModbusControllerScanner` | **Hạ tầng framework**. Tìm controller Modbus đã decorate lúc startup; khai package cần quét, không gọi từ handler. | — |
| `ModbusRouteBuilder` | **Hạ tầng framework**. Gắn handler với instance DI và dựng nhóm poll; startup của adapter quản lý bước này. | — |
| `PollGroup` | **Hạ tầng framework**. Model, chu kỳ và handler của một vòng poll; routing tạo ra, không phải hợp đồng scheduler nghiệp vụ. | — |
| `ResolvedPoll` | **Hạ tầng framework**. Callback poll đã gắn controller; khai bằng decorator, không tự dựng bản ghi routing. | — |
| `ResolvedChangeWatch` | **Hạ tầng framework**. Bản ghi callback/deadband đã phân giải; sinh từ khai báo on_change. | — |

## `xime.adapters.mqtt`

Hướng dẫn: [mqtt.md](mqtt.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `MqttConnection` | **Hạ tầng framework**. Holder client aiomqtt với reconnect/vòng đời do adapter quản lý; dùng MqttPublisher để gửi. | — |
| `MqttConfig` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Cấu hình broker trong mqtt: credential, client ID, keepalive; model không tự kết nối. | — |
| `mqtt_registry` | **Hạ tầng framework**. Trạng thái đăng ký chung cho adapter/publisher; dùng configure_mqtt, không đổi khi đang kết nối. | — |

## `xime.adapters.mqtt.routing`

Hướng dẫn: [mqtt.md](mqtt.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `MqttRouteBuilder` | **Hạ tầng framework**. Dựng bảng dispatch MQTT sau DI; adapter startup quản lý kiểm tra và subscribe. | — |
| `ResolvedMqttRoute` | **Hạ tầng framework**. Handler đã bind cùng topic, subscription và model RPC; do route builder tạo. | — |
| `MqttControllerScanner` | **Hạ tầng framework**. Quét package controller đã khai; dùng configure_mqtt thay vì scanner trong request. | — |

## `xime.adapters.opcua`

Hướng dẫn: [opcua.md](opcua.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `OpcuaNode` | **Alias hoặc re-export tương đương**. Descriptor cũng export dưới tên Node; dùng Node khi khai node model; hai tên cùng một hiện thực. | `OpcuaNode(node_id: 'str', *, writable: 'bool' = True, default: 'Any' = None) -> 'None'` |
| `NodeModelInfo` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Metadata node model: class, descriptor và namespace server tùy chọn; lấy bằng các hàm metadata. | `NodeModelInfo(cls: 'type', nodes: 'dict[str, OpcuaNode]', namespace: 'str \| None')` |
| `get_node_model_info` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Trả metadata node hoặc None nếu class/instance không phải node model. | `(target: 'Any') -> 'NodeModelInfo \| None'` |
| `require_node_model_info` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Trả metadata node hoặc báo lỗi có hướng sửa nếu model chưa decorate. | `(target: 'Any') -> 'NodeModelInfo'` |
| `OpcuaConnection` | **Hạ tầng framework**. Holder kết nối asyncua do adapter quản lý; inject OpcuaClient thay vì tự mở session được quản lý khác. | — |
| `OpcuaConfig` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Cấu hình endpoint/security đã phân giải từ opcua.servers.<id>; đường dẫn cert thuộc cấu hình server được chọn. | — |
| `OpcuaServerConfig` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Endpoint, tên và security của opcua.server; chế độ None không mã hóa vẫn được hỗ trợ khi chọn tường minh. | — |
| `opcua_registry` | **Hạ tầng framework**. Đăng ký node/server để adapter đọc; dùng configure_opcua khi nạp config. | — |
| `DEFAULT_SERVER` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. ID đích OPC UA mặc định default; chọn một cấu hình server có tên. | — |
| `SECURITY_MODES` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Các tên hỗ trợ: None, Sign, SignAndEncrypt; dùng normalize_mode để kiểm chuỗi đầu vào. | — |
| `normalize_mode` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Chuẩn hóa mode bảo mật không phân biệt hoa/thường; tên lạ bị từ chối thay vì ngầm chọn None. | `(value: 'str \| None') -> 'str'` |
| `build_security_string` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Dựng tham số security cho asyncua từ mode và đường dẫn cert/key; trả None ở chế độ không bảo mật. | `(mode: 'str', certificate: 'str \| None', private_key: 'str \| None') -> 'str \| None'` |
| `OpcuaError` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Lỗi gốc thao tác OPC UA; dùng lỗi cụ thể hơn để quyết định retry hoặc sửa dữ liệu. | — |

## `xime.adapters.socket`

Hướng dẫn: [socket-adapter.md](socket-adapter.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `ClientUpload` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Context manager do SocketClient.upload trả về; write các chunk rồi finish để nhận đáp án, không tự dựng. | `ClientUpload(client: 'SocketClient', session_id: 'int', endpoint: 'str', request: 'BaseModel') -> 'None'` |
| `SocketServerConfig` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Đường dẫn Unix socket, quyền/owner POSIX, danh sách UID và timeout; chỉ dùng POSIX. | — |

## `xime.adapters.socket.routing`

Hướng dẫn: [socket-adapter.md](socket-adapter.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `ResolvedEndpoint` | **Hạ tầng framework**. Bản ghi dispatch socket gồm model request/response và tham số stream; sinh từ decorator endpoint. | — |
| `SocketEndpointBuilder` | **Hạ tầng framework**. Bind khai báo endpoint socket vào object DI lúc startup; không phải điểm mở rộng service. | — |

## `xime.adapters.web`

Hướng dẫn: [configuration.md](configuration.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `ServerTlsConfig` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Cert/key TLS HTTP, CA client và cipher; không khai cert/key là chủ ý dùng HTTP. | — |
| `WebServerConfig` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Mặc định listener webserver, SSL/reload và management; server là alias tương thích. | `WebServerConfig(*, host: str = '0.0.0.0', port: int = 8080, ssl: WebServerTlsConfig = ..., management: ManagementServerConfig = ...) -> None` |
| `TlsReloadResult` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Kết quả tổng gồm outcome, workers, missing_workers; dùng succeeded: cần ACK thành công không rỗng và không thiếu worker. | `TlsReloadResult(server_id: 'str', outcome: 'str', workers: 'tuple[TlsWorkerResult, ...]', missing_workers: 'tuple[int, ...]' = ()) -> None` |
| `TlsWorkerResult` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Kết quả từng worker và certificate_fingerprint; fingerprint hash byte file, không phải DER chuẩn hóa hay xác minh hostname/hạn cert. | `TlsWorkerResult(worker_index: 'int', outcome: 'str', certificate_fingerprint: 'str \| None' = None, detail: 'str \| None' = None) -> None` |
| `BEARER_SUBPROTOCOL_PREFIX` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Prefix token WebSocket xime.bearer.; đề nghị thêm subprotocol ứng dụng thật và không vọng lại entry chứa token. | — |
| `WS_UNAUTHORIZED` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Mã đóng WebSocket khi xác thực thất bại 3000; middleware JWT HTTP không xác thực scope WebSocket. | — |

## `xime.adapters.web.files`

Hướng dẫn: [file-storage.md](file-storage.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `DEFAULT_MAX_BYTES` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Trần upload mặc định 32 MiB của save_upload; truyền max_bytes tường minh khi route cần giới hạn khác. | — |

## `xime.adapters.web.openapi`

Hướng dẫn: [configuration.md](configuration.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `ApiKey` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Metadata scheme API key của OpenAPI (name, location, scheme_name); mô tả credential, không tự xác thực request. | `ApiKey(name: 'str', location: "Literal['header', 'query', 'cookie']" = 'header', scheme_name: 'str' = 'ApiKeyAuth') -> None` |
| `SecurityScheme` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Protocol khai báo security OpenAPI; hiện thực cấp metadata schema, không phải logic phân quyền. | — |

## `xime.adapters.web.ws`

Hướng dẫn: [websocket.md](websocket.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `BEARER_SUBPROTOCOL_PREFIX` | **Alias hoặc re-export tương đương**. Prefix token WebSocket xime.bearer.; đề nghị thêm subprotocol ứng dụng thật và không vọng lại entry chứa token. Cùng tên được re-export ở xime.adapters.web. | — |
| `WS_UNAUTHORIZED` | **Alias hoặc re-export tương đương**. Mã đóng WebSocket khi xác thực thất bại 3000; middleware JWT HTTP không xác thực scope WebSocket. Cùng tên được re-export ở xime.adapters.web. | — |

## `xime.core.bootstrap`

Hướng dẫn: [multi-process.md](multi-process.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `StartupOrchestrator` | **Hạ tầng framework**. Pipeline bootstrap DI/vòng đời/primary do Application sở hữu; không tự khởi chạy orchestrator thứ hai. | — |

`Application.use_logging_console(handler: logging.Handler) -> Application` bàn giao
console trước startup; YAML quản lý công tắc/mức khai riêng, giữ formatter/filter.
Xem [logging](logging.md).

## `xime.core.config`

Hướng dẫn: [configuration.md](configuration.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `YamlConfigLoader` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. load() đọc application.yml và overlay được chọn; không trộn biến profile với environments trong một file. | `YamlConfigLoader(resources_dir: 'str \| Path' = 'resources') -> 'None'` |
| `detect_env` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Đọc XIME_ENV trước APP_ENV, trả None nếu chưa đặt; chúng chọn file profile, không chọn nhánh local/server. | `() -> 'str \| None'` |
| `LoggingConfig` | Cấu hình console/file, level/format/datefmt cũ, service_name và hai sink độc lập. Xem [logging](logging.md). | `LoggingConfig(...)` |
| `ConsoleLoggingConfig` | Công tắc console và mức kế thừa logging.level nếu bỏ trống. | `ConsoleLoggingConfig(enabled=True, level=None)` |
| `FileLoggingConfig` | File opt-in, path/format, xoay, trần queue/record và timeout dừng. | `FileLoggingConfig(enabled=False, ...)` |

## `xime.core.container`

Hướng dẫn: [core-concepts.md](core-concepts.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `XimeContainer` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. API scan/bind/build/get cấp thấp cho tích hợp/kiểm thử; service thông thường dùng Application và constructor injection. | `XimeContainer() -> None` |

## `xime.core.contract`

Hướng dẫn: [socket-adapter.md](socket-adapter.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `ENDPOINT_ATTR` | **Hạ tầng framework**. Thuộc tính metadata dành riêng cho decorator/scanner endpoint; không tự ghi bằng tay. | — |
| `EndpointInfo` | **Hạ tầng framework**. Tên/loại endpoint được decorator command/upload/download gắn vào; scanner đọc bản ghi này. | — |
| `EndpointKind` | **Hạ tầng framework**. Enum khai báo trung tính giao thức trong metadata endpoint; dùng decorator thay vì ghép metadata thủ công. | — |
| `ControllerScanner` | **Hạ tầng framework**. Tìm controller contract trong package cho startup gRPC/socket; framework quản lý thứ tự quét và đăng ký. | — |

## `xime.core.event`

Hướng dẫn: [multi-process.md](multi-process.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `EventBusConfig` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Chính sách áp lực event trong một tiến trình: max_pending, never_drop; khai bằng configure_event_bus trước startup. | `EventBusConfig(max_pending: 'int \| None' = 10000, never_drop: 'frozenset[type]' = ...) -> None` |
| `event_bus_registry` | **Hạ tầng framework**. Kho cấu hình event bus lúc bootstrap; ghi qua configure_event_bus. | — |

## `xime.core.exception`

Hướng dẫn: [core-concepts.md](core-concepts.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `XimeException` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Lỗi gốc framework; ưu tiên lớp con cụ thể khi chọn cách phục hồi. | — |
| `StartupException` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Ứng dụng không thể khởi động an toàn; sửa cấu hình/đồ thị được báo trước khi phục vụ. | — |
| `MissingTypeHintException` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Không phân giải được type hint constructor; bảo đảm type import được và sửa forward reference. | `MissingTypeHintException(class_name: str, detail: str)` |
| `MissingImplementationException` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Protocol chưa có hiện thực đăng ký; quét package hiện thực và khai binding tường minh. | `MissingImplementationException(interface_name: str)` |
| `MissingBindingException` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Có một ứng viên phù hợp cấu trúc nhưng chưa bind; khai binding Protocol để giữ kiểm tra fail-fast. | `MissingBindingException(interface_name: str, candidate_name: str)` |
| `UnregisteredDependencyException` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Dependency concrete chưa được quét/cấp; đăng ký type đó thay vì bỏ qua DI. | `UnregisteredDependencyException(dependent_name: str, dependency_name: str, hint: str \| None = None)` |
| `MultipleImplementationException` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Có nhiều ứng viên nhưng chưa chọn tường minh; khai binding hoặc dynamic binding đúng cấu hình. | `MultipleImplementationException(interface_name: str, candidates: list[str])` |
| `CircularDependencyException` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Chu trình dependency constructor; tách chu trình đồ thị thay vì trì hoãn bằng biến global ẩn. | `CircularDependencyException(cycle: list[str])` |
| `BindingValidationException` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Hiện thực được chọn thiếu method của Protocol; sửa hiện thực hoặc binding. | `BindingValidationException(interface_name: str, implementation_name: str, missing_methods: list[str])` |
| `InvalidOrderRuleException` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. dependency.order trỏ tới class chưa đăng ký; đăng ký class hoặc bỏ luật cũ. | `InvalidOrderRuleException(unknown_classes: str)` |
| `OrderRuleCycleException` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Thứ tự startup tường minh tạo chu trình; bỏ các ràng buộc thứ tự xung đột. | `OrderRuleCycleException(cycle: list[str])` |
| `SecurityException` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Lỗi gốc bảo mật runtime; adapter ánh xạ lỗi xác thực/phân quyền cụ thể theo giao thức. | — |
| `AuthorizationException` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Danh tính đã xác thực thiếu quyền yêu cầu; trả từ chối truy cập, không lặp lại xác thực. | `AuthorizationException(message: str = 'Access denied')` |
| `SocketException` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Lỗi gốc runtime/giao thức Unix socket; vẫn yêu cầu nền tảng POSIX. | — |
| `ProtocolError` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Frame socket sai giao thức; sửa client protocol, không coi là lỗi kiểm dữ liệu nghiệp vụ. | — |
| `EndpointNotFound` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Tên endpoint socket chưa đăng ký; đồng bộ tên hợp đồng client/server. | `EndpointNotFound(endpoint: str)` |
| `SessionTimeout` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Session stream socket vượt timeout nhàn rỗi; chỉ retry nếu thao tác cho phép lặp an toàn. | `SessionTimeout(session_id: int)` |
| `SocketCommandError` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Client nhận frame ERROR với code/message từ server; xử lý theo code, không công khai chi tiết nội bộ. | `SocketCommandError(code: str, message: str)` |

## `xime.core.lifecycle`

Hướng dẫn: [multi-process.md](multi-process.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `RunOnce` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Protocol lifecycle async run_once: primary chạy một lần mỗi cụm trước khi phục vụ; việc định kỳ thuộc scheduler. | — |
| `LifecycleManager` | **Hạ tầng framework**. Sắp PostConstruct/PreDestroy cho instance đăng ký; Application quản lý để tránh chạy hook hai lần. | — |

## `xime.core.link`

Hướng dẫn: [process-link.md](process-link.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `LinkError` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Thao tác ProcessLink sai: kênh lạ, payload quá cỡ hoặc dùng sau đóng; sửa caller/cấu hình. | — |
| `LinkLayoutMismatch` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Bố cục vùng nhớ bus khác khuôn của tiến trình; không đọc byte bằng layout sai. | — |
| `link_registry` | **Hạ tầng framework**. Đăng ký kênh/handler lúc startup; khai qua configure_link, không đổi tùy tiện lúc chạy. | — |
| `INTERNAL_CHANNEL` | **Hạ tầng framework**. Kênh điều khiển __xime__ dành riêng; kênh ứng dụng không được dùng lại tên này. | — |
| `BoundHandler` | **Hạ tầng framework**. Bản ghi callback ProcessLink đã bind DI; framework thu từ method on_request/on_announce. | — |
| `collect` | **Hạ tầng framework**. Thu handler từ instance DI đã dựng; startup quản lý kiểm trùng kênh và gắn vào bus. | — |
| `Outcome` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Union kết quả ProcessLink.ask: Done, NoOwner, NoAnswer, Failed; xử lý tường minh cả bốn. | — |
| `LinkMessage` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Bản ghi quan sát channel/key/payload/sender; payload là byte ứng dụng, không phải danh tính tin cậy. | `LinkMessage(channel: 'str', key: 'str', payload: 'bytes', sender: 'int') -> None` |
| `LinkStats` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Ảnh chụp gần đúng từ link.stats(), gồm số liệu từng kênh; quan sát không thay đồng bộ. | `LinkStats(link_id: 'str', channels: 'tuple[ChannelStats, ...]') -> None` |
| `ChannelStats` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Dung lượng/mức dùng, tuổi dòng chưa đọc và số liệu reader của kênh; dùng chẩn đoán vận hành. | `ChannelStats(name: 'str', rows_total: 'int', rows_used: 'int', oldest_unread_age_ms: 'int \| None', readers: 'tuple[ReaderStats, ...]') -> None` |
| `ReaderStats` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. process_index, unread, missed theo reader; phục hồi tin mất tùy nghiệp vụ ứng dụng. | `ReaderStats(process_index: 'int', unread: 'int', missed: 'int') -> None` |
| `RawRow` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Dòng gỡ lỗi từ link.dump(channel); có thể chứa payload nhạy cảm, không công khai dump. | `RawRow(row: 'int', kind: 'str', key: 'str', sender: 'int', taker: 'int \| None', unread_by: 'tuple[int, ...]', payload: 'bytes', age_ms: 'int') -> None` |
| `sweep_orphans` | **Hạ tầng framework**. Dọn vùng nhớ lần chạy có tiến trình gốc đã chết; framework startup quản lý, không phải API dọn nghiệp vụ định kỳ. | — |

## `xime.core.metadata`

Hướng dẫn: [core-concepts.md](core-concepts.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `resolve_constructor_hints` | **Hạ tầng framework**. Helper reflection phân giải type DI; tên không phân giải được là lỗi startup, không phải dữ liệu nghiệp vụ thiếu. | — |
| `get_init_parameters` | **Hạ tầng framework**. Đọc tên tham số constructor để kiểm DI; framework dùng phát hiện thiếu hint. | — |
| `is_protocol` | **Hạ tầng framework**. Nhận diện khai báo Protocol cho DI; class hiện thực theo cấu trúc vẫn được dựng. | — |
| `is_abstract` | **Hạ tầng framework**. Đọc trạng thái abstract khi quét; không phải kiểm quyền hay năng lực nghiệp vụ. | — |
| `get_protocol_methods` | **Hạ tầng framework**. Lấy tên method Protocol để kiểm binding; khai binding tường minh, không sửa tập method. | — |

## `xime.core.refdata`

Hướng dẫn: [refdata.md](refdata.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `RefDataArena` | **Hạ tầng framework**. Sở hữu block vùng nhớ và quyền ghi primary của một lần chạy; Application tạo/gắn/đóng arena. | — |
| `RefDataLayout` | **Hạ tầng framework**. Tính offset byte từ max_bytes; chi tiết bố cục vùng nhớ, không phải định dạng lưu trữ app. | — |
| `RefDataStats` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Quan sát gần đúng từ table.stats(): generation, served_generation, stale, fill_ratio; dùng read() để lấy dữ liệu thật. | `RefDataStats(name: 'str', generation: 'int', served_generation: 'int', written_at_ms: 'int \| None', used_bytes: 'int', limit_bytes: 'int', segments: 'int', writer: 'int \| None', stale: 'bool') -> None` |
| `TableSpec` | **Hạ tầng framework**. Tên/dung lượng bảng trích trước DI; khai bảng bằng configure_refdata thay vì tự dựng spec. | — |
| `refdata_registry` | **Hạ tầng framework**. Đăng ký bảng lúc bootstrap; điểm vào cấu hình là configure_refdata. | — |
| `specs_of` | **Hạ tầng framework**. Trích TableSpec từ class RefData đã đăng ký; Application dùng để dựng vùng nhớ. | — |
| `block_name` | **Hạ tầng framework**. Sinh tên vùng nhớ từ cặp lần chạy/bảng; không phải định danh bền vững của ứng dụng. | — |
| `new_run_id` | **Hạ tầng framework**. Mã lần chạy bộ cấp phát từ PID và phần ngẫu nhiên; framework quản lý vòng đời. | — |
| `DEFAULT_MAX_BYTES` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Dung lượng bảng RefData mặc định 65536 byte; đổi max_bytes khi khai class bảng nếu cần. | — |
| `MAX_SPINS` | **Hạ tầng framework**. Trần lặp đọc snapshot RefData, hiện 100; cơ chế nội bộ, không phải khóa YAML để chỉnh. | — |
| `RefDataLayoutMismatch` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Layout bảng dùng chung không khớp tiến trình; đồng bộ lần chạy/phiên bản, không đọc byte không tương thích. | — |
| `RefDataClosedError` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Truy cập bảng sau khi arena đóng; sửa quyền sở hữu vòng đời, không mở lại vùng nhớ từ handler. | — |
| `RefDataError` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Lỗi gốc kho tham chiếu dùng chung; phân biệt lỗi vòng đời/layout với số liệu quan sát cũ. | — |
| `RefDataTornError` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Không lấy được snapshot nhất quán sau số lần thử có trần; caller retry theo chính sách khả dụng. | — |

## `xime.core.security`

Hướng dẫn: [starters.md](starters.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `credential_type` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Slot bảo mật theo task với get/set; mô tả loại credential đã xác thực, được dọn ở biên request. | — |
| `permissions` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Slot quyền theo task; AuthorizationManager quyết định ngữ nghĩa quyền, slot này chỉ giữ dữ liệu. | — |
| `authenticate` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Đặt field bảo mật sau xác minh; field bỏ qua giữ nguyên, None tường minh xóa field; hàm không tự xác minh credential. | `(*, identity=..., credentials=..., credential_type=..., permissions=...) -> None` |
| `clear_security` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Xóa mọi field bảo mật của task hiện tại; code transport tự viết phải gọi trong finally. | `() -> 'None'` |
| `CredentialType` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Enum tiện ích PASSWORD, TOKEN, API_KEY, OAUTH2, CERTIFICATE; ứng dụng có thể dùng enum riêng. | — |

## `xime.core.shared`

Hướng dẫn: [multi-process.md](multi-process.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `MP_CONTEXT` | **Hạ tầng framework**. Context multiprocessing chung của framework; không thay hoặc trộn chiến lược tạo tiến trình. | — |
| `ghi_o` | **Hạ tầng framework**. Hàm ghi bản ghi vùng nhớ tránh cửa sổ zero-fill của pack_into; để framework quản lý ghi layout. | — |
| `view_of` | **Hạ tầng framework**. Helper thu block thành memoryview; không giữ view sau khi block đóng. | — |

## `xime.core.transaction`

Hướng dẫn: [transaction.md](transaction.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `ReadOnlyContext` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Protocol context manager async do ReadOnlyManager trả về; mượn session bao ngoài mà không commit/đóng nó. | — |

## `xime.starters.lmdb`

Hướng dẫn: [store.md](store.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `DEFAULT_TTL` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. TTL mặc định Store LMDB là 3600 giây; khai TTL class tường minh khi thời hạn nghiệp vụ khác. | — |
| `store_registry` | **Hạ tầng framework**. Theo dõi instance Store trong tiến trình cho cleanup; đăng ký theo lúc dựng và vòng đời Store. | — |

## `xime.starters.mail`

Hướng dẫn: [starters.md](starters.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `SmtpMailService` | **API ứng dụng hoặc kiểu cấu hình/kết quả**. Backend SMTP của MailService dùng YAML mail; scan/bind service; mỗi lần gửi dùng aiosmtplib, không có pool kết nối lúc startup. | `SmtpMailService(config: 'RuntimeConfig') -> 'None'` |

## `xime.starters.sqlalchemy`

Hướng dẫn: [transaction.md](transaction.md).

| Tên | Phân loại và hợp đồng | Chữ ký |
|---|---|---|
| `AsyncEngineProvider` | **Hạ tầng framework**. Engine SQLAlchemy và dispose do DI quản lý; inject dịch vụ session/transaction thay vì tạo thêm provider. | — |

## Ví dụ và giới hạn hành vi

### TLS reload

```python
from xime.core.bootstrap import Application
from xime.adapters.web import TlsReloadResult, reload_tls

async def refresh_certificate(app: Application) -> bool:
    result: TlsReloadResult = await reload_tls(app, server_id="default")
    return result.succeeded
```

Listener phải được cấu hình TLS từ trước. Kết quả thành công xác nhận nạp context tại các worker đang phục vụ, không xác minh hostname/hạn cert thay mọi client. certificate_fingerprint hash byte file PEM; cách định dạng hoặc chứng thư hợp lệ khác nhau có thể cho giá trị khác. Không truyền byte private key giữa worker. Endpoint management vẫn chỉ loopback và đi theo primary.

### Security context

```python
from xime.core.security import (
    CredentialType, authenticate, clear_security, credential_type, permissions,
)

def invoke_verified_handler(verified_identity, verified_permissions, handler):
    authenticate(
        identity=verified_identity,
        credential_type=CredentialType.TOKEN,
        permissions=verified_permissions,
    )
    try:
        return handler(credential_type.get(), permissions.get())
    finally:
        clear_security()
```

Chỉ gọi sau khi đã xác minh credential. authenticate chỉ cập nhật field được truyền, không tự kiểm token hay quyết định quyền. Ví dụ đồng bộ này dọn context task của transport tự viết bằng finally; handler async phải được await bên trong cùng khối bảo vệ. Middleware chuẩn của framework đã tự quản lý cleanup context.

### Protobuf scalar markers

```python
from typing import Annotated
from pydantic import BaseModel
from xime.adapters.grpc.codefirst import ProtoInt64, ProtoUInt32, ProtoSInt32, ProtoSInt64

class CounterMessage(BaseModel):
    total: Annotated[int, ProtoInt64]
    device: Annotated[int, ProtoUInt32]
    delta: Annotated[int, ProtoSInt32]
    long_delta: Annotated[int, ProtoSInt64]
```

Marker chọn scalar trên wire. Giữ số field trong lock và tương thích với client cũ; đổi int64 sang sint64 là đổi hợp đồng wire dù cả hai annotation Python đều chứa int.

### Modbus codecs

```python
from xime.adapters.modbus import Holding, decode_field, device, encode_field, get_device_info

@device(unit=1)
class Meter:
    reading: int = Holding(0, type="uint16")

info = get_device_info(Meter)
assert info is not None
registers = encode_field(Meter.reading, info, 42)
assert decode_field(Meter.reading, info, registers) == 42
```

Ví dụ cần xime[modbus] và không giao tiếp thiết bị thật. Service thông thường dùng ModbusClient; codec trực tiếp hữu ích cho fixture giao thức hoặc tích hợp đã có register thô. Không bật allow_read_only cho lệnh ghi phía client.

### SMTP binding

```python
from xime.core.config import BindingConfig
from xime.starters.mail import MailService, SmtpMailService

dependency = BindingConfig()
dependency.scan("xime.starters.mail")
dependency.bind({MailService: SmtpMailService})
```

Đặt các khai báo tương đương trong config/dependency.py hiện có của ứng dụng; BindingConfig riêng ở đây minh họa binding. Khai host/port và xác thực mail trong YAML runtime. Thiếu credential hoặc server không sẵn sàng vẫn gây lỗi gửi; binding không phải phép kiểm giao thư.

### Xử lý exception

```python
from xime.core.exception import StartupException, XimeException

async def start_or_report(app, report):
    try:
        await app.start()
    except StartupException as error:
        report(type(error).__name__)
        raise
    except XimeException:
        raise
```

Startup lỗi phải tiếp tục là lỗi. Ghi lỗi phù hợp vào log được bảo vệ rồi sửa cấu hình/DI; không tiếp tục phục vụ app khởi tạo dở. Lỗi xác thực, phân quyền, protocol và kết nối có chính sách phục hồi khác nhau; không gộp mọi XimeException vào một vòng retry chung.

## `xime.observability`

Guide: [grpc-handshake-logging.md](grpc-handshake-logging.md).

| Name | Contract | Signature |
|---|---|---|
| `GrpcHandshakeLoggingConfig` | Process-start native tracing switch, level, rate/queue/record limits. Default disabled. | `GrpcHandshakeLoggingConfig(...)` |
| `GrpcHandshakeLoggingStats` | Immutable cumulative process counters, including loss and parse/flush errors. | `GrpcHandshakeLoggingStats(...)` |
| `prepare_grpc_handshake_logging` | Call before grpc imports in every process; off allocates nothing; on has process lifetime. | `(*, resources_dir: str = "resources", runtime: RuntimeConfig \| None = None) -> None` |
| `grpc_handshake_logging_stats` | Snapshot of local counters; off returns zeros without setup. | `() -> GrpcHandshakeLoggingStats` |
