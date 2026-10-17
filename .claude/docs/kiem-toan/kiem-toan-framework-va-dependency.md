# Kiểm toán một lượt Xime Framework — 17/10/2026

> **Trạng thái:** Bước 0–6 đã hoàn tất trên Windows ngày 2026-10-17: sáu lỗi
> đã vá, 16 advisory có kết luận, mypy/API đã xử lý; nghiệm thu tổng 2.881 passed.
> Commit **e5a5b5c**; Bước 7 Windows đã kiểm thêm resolver/consumer/artifact;
> [nghiệm thu Windows](nghiem-thu-windows-framework.md). Linux dừng theo yêu cầu.
> Hậu kiểm phát hiện [F7 thiếu crypto trong extra JWT](jwt-extra-thieu-crypto.md)
> và bổ sung che credential trong lỗi YAML của F4; đã vá và full suite cuối
> 2.884 passed trên mỗi bộ; [đối chiếu yêu cầu](doi-chieu-nghiem-thu-ke-hoach.md).
> **Thuộc bản:** baseline `2ad5274`, metadata `0.8.3`; bản vá chưa chọn số phiên bản.
> **Thay:** lưu bền báo cáo `bao-cao-kiem-toan.md` của lượt kiểm toán cùng ngày;
> bổ sung bốn phát hiện mới ngoài hai mục TLS/config đã có.
> **Bị thay bởi:** chưa có; tiến độ theo
> [kế hoạch đã duyệt](../sap-toi/ke-hoach-va-loi-kiem-toan-framework.md).

