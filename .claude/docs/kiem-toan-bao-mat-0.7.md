# Kiểm toán BẢO MẬT - Xime Framework 0.7.0 và các app xây từ nó

> **Đây là file kế hoạch VÀ file kết quả.** Phần I là kế hoạch (viết trước khi làm),
> phần II trở đi là phát hiện (ghi trong lúc làm). Ngày lập: 2026-08-01.
>
> Khác với ba đợt kiểm toán trước (`kiem-toan-0.5.md`, `0.6.md`, `0.7.md`) vốn hỏi
> **"code có chạy đúng không"**. Đợt này hỏi **"kẻ tấn công làm được gì"** - cùng một
> dòng code, hai câu hỏi khác nhau, và câu thứ hai chưa ai hỏi bao giờ.

---

> **Kế hoạch vá (chốt 2026-08-01, chưa thi công):**
> [`ke-hoach-va-bao-mat-2026-08-01.md`](ke-hoach-va-bao-mat-2026-08-01.md) - 5 đợt, code cụ thể
> cho từng mục, cách kiểm chứng, và 4 quyết định của chủ dự án. **Hai sự thật ở mục 1 của file
> đó phải đọc trước khi sửa bất cứ gì**: `xime` cài editable và không app nào có venv riêng, nên
> một lần sửa framework là chạm 31 app ngay lập tức; và `xime.__version__` đang trả 0.6.3 trong
> khi code là 0.7.0, nên đừng dùng nó để xác nhận bản vá.

# PHẦN I - KẾ HOẠCH

## 1. Vì sao đợt này tồn tại

Chủ dự án nêu lý do trực tiếp: *"framework này dùng để xây rất nhiều ứng dụng nên tôi
không muốn lỗi framework là sập toàn bộ"*.

Đây là **mô hình rủi ro nhân bội**. Một lỗ hổng trong `xime/starters/jwt/_verifier.py`
không phải là một lỗ hổng - nó là **31 lỗ hổng**, vì có 31 codebase đang dùng. Và vì gói
đã lên PyPI 11 bản, số codebase đó không còn nằm trong tầm kiểm soát nữa.

Quy mô thực tế đã đếm được:

| | Số lượng |
|---|---|
| File Python của framework | 190 file, 21.446 dòng |
| App trong `D:\code\xime` (Base + App Layer + Service ngang) | 25 codebase Python, ~6.500 file |
| App trong `D:\code\Monolithic` | 6 codebase, 927 file |
| Bản đã phát hành công khai trên PyPI | 11 (`0.1.0` -> `0.7.0`) |

## 2. Mô hình mối đe dọa - ai tấn công, từ đâu

Framework là **thư viện**, không phải ứng dụng. Nên mối đe dọa của nó là "app xây từ tôi
bị thủng vì tôi cho sẵn mặc định không an toàn, hoặc vì tôi có lỗi mà app không thể tự vá".

| Mã | Kẻ tấn công | Đứng ở đâu | Quan tâm nhất |
|---|---|---|---|
| **T1** | Người dùng cuối / khách vãng lai | Internet, gọi HTTP/WS của app | Vượt xác thực, đọc file người khác, chiếm phiên |
| **T2** | Khách thuê bao hợp lệ (tenant) | Đã đăng nhập app SaaS | **Leo sang dữ liệu tổ chức khác** (`org_id`, `shard_id`) |
| **T3** | Một service nội bộ đã bị chiếm | Trong mạng, có cert mTLS hợp lệ | Giả danh service/app khác, leo quyền qua gRPC |
| **T4** | Kẻ trong mạng nhà máy | Cùng LAN với Modbus/OPC UA | Ghi thanh ghi thiết bị, giả server |
| **T5** | Chuỗi cung ứng | PyPI, dependency, máy build | Nhét code, đánh cắp token phát hành |
| **T6** | Chính lập trình viên app | Viết code dùng framework | Dùng đúng tài liệu mà vẫn ra app không an toàn |

**T6 là loại quan trọng nhất và dễ bị bỏ sót nhất.** Một framework mà "làm đúng hướng dẫn
thì vẫn thủng" nguy hiểm hơn một framework có bug, vì bug thì vá một lần, còn mặc định
sai thì nhân lên theo mỗi app mới.

## 3. Nguyên tắc chấm điểm

| Mức | Nghĩa | Ví dụ |
|---|---|---|
| **NGHIÊM TRỌNG** | Vượt xác thực / rò dữ liệu xuyên tenant, khai thác được từ xa, không cần điều kiện lạ | JWT chấp nhận `alg: none` |
| **CAO** | Rò rỉ hoặc leo quyền có điều kiện, hoặc mặc định không an toàn mà tài liệu không cảnh báo | Path traversal cần biết trước tên file |
| **TRUNG** | Phòng thủ chiều sâu thiếu, DoS, rò thông tin phụ trợ | Stack trace lọt ra ngoài |
| **THẤP** | Làm khó kẻ tấn công thêm chút, hoặc chỉ sai thực hành | Quyền file 0644 thay vì 0600 |
| **GHI NHẬN** | Không phải lỗi, nhưng người sau cần biết | Ranh giới đã cố ý không làm |

Mỗi phát hiện **bắt buộc** có: đường dẫn `file:dòng`, kịch bản khai thác cụ thể (input gì
-> hậu quả gì), và mức. **Không chấp nhận** phát hiện dạng "chỗ này nên cẩn thận".

Nghi ngờ nào chứng minh được bằng code chạy thì **phải viết PoC** rồi chạy. Đây là bài học
đắt nhất của kiểm toán 0.6: ba báo động giả vì kết luận bằng suy đoán chứ không bằng thực
nghiệm.

## 4. Tầng 1 - Framework, đọc từng dòng theo 14 miền

Thứ tự dưới đây xếp theo **hậu quả nếu thủng**, không theo cấu trúc thư mục.

### M1 - Xác thực JWT (`starters/jwt/`, 7 file)

Nơi thủng thì mọi app mất trắng xác thực.

- `alg` confusion: nhận `none`? nhận `HS256` khi cấu hình khóa RSA (dùng public key làm HMAC secret)?
- `verify_signature`, `verify_exp`, `verify_aud`, `verify_iss` có bị tắt ở nhánh nào không
- `leeway` bao nhiêu, có cho token hết hạn lọt không
- `kid` lấy từ header token (do kẻ tấn công điều khiển) rồi dùng để tra khóa - có path traversal / SSRF / nhét khóa lạ không
- Token lấy từ đâu: chỉ `Authorization`, hay còn query string (lọt vào access log)?
- Scheme `Bearer` phân biệt hoa thường (đã ghi ở C15 kiểm toán 0.7) - xem lại dưới góc bảo mật
- Middleware: đường nào **bỏ qua** xác thực (`public_paths`) - so khớp bằng prefix hay bằng đường chính xác? `/health` có match `/healthz-secret` không? Có chuẩn hóa `//`, `/./`, `%2e%2e` trước khi so không
- Xác thực thất bại thì middleware **chặn** hay **cho đi tiếp với context rỗng**? (đây là chỗ hay sai nhất: fail-open)
- Claim đưa vào `request_context[JWT_CLAIMS]` - app đọc ra có bị lẫn giữa request không

### M2 - Rò rỉ ngữ cảnh giữa các request (`core/context/`, `core/security/context.py`)

Loại lỗi tệ nhất trong app async: **người dùng A thấy dữ liệu người dùng B**. Đã từng xảy
ra một lần ở 0.5 (sửa bằng cách chuyển middleware sang pure-ASGI) nên phải soi kỹ có chỗ nào
còn sót.

- `ContextVar` được `set` mà không `reset`, ở nhánh lỗi có reset không
- Task nền (`asyncio.create_task`) copy context - dữ liệu phiên có sống dai hơn request không
- WebSocket sống lâu: context set một lần, dùng cho mọi message?
- Event bus fire-and-forget: handler chạy sau khi request kết thúc, còn thấy `SecurityContext` cũ?
- Scheduler job: chạy với context của ai
- gRPC streaming: mỗi message hay mỗi stream một context

### M3 - Ủy quyền (`core/security/authorization.py`, `authentication.py`, `session.py`, `enums.py`)

- Mặc định là **cho phép** hay **từ chối** khi không khai quyền
- So sánh quyền: có phân biệt hoa thường, có so bằng `in` (chuỗi con) thay vì bằng nhau không
- `SecurityContext` có thể bị ghi đè từ code nghiệp vụ giữa chừng không
- Vai trò rỗng / `None` xử lý thế nào

### M4 - Web adapter (`adapters/web/`, 22 file)

- **CORS** (`_cors.py`): `allow_origins=["*"]` cộng `allow_credentials=True` là tổ hợp chết người. Framework có chặn không? Đọc từ YAML thì chuỗi `"*"` có thành list `["*"]` không? Có khớp origin bằng chuỗi con không (`evil-myapp.com` khớp `myapp.com`)
- **TLS** (`_adapter.py::_tls_kwargs`): mặc định `cert_reqs`, có cho phép cấu hình nửa vời mà im lặng chạy HTTP không
- **Xử lý lỗi**: `configure_exception_handlers` - handler mặc định có trả stack trace / câu SQL / đường dẫn file ra ngoài không
- **OpenAPI** (`openapi/_builder.py`): `/docs`, `/openapi.json` có bật mặc định ở production không - phơi toàn bộ bản đồ API
- **WebSocket** (`ws/_handler.py`): xác thực trước hay sau khi accept, có kiểm `Origin` chống CSWSH không, giới hạn kích thước message
- **Routing** (`routing/_builder.py`, `_decorators.py`): tham số đường dẫn có được ép kiểu không, `_make_handler` có nuốt lỗi thành 200 không
- **Middleware order** (`_registry.py`): ai chắc chắn ngoài cùng, CORS đứng trước hay sau auth (Monolithic đã phải tự xoay - dấu hiệu framework chưa quyết hộ)
- Giới hạn kích thước body, số header, độ dài URL - có gì chống DoS không

### M5 - File upload / download (`adapters/web/files/`)

Đây là chỗ tôi kỳ vọng tìm thấy lỗi thật nhất, vì nó nhận input trực tiếp từ người lạ.

- `_upload.py`: tên file người dùng gửi có được dùng làm tên file trên đĩa không (`../../../etc/passwd`, `..\\`, ký tự NUL, tên Windows đặc biệt `CON`, `PRN`, `AUX`, `NUL`, `COM1`), có giới hạn dung lượng không (upload 100 GB làm đầy đĩa), có giới hạn số chunk không, chunk ghi vào đâu giữa chừng
- `_download.py`: phân tích header `Range` - `bytes=-1`, `bytes=0-999999999999`, `bytes=5-1`, nhiều range, số âm, tràn số. Sai một chỗ là đọc ra ngoài file hoặc treo tiến trình
- Content-Type / Content-Disposition trả về: có cho phép XSS lưu trữ (upload `.html` rồi mở trực tiếp) không
- Đường dẫn hợp thành có kiểm symlink không (`os.path.realpath` sau khi ghép)
- TOCTOU giữa lúc kiểm và lúc mở file

### M6 - Storage (`starters/storage/_keys.py`, `starters/localfs/_storage.py`, `starters/s3/`)

- `_keys.py` là điểm chuẩn hóa khóa dùng chung -> nếu nó sai thì cả localfs lẫn S3 cùng thủng. Đọc từng dòng.
- localfs: chống path traversal đã có (tài liệu nói vậy) - **kiểm chứng bằng PoC**, gồm cả ký tự Unicode chuẩn hóa (`％2e`), NUL byte, đường dẫn tuyệt đối, symlink trỏ ra ngoài
- Quyền file khi ghi: `0600` hay `0644` (dữ liệu khách trên máy chung)
- Ghi nguyên tử: file tạm đặt ở đâu, tên có đoán được không (kẻ tấn công tạo trước symlink cùng tên)
- S3: presigned URL hạn bao lâu, có ký cả tên bucket không, có bật SSL verify không, có cho phép `endpoint_url` từ config không kiểm

### M7 - gRPC và mTLS (`adapters/grpc/`, 33 file)

Đây là mặt phẳng tin cậy giữa các service, T3 tấn công thẳng vào đây.

