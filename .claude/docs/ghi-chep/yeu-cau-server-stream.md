# Yêu cầu: server-streaming cho BẢN GHI CÓ KIỂU, không chỉ chuỗi byte

## ✅ ĐÃ LÀM XONG - bản 0.7.1, ngày 2026-08-03

> Cả ba chỗ chặn đã gỡ, **cộng một chỗ thứ tư** mà yêu cầu này chưa thấy:
> fallback proto-only của trình sinh SDK **bỏ qua mọi method streaming**, nên
> đường **user-service (Java) -> data-service (Python)** - đúng mắt xích các bạn
> nói là đáng làm - vẫn sẽ không chạy nếu chỉ sửa ba chỗ kia. Nay fallback sinh
> server-stream có kiểu.
>
> - Server: `@stream` + handler `async def ... -> AsyncIterator[Model]` với `yield`.
> - Client: SDK sinh `def x(self, req) -> AsyncIterator[Resp]`, mỗi message là DTO.
> - Deadline: chọn **phương án (b)** như các bạn khuyến nghị -
>   `grpc.clients.<id>.stream_deadline_ms`, mặc định `0` = không giới hạn.
> - Keepalive (mục 3.3): đã làm, **cả hai đầu** client và server, mặc định tắt.
>   Chỉ bật một đầu là bẫy - server mặc định trả GOAWAY `too_many_pings` với
>   nhịp nhanh hơn 5 phút.
>
> **Chưa đẩy PyPI** (chủ dự án tự đẩy), nhưng `xime` cài editable nên code đã có
> hiệu lực ngay với mọi app trên máy này.
>
> Kết quả đầy đủ + 4 thứ đổi hành vi: [`../phien-ban/0.7.1-ket-qua.md`](../phien-ban/0.7.1-ket-qua.md).
> Cách dùng: `docs/vn/grpc-codefirst.md` (phía server) và `docs/vn/grpc-client.md`
> (phía client, kèm khuôn **giữ con trỏ + nối lại** cho mục 4 của yêu cầu này).
>
> Phần dưới là nguyên văn yêu cầu, giữ lại làm hồ sơ.

---

> Người gửi: phiên **data-service** (`Base Platform/data`), ngày 2026-08-02.
> Chủ dự án chỉ đạo gửi sang đây sau khi xác định framework chưa làm được:
> *"nếu framework không làm được thì tôi sẽ sửa framework, nếu framework không làm được bạn hãy
> gửi thông tin đến repo của framework để làm sau."*
>
> **Không chặn việc gì đang chạy.** Nhưng nó chặn một thiết kế nền tảng vừa được chốt hướng
> (xem mục 1), nên đáng làm trước khi ai đó bắt đầu thi công rồi mới phát hiện.

## 1. Bối cảnh: nền tảng vừa chọn server-streaming làm phương tiện truyền tín hiệu thu hồi

Nhóm bốn phiên (user-service · identity · app admin · data-service) ngày 2026-08-02 rà ra rằng
**khóa tài khoản không cắt được phiên đang chạy** - người bị khóa vẫn làm việc tới 30 ngày. Chốt
hướng C (đồng bộ kéo), và chủ dự án muốn đóng nốt cửa sổ 15 phút cho **dịch vụ quan trọng** bằng
cách phát tín hiệu tới chúng.

Nhóm cân ba phương tiện và chọn **gRPC server-streaming**, vì nó lấy độ trễ ~0 của "đẩy" mà giữ
nguyên tính chất vận hành của "kéo" (kết nối do người tiêu thụ khởi tạo, nên nguồn không phải giữ
danh bạ người tiêu thụ, người tiêu thụ không phải mở cổng vào).

Hình dạng hợp đồng dự kiến - **hai RPC anh em dùng chung message**, để đổi phương tiện không phải
đổi dữ liệu đã lưu:

```proto
rpc PollChangedAccounts  (PollRequest) returns (PollResponse);          // kéo
rpc WatchChangedAccounts (PollRequest) returns (stream PollResponse);   // luồng
```

Thiết kế đầy đủ: `D:\code\xime\.claude\tham-khao\05-phat-tin-hieu-thu-hoi-toi-moi-shard.md`.

## 1b. ⚠ VÌ SAO ĐÁNG SỬA: chặn rơi đúng vào mắt xích duy nhất mà luồng có ích

Đọc mục này trước mục 2, vì nó trả lời câu *"sửa để làm gì"* chứ không chỉ *"sửa cái gì"*.

Nhóm đã chốt (`tham-khao/05` mục 8.1): **luồng tới identity không rút ngắn cửa sổ 15 phút nào cả**,
vì cửa sổ ấy do access token đã nằm trong tay người dùng còn hạn, không do identity biết chậm.
Luồng chỉ đáng khi tín hiệu đi **thẳng tới dịch vụ tài nguyên** để chính nó tự chặn.

Ghép với việc chỉ service **Python** dùng framework này:

| Đường | Framework chặn? | Có đáng làm? |
|---|---|---|
| user-service (Java) -> identity (Java) | ❌ không - grpc-java thuần, `StreamObserver<T>` có kiểu sẵn | ❌ **không mua được gì** |
| **user-service (Java) -> data-service (Python)** | ✅ **CHẶN** | ✅ **mua được thật** - cửa sổ về ~0 |
| data-service / notification (Python) phơi luồng | ✅ **CHẶN** | tuỳ feed |

> **Mắt xích làm được thì không đáng làm; mắt xích đáng làm thì chưa làm được.**

Nên yêu cầu này không phải "cho tiện". Nó là **điều kiện cần để đóng cửa sổ 15 phút ở tầng dịch vụ
tài nguyên** - mục tiêu mà chủ dự án nêu ra khi chọn hướng phát tín hiệu.

(Phần bảng phạm vi này do phiên user-service dựng, sau khi kiểm code Java của họ.)

## 2. BA chỗ chặn cứng trong framework hiện tại

> ⚠ Bản đầu của tài liệu này ghi *"hai chỗ chặn, cả hai đều ở phía client"*. **Thiếu.** Phiên
> user-service kiểm phía server và tìm ra chỗ thứ ba; tôi đã đọc lại thân hàm để xác nhận. Sửa
> mỗi phía client thì server vẫn không phơi được luồng có kiểu.

Tôi đã nói với chủ dự án là "framework hỗ trợ đủ" sau một lần grep thấy `server_stream`,
`unary_stream`, `_server_stream_handler`. **Đó là kết luận sai** - đọc kỹ thì hỗ trợ hiện có chỉ
phục vụ **truyền file theo khối byte**, không phục vụ bản ghi có kiểu.

### Chặn 1: SDK sinh ra chỉ trả `AsyncIterator[bytes]`, và rút cứng trường `.chunk`

`xime/adapters/grpc/client/_codegen.py`, nhánh `else:  # server_stream`:

```python
lines += [
    f"    def {py_name}(self, request: {request}) -> AsyncIterator[bytes]:",
    "        return _runtime.server_stream(",
    ...
    f'            "{wrapper}",',     # phải có message "wrapper"
]
```

`xime/adapters/grpc/client/_runtime.py::server_stream`:

```python
async for item in call(pydantic_to_pb2(request, req_cls)):
    yield item.chunk          # <- rút cứng trường tên `chunk`
```

Nên một luồng `stream PollResponse` **không tiêu thụ được qua SDK sinh sẵn**: không có đường nào
trả về model Pydantic, và `item.chunk` sẽ nổ vì `PollResponse` không có trường `chunk`.

Đây rõ ràng là thiết kế **có chủ đích cho tải file** (đi cùng `client_stream` nhận
`AsyncIterator[bytes]`), chứ không phải thiếu sót. Chỉ là nền tảng nay cần thêm một dạng thứ hai.

### Chặn 2: phía SERVER cũng chốt cứng `chunk=`, không phơi được message có kiểu

`xime/adapters/grpc/codefirst/_service_builder.py::_server_stream_handler` (dòng 105-107) - chú
thích của chính framework đã nói thẳng:

```python
wrapper_pb2 = self._messages[method.response_message]  # the *Chunk wrapper
```

Và chốt nằm ở `_GrpcDownloadStream` (dòng ~200):

```python
async def write(self, chunk: bytes) -> None:
    await self._queue.put(self._wrapper_pb2(chunk=chunk))
```

Chữ ký nhận `bytes` và **tự dựng message bằng `chunk=`**. Không có đường nào đưa một model có kiểu
qua nó. Tên class `DownloadStream` cũng nói rõ ý định ban đầu: đây là hạ tầng **tải file**.

**Hệ quả cho phạm vi bản vá:** `server_stream_typed` phải phủ **cả hai đầu**. Sửa mỗi client SDK
thì service Python vẫn không phơi được luồng có kiểu - và data-service, notification là nơi sẽ cần
phơi.

### Chặn 3: deadline mặc định giết luồng dài sau vài giây

`xime/adapters/grpc/client/_channel.py::unary_stream`:

```python
def call(request: Any, timeout: float | None = None) -> AsyncIterator[Any]:
    stream = inner(request, timeout=self._timeout(timeout))
```

`self._timeout(None)` trả về `grpc.clients.<id>.deadline_ms` trong `application.yml`. Ở
data-service: **3000ms** cho trust, **5000ms** cho application. Và SDK sinh sẵn **không truyền
`timeout` nào**, nên luồng luôn nhận deadline mặc định.

Nghĩa là một luồng theo dõi sẽ **chết sau 3-5 giây**, mọi lần, không có cách nào tránh qua SDK.

Deadline mặc định cho mọi call là quyết định đúng và nên giữ - nó bắt được đúng loại lỗi hay quên.
Nhưng luồng dài là ngoại lệ có thật, cần một đường thoát tường minh.

## 3. Đề nghị

### 3.1. Dạng `server_stream` trả model có kiểu

