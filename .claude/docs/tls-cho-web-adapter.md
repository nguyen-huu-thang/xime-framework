# TLS cho web adapter (HTTPS) - ĐÃ LÀM (mức 1)

> **Trạng thái: ĐÃ LÀM ở 0.6.3** (2026-07-27). Mức 1 code xong, test **29 pass + 1 skip**
> (`tests_temp/web/test_tls.py`; skip là ca phân quyền file chỉ chạy trên POSIX), gồm một
> ca gọi HTTPS thật vào uvicorn đang chạy. **Mức 2 đã BỎ HẲN** - lý do ở mục 4.
> Đặt 2026-07-27, giữ lại làm tài liệu thiết kế + vận hành.
>
> Đây là **thứ chặn mọi app Python phục vụ Internet**, không phải tính năng "nice to
> have": kiến trúc platform cố ý **không có gateway / reverse proxy**, nên mỗi service
> phải tự làm TLS. Không có nó thì 6 app đang chạy chỉ dùng được trong mạng nội bộ.
>
> **Đã hiện thực**, với ba điểm chệch so với bản thiết kế gốc bên dưới (đều có lý do,
> ghi rõ tại chỗ): `cert_reqs` dùng chữ thay vì số (mục 3.2), validate fail-fast tách
> thành `_tls_kwargs()` (mục 3.3), multi-server chốt phương án kế thừa (mục 3.4).

---

## 1. Hiện trạng

`xime/adapters/web/_adapter.py:112`:

```python
config = uvicorn.Config(fastapi_app, host=host, port=port)
self._server = uvicorn.Server(config)
await self._server.serve()
```

Không truyền tham số ssl nào. `RuntimeConfig.ServerConfig`
(`xime/core/config/runtime.py:19`) cũng chỉ có `host` và `port`.

Kết quả: mọi app Xime chạy HTTP thuần. Đối chiếu: payment-service (Java) đã làm được
HTTPS 8087 bằng keystore, còn app Python **không có đường nào**.

---

## 2. Quyết định thiết kế phải chốt trước khi code: dùng cert nào

Đây là chỗ dễ làm sai nhất, vì trong platform có sẵn một nguồn cert (Trust) và rất dễ
tưởng nên dùng nó.