- `tls/_credentials.py`, `_provider.py`: server có **bắt buộc** client cert không (`require_client_auth`), hay chỉ "tùy chọn" - tùy chọn nghĩa là ai cũng gọi được
- Có verify chuỗi cert tới CA không, có kiểm hạn không, có kiểm revoke không
- `interceptors/_context.py`: `_read_peer_app_id` đọc SAN `xime-app://`. **Kẻ tấn công có cert hợp lệ của service khác có tự khai SAN tùy ý không?** Framework có kiểm SAN nằm trong cert đã verify, hay đọc từ metadata do client gửi? (nếu là metadata thì đây là NGHIÊM TRỌNG)
- `PEER_CN` lấy từ đâu, có tin được không
- `interceptors/_error.py`: lỗi nội bộ có lọt chi tiết ra `details` của gRPC status không
- Giới hạn kích thước message, số stream đồng thời, deadline mặc định
- `codefirst/_pb2_loader.py` và `_generator.py`: có gọi `protoc` qua subprocess với đường dẫn từ config không (command injection lúc build)
- Client `_channel.py`: `tls.server_id` - có verify hostname không, có chỗ nào `insecure_channel` lọt vào nhánh production không

### M8 - Socket adapter (`adapters/socket/`)

- `_peercred.py`: SO_PEERCRED chỉ có trên Linux. Trên nền khác thì **fail-open hay fail-closed**?
- Quyền file socket khi tạo (umask) - `0777` thì mọi tiến trình trên máy gọi được
- Đường dẫn socket lấy từ config, có kiểm không
- `_protocol.py`: khung tin có trường độ dài -> kẻ gửi khai 4 GB thì server cấp phát bao nhiêu (DoS nhớ)

### M9 - MQTT (`adapters/mqtt/`)

- Mặc định có TLS không, có verify cert broker không
- Credential đọc từ đâu, có log ra không
- RPC over MQTT: reply-topic do người gọi khai -> có kiểm không (kẻ tấn công khai reply-topic của người khác để đọc trộm phản hồi)
- Correlation data có đoán được không

### M10 - Modbus / OPC UA (`adapters/modbus/`, `adapters/opcua/`)

Giao thức công nghiệp gốc **không có xác thực**. Vấn đề không phải "framework có lỗi" mà là
"framework có nói rõ với người dùng rằng chế độ slave/server là mở toang không".

- Chế độ slave Modbus (`@serve`/`@on_write`): ai cũng ghi được thanh ghi. Tài liệu có cảnh báo không
- OPC UA: mặc định `SecurityPolicy` là None? `@on_node_write` có kiểm quyền không
- Client có verify cert server không (đã ghi C10 ở kiểm toán 0.7 - xem lại dưới góc bảo mật)

### M11 - Cấu hình và bí mật (`core/config/`, `core/container/config_loader.py`)

- Đọc YAML bằng `yaml.safe_load` hay `yaml.load` (`yaml.load` = thực thi mã tùy ý)
- **`XIME_ENV` / `APP_ENV` ghép thẳng vào tên file `application-{env}.yml`** -> đặt `XIME_ENV=../../../../etc/passwd` thì sao. Có kiểm ký tự không
- Config object có `__repr__` / `__str__` in ra mật khẩu DB, secret JWT không (một dòng log lỗi là rò secret)
- Ngoại lệ lúc startup có kèm nội dung config không
- Có nơi nào ghi secret vào log/metric/OpenAPI không

### M12 - Chèn mã và giải tuần tự hóa (quét toàn framework)

- `eval`, `exec`, `compile`, `pickle`, `marshal`, `shelve`, `yaml.load`, `subprocess` với `shell=True`
- `importlib.import_module` với chuỗi từ input/config (nạp module tùy ý)
- `getattr(obj, name)` với `name` từ request (gọi hàm tùy ý)
- SQL: `text()` của SQLAlchemy có f-string bên trong không
- Format string đưa dữ liệu người dùng vào (`"...".format(user_input)` -> đọc thuộc tính object)

### M13 - Crypto và số ngẫu nhiên (quét toàn framework)

- `random` (dự đoán được) dùng cho thứ cần bí mật -> phải là `secrets`
- So sánh bí mật bằng `==` thay vì `hmac.compare_digest` (rò rỉ qua thời gian)
- `md5`, `sha1` dùng cho mục đích bảo mật
- `verify=False` ở bất kỳ lời gọi TLS nào
- Sinh ID: có đoán được không

### M14 - Sẵn sàng phục vụ, tức "sập toàn bộ" theo đúng lời chủ dự án

Đây là miền mà chủ dự án nêu đích danh, nên nó là mục tiêu chứ không phải phần phụ.

- Chỗ nào một request lạ làm **chết cả tiến trình** (exception thoát ra khỏi vòng lặp adapter, không phải chỉ hỏng một request)
- `except:` rỗng nuốt lỗi -> hỏng âm thầm; ngược lại chỗ nào **không** bắt mà nên bắt
- Hàng đợi không giới hạn, `asyncio.Queue()` không maxsize
- Không có timeout: gọi mạng, gọi DB, gọi SMTP
- Regex có nguy cơ bùng nổ (ReDoS), nhất là trong routing và phân tích header
- Rò rỉ tài nguyên: session DB, kết nối, file handle không đóng ở nhánh lỗi
- `LifecycleManager` không gọi `pre_destroy` khi `post_construct` ném (đã ghi ở 0.7, chủ dự án chốt giữ nguyên) - kiểm xem có gây rò tài nguyên khai thác được không

## 5. Tầng 2 - Các app, quét theo mẫu tấn công

Toàn bộ 31 codebase, quét bằng ripgrep theo bộ mẫu. Mục tiêu **kép**: tìm lỗ hổng trong app,
và quan trọng hơn - **đếm xem cùng một sai lầm lặp lại ở bao nhiêu app**. Sai lầm lặp ở
nhiều app là bằng chứng framework thiếu API an toàn, và đó là phát hiện về framework chứ
không phải về app.

Bộ mẫu:

| Nhóm | Tìm gì |
|---|---|
| Bí mật lộ | Chuỗi giống khóa/mật khẩu/token trong file đã commit, `application.yml` có vào git không, `.env` |
| CORS | `allow_origins` có `*`, kèm `allow_credentials` |
| JWT | Khóa yếu / khóa mặc định dùng chung, thời hạn quá dài, thiếu `audience`/`issuer` |
| SQL | `text(` + f-string, `execute(` với chuỗi ghép |
| Ủy quyền | Route không có kiểm quyền, so quyền bằng chuỗi |
| **Xuyên tenant** | Truy vấn thiếu `org_id` / `shard_id` trong `where` - đây là T2, mối đe dọa lớn nhất của SaaS đa khách |
| Mật khẩu | Băm bằng gì, có muối không, số vòng |
| Debug | `debug=True`, `reload=True`, `/docs` mở công khai |
| Upload | App tự xử lý tên file thay vì dùng helper framework |
| Xác thực đầu vào | Endpoint nhận thẳng dict thay vì model Pydantic |

Đọc kỹ 3 app đại diện (đã chốt với chủ dự án):

1. **`Base Platform/data`** - 427 file, chuẩn tham chiếu của mọi service Python, lại là nơi giữ **file của mọi app** nên thủng là rò dữ liệu toàn nền tảng
2. **`Application Layer/linh-kien-dien-tu`** - 296 file, code mới nhất, có giỏ hàng + đặt hàng + người mua ngoài (bề mặt tấn công công khai lớn nhất)
3. **`Monolithic/shop`** - 218 file, kiến trúc đa lớp khác hẳn, kiểm xem framework có an toàn ngoài khuôn Hexagonal không

## 6. Tầng 3 - Chuỗi cung ứng và phát hành

- `pyproject.toml`: dependency có sàn phiên bản nào đang dính CVE đã biết
- `pip-audit` trên bộ deps đầy đủ và trên bộ deps sàn
- Nội dung sdist/wheel bản 0.7.0: có lọt `.claude/`, `tests_temp/`, két token, file cấu hình chứa secret không (A1/A2 của kiểm toán 0.7 đã vá - **kiểm chứng lại**, vì đây là loại lỗi tái phát)
- `pypi_token.py`: token lưu thế nào, có mã hóa không, `.gitignore` có chắc chắn không, lịch sử git có từng commit nhầm không
- Quét lịch sử git tìm secret đã từng bị commit rồi xóa (vẫn còn trong lịch sử)

## 7. Công cụ

Chủ dự án đã đồng ý cài vào **venv riêng ở thư mục tạm**, không đụng Python hệ thống và
không đụng dependency của bất kỳ project nào:

| Công cụ | Dùng để | Ghi chú |
|---|---|---|
| `bandit` | Quét mẫu nguy hiểm trong Python | Nhiều báo động giả, chỉ dùng để **gợi ý chỗ đọc**, không dùng để kết luận |
| `pip-audit` | Đối chiếu dependency với CSDL CVE | Lớp duy nhất mà đọc code không thay thế được |
| `semgrep` | Mẫu ngữ nghĩa, quét 31 app | Nếu cài được offline |
| `ruff` | Đã có sẵn | Bổ sung rule `S` (bandit) |
| Ripgrep | Quét mẫu tự viết | Xương sống của tầng 2 |
| PoC tự viết | Chứng minh / bác bỏ nghi ngờ | **Bắt buộc** trước khi ghi phát hiện mức Cao trở lên |

Nguyên tắc: **công cụ chỉ chỉ chỗ, con người kết luận.** Không có phát hiện nào trong báo
cáo này được phép chỉ dựa vào output của công cụ.

## 8. Thứ tự thực hiện

| Bước | Việc | Miền |
|---|---|---|
| 1 | Dựng venv, cài công cụ, chạy quét thô lấy danh sách chỗ đáng đọc | - |
| 2 | Đọc từng dòng nhóm xác thực/ủy quyền/ngữ cảnh | M1, M2, M3 |
| 3 | Đọc từng dòng nhóm nhận input từ người lạ | M4, M5, M6 |
| 4 | Đọc từng dòng nhóm tin cậy giữa service | M7, M8, M9 |
| 5 | Đọc nhóm còn lại | M10, M11, M12, M13, M14 |
| 6 | Viết và chạy PoC cho mọi nghi ngờ mức Cao trở lên | - |
| 7 | Quét mẫu 31 app, đọc kỹ 3 app | Tầng 2 |
| 8 | Chuỗi cung ứng | Tầng 3 |
| 9 | Viết phần II, xếp hạng, đề xuất thứ tự vá | - |

## 9. Điều đợt này KHÔNG làm

Ghi rõ để người sau không tưởng đã kiểm:

- **Không** kiểm thử xâm nhập trên hệ thống đang chạy (không dựng môi trường, không bắn traffic thật)
- **Không** kiểm tra service Java (Trust, identity, user, payment, application, agent, organization) - khác ngôn ngữ, khác đợt
- **Không** kiểm tra frontend Next.js (XSS phía trình duyệt, CSP)
- **Không** kiểm tra hạ tầng (cấu hình DB, tường lửa, hệ điều hành)
- **Không** tự ý vá. Phát hiện được ghi lại kèm đề xuất; chủ dự án quyết vá cái nào trước

---

# PHẦN II - PHÁT HIỆN

> Trạng thái: **ĐÃ CHẠY XONG 2026-08-01.** 24 phát hiện: 1 Nghiêm trọng, 5 Cao, 10 Trung, 8 Thấp.
> **Chưa vá gì cả** - đúng như mục 9 của kế hoạch, việc vá là quyết định của chủ dự án.

## Tóm tắt cho người bận

Ba câu đáng nhớ nhất từ đợt này:

1. **Lỗ hổng nặng nhất không nằm trong framework, nó nằm ở CÁCH 21 app cấu hình xác thực.**
   Khi không lấy được khóa verify JWT, các app **không cài middleware xác thực** rồi chạy tiếp
   với một dòng log cảnh báo. Toàn bộ API thành công khai. Mà `application.yml` bị gitignore ở
   30/31 repo, nên **một lần clone rồi chạy là rơi đúng vào nhánh đó**.
2. **Framework mặc định KHÔNG an toàn ở bốn chỗ và không nói gì cả**: gRPC chạy plaintext không
   client cert, OPC UA mức bảo mật None, MQTT không TLS, WebSocket không đi qua xác thực. Cả bốn
   đều im lặng - không một dòng log nào cho biết đang chạy chế độ mở.
3. **Chủ dự án lo "lỗi framework là sập toàn bộ" - nỗi lo đó có cơ sở, và ở đúng chỗ không ngờ**:
   `Application._run_async` dùng `asyncio.TaskGroup`, nên **một adapter chết là mọi adapter còn
   lại bị hủy theo**. gRPC lỗi thì HTTP tắt cùng.

