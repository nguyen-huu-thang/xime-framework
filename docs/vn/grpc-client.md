# gRPC Client SDK + mTLS động

[English](../en/grpc-client.md) | **Tiếng Việt**

[← Code-First gRPC](grpc-codefirst.md) · **Phần bổ sung — gRPC Client SDK** · [Starters →](starters.md)

---

[Code-First gRPC](grpc-codefirst.md) lo phía **server**: bạn viết controller
Python, XIME phục vụ qua gRPC. Trang này lo phía **client**: gọi sang một service
khác mà cảm giác như gọi hàm nội bộ - không dựng channel tay, không marshal
protobuf, không bắt `grpc.RpcError` trần.

```text
service đích (.proto + contract.json)
        │  xime grpc client
        ▼
clients/<service>/   ← SDK Python tự chứa (Pydantic + client class)
        │  configure_grpc_clients(...) + application.yml
        ▼
inject thẳng vào constructor — XimeGrpcChannel lo deadline, lỗi typed, mTLS động
```

> **Yêu cầu:** `pip install "xime[grpc]"`

---

## 1. Sinh SDK từ `.proto`

Lấy file `.proto` của service đích (và `contract.json` nếu đó là service Xime -
xem mục 6), đặt vào một thư mục, rồi chạy:

```bash
xime grpc client --proto contracts/trust --out clients/trust
```

Kết quả là một package Python tự chứa:

```text
clients/trust/
├── __init__.py          # export client class + DTO
├── _models.py           # Pydantic model + IntEnum, lật gương từ message
├── _clients.py          # mỗi service → một client class, mỗi rpc → một method
└── _descriptors.binpb   # FileDescriptorSet, nạp lúc chạy
```

Điểm cốt lõi: **code trong `app/` import package này như import thư viện** - nó
không phải mã bạn sửa, mà là artifact sinh ra. SDK không dùng `*_pb2.py`; message
class được dựng trong một `DescriptorPool` riêng từ `_descriptors.binpb`, nên
hai SDK trong cùng tiến trình không bao giờ đụng tên module.

Client class là gương của controller phía server:

```python
# clients/trust/_clients.py — mã sinh, không sửa tay
class KeyClient:
    def __init__(self, channel: grpc.aio.Channel) -> None: ...

    async def get_verification_keys(self, request: KeyQuery) -> KeyList: ...
```

---

## 2. Đưa client vào DI

Theo đúng pattern `configure_*` của XIME. Khai báo trong `config/grpc.py`:

```python
# config/grpc.py
from xime.adapters.grpc import configure_grpc_clients
from clients.trust import KeyClient, CertClient

configure_grpc_clients("trust", KeyClient, CertClient)
#                       ^^^^^ client_id, khớp grpc.clients.trust trong YAML
```

Và cấu hình địa chỉ + bảo mật trong `application.yml`:

```yaml
grpc:
  clients:
    trust:
      host: trust.internal
      port: 9090
      deadline_ms: 3000      # deadline mặc định mỗi call; 0 = tắt
```

Lúc startup, framework tạo một `XimeGrpcChannel` cho mỗi `client_id`, khởi tạo
từng client class với channel đó, và **đăng ký instance vào DI container**. Từ đó
mọi class chỉ việc khai constructor:

```python
class VerificationKeySynchronizer:
    def __init__(self, keys: KeyClient, cache: VerificationKeyCache):
        self._keys = keys
        self._cache = cache

    async def synchronize(self) -> None:
        result = await self._keys.get_verification_keys(KeyQuery(active_only=True))
        self._cache.update(result.keys)
```

Các client cùng `client_id` chia sẻ một channel. Channel được đóng graceful khi
ứng dụng tắt.

> **Fail fast:** đăng ký `configure_grpc_clients("trust", ...)` mà thiếu block
> `grpc.clients.trust` trong YAML → startup thất bại với thông báo kèm mẫu YAML
> cần thêm.

---

## 3. Deadline và lỗi typed

`XimeGrpcChannel` thêm hai thứ tại biên mỗi call - SDK sinh ra không cần biết:

**Deadline.** Mọi call có deadline mặc định (`deadline_ms` trong YAML). Override
cho một call cụ thể qua `timeout=` (giây). `deadline_ms: 0` để tắt deadline.

**Lỗi typed.** `grpc` báo lỗi bằng `AioRpcError` với status code. XIME dịch sang
phân cấp exception riêng để bạn bắt theo ngữ nghĩa, không phải so sánh status
code thủ công:

| gRPC StatusCode | Exception XIME |
|---|---|
| `DEADLINE_EXCEEDED` | `RemoteCallTimeout` |
| `UNAVAILABLE` | `RemoteServiceUnavailable` |
| còn lại | `RemoteCallError` |

```python
from xime.core.exception.framework import (
    RemoteCallError, RemoteCallTimeout, RemoteServiceUnavailable,
)

try:
    keys = await self._keys.get_verification_keys(query)
except RemoteCallTimeout:
    ...                       # quá deadline
except RemoteServiceUnavailable:
    ...                       # không kết nối được
except RemoteCallError as exc:
    if exc.code == "KeyNotFoundException":   # tên exception phía server
        ...
```

`RemoteCallError` mang theo:

- `status` — tên gRPC StatusCode (`"NOT_FOUND"`, `"INTERNAL"`...).
- `code` — tên class exception phía server, đọc từ trailing metadata
  `xime-error` mà `ErrorMappingInterceptor` của server gắn vào. Rỗng nếu service
  đích không phải XIME (vẫn typed).
- `path` — method bị lỗi (`/xime.internal.KeyController/GetKeys`).
- `error_message` — message từ server.

> Đây là gương của `configure_grpc_error_mappings` phía server: server map
> exception → StatusCode, client map StatusCode → exception trở lại.

**Retry (tùy chọn).** Bật tự động thử lại cho call **unary** qua YAML. Tắt mặc
định - bật tường minh đúng triết lý "no magic":

```yaml
grpc:
  clients:
    trust:
      retry:
        enabled: true
        max_attempts: 3            # tổng số lần thử, kể cả lần đầu
        initial_backoff_ms: 100
        max_backoff_ms: 2000
        backoff_multiplier: 2.0
        retryable_status: [UNAVAILABLE]   # tên gRPC StatusCode
```

- Chỉ retry call **unary** - request/response streaming không replay an toàn sau
  khi đã tiêu thụ.
- Mặc định chỉ `UNAVAILABLE` (request thường chưa tới server nên an toàn thử
  lại). Thêm status khác cho call không idempotent có thể gây tác dụng phụ trùng
  lặp - tự cân nhắc.
- Mỗi lần thử có **deadline riêng** (`deadline_ms`); backoff mũ, có cap
  `max_backoff_ms`. Hết số lần thử thì ném lỗi typed như thường.

---

## 4. mTLS động (cert xoay không downtime)

Để gọi qua mTLS với cert tự xoay, dùng chung `GrpcCertificateProvider` đã đăng
ký cho server (cert định danh service, nên inbound và outbound dùng một nguồn -
xem [Code-First gRPC](grpc-codefirst.md) phần TLS động). Chỉ cần bật `dynamic`:

```yaml
grpc:
  clients:
    trust:
      host: trust.internal
      port: 9090
      tls:
        enabled: true
        dynamic: true        # cert lấy từ provider, không khai file
```

```python
# config/grpc.py — provider dùng chung cho cả server lẫn client
configure_grpc_tls(provider=MyCertificateProvider)
configure_grpc_clients("trust", KeyClient)
```

Cơ chế: mỗi call, `XimeGrpcChannel` so `provider.version()` với version của
channel hiện tại. Khác nhau (cert đã xoay) → dựng channel mới với cert mới;
channel cũ được đóng graceful để call đang bay chạy nốt - **không cắt phiên,
không restart**. Giống nhau → dùng lại channel (chỉ so chuỗi, không tốn gì).

Đây là chiều outbound đối xứng với cert động phía server. Bộ máy xoay cert của
bạn chỉ việc cập nhật resolver như thường; cả hai chiều tự nhặt cert mới ở
handshake kế tiếp.

**Multi-server.** Mặc định client lấy provider đăng ký dưới `server_id="default"`.
Nếu service có nhiều provider theo `server_id` (vd internal vs public) và client
này cần dùng một định danh khác, khai `tls.server_id`:

