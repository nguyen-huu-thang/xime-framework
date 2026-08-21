# Kế hoạch - gRPC Client SDK + mTLS động

> Chốt thiết kế ngày 2026-06-12 cùng người thiết kế framework. Tài liệu giải thích
> chi tiết (dạng đọc hiểu): `D:/tài liệu/xime/grpc-code-first-server-client-mtls.md`.
> Tài liệu thiết kế server code-first sẵn có: `05-grpc-codefirst.md`.

---

## 1. Bối cảnh và phát hiện

- Framework hiện chỉ có TLS **tĩnh** (`tls/_credentials.py` đọc cert từ file một lần
  lúc start, chỉ áp dụng cho server `default`).
- **data-service đã xây đủ bộ máy cert động phía app** (resolver, synchronizer,
  CertRotationJob, GrpcServerSslContextProvider có `reload()/current()`) nhưng
  **không có chỗ cắm vào GrpcAdapter** - server gRPC inbound của data-service đang
  chạy `add_insecure_port` (application.yml không có block `grpc.tls`).
- Client gRPC hiện viết tay hoàn toàn trong `app/integration/` của từng service
  (dựng channel, marshal pb2, map lỗi thủ công).

## 2. Quyết định đã chốt

1. **Mã sinh server** giữ nguyên: `generated/` ở project root, ngoài `app/`,
   không ai trong app import (chỉ framework path-load qua `_pb2_loader`).
2. **Client SDK sinh tự động** từ `.proto` + **file sidecar metadata**
   (`contract.json`) để lật gương 1:1 những gì proto làm phẳng mất
   (tên endpoint gốc, Decimal/UUID/datetime fidelity, ngữ nghĩa chunk-wrapper).
   Sinh từ `.proto` (không từ ContractModel) để dùng được với cả service Java.
   Không có sidecar (service Java) thì fallback map từ proto trần.
3. **Vị trí client SDK:** `clients/<service>/` ở project root, ngoài `app/`,
   package tự chứa (Pydantic models + pb2 + client class) - hành xử như thư viện
   ngoài, tương lai publish PyPI nội bộ.
4. **DI:** `configure_grpc_clients(client_id, *client_classes)` trong
   `config/grpc.py`; framework tạo channel theo YAML `grpc.clients.<client_id>`,
   khởi tạo client class, **pre-register instance vào container** trước khi build
   graph của user. Không auto-scan `clients/`.
5. **mTLS động:** Protocol `GrpcCertificateProvider` (`version()` + `current()`)
   dùng chung cho cả server lẫn client.
   - Server: bọc `grpc.dynamic_ssl_server_credentials` - fetcher gọi mỗi
     handshake mới, so version, không đổi trả None. Phiên đã thiết lập không bị
     ảnh hưởng khi rotate (TLS tự có).
   - Client: gRPC Python không có dynamic creds cho channel nên `XimeGrpcChannel`
     so version mỗi lần lấy channel, khác thì tạo channel mới, channel cũ đóng
     graceful (call đang bay chạy nốt).
   - Resolver/persistence/bootstrap/scheduler rotation: **ở app**, framework
     không ôm. Sự kiện handshake chỉ đọc memory từ resolver, không bao giờ gọi
     Trust realtime.
6. **Per-server TLS:** `configure_grpc_tls(provider=X)` áp dụng mọi server;
   override `configure_grpc_tls(provider=Y, server_id="public")`. Bỏ giới hạn
   TLS-chỉ-default-server. Cert mặc định dùng chung cho mọi server của một
   service (cert định danh service, không định danh port); hỗ trợ riêng cho
   kịch bản internal (Trust CA) vs public (public CA).
7. **Integration layer vẫn giữ** làm anti-corruption layer: usecase → port →
   integration adapter → client SDK (DI) → XimeGrpcChannel. Generated client
   được inject vào integration qua constructor.
8. **Generated client phải "nói thật" về phân tán:** map StatusCode về exception
   hierarchy Xime, deadline mặc định mọi call (YAML per-client, override
   per-call), chỗ cắm retry policy trong YAML.

## 3. Lộ trình triển khai

### Phase 0 - Server TLS động (HOÀN THÀNH 2026-06-13)

Lý do: data-service đang chạy gRPC inbound không mã hóa dù đã có đủ cert machinery.

- [x] `GrpcCertificateProvider` Protocol + dataclass `ServerCertificates`
      (private_key_pem, cert_chain_pem, root_ca_pem) trong `adapters/grpc/tls/_provider.py`
- [x] `configure_grpc_tls(provider=..., server_id=...)` theo pattern config
      discovery (registry + reset() cho test) - `tls/_config.py`