Bốn thứ **làm tốt**, ghi lại để không ai sửa nhầm: `_RequestContext` sao chép dict theo kiểu
copy-on-write nên không rò dữ liệu giữa request (đây là loại lỗi tệ nhất trong app async, và nó
đã được xử lý đúng); không có `eval`/`exec`/`pickle`/`yaml.load`/`shell=True` ở đâu trong 21.446
dòng; `PyJwtTokenVerifier` ép `algorithms=[key_context.algorithm]` nên không có cửa alg
confusion; `LocalFileStorage._resolve` có phòng tuyến thứ hai bằng `.resolve()` và nó **đã chặn
thật** khóa `..\..\` mà lớp kiểm tra thứ nhất cho lọt (PoC 7).

## Bảng phát hiện

> **Cột trạng thái cập nhật 2026-08-03** (bản 0.7.1): **đợt 2 của kế hoạch vá đã
> thi công xong** - mười mục framework F2, F4, F5, F6, F7, F8, F11, F12, F13,
> F16 đã vá, có test canh, và PoC tương ứng đã chạy lại. Nhóm A (app) và các mục
> framework còn lại **chưa vá**. Chi tiết: [`ket-qua-0.7.1-2026-08-03.md`](ket-qua-0.7.1-2026-08-03.md).

| Mã | Mức | Phát hiện | Ảnh hưởng | Trạng thái |
|---|---|---|---|---|
| **A1** | 🔴 NGHIÊM TRỌNG | Không có khóa JWT -> app KHÔNG cài middleware xác thực, vẫn chạy | 21 codebase | ⬜ chưa vá |
| **A2** | 🟠 CAO | `allow_origin_regex` khớp **mọi IPv4 công cộng**, kèm `allow_credentials: true` | 23 codebase | ⬜ chưa vá |
| **A3** | 🟠 CAO | Sáu app Monolithic ký JWT HS256 bằng **cùng một secret literal**; ở `shop` nó nằm trong git và app đã deploy | 6 app | ⬜ chưa vá |
| **F1** | 🟠 CAO | WebSocket đi thẳng qua `JwtAuthMiddleware` | framework (chưa app nào dùng WS) | ✅ vá 2026-08-18 (0.7.2) |
| **F2** | 🟠 CAO | `save_upload` tin Content-Type của client, `stream_object` phát lại inline -> XSS lưu trữ | framework | ✅ vá 0.7.1 |
| **F3** | 🟠 CAO | Sàn dependency cho phép bộ thư viện có **26 CVE**, gồm PyJWT 2.8.0 | mọi bản cài mới | ✅ vá 2026-08-18 (0.7.2) - **rộng hơn đề xuất gốc**, xem mục F3 |
| **F4** | 🟡 TRUNG | `configure_cors` không kiểm kiểu giá trị YAML -> chuỗi thành wildcard / khớp chuỗi con | framework | ✅ vá 0.7.1 |
| **F5** | 🟡 TRUNG | `RuntimeConfig.__repr__` in ra toàn bộ secret | framework | ✅ vá 0.7.1 |
| **F6** | 🟡 TRUNG | Bốn mặc định không an toàn, không cảnh báo (gRPC, OPC UA, MQTT, socket ngoài Linux) | framework | ✅ vá 0.7.1 |
| **F7** | 🟡 TRUNG | Thiếu file profile YAML -> im lặng chạy bằng config gốc | framework | ✅ vá 0.7.1 |
| **F8** | 🟡 TRUNG | `Content-Disposition` dựng bằng f-string: tên file tiếng Việt -> HTTP 500 | framework | ✅ vá 0.7.1 |
| ~~**F9**~~ | 🟡 TRUNG | `_read_peer_app_id` tìm chuỗi trong MỌI loại SAN | framework | ⛔ **KHÔNG CÒN ÁP DỤNG** - `_read_peer_app_id` đã bị **XOÁ** ở 0.7.1 khi gỡ phụ thuộc khái niệm; `current_peer_sans()` trả SAN thô, không lọc scheme, nên không còn chuỗi nào để neo |
| **F10** | 🟡 TRUNG | Một adapter chết kéo sập cả tiến trình (`TaskGroup`) | framework | ➡ **DỜI SANG 0.8** - nó mở rộng `Adapter` protocol (đổi API cho cả adapter người dùng tự viết), và supervisor của 0.8 cần đúng tín hiệu "ready" đó |
| **F11** | 🟡 TRUNG | `audience` mặc định KHÔNG ép | framework | ✅ vá 0.7.1 |
| **A4** | 🟡 TRUNG | `/docs`, `/redoc`, `/openapi.json` nằm trong `public_paths` | toàn bộ app | ⬜ chưa vá |
| **A5** | 🟡 TRUNG | 6 app Monolithic: thiếu header Authorization -> đi tiếp **ẩn danh** | 6 app | ⬜ chưa vá |
| **A6** | 🟡 TRUNG | Tài liệu bảo để secret vào `application-secret.yml` - framework **không nạp file đó** | shop + khuôn mẫu | ⬜ chưa vá |
| **F12** | ⚪ THẤP | `ErrorMappingInterceptor` gửi tên class exception nội bộ cho **mọi** lỗi | framework | ✅ vá 0.7.1 |
| **F13** | ⚪ THẤP | localfs: quyền file 0644, tên file tạm đoán được, `put()` không nguyên tử | framework | ✅ vá 0.7.1 |
| **F14** | ⚪ THẤP | `validate_object_key` cho lọt khóa có `\` (khác nhau giữa các backend) | framework | ✅ vá 2026-08-18 (0.7.2) |
| **F15** | ⚪ THẤP | `EventBus.publish` tạo task không giới hạn | framework | ✅ vá 2026-08-18 (0.7.2) |
| **F16** | ⚪ THẤP | `save_upload` không có giới hạn dung lượng mặc định | framework | ✅ vá 0.7.1 |
| **F17** | ⚪ THẤP | MQTT RPC trả lời về `ResponseTopic` do client chỉ định | framework | ✅ vá 2026-08-18 (0.7.2, **cảnh báo chứ không chặn**) |
| **A7** | ⚪ THẤP | `callback_secret` là chuỗi literal yếu, giống nhau theo khuôn mẫu | nhiều app | ⬜ chưa vá |

---

# NHÓM A - CÁC APP

## 🔴 A1 - Không lấy được khóa JWT thì app bỏ luôn xác thực (21 codebase)

**Chỗ:** `app/config/jwt.py` của mỗi app, ví dụ
`Application Layer/trung-tam-day-hoc/backend/app/config/jwt.py:78-99`.

```python
def configure() -> None:
    config = _load_config()
    keyset = _build_keyset(config)

    if keyset is None:
        logger.warning(
            "Chưa có khóa verify JWT (...) -> middleware JWT KHÔNG cài. "
            "Chỉ dùng cho dev; production PHẢI có key."
        )
        return                      # <-- thoát ở đây

    configure_middleware(TrustJwtAuthMiddleware, ...)   # <-- không bao giờ chạy
```

`_build_keyset` trả `None` khi `trust.enabled` là false/vắng **và** không có `public_key_pem`/
`public_key_file`. Lúc đó `configure_middleware` không được gọi, nên FastAPI dựng lên **không có
middleware xác thực nào**. Mọi route - danh sách khách, doanh thu, đơn hàng, chấm công - trả 200
cho request không có token.

**Vì sao đây không phải chuyện lý thuyết.** `trust.enabled: true` nằm trong `application.yml`, mà
`application.yml` **bị gitignore ở 30/31 repo** (kiểm bằng `git check-ignore`, chỉ
`Monolithic/shop/backend` là theo dõi). Nghĩa là đường đi tự nhiên nhất:

```
git clone <repo>  ->  không có application.yml  ->  RuntimeConfig rỗng
                  ->  trust.enabled = False (mặc định của .get)
                  ->  không có key tĩnh  ->  keyset = None
                  ->  API MỞ TOANG, chỉ có một dòng WARNING trong log
```

Nối thêm **F7** (framework im lặng khi thiếu file YAML) thì cả chuỗi này không có một chỗ nào
dừng lại.

**Kịch bản khai thác:** `curl https://app.example/api/v1/customers` không kèm token. Không cần
kỹ thuật gì.

**Đề xuất:** đảo thành fail-closed. Không có khóa thì **ném `StartupException`**, trừ khi có một
cờ tường minh kiểu `auth.jwt.allow_insecure_dev: true` viết thẳng trong YAML. Nguyên tắc: "thiếu
cấu hình bảo mật thì không khởi động được" chứ không phải "thiếu thì bỏ qua bảo mật". Sửa ở
`saas-foundation/template` rồi lan xuống 20 bản sao.

## 🟠 A2 - CORS chấp nhận mọi địa chỉ IP công cộng, kèm cookie (23 codebase)

**Chỗ:** `resources/application.yml` của 24 codebase (23 app + template), ví dụ
`Service ngang/crm/backend/resources/application.yml:40`:

```yaml
cors:
  allow_origins: ["http://localhost:8178", "http://localhost:8171"]
  # DEV: khớp localhost / IP LAN mọi cổng. Production đặt null để TẮT regex này.
  allow_origin_regex: '^http://(localhost|(\d{1,3}\.){3}\d{1,3})(:\d+)?$'
```

cộng với `configure_cors(allow_credentials=True, allow_methods=["*"], allow_headers=["*"])`
trong `app/config/web.py`.

**Chú thích trong file nói "IP LAN". Regex KHÔNG giới hạn ở LAN.** `(\d{1,3}\.){3}\d{1,3}` khớp
**mọi** địa chỉ IPv4, kể cả IP công cộng:

```
re.fullmatch(regex, 'http://203.0.113.66')  -> khớp
re.fullmatch(regex, 'http://8.8.8.8:9999')  -> khớp
```

PoC 12 chạy với đúng cấu hình trên:

```
Origin http://localhost:8171     -> ACAO='http://localhost:8171'  ACAC='true'
Origin http://203.0.113.66       -> ACAO='http://203.0.113.66'    ACAC='true'  <== ĐỌC ĐƯỢC
Origin http://8.8.8.8:9999       -> ACAO='http://8.8.8.8:9999'    ACAC='true'  <== ĐỌC ĐƯỢC
Origin https://ke-tan-cong.example -> ACAO=None
```

**Kịch bản khai thác:** kẻ tấn công thuê một VPS, **không cần tên miền, không cần chứng chỉ**, để
trang độc ở `http://<IP-của-nó>/`. Dụ một chủ tiệm đang đăng nhập mở trang đó. JavaScript trên
trang gọi chéo miền tới API của app, trình duyệt cho đọc phản hồi vì `ACAO` khớp và `ACAC: true`.
`allow_methods: ["*"]` nên ghi cũng được.

**Điều kiện, nói cho đúng:** để cookie phiên đi kèm request chéo miền thì cookie phải là
`SameSite=None; Secure`. Ở `Monolithic/shop` thì **đúng là vậy** -
`application-production.yml` đặt `cookie.samesite: "none"`. Với các app dùng cookie refresh của
identity-service (Java, ngoài phạm vi đợt này) thì phải kiểm riêng. Nhưng ngay cả khi cookie
không đi kèm, việc trả `Access-Control-Allow-Credentials: true` cho một origin do kẻ tấn công
chọn đã là hỏng hàng rào origin, và bất kỳ luồng nào dựa vào cookie đều thủng.

Chỉ **1/24** codebase có `application-production.yml` tắt regex này (`Monolithic/shop`). 23 chỗ
còn lại thì cấu hình dev **chính là** cấu hình production.

**Đề xuất:** bỏ hẳn regex khỏi `application.yml` gốc, chuyển sang `application-local.yml` (vốn
đã có ở 15 repo và không dùng khi deploy). Nếu vẫn muốn giữ tiện lợi khi dev thì siết regex về
đúng dải riêng: `127\.0\.0\.1|localhost|192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.`.

## 🟠 A3 - Sáu app Monolithic ký JWT bằng cùng một secret, và ở `shop` nó nằm sẵn trong git

**Chỗ:** `Monolithic/shop/backend/resources/application.yml:19` (file này **có trong git**):

```yaml
jwt:
  secret: "dev-secret-CHANGE-IN-PRODUCTION-use-32chars-minimum"
```

`app/service/authentication_service.py:79` ký bằng HS256 với chính giá trị đó, và fallback trong
code cũng là literal: `config.get("jwt.secret", "dev-secret-CHANGE-IN-PRODUCTION")`.

`application-production.yml` **cũng nằm trong git** và **không đè `jwt.secret`** - nó chỉ đè
`cookie` và `cors`. Framework không có nội suy biến môi trường (đây là quyết định thiết kế đã
chốt), nên không có đường nào khác để giá trị thật lọt vào.

**Hậu quả:** HS256 là khóa đối xứng - biết secret là **ký được token cho bất kỳ `uid` nào**. Ai
đọc được repo là đăng nhập được với tư cách bất kỳ người dùng nào, gồm cả quản trị. Không cần
mật khẩu, không cần chạm vào máy chủ.

App này đang chạy thật: `application-production.yml` khai origin `https://shop.scime.click`.

### Bổ sung sau khi rà lại (cùng ngày): cả SÁU app Monolithic dùng CHUNG một chuỗi ký

