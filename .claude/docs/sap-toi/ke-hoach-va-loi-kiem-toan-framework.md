# Kế hoạch vá lỗi kiểm toán framework và dependency

> **Trạng thái:** ĐÃ DUYỆT ngày 2026-10-17; Bước 0 và nhóm Bước 1 đã nghiệm thu
> trên Windows. Chủ dự án yêu cầu làm liền đến hết Bước 6, git add -A sau mỗi
> nhóm, commit sau Bước 6; Bước 7 làm phần Windows và dừng trước phần Linux.
> **Thuộc bản:** checkout phát triển sau `2ad5274`; chưa chọn số bản phát hành.
> **Thay cái gì:** bản kế hoạch đầu tiên cho các phát hiện ngày 2026-10-17;
> tiếp nối hai mục TLS/config đang mở trong `../kiem-toan/backlog-sua-loi.md`.
> **Bị thay bởi:** chưa có.

## 1. Mục tiêu và phạm vi xin duyệt

Khắc phục sáu lỗi đã xác nhận; xử lý các advisory dependency có liên quan;
trả nợ kiểm tra kiểu và tài liệu API đã được nêu trong báo cáo. Mỗi nhóm vá có
test đối chứng và kết quả bàn giao riêng để chủ dự án có thể commit từng phần.

Phạm vi thực thi sau khi được duyệt: source/test, khai báo dependency,
changelog và tài liệu trong repo `D:\code\xime\xime framework`.
Chủ dự án đã duyệt triển khai trong phiên làm việc ngày 2026-10-17.

Không nằm trong đề nghị duyệt này: sửa consumer, database/migration, cấu hình
triển khai của ứng dụng, dịch vụ đang chạy, CI, tag/push, nâng số phiên bản
hay phát hành PyPI. Nếu kiểm tra consumer phát hiện lỗi của consumer, ghi yêu cầu
riêng kèm bằng chứng; giữ ranh giới repo.

Chỉ thị bổ sung đã cho phép `git add -A` sau từng nhóm và commit sau Bước 6,
gồm các tài liệu có sẵn đã staged. Không cần xin duyệt lại giữa các nhóm.

Môi trường Python chung đang cài framework editable. Các phép thử dependency
phải dùng venv riêng, không chạy `pip install -U` vào môi trường đang dùng chung.
Thay source của checkout editable cũng có thể ảnh hưởng consumer khi họ nạp
mã mới; ghi rõ điều này ở mỗi lần bàn giao. Không tự restart consumer.

## 2. Căn cứ hiện tại

- HEAD: `2ad5274`; metadata và `pyproject.toml`: `0.8.3`.
- Windows/Python 3.14.8/OpenSSL 3.5.9; Uvicorn 0.47.0, PyJWT 2.13.0,
  AnyIO 4.12.1.
- Hồi quy ngày 17/10: **2.803 passed, 25 skipped, 1 deselected**; test bị
  deselect chạy riêng đạt 1 passed. Tổng thu thập khi đó là 2.829 ca.
- Ruff và pip check đạt; mypy có 49 lỗi trong 28 file; không coi đó là cổng đạt.
- Kiểm import tài liệu: 366 tên/46 file đạt; cú pháp: 426 block Python đạt.
- Coverage tên API trong docs/en: 148/317 tên chưa xuất hiện. Đây là phép dò
  cần phân loại, không đồng nghĩa thiếu 148 tính năng hoàn chỉnh.
- Có sẵn 11 đường dẫn tài liệu staged từ lượt trước; bảo toàn nội dung và index.