```yaml
grpc:
  clients:
    public-api:
      tls:
        enabled: true
        dynamic: true
        server_id: public     # dùng provider configure_grpc_tls(..., server_id="public")
```

`get_provider()` vẫn fallback về `"default"` nếu `server_id` đó chưa đăng ký
riêng.

**Chế độ tĩnh** (`dynamic: false` hoặc bỏ trống) đọc cert từ file:

```yaml
grpc:
  clients:
    trust:
      tls:
        enabled: true
        ca_file:   certs/ca.pem      # verify server
        cert_file: certs/client.crt  # mTLS: trình cert của mình
        key_file:  certs/client.key
```

Không khai file nào → dùng CA hệ thống (TLS thường tới endpoint public).

---

## 5. Streaming

Client class phản ánh đúng kiểu stream của endpoint:

```python
# upload (client streaming): truyền request + iterator các chunk bytes
async def push_doc(self, request: PushMeta, chunks: AsyncIterator[bytes]) -> PushDone: ...

# download (server streaming, byte): trả về iterator các chunk bytes
def pull_doc(self, request: PullQuery) -> AsyncIterator[bytes]: ...

# server streaming CÓ KIỂU (0.7.1): trả về iterator các DTO
def watch_changed_accounts(self, request: WatchRequest) -> AsyncIterator[AccountChanged]: ...
```

```python
async def chunks():
    yield b"phan-1"
    yield b"phan-2"

done = await client.push_doc(PushMeta(name="tai-lieu"), chunks())

async for chunk in client.pull_doc(PullQuery(parts=3)):
    process(chunk)

async for event in client.watch_changed_accounts(WatchRequest(after_sequence=0)):
    revoke(event.account_id)          # event là DTO Pydantic, không phải bytes
```

Quy ước chunk-wrapper (metadata trước, chunk sau) do framework xử lý hoàn toàn,
business code không thấy message bọc. Stream có kiểu thì không có wrapper nào
cả: mỗi message chính là DTO.

### Deadline của stream - khác với deadline của call thường

```yaml
grpc:
  clients:
    user:
      deadline_ms: 3000          # call unary
      stream_deadline_ms: 0      # server streaming; 0 = không giới hạn (mặc định)
```

Hai khoá tách rời có chủ đích: `deadline_ms` được chỉnh để bắt một vòng gọi bị
treo trong vài giây, mà tuổi thọ của luồng thì không liên quan gì tới điều đó -
luồng theo dõi sống hàng giờ, tải file kéo dài tuỳ kích thước. Nếu stream dùng
chung `deadline_ms` thì nó chết sau vài giây, **mọi lần**.

Muốn giới hạn thì đặt `stream_deadline_ms` thành số dương (ví dụ `3600000` cho
một giờ).

### Luồng bị đứt là chuyện THƯỜNG, không phải sự cố

Đừng viết như thể luồng sống mãi. Với `tls.dynamic: true`, `XimeGrpcChannel`
**thay channel mỗi lần cert mTLS xoay** và channel cũ chỉ được ân hạn 30 giây.
Luồng nào sống lâu hơn thế kể từ lúc cert xoay thì **chắc chắn bị cắt giữa
chừng**. Cộng thêm restart phía server, mạng chập chờn, cân bằng tải.

Nên khuôn đúng là: người tiêu thụ **giữ con trỏ** (số thứ tự đã xử lý tới đâu),
bắt lỗi, rồi nối lại **từ con trỏ đó**:

```python
cursor = load_cursor()
while True:
    try:
        async for event in client.watch_changed_accounts(WatchRequest(after_sequence=cursor)):
            handle(event)
            cursor = event.sequence
            save_cursor(cursor)
    except (RemoteServiceUnavailable, RemoteCallError):
        await asyncio.sleep(backoff())   # rồi nối lại từ cursor
```

Framework **không** tự nối lại: nó không biết con trỏ của bạn nằm ở đâu, và nối
lại sai chỗ thì mất hoặc lặp bản ghi. Retry tự động cũng cố ý **không** áp cho
streaming vì lý do đó.