Phần đầu đến hết “Giới hạn và lệnh tái hiện” là **snapshot trước bản vá**:
lượt kiểm toán đó chỉ đọc mã/tài liệu và chạy phép đo, không sửa source/test/
dependency/index hoặc dịch vụ consumer. Log gốc ở
`%TEMP%\xime-framework-audit-20261017\`; kết quả sau khi được duyệt triển khai
ghi riêng tại **“Nghiệm thu nhóm 1”** phía cuối. Không dùng snapshot để suy ra
trạng thái worktree sau bản vá.

## Hiện trạng và cách làm

- Checkout: `D:\code\xime\xime framework`, nhánh `main`, HEAD `2ad5274`.
- `pyproject.toml` và metadata editable: `0.8.3`. Không dùng số metadata để
  suy ra nội dung source hay trạng thái PyPI hiện tại; lượt này không kiểm phát hành.
- Máy đo: Windows, Python 3.14.8, OpenSSL 3.5.9, Uvicorn 0.47.0,
  FastAPI 0.135.1, Starlette 1.6.0, PyJWT 2.13.0, AnyIO 4.12.1.
- Đã đọc hướng dẫn repo/cha, chỉ mục và ghi chú Claude, bộ nhớ Codex về lượt
  15/10, backlog, thiết kế liên quan, quy tắc code/transaction và công cụ kiểm toán.
- Theo phương pháp cũ: kiểm hiện trạng bằng lệnh; chạy hồi quy; tìm test bằng
  nội dung symbol; tái hiện nghi vấn kèm đối chứng; ghi rõ giới hạn bằng chứng.
- Có sẵn 11 đường dẫn tài liệu đang staged từ trước. Trạng thái cuối giữ nguyên.

## Các phát hiện

### F1 — P2: JWT với khóa tĩnh có thể trả 500 cho header JSON lồng sâu

Vị trí: `xime/starters/jwt/_verifier.py:122,145`,
`xime/starters/jwt/_authenticator.py:110-113`,
`xime/starters/jwt/_middleware.py:122-126`, `pyproject.toml:178`.

PyJWT 2.13.0 có advisory `PYSEC-2026-4142` / `GHSA-8wjv-2p76-3863`:
header được phân tích trước kiểm chữ ký, và JSON lồng quá sâu ném `RecursionError`
thay vì exception JWT. Verifier của Xime chỉ chuyển `InvalidTokenError` thành
`AuthenticationException`; nhánh khóa tĩnh không đi qua `read_kid()` có bắt lỗi.

Đã đo trên API có `JwtAuthMiddleware`, Uvicorn 0.47.0/httptools, listener loopback:

| Đầu vào | Khóa tĩnh | Key provider |
|---|---:|---:|
| Token hợp lệ | 200 | 200 |
| Chữ ký sai bình thường | 401 | 401 |
| Header JSON lồng 70.000 tầng, token 186.721 byte | 500 | 401 |

Đối chứng key provider đo bằng ASGITransport. Nhánh khóa tĩnh cũng đã đo qua
listener TCP thật: httptools trả 500; h11 chặn yêu cầu lớn và trả 400 trước khi
tới xác thực. Token hợp lệ tiếp theo vẫn trả 200 ở cả hai protocol.

Giới hạn: đây là lỗi xử lý đầu vào và khả dụng; chưa thấy bypass chữ ký hoặc
worker chết. Trên Python 3.14.8, header khoảng 3.788 byte/1.400 tầng vẫn trả 401;
không suy từ giới hạn recursion của Python sang độ sâu JSON gây lỗi.

Hướng xử lý: nâng/kiểm chứng sàn PyJWT và bảo đảm verifier chuyển lỗi phân tích
đầu vào không tin cậy thành lỗi xác thực. Không nuốt mọi exception lập trình
một cách vô điều kiện. Bổ sung test khóa tĩnh và key provider, qua HTTP thật.

Nguồn chính chủ:
https://github.com/jpadilla/pyjwt/security/advisories/GHSA-8wjv-2p76-3863

Bằng chứng: `edges.log`, `jwt-live.log`; tái hiện bằng `audit_edges.py`, `jwt_live.py`.

### F2 — P2: Tải tiếp file bỏ qua If-Range, có thể trộn hai phiên bản

Vị trí: `xime/adapters/web/files/_download.py:169-174,186-193`.

`stream_object()` có ETag và hỗ trợ Range nhưng không đọc `If-Range`.
Đã tái hiện bằng FastAPI + LocalFileStorage thật:

1. Object ban đầu là `0123456789`; lưu ETag và 5 byte đầu `01234`.
2. Khi ETag còn khớp, `Range: bytes=5-` + `If-Range: <etag cũ>` trả
   206 với `56789` — đối chứng đúng.
3. Ghi đè cùng key bằng `ABCDEFGHIJ`; ETag thực sự đổi.
4. Gửi lại yêu cầu tải tiếp với ETag cũ: vẫn nhận 206 và `FGHIJ`.
5. Client ghép phần đã có thành `01234FGHIJ`, không bằng phiên bản cũ hay mới.

RFC 9110 mục 13.1.5 yêu cầu bỏ qua Range nếu If-Range không khớp và trả toàn bộ
biểu diễn mới. Hướng xử lý: đánh giá validator trước khi áp dụng Range;
ETag không khớp phải về phản hồi full 200. Cần giữ đối chứng ETag khớp -> 206.

Nguồn: https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.5

Bằng chứng: các dòng `if_range` trong `edges.log`.

### F3 — P2: Lỗi/cancellation lúc đóng SQLAlchemy session bỏ qua khôi phục ContextVar

Vị trí: `xime/starters/sqlalchemy/transaction.py:50-52` và
`xime/starters/sqlalchemy/readonly.py:75-79`.

Cả hai context manager đều `await session.close()` trước khi reset token.
Nếu close ném lỗi hoặc bị hủy, phần reset không chạy. Sau khi bên gọi bắt lỗi
và tiếp tục trong cùng async context, `AsyncSessionFactory.current()` vẫn trả
session của khối đã thoát; read-only tiếp theo có thể mượn session đó.

Đã chạy fault injection cho cả hai manager:

| close() | ContextVar được khôi phục |
|---|---|
| Thành công | Có |
| RuntimeError | Không |
| CancelledError | Không |

Giới hạn: fault injection bằng AsyncMock, không phải bằng chứng một database
đang vận hành đã gặp sự cố. Không suy ra rò session giữa các request độc lập.

Hướng xử lý: bảo đảm reset token nằm trong finally riêng, luôn chạy dù thao tác
đóng session thất bại; giữ exception gốc và semantics cancellation phù hợp.

Bằng chứng: các dòng `session_cleanup` trong `edges.log`.

### F4 — P2, đã có trong backlog: Checker bỏ sót khóa gõ sai trong environments

Vị trí: `xime/cli/_config_check.py:144-158`, `xime/core/config/loader.py:134-159`.

Đã tái hiện lại: `environments.server.websever.ssl` cho verdict `clean`;
cấu hình hiệu lực có `websever`, không có `webserver`. Checker kiểm hình dạng
overlay nhưng không đi vào schema framework của nhánh được chọn.

Hệ quả HTTP thuần thay vì HTTPS đã được kiểm chứng qua listener trong lượt
15/10 trên cùng HEAD; lượt này tái kiểm checker/loader, không lặp lại toàn bộ
ma trận startup đó. Cần typo và không có TLS chung hợp lệ để kế thừa.
Client HTTPS không tự chuyển sang HTTP. Không kết luận mọi consumer đang lỗi.

Hướng xử lý: kiểm schema framework trong nhánh/effective config, tiếp tục cho
phép các khối riêng của ứng dụng. Chi tiết cũ ở backlog và báo cáo TLS/config.

### F5 — P2, đã có trong backlog: Mặc định cipher Uvicorn 0.47.0 kém tương thích TLS 1.2

Vị trí: `pyproject.toml:128`, `xime/adapters/web/_adapter.py` phần TLS kwargs.

Máy hiện tại vẫn dùng 0.47.0. Đã tính lại: server default `TLSv1` có tập cipher
TLS <=1.2 giao với client Python mặc định là rỗng. TLS 1.3 không thuộc giao này.
Lượt 15/10 trên cùng HEAD đã đo handshake thất bại ở TLS 1.2 mặc định, hoạt động
với cipher tường minh, và kiểm Uvicorn 0.48.0 trong môi trường riêng.

Giới hạn: lượt này xác minh cấu hình/tập cipher; không lặp lại toàn bộ ma trận
Uvicorn 0.47/0.48 và không đo VPS. Không phải mọi client TLS 1.2 đều bị ảnh hưởng.

Hướng xử lý: chọn sàn/default đã đo trên các OpenSSL/client được hỗ trợ.

### F6 — P3: Suffix Range của object rỗng tạo Content-Range không hợp lệ

Vị trí: `xime/adapters/web/files/_download.py:98-99,187-190`.

Object 0 byte + `Range: bytes=-1` trả HTTP 206,
`Content-Range: bytes 0--1/0`. Cùng object + `bytes=0-` trả 416,
`Content-Range: bytes */0`. Suffix range trên object không rỗng trả đúng dữ liệu.

Hướng xử lý: xử lý tổng độ dài 0 trước khi dựng range, tránh khoảng byte kết thúc
âm; trả một phản hồi hợp lệ. Đây là lỗi ca biên, không phải bằng chứng mất dữ liệu.

Bằng chứng: các dòng `download_range` trong `edges.log`.

## Advisory dependency: 16 mục chưa có quyết định xử lý

`check_dep_advisories.py` chạy trực tuyến hoàn tất với exit 1:

- 14 advisory PyJWT ở sàn 2.13; máy hiện tại cũng là PyJWT 2.13.0.
- 2 advisory AnyIO ở sàn 4.0; AnyIO 4.12.1 đang cài cũng thuộc dải affected.
- Advisory APScheduler `PYSEC-2026-282` vẫn là mục đã chấp nhận từ trước.
- Đã tải JSON gốc OSV cho 16 mục, không có mục bị withdrawn.
- `PYSEC-2026-4146` chưa có fixed event trong dữ liệu OSV; không được tuyên bố
  chỉ nâng lên 2.15.0 là đóng được toàn bộ 16 mục.

Đây là 16 advisory theo phiên bản, không phải 16 lỗ hổng đều đi tới được qua
Xime. F1 là đường ảnh hưởng trực tiếp đã tái hiện. Nhiều mục còn lại yêu cầu
PyJWKClient, trộn symmetric/asymmetric algorithm, JWK không tin cậy, tái dùng
options của chế độ bỏ kiểm chữ ký, token revocation theo chuỗi thô, AnyIO process
pool hoặc hostname quốc tế. Chưa chứng minh framework hiện tại đi vào các đường đó.
Verifier Xime ghim algorithm theo KeyContext và tạo options mới cho mỗi lần verify.

Tham chiếu AnyIO chính chủ:
https://github.com/agronholm/anyio/security/advisories/GHSA-82r6-8w77-94w6
https://github.com/agronholm/anyio/security/advisories/GHSA-5p39-cfhj-2xmp

Bằng chứng: `dependency-floor-live.log`, `advisories.json`.
Lượt đầu trong sandbox bị chặn mạng, exit 2; đó không phải kết quả sạch.
Kết luận ở trên dựa trên lượt tra cứu trực tuyến hoàn tất sau đó.

## Kết quả kiểm tra và đối chứng không phát hiện lỗi

| Phép kiểm | Kết quả |
|---|---|
| Hồi quy tests_temp | 2.803 passed, 25 skipped, 1 deselected, 19 warnings; 284,42 giây |
| Test bị deselect chạy riêng | 1 passed, 0,02 giây |
| Ruff xime, không cache | Đạt |
| pip check | Đạt; chỉ chứng minh dependency thỏa khai báo |
| mypy xime | 49 lỗi / 28 file, trên 249 file được kiểm |
| check_doc_imports docs | 366 tên import / 46 file, đạt |
| check_doc_code | 426 block Python, đạt |
| check_doc_register | 0 lỗi; 2 class ví dụ A/B không có import nên công cụ bỏ qua |
| check_doc_coverage | 148/317 tên không xuất hiện trong 23 trang docs/en; exit 1 |
| git diff --check, cached --check | Đạt |

Mypy bằng số lượng lỗi ghi trong mốc cũ; không dùng việc bằng số lượng để khẳng định
từng lỗi là giống nhau. Coverage chỉ đo xuất hiện tên trong docs/en, gồm cả nhiều
symbol hạ tầng; không kết luận 148 tính năng thiếu hoàn toàn tài liệu.
`find_reexport_gap.py` có output các import nội bộ; exit 0 không phải chứng minh
mọi tên đó phải trở thành public API, nên không nâng thành phát hiện.

Phép thử thêm về TLS: xoay trust bundle mTLS từ CA A sang CA B đã hoạt động
đúng trên TLS 1.2 và 1.3, đủ 12 đối chứng trước/sau: client A được nhận trước và
bị từ chối sau; client B ngược lại; không có client cert luôn bị từ chối.
Không ghi vấn đề CA reload từ nghi vấn chưa đúng này.

## Giới hạn và lệnh tái hiện

- Chưa chạy Linux/uvloop, Certbot, VPS hay consumer nghiệp vụ đang triển khai.
- 25 skip gồm POSIX-only, MQTT broker không có, S3/MinIO không có và ca quyền file
  riêng hệ điều hành. Không tự bật dịch vụ để biến skip thành pass.
- Một test `_alive(os.getpid())` đã deselect khỏi run gộp theo lịch sử Windows;
  test đó và lời gọi trực tiếp đều đạt khi chạy riêng trong lượt này.
- Không load-test denial of service; F1 chỉ kiểm một yêu cầu xấu kèm đối chứng.
- Không sửa file trong repo. Bằng chứng tạm có thể bị hệ điều hành dọn;
  chưa chép các phát hiện mới vào backlog của repo.

Chạy từ repo (đổi đường dẫn TEMP nếu máy khác):

```powershell
python -m pytest tests_temp -q -rs --deselect=tests_temp/link/test_cleanup.py::TestAlive::test_this_process_is_alive --basetemp "$env:TEMP\xime-framework-audit-20261017\pytest-replay"
python -m pytest tests_temp/link/test_cleanup.py::TestAlive::test_this_process_is_alive -q
python -m ruff check xime --no-cache
python -m pip check
python -m mypy xime
python .claude/scripts/check_doc_imports.py docs
python .claude/scripts/check_doc_code.py
python .claude/scripts/check_dep_advisories.py
python "$env:TEMP\xime-framework-audit-20261017\audit_edges.py"
python "$env:TEMP\xime-framework-audit-20261017\jwt_live.py"
```

Ưu tiên xử lý đề nghị: F1 và triage dependency, F2, F3, hai mục TLS/config cũ,
sau đó F6. Mỗi bản vá cần đối chứng riêng; chưa có bản vá nào trong lượt kiểm toán này.

## Nghiệm thu nhóm 1 — JWT và dependency (2026-10-17)

Chủ dự án đã duyệt kế hoạch và yêu cầu bắt đầu triển khai. Nhóm này bao gồm
Bước 0 và Bước 1; chưa triển khai F2–F6 hoặc nợ mypy/tài liệu API.

### Hành vi và phạm vi thay đổi

- `_verifier.py` chuyển riêng `RecursionError` do decoder thành
  `AuthenticationException`, giữ `__cause__`. Expired token giữ phân loại cũ;
  RuntimeError/ValueError/TypeError không bị chuyển thành lỗi xác thực.
  Không cần đổi authenticator, middleware hoặc public_paths.
- `pyproject.toml`: PyJWT >=2.15.0 ở extra jwt; AnyIO >=4.14.2 trong dependencies
  runtime; bỏ ràng buộc AnyIO trùng trong dev. Không đổi Uvicorn trong nhóm này.
- `tests_temp/jwt/test_untrusted_input.py`: 12 ca cho JSON lồng sâu thật,
  khóa tĩnh/provider, ASGI và listener httptools/h11, yêu cầu hợp lệ trước/sau,
  exception được giữ đúng loại và options được tạo mới mỗi lượt verify.
- `CHANGELOG.md` có phần Unreleased; backlog và kế hoạch ghi đúng tiến độ.
  Không thêm ngoại lệ vào `check_dep_advisories.py`.

### Triage 16 advisory của baseline

Tra dữ liệu OSV và nguồn chính chủ ngày 2026-10-17. Cột đường gọi mô tả code
framework hiện tại, **không** kết luận về mọi đoạn code riêng của consumer.
Các hàng có fixed event đều đã được loại khỏi dải affected bằng sàn mới;
riêng 4146 cần đối chứng hành vi vì dữ liệu không ghi fixed event.

| Advisory | Điều kiện và đường gọi Xime | Mốc xử lý / kết luận |
|---|---|---|
| [PYSEC-2026-4024](https://osv.dev/vulnerability/PYSEC-2026-4024) | AnyIO process-pool bị kẹt stderr; không có lời gọi `to_process` trong Xime | Fixed 4.14.2; nâng sàn runtime; chưa tái hiện process-pool riêng |
| [PYSEC-2026-4025](https://osv.dev/vulnerability/PYSEC-2026-4025) | TLSStream dùng IDNA cho hostname quốc tế; ảnh hưởng tùy outbound client và hostname ứng dụng | Fixed 4.14.2; nâng sàn runtime; không coi test JWT là test khai thác IDNA |
| [PYSEC-2026-4140](https://osv.dev/vulnerability/PYSEC-2026-4140) | Unknown kid kích JWKS fetch; Xime không dùng PyJWKClient, provider do ứng dụng cấp | Fixed 2.14.0; sàn 2.15.0 nằm ngoài dải affected |
| [PYSEC-2026-4141](https://osv.dev/vulnerability/PYSEC-2026-4141) | Payload lồng sâu qua PyJWKClient hoặc bỏ kiểm chữ ký; verifier Xime không dùng hai đường này | Fixed 2.15.0; không đồng nhất mục này với header F1 |
| [PYSEC-2026-4142](https://osv.dev/vulnerability/PYSEC-2026-4142) | Header JSON lồng sâu trước kiểm chữ ký; **đã tái hiện F1** ở khóa tĩnh | Fixed 2.14.0; sàn 2.15.0 và lớp chuyển exception trong Xime; test thật đạt |
| [PYSEC-2026-4143](https://osv.dev/vulnerability/PYSEC-2026-4143) | HMAC JWK rỗng; Xime dùng secret từ KeyContext, chặn giá trị rỗng trước decode | Fixed 2.14.0; sàn 2.15.0; không có lời gọi PyJWK của framework |
| [PYSEC-2026-4144](https://osv.dev/vulnerability/PYSEC-2026-4144) | JWKS redirect; framework không có PyJWKClient | Fixed 2.14.0; sàn 2.15.0 |
| [PYSEC-2026-4145](https://osv.dev/vulnerability/PYSEC-2026-4145) | PEM biến thể làm lẫn HMAC/asymmetric; verifier ghim algorithm theo từng KeyContext | Fixed 2.14.0; sàn 2.15.0; cấu hình khóa của app vẫn phải đúng |
| [PYSEC-2026-4146](https://osv.dev/vulnerability/PYSEC-2026-4146) | Options bị mutate rồi tái dùng; Xime tạo dict mới và sao chép require mỗi lần | Không có fixed event, last_affected=2.13.0; đối chứng trực tiếp 2.15.0 không còn tái hiện; test chống tái dùng đạt |
| [PYSEC-2026-4147](https://osv.dev/vulnerability/PYSEC-2026-4147) | Signature segment không canonical khi revoke theo chuỗi token thô; Xime không cung cấp kho revoke đó | Fixed 2.14.0; sàn 2.15.0; không xác nhận thiết kế revoke riêng của consumer |
| [PYSEC-2026-4148](https://osv.dev/vulnerability/PYSEC-2026-4148) | ReDoS khi nhận diện PEM; key của verifier lấy từ cấu hình/provider, không đọc PEM từ token | Fixed 2.14.0; sàn 2.15.0; provider vẫn là ranh giới tin cậy của app |
| [PYSEC-2026-4149](https://osv.dev/vulnerability/PYSEC-2026-4149) | DER public key bị dùng làm HMAC secret; Xime ghim algorithm theo KeyContext | Fixed 2.14.0; sàn 2.15.0; không suy rằng mọi cấu hình secret sai đều được Xime phát hiện |
| [PYSEC-2026-4150](https://osv.dev/vulnerability/PYSEC-2026-4150) | BOM vượt kiểm PEM/HMAC; cùng ranh giới KeyContext và algorithm như trên | Fixed 2.14.0; sàn 2.15.0 |
| [PYSEC-2026-4151](https://osv.dev/vulnerability/PYSEC-2026-4151) | Public JWK container được dùng như HMAC secret; framework không import JWK, algorithm được ghim | Fixed 2.14.0; sàn 2.15.0 |
| [PYSEC-2026-4152](https://osv.dev/vulnerability/PYSEC-2026-4152) | RSA JWK hỏng làm lỗi toàn JWK Set; framework không gọi PyJWKSet | Fixed 2.14.0; sàn 2.15.0 |
| [PYSEC-2026-4183](https://osv.dev/vulnerability/PYSEC-2026-4183) | Private OKP JWK có x/d không khớp; Xime dùng PEM, không nhận private JWK từ proof header | Fixed 2.15.0; sàn 2.15.0 |

Đối chứng 4146: trên PyJWT 2.13.0, lời gọi trực tiếp bỏ kiểm chữ ký làm thay
options của bên gọi; tái dùng dict đó nhận token hết hạn/sai audience. Trên
2.15.0, dict không bị đổi và lần verify tiếp theo ném ExpiredSignatureError.
Đường Xime tạo options mới từ đầu ném TokenExpiredException trên cả hai bản.
Không tuyên bố một bản vá cụ thể chỉ từ cột Fix Versions trống.

APScheduler `PYSEC-2026-282` là **một advisory duy nhất**, bị công cụ in hai
dòng trùng ID. Đã kiểm lại `SchedulerRunner.post_construct()` gọi
`AsyncScheduler()` không tham số; mặc định MemoryDataStore/LocalEventBroker,
không đi qua serializer của kho ngoài. Giữ ngoại lệ đã có từ trước, không mở
thêm ACCEPTED. Consumer tự cấu hình datastore/serializer khác cần đánh giá riêng.

### Bằng chứng kiểm thử

| Phép kiểm | Kết quả thực đo |
|---|---|
| 12 test mới trên source cũ, PyJWT 2.13.0 | **5 failed, 7 passed**; gồm HTTP 500 qua listener thật |
| 12 test mới sau vá, vẫn PyJWT 2.13.0 | **12 passed**; backstop hoạt động cả trước nâng dependency |
| JWT + WebSocket với PyJWT 2.15.0 / AnyIO 4.14.2 | **227 passed**, 19 cảnh báo độ dài khóa fixture cũ |
| Hồi quy tổng với cùng bộ dependency mục tiêu | **2.815 passed, 25 skipped, 1 deselected**, 19 warnings; 315,75 giây |
| Test `_alive(current_pid)` chạy riêng | **1 passed**, 0,05 giây |
| Ruff source và test mới; mypy riêng verifier | Đạt; không gọi mypy toàn repo đã đạt |
| Venv sạch: editable `[web,jwt]`, pip check, import và HS256 sign/verify | Đạt; metadata runtime có AnyIO >=4.14.2 |
| Audit bộ sàn khai báo | Exit 0 sau áp dụng ngoại lệ APScheduler cũ; không có 16 advisory mới |
| Audit 35 package dependency khai báo đang cài trong venv test | 0 vi phạm specifier nguồn; chỉ một advisory APScheduler (hai dòng); pip-audit thô exit 1 đúng vì mục này |
| Audit toàn bộ 22 package ngoài Xime trong venv sạch, gồm dependency bắc cầu | Không báo advisory, exit 0 |
| Import và cú pháp tài liệu | 366 tên/46 file và 426 block Python đều đạt |

Full run thu thập **2.841 ca**, tăng đúng 12 từ baseline 2.829. Skip/deselect
giữ nguyên lý do Windows/POSIX, MQTT/S3 chưa có tài nguyên test và test `_alive`
phải chạy riêng. Không có test bị bỏ để che hồi quy. Cảnh báo 19 ca là khóa HMAC
ngắn trong fixture có sẵn, không phải secret của ứng dụng.

Venv test có `system-site-packages` để dùng lại đủ optional adapter/test tools,
nhưng PyJWT/AnyIO được cài riêng và đã xác nhận module lấy từ venv đó. Venv cài
đặt sạch tách hẳn system packages, giữ các bản FastAPI 0.135.1, Starlette 1.6.0,
Pydantic 2.12.5, PyYAML 6.0.3, Uvicorn 0.47.0 để tách thay đổi của nhóm này;
dependency bắc cầu còn lại do resolver chọn. Chưa coi đây là nghiệm thu sàn
Uvicorn mới hoặc toàn bộ phiên bản sàn của mọi extra.

Log chi tiết ở `%TEMP%\xime-framework-fixes-20261017\`:
`jwt-red.log`, `jwt-green-old.log`, `jwt-ws-candidate.log`,
`full-candidate.log`, `full-candidate.xml`, `alive-candidate.log`, `options-baseline.log`,
`options-candidate.log`, `floor-advisories.log`, `candidate-advisories.json`,
`candidate-advisory-summary.log`, `clean-install-report.json`,
`clean-requirements.txt`, `clean-advisories.json`, `doc-imports.log`, `doc-code.log`.
Các kết luận và test hồi quy cần lưu bền đã nằm trong repo, không phụ thuộc
việc thư mục tạm còn tồn tại để biết nhóm này đã đo những gì.

Lệnh kiểm chính, chạy từ repo với venv đã chuẩn bị:

```powershell
$candidatePython = "$env:TEMP\xime-framework-fixes-20261017\venv-jwt\Scripts\python.exe"
& $candidatePython -m pytest tests_temp/jwt tests_temp/ws -q
& $candidatePython -m pytest tests_temp -q -rs --deselect=tests_temp/link/test_cleanup.py::TestAlive::test_this_process_is_alive
& $candidatePython -m pytest tests_temp/link/test_cleanup.py::TestAlive::test_this_process_is_alive -q
& $candidatePython -m mypy xime/starters/jwt/_verifier.py --follow-imports=silent
& $candidatePython .claude/scripts/check_dep_advisories.py
```

### Trạng thái bàn giao và giới hạn

F1 đóng trong worktree sau nghiệm thu; F2–F6 còn mở. Nợ 49 lỗi mypy/28 file
và phân loại tài liệu API vẫn theo Bước 6. Linux/Python 3.12/uvloop, consumer
nghiệp vụ, Certbot/ACME/VPS chưa được kiểm trong nhóm 1.

Giữ nguyên Git index của 11 file có sẵn. Chỉ README nội bộ và backlog có bổ
sung ở worktree để ghi kết quả nhóm này; phần staged cũ không bị thay thế.
Hai tài liệu mới `kiem-toan/kiem-toan-framework-va-dependency.md` và
`sap-toi/ke-hoach-va-loi-kiem-toan-framework.md` đang nằm dưới Git ignore của
`.claude`; khi chủ dự án commit cần chọn rõ cả hai file này. Tám đường dẫn của
nhóm bàn giao (tính từ gốc repo):

```text
xime/starters/jwt/_verifier.py
pyproject.toml
tests_temp/jwt/test_untrusted_input.py
CHANGELOG.md
.claude/docs/README.md
.claude/docs/kiem-toan/backlog-sua-loi.md
.claude/docs/kiem-toan/kiem-toan-framework-va-dependency.md
.claude/docs/sap-toi/ke-hoach-va-loi-kiem-toan-framework.md
```

Không commit/tag/push, nâng số phiên bản hay phát hành. Python chung vẫn giữ
PyJWT 2.13.0 / AnyIO 4.12.1 / Uvicorn 0.47.0; bản sửa khai báo chưa tự nâng chúng.
Framework đang editable nên source mới có thể được consumer nạp khi import
lại; không restart dịch vụ hoặc thay cấu hình consumer trong lượt này.

## Nghiệm thu Bước 2–6 (2026-10-17)

Chủ dự án chỉ thị làm liền đến hết Bước 6, `git add -A` sau mỗi nhóm và commit
khi xong Bước 6. Chỉ thị này thay nhịp chờ owner commit từng nhóm; không cho
phép tag/push/nâng phiên bản/phát hành, sửa repo consumer hoặc restart dịch vụ.

### Các bản vá runtime

| Bước / lỗi | Trước vá / đối chứng | Sau vá và nghiệm thu |
|---|---|---|
| 2 / F2, F6 | 10/16 test mới thất bại trên source cũ: stale If-Range, validator không xác nhận được, suffix file rỗng và malformed Range trên file rỗng | Xét strong ETag trước Range; không khớp/weak/date/không metadata thì full 200; file rỗng có Range hợp lệ trả 416; web_files/storage **95 passed, 6 skipped** |
| 3 / F3 | 14/15 ca fault injection thất bại trên source cũ | Reset ContextVar trong finally riêng kể cả begin/close lỗi; lỗi gốc được giữ kèm log/note cleanup, không nuốt cancellation/process-control; SQLAlchemy **43 passed** gồm SQLite thật |
| 4 / F4 | 23/25 test mới thất bại trên source cũ | Kiểm khóa overlay thô ở cả local/server; field bắt buộc và alias trên config đã merge; SSL của endpoint tên động được rà; config/SQLAlchemy **307 passed** |
| 5 / F5 | Uvicorn 0.47.0: đối chứng RSA cipher mặc định cho **1 failed (TLS 1.2), 1 passed (TLS 1.3)** | Sàn web >=0.48.0, dùng default OpenSSL; **110 passed, 1 skipped** trong nhóm TLS/management/health |

If-Range không thay hợp đồng StorageStat, không tải cả object vào RAM và không
cam kết snapshot nguyên tử khi có ghi đồng thời giữa stat/open_stream. Read-only
tiếp tục mượn session bao ngoài; không đóng nhầm session và vẫn detach trước rollback.
Checker không đọc schema nghiệp vụ của app và không cấm HTTP nói chung.

Một test checker cũ dùng `process.web.port` thiếu endpoint ID. Parser runtime
hiện tại yêu cầu `process.web.<id>.port`; đã sửa fixture thành `default` để giữ
đúng mục tiêu test “process là khối hợp lệ”, không hạ checker để nhận cấu trúc sai.

Ma trận TLS đã thêm: RSA/ECDSA × TLS 1.2/1.3 × cipher mặc định/tường minh;
startup và A→B→C; SNI/no-SNI; keep-alive còn dùng context cũ; cert/key sai giữ
context đang phục vụ; CA/hostname sai bị từ chối; watcher/backoff/deduplication.
mTLS dùng hai CA client thật, trước/sau đổi A→B nhận và từ chối đúng trên cả
hai protocol. Fixture đầu bị OpenSSL từ chối vì CA/leaf trùng subject; sửa
chứng thư test, không sửa framework theo lỗi fixture. Suite process rộng lúc
đầu có 274 passed/3 skipped và bốn lỗi fixture này; lần kiểm TLS cuối đã đạt.
ACK rỗng/hỏng/thiếu/partial/timeout và management primary được giữ qua suite có sẵn.

### Bước 6A — kiểm kiểu

Mypy **2.3.1**, cấu hình pyproject hiện tại, từ **49 lỗi / 28 file** xuống
**0 lỗi / 250 file**. Không đổi strictness, không bỏ module hay thêm type-ignore.
Kiểm tĩnh `--platform linux` ngay trên Windows cũng đạt 0 lỗi; **đây không phải
chạy Linux** và không đóng cổng Linux/Python 3.12/uvloop.

Thay đổi gồm annotation slot/generic, Protocol/binding union, metadata phản chiếu,
Message protobuf, Literal word order, tuple bốn vùng Modbus, kiểu tag FastAPI,
narrowing model MQTT và tham số stream socket. Metadata class sinh động được
đọc/ghi tường minh bằng getattr/setattr; không thêm thành viên vào Protocol
runtime chỉ để làm mypy xanh. Ba cast tại biên có căn cứ: registry DI keyed by
class, Redis provider cố định decode_responses=False, factory middleware ASGI.
API POSIX/Win32 có guard rõ nền tảng; không đưa socket Unix lên Windows.

Nhóm hồi quy các module liên quan: **898 passed, 6 skipped**, 83,16 giây.

### Bước 6B — tài liệu API

- Trước vá: EN thiếu 148/317, VN thiếu 152/317. Sau vá: **0/317 thiếu ở cả hai**.
- 152 lượt export thiếu ở ít nhất một ngôn ngữ (148 tên riêng) đã
  [phân loại từng mục](phan-loai-api-cong-khai.md): **94 API/kiểu cấu hình/kết quả,
  54 hạ tầng, 4 alias/re-export**. Không đổi __all__ để làm giảm counter.
- API reference EN/VN có vai trò, chữ ký hoặc ví dụ; hạ tầng có lý do và chủ
  sở hữu vòng đời cụ thể. Không quảng cáo scanner/builder/adapter như điểm mở rộng.
- Có `docs/README.md`, 24 trang mỗi ngôn ngữ, liên kết từ README gốc. Cập nhật
  Range, cleanup transaction, checker, dependency và nghĩa fingerprint/succeeded.
- **410 tên import / 49 file**, **438 block Python** đạt; sáu ví dụ mới thực thi
  không cần dịch vụ ngoài. Register checker: 0 lỗi, ba class kiểm được; A/B
  chưa có import trong ví dụ cũ vẫn được ghi là bỏ qua, không gọi là đã kiểm đủ năm.
- Sổ thiếu tài liệu giữ rõ snapshot cũ; các đề xuất deployment/observability
  và các chủ đề ngoài Bước 6 vẫn là backlog, không gọi mọi đề xuất cũ đã hoàn tất.

### Cổng trước commit Bước 6

| Kiểm tra | Kết quả |
|---|---|
| Hồi quy tổng với PyJWT 2.15.0 / AnyIO 4.14.2 / Uvicorn 0.48.0 | **2.881 passed, 25 skipped, 1 deselected**, 307,62 giây |
| Số thu thập | **2.907**, tăng đúng 78 từ baseline 2.829: JWT 12 + Range 16 + cleanup 15 + config 25 + TLS 10 |
| `_alive(current_pid)` riêng | **1 passed**, 0,03 giây |
| Ruff 0.16.0, mypy, pip check | Đạt; không sửa cấu hình công cụ để giảm yêu cầu |
| Audit trực tuyến bộ sàn sau nâng Uvicorn | Exit 0 theo ngoại lệ APScheduler đã có; chỉ một ID PYSEC-2026-282, hai dòng trùng; không thêm ACCEPTED |
| Import/cú pháp/coverage/register tài liệu, link mới | Đạt theo số đo phía trên |
| Git diff và cached diff check | Đạt; nội dung staged có sẵn được giữ cùng các thay đổi theo chỉ thị git add -A |

25 skip vẫn do POSIX/Windows, MQTT/S3 chưa có tài nguyên test; không tự bật
dịch vụ để tăng passed. Trong 20 warning có 19 cảnh báo thư viện/fixture cũ
và một PytestCacheWarning WinError 183 khi ghi cache; test không lỗi. Phép chạy
sau dùng cache riêng hoặc tắt cache provider, không sửa mã sản phẩm theo cảnh báo này.

Log mới trong `%TEMP%\xime-framework-fixes-20261017\`: `range-red.log`,
`range-green.log`, `session-red.log`, `session-green.log`, `config-red.log`,
`config-session-green.log`, `tls-floor-red.log`, `tls-final.log`,
`types-focused.log`, `mypy-progress2.log`, `mypy-linux-static.log`,
`full-step6.log`, `full-step6.xml`, `alive-step6.log`, `floor-step6.log`,
`coverage-before-en/vn.log`, `coverage-after-en/vn.log`, `doc-*-final.log`.

Đủ điều kiện commit Bước 6. Bước 7 sẽ kiểm bộ dependency resolver mới trong
venv sạch và consumer không cần dịch vụ ngoài, ghi riêng phần làm được trên
Windows. Linux/Python 3.12/uvloop, Certbot/ACME/VPS và tài nguyên MQTT/S3 thật
chưa được nghiệm thu; dừng trước phần cần chuyển Linux theo yêu cầu.

**Cập nhật sau commit:** đã commit Bước 0–6 tại `e5a5b5c`. Bước 7 Windows đạt:
resolver mới 2.881 passed/25 skipped/1 deselected; 12 consumer 6.557 passed/8
skipped; 24 nhánh cấu hình và 12 đồ thị DI đạt; wheel/sdist và cài wheel trắng
đạt. Chi tiết, giới hạn DI/hook và các cổng Linux ở
[`nghiem-thu-windows-framework.md`](nghiem-thu-windows-framework.md).

## Hậu kiểm hoàn thiện F4 và F7

F7 là lỗi đóng gói được wheel sạch phát hiện: chỉ cài extra jwt thì thiếu
cryptography dù tài liệu hướng dẫn RSA/EC/EdDSA. Đã bổ sung PyJWT[crypto] và
sàn cryptography runtime, kiểm 15 ca trên từng venv resolver/sàn độc lập;
[báo cáo và đối chứng](jwt-extra-thieu-crypto.md).

Ở F4, `_load()` từng trả `str(YAMLError)`, mà PyYAML có thể chép dòng cấu hình
vào thông báo. Các finding từ YAML hợp lệ đã che giá trị, nhưng parse failure
chưa đạt invariant không echo credential. Đã chỉ giữ loại lỗi và dòng/cột.
Đối chứng trực tiếp với source HEAD e5a5b5c: hai ca quoted password/secret tag
echo credential; ca URL của fixture này vốn không echo. Bản mới không echo ở
cả ba và vẫn trả inconclusive với vị trí lỗi; không biến parse lỗi thành clean.
Ba test hồi quy mới đạt, toàn nhóm config đạt 267 ca. Kiểm 12 YAML consumer
trước/sau cho kết quả tương đương hoàn toàn và đều clean; không sửa consumer.

`yaml-redaction-controls.json` ghi boolean đối chứng, không lưu lại giá trị
credential của ứng dụng. Secret trong fixture là dữ liệu thử tự tạo.
