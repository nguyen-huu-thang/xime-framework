# File Storage

[English](../en/file-storage.md) | **Tiếng Việt**

[← OPC UA Adapter](opcua.md) · **File Storage** · [Testing →](testing.md)

---

Hỗ trợ file của XIME gồm hai phần phối hợp với nhau:

1. **`StorageService`** - hợp đồng lưu trữ object/blob trung lập backend (một `Protocol`), với hai backend sẵn dùng: **filesystem local** và **S3 / MinIO**.
2. **Web file helper** (`xime.adapters.web.files`) - stream object lên/xuống HTTP không buffer, tôn trọng download HTTP **Range** và upload theo chunk có giới hạn dung lượng.

Business code chỉ phụ thuộc `StorageService`; đổi local ⇆ S3 chỉ là một dòng bind. Object là `bytes` thô (hoặc stream bytes) - framework không áp policy đặt tên, authorization, content-type hay encoding.

---

## Hợp đồng `StorageService`

```python
from collections.abc import AsyncIterator
from xime.starters.storage import StorageService, StorageStat

class StorageService(Protocol):
    async def put(self, key, data: bytes, *, content_type=None) -> None: ...
    async def get(self, key) -> bytes | None: ...
    def open_stream(self, key, *, offset=0, length=None) -> AsyncIterator[bytes]: ...
    async def put_stream(self, key, chunks: AsyncIterator[bytes], *, content_type=None) -> None: ...
    async def delete(self, key) -> None: ...
    async def exists(self, key) -> bool: ...
    async def stat(self, key) -> StorageStat | None: ...   # size / content_type / etag
    async def url(self, key, *, expires=None) -> str: ...   # presigned URL (nếu backend hỗ trợ)
```

Hai dạng truy cập có chủ đích:

| Dạng | Method | Dùng cho |
| --- | --- | --- |
| Nguyên object | `put` / `get` | object nhỏ, vào/ra bytes tiện lợi |
| Streaming | `put_stream` / `open_stream` | object lớn không nạp hết vào RAM |

`open_stream` nhận `offset` / `length` để phục vụ một dải byte (dùng cho download HTTP Range). Lưu ý nó **không** phải `async def` - trả thẳng một async iterator, nên gọi kiểu `async for chunk in storage.open_stream(key): ...`.

### Hợp đồng key (mọi backend)

`key` là định danh tương đối (vd `"avatars/u123.png"`). **Mọi backend** đều từ chối key rỗng/tuyệt đối/`..` (traversal) như nhau (`storage._keys.validate_object_key`), nên đổi backend không đổi tập key hợp lệ.

---

## Backend filesystem local — `xime.starters.localfs`

```python
# config/dependency.py
from xime.starters.storage import StorageService
from xime.starters.localfs import LocalFileStorage

dependency.scan("xime.starters.localfs")
dependency.bind({ StorageService: LocalFileStorage })
```

```yaml
# resources/application.yml
storage:
  local:
    root: /var/lib/myapp/objects   # bắt buộc - thiếu là fail-fast lúc startup
    file_mode: "0600"              # tùy chọn, mặc định 0600 (chỉ chủ sở hữu)
    dir_mode:  "0700"              # tùy chọn, mặc định 0700
```

> Quyền viết dạng **chuỗi có nháy**: YAML đọc `0600` không nháy thành số **600
> hệ mười**, ra quyền vô nghĩa. Windows bỏ qua hai khoá này.

- **Ghi nguyên tử:** cả `put` lẫn `put_stream` ghi ra file tạm rồi `os.replace`, nên reader không bao giờ thấy object ghi dở. Tên file tạm mang `uuid4` nên hai lần ghi cùng key không giẫm lên nhau.
- **Chặn path traversal:** từ chối key thoát khỏi `root` (kể cả qua symlink, kiểm tra sau `realpath`).
- **Không chặn event loop:** IO file chạy trong worker thread (`asyncio.to_thread`) - không cần `aiofiles`, không cần cài thêm.
- `url()` ném `UnsupportedOperation` - phục vụ file qua helper web bên dưới.

---

## Backend S3 / MinIO — `xime.starters.s3`

Cài bằng `pip install "xime[s3]"` (thêm `aioboto3`).

```python
# config/dependency.py
from xime.starters.storage import StorageService
from xime.starters.s3 import S3FileStorage

dependency.scan("xime.starters.s3")
dependency.bind({ StorageService: S3FileStorage })
```

```yaml
# resources/application.yml
storage:
  s3:
    bucket: my-bucket            # bắt buộc
    region: us-east-1            # tùy chọn
    endpoint_url: http://minio:9000   # tùy chọn (MinIO / S3-compatible)
    access_key: ...              # tùy chọn (hoặc lấy từ env / instance role)
    secret_key: ...
    addressing_style: path       # tùy chọn: "path" (MinIO) | "virtual"
```