| | Cert Trust (mTLS nội bộ) | Cert CA công cộng (Let's Encrypt...) |
|---|---|---|
| Ai tin | Chỉ service trong mesh (CA nội bộ) | Mọi trình duyệt |
| Dùng cho | gRPC service-service | **HTTPS cho người dùng** |
| Nằm ở đâu | DB của app, mã hóa Fernet | File trên đĩa (do certbot quản) |
| Vòng đời | 365 ngày, tự rotate | 90 ngày, certbot gia hạn |

**KHÔNG dùng cert Trust cho HTTPS mà trình duyệt gọi tới.** Browser sẽ báo cert không
tin cậy vì CA của Trust là CA riêng. Trust sinh ra để service nhận diện nhau, không phải
để phục vụ người dùng cuối.

Vì vậy **mức 1 dưới đây (cert từ file) là đủ cho nhu cầu thật**, và cũng là thứ nên làm
trước. Mức 2 chỉ cần khi muốn HTTPS nội bộ bằng cert Trust.

---

## 3. Mức 1 - cert từ file (làm trước, đủ dùng)

### 3.1. uvicorn hỗ trợ sẵn

Đã kiểm chứng trên uvicorn **0.41.0** cài trên máy này -
`uvicorn.Config.__init__` nhận đúng 7 tham số:

```text
ssl_keyfile  ssl_certfile  ssl_keyfile_password  ssl_version
ssl_cert_reqs  ssl_ca_certs  ssl_ciphers
```

`Config.is_ssl` chỉ là `bool(self.ssl_keyfile or self.ssl_certfile)`, và khi bật thì
`Config.load()` tự dựng `SSLContext` qua `create_ssl_context(...)`. Nghĩa là framework
**chỉ cần chuyển tiếp tham số**, không phải tự dựng gì.

### 3.2. Thêm vào `ServerConfig` (ĐÃ LÀM)

`xime/core/config/runtime.py`, model con (giữ mặc định `None` để không cấu hình =
hành vi cũ y nguyên). **Bản hiện thực khác thiết kế gốc ở `cert_reqs`:**

```python
class ServerTlsConfig(BaseModel):
    certfile: str | None = None
    keyfile: str | None = None
    keyfile_password: str | None = None
    ca_certs: str | None = None       # để yêu cầu client cert (mTLS trên REST)
    # Thiết kế gốc: cert_reqs: int | None (ssl.CERT_REQUIRED = 2).
    # Đã đổi sang chữ: operator đọc `cert_reqs: required` trong YAML là hiểu ngay,
    # còn `cert_reqs: 2` thì không. Framework tự map sang hằng ssl.CERT_*.
    cert_reqs: Literal["none", "optional", "required"] | None = None
    ciphers: str | None = None

    @property
    def enabled(self) -> bool:        # soi gương uvicorn Config.is_ssl
        return bool(self.certfile or self.keyfile)


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    ssl: ServerTlsConfig = Field(default_factory=ServerTlsConfig)
```

Export ở `xime.core.config` và `xime.adapters.web` (app cần nó cho server phụ, mục 3.4).

YAML tương ứng:

```yaml
server:
  host: "0.0.0.0"
  port: 8107
  ssl:
    certfile: "/etc/letsencrypt/live/gym.xime.vn/fullchain.pem"
    keyfile: "/etc/letsencrypt/live/gym.xime.vn/privkey.pem"
```

### 3.3. Sửa `_adapter.py` (ĐÃ LÀM)

Giữ nguyên phần resolve host/port phía trên (nó xử lý `server_id` và override).

Thiết kế gốc gợi ý nhét thẳng vào lời gọi `uvicorn.Config` bằng `**({...} if ... else {})`.
**Bản hiện thực tách thành hàm `_tls_kwargs(tls, server_id)`** vì hai lý do:

1. Dạng dict-splat inline khó đọc, ngược nguyên tắc "ưu tiên đơn giản dễ bảo trì".
2. Cần chỗ để **validate fail-fast**, và validate là phần đáng giá nhất (xem dưới).

```python
tls = self._ssl_override if self._ssl_override is not None else runtime.server.ssl
config = uvicorn.Config(
    fastapi_app, host=host, port=port, **_tls_kwargs(tls, self._server_id)
)
```

`_tls_kwargs` trả **dict rỗng** khi không cấu hình TLS, nên đường HTTP thuần y hệt cũ.

**Vì sao phải tự validate thay vì phó mặc uvicorn** - đã đo trên uvicorn 0.41.0:

| Cấu hình sai | uvicorn ném ra |
|---|---|
| Có `certfile`, thiếu `keyfile` | `SSLError: [SSL] PEM lib (_ssl.c:4184)` |
| Có `keyfile`, thiếu `certfile` | `AssertionError` **message rỗng** |
| File không tồn tại | `FileNotFoundError` không nêu key nào sai |

Hai dòng đầu là lỗi **không thể debug**. Nên `_tls_kwargs` kiểm trước và ném
`StartupException` nêu rõ key + đường dẫn + server_id. Tuyệt đối không im lặng rơi về
HTTP: server tưởng HTTPS mà thật ra HTTP là lỗ hổng bảo mật.

**Cảnh báo `cert_reqs`/`ciphers` trong thiết kế gốc là ĐÚNG, đã kiểm chứng:** truyền
`ssl_cert_reqs=None` cho `ValueError: None is not a valid VerifyMode` lúc dựng
`SSLContext`. uvicorn mặc định `ssl_cert_reqs = ssl.CERT_NONE` (số 0) và
`ssl_ciphers = "TLSv1"` (chuỗi), nên `None` KHÔNG có nghĩa "dùng mặc định" mà ghi đè
mất. Chỉ forward khi thực sự được cấu hình.

### 3.4. Multi-server (ĐÃ CHỐT: kế thừa, có đường thoát tường minh)

`WebAdapter` cho phép chạy nhiều server; khi `server_id != "default"` thì host/port
**không** đọc từ `runtime.server`.

**Quyết định (2026-07-27):** theo đề xuất tối thiểu - `WebAdapter(..., ssl=...)` nhận
`ServerTlsConfig` riêng, **để trống thì kế thừa `server.ssl`**.

```python
app.use(WebAdapter())                                             # kế thừa server.ssl
app.use(WebAdapter("admin", "0.0.0.0", 8081))                     # cũng kế thừa
app.use(WebAdapter("admin", "0.0.0.0", 8081, ssl=ServerTlsConfig(...)))   # cert riêng
app.use(WebAdapter("internal", "127.0.0.1", 8082, ssl=ServerTlsConfig())) # tắt TLS
```

Kế thừa (thay vì mặc định HTTP thuần) là có chủ đích: server phụ âm thầm chạy HTTP khi
server chính đã HTTPS là lỗ hổng không ai để ý. Muốn tắt thì phải viết ra.

> **Nếu sau này cần tính lại:** phương án thay thế là mỗi server một khối YAML riêng
> (`servers.<id>.ssl`). Chưa làm vì hiện chưa app nào chạy nhiều server có cert khác
> nhau, mà thêm khối YAML lồng thì phải giải quyết cả host/port cho nhất quán - việc
> lớn hơn nhiều so với một tham số constructor. Khi có app thật cần cert khác nhau cho
> từng server thì mở lại chỗ này; đường nâng cấp không vỡ vì `ssl=` vẫn là override
> ưu tiên cao nhất.

---

## 4. Mức 2 - cert in-memory, xoay được: **ĐÃ BỎ HẲN** (quyết 2026-07-27)

> **Không làm, và không phải "hoãn lại".** Giữ nguyên phần phân tích bên dưới làm hồ sơ
> để sau này không ai đề xuất lại mà không biết vì sao đã bỏ.

**Lý do bỏ: mức 2 không giải quyết được vấn đề nó sinh ra để giải quyết.**

Nó tồn tại để "HTTPS bằng cert Trust mà private key không nằm trên đĩa". Nhưng chính
mục 4.1 dưới đây đã chỉ ra `load_cert_chain()` **bắt buộc phải qua file một nhịp**. Nên
mức 2 chỉ đổi từ "file do certbot quản, quyền hệ thống" sang "file tạm tự ghi rồi tự
xóa" - key vẫn chạm đĩa, mà phải trả thêm hai cái giá: phụ thuộc API nội bộ uvicorn
(mục 4.2) và độ phức tạp xoay context (mục 4.3).

Thêm nữa, nhu cầu "REST nội bộ có xác thực hai chiều" **mức 1 đã làm được** qua
`ca_certs` + `cert_reqs: required`. Còn HTTPS cho trình duyệt thì bắt buộc cert CA công
cộng, không dùng cert Trust được (mục 2). Mức 2 không còn ca sử dụng nào.

### 4.0. Thay thế: "mức 1.5" - gia hạn cert không cần restart

Vấn đề thật duy nhất mà mức 2 từng hứa giải quyết là **certbot gia hạn thì phải restart
app** (mục 7). Có đường rẻ hơn nhiều, **đã kiểm chứng bằng handshake TLS thật**:

```text
handshake 1 (trước khi nạp đè): CN=old.example.com
srv_ctx.load_cert_chain('c2.pem','k2.pem')   # nạp đè lên context ĐANG PHỤC VỤ
handshake 2 (sau khi nạp đè) : CN=new.example.com
```

Gọi `load_cert_chain()` lần hai lên chính `SSLContext` đang phục vụ thì **kết nối mới
nhận cert mới ngay**, kết nối cũ không bị ảnh hưởng. Nghĩa là chỉ cần:

- cert vẫn từ file như mức 1 (certbot quản, không ghi file tạm, không đụng nguyên tắc
  vòng đời cert),
- framework **đọc** `config.ssl` rồi nạp đè khi file đổi (watch mtime, hoặc một endpoint
  admin, hoặc SIGHUP).

So với mức 2: không ghi file tạm, và chỉ *đọc* `config.ssl` chứ không *gán* - chạm API
nội bộ uvicorn ít hơn hẳn, không cần gọi `config.load()` thủ công.

**Chưa làm ở 0.6.3.** Restart mỗi ~60 ngày với 6 app là chấp nhận được, và mức 1 cần ra
trước để app dùng được ngay. Khi nào việc restart thành phiền thì làm mức 1.5, đừng làm
mức 2.

---

### Hồ sơ mức 2 (giữ lại để tra cứu, KHÔNG phải việc cần làm)

Framework đã có tiền lệ cho gRPC, **theo đúng khuôn đó** nếu làm:

- `xime/adapters/grpc/tls/_provider.py`: `GrpcCertificateProvider` Protocol với
  `version()` (đọc memory, không gọi mạng) + `current()` trả `ServerCertificates`
  (PEM text).
- `xime/adapters/grpc/tls/_config.py:41`: `configure_grpc_tls(provider, server_id)`.

Bản web tương ứng sẽ là `configure_web_tls(provider=...)`. **Nhưng có hai cạm bẫy đã
kiểm chứng, phải biết trước khi hứa làm được:**

### 4.1. Python không load được cert từ chuỗi PEM

`ssl.SSLContext.load_cert_chain()` **chỉ nhận đường dẫn file**. Thử truyền chuỗi PEM trực
tiếp trên Python 3.14 (máy này) cho `OSError: [Errno 22] Invalid argument` - nó coi tham
số là path.

Nên cert in-memory vẫn phải qua file một nhịp: ghi file tạm quyền `0600` -> `load_cert_chain`
-> xóa ngay (SSLContext đã giữ key trong bộ nhớ sau khi load). Trên Linux nên ghi vào
tmpfs (`/dev/shm`) hoặc memfd để không chạm đĩa thật.

Đây là đánh đổi có thật: nó mâu thuẫn một phần với nguyên tắc "private key không nằm
trần trên đĩa" của vòng đời cert
(`D:\code\xime\.claude\docs\vong-doi-cert-mtls-va-file-bootstrap.md`). Phải nêu rõ khi
chốt, đừng lặng lẽ làm.

### 4.2. Gán `SSLContext` vào uvicorn phải dựa vào API nội bộ

`uvicorn.Config` không nhận `SSLContext` dựng sẵn. Đường duy nhất (đã đọc source uvicorn
0.41.0):

```python
config = uvicorn.Config(app, host=host, port=port)
config.load()            # sau bước này config.loaded = True, config.ssl = None
config.ssl = my_context  # gán thủ công
server = uvicorn.Server(config)
await server.serve()     # _serve() chỉ load() lại nếu `not config.loaded` -> không ghi đè
```

`Server.startup()` truyền thẳng `config.ssl` vào `loop.create_server(..., ssl=config.ssl)`,
nên cách này chạy. Nhưng `config.loaded` và `config.ssl` là **nội bộ uvicorn, không phải
API công khai** - nâng uvicorn có thể vỡ. Nếu làm, phải có test khóa lại hành vi này để
lần nâng version sau phát hiện ngay.

### 4.3. Rotate

TLS chỉ dùng cert lúc handshake, nên đổi cert chỉ ảnh hưởng kết nối mới - giống ghi chú
trong `GrpcCertificateProvider`. Với `SSLContext` gán sẵn thì phải dùng
`context.set_servername_callback` hoặc dựng lại context, không đơn giản như gRPC. Cân
nhắc kỹ trước khi hứa "xoay nóng".

---

## 5. Ràng buộc phải giữ (đã giữ đủ ở bản hiện thực)

- **Không cấu hình ssl = hành vi cũ y nguyên** (HTTP thuần). Không được ép TLS, vì test
  và môi trường dev đang chạy HTTP. -> `_tls_kwargs` trả dict rỗng, lời gọi
  `uvicorn.Config` không đổi một tham số nào.
- **Không đụng phần resolve host/port** trong `start()` - nó xử lý `server_id`, override,
  và kiểm `None` tường minh để `host=""` / `port=0` vẫn hợp lệ. -> giữ nguyên.
- **`build_app()` không đổi** - test tích hợp dùng nó để lấy FastAPI app, không qua
  uvicorn. -> giữ nguyên; TLS chỉ chạm đường `start()`.
- Thiếu file cert mà cấu hình có -> **fail fast lúc startup** với thông báo rõ, đúng
  nguyên tắc framework. Đừng im lặng rơi về HTTP: một server tưởng đang HTTPS mà thật ra
  HTTP là lỗi bảo mật. -> `StartupException` nêu key + đường dẫn + server_id.
- **Toàn bộ 1193 test cũ vẫn pass**, không ca nào phải sửa theo.

---

## 6. Test (ĐÃ LÀM - `tests_temp/web/test_tls.py`, 29 pass + 1 skip)

Không cần CA thật - fixture `cert_pair` sinh cert tự ký bằng `cryptography`. Thư viện
này trước đây chỉ có mặt **gián tiếp**; đã khai báo tường minh vào extra `dev` của
`pyproject.toml` để test không phụ thuộc may mắn của môi trường.

| Ca | Mong đợi | Kết quả |
|---|---|---|
| Không cấu hình `server.ssl` | `is_ssl` False, app chạy HTTP (như cũ) | pass |
| Có `certfile` + `keyfile` hợp lệ | `is_ssl` True, `config.ssl` là `SSLContext` | pass |
| Có `certfile` nhưng thiếu `keyfile` | startup fail, thông báo nêu đúng thiếu gì | pass |
| File cert không tồn tại | startup fail sớm, nêu key + đường dẫn | pass |
| `cert_reqs`/`ciphers` không cấu hình | không truyền vào uvicorn (giữ mặc định) | pass |
| Gọi thật qua HTTPS bằng client tin cert tự ký | 200 | pass |

Thêm ngoài bảng gốc:

- `cert_reqs` ba giá trị chữ map đúng hằng `ssl.CERT_*`; `cert_reqs: none` tường minh
  vẫn được forward (khác với bỏ trống).
- mTLS thật dựng được `SSLContext` với `verify_mode == CERT_REQUIRED`.
- Sai chính tả `cert_reqs` bị Pydantic từ chối ngay lúc dựng config.
- Bốn ca resolve TLS của multi-server (kế thừa / override / tắt tường minh / không có).
- Thông báo lỗi có nêu `server_id` để biết server nào sai.
- Truyền thư mục thay vì file -> báo "not a regular file".
- **File tồn tại nhưng không đọc được** (`chmod 000`) -> báo `TLS File Not Readable` kèm
  đường dẫn. Đây là ca duy nhất phải **skip trên Windows** (`chmod 000` không chặn đọc),
  nên tổng skip của repo tăng từ 4 lên 5.

---

## 7. Vận hành (ghi để phiên sau khỏi phải tự nghĩ ra)

- Cert công cộng: Let's Encrypt qua certbot, gia hạn mỗi ~60 ngày. Cert đổi file thì
  **phải restart app** (mức 1 không đọc lại file). Chấp nhận được với 6 app hiện tại;
  khi nào thấy phiền thì làm **mức 1.5** (mục 4.0), KHÔNG phải mức 2 (đã bỏ).
- Mỗi app một domain riêng (`gym.xime.vn`, `spa.xime.vn`...) vì không có gateway để
  route theo host.
- Port: app đang dùng dải 8100-8149 (`D:\code\xime\đăng kí mạng.md`). HTTPS vẫn dùng
  đúng port đã đăng ký của app, không cấp port mới.
- Bật cho một app: chỉ thêm khối `server.ssl` vào `application.yml`, không sửa code.

  ```yaml
  server:
    host: "0.0.0.0"
    port: 8107
    ssl:
      certfile: "/etc/letsencrypt/live/gym.xime.vn/fullchain.pem"
      keyfile: "/etc/letsencrypt/live/gym.xime.vn/privkey.pem"
  ```

- Tiến trình app phải **đọc được** hai file đó. Certbot đặt quyền chặt (`privkey.pem`
  thường `root:root 0600`), nên hoặc chạy app bằng user có quyền, hoặc thêm user app vào
  group đọc được `/etc/letsencrypt/archive`. Sai quyền thì startup nổ `StartupException`
  nêu đúng đường dẫn, không phải lỗi mơ hồ.

---

## 8. Liên quan

- Khảo sát toàn cảnh (mục **A1** là mục này):
  `D:\code\xime\.claude\docs\khao-sat-ha-tang-cho-app-chay-that.md`
- Vì sao không có gateway: `D:\code\xime\thiết kế chi tiết trong giai đoạn khởi nghiệp\tong-quan\06-van-hanh-va-phap-ly.md`
  (đính chính 2026-07-04 - đã bỏ ý tưởng Caddy edge)
- Tiền lệ TLS động trong chính framework: `xime/adapters/grpc/tls/`
- Mắt xích khác đang chờ ở repo này: `docs/peer-app-id-tu-san-cert.md`