- [x] Nhánh dynamic trong `GrpcAdapter._build_credentials()`: enabled + provider →
      `dynamic_ssl_server_credentials`; enabled không provider → file-based như
      cũ; cache theo `version()` trong fetcher; fetcher lỗi giữa chừng → giữ
      cert hiện tại (không giết handshake) - `tls/_credentials.py`
- [x] Bỏ giới hạn TLS-chỉ-default; YAML block per-server `grpc.servers.<id>.tls`
      (`GrpcServerConfig.for_server()`; port của server non-default vẫn ở
      constructor - quyết định v1, tránh ambiguity với default 50051)
- [x] Fail fast: enabled + provider nhưng `current()` lỗi lúc startup → RuntimeError
      rõ ràng; provider không có trong DI → RuntimeError chỉ dẫn dependency.scan()
- [x] Sửa data-service: thêm `TrustGrpcCertificateProvider` (integration/trust/ssl/),
      đăng ký trong config/grpc.py, bật `grpc.tls.enabled+mutual` trong application.yml
- [ ] Dọn dẹp data-service (chờ duyệt vì có xóa file): bỏ
      `GrpcServerSslContextProvider` + lời gọi `reload()` trong
      TrustStartupOrchestrator/CertRotationJob (đã thừa - framework tự nhặt cert
      mới qua provider ở handshake kế tiếp)

Test: `tests_temp/grpc/test_tls.py` (dynamic credentials + fetcher + registry),
`tests_temp/grpc/test_config.py` (for_server). Đã pass cùng toàn bộ suite
(10 fail sẵn có ở `tests_temp/event/test_bus.py`, không liên quan).

### Phase 1 - Codegen client SDK (HOÀN THÀNH 2026-06-13)

- [x] Chốt spec `contract.json` (sidecar) - xem mục 3b bên dưới
- [x] `xime grpc generate` phát thêm sidecar cạnh `.proto`
      (`codefirst/_sidecar.py`, nối vào `build_proto_files` nên `check`
      cũng phát hiện drift của sidecar; `_run_protoc` bỏ qua file non-proto)
- [x] CLI `xime grpc client --proto <dir> --out clients/<name>`
      (`adapters/grpc/client/_codegen.py`): sinh `_models.py` (Pydantic +
      IntEnum, fidelity Decimal/UUID/date) + `_clients.py` (client class per
      service) + `__init__.py` + `_descriptors.binpb`
- [x] Fallback proto-only khi không có sidecar (service Java): chỉ sinh method
      unary (streaming bị skip kèm cảnh báo), kiểu theo map proto thuần
- [x] Runtime SDK (`adapters/grpc/client/_runtime.py`): nạp FileDescriptorSet
      vào DescriptorPool RIÊNG (né luôn điểm yếu pb2 collision cho phía
      client), marshal qua `codefirst/_marshal.py`, unary/upload/download theo
      quy ước chunk-wrapper
- [x] Sửa kèm: `_marshal._message_to_dict` thêm `use_integers_for_enums=True`
      (MessageToDict mặc định trả TÊN enum dạng chuỗi → Pydantic IntEnum fail)

Test: `tests_temp/grpc_codefirst/test_sidecar.py` (spec + hints + generator),
`tests_temp/grpc_client/test_client_sdk_e2e.py` (e2e: generate → protoc → sinh
SDK → import → gọi unary/upload/download qua TCP thật, kiểm chứng Decimal/UUID
fidelity hai chiều).

### 3b. Spec contract.json (sidecar) - ĐÃ CHỐT v1

Một file `contract.json` mỗi thư mục `server_id` (cạnh các `.proto`), output
ổn định từng byte (sort_keys + indent 2) để commit và diff được:

```json
{
  "schema_version": 1,
  "server_id": "internal",
  "package": "xime.internal",
  "services": {
    "CryptoController": {
      "proto_file": "crypto.proto",
      "methods": {
        "Hash":    {"name": "hash", "kind": "unary",
                     "request": "HashRequest", "response": "HashResponse"},
        "Encrypt": {"name": "encrypt", "kind": "client_stream",
                     "request": "EncryptRequest", "response": "EncryptResponse",
                     "wrapper": "EncryptChunk"},
        "Pull":    {"name": "pull", "kind": "server_stream",
                     "request": "PullQuery", "wrapper": "PullChunk"}
      }
    }
  },
  "wrappers": ["EncryptChunk", "PullChunk"],
  "field_types": {"PriceReply.amount": "decimal", "Query.id": "uuid",
                   "Doc.issued_on": "date"}
}
```

Quy tắc:

- `methods` khóa theo rpc_name PascalCase; `name` là endpoint name gốc
  (snake_case) - thành tên method của client.