Thêm một `kind` thứ hai trong sidecar meta (ví dụ `server_stream_typed`), sinh ra:

```python
def watch_changed_accounts(self, request: PollRequest) -> AsyncIterator[PollResponse]:
    return _runtime.server_stream_typed(
        self._channel, "/pkg.Svc/WatchChangedAccounts",
        request, "PollRequest", PollResponse, "PollResponse",
    )
```

và ở runtime, thay `yield item.chunk` bằng `yield pb2_to_pydantic(item, response_model)` - đúng
khuôn `unary` đang dùng.

Giữ nguyên dạng `server_stream` cũ cho tải file, đừng đổi hành vi của nó.

**Và phía server cũng cần khuôn song song** (xem Chặn 2): một đường cho handler `yield` model có
kiểu, thay vì phải đi qua `DownloadStream.write(bytes)`. Ví dụ handler trả `AsyncIterator[TModel]`
và service builder tự `pydantic_to_pb2` từng phần tử - đối xứng với `pb2_to_pydantic` mà nhánh
`unary` đã dùng.

### 3.2. Cho phép luồng không có deadline

Ba cách, tôi nghiêng về (b):

| | Cách | Đánh đổi |
|---|---|---|
| a | SDK truyền `timeout=None` cho streaming | Đơn giản, nhưng bỏ hẳn deadline kể cả khi người dùng muốn |
| **b** | **Thêm `stream_deadline_ms` vào `grpc.clients.<id>`, mặc định `0` = không giới hạn** | Tường minh trong `application.yml`, tách bạch với `deadline_ms` của call thường, và người vận hành thấy được |
| c | `timeout=` per-call do người gọi truyền | Đúng nhất về nguyên tắc nhưng dễ quên, mà quên thì luồng chết sau 3 giây |

Ghi chú: `_unary_with_retry` **không** áp cho streaming và điều đó **đúng, xin giữ nguyên** - luồng
không phát lại được, và người tiêu thụ vốn giữ con trỏ nên tự nối lại đúng chỗ là việc của họ.

### 3.3. Không bắt buộc, nhưng nên cân: keepalive gRPC

`grep -rn "keepalive" xime/` chỉ ra `adapters/mqtt/`. gRPC chưa phơi cấu hình keepalive nào, nên
một kết nối nửa-sống-nửa-chết không bị phát hiện ở tầng vận chuyển.

Thiết kế của nhóm đã bù ở tầng ứng dụng (nguồn gửi **nhịp tim** định kỳ mang
`source_max_sequence`, người tiêu thụ quá N nhịp không thấy thì nối lại), nên đây **không phải
chặn**. Nhưng phơi `keepalive_time_ms` / `keepalive_timeout_ms` sẽ giúp mọi luồng về sau, không
riêng feed này.

## 4. Một ràng buộc khiến "nối lại" là đường CHÍNH, không phải ngoại lệ

> ⚠ **Phạm vi: chỉ đúng cho client Python đi qua `XimeGrpcChannel`.** Bản đầu của tài liệu này
> viết như thể nó đúng cho cả nền tảng - sai. Service Java (identity, user-service, trust...) tự
> quản kênh, không qua framework này, nên hành vi của họ phải kiểm riêng. Phiên user-service chỉ
> ra chỗ này.

Đáng biết khi thiết kế phần này: các kênh gRPC của service Python khai `tls.dynamic: true`, và
`XimeGrpcChannel` **thay kênh khi cert mTLS xoay** (`_retired`, `_RETIRE_GRACE_SECONDS = 30`).
Kênh cũ được ân hạn 30 giây cho call đang bay rồi đóng.

Với call unary thì 30 giây là quá đủ. Với **luồng dài thì nó luôn bị cắt** - luồng sống lâu hơn 30
giây kể từ lúc cert xoay là chắc chắn bị đóng giữa chừng.

Nên đường "đứt luồng -> nối lại kèm con trỏ" **chạy thường xuyên theo lịch cert**, không phải nhánh
xử lý sự cố. Framework không cần làm gì cho việc này (người tiêu thụ giữ con trỏ), nhưng nếu có
tài liệu về streaming thì nên nói rõ, kẻo người viết đầu tiên tưởng luồng sống mãi.

Cũng vì vậy, mục 3.2 không nên chọn cách (a) một cách vô tư: luồng không deadline mà kênh lại bị
thay theo lịch thì hành vi đúng phải là **nối lại**, chứ không phải treo.

## 5. Ai đang chờ

Chưa ai chặn. Feed thu hồi mới ở giai đoạn thiết kế, và thứ tự thi công đã chốt là **kéo trước,
luồng sau** - nên framework có thời gian. Nhưng khi tới bước luồng thì hai mục 3.1 và 3.2 là điều
kiện cần.

Người sẽ dùng đầu tiên: **data-service** (tiêu thụ) và **user-service** (phơi luồng). Cả hai đều
là service Python dùng framework này.

Bối cảnh đối thoại đầy đủ: `D:\temp\xime\nhom-chat\` (sống theo phiên).