### Keepalive (tuỳ chọn)

Một kết nối chết âm thầm (NAT hết hạn, peer mất điện) chỉ lộ ra khi có gì đó
được ghi - mà luồng theo dõi thì hàng giờ không ghi gì. Bật ping định kỳ:

```yaml
grpc:
  clients:
    user:
      keepalive:
        time_ms: 30000              # ping mỗi 30 giây; 0 = tắt (mặc định)
        timeout_ms: 20000           # không có ack trong khoảng này → bỏ kết nối
        permit_without_calls: true  # vẫn ping khi không có RPC nào chạy
```

> ⚠ **Server phải cho phép nhịp đó.** gRPC server mặc định chỉ chấp nhận ping
> cách nhau 5 phút, nhanh hơn thì nó trả GOAWAY `too_many_pings` - giết đúng
> những luồng dài mà keepalive sinh ra để bảo vệ. Phía server (nếu cũng là app
> Xime) khai `grpc.keepalive.min_ping_interval_without_data_ms` bằng `time_ms`
> của client hoặc thấp hơn.

---

## 6. Service Xime vs service ngoài (Java...)

Generator đọc thêm file `contract.json` (sidecar) nếu có - file này do
`xime grpc generate` của service Xime phát ra cạnh `.proto`, ghi những gì proto
làm phẳng mất:

- **Có sidecar** (service đích là Xime): SDK lật gương 1:1 - tên method gốc, kiểu
  `Decimal`/`UUID`/`date` đúng như DTO gốc, đủ cả unary lẫn streaming.
- **Không có sidecar** (service đích viết bằng Java, chỉ có `.proto`): generator
  fallback proto-only - sinh method **unary** và **server streaming** (mỗi
  message là DTO của response), kiểu theo map proto thuần (`Decimal` thành
  `str`...). Chỉ **client streaming** bị bỏ qua kèm cảnh báo, vì quy ước upload
  của xime cần sidecar mới biết message nào là wrapper metadata.

Để dùng SDK gọi một service Java, chỉ cần copy `.proto` của nó vào `contracts/`
rồi `xime grpc client` như bình thường.

---

## 7. Đóng gói SDK (tùy chọn)

Mặc định `--out` chính là package import được, commit thẳng vào repo consumer.
Khi một service có nhiều consumer, sinh layout cài được bằng pip để producer
phân phối:

```bash
xime grpc client --proto contracts/trust --out sdk/python \
    --package trust-client --package-version 1.0.0
```

```text
sdk/python/
├── pyproject.toml        # name, version, dependency xime[grpc]
└── trust_client/         # tên package, '-' thành '_'
    └── ...
```

Consumer cài bằng đường dẫn local (`pip install -e ./sdk/python`) hoặc git URL
(`pip install "trust-client @ git+<repo>@<tag>#subdirectory=sdk/python"`) - không
cần dựng PyPI riêng. Phiên bản quản lý bằng git tag.

---

## 8. Tham chiếu nhanh

| Việc | API |
|---|---|
| Sinh SDK | `xime grpc client --proto <dir> --out <dir>` |
| Sinh SDK dạng package | thêm `--package <tên> [--package-version <v>]` |
| Đăng ký vào DI | `configure_grpc_clients("<id>", ClientA, ClientB)` |
| Địa chỉ + deadline | `grpc.clients.<id>.{host,port,deadline_ms}` (YAML) |
| Deadline cho stream | `grpc.clients.<id>.stream_deadline_ms` (0 = không giới hạn) |
| Keepalive | `grpc.clients.<id>.keepalive.{time_ms,timeout_ms,permit_without_calls}` |
| mTLS động | `tls.dynamic: true` + `configure_grpc_tls(provider=...)` |
| mTLS tĩnh | `tls.{ca_file,cert_file,key_file}` (YAML) |
| Override deadline 1 call | `await client.method(req, timeout=<giây>)` |
| Bắt lỗi | `RemoteCallError` / `RemoteCallTimeout` / `RemoteServiceUnavailable` |

---

[← Code-First gRPC](grpc-codefirst.md) · **Phần bổ sung — gRPC Client SDK** · [Starters →](starters.md)