- `S3ClientProvider` sở hữu vòng đời client async: mở ở `PostConstruct`, đóng ở `PreDestroy`.
- `put_stream` dùng **multipart upload** (part 5 MiB, abort khi có lỗi nên không để lại upload treo).
- `open_stream` dùng **ranged GET**.
- `url()` trả **presigned URL** (mặc định 3600s; truyền `expires=`).
- `aioboto3` import lười nên module starter vẫn import được khi chưa cài extra.

---

## Streaming qua HTTP — `xime.adapters.web.files`

Hai hàm helper, gọi trong controller (KHÔNG phải component DI):

```python
from fastapi import Request, UploadFile
from xime.adapters.web.routing import get, post
from xime.adapters.web.files import stream_object, save_upload, PayloadTooLarge
from xime.starters.storage import StorageService

class FileController:
    def __init__(self, storage: StorageService) -> None:
        self._storage = storage

    @get("/files/{key:path}")
    async def download(self, key: str, request: Request):
        return await stream_object(self._storage, key, request=request)

    @post("/files/{key:path}")
    async def upload(self, key: str, file: UploadFile):
        await save_upload(self._storage, key, file, max_bytes=50 * 1024 * 1024)
        return {"key": key}
```

### `stream_object(storage, key, *, request=None, filename=None, content_type=None, download=False)`

- Tra metadata qua `stat()`; object không có → **404**.
- Có header `Range` thoả mãn → **206 Partial Content** + `Content-Range`; ngược lại stream **200** đầy đủ.
- Header `Range` sai cú pháp bị **bỏ qua** (trả full 200, theo RFC 7233); range hợp lệ cú pháp nhưng không thoả → **416** kèm `Content-Range: */<total>`.
- Set `Accept-Ranges`, `Content-Length`, `ETag` (khi biết), `Content-Disposition` và `X-Content-Type-Options`.
- Đọc lười từ `open_stream` - object lớn không bao giờ nạp hết vào RAM.

**Hai lớp chống XSS lưu trữ (0.7.1), luôn bật:**

1. `X-Content-Type-Options: nosniff` gắn cho **mọi** phản hồi.
2. Kiểu **ngoài danh sách hiển thị-an-toàn** bị ép `Content-Disposition: attachment`
   kể cả khi `download=False` và kể cả khi không có `filename`. Danh sách an
   toàn: PNG, JPEG, GIF, WebP, BMP, AVIF, PDF, MP4, WebM, MP3, OGG, WAV,
   `text/plain`.

`image/svg+xml` **cố ý không** nằm trong danh sách đó: SVG chạy được script, nên
hiển thị tại chỗ một file SVG người dùng tải lên chính là XSS trên origin của
app. Muốn phục vụ SVG do chính bạn tạo thì đặt `content_type=` tường minh sang
kiểu khác, hoặc phục vụ từ một tên miền riêng.

Tên file có dấu chạy đúng: header dựng theo RFC 6266 (`filename=` bản ASCII +
`filename*=UTF-8''...`). Trước 0.7.1 tải file tên `Hóa đơn.pdf` là HTTP 500.

### `save_upload(storage, key, upload_file, *, max_bytes=32MiB, content_type=None)`

- Stream `UploadFile` theo chunk thẳng vào `put_stream` - không buffer toàn bộ.
- Nếu tổng vượt `max_bytes`, raise `PayloadTooLarge` (HTTP **413**) trước khi đọc hết body. Object dở dang được dọn (local xóa `.part`; S3 abort multipart).
- **Trần mặc định 32 MiB** (từ 0.7.1; trước đó không giới hạn). Bỏ trần thì
  truyền `max_bytes=None` tường minh.
- **Content type lưu lại suy từ TÊN FILE**, không lấy header `Content-Type` của
  phần multipart - header đó do kẻ gọi điều khiển, và backend S3 trả lại y
  nguyên lúc tải về. Không đoán được đuôi file thì lưu
  `application/octet-stream`. Truyền `content_type=` khi caller thật sự biết rõ.
- Trả về số byte đã ghi.

---

## Đổi backend

Vì business code (và controller) chỉ phụ thuộc `StorageService`, chuyển từ local sang S3 - hoặc sang fake in-memory khi test - chỉ là một dòng bind:

```python
# Production (cloud): S3 / MinIO
dependency.bind({ StorageService: S3FileStorage })

# Triển khai local / một node
dependency.bind({ StorageService: LocalFileStorage })

# Testing: fake thỏa mãn Protocol StorageService
dependency.bind({ StorageService: InMemoryStorage })
```

---

## Cài đặt

```bash
# backend filesystem local - không cần extra (có sẵn trong xime)
pip install "xime[s3]"   # backend S3 / MinIO (thêm aioboto3)
```

---

[← OPC UA Adapter](opcua.md) · **File Storage** · [Testing →](testing.md)
