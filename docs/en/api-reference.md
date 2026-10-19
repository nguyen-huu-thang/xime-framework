# API reference and ownership

[Documentation index](../README.md) · [Tiếng Việt](../vn/api-reference.md)

This reference complements the task guides. It covers exported names that previously lacked a reference in at least one language, and distinguishes application APIs, aliases, and framework infrastructure. An export alone does not promise a stable extension point. In particular, scanners, builders, registries and adapter internals belong to bootstrap; configure an adapter through its documented configuration functions and controller decorators.

Configuration/result types describe values parsed from YAML or returned by operations. Listing their constructor does not mean an application should construct every type. Infrastructure is included to explain ownership and diagnostics, rather than to recommend calling it from request handlers. Optional transports and starters still require their corresponding installation extras.

## `xime`

Guide: [core-concepts.md](core-concepts.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `__version__` | **Application API or configuration/result type**. Installed package version; it does not identify a development checkout commit. | — |

## `xime.adapters.grpc`

Guide: [grpc-codefirst.md](grpc-codefirst.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `configure_grpc_interceptors` | **Application API or configuration/result type**. Register interceptor instances before startup; framework context/error interceptors remain outermost. | `(interceptors: 'list[grpc.aio.ServerInterceptor]') -> 'None'` |

## `xime.adapters.grpc.client`

Guide: [grpc-client.md](grpc-client.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `ClientGenResult` | **Application API or configuration/result type**. SDK generation result: written files and skipped_methods; inspect skips before shipping the SDK. | `ClientGenResult(written: 'list[str]' = ..., skipped_methods: 'list[str]' = ...) -> None` |
| `GrpcClientConfig` | **Application API or configuration/result type**. Settings for grpc.clients.<id>: target host/port, deadlines, TLS and keepalive; configure through YAML. | — |
| `GrpcClientTlsConfig` | **Application API or configuration/result type**. Outbound TLS settings: CA, client certificate/key and dynamic rotation; enabling TLS does not choose an identity for you. | `GrpcClientTlsConfig(*, enabled: bool = False, dynamic: bool = False, ca_file: str \| None = None, cert_file: str \| None = None, key_file: str \| None = None, server_id: str = 'default') -> None` |
| `GrpcKeepaliveConfig` | **Application API or configuration/result type**. Outbound HTTP/2 ping policy; time_ms=0 disables pings; select intervals accepted by the peer. | `GrpcKeepaliveConfig(*, time_ms: int = 0, timeout_ms: int = 20000, permit_without_calls: bool = False) -> None` |
| `SdkRuntime` | **Framework infrastructure**. Generated SDK implementation: loads descriptors and marshals calls; use the generated typed client rather than constructing this runtime. | — |
| `generate_client_sdk` | **Application API or configuration/result type**. Build a typed SDK from a proto directory; out_dir is written; optional package metadata names the generated distribution. | `(proto_dir: 'str', out_dir: 'str', package: 'str \| None' = None, package_version: 'str' = '0.1.0') -> 'ClientGenResult'` |

## `xime.adapters.grpc.codefirst`

Guide: [grpc-codefirst.md](grpc-codefirst.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `CodeFirstConfig` | **Framework infrastructure**. Registration record owned by configure_grpc_codefirst; describes packages, output and lock settings, not a DI service. | — |
| `codefirst_registry` | **Framework infrastructure**. CLI/adapter registration store; populate through configure_grpc_codefirst and avoid mutating it after startup. | — |
| `build_proto_files` | **Framework infrastructure**. Generation pipeline with a LockFile; the CLI owns lock consistency and output handling; prefer xime grpc generate/check. | — |
| `GenerateResult` | **Application API or configuration/result type**. Code-first generation result with written and protoc_outputs paths; inspect it when driving generation from a tool. | `GenerateResult(written: 'list[str]' = ..., protoc_outputs: 'list[str]' = ...) -> None` |
| `CheckResult` | **Application API or configuration/result type**. Code-first check result: up_to_date, stale and missing; a stale or missing output requires regeneration. | `CheckResult(up_to_date: 'bool', stale: 'list[str]' = ..., missing: 'list[str]' = ...) -> None` |
| `ProtoInt64` | **Application API or configuration/result type**. Annotated integer marker selecting protobuf int64; changes wire representation, not Python int range checks. | `ProtoInt64()` |
| `ProtoUInt32` | **Application API or configuration/result type**. Annotated integer marker selecting unsigned protobuf uint32; choose field width to match the external contract. | `ProtoUInt32()` |
| `ProtoSInt32` | **Application API or configuration/result type**. Annotated integer marker selecting zig-zag sint32 for signed values near zero. | `ProtoSInt32()` |
| `ProtoSInt64` | **Application API or configuration/result type**. Annotated integer marker selecting zig-zag sint64; keep existing field numbers and wire types compatible. | `ProtoSInt64()` |

## `xime.adapters.grpc.interceptors`

Guide: [grpc-codefirst.md](grpc-codefirst.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `configure_grpc_interceptors` | **Alias or equivalent re-export**. Re-export of xime.adapters.grpc.configure_grpc_interceptors; same registration and ordering, not a second interceptor chain. | `(interceptors: 'list[grpc.aio.ServerInterceptor]') -> 'None'` |
| `grpc_interceptor_registry` | **Framework infrastructure**. Bootstrap store for interceptors/error mappings; configure through the public configuration functions, not reset during service execution. | — |
| `RequestContextInterceptor` | **Framework infrastructure**. Built-in gRPC request-context lifecycle; installed by the adapter, so adding it again duplicates context handling. | — |

## `xime.adapters.grpc.routing`

Guide: [grpc-codefirst.md](grpc-codefirst.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `grpc_service_registry` | **Framework infrastructure**. Bindings/packages consumed by GrpcAdapter; register via configure_grpc rather than maintaining a second registry. | — |

## `xime.adapters.grpc.tls`

Guide: [grpc-codefirst.md](grpc-codefirst.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `grpc_tls_registry` | **Framework infrastructure**. Certificate-provider registration owned by configure_grpc_tls; not a certificate cache for business code. | — |

## `xime.adapters.modbus`

Guide: [modbus.md](modbus.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `Area` | **Application API or configuration/result type**. Enum for COIL, DISCRETE, HOLDING and INPUT; addresses belong to separate spaces and cannot be merged across areas. | — |
| `DataType` | **Application API or configuration/result type**. Modbus scalar type enum used by field declarations/codecs; its register width determines read/write size. | — |
| `DeviceInfo` | **Application API or configuration/result type**. Metadata for one decorated device: class, unit, fields and byte/word order; obtain through get_device_info. | `DeviceInfo(cls: 'type', unit: 'int', fields: 'dict[str, ModbusField]', byte_order: 'ByteOrder', word_order: 'WordOrder') -> 'None'` |
| `ModbusField` | **Application API or configuration/result type**. Field descriptor behind Holding/Input/Coil/Discrete; use those declarations to select an area explicitly. | — |
| `get_device_info` | **Application API or configuration/result type**. Read device metadata from a class or instance; returns None for undecorated input. | `(target: 'Any') -> 'DeviceInfo \| None'` |
| `ModbusConnection` | **Framework infrastructure**. Live pymodbus connection holder managed by the adapter; inject ModbusClient for operations instead of owning a second connection. | — |
| `ModbusConfig` | **Application API or configuration/result type**. Resolved modbus.devices.<id> client settings, including host, unit, timeout and byte/word order. | — |
| `ModbusServerConfig` | **Application API or configuration/result type**. Settings for modbus.server host/port; listener endpoint overrides still belong to process topology. | `ModbusServerConfig(*, host: str = '0.0.0.0', port: int = 5020) -> None` |
| `modbus_registry` | **Framework infrastructure**. Device/server registration consumed during startup; use configure_modbus to populate it. | — |
| `DEFAULT_DEVICE` | **Application API or configuration/result type**. Default Modbus target ID, default; it is a configuration name, not a physical unit address. | — |
| `decode_field` | **Application API or configuration/result type**. Decode one field from raw registers/bits using DeviceInfo order, scaling and offset. | `(field: 'ModbusField', info: 'DeviceInfo', raw: 'Any') -> 'Any'` |
| `encode_field` | **Application API or configuration/result type**. Encode a field to registers/bits; read-only areas reject writes unless the explicit server-side override is used. | `(field: 'ModbusField', info: 'DeviceInfo', value: 'Any', *, allow_read_only: 'bool' = False) -> 'list[Any]'` |
| `decode_device` | **Application API or configuration/result type**. Construct a device value from per-area address/value payloads; payloads must cover the declared fields. | `(info: 'DeviceInfo', payloads: 'dict[Area, dict[int, Any]]') -> 'Any'` |
| `ModbusError` | **Application API or configuration/result type**. Base exception for Modbus adapter operations; catch narrower connection/codec errors where recovery differs. | — |
| `ReadCommand` | **Application API or configuration/result type**. Read-plan item (area, address, count); one command never spans different address spaces. | `ReadCommand(area: 'Area', address: 'int', count: 'int') -> None` |

## `xime.adapters.modbus.routing`

Guide: [modbus.md](modbus.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `ModbusControllerScanner` | **Framework infrastructure**. Discovers decorated Modbus controllers at startup; configure scanned packages instead of invoking this from a handler. | — |
| `ModbusRouteBuilder` | **Framework infrastructure**. Binds discovered handlers to DI instances and builds poll groups; adapter startup owns this work. | — |
| `PollGroup` | **Framework infrastructure**. One polling loop's model, interval and handlers; generated by routing, not a business scheduler contract. | — |
| `ResolvedPoll` | **Framework infrastructure**. A poll callback bound to its controller; construct handlers with decorators, not this routing record. | — |
| `ResolvedChangeWatch` | **Framework infrastructure**. Resolved change callback/deadband record; generated from on_change declarations. | — |

## `xime.adapters.mqtt`

Guide: [mqtt.md](mqtt.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `MqttConnection` | **Framework infrastructure**. Live aiomqtt client holder with adapter-owned reconnect/lifecycle; use MqttPublisher to publish. | — |
| `MqttConfig` | **Application API or configuration/result type**. Broker settings under mqtt, including credentials, client ID and keepalive; configuration does not connect on its own. | — |
| `mqtt_registry` | **Framework infrastructure**. MQTT registration state shared by adapter/publisher; use configure_mqtt and avoid changing it while connected. | — |

## `xime.adapters.mqtt.routing`

Guide: [mqtt.md](mqtt.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `MqttRouteBuilder` | **Framework infrastructure**. Builds the MQTT dispatch table after DI; adapter startup owns validation and subscription setup. | — |
| `ResolvedMqttRoute` | **Framework infrastructure**. Bound handler plus topic, subscription and RPC model metadata; obtained from the route builder. | — |
| `MqttControllerScanner` | **Framework infrastructure**. Scans configured controller packages; use configure_mqtt rather than a scanner in request code. | — |

## `xime.adapters.opcua`

Guide: [opcua.md](opcua.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `OpcuaNode` | **Alias or equivalent re-export**. Descriptor also exported as Node; use Node in declarative node models; both names refer to the same implementation. | `OpcuaNode(node_id: 'str', *, writable: 'bool' = True, default: 'Any' = None) -> 'None'` |
| `NodeModelInfo` | **Application API or configuration/result type**. Metadata for a node model: class, node descriptors and optional server namespace; obtain from the metadata helpers. | `NodeModelInfo(cls: 'type', nodes: 'dict[str, OpcuaNode]', namespace: 'str \| None')` |
| `get_node_model_info` | **Application API or configuration/result type**. Return node metadata or None when the class/instance is not a node model. | `(target: 'Any') -> 'NodeModelInfo \| None'` |
| `require_node_model_info` | **Application API or configuration/result type**. Return node metadata or raise an actionable error when the model is undecorated. | `(target: 'Any') -> 'NodeModelInfo'` |
| `OpcuaConnection` | **Framework infrastructure**. Adapter-owned asyncua connection holder; inject OpcuaClient rather than opening another managed session. | — |
| `OpcuaConfig` | **Application API or configuration/result type**. Resolved opcua.servers.<id> endpoint/security settings; certificate paths belong to the selected server configuration. | — |
| `OpcuaServerConfig` | **Application API or configuration/result type**. opcua.server endpoint, name and security settings; plain None security remains an explicit supported choice. | — |
| `opcua_registry` | **Framework infrastructure**. Node/server registration consumed by the adapter; use configure_opcua during configuration imports. | — |
| `DEFAULT_SERVER` | **Application API or configuration/result type**. Default OPC UA target ID, default; it selects a named server configuration. | — |
| `SECURITY_MODES` | **Application API or configuration/result type**. Supported names: None, Sign, SignAndEncrypt; use normalize_mode to validate external text. | — |
| `normalize_mode` | **Application API or configuration/result type**. Normalize a supported security mode case-insensitively; reject unknown modes instead of silently selecting None. | `(value: 'str \| None') -> 'str'` |
| `build_security_string` | **Application API or configuration/result type**. Build asyncua security parameters from mode and certificate/key paths; returns None for unsecured mode. | `(mode: 'str', certificate: 'str \| None', private_key: 'str \| None') -> 'str \| None'` |
| `OpcuaError` | **Application API or configuration/result type**. Base exception for OPC UA adapter operations; use narrower errors for retry or validation decisions. | — |

## `xime.adapters.socket`

Guide: [socket-adapter.md](socket-adapter.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `ClientUpload` | **Application API or configuration/result type**. Context manager returned by SocketClient.upload; write chunks and finish for the response, rather than constructing it manually. | `ClientUpload(client: 'SocketClient', session_id: 'int', endpoint: 'str', request: 'BaseModel') -> 'None'` |
| `SocketServerConfig` | **Application API or configuration/result type**. Unix socket path, POSIX permissions/ownership, peer UID allowlist and timeout settings; POSIX only. | — |

## `xime.adapters.socket.routing`

Guide: [socket-adapter.md](socket-adapter.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `ResolvedEndpoint` | **Framework infrastructure**. Socket dispatch record with request/response models and stream parameter; produced from endpoint decorators. | — |
| `SocketEndpointBuilder` | **Framework infrastructure**. Binds socket endpoint declarations to DI objects at adapter startup; not a service extension point. | — |

## `xime.adapters.web`

Guide: [configuration.md](configuration.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `ServerTlsConfig` | **Application API or configuration/result type**. HTTP TLS certificate/key, client CA and cipher settings; neither certificate nor key means intentional HTTP. | — |
| `WebServerConfig` | **Application API or configuration/result type**. webserver listener defaults, SSL/reload and management policy; server is the compatibility alias. | `WebServerConfig(*, host: str = '0.0.0.0', port: int = 8080, ssl: WebServerTlsConfig = ..., management: ManagementServerConfig = ...) -> None` |
| `TlsReloadResult` | **Application API or configuration/result type**. Aggregate outcome, workers and missing_workers; use succeeded, which requires nonempty successful ACKs and no missing workers. | `TlsReloadResult(server_id: 'str', outcome: 'str', workers: 'tuple[TlsWorkerResult, ...]', missing_workers: 'tuple[int, ...]' = ()) -> None` |
| `TlsWorkerResult` | **Application API or configuration/result type**. Per-worker outcome and certificate_fingerprint; fingerprint hashes file bytes, not normalized DER or hostname/expiry validation. | `TlsWorkerResult(worker_index: 'int', outcome: 'str', certificate_fingerprint: 'str \| None' = None, detail: 'str \| None' = None) -> None` |
| `BEARER_SUBPROTOCOL_PREFIX` | **Application API or configuration/result type**. WebSocket token entry prefix xime.bearer.; also offer a real application subprotocol and never echo the token entry. | — |
| `WS_UNAUTHORIZED` | **Application API or configuration/result type**. WebSocket authentication rejection code 3000; HTTP JWT middleware does not authenticate WebSocket scopes. | — |

## `xime.adapters.web.files`

Guide: [file-storage.md](file-storage.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `DEFAULT_MAX_BYTES` | **Application API or configuration/result type**. Default upload cap of 32 MiB for save_upload; pass max_bytes explicitly when a route needs a different limit. | — |

## `xime.adapters.web.openapi`

Guide: [configuration.md](configuration.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `ApiKey` | **Application API or configuration/result type**. OpenAPI API-key scheme metadata (name, location, scheme_name); it documents a credential and does not authenticate requests. | `ApiKey(name: 'str', location: "Literal['header', 'query', 'cookie']" = 'header', scheme_name: 'str' = 'ApiKeyAuth') -> None` |
| `SecurityScheme` | **Application API or configuration/result type**. Protocol for OpenAPI security declarations; implementations supply schema metadata rather than authorization logic. | — |

## `xime.adapters.web.ws`

Guide: [websocket.md](websocket.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `BEARER_SUBPROTOCOL_PREFIX` | **Alias or equivalent re-export**. WebSocket token entry prefix xime.bearer.; also offer a real application subprotocol and never echo the token entry. Equivalent re-export of the name available from xime.adapters.web. | — |
| `WS_UNAUTHORIZED` | **Alias or equivalent re-export**. WebSocket authentication rejection code 3000; HTTP JWT middleware does not authenticate WebSocket scopes. Equivalent re-export of the name available from xime.adapters.web. | — |

## `xime.core.bootstrap`

Guide: [multi-process.md](multi-process.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `StartupOrchestrator` | **Framework infrastructure**. Application-owned DI/lifecycle/primary bootstrap pipeline; use Application rather than starting a second orchestrator. | — |

`Application.use_logging_console(handler: logging.Handler) -> Application` registers
a custom console before startup; YAML owns switches/explicit levels and Xime
retains the formatter/filters. See [logging](logging.md).

## `xime.core.config`

Guide: [configuration.md](configuration.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `YamlConfigLoader` | **Application API or configuration/result type**. load() reads application.yml and selected overlays; do not combine profile environment variables with single-file environments. | `YamlConfigLoader(resources_dir: 'str \| Path' = 'resources') -> 'None'` |
| `detect_env` | **Application API or configuration/result type**. Read XIME_ENV before APP_ENV, returning None when unset; these select legacy profile files, not local/server branches. | `() -> 'str \| None'` |
| `LoggingConfig` | Root console/file ownership, legacy level/format/datefmt, optional service_name and independent sink models. See [logging](logging.md). | `LoggingConfig(...)` |
| `ConsoleLoggingConfig` | Console switch and optional level inheriting logging.level. | `ConsoleLoggingConfig(enabled=True, level=None)` |
| `FileLoggingConfig` | Opt-in file path/format, rotation, bounded queue/record size and shutdown limits. | `FileLoggingConfig(enabled=False, ...)` |

## `xime.core.container`

Guide: [core-concepts.md](core-concepts.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `XimeContainer` | **Application API or configuration/result type**. Low-level scan/bind/build/get API for embedding/testing; normal services use Application and constructor injection. | `XimeContainer() -> None` |

## `xime.core.contract`

Guide: [socket-adapter.md](socket-adapter.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `ENDPOINT_ATTR` | **Framework infrastructure**. Reserved metadata attribute used by endpoint decorators/scanners; do not write it by hand. | — |
| `EndpointInfo` | **Framework infrastructure**. Declared endpoint name/kind attached by command/upload/download decorators; scanners consume it. | — |
| `EndpointKind` | **Framework infrastructure**. Transport-neutral declaration enum used in endpoint metadata; prefer endpoint decorators to manual metadata assembly. | — |
| `ControllerScanner` | **Framework infrastructure**. Core contract package discovery used by gRPC/socket startup; framework-owned scan order controls registration. | — |

## `xime.core.event`

Guide: [multi-process.md](multi-process.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `EventBusConfig` | **Application API or configuration/result type**. In-process event backpressure policy: max_pending and never_drop; set via configure_event_bus before startup. | `EventBusConfig(max_pending: 'int \| None' = 10000, never_drop: 'frozenset[type]' = ...) -> None` |
| `event_bus_registry` | **Framework infrastructure**. Bootstrap store for event-bus configuration; configure_event_bus is the public write path. | — |

## `xime.core.exception`

Guide: [core-concepts.md](core-concepts.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `XimeException` | **Application API or configuration/result type**. Base of framework errors; prefer narrower subclasses when choosing recovery behavior. | — |
| `StartupException` | **Application API or configuration/result type**. Application cannot start safely; fix the reported configuration/graph before serving requests. | — |
| `MissingTypeHintException` | **Application API or configuration/result type**. A constructor hint cannot be resolved; make types importable and remove unresolved forward references. | `MissingTypeHintException(class_name: str, detail: str)` |
| `MissingImplementationException` | **Application API or configuration/result type**. A Protocol has no registered implementation; scan the implementation package and add an explicit binding. | `MissingImplementationException(interface_name: str)` |
| `MissingBindingException` | **Application API or configuration/result type**. One structural candidate exists but no binding; explicitly bind the Protocol to preserve fail-fast wiring. | `MissingBindingException(interface_name: str, candidate_name: str)` |
| `UnregisteredDependencyException` | **Application API or configuration/result type**. A concrete dependency was not scanned or supplied; register that type rather than bypassing DI. | `UnregisteredDependencyException(dependent_name: str, dependency_name: str, hint: str \| None = None)` |
| `MultipleImplementationException` | **Application API or configuration/result type**. Several candidates exist without an explicit choice; provide a binding or configured dynamic binding. | `MultipleImplementationException(interface_name: str, candidates: list[str])` |
| `CircularDependencyException` | **Application API or configuration/result type**. Constructor dependency cycle; break the graph cycle instead of delaying construction with hidden globals. | `CircularDependencyException(cycle: list[str])` |
| `BindingValidationException` | **Application API or configuration/result type**. A chosen implementation lacks Protocol methods; correct the implementation or binding. | `BindingValidationException(interface_name: str, implementation_name: str, missing_methods: list[str])` |
| `InvalidOrderRuleException` | **Application API or configuration/result type**. dependency.order references an unregistered class; register it or remove the obsolete rule. | `InvalidOrderRuleException(unknown_classes: str)` |
| `OrderRuleCycleException` | **Application API or configuration/result type**. Explicit startup ordering forms a cycle; remove the conflicting ordering constraints. | `OrderRuleCycleException(cycle: list[str])` |
| `SecurityException` | **Application API or configuration/result type**. Base for security runtime errors; transport adapters map concrete authentication/authorization failures. | — |
| `AuthorizationException` | **Application API or configuration/result type**. Authenticated identity lacks required permission; map to access denied rather than retrying authentication. | `AuthorizationException(message: str = 'Access denied')` |
| `SocketException` | **Application API or configuration/result type**. Base of Unix socket runtime/protocol errors; POSIX transport requirements still apply. | — |
| `ProtocolError` | **Application API or configuration/result type**. Malformed socket wire frame; repair the client protocol rather than treating it as business validation. | — |
| `EndpointNotFound` | **Application API or configuration/result type**. Socket endpoint name is unregistered; align client/server contract names. | `EndpointNotFound(endpoint: str)` |
| `SessionTimeout` | **Application API or configuration/result type**. Socket streaming session exceeded its idle timeout; decide whether the operation can be retried safely. | `SessionTimeout(session_id: int)` |
| `SocketCommandError` | **Application API or configuration/result type**. Client receives a server ERROR frame with code/message; branch on the code without exposing internal details. | `SocketCommandError(code: str, message: str)` |

## `xime.core.lifecycle`

Guide: [multi-process.md](multi-process.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `RunOnce` | **Application API or configuration/result type**. Lifecycle Protocol for async run_once: primary runs it once per cluster before serving; recurring work belongs in a scheduler. | — |
| `LifecycleManager` | **Framework infrastructure**. Orders PostConstruct/PreDestroy hooks for registered instances; Application owns it to avoid duplicate hooks. | — |

## `xime.core.link`

Guide: [process-link.md](process-link.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `LinkError` | **Application API or configuration/result type**. Invalid ProcessLink operation such as unknown channel, oversized payload or use after close; fix the caller/configuration. | — |
| `LinkLayoutMismatch` | **Application API or configuration/result type**. Shared bus memory layout differs from this process; do not interpret bytes using the wrong layout. | — |
| `link_registry` | **Framework infrastructure**. Startup registration for channels and handlers; populate with configure_link, not ad hoc runtime changes. | — |
| `INTERNAL_CHANNEL` | **Framework infrastructure**. Reserved __xime__ control channel; application channels must not reuse it. | — |
| `BoundHandler` | **Framework infrastructure**. DI-bound ProcessLink callback record; framework collects it from on_request/on_announce methods. | — |
| `collect` | **Framework infrastructure**. Collect handlers from built DI instances; startup owns duplicate-channel checks and attachment. | — |
| `Outcome` | **Application API or configuration/result type**. ProcessLink.ask return union: Done, NoOwner, NoAnswer or Failed; handle all four outcomes explicitly. | — |
| `LinkMessage` | **Application API or configuration/result type**. Observed channel/key/payload/sender record; payload is application bytes and is not a trusted identity. | `LinkMessage(channel: 'str', key: 'str', payload: 'bytes', sender: 'int') -> None` |
| `LinkStats` | **Application API or configuration/result type**. Approximate bus snapshot from link.stats(), containing per-channel counters; observation is not synchronization. | `LinkStats(link_id: 'str', channels: 'tuple[ChannelStats, ...]') -> None` |
| `ChannelStats` | **Application API or configuration/result type**. Per-channel capacity/usage, oldest unread age and reader snapshots; use for operational diagnosis. | `ChannelStats(name: 'str', rows_total: 'int', rows_used: 'int', oldest_unread_age_ms: 'int \| None', readers: 'tuple[ReaderStats, ...]') -> None` |
| `ReaderStats` | **Application API or configuration/result type**. Per-reader process_index, unread and missed counts; missed messages require application-specific recovery. | `ReaderStats(process_index: 'int', unread: 'int', missed: 'int') -> None` |
| `RawRow` | **Application API or configuration/result type**. Debug row returned by link.dump(channel); may contain sensitive application payload, so do not expose dumps publicly. | `RawRow(row: 'int', kind: 'str', key: 'str', sender: 'int', taker: 'int \| None', unread_by: 'tuple[int, ...]', payload: 'bytes', age_ms: 'int') -> None` |
| `sweep_orphans` | **Framework infrastructure**. Allocator cleanup for dead process-run memory; framework startup owns it, not a recurring business cleanup API. | — |

## `xime.core.metadata`

Guide: [core-concepts.md](core-concepts.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `resolve_constructor_hints` | **Framework infrastructure**. Reflection helper for DI type resolution; unresolved names are startup errors, not missing business data. | — |
| `get_init_parameters` | **Framework infrastructure**. Reflect constructor parameter names for DI validation; framework uses this to detect missing hints. | — |
| `is_protocol` | **Framework infrastructure**. Detect an actual Protocol declaration for DI; structural implementation classes remain instantiable. | — |
| `is_abstract` | **Framework infrastructure**. Reflect abstract class status while scanning; not an application authorization or capability check. | — |
| `get_protocol_methods` | **Framework infrastructure**. Extract Protocol method names for binding validation; use explicit bindings rather than editing the method set. | — |

## `xime.core.refdata`

Guide: [refdata.md](refdata.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `RefDataArena` | **Framework infrastructure**. Owns shared-memory blocks and primary write rights for one run; Application creates/attaches/closes the arena. | — |
| `RefDataLayout` | **Framework infrastructure**. Computes byte offsets from max_bytes; implementation detail of shared-memory layout, not an app storage format. | — |
| `RefDataStats` | **Application API or configuration/result type**. Approximate table.stats() observation including generation, served_generation, stale and fill_ratio; read() determines actual data. | `RefDataStats(name: 'str', generation: 'int', served_generation: 'int', written_at_ms: 'int \| None', used_bytes: 'int', limit_bytes: 'int', segments: 'int', writer: 'int \| None', stale: 'bool') -> None` |
| `TableSpec` | **Framework infrastructure**. Table name/capacity record extracted before DI; configure_refdata supplies tables rather than constructing specs manually. | — |
| `refdata_registry` | **Framework infrastructure**. Bootstrap table registration; configure_refdata is the supported configuration entry point. | — |
| `specs_of` | **Framework infrastructure**. Derive TableSpec records from registered RefData classes; Application uses them for shared-memory setup. | — |
| `block_name` | **Framework infrastructure**. Shared-memory name derivation for a run/table pair; not a persistent application identifier. | — |
| `new_run_id` | **Framework infrastructure**. Allocator run identifier derived from PID plus randomness; framework controls run lifetime. | — |
| `DEFAULT_MAX_BYTES` | **Application API or configuration/result type**. Default RefData table capacity of 65536 bytes; override max_bytes in the table class when needed. | — |
| `MAX_SPINS` | **Framework infrastructure**. Bounded RefData snapshot retry constant, currently 100; internal mechanism, not a YAML tuning key. | — |
| `RefDataLayoutMismatch` | **Application API or configuration/result type**. Shared table layout does not match this process; align the run/version rather than reading incompatible bytes. | — |
| `RefDataClosedError` | **Application API or configuration/result type**. Table accessed after arena closure; fix lifecycle ownership instead of reopening memory from a handler. | — |
| `RefDataError` | **Application API or configuration/result type**. Base exception for shared reference data; distinguish lifecycle/layout failures from stale observations. | — |
| `RefDataTornError` | **Application API or configuration/result type**. A consistent snapshot was unavailable after bounded retries; caller may retry according to its availability policy. | — |

## `xime.core.security`

Guide: [starters.md](starters.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `credential_type` | **Application API or configuration/result type**. Task-local security slot with get/set; describes verified credential kind and is cleared at the request boundary. | — |
| `permissions` | **Application API or configuration/result type**. Task-local permission slot; AuthorizationManager decides permission semantics, not this storage slot. | — |
| `authenticate` | **Application API or configuration/result type**. Set explicitly supplied security fields after verification; omitted fields remain unchanged and explicit None clears a field; this function does not verify credentials. | `(*, identity=..., credentials=..., credential_type=..., permissions=...) -> None` |
| `clear_security` | **Application API or configuration/result type**. Clear every security field in the current task; custom transport code must call it in finally. | `() -> 'None'` |
| `CredentialType` | **Application API or configuration/result type**. Convenience enum PASSWORD, TOKEN, API_KEY, OAUTH2, CERTIFICATE; applications may use their own enum. | — |

## `xime.core.shared`

Guide: [multi-process.md](multi-process.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `MP_CONTEXT` | **Framework infrastructure**. Framework multiprocessing context shared by bootstrap tools; do not replace it or mix process creation strategies. | — |
| `ghi_o` | **Framework infrastructure**. Internal shared-memory record writer avoiding pack_into's zero-fill window; keep layout writes inside the framework. | — |
| `view_of` | **Framework infrastructure**. Internal helper narrowing a block to memoryview; callers must not retain a view after block closure. | — |

## `xime.core.transaction`

Guide: [transaction.md](transaction.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `ReadOnlyContext` | **Application API or configuration/result type**. Async context-manager Protocol returned by ReadOnlyManager; borrow enclosing sessions without committing or closing them. | — |

## `xime.starters.lmdb`

Guide: [store.md](store.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `DEFAULT_TTL` | **Application API or configuration/result type**. LMDB Store default expiration of 3600 seconds; choose explicit class TTL when domain expiry differs. | — |
| `store_registry` | **Framework infrastructure**. Tracks process-local Store instances for framework cleanup; registration follows Store construction and lifecycle. | — |

## `xime.starters.mail`

Guide: [starters.md](starters.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `SmtpMailService` | **Application API or configuration/result type**. MailService SMTP backend using mail YAML settings; scan/bind the service; each send uses aiosmtplib, without a startup connection pool. | `SmtpMailService(config: 'RuntimeConfig') -> 'None'` |

## `xime.starters.sqlalchemy`

Guide: [transaction.md](transaction.md).

| Name | Classification and contract | Signature |
|---|---|---|
| `AsyncEngineProvider` | **Framework infrastructure**. DI-managed SQLAlchemy engine and disposal; inject session/transaction services instead of creating extra providers. | — |

## Examples and behavioral limits

### TLS reload

```python
from xime.core.bootstrap import Application
from xime.adapters.web import TlsReloadResult, reload_tls

async def refresh_certificate(app: Application) -> bool:
    result: TlsReloadResult = await reload_tls(app, server_id="default")
    return result.succeeded
```

The listener must already be configured for TLS. A successful result acknowledges context loading across the serving workers, not certificate hostname/expiry validation for all clients. `certificate_fingerprint` hashes PEM file bytes; differing formatting or valid certificates can produce different values. No private-key bytes cross workers. Management endpoints remain loopback-only and follow the primary.

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

Call this only after verifying credentials. `authenticate` updates only supplied fields; it does not verify a token or make an authorization decision. This synchronous example clears the custom transport's task context in `finally`; asynchronous handlers must be awaited inside the same protected block. Standard framework middleware already owns its context cleanup.

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

Markers select the wire scalar. Preserve lock-file field numbers and compatibility with existing clients; changing int64 to sint64 is a wire-contract change even though both Python annotations contain int.

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

This example needs `xime[modbus]` and performs no device I/O. Normal services use ModbusClient; direct codecs are useful for protocol fixtures and integrations that already possess raw registers. Do not enable allow_read_only for client writes.

### SMTP binding

```python
from xime.core.config import BindingConfig
from xime.starters.mail import MailService, SmtpMailService

dependency = BindingConfig()
dependency.scan("xime.starters.mail")
dependency.bind({MailService: SmtpMailService})
```

Put equivalent declarations in your application's existing config/dependency.py; this isolated BindingConfig illustrates the binding. Set mail host/port and authentication in runtime YAML. Missing credentials or server availability still cause send errors; binding does not test delivery.

### Exception handling

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

Startup failures must remain failures. Log the relevant error securely and fix configuration/DI; do not continue serving a partly initialized app. Runtime authentication, authorization, protocol and connectivity subclasses have different recovery policies; avoid one broad retry loop for all XimeException values.

## `xime.observability`

Guide: [grpc-handshake-logging.md](grpc-handshake-logging.md).

| Name | Contract | Signature |
|---|---|---|
| `GrpcHandshakeLoggingConfig` | Process-start native tracing switch, level, rate/queue/record limits. Default disabled. | `GrpcHandshakeLoggingConfig(...)` |
| `GrpcHandshakeLoggingStats` | Immutable cumulative process counters, including loss and parse/flush errors. | `GrpcHandshakeLoggingStats(...)` |
| `prepare_grpc_handshake_logging` | Call before grpc imports in every process; off allocates nothing; on has process lifetime. | `(*, resources_dir: str = "resources", runtime: RuntimeConfig \| None = None) -> None` |
| `grpc_handshake_logging_stats` | Snapshot of local counters; off returns zeros without setup. | `() -> GrpcHandshakeLoggingStats` |