- `request` của client_stream là DTO metadata thật, KHÔNG phải wrapper;
  wrapper ghi riêng ở key `wrapper` và gom vào danh sách `wrappers` để
  generator client bỏ qua khi sinh model.
- `field_types` chỉ ghi field mà proto làm phẳng mất kiểu: `decimal` / `uuid`
  / `date` (datetime đã có Timestamp - lossless). Hint xuyên qua
  Optional/list/dict (áp cho phần tử). StrEnum chưa hỗ trợ (v2).
- Service ngoài (Java) không có sidecar → generator fallback proto-only.

### Phase 2 - DI + channel quản lý (HOÀN THÀNH 2026-06-13)

- [x] `XimeGrpcChannel` (`client/_channel.py`): facade 3 factory method của
      grpc.aio.Channel mà SDK sinh ra dùng - SDK chạy nguyên vẹn trên nó,
      không sửa mã sinh. Thêm tại biên call: deadline mặc định
      (`deadline_ms`, override per-call qua `timeout=`, 0 = tắt) + dịch lỗi
      typed. TLS tĩnh từ file (`grpc.clients.<id>.tls`); provider động ở Phase 3.
- [x] `configure_grpc_clients(client_id, *classes)` (`client/_config.py`) +
      `GrpcClientConfig.from_runtime` (fail fast khi YAML thiếu block, message
      kèm mẫu YAML). Cùng client_id chia sẻ một channel; một class hai
      client_id → lỗi.
- [x] Hook pre-register: KHÔNG cần sửa core/container -
      `XimeContainer.register_instance` đã có sẵn và validator/lifecycle đã hỗ
      trợ instance pre-built. Chỉ thêm `_collect_framework_instances()` +
      `_try_build_grpc_clients()` vào StartupOrchestrator (mirror pattern
      `_try_build_scheduler`, lazy import, no-op khi không có client).
      `GrpcClientChannels` holder có `pre_destroy` đóng channel - đứng đầu
      lifecycle list nên chạy CUỐI lúc stop (sau khi user teardown xong).
- [x] Error convention ĐÃ CHỐT: server `ErrorMappingInterceptor` gắn trailing
      metadata `xime-error: <tên exception class>` khi abort
      (`XIME_ERROR_METADATA_KEY`). Client dịch AioRpcError →
      `RemoteCallError(status, code, message, path)` trong
      `core/exception/framework.py` (mirror `SocketCommandError`); subclass
      `RemoteCallTimeout` (DEADLINE_EXCEEDED), `RemoteServiceUnavailable`
      (UNAVAILABLE). Server không phải Xime → `code` rỗng, vẫn typed.
- [x] Retry policy: chưa làm (dời Phase 4 như kế hoạch - YAML đã có chỗ).

Test: `tests_temp/grpc_client/` - test_client_config (YAML/registry/instances),
test_channel (deadline/translate/TLS), test_di_integration (orchestrator
pre-register + constructor injection + fail fast), test_channel_e2e (SDK sinh
ra chạy trên XimeGrpcChannel qua TCP thật: happy path + RemoteCallError đúng
status/code + RemoteCallTimeout). 3 test cũ của interceptor cập nhật theo
trailing metadata mới.

### Phase 3 - Client mTLS động (HOÀN THÀNH 2026-06-13, trừ data-service)

- [x] YAML: `grpc.clients.<id>.tls.dynamic: true` (tường minh, không suy đoán;
      dynamic=false giữ nguyên chế độ file tĩnh/CA hệ thống của Phase 2)
- [x] `XimeGrpcChannel._dynamic_channel()`: so `provider.version()` mỗi call
      (so chuỗi, rẻ), version đổi → build channel mới từ `provider.current()`
      (cần đủ root CA - thiếu thì RuntimeError), channel cũ retire đóng
      graceful 30s trong background (call đang bay chạy nốt); `close()` đóng
      cả channel hiện tại lẫn retired
- [x] Wiring: provider là singleton DI nhưng client instance được pre-register
      TRƯỚC khi build container → orchestrator có bước
      `_wire_framework_instances(resolver)` SAU build, TRƯỚC lifecycle, gọi
      `wire_dynamic_certificates()` attach provider vào các channel dynamic.
      KHÔNG đọc cert lúc wire (resolver của provider có thể được PostConstruct
      bootstrap nạp sau) - channel đọc lười ở call đầu tiên.
- [x] Fail fast lúc startup: dynamic bật mà chưa `configure_grpc_tls` →
      RuntimeError; provider không có trong DI → RuntimeError kèm chỉ dẫn
- [x] Provider dùng chung với server (cert định danh service, hai chiều một
      nguồn): client tra `grpc_tls_registry.get_provider("default")`