Báo cáo và phép tái hiện của lượt kiểm toán nằm ở:
`%TEMP%\xime-framework-audit-20261017\`:
`bao-cao-kiem-toan.md`, `audit_edges.py`, `jwt_live.py`, `edges.log`,
`jwt-live.log`, `pytest.xml`, `mypy.log`, `dependency-floor-live.log`,
`advisories.json`. Sau khi duyệt, đưa nội dung kết luận cần lưu bền vào tài liệu
kiểm toán của repo; không để việc nghiệm thu chỉ phụ thuộc file tạm.

## 3. Thứ tự và kết quả giao

| Bước | Nội dung | Kết quả bắt buộc trước khi bàn giao |
|---|---|---|
| 0 | Chốt baseline, môi trường và bằng chứng | Có snapshot phần sửa sẵn; test tái hiện các lỗi và đối chứng |
| 1 | F1: JWT và rà advisory PyJWT/AnyIO | Token lỗi bị từ chối đúng; sàn dependency được đo; từng advisory có kết luận |
| 2 | F2 + F6: If-Range và Range file rỗng | File đổi phiên bản trả full; không có Content-Range vô hiệu |
| 3 | F3: cleanup SQLAlchemy session | ContextVar khôi phục dù close lỗi hoặc bị hủy |
| 4 | F4: checker cấu hình môi trường | Bắt typo trong cả hai nhánh và endpoint; không báo oan cấu hình kế thừa |
| 5 | F5: sàn Uvicorn và TLS 1.2 | Handshake mặc định và reload đạt ma trận TLS đã định |
| 6 | Nợ mypy và tài liệu API | Sửa lỗi kiểu; API người dùng có tài liệu và ví dụ đúng |
| 7 | Nghiệm thu tổng, tương thích consumer và bàn giao | Báo cáo bằng chứng, phần còn giới hạn, danh sách file/diff từng nhóm |

Ưu tiên xử lý lỗi runtime trước phần nợ tài liệu. Bước 2 gộp hai phát hiện cùng
helper download để tránh sửa đi sửa lại cùng đường xử lý. Chỉ chuyển trạng thái
một phát hiện sang đã sửa khi test tái hiện và đối chứng đều đạt.

## 4. Bước 0 — baseline và cách kiểm chứng

1. Kiểm lại Git HEAD, worktree/index và phiên bản Python/dependency trước khi sửa.
2. Giữ snapshot nội dung 11 file tài liệu đang staged; không reset, restore hoặc
   stage lại toàn bộ. Các phần bổ sung sau này phải phân biệt được với phần cũ.
3. Chuyển phép tái hiện cần thiết thành test hồi quy ở nhóm tương ứng. Test phải
   thất bại trên mã cũ đúng vì lỗi đã xác nhận; có đối chứng hợp lệ đi cùng.
4. Tạo venv và thư mục output riêng cho phép thử phiên bản sàn. Không dùng broker,
   bucket hoặc database production. Chỉ dựng listener test loopback/cổng trống.
5. Lưu kết quả kiểm toán ngày 17/10 vào tài liệu theo chủ đề ở
   `.claude/docs/kiem-toan/`; giữ nhận định chưa được chứng minh dưới nhãn phù hợp.

Không chạy lại full suite sau mọi sửa chú thích hoặc annotation. Mỗi nhóm chạy
test liên quan; full suite chạy tại các mốc dependency và nghiệm thu tổng.

## 5. Bước 1 — F1: JWT và dependency bảo mật

### Thay đổi dự kiến

- `xime/starters/jwt/_verifier.py`: chuyển lỗi phân tích JSON lồng sâu từ token
  không tin cậy thành `AuthenticationException`, nhất quán với lỗi token sai;
  giữ phân loại `TokenExpiredException` và chuỗi nguyên nhân. Không catch-all
  để biến lỗi lập trình, lỗi cấu hình khóa hoặc mọi sự cố hệ thống thành 401.
- Kiểm `_authenticator.py` và `_middleware.py`; chỉ sửa nếu cần bảo đảm cùng
  hợp đồng ở nhánh khóa tĩnh và provider. Không thay quy tắc public_paths.
- `pyproject.toml`: mốc thử nghiệm ban đầu **PyJWT >=2.15.0** ở extra jwt;
  **AnyIO >=4.14.2** ở dependencies runtime vì FastAPI/Starlette kéo AnyIO vào
  runtime. Chỉ nâng dòng AnyIO trong dev sẽ không bảo vệ bản cài của người dùng.
  Tránh giữ hai sàn AnyIO mâu thuẫn giữa core và dev.
- `.claude/scripts/check_dep_advisories.py` và tài liệu kiểm toán: lập bảng từng
  advisory với điều kiện ảnh hưởng, đường gọi Xime, phiên bản đã vá và kết luận.
  Chỉ chỉnh công cụ khi có yêu cầu cụ thể từ kết quả đo.

### Quy tắc quyết định advisory

14 mục PyJWT và 2 mục AnyIO là cảnh báo theo phiên bản, không phải 16 đường
khai thác đã được chứng minh trong framework. F1 là đường đã tái hiện trực tiếp.

`PYSEC-2026-4146` / `GHSA-gvp8-978c-rx2q` chưa có fixed event trong JSON OSV
đã tải. Xime tạo options mới mỗi lượt verify và không bỏ kiểm chữ ký ở đường này.
Phải kiểm lại trên phiên bản mục tiêu; không mặc định nâng 2.15.0 là sạch toàn bộ.
Giữ test cho token hết hạn, issuer/audience sai và options không bị tái dùng.

Một advisory chỉ được kết luận đã xử lý khi đã nâng sang bản không affected,
hoặc chứng minh đường framework không đi vào điều kiện lỗi kèm test/tài liệu.
Không tự thêm ngoại lệ ACCEPTED chỉ để làm mã thoát thành 0. Nếu còn rủi ro
reachable chưa vá, báo rõ để chủ dự án quyết định; không coi nhóm này đã đạt.
Advisory APScheduler đã được chấp nhận từ trước phải được kiểm lại điều kiện
MemoryDataStore/LocalEventBroker; không tự thay kiến trúc scheduler.

### Nghiệm thu

- `tests_temp/jwt/` và `tests_temp/ws/`: hợp lệ, chữ ký sai, hết hạn, thiếu claim,
  issuer/audience sai, xoay khóa, public_paths và nhánh provider đều giữ semantics.
- Header JSON lồng sâu: khóa tĩnh/provider đều từ chối; không có RecursionError
  thoát khỏi verifier. Kiểm qua API thật ở httptools và h11: lỗi bị chặn ở parser
  hoặc trả 401, không thành 500 do JWT; yêu cầu hợp lệ kế tiếp vẫn hoạt động.
- Depth/size của fixture phải điều chỉnh theo interpreter thực; không suy rằng
  sys.getrecursionlimit() chính là ngưỡng của JSON decoder.
- Venv mới giải dependency được, pip check đạt; kiểm advisory cả bộ sàn và tập
  package thực cài. Có bảng triage đầy đủ và giới hạn kiểm chứng.

Nguồn đã đối chiếu khi lập kế hoạch:
[PyJWT 2.15.0](https://github.com/jpadilla/pyjwt/releases/tag/2.15.0),
[advisory options](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-gvp8-978c-rx2q),
[AnyIO 4.14.2](https://github.com/agronholm/anyio/releases/tag/4.14.2).
Đây là mốc để thử, sàn cuối cùng phải qua phép đo và tra advisory lại lúc triển khai.

## 6. Bước 2 — F2 và F6: tải file đúng phiên bản

### Thay đổi dự kiến

- `xime/adapters/web/files/_download.py`: đánh giá If-Range trước khi parse/áp dụng
  Range. Strong ETag khớp mới tiếp tục trả 206; không khớp, weak/malformed
  validator hoặc không có metadata đủ để xác nhận thì bỏ Range và trả full 200.
- `StorageStat` hiện chỉ có size/content_type/etag, chưa có last_modified.
  Với If-Range dạng ngày, chọn full 200 khi không xác nhận được strong validator;
  không thêm field bắt buộc hay đổi hợp đồng StorageService để vá mục này.
- File 0 byte có byte-range không thể phục vụ: trả 416 và `bytes */0`, tránh
  tạo range kết thúc âm. Giữ malformed Range theo quy tắc bỏ qua và trả full.
- Giữ streaming; không nạp toàn bộ object vào RAM để so sánh hoặc xử lý range.

### Nghiệm thu

Trong `tests_temp/web_files/test_file_helpers.py`, bổ sung:

- ETag khớp + Range: 206 đúng dữ liệu; ETag cũ sau ghi đè: 200 chứa toàn bộ file mới.
- ETag cũ + Range không thỏa: vẫn 200, vì phải bỏ Range trước khi xét 416.
- Không If-Range: các dạng Range đang hỗ trợ giữ nguyên.
- Weak ETag, thiếu ETag, validator sai hoặc dạng ngày không xác nhận được: full 200.
- File rỗng: suffix/open/closed Range không tạo Content-Range vô hiệu.
- File không rỗng: suffix và range bình thường giữ đúng; 404, nosniff,
  Content-Disposition, Unicode filename và stream theo chunk vẫn đúng.
- LocalFileStorage thật cho ca ghi đè; fake/S3 metadata cho đối chứng backend
  trung tính. Không bật MinIO hoặc dùng bucket của người dùng.

Không mở rộng sang multi-range hay đổi public StorageService. Bản vá validator
không được quảng cáo là bảo đảm snapshot nguyên tử giữa stat() và open_stream()
khi có ghi đè đồng thời; đó là một hợp đồng khác.

Chuẩn đối chiếu: [RFC 9110, 13.1.5](https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.5).

## 7. Bước 3 — F3: khôi phục session trong mọi đường thoát

File dự kiến: `xime/starters/sqlalchemy/transaction.py`, `readonly.py`,
`tests_temp/sqlalchemy/test_read_only.py` và một file test cleanup riêng nếu cần.

- Đặt reset ContextVar trong finally riêng, luôn chạy dù session.close() thất bại.
- Read-only dọn `_session`/`_token` của context sau khi thoát; giữ semantics mượn
  session của khối ngoài, không đóng session không thuộc quyền sở hữu của mình.
- Nếu chỉ close lỗi, lỗi phải được báo; nếu đã có lỗi nghiệp vụ/commit/rollback,
  giữ nguyên lỗi gốc và báo lỗi cleanup rõ ràng. Không nuốt CancelledError.
- Giữ entity dùng được sau khối đọc, thứ tự expunge/rollback, và transaction
  tường minh. Không thêm savepoint, AOP hoặc thay chính sách transaction lồng nhau.

Nghiệm thu gồm thành công, lỗi trong thân khối, lỗi begin/commit/rollback/close,
cancellation tại close, khôi phục session bao ngoài và gọi read-only tiếp theo
sau khi bên gọi bắt lỗi. Dùng fault injection có đối chứng và test SQLite thật
cho đường bình thường. Không coi fault injection là bằng chứng DB live từng lỗi.

## 8. Bước 4 — F4: checker rà nhánh môi trường và TLS endpoint

File dự kiến: `xime/cli/_config_check.py`, `_config_spec.py`;
`tests_temp/cli_config/test_check.py`, `test_spec.py`,
`tests_temp/config/test_runtime_environment_overlay.py` khi cần.

- Dùng chung logic kiểm khối framework cho common và cả hai nhánh local/server.
- Kiểm tên khóa của từng overlay thô; kiểm cấu trúc ngữ nghĩa cần thiết trên
  cấu hình đã merge. Không bắt một overlay thiếu field vốn được common cấp.
- Nhận diện tên động ở `process.web.<id>` và
  `processes.<process_id>.web.<id>`; kiểm schema SSL bên trong endpoint.
- Báo đúng đường dẫn nhánh/key, ví dụ `environments.server.webserver.ssl.ss1`;
  không in giá trị credential, URL có mật khẩu hoặc nội dung key/cert.
- Không đi vào schema riêng của app; giữ ba verdict clean/findings/inconclusive,
  alias server/webserver và quy tắc chỉ một cơ chế chọn môi trường.

Nghiệm thu: typo websever/ss1/certfil ở root, nhánh đang chọn, nhánh chưa chọn và
endpoint; cấu hình kế thừa một phần hợp lệ; tên process/server tùy ý; HTTP chủ ý;
ssl rỗng chủ ý; khối riêng của app; xung đột alias; overlay sai hình dạng; file
không đọc được. Không biến bản vá checker thành lệnh cấm khởi động HTTP nói chung.

## 9. Bước 5 — F5: Uvicorn và ma trận TLS mặc định

File dự kiến: `pyproject.toml`, `tests_temp/web/test_tls.py`,
`test_tls_reload.py`; chỉ sửa `_adapter.py`/`_tls_reload.py` nếu phép đo yêu cầu.

Hướng đề nghị: nâng sàn extra web lên **Uvicorn >=0.48.0**, dùng default OpenSSL
qua API của Uvicorn; tiếp tục tôn trọng cipher ứng dụng khai tường minh.
Không tự chọn danh sách cipher cứng riêng cho framework.
Release notes tại tag 0.48.0 ghi thay default ssl_ciphers thành None:
https://raw.githubusercontent.com/Kludex/uvicorn/0.48.0/docs/release-notes.md

Nghiệm thu trong venv riêng:

- RSA và ECDSA; client TLS 1.2 và 1.3; cipher mặc định và khai tường minh.
- Startup và reload A -> B -> C; SNI/no-SNI; keep-alive giữ context cũ.
- Cert/key không khớp giữ context cũ; CA/hostname sai vẫn bị client từ chối.
- Watcher, retry/backoff và concurrent deduplication.
- CA client mTLS A -> B: trước/sau nhận và từ chối đúng ở TLS 1.2/1.3.
- Cụm hai worker: ACK đủ/thiếu/hỏng, partial/timeout và rollback promotion.
- Management vẫn loopback, theo primary; public health vẫn chỉ status.

Không áp chính sách bắt fingerprint các worker bằng nhau; vấn đề đó đã được
rút lại. Không sửa cấu hình process/processes của consumer để né lỗi.

## 10. Bước 6 — trả nợ mypy và tài liệu API

### 6A. 49 lỗi mypy

Phân nhóm 28 file theo output thật: reflection/DI, adapter metadata và generic,
API POSIX khi kiểm trên Windows, grpc/protobuf, web middleware/router,
MQTT/Modbus/OPC UA và kiểu trả về Redis.

Sửa annotation, narrowing, Protocol, generic và platform guard đúng theo code;
nếu là lỗi hành vi thật, bổ sung test rồi sửa hẹp. Mục tiêu là
`python -m mypy xime` đạt 0 lỗi theo cấu hình hiện tại và phiên bản công cụ ghi
trong báo cáo. Không hạ strictness, tắt error code toàn cục, bỏ kiểm module hay
rải Any/type: ignore để xóa số lỗi. Ngoại lệ typeshed có bằng chứng phải giải
thích tại dòng, phạm vi tối thiểu và có đối chứng; ưu tiên không thêm ngoại lệ.

Không đổi runtime public API chỉ để chiều bộ kiểm kiểu. Phần sửa annotation
chạy nhóm test liên quan; không viết test chỉ sao chép annotation.

### 6B. 148/317 tên chưa có mặt trong docs/en

1. Chạy lại công cụ cho cả docs/en và docs/vn; lập bảng tên/module/vai trò.
2. Phân biệt API người dùng, tên tương thích và hạ tầng được export để DI quét.
3. Bổ sung hướng dẫn/tra cứu có mục đích, chữ ký hoặc ví dụ cho API người dùng;
   mô tả vai trò/giới hạn của hạ tầng khi cần. Có thể thêm trang api-reference
   song ngữ để tổ chức phần tra cứu, không thay bằng danh sách tên vô ngữ cảnh.
4. Không xóa export hay thay __all__ để làm giảm counter: __all__ còn điều khiển
   DI scanner. Không công bố adapter như một điểm mở rộng công khai.
5. Cập nhật tài liệu cấu hình/dependency, Range, transaction và backlog sau các
   bản vá; sửa sổ thiếu tài liệu `lo-hong-tai-lieu-nguoi-dung.md` theo số đo mới.

Nghiệm thu: mọi tên bị báo thiếu có trạng thái giải thích được; API người dùng
thuộc phạm vi đều có tài liệu song ngữ; import/cú pháp/register/example đạt.
Báo cả counter thô và bảng phân loại; không gọi công cụ đạt nếu mã thoát còn 1.
Tên hạ tầng chưa đưa vào hướng dẫn người dùng phải có lý do cụ thể trong sổ,
không gộp thành một mục 'bỏ qua phần còn lại'.

## 11. Bước 7 — nghiệm thu tổng và giới hạn bàn giao

### Cổng nghiệm thu

- Sáu lỗi có test tái hiện và đối chứng đạt; bảng advisory có kết luận từng mục.
- Full suite framework đạt, không giảm số test để đạt. So cả số thu thập,
  skipped/deselected và lý do; không ép số passed bằng mốc cũ khi test đã thêm.
- Test `_alive(os.getpid())` chạy riêng nếu run gộp Windows vẫn có vấn đề;
  ghi chính xác số đã đo. Không sửa code sản phẩm theo triệu chứng của test đó.
- Ruff, pip check, mypy và các phép kiểm tài liệu đạt theo phạm vi đã nêu.
- Kiểm phiên bản sàn và một tập dependency mới được resolver chọn, trong venv
  riêng; chỉ chạy lại full suite khi tập dependency thay đổi đáng kể hoặc có
  lỗi/chỉnh sửa mới cần kiểm chứng.
- Kiểm consumer tuần tự để giảm RAM: chỉ đọc config, chạy test không cần dịch vụ
  và kiểm DI trên bản sao/temp nếu có thể; dùng framework candidate trong venv,
  không cài lại hoặc sửa repo của họ. Ghi danh sách consumer thực kiểm và kết quả.
- Linux/Python 3.12/uvloop phải được chạy khi có môi trường; thiếu thì ghi
  CHƯA KIỂM CHỨNG và giữ làm điều kiện trước phát hành, không gắn nhãn pass.
  Broker MQTT, MinIO, Certbot/ACME/VPS thật chỉ nghiệm thu khi có tài nguyên
  test phù hợp; không tự bật/tắt dịch vụ của phiên khác.

### Bàn giao theo từng nhóm

Mỗi nhóm báo: file thay đổi, hành vi trước/sau, test/log, rủi ro còn lại và
diff để chủ dự án có thể commit riêng. Theo nhịp làm cũ của repo, bàn giao từng
nhóm cho chủ dự án commit trước khi nhận nhóm kế. **Chỉ thị mới 2026-10-17:**
làm liền đến hết Bước 6, chạy `git add -A` sau mỗi nhóm, commit khi Bước 6 xong;
thực hiện Bước 7 trong phạm vi Windows rồi dừng ở phần Linux. Chỉ thị này thay
nhịp bàn giao cũ; không bao gồm tag/push/nâng phiên bản/phát hành PyPI.

Changelog và backlog chỉ ghi 'đã sửa' sau nghiệm thu nhóm tương ứng. Bản nâng
số phiên bản và công việc phát hành là bước sau do chủ dự án quyết định.

### Trạng thái hiện tại

| Bước | Trạng thái ngày 2026-10-17 |
|---|---|
| 0 | Đạt: snapshot index và 11 file sửa sẵn; venv/output riêng; báo cáo kiểm toán đã lưu bền |
| 1 | Đạt trên Windows: F1 được vá; PyJWT 2.15.0/AnyIO 4.14.2 đã kiểm chứng; 16 advisory có kết luận |
| 2 | Đạt: 10/16 test mới đỏ trên mã cũ; web_files/storage sau vá 95 passed, 6 skipped; If-Range và file rỗng đúng hợp đồng |
| 3 | Đạt: 14/15 ca fault injection đỏ trên mã cũ; SQLAlchemy sau vá 43 passed, gồm SQLite thật |
| 4 | Đạt: 23/25 test mới đỏ trên mã cũ; fixture topology cũ được sửa đúng parser; config/SQLAlchemy hồi quy 307 passed |
| 5 | Đạt: đối chứng Uvicorn 0.47 lỗi TLS 1.2; 0.48 đạt 110 test TLS/management/health, 1 skip; RSA/ECDSA, TLS 1.2/1.3, cipher mặc định/tường minh, mTLS CA A→B |
| 6 | Đạt: mypy 0/250 file; EN/VN 0/317 tên thiếu; 152 lượt export phân loại đủ; full 2.881 passed, 25 skipped, 1 deselected; test tách riêng đạt 1; đủ điều kiện commit |
| 7 | Tiếp tục sau commit: dependency resolver mới, consumer Windows; dừng trước phần Linux |

Nhóm 1 thay `_verifier.py`, `pyproject.toml`, thêm
`tests_temp/jwt/test_untrusted_input.py`, ghi changelog và cập nhật tài liệu
kiểm toán. Trước bản vá, 5/12 ca mới thất bại đúng vì F1; sau bản vá cả 12 đạt
ngay trên dependency cũ. Với dependency mục tiêu, JWT/WebSocket đạt 227 ca;
hồi quy tổng đạt **2.815 passed, 25 skipped, 1 deselected**. Test Windows tách
riêng đạt 1 ca. Ruff, pip check, mypy riêng verifier và kiểm tài liệu đạt.
49 lỗi mypy toàn repo vẫn thuộc Bước 6, chưa được tuyên bố đã xử lý.

Đã kiểm cài editable `[web,jwt]` trong venv sạch và audit đủ 22 package khác
Xime ở đó: không có advisory được báo. Audit bộ sàn và 35 dependency khai báo
thực cài chỉ còn một advisory APScheduler đã được chấp nhận từ trước (hai dòng
trùng ID); không thêm ngoại lệ mới. Bảng triage và lệnh kiểm ở
[`kiem-toan-framework-va-dependency.md`](../kiem-toan/kiem-toan-framework-va-dependency.md).

Trước chỉ thị làm liền, Git index và 11 nội dung đã stage được giữ nguyên. Chưa commit/tag/push,
nâng phiên bản hay phát hành. Không cài lại dependency vào Python chung và
không restart consumer; source editable đã thay nên consumer có thể nạp bản vá
khi import lại. Tiếp tục nhóm 2 theo chỉ thị mới ở mục 11.