Không chỉ `shop`. `auto-garage`, `dental-clinic`, `english-center`, `rental-management`, `spa`
đều có **đúng cùng một giá trị** trong `backend/resources/application.yml`:

```
secret: "dev-secret-CHANGE-IN-PRODUCTION-use-32chars-minimum"
```

Khác biệt về mức độ, phải nói cho chính xác:

- **`shop`**: giá trị nằm **trong git** và app **đã deploy**. Đây là chỗ nghiêm trọng.
- **5 app còn lại**: chưa phải repo git (`git rev-parse` báo không phải repo), chưa có
  `application-production.yml`, nên chưa deploy. Nhưng giá trị thì y hệt, và nó là một literal
  đoán được, xuất hiện cả trong code làm giá trị fallback.

**Kiểm và ĐẠT một chỗ, ghi lại để không lo thừa:** `validate_token` của cả sáu app **có** ép
`audience` + `issuer` và `options={"require": ["jti","exp","iss","aud"]}`, mỗi app một `aud` riêng
(`https://garage.scime.click`...). Nên token của app này **không** dùng lại được ở app kia. Việc
dùng chung secret không tạo ra lỗ hổng chéo app.

Nhưng nó không cứu được gì trước việc lộ secret: biết secret thì tự ký một token với đúng `aud`
của app đích là xong. Ép `aud` chặn tái sử dụng token, không chặn giả mạo token.

**Đề xuất:** coi secret này là **đã lộ** - đổi ngay và vô hiệu mọi token đang sống của `shop`,
đừng chỉ sửa file. Năm app còn lại đổi trước khi deploy, mỗi app một giá trị ngẫu nhiên riêng
(`secrets.token_urlsafe(32)`), và **bỏ luôn giá trị fallback trong code** để thiếu cấu hình là
nổ chứ không phải im lặng dùng chuỗi đoán được. Sau đó dứt secret ra khỏi file trong git (xem A6
- chỗ tài liệu bảo để secret vào là một file framework không bao giờ đọc).

## 🟡 A4 - `/docs`, `/redoc`, `/openapi.json` mở công khai ở toàn bộ app

Mọi `application.yml` đều có:

```yaml
    public_paths:
      - /openapi.json
      - /docs
      - /redoc
      - /health
```

Toàn bộ bản đồ API - đường dẫn, tham số, tên trường, mã lỗi - đọc được mà không cần đăng nhập.
Đây không phải lỗ hổng tự thân, nhưng nó **rút ngắn giai đoạn thăm dò xuống gần bằng không** và
làm cho A1 dễ khai thác hơn nhiều: có OpenAPI thì biết chính xác gọi cái gì.

**Đề xuất:** giữ `/health` public; bỏ ba đường còn lại khỏi `public_paths` ở production, hoặc tắt
hẳn (`configure_openapi(docs_url=None, ...)`).

## 🟡 A5 - Sáu app Monolithic: không có token thì đi tiếp ẩn danh

**Chỗ:** `Monolithic/{shop,spa,auto-garage,dental-clinic,english-center,rental-management}/backend/app/security/jwt_middleware.py:57-62`:

```python
if not auth_header:
    # Request ẩn danh - tiếp tục; controller quyết định có cần đăng nhập không
    await self.app(scope, receive, send)
    return
```

Mô hình này (fail-open ở middleware, kiểm quyền ở từng controller) hợp lệ, nhưng nó chuyển toàn
bộ trách nhiệm sang việc **mọi controller đều nhớ kiểm tra**. Một route mới quên gọi
`get_current_user()` là một route công khai, và **không có gì báo** - không test, không lint, không
lỗi lúc chạy.

**Đề xuất:** đảo mặc định: chặn hết, khai `public_paths` cho ngoại lệ (đúng như khuôn của 21 app
kia và của `JwtAuthMiddleware` trong framework). Nếu giữ nguyên vì đã port từ PHP thì tối thiểu
viết một test đếm số route và bắt buộc mỗi route phải nằm trong một trong hai danh sách
"cần đăng nhập" / "cố ý công khai".

## 🟡 A6 - Tài liệu chỉ chỗ để secret vào một file framework không bao giờ đọc

`Monolithic/shop/backend/resources/application-production.yml:4` viết:

> *"Không commit thông tin nhạy cảm thật vào đây (dùng `application-secret.yml` cho secret)."*

`YamlConfigLoader.load()` chỉ nạp đúng hai file: `application.yml` và `application-{env}.yml`.
**Không có cơ chế nào nạp `application-secret.yml`**, và file đó không tồn tại ở đâu trong cả hai
workspace.

Đây là nguyên nhân trực tiếp của **A3**: người viết tin rằng có chỗ an toàn để đặt secret, nên để
giá trị dev lại trong file gốc.

**Đề xuất:** chọn một trong hai, đừng để lửng lơ. Hoặc thêm thật vào loader một tầng thứ ba
(`application-secret.yml`, luôn gitignore, nạp sau cùng), hoặc sửa mọi chú thích để chỉ đúng vào
`application-local.yml` là thứ đang có thật.

## ⚪ A7 - `callback_secret` là literal yếu, sinh theo khuôn

`callback_secret: "s3cr3t-callback-nha-tro"`, `"s3cr3t-callback-dai-ly-phan-phoi"`,
`"s3cr3t-callback-internal"`... Bí mật HMAC xác thực webhook payment mà **đoán được từ tên app**.
Biết công thức là ký được callback giả "đã thanh toán".

Giảm nhẹ: các file này gitignore ở hầu hết repo. Nhưng khuôn đặt tên thì nằm trong tài liệu.

**Đề xuất:** sinh ngẫu nhiên (`secrets.token_urlsafe(32)`) lúc đăng ký app, không đặt tay.

---

# NHÓM F - FRAMEWORK

## 🟠 F1 - WebSocket không đi qua xác thực JWT

**Chỗ:** `xime/starters/jwt/_middleware.py:63-65`

```python
if scope["type"] != "http":
    await self.app(scope, receive, send)   # websocket đi thẳng
    return
```

và `WebSocketHandler.on_connect` mặc định (`xime/adapters/web/ws/_handler.py:48`) là
`await ws.accept()` - nhận mọi kết nối.

PoC 1, chạy thật:

```
HTTP  GET /api/secret  (không token) -> 401 {"detail":"Missing authorization token"}
WS    /ws/secret       (không token) -> KẾT NỐI ĐƯỢC, nhận: 'DU-LIEU-BI-MAT-CUA-TENANT'
```