- [ ] Sửa data-service: xóa `reset_channel()` trong CertRotationJob - BỊ CHẶN
      bởi việc migrate trust client viết tay sang SDK sinh + XimeGrpcChannel
      (việc lớn, có chicken-egg bootstrap cert; đã ghi vào
      `data/.claude/docs/don-dep-ssl-provider.md` làm cùng đợt dọn dẹp)

Test: `tests_temp/grpc_client/test_channel_rotation.py` - rotation (build từ
provider, reuse khi version giữ nguyên, rebuild + retire khi đổi, close dọn
retired), fail fast (thiếu provider, thiếu root CA), wiring qua orchestrator
thật (attach đúng, fail fast khi thiếu đăng ký/thiếu DI, static không bị wire).

### Phase 4 - Sau này

- [x] SDK sẵn sàng đóng gói: `xime grpc client --package <tên> [--package-version]`
      sinh layout pip-installable (`<out>/pyproject.toml` + `<out>/<module>/`,
      dependency `xime[grpc]`, package-data `*.binpb`). Hoàn thành 2026-06-13.
- [ ] Sinh SDK trực tiếp từ ContractModel cho Xime-to-Xime (fidelity cao hơn)
- [x] Retry policy trong YAML (0.3, 2026-06-19): `grpc.clients.<id>.retry`
      (`GrpcRetryConfig`: enabled/max_attempts/backoff/retryable_status). Chỉ
      retry call UNARY (stream không replay được), mặc định chỉ `UNAVAILABLE`,
      backoff mũ có cap, mỗi lần thử deadline riêng. Áp trong
      `XimeGrpcChannel._unary_with_retry`. Test: `test_channel.py::TestRetry`.

**Quyết định phân phối SDK (chốt 2026-06-13): KHÔNG cần PyPI nội bộ.**
Ba mức, đi từ thấp lên khi platform lớn dần - kênh phân phối là quyết định
vận hành từng giai đoạn, không phải của framework:

1. **Hiện tại:** consumer tự sinh, commit `clients/<service>/` vào repo mình
   (mặc định, zero hạ tầng).
2. **Khi một service có nhiều consumer:** repo producer sinh bằng `--package`,
   commit `sdk/python/`; consumer cài `pip install -e <đường dẫn local>` (dev,
   giống cách cài xime framework hiện nay) hoặc
   `pip install "<tên> @ git+<repo>@<tag>#subdirectory=sdk/python"` (CI).
   Version bằng git tag.
3. **Khi team đông:** dựng registry thật (pypiserver/devpi một container
   Docker, hoặc package registry của GitLab/Gitea self-host). SDK đã có
   pyproject.toml nên publish được ngay, không sửa gì thêm.

### Backlog kỹ thuật

- [x] **pb2 loader collision** (ĐÃ SỬA 2026-06-13): server nạp message class qua
      `adapters/grpc/_descriptors.py` (DescriptorPool riêng từ
      `_descriptors.binpb`), không còn import `*_pb2.py` → hết đụng tên module
      `common_pb2`. Dùng chung loader với client SDK. Xem `../kiem-toan/backlog-sua-loi.md`.
- [x] **Bug marshal bytes** (ĐÃ SỬA 2026-06-13): `_marshal.py` base64 hai chiều.
- [x] **10 test event bus fail** (ĐÃ SỬA 2026-06-13): test lỗi thời, viết lại
      theo semantics fire-and-forget.

## 4. Việc thiết kế còn mở (chốt trước khi code phase tương ứng)

| Việc | Cần cho | Nội dung |
| --- | --- | --- |
| Spec `contract.json` | Phase 1 | Schema: endpoint name gốc, python_type per field (decimal/uuid/datetime), optional semantics, đánh dấu chunk-wrapper message + field metadata, server_id, version schema |
| Hook pre-register DI | Phase 2 | ĐÃ XONG (2026-06-13): dùng `register_instance` sẵn có + `_collect_framework_instances` trong orchestrator |
| Error detail convention | Phase 2 | ĐÃ CHỐT (2026-06-13): trailing metadata `xime-error` = tên exception class; client → `RemoteCallError.code` |
| Deadline/retry schema YAML | Phase 2/4 | deadline ĐÃ XONG (`grpc.clients.<id>.deadline_ms`); retry dời Phase 4 |
| Chữ ký streaming client | Phase 1 | upload: `async def encrypt(request, chunks: AsyncIterator[bytes])`; download: trả `AsyncIterator[bytes]` - chốt chính thức |
| YAML per-server | Phase 0 | ĐÃ CHỐT (2026-06-13): `grpc.servers.<id>.tls` chỉ chứa TLS; port server non-default vẫn khai trong constructor GrpcAdapter (tránh ambiguity với default 50051); `grpc.port`/`grpc.tls` ngoài cùng giữ nguyên cho server default |