Lập trình viên đọc docstring của `JwtAuthMiddleware` ("Path in public_paths? -> skip... All checks
pass -> authenticate") kết luận hợp lý rằng mọi thứ ngoài `public_paths` đều cần token. Route
`@ws` phá kết luận đó mà không có gì cảnh báo.

**Mức thật hiện tại: tiềm ẩn.** Đã quét cả hai workspace: **không app nào dùng WebSocket** (chỉ
framework và test của nó có). Nên hôm nay chưa có gì bị lộ. Nhưng `xime chat` nằm trong danh sách
sản phẩm, và app chat thì WebSocket là đường chính - ngày đó lỗ hổng này thành mức Cao thật.

**Đề xuất:** hai việc. (1) `RequestContextMiddleware` và `JwtAuthMiddleware` bỏ qua WS là đúng về
kỹ thuật ASGI, nhưng framework phải cấp một helper tương đương - ví dụ
`WebSocketHandler.require_auth(ws)` verify token từ query string hoặc subprotocol rồi gọi
`authenticate()`. (2) Đổi mặc định `on_connect`: nếu `configure_jwt()` đã được gọi mà handler
không override `on_connect`, thì **từ chối** kết nối kèm thông báo rõ, thay vì accept.

### ✅ ĐÃ VÁ 2026-08-18 (0.7.2)

Chủ dự án chốt làm ngay trong 0.7.2 - **vượt luật "0.7.x không đổi API công khai"** của chính mình,
và đây là ngoại lệ có ý thức chứ không phải bỏ sót: F1 thêm API mới (`@ws`) và đổi hành vi mặc
định, nhưng **chưa app nào dùng WebSocket** nên hôm nay đổi là miễn phí, còn đợi tới sau `xime chat`
thì không.

### ⚠ Kiểm toán bỏ sót MỘT mảnh, và nó đổi cả bức tranh

Đo lại: **framework KHÔNG CÓ đường đăng ký route WebSocket nào cả.** Không `@ws`, không
`add_api_websocket_route`, không `websocket_route` - grep toàn `xime/` ra rỗng. `WebSocketHandler`
là một lớp nền **không có cách nào gắn vào ứng dụng**, và chính docstring của nó viết *"routing API
sẽ được thiết kế sau"*. Tài liệu công khai nói đúng như vậy ở hai chỗ:

| Chỗ | Nội dung (trước bản vá) |
|---|---|
| `docs/vn/routing.md` | *"WebSocket và gRPC routing - chưa trong scope của class-based controller"* |
| `docs/vn/contributing.md` | WebSocket support nằm trong **danh sách việc mời đóng góp** |

PoC 1 chạy được là vì nó **tự dựng `WebSocketRoute` bằng Starlette**, không đi qua đường nào của
Xime. Nên gọi F1 là "vá lỗ hổng" là gọi sai tên: **WebSocket của Xime chưa được hoàn thành, và cái
chưa hoàn thành đó bao gồm cả phần xác thực.** Thêm mỗi `require_auth()` như đề xuất gốc là thêm
một helper **không có nhà** - không app nào gọi được vì không app nào đăng ký được route.

### ⭐ Chỗ lệch khỏi đề xuất, và đây là phần đáng đọc nhất

Đề xuất (2) nói: đổi mặc định `on_connect` thành **từ chối**. Bản vá **không làm vậy** - xác thực
chạy ở **lớp đăng ký route**, trước khi vào handler.

> Đặt phép từ chối vào `on_connect` là biến nó thành một mặc định mà **lớp con xoá đi chỉ bằng cách
> override method đó** - tức là chốt chặn biến mất đúng lúc người ta viết code mà tài liệu bảo họ
> viết. Mà `on_connect` là method đầu tiên ai cũng override.

Có test canh riêng cho điều này (`TestAuthCannotBeOverriddenAway`): một handler tự gọi
`socket.accept()` và **không** gọi `super()` vẫn không tới được, vì phép kiểm nằm ngoài nó. Override
cả `handle()` cũng không bỏ qua được.

### Bốn quyết định của chủ dự án

| Câu | Chốt |
|---|---|
| Token đi đường nào | **Subprotocol** (`Sec-WebSocket-Protocol`), chuẩn ngành - Kubernetes và Firebase đều dùng |
| Mặc định | **Từ chối** |
| Có làm đường đăng ký route không | **Có** |
| mTLS | *"gRPC 2 dịch vụ mới cần mTLS hai chiều; robot, điện thoại, websocket thì một chiều là đủ"* - đúng, với một đính chính: *"một chiều"* nói về **tầng vận chuyển**; client vẫn được xác thực, chỉ là ở **tầng ứng dụng** bằng token |

### Hiện thực

| Thành phần | Việc |
|---|---|
| `@ws("/path")` | Decorator **cấp lớp**, đánh dấu một `WebSocketHandler`. Nổ ngay lúc import nếu gắn vào lớp không phải `WebSocketHandler` |
| `WebSocketRegistrar` | Đăng ký route, **xác thực chạy trước handler** |
| `JwtAuthenticator` | **Tách khỏi `JwtAuthMiddleware`** để HTTP và WebSocket dùng **chung một** định nghĩa "token hợp lệ". Hai bản là hai chỗ phải sửa khi thêm knob, và cái không ai nhớ sẽ mục |
| `split_subprotocols` | Tách `["xime.bearer.<jwt>", "xime"]` thành (token, thứ vọng lại). **Không bao giờ vọng lại entry chở token** - làm vậy là gửi token về đúng nơi vừa hỏi |
| `close_on_token_expiry` | Mặc định **BẬT**: đóng kết nối khi token hết hạn |
| Cảnh báo khởi động | Có route `@ws` mà chưa gọi `configure_jwt()` thì WARNING nêu tên từng handler |

**Bốn chi tiết cố ý:**

1. **Mọi lần từ chối dùng chung mã đóng 3000 và không nói bước nào hỏng.** Bắt tay không có body để
   chở lý do, và hành động của client giống hệt nhau ở cả bốn ca - lấy token hợp lệ rồi thử lại -
   nên tách ra chỉ mách kẻ tấn công biết nửa nào của phỏng đoán là đúng. Lý do thật đi vào **log**.
2. **`public_paths` dùng chung với HTTP**, không đẻ ra danh sách thứ hai: *"đường này mở"* nên mang
   một nghĩa trong một ứng dụng.
3. **Đồng hồ canh hết hạn là task riêng, không bọc `receive()` bằng `wait_for`** - bọc thì huỷ
   `receive()` giữa chừng và một message đang trên đường có thể mất.
4. **Đóng vì hết hạn dùng CÙNG mã 3000 với bắt tay bị từ chối**, cố ý: client làm đúng một việc
   trong cả hai ca. Đúng phanh thứ hai của [luật 03 mục 4e](../../../.claude/rules/03-mot-gia-tri-mot-nghia.md)
   - phép kiểm là *"người gọi có làm hai việc khác nhau không"*, không phải *"hai tình huống có khác
   nhau không"*.

### ⛔ Kiểm `Origin` - cố ý KHÔNG làm, và lý do phải đọc kỹ

Trình duyệt **không áp CORS lên bắt tay WebSocket**, nên *Cross-Site WebSocket Hijacking* là rủi ro
thật - **nhưng chỉ khi xác thực dựa vào cookie**, vì lúc đó trình duyệt tự gửi cookie cho một trang
web bất kỳ. Chọn subprotocol đã đóng rủi ro đó **ở gốc**: trang của kẻ tấn công **không có token**
để đưa vào.

⚠ **Ngày nào có người thêm đường xác thực bằng cookie thì kiểm `Origin` thành BẮT BUỘC.** Đã ghi vào
`docs/{vn,en}/websocket.md` mục 7.

### Test

**31 test mới** (`test_ws_auth.py` 22 + `test_ws_registration.py` 9), đi thành **cặp** ở mọi chỗ:
từ chối/nhận · override được/không bỏ qua được · trong `public_paths`/ngoài · có JWT/không có JWT ·
đồng hồ canh bật/tắt.

**Đối chứng**: gỡ lời gọi `_authenticate` thì **5 đỏ**, gồm cả test then chốt về việc override không
bỏ qua được xác thực.

⚠ **Hai lỗi trong chính bộ test này, ghi lại vì chúng là khuôn dễ lặp:**

1. **TTL dưới một giây không dùng được** - PyJWT ép `exp` về số nguyên, nên `exp = now + 0.1` bị cắt
   xuống dưới `now` và token chết ngay lúc bắt tay.
2. ⭐ **Bản test đầu chỉ đòi "bị ngắt" nên nó XANH cả khi bắt tay bị từ chối** - tức nó đo đúng
   triệu chứng của một nguyên nhân hoàn toàn khác. Nay test khẳng định bắt tay **đã thành công**
   (nhận được một message) trước rồi mới đợi bị ngắt, và kiểm luôn mã đóng.

### Một lỗi thật do script phát hành bắt được

`check_doc_imports.py` báo `from xime.starters.jwt import JWT_CLAIMS` **không chạy được**: hằng số
đó chưa bao giờ được export, nó nằm trong `_middleware`. Tài liệu WebSocket bảo người đọc tra claim,
mà chỉ họ vào một module có tên bắt đầu bằng gạch dưới là bảo họ thò tay vào ruột framework. Đã
export ở `xime/starters/jwt/__init__.py`.

**Đo**: framework **1624 passed, 11 skipped** (+31). PoC 1 chạy lại qua đường thật của Xime:
không token -> **đóng, mã 3000**; có token -> vào được, subprotocol vọng lại `'xime'`.

## 🟠 F2 - Cặp helper upload/download tạo sẵn một lỗ XSS lưu trữ

Hai dòng, hai file, ghép lại thành lỗ hổng:

`xime/adapters/web/files/_upload.py:47`
```python
resolved_type = content_type or upload_file.content_type   # Content-Type của CLIENT
await storage.put_stream(key, _chunks(), content_type=resolved_type)
```

`xime/adapters/web/files/_download.py:102`
```python
media_type = content_type or stat.content_type or _DEFAULT_MEDIA_TYPE
```

`upload_file.content_type` là header của phần multipart - **kẻ tấn công điều khiển hoàn toàn**.
`S3FileStorage.stat()` trả lại đúng giá trị đó (`_storage.py:222`). `stream_object` mặc định
`download=False`, và khi caller không truyền `filename` thì **không có `Content-Disposition` nào cả**.

PoC 8, chạy thật:

```
upload   -> 200; content_type đã lưu = 'text/html'
download -> 200; Content-Type trả về = 'text/html; charset=utf-8'
           X-Content-Type-Options = None
           Content-Disposition    = None
           thân phản hồi          = '<script>alert(document.domain)</script>'
=> trình duyệt CHẠY script này trên origin của app
```

Kẻ tấn công tải lên một "ảnh đại diện" tên `innocent.png` nhưng khai `Content-Type: text/html`,
rồi gửi link tới nạn nhân. Script chạy trên origin của app, đọc được token trong localStorage,
gọi API thay nạn nhân.

Giảm nhẹ một phần: `LocalFileStorage.stat()` luôn trả `content_type=None` nên chuỗi này chỉ nổ
với backend **S3/MinIO**. Nhưng S3 là backend dành cho production.

**Đề xuất:** ba lớp, làm cả ba. (1) `save_upload` không tin `upload_file.content_type` - suy từ
đuôi file bằng `mimetypes`, hoặc nhận allowlist từ caller, hoặc lưu là
`application/octet-stream` khi không chắc. (2) `stream_object` **luôn** gắn
`X-Content-Type-Options: nosniff`. (3) Với mọi media type không nằm trong danh sách an toàn
(ảnh, PDF, video), ép `Content-Disposition: attachment` bất kể tham số `download`.

## 🟠 F3 - Sàn dependency cho phép một bộ thư viện có 26 CVE

`pyproject.toml` khai sàn: `fastapi>=0.110.1`, `pydantic>=2.5`, `pyyaml>=6.0.1`,
`python-multipart>=0.0.7`, `pyjwt>=2.8`, `uvicorn[standard]>=0.27`.

Chú thích ngay trên đó ghi rõ các sàn này **đã được cài thử và chạy hết bộ test** - tức là chúng
được coi là tổ hợp hợp lệ, không phải con số cho có. `pip-audit` trên đúng tổ hợp đó:

```
Found 26 known vulnerabilities in 3 packages
python-multipart 0.0.7   7 advisory  (fix: 0.0.18 / 0.0.22 / 0.0.26 / 0.0.30 / 0.0.31)
pyjwt            2.8.0   8 advisory  (fix: 2.12.0 / 2.13.0)
starlette        0.37.2  11 advisory (fix: 0.40.0 / 0.47.2 / 1.x)
```

Đáng lo nhất là **PyJWT 2.8.0**: đây là thư viện đứng giữa mọi quyết định xác thực của mọi app.

Máy dev hiện tại đang cài bản mới (pyjwt 2.13.0, starlette 0.52.1, python-multipart 0.0.22) nên
**hệ thống đang chạy không dính**. Rủi ro nằm ở người cài mới: `pip install xime[jwt]` trong một
môi trường đã ghim sẵn phiên bản cũ sẽ giải ra đúng bộ trên mà không có gì phản đối. Đây là rủi
ro của **gói đã phát hành công khai 11 bản trên PyPI**, không phải rủi ro nội bộ.

**Đề xuất:** nâng sàn lên bản đã vá (`pyjwt>=2.13`, `python-multipart>=0.0.31`,
`fastapi>=0.115.3` để kéo starlette >= 0.40) và thêm `pip-audit` vào danh sách kiểm trước mỗi lần
phát hành, cạnh ba script đã có trong `.claude/scripts/`.

### ✅ ĐÃ VÁ 2026-08-18 - và bản vá RỘNG HƠN đề xuất trên, kèm một chỗ đề xuất SAI

Chi tiết đầy đủ trong `CHANGELOG.md` mục `[0.7.2]`. Ba thứ đáng đọc lại ở đây:

**1. Vế `fastapi>=0.115.3` để kéo starlette lên 0.40 là SAI.** Mọi bản fastapi từ 0.115 tới
0.132 khai `starlette>=0.40.0` với **nắp trên di chuyển còn cận dưới đứng yên**:

```text
0.115.3 -> starlette<0.42.0,>=0.40.0
0.128.0 -> starlette<0.51.0,>=0.40.0
0.133.0 -> starlette>=0.40.0            <- ban dau tien bo nap
```

Nên sàn fastapi **vĩnh viễn không kéo starlette quá 0.40**, bất kể nâng lên bao nhiêu. Mà
advisory của starlette chỉ vá trong nhánh **1.x**, không backport về 0.x.

> **Lái một phụ thuộc bắc cầu bằng sàn của phụ thuộc trực tiếp chỉ đi được tới cận dưới của
> nó - và cận dưới đó không phải của mình.**

Tệ hơn: đúng ca F3 lo (môi trường ghim fastapi cũ) là ca resolver chọn `0.115.3`, tức nắp
`<0.42.0`, tức đúng vùng còn advisory. Sàn đó che được ca không cần che và hở đúng ca cần che.

Lời giải: **khai `starlette` trực tiếp** (`>=1.3.1`) dù xime không import gì từ nó, cộng
`fastapi>=0.133.0` để nắp không chặn.

**2. Phạm vi thật rộng gấp đôi.** F3 chỉ soi sàn của core + web + jwt. Soi cả **28 sàn** thì
thêm `msgpack`, `aiosmtplib`, `protobuf`, `cryptography`, `pytest`. Cùng khuôn lỗi phạm vi đã
ghi ở nhiều nơi: *phép dò chỉ thấy thứ nó được trỏ vào*.

**3. Phép thử "cài ở đúng sàn rồi chạy test" ra nhiều lỗi hơn cả pip-audit** - và ba lỗi nó tìm
ra đều **không phải advisory**:

| Tìm ra | Loại |
| --- | --- |
| `aiomqtt>=2.0` + `paho-mqtt>=2.1` mâu thuẫn - `pip install xime[mqtt]` ở đúng sàn **bất khả thi** | hai sàn cùng extra chống nhau |
| `pytest>=9.0.3` + `pytest-asyncio>=0.23` nổ `INTERNALERROR`, dù metadata khai tương thích (`pytest>=7.0.0`, không nắp) | metadata là lời khai, không phải bằng chứng |
| `sqlalchemy>=2.0` **chưa bao giờ đúng**, lệch 38 bản patch | sàn sai từ ngày viết |

> ⭐ **Sàn là `>=`, nên pip mặc định cài bản MỚI NHẤT. Một sàn sai vì vậy hoàn toàn vô hình -
> cho tới ngày có người ghim xuống, và khi đó nó đã thành vấn đề của họ.**

**Còn một advisory KHÔNG vá được, đã ghi nhận:** `apscheduler` PYSEC-2026-282 (RCE qua
`JSONSerializer`/`CBORSerializer`), dải `4.0.0a1..4.0.0a6` không có bản vá và `4.0.0a6` là bản
mới nhất tồn tại. Xime không dính ở cấu hình mặc định (`AsyncScheduler()` -> `MemoryDataStore`
+ `LocalEventBroker`, không serializer). ⚠ Nhưng **an toàn đó thuộc về cách nối dây mặc định,
không thuộc về thư viện**: app tự cấu hình kho ngoài thì có dính.

**Phần `pip-audit` vào quy trình: đã làm**, thành `.claude/scripts/check_dep_advisories.py`
(bước 1b của hướng dẫn phát hành). Nó soi **bộ sàn khai trong `pyproject.toml`**, không soi môi
trường đang chạy - vì máy dev bao giờ cũng có bản mới, nên nó luôn sạch và luôn vô nghĩa.

## 🟡 F4 - `configure_cors` không kiểm kiểu giá trị đọc từ YAML

**Chỗ:** `xime/adapters/web/_cors.py:88` - `FromConfig(f"cors.{name}", _CORS_DEFAULTS[name])`
lấy giá trị YAML thô rồi đưa thẳng cho `CORSMiddleware`, không kiểm kiểu.

Operator viết thiếu ngoặc vuông - lỗi YAML phổ biến nhất - thì:

| YAML | Starlette hiểu thành | Hậu quả |
|---|---|---|
| `allow_origins: "*"` | `"*" in "*"` là True -> **wildcard** | mọi origin, kèm credentials |
| `allow_origins: "https://app.example.com"` | so khớp bằng `in` trên **chuỗi** | `https://app.example.co` cũng khớp |

PoC 2, chạy thật:

```
allow_origins: "*" + credentials true
  Origin https://ke-tan-cong.example -> ACAO='https://ke-tan-cong.example' ACAC='true'
allow_origins: "https://app.example.com"
  Origin https://app.example.co      -> ACAO='https://app.example.co'      ACAC='true'
```

Ca thứ hai đáng sợ hơn ca thứ nhất: nó **trông giống một cấu hình đúng**. Kẻ tấn công chỉ cần
đăng ký một tên miền là chuỗi con của tên miền thật (`.co` thay vì `.com`) là qua.

**Kèm theo: chú thích bảo mật trong chính file đó đang SAI.** Dòng 22-23 viết *"KHÔNG dùng
`allow_origins=["*"]` khi `allow_credentials=True` (trình duyệt sẽ chặn)"*. Trình duyệt **không**
chặn - Starlette phát hiện có cookie rồi **phản chiếu lại origin của người gọi** thay vì trả `*`,
nên hàng rào biến mất một cách im lặng. Một người đọc chú thích đó sẽ tin rằng framework tự bảo
vệ mình.

**Đề xuất:** `configure_cors` ép kiểu và fail-fast: `allow_origins` không phải list/tuple thì ném
`StartupException`; `"*"` kèm `allow_credentials=True` thì cũng ném. Và sửa lại chú thích cho
đúng sự thật.

## 🟡 F5 - `RuntimeConfig` in ra toàn bộ secret khi bị log

**Chỗ:** `xime/core/config/runtime.py:103` - `model_config = {"extra": "allow"}`. Mọi khóa
ứng dụng (database, jwt, s3, mail...) thành field của một Pydantic model, và `__repr__` mặc định
của Pydantic in **hết**.

PoC 9:

```python
cfg = RuntimeConfig.from_dict({
    "database": {"url": "postgresql://xime:SIEU_MAT_KHAU@db/xime"},
    "jwt": {"secret": "KHOA-KY-JWT-BI-MAT"},
})
repr(cfg)   # chứa nguyên văn cả hai
```

Một dòng `logger.info("config=%s", config)` khi debug, hoặc một exception nào đó lỡ nhét config
vào message, là mật khẩu database và khóa ký JWT nằm trong log. `LoggingConfig` mặc định
`enabled: True` ở mức INFO ghi ra stdout, tức là vào log container / log tập trung.

Framework hiện **không** log config ở đâu (đã kiểm bằng grep) - nên đây là mìn chưa nổ, không
phải rò rỉ đang diễn ra.

**Đề xuất:** override `__repr__`/`__str__` của `RuntimeConfig` để che giá trị của các khóa có tên
khớp `secret|password|token|key|credential`, giữ nguyên `.get()`. Rẻ, không phá gì.

## 🟡 F6 - Bốn mặc định không an toàn, và không chỗ nào nói ra

| Chỗ | Mặc định | Nghĩa là |
|---|---|---|
| `grpc/_config.py:22-26` | `tls.enabled=False`, `mutual=False` | `add_insecure_port` - plaintext, ai gọi cũng được |
| `opcua/_config.py:42,131` | `security="None"` (client và server) | không mã hóa, không xác thực |
| `mqtt/_config.py:64` | `tls=None` | username/password đi trên dây trần |
| `socket/_peercred.py:57-60` | không đọc được SO_PEERCRED -> `return True` | ngoài Linux thì không kiểm gì |

Điểm chung là **không có một dòng log nào** cho biết đang chạy chế độ mở. `GrpcAdapter.start()`
gọi `add_insecure_port` (`_adapter.py:142`) rồi chạy tiếp, im lặng. Với gRPC thì hậu quả cụ thể:
mọi thứ dựa trên `current_caller()` / `current_app_id()` (mô hình "hồn - xác" của cả nền tảng)
trả `None`, vì `auth_context()` chỉ có dữ liệu x509 khi có client cert đã verify.

**Đề xuất:** không đổi mặc định (sẽ phá tương thích ngược), nhưng **log `WARNING` một lần lúc
khởi động** cho từng chế độ không an toàn, nêu rõ khóa YAML cần bật. Người vận hành nhìn log là
biết. Riêng chế độ slave Modbus và server OPC UA - vốn cho ghi vào thiết bị - nên có thêm một
mục cảnh báo trong `docs/{vn,en}/modbus.md` và `opcua.md`.

## 🟡 F7 - Thiếu file profile YAML thì im lặng chạy bằng config gốc

**Chỗ:** `xime/core/config/loader.py:42-47`

```python
def _load_file(self, filename: str) -> dict[str, Any]:
    path = self._resources_dir / filename
    if not path.exists():
        return {}          # <-- im lặng
```

PoC 11: `XIME_ENV=production` mà không có `application-production.yml` -> nạp được, không cảnh
báo, chạy bằng cấu hình dev.

Ghép với **A1** và **A2** thì đây là mắt xích giữa: gõ nhầm tên file, hoặc quên copy file lúc
deploy, thì app lên bình thường - nhưng chạy bằng CORS dev và không có khóa JWT.

Đã kiểm và **KHÔNG phải lỗ hổng**: `XIME_ENV` ghép vào `application-{env}.yml` **không** dùng
được để đọc file ngoài `resources/` (PoC 10 - `../NGOAI` không nạp được, vì `..` không thành
segment riêng sau tiền tố `application-`).

**Đề xuất:** khi `detect_env()` trả về một giá trị mà file tương ứng không tồn tại, log `WARNING`
nêu đúng đường dẫn đã tìm. Cân nhắc thêm cờ `xime.config.require-profile: true` để production
fail-fast.

## 🟡 F8 - `Content-Disposition` dựng bằng f-string: tên file tiếng Việt làm hỏng phản hồi

**Chỗ:** `xime/adapters/web/files/_download.py:108`

```python
headers["Content-Disposition"] = f'{disposition}; filename="{filename}"'
```

Header HTTP mã hóa bằng latin-1. PoC 3/6:

| Tên file | Kết quả |
|---|---|
| `Hóa đơn.pdf` | `UnicodeEncodeError` -> **HTTP 500** |
| `a".pdf` | `filename="a".pdf"` - thoát khỏi dấu nháy, sửa được tham số header |
| `a.pdf\r\nSet-Cookie: ...` | uvicorn (cả `h11` lẫn `httptools`) **đóng kết nối, không trả gì** |

Đã kiểm bằng uvicorn thật cho ca CRLF: **không tách được response** - đây là điểm cần nói rõ để
không thổi phồng. Nhưng hai ca còn lại là thật, và ca đầu gần như chắc chắn xảy ra: đây là sản
phẩm Việt Nam, người dùng đặt tên file có dấu là chuyện bình thường. Tải file nào tên có dấu là
lỗi 500 file đó.

**Đề xuất:** dựng header theo RFC 6266 - `filename="<phiên bản ASCII>"; filename*=UTF-8''<đã
percent-encode>` - và lọc bỏ ký tự điều khiển cùng dấu nháy trước khi ghép. `urllib.parse.quote`
làm được cả hai.

## ~~🟡 F9~~ - `_read_peer_app_id` tìm chuỗi trong MỌI loại SAN

> ⛔ **KHÔNG CÒN ÁP DỤNG từ 0.7.1.** Cả `_read_peer_app_id`, `PEER_APP_ID` và
> `current_app_id()` đã bị **XOÁ** khi gỡ phụ thuộc khái niệm (xem
> [`go-phu-thuoc-khai-niem-2026-08-17.md`](go-phu-thuoc-khai-niem-2026-08-17.md)). Thay bằng
> `current_peer_sans()` trả **mọi** entry SAN dạng thô, không lọc scheme, không kiểm độ dài - nên
> không còn chuỗi nào để neo và không còn phép lọc nào để làm rộng quá mức.
>
> ⚠ Đây là ca **một mục kiểm toán biến mất vì thứ nó nói tới bị xoá, không phải vì được vá.** Hai
> chuyện khác nhau: bản vá làm hành vi đúng lên, còn ở đây trách nhiệm **chuyển sang người gọi** -
> app nào cần lọc SAN thì tự lọc, và nếu họ lọc bằng `find()` thì F9 sống lại trong repo của họ.
> Bảng trạng thái ghi "chưa vá" suốt hai tuần vì không ai phân biệt hai chuyện đó.

Nội dung dưới đây giữ nguyên làm lịch sử.

**Chỗ:** `xime/adapters/grpc/interceptors/_context.py:120-127`

```python
position = entry.find(_APP_ID_SCHEME)     # tìm ở BẤT KỲ đâu trong chuỗi
if position < 0:
    continue
app_id = entry[position + len(_APP_ID_SCHEME):]
if len(app_id) != _APP_ID_LENGTH:
    continue
return app_id
```

gRPC phơi `x509_subject_alternative_name` là property **nhiều giá trị** gồm mọi loại SAN - DNS,
IP, email, URI - và giá trị trả về **không kèm tiền tố loại**. Nên một entry DNS hay email chứa
chuỗi `xime-app://` cộng đúng 33 ký tự sẽ được nhận là định danh app, dù nó không phải SAN URI.

Điều kiện khai thác: kẻ tấn công phải xin được cert từ Trust CA với SAN do nó tự khai. Theo tài
liệu nền tảng, *"Trust chỉ kiểm độ dài rồi khắc, KHÔNG gọi application-service"* - nên hàng rào
thật nằm ở chính sách cấp cert của Trust, không nằm ở đây. **Đợt này không kiểm Trust** (dịch vụ
Java, ngoài phạm vi), nên tôi ghi lại điều kiện thay vì khẳng định khai thác được.

Dù sao, việc đọc một định danh dùng để phân quyền bằng `find()` trên mọi loại SAN là rộng hơn
mức cần thiết.

**Đề xuất:** neo vào đầu chuỗi (`entry.startswith(...)`, chấp nhận thêm dạng `URI:` như hiện
tại) và, nếu phiên bản gRPC cho phép, chỉ duyệt entry loại URI. Việc này không phá tương thích vì
cert thật do Trust cấp vẫn ở dạng `xime-app://...` đứng đầu.

## 🟡 F10 - Một adapter chết kéo sập mọi adapter còn lại

**Chỗ:** `xime/core/bootstrap/application.py:153-158`

```python
async with asyncio.TaskGroup() as tg:
    for adapter in self._adapters:
        tg.create_task(adapter.start(self))
```

`TaskGroup` có ngữ nghĩa: **một task ném lỗi thì mọi task anh em bị hủy**. Chú thích ngay trên đó
nói rõ đây là chủ đích ("no orphaned background tasks"), và với lỗi *lúc khởi động* thì đúng.
Nhưng `adapter.start()` **chạy suốt vòng đời** (`await self._server.serve()` /
`wait_for_termination()`), nên luật đó áp cả cho lỗi *lúc đang chạy*: server gRPC ném một lỗi
không bắt được là web adapter bị hủy theo, tiến trình thoát. Một app đang phục vụ HTTP cho người
dùng thật tắt vì một sự cố ở kênh nội bộ.

Đây đúng là điều chủ dự án nêu khi đặt đợt kiểm toán này: *"không muốn lỗi framework là sập toàn
bộ"*.

**Đánh đổi phải cân nhắc, không có đáp án hiển nhiên:** giữ nguyên thì một adapter chết là mất
tất cả; đổi sang cô lập thì tiến trình sống với một adapter đã chết - và đó cũng là một kiểu hỏng
âm thầm. Hướng cân bằng: giữ nguyên hành vi khi lỗi xảy ra **trước khi phục vụ**, còn sau đó thì
cô lập, log `CRITICAL`, đánh dấu `/health` là không lành mạnh để bộ điều phối khởi động lại. Cần
chủ dự án quyết.

## 🟡 F11 - `audience` mặc định KHÔNG được ép

**Chỗ:** `xime/starters/jwt/_config.py:48` (`audience: str | list[str] | None = None`) và
`_verifier.py:84` (`options = {"verify_aud": audience is not None}`).

Bỏ trống thì token có claim `aud` vẫn được nhận. Trên một nền tảng mà identity-service ký token
cho **mọi** app bằng cùng bộ khóa, điều đó có nghĩa: token cấp cho `gym` dùng được ở `nha-tro`.
Docstring có cảnh báo đúng chỗ này, nhưng cảnh báo không phải cơ chế.

Giảm nhẹ: **không app nào dùng `configure_jwt` của framework** - cả 21 app đều tự viết
`TrustJwtAuthMiddleware` và **có** đặt `audience`/`issuer` từ YAML. Nên hôm nay không app nào
dính. Đây là rủi ro cho người dùng thứ ba của gói trên PyPI.

**Đề xuất:** giữ mặc định `None` nhưng log `WARNING` một lần lúc khởi động khi `configure_jwt`
được gọi mà không có `audience`.

## ⚪ F12 - `ErrorMappingInterceptor` gửi tên class exception nội bộ cho mọi lỗi

**Chỗ:** `xime/adapters/grpc/interceptors/_error.py:157`

`_safe_details()` cẩn thận trả `"Internal server error"` cho lỗi chưa map - nhưng ngay bên cạnh,
`_error_metadata(exc)` gửi `type(exc).__name__` trong trailing metadata cho **mọi** exception.
Client nhận được `IntegrityError`, `OperationalError`, `FileNotFoundError`... Ít giá trị với kẻ
tấn công, nhưng nó mâu thuẫn với chính ý định của hàm bên cạnh.

**Đề xuất:** chỉ gửi metadata `xime-error` cho exception **đã map**; lỗi chưa map thì gửi một mã
chung.

## ⚪ F13 - localfs: quyền file, tên file tạm, và `put()` không nguyên tử

`xime/starters/localfs/_storage.py`:

1. `open(tmp, "wb")` và `mkdir` dùng quyền mặc định -> thường là `0644`/`0755`. Dữ liệu khách
   đọc được bởi mọi user trên cùng máy. Framework không cho khai quyền.
2. Tên file tạm là `f"{path.name}.{os.getpid()}.part"` (dòng 135). PID **không** duy nhất theo
   request: hai lần upload cùng key trong cùng tiến trình dùng chung một file tạm, ghi đè lẫn
   nhau, rồi `os.replace` công bố kết quả lai. Đây là lỗi toàn vẹn dữ liệu, không phải chỉ lý
   thuyết.
3. `put()` (dòng 234) ghi thẳng bằng `path.write_bytes` - **không** nguyên tử, trong khi
   `put_stream` thì có. Docstring của class chỉ nói "ghi nguyên tử" chung chung.

**Đề xuất:** `uuid4().hex` thay `os.getpid()`; thêm `storage.local.file_mode` (mặc định `0o600`);
cho `put()` đi qua cùng đường staging như `put_stream`.

## ⚪ F14 - `validate_object_key` cho lọt khóa chứa `\`

`xime/starters/storage/_keys.py` dùng `PurePosixPath`, nên `\` là ký tự thường. PoC 4:

```
từ chối    '../../../etc/passwd'
CHẤP NHẬN  '..\\..\\..\\Windows\\System32\\config\\SAM'
CHẤP NHẬN  'C:\\Windows\\win.ini'
```

Docstring hứa *"Local và S3 đều áp dụng nên đổi backend không đổi tập key hợp lệ"* - lời hứa đó
không đúng: PoC 7 cho thấy `LocalFileStorage` **từ chối** đúng hai khóa mà `validate_object_key`
chấp nhận, vì nó có phòng tuyến thứ hai (`.resolve()` + kiểm `parents`).

**Không khai thác được**: phòng tuyến thứ hai giữ vững trên Windows, và trên Linux `\` là ký tự
tên file hợp lệ nên không có traversal. Đây là chuyện nhất quán, không phải lỗ hổng.

**Đề xuất:** `validate_object_key` từ chối luôn `\` và ký tự NUL, để hai backend nhận đúng một
tập khóa như docstring đã hứa.

### ✅ ĐÃ VÁ 2026-08-18 (0.7.2)

Từ chối `\` và NUL trong `validate_object_key`. Đo lại thì phạm vi thật **rộng hơn một trục** so
với báo cáo gốc: không phải hai backend nhận hai tập khóa, mà **ba** kết quả cho cùng một khóa.

| `..\..\Windows\System32\config\SAM` | Trước bản vá |
| --- | --- |
| `validate_object_key` | chấp nhận |
| Local trên **Windows** | từ chối (thoát root) |
| Local trên **Linux** | **nhận** - `\` là ký tự tên file hợp lệ, tạo một file tên đúng như vậy trong root |
| S3 | nhận, không phòng tuyến nào |

**NUL thì thuộc loại khác, và đó mới là phần đáng vá nhất** - nó không phải chuyện nhất quán mà là
hai lỗi hợp đồng, đo được:

```text
Path('C:/kho/a\x00b').exists()  ->  False, khong loi
open(...)                       ->  ValueError: embedded null character
```

- `exists()` trả **`False`** cho khóa không hợp lệ, tức người gọi không phân biệt được *"không có
  file"* với *"khóa sai"*. Đúng **dấu hiệu 3 của [luật 03](../../../.claude/rules/03-mot-gia-tri-mot-nghia.md)**.
- `put()` ném **`ValueError`** chứ không phải `StorageError`, tức rò kiểu ngoại lệ qua biên API
  công khai - người dùng bắt `StorageError` theo tài liệu thì không bắt được.

**Test đi thành cặp**, cả hai backend dùng **chung một danh sách** `UNSAFE_KEYS` (S3 `import` từ
file test của local, không chép tay - chép tay là cách hai backend trôi lệch nhau trong im lặng):

| Test | Kỳ vọng |
| --- | --- |
| `test_backslash_and_nul_rejected` | 4 khóa xấu bị từ chối ở **cả hai** backend |
| `test_ordinary_keys_still_accepted` | `a..b/c` và ba khóa thường **vẫn nhận** |

Vế thứ hai không thừa: chỉ có vế đầu thì cách sửa sai *"từ chối mọi thứ có dấu chấm"* cũng qua
được. `a..b/c` là cái bẫy - chứa `..` nhưng không phải một đoạn đường dẫn.

**Đối chứng đã chạy**: gỡ hai dòng vá thì **5 test đỏ** (1 local + 4 tham số S3), khôi phục thì
xanh. Không có đối chứng thì không biết test có canh gì thật không.

**Không app nào phải sửa**: `data-service` là nơi duy nhất gọi tầng storage, và `ObjectKeyPolicy`
của nó đã tự chuẩn hoá `filename.replace("\\", "/").split("/")[-1]` **trước** khi dựng khóa. Đo:
framework 1563 passed (+10), data-service 388 passed.

## ⚪ F15 - `EventBus.publish` tạo task không giới hạn

`xime/core/event/bus.py:76` - mỗi handler một `create_task`, không có trần, không có backpressure.
Đường đi người dùng nào publish event là kẻ tấn công nhân được số task theo số request.

Kèm theo, đáng ghi để người sau biết chứ không phải lỗi: task nền **sao chép context lúc tạo**,
nên handler chạy với `identity`/`JWT_CLAIMS` của người gửi request, và `clear_security()` cuối
request không đụng tới bản sao đó. Ngữ cảnh bảo mật sống lâu hơn request - hợp lý cho audit, nhưng
phải biết mà tính.

**Đề xuất:** thêm trần số task đang chờ (cấu hình được), quá trần thì từ chối và log.

### ✅ ĐÃ VÁ 2026-08-18 (0.7.2)

**Đo trước khi sửa** (ba phép, trên code cũ):

| Phép đo | Kết quả |
|---|---|
| 50.000 `publish`, 2 handler | **100.000 task đang chờ** |
| 20.000 event x payload 1 KB | **36,0 MB**, trung bình **1.889 byte/task** |
| Ngữ cảnh bảo mật sau `clear_security()` | trong request: `None` · **trong handler nền: `('user-42', ['ADMIN'])`** |

⭐ Phép đo thứ hai nói một chuyện mà báo cáo gốc chưa nói: `_pending` giữ **tham chiếu mạnh**,
task giữ coroutine, coroutine giữ **chính object event**. Nên bộ nhớ tăng theo **KÍCH THƯỚC
EVENT**, không theo một hằng số overhead. Event mang ảnh base64 hay danh sách bản ghi thì con số
1,9 KB kia thành vài trăm KB.

⭐ Phép đo thứ ba xác nhận ghi chú của báo cáo, và cộng với phép đo thứ hai nó thành một câu đáng
nhớ: **task tồn đọng cũng là quyền hạn tồn đọng.**

### Chủ dự án chốt: **BỎ**, và con số là việc của người thiết kế app

Ba phương án đưa lên - bỏ + log · chặn (backpressure) · ném lỗi. Chọn **bỏ**.

Nguyên văn về chỗ đặt cấu hình: *"bao nhiêu thì bỏ thì đây là việc của người thiết kế app. không
phải việc của tôi, cần đặt vào file cấu hình (file .py cho lập trình viên)"*.

Nên nó là **framework config, không phải runtime config**: `configure_event_bus()` trong
`config/*.py`, **không** có khoá nào trong `application.yml`. Lý do ghi lại thành phép kiểm chung ở
[`../rules/config-discovery.md`](../rules/config-discovery.md): *người vận hành có đủ thông tin để
chọn giá trị này không?* Trần này đòi biết **handler chạy bao lâu, event to cỡ nào, event nào không
được phép mất** - ba thứ người vận hành không biết.

```python
# config/event.py
from xime.core.event import configure_event_bus

configure_event_bus(max_pending=50_000, never_drop=(AuditEvent, PaymentEvent))
```

### ⭐ `never_drop` - chủ dự án bổ sung giữa chừng

Nguyên văn: *"cũng có cái cấu hình cho không bao giờ bỏ. lỡ cái quan trọng bỏ lại dở"*. Đây là
phần mà cả kiểm toán lẫn tôi đều thiếu: đề xuất gốc chỉ có **một** con số, mà một con số thì đối
xử với event kiểm toán y hệt event thông báo.

| Khai | Nghĩa |
|---|---|
| `never_drop=(AuditEvent,)` | Miễn trần cho vài loại, phần còn lại vẫn có trần. **Khớp kiểu chính xác**, giống cách tra handler - lớp con không thừa hưởng |
| `max_pending=None` | Bỏ trần hoàn toàn - đúng hành vi trước 0.7.2, là lựa chọn hợp lệ miễn là **có ý thức** |

⚠ `never_drop` **dời** rủi ro chứ không xoá: lũ event được miễn vẫn phình vô hạn, nên khi vượt trần
bus ghi WARNING nói đúng điều đó.

### Bốn quyết định hiện thực

1. **Bỏ NGUYÊN CON, không bao giờ bỏ nửa số handler.** Một tác dụng phụ xảy ra còn cái đi kèm thì
   không là trạng thái không ai thiết kế cho, mà lại không nhìn thấy được từ bên ngoài.
2. **Log có hãm nhịp** (lần đầu + mỗi 1.000 lần), kèm **hai bộ đếm** `dropped` và
   `dropped_by_type()`. Log nói *vừa bỏ một cái*; bộ đếm nói *đã bỏ bao nhiêu* - chỉ cái sau dùng
   được để chỉnh trần.
3. **Bộ đếm hãm nhịp của cảnh báo "miễn trần" phải RIÊNG.** Bản nháp đầu dùng chung với `_dropped`,
   mà `0 % 1000 == 0`, nên nó kêu ở **mọi** lần publish khi chưa bỏ cái nào - đúng cái lũ log mà
   phép hãm nhịp sinh ra để chặn. Có test canh riêng cho lỗi này.
4. **Mặc định 10.000** chứ không phải "không trần": chọn "bỏ" là chọn cưỡng chế, mà một chốt chặn
   chỉ tồn tại khi ai đó gõ tay thì phần lớn sẽ không tồn tại. Ai muốn hành vi cũ thì khai
   `max_pending=None` - vẫn làm được, nhưng phải tự tay viết ra.

### Nợ luật 03 - khai ra, cố ý chưa trả

Bên gọi **không phân biệt được** event bị bỏ với event đã xếp lịch: cả hai trả `None`. Đúng
[luật 03](../../../.claude/rules/03-mot-gia-tri-mot-nghia.md), và đóng nó là **đổi chữ ký công
khai** - thứ 0.7.x không được làm. Để lại cho **0.8**, đã ghi trong docstring `publish()` và trong
`docs/{vn,en}/core-concepts.md`.

Hệ quả thực dụng đã viết vào tài liệu: **đừng dùng event bus cho thứ mà mất là phải phát hiện
được** - hoặc khai vào `never_drop`, hoặc đừng đi qua bus.

### Test

**16 test**, đi thành **cặp** ở mọi chỗ:

| Phải bỏ | Phải KHÔNG bỏ |
|---|---|
| quá trần | dưới trần · loại trong `never_drop` · `max_pending=None` |
| loại không được miễn | (lớp con của loại được miễn thì **vẫn bỏ** - khớp kiểu chính xác) |
| cảnh báo "miễn trần" khi vượt trần | cảnh báo đó **im** khi còn dưới trần |

**Đối chứng**: gỡ phép kiểm trần thì **8 đỏ / 8 xanh**, và 8 cái xanh đúng là nhóm "phải không bỏ"
cộng nhóm test cấu hình. Đó là bằng chứng cặp test canh hai chiều khác nhau chứ không canh cùng một
thứ.

### Một thứ phát hiện khi đo, KHÔNG thuộc F15 và chưa làm

`drain()` tồn tại và docstring bảo dùng nó trong shutdown hook, nhưng **framework không bao giờ tự
gọi** (grep toàn `xime/`). Tắt app là cắt ngang mọi handler đang chạy, không có gì báo. Đã ghi vào
`docs/{vn,en}/core-concepts.md` để người dùng tự gọi trong `PreDestroy`; sửa cho tử tế thì thuộc
0.8, vì nó chạm vòng đời adapter.

**Không app nào phải sửa**: quét toàn workspace, **không repo nào dùng `EventBus`**. Đo:
**1593 passed** (+16).

## ⚪ F16 - `save_upload` không giới hạn dung lượng mặc định

`max_bytes: int | None = None` (`_upload.py:20`). Không truyền thì upload bao nhiêu cũng nhận -
đầy đĩa hoặc đầy hóa đơn S3. Kiểm tra lại chỉ chạy **sau** khi đã đọc xong một chunk, nên còn
vượt tối đa 1 MiB (chấp nhận được).

**Đề xuất:** đặt mặc định hữu hạn (ví dụ 32 MiB), muốn không giới hạn thì truyền `max_bytes=None`
tường minh.

## ⚪ F17 - MQTT RPC trả lời về topic do client chỉ định

`xime/adapters/mqtt/_dispatcher.py:122-136` - `response_topic` lấy từ
`properties.ResponseTopic` của người gọi rồi publish thẳng vào đó. Đúng chuẩn MQTT v5, nhưng
server publish bằng **credential của server**, nên client mượn được quyền publish của server tới
topic mà chính nó không được phép (confused deputy).

**Đề xuất:** cho phép khai một allowlist tiền tố topic cho reply (`mqtt.rpc.reply_prefix`), mặc
định giữ nguyên hành vi.

### ✅ ĐÃ VÁ 2026-08-18 (0.7.2) - chủ dự án chốt **cảnh báo, không chặn**

Ba phương án đưa lên: mặc định bắt buộc khai (nổ lúc khởi động) · mặc định tắt hẳn · **mặc định
cho qua nhưng có cảnh báo**. Chủ dự án chọn phương án thứ ba.

**Khoá cấu hình `mqtt.rpc.reply_topics`** (⚠ **không phải `reply_prefix` như đề xuất gốc**):

```yaml
mqtt:
  rpc:
    reply_topics: [nhamay/reply/#, devices/+/reply]
```

Đổi tên vì đổi ngữ nghĩa: chúng là **topic filter MQTT** dùng lại `topic_matches` sẵn có, không
phải tiền tố chuỗi. Lý do chọn filter: adapter này vốn đã bắt người dùng nghĩ bằng filter ở
`@subscribe`, nên thêm một hệ so khớp thứ hai trong cùng một adapter là tự tạo bẫy. Và **một cái
tên nói sai về thứ nó làm thì tệ hơn một cái tên dài hơn** - `prefix` mà thật ra là filter sẽ khiến
người ta khai `nhamay/reply/` rồi tưởng là xong, trong khi nó khớp **không gì cả**.

| Cấu hình | Hành vi |
|---|---|
| Không khai | Y hệt trước. **Một** WARNING lúc khởi động, **chỉ khi** client có `@rpc` |
| Khai, reply khớp | Im lặng |
| Khai, reply không khớp | **Vẫn gửi**, kèm WARNING nêu tên topic |

**Bốn quyết định hiện thực đáng ghi:**

1. **Kiểm TRƯỚC khi gọi handler**, không phải trước lúc publish. Đặt sau thì ca handler ném lỗi -
   đúng ca đáng nhìn nhất - lại là ca không có dòng log nào. Có test riêng cho việc này.
2. **Khử trùng lặp + chặn trần 64 topic khác nhau.** Không có nó thì bên gọi biến một cảnh báo
   thành lũ log chỉ bằng cách đổi topic mỗi lần - cùng họ với F15, và nó sẽ nuốt mất chính dòng
   cảnh báo mà ta vừa dựng lên.
3. **Filter sai cú pháp thì nổ lúc khởi động.** Filter không bao giờ khớp sẽ biến **mọi** reply
   thành cảnh báo, tức phép dò kêu oan, tức phép dò sẽ bị tắt.
4. **Cảnh báo khởi động chỉ kêu khi client thực sự có `@rpc`.** Client chỉ pub/sub không bao giờ
   publish vào topic do bên gọi đặt, nên kêu ở đó là kêu sai chỗ.

**Test đi thành cặp ở cả hai tầng**, vì bản hiện thực *"luôn kêu"* cũng qua được nếu chỉ kiểm vế
kêu - mà bản đó còn tệ hơn không có gì, nó dạy người ta bỏ qua log:

| Tầng | Phải kêu | Phải IM |
|---|---|---|
| Dispatcher | reply ngoài danh sách | reply trong danh sách · **chưa khai danh sách nào** |
| Adapter | có `@rpc` mà chưa khai | đã khai · **client chỉ có `@subscribe`** |

**Đối chứng đã chạy**: gỡ lời gọi `_check_reply_topic` thì **4 test đỏ** (đúng nhóm "phải kêu"),
còn nhóm "phải im" vẫn xanh - đó chính là bằng chứng cặp test đang canh hai chiều khác nhau. Gỡ
điều kiện `cfg.rpc.reply_topics` ở cảnh báo khởi động thì **1 test đỏ**.

⚠ **Đây là phòng thủ chiều sâu, không thay thế ACL broker** - đã ghi rõ trong `docs/{vn,en}/mqtt.md`.

**Không app nào phải sửa**: quét lại toàn workspace, không repo nào import `xime.adapters.mqtt`,
không repo nào có `@rpc`, không `application.yml` nào có khối `mqtt`. Đo: **1577 passed** (+14).

---

# ĐÃ KIỂM VÀ ĐẠT - đừng làm lại

| Miền | Kết luận |
|---|---|
| Rò ngữ cảnh giữa request | `_RequestContext.set/delete` **tạo dict mới mỗi lần** (`request_context.py:31-35`) nên task con không dùng chung dict với cha. Middleware là pure-ASGI ở cả hai lớp, `clear()` nằm trong `finally`. Sạch. |
| Alg confusion JWT | `algorithms=[key_context.algorithm]` - thuật toán lấy từ **cấu hình**, không lấy từ token. Không có cửa `none`, không có cửa HS/RS. |
| Chèn mã | Không có `eval`, `exec`, `pickle`, `marshal`, `yaml.load`, `shell=True`, `os.system` ở đâu trong 190 file. YAML nạp bằng `safe_load`. `importlib` chỉ nhận tên package do lập trình viên khai. |
| Crypto / ngẫu nhiên | Không dùng `random` cho mục đích bí mật; không `md5`/`sha1` cho bảo mật; không `verify=False`. `uuid4` chỉ dùng cho request_id (không phải token). |
| Path traversal localfs | Phòng tuyến `.resolve()` + kiểm `parents` **chặn thật** (PoC 7), kể cả `..\` và đường dẫn tuyệt đối Windows. |
| Lách `public_paths` | Thử `/admin/users/`, `/./admin/users`, `//admin/users`, `/admin%2fusers`, `/ADMIN/USERS` - **tất cả 401** (PoC 5). So khớp bằng tập hợp chính xác chứ không bằng tiền tố, đây là lựa chọn đúng. |
| `XIME_ENV` traversal | **Không** đọc được file ngoài `resources/` (PoC 10). |
| Rò chi tiết lỗi gRPC | `_safe_details()` che `str(exc)` cho exception chưa map. Đúng. (Còn metadata - xem F12.) |
| Frame socket | Giới hạn payload 64 MiB (`_protocol.py:36`), quyền socket mặc định `0600`, có whitelist UID. |
| Bí mật trong lịch sử git framework | 46 commit, không có secret thật nào. `pypi_token.py` gitignore. |
| bandit / semgrep | bandit: 18 cảnh báo, **không cái nào là lỗ hổng thật** (B101 assert trong code phòng thủ, B104 bind 0.0.0.0 là chủ đích, B105 là tên hằng). semgrep `p/security-audit`: 1 kết quả, dương tính giả. Đúng như dự đoán ở mục 7 của kế hoạch - công cụ chỉ chỗ, không kết luận. |

---

# ĐỀ XUẤT THỨ TỰ VÁ

Xếp theo **hậu quả chia cho công sức**, không theo mức nghiêm trọng thuần.

| # | Việc | Vì sao đứng đây | Công sức |
|---|---|---|---|
| 1 | **A3** - đổi `jwt.secret` của `shop`, vô hiệu token đang sống | Secret đang nằm trong git của một app **đã deploy**. Mỗi giờ trôi qua là một giờ rủi ro | 1 giờ |
| 2 | **A1** - đảo fail-open thành fail-closed ở `config/jwt.py` | 21 codebase, và đường deploy tự nhiên rơi trúng nhánh hỏng | nửa ngày (sửa template + 20 bản sao) |
| 3 | **A2** - bỏ `allow_origin_regex` khỏi `application.yml` gốc | 23 codebase, sửa bằng cách xóa một dòng | 2 giờ |
| 4 | **F3** - nâng sàn dependency + thêm `pip-audit` vào quy trình phát hành | Gói công khai, ảnh hưởng người ngoài | 1 giờ |
| 5 | **F2** - nosniff + không tin Content-Type + ép attachment | Lỗ hổng thật, sửa gọn trong 2 file | 2 giờ |
| 6 | **F8** - Content-Disposition theo RFC 6266 | Đang làm hỏng tính năng thật với tên file tiếng Việt | 1 giờ |
| 7 | **F4** - `configure_cors` ép kiểu + sửa chú thích sai | Chặn được lần tái phát của A2 | 1 giờ |
| 8 | **F6** + **F7** - log WARNING cho mọi chế độ không an toàn và profile thiếu | Rẻ, và nó làm mọi lỗi cấu hình về sau tự lộ ra | 2 giờ |
| 9 | **F5** - che secret trong `__repr__` | Mìn chưa nổ, vá trước khi ai đó log config | 1 giờ |
| 10 | **A4**, **A6**, **F9**, **F11**, **F12** | Phòng thủ chiều sâu và dọn mâu thuẫn tài liệu | 1 ngày |
| 11 | **F1** - đường xác thực cho WebSocket | Chưa app nào dùng WS. Phải xong **trước** khi làm `xime chat` | nửa ngày |
| 12 | **F10** - cô lập adapter | Cần chủ dự án quyết đánh đổi trước khi code | chờ quyết |
| 13 | Phần còn lại (F13-F17, A5, A7) | Không có đường khai thác rõ ràng | tùy lúc rảnh |

---

# PHƯƠNG PHÁP & BẰNG CHỨNG

**Đã đọc từng dòng:** `starters/jwt` (7 file), `core/security` (7), `core/context` (2),
`core/config` (3), `adapters/web` (phần adapter, cors, files, ws, middleware),
`starters/storage` + `localfs` + `s3`, `adapters/grpc` (tls, interceptors, adapter),
`adapters/socket` (peercred, config, protocol), `adapters/mqtt` (dispatcher, config),
`core/event`, `core/bootstrap`.

**Đã quét mẫu:** toàn bộ 31 codebase ứng dụng (~7.400 file Python) bằng ripgrep theo bộ mẫu ở
mục 5 của kế hoạch. Đọc kỹ: `trung-tam-day-hoc` (khuôn của 20 app), `Monolithic/shop` (kiến trúc
đa lớp), `linh-kien-dien-tu` (repository/org_id).

**12 PoC đã chạy thật**, lưu lại trong repo ở
[`.claude/scripts/bao-mat/`](../scripts/bao-mat/README.md) (có README riêng, chạy được ngay,
không cần service nào đang chạy): `poc_web.py` (PoC 1-5), `poc_web2.py` (6-8), `poc_config.py`
(9-11), `poc_cors_real.py` (12).
**Ba PoC cho kết quả ÂM TÍNH và đã làm giảm mức của phát hiện** - ghi lại để không ai kết luận
quá tay lần sau: CRLF **không** tách được response qua uvicorn thật (F8); `..\` **không** thoát
được storage root (F14); `XIME_ENV` **không** đọc được file ngoài `resources/` (không thành phát
hiện).

**Công cụ:** bandit 1.9.4 + semgrep 1.172.0 + pip-audit, cài trong venv riêng ở thư mục tạm,
không đụng Python hệ thống và không đụng dependency của project nào. Trong 24 phát hiện,
**đúng 1 cái** (F3) đến từ công cụ; 23 cái còn lại đến từ đọc code.

**Phạm vi KHÔNG kiểm** (nhắc lại từ mục 9): service Java (Trust, identity, user, payment,
application, agent, organization), frontend Next.js, hạ tầng, và kiểm thử xâm nhập trên hệ thống
đang chạy. Hai chỗ mà kết luận của đợt này **phụ thuộc vào phần Java chưa kiểm**: F9 (chính sách
cấp SAN của Trust) và A2 (thuộc tính `SameSite` của cookie refresh do identity-service đặt).
