# Nghiệm thu Windows sau kiểm toán framework

> **Trạng thái:** Bước 0–6 đã commit; phần Bước 7 thực hiện được trên Windows
> đã đạt ngày 2026-10-17. **DỪNG trước Linux** theo chỉ thị chủ dự án.
> **Thuộc bản:** nền commit `e5a5b5c` và bản vá bổ sung F4/F7; metadata vẫn 0.8.3,
> chưa nâng số/phát hành. Các số đo e5a5b5c phía dưới giữ như snapshot lịch sử.
> **Thay:** bổ sung nghiệm thu consumer, resolver và artifact sau
> [báo cáo vá Bước 0–6](kiem-toan-framework-va-dependency.md).
> **Bị thay bởi:** chưa có; Linux/Python 3.12/uvloop vẫn chưa kiểm runtime.

## Cập nhật completion audit

Đối chiếu lại từng yêu cầu đã phát hiện và xử lý thêm hai phần còn thiếu:

- **F7, đóng gói JWT:** wheel sạch trước đây chỉ có HMAC vì crypto nằm ở dev.
  Extra jwt hiện kéo PyJWT[crypto] và cryptography >=50.0.0. Wheel cuối cài
  **chỉ jwt**, không dev/system-site-packages, đạt **15/15 ca trên mỗi venv**:
  resolver PyJWT 2.15.1/crypto 50.0.2 và đúng sàn 2.15.0/50.0.0. Ký, verify
  token đối chứng và từ chối chữ ký sửa đều đạt. Hai runtime đều audit exit 0.
- **F4, parse YAML:** exception của PyYAML từng có thể echo dòng chứa credential.
  Hiện chỉ báo loại lỗi và dòng/cột. Ba test mới đạt, đối chứng source HEAD
  chứng minh hai fixture cũ lộ giá trị còn bản mới không lộ. 12 YAML consumer
  hợp lệ cho kết quả trước/sau giống hệt và đều clean.
- **Hồi quy cuối:** bộ sàn mới **2.884 passed, 25 skipped, 1 deselected**
  (274,92 giây); resolver mới cũng **2.884/25/1** (319,40 giây). Thu thập 2.910
  ca, tăng ba test parse YAML; `_alive` riêng 1 passed (0,02 giây).
- Mypy 0/250, Ruff, kiểm tài liệu EN/VN và audit sàn đều đạt. Artifact cuối
  256/306 entry, **251 file package khớp byte với source hiện tại**, không rò
  tài liệu nội bộ/test/token. Crypto runtime và redaction cũng đã kiểm từ wheel.

[F7 và phép kiểm wheel](jwt-extra-thieu-crypto.md) ·
[Ma trận yêu cầu/bằng chứng](doi-chieu-nghiem-thu-ke-hoach.md).
Kết quả consumer 6.557/8 bên dưới là bộ kiểm e5a5b5c; không gọi đó là lượt chạy
lại toàn bộ consumer sau bổ sung. Phần bổ sung chỉ đổi dependency và thông báo
parse lỗi; đồ thị/runtime nghiệp vụ không đổi, và checker đã được đối chứng lại
trên 12 YAML nguồn. Linux và các cổng có điều kiện vẫn giữ nguyên bên dưới.

## 1. Phạm vi và hai bộ dependency

Chạy trên Windows/Python 3.14.8/OpenSSL 3.5.9. Không cài lại Python/dependency
chung, sửa repo/cấu hình consumer, restart dịch vụ, gọi API nghiệp vụ trên dịch vụ đang chạy, chạy
migration hoặc gửi email. Chỉ listener loopback và tiến trình test do framework
suite sở hữu; consumer dùng mock và SQLite in-memory theo fixture đã rà.

| Package | Bộ kiểm sàn mới của bản vá | Resolver trong venv sạch `[all,dev]` |
|---|---|---|
| FastAPI | 0.135.1 | 0.143.3 |
| Starlette | 1.6.0 | 1.8.0 |
| Pydantic | 2.12.5 | 2.14.1 |
| SQLAlchemy | 2.0.48 | 2.1.5 |
| PyJWT | **2.15.0** | 2.15.1 |
| AnyIO | **4.14.2** | 4.15.1 |
| Uvicorn | **0.48.0** | 0.54.0 |
| mypy | 2.3.1 | 2.4.0 |
| Ruff | 0.16.0 | 0.17.1 |

“Bộ kiểm sàn mới” kiểm đúng ba sàn đã thay trong bản vá, còn các dependency
khác giữ baseline đang dùng. **Không phải** bằng chứng chạy toàn bộ tổ hợp
minimum của mọi extra. Python 3.12 không có trên máy này; tổ hợp minimum còn
lại để nghiệm thu ở cổng Linux, không dùng Python 3.10 trái requires-python.

## 2. Framework và dependency

| Phép kiểm | Kết quả |
|---|---|
| Full suite bộ sàn mới | **2.881 passed, 25 skipped, 1 deselected**, 307,62 giây, 20 warnings |
| Full suite resolver mới, venv sạch | **2.881 passed, 25 skipped, 1 deselected**, 306,26 giây, 18 warnings |
| `_alive(current_pid)` riêng | 1 passed trên mỗi bộ, 0,03 giây |
| Số thu thập mỗi full suite | 2.907, tăng đúng 78 ca so baseline |
| mypy/Ruff trên cả hai bộ công cụ | Đạt; mypy 0 lỗi / 250 file, không hạ cấu hình |
| Phân tích tĩnh `--platform linux` trên Windows | 0 lỗi; không coi là chạy Linux |
| Cài mới `[all,dev]` và pip check | Đạt; không dùng system-site-packages trong venv resolver |
| Audit bộ sàn pyproject | Không có advisory mới; giữ ngoại lệ APScheduler đã có |
| Audit **120 package thực cài**, gồm dependency bắc cầu/dev | Chỉ **PYSEC-2026-282** của APScheduler 4.0.0a6; hai dòng trùng một ID; pip-audit thô exit 1 đúng vì mục này |

Không thêm ACCEPTED hoặc bỏ test để đạt. 25 skip vẫn do POSIX/Windows, thiếu
MQTT/S3 test endpoint; `_alive` được chạy riêng theo lịch sử Windows. Một warning
cache WinError 183 ở bộ đầu được ghi rõ trong báo cáo Bước 6; bộ resolver dùng
`-p no:cacheprovider`. Các warning còn lại là fixture HMAC ngắn và cảnh báo thư viện.

Ma trận TLS RSA/ECDSA × TLS 1.2/1.3 × default/explicit cipher, CA mTLS A→B,
rollback cert/key sai, watcher, SNI/no-SNI, keep-alive và deduplication đã nằm
trong suite. `TestTlsReloadCoordination` chạy cụm hai worker thật, API chờ đủ
ACK và duplicate chỉ áp dụng một lần mỗi worker. Suite ACK hỏng/thiếu/rỗng và
promotion/management được giữ trên cả hai tổ hợp dependency.

## 3. Mười hai consumer

Chạy tuần tự để giảm RAM bằng Python của venv bản vá (PyJWT 2.15.0,
AnyIO 4.14.2, Uvicorn 0.48.0); PYTHONPATH trỏ framework source và consumer
tương ứng. Không cài package vào repo consumer. Tắt bytecode/cache pytest,
đặt basetemp/JUnit/log ngoài repo và tạo thư mục cha trước khi chạy.

| Consumer | Passed | Skipped | Đồ thị DI: số singleton trong kế hoạch |
|---|---:|---:|---:|
| Base Data | 688 | 0 | 135 |
| Base Notification | 457 | 0 | 75 |
| CRM | 207 | 1 | 77 |
| Giao việc | 171 | 1 | 78 |
| Kho | 234 | 1 | 76 |
| Nhân sự/chấm công | 684 | 1 | 176 |
| Sổ thu chi | 241 | 1 | 79 |
| Admin | 315 | 1 | 95 |
| Dental | 1.574 | 0 | 481 |
| Nhà trọ | 428 | 0 | 246 |
| Nhà hàng | 485 | 0 | 354 |
| Shop hoa | 1.073 | 2 | 190 |
| **Tổng** | **6.557** | **8** | **12/12 đồ thị đạt** |

Thu thập 6.565 test, **0 failed / 0 errors**. Đối chiếu hash trước/sau cho
**5.709 file tracked** thuộc app/clients/resources/test/pyproject của các backend:
không thay đổi. Tám assertion frontend lỗi thời ghi ngày 11/10 không còn fail
trong snapshot hiện tại; không dùng số đo cũ để mô tả các repo đang chạy.

Tám skip thực tế: năm bộ Service ngang có parameter set kiểm vòng nền rỗng;
Admin không có registry cấp độ tính năng; Shop hoa có một topology một process
không cần shared và một test không tìm thấy CLIENT_ID trong cấu hình frontend.
Không sửa/loại test hay mã consumer để đổi verdict.

Đã kiểm cấu hình bằng checker mới **12/12 clean**, model/topology của **24 nhánh
local/server** đều hợp lệ. Nhánh server của cả 12 khai TLS và một process;
đó là kiểm cấu hình nguồn, **không phải** xác nhận cert production tồn tại,
còn hạn hoặc đang được service thực dùng.

DI probe dùng config thực và `XimeContainer.build()` để quét, phân giải hint,
kiểm binding/chu trình/thứ tự; giữ các config factory và SDK đăng ký. Arena/bus
chỉ có placeholder đúng type phục vụ đồ thị, không cấp vùng nhớ hay chạy
constructor nghiệp vụ qua get_all_in_order. **Không chạy PostConstruct/RunOnce**,
không coi đồ thị đạt là consumer đã startup/live-test thành công. Những luồng
cần DB/cert runtime/dịch vụ thật nằm ngoài phép đo này.

## 4. Artifact

- Build wheel/sdist từ commit đã vá bằng hatchling 1.32.4; `twine check` đều PASSED.
- Wheel **256 entry**, sdist **306 entry**; không chứa `.claude/`, `tests_temp/`,
  CLAUDE/AGENTS hay pypi_token. Gói chỉ để QA; không upload/phát hành.
- Cài wheel `[web,jwt]` vào venv trắng: pip check, CLI `--help`, import,
  HS256 sign/verify và từ chối token JSON lồng sâu đều đạt.
- Xác nhận import từ **venv-wheel/Lib/site-packages/xime**, chạy ngoài checkout,
  không bị source editable che khuất. Metadata wheel có đúng AnyIO >=4.14.2,
  Uvicorn >=0.48.0, PyJWT >=2.15.0.
- Sau QA không còn tiến trình Python mang đường dẫn thư mục test của lượt này.
  Môi trường chung vẫn PyJWT 2.13.0 / AnyIO 4.12.1 / Uvicorn 0.47.0;
  source editable đã đổi, dependency triển khai cần cập nhật qua quy trình riêng.

## 5. Bằng chứng và chạy lại

Output riêng ở `%TEMP%\xime-framework-fixes-20261017\`:

- `full-step6.log`, `full-step6.xml`, `full-resolved.log`, `full-resolved.xml`,
  `alive-step6.log`, `alive-resolved.log`.
- `resolved-install-report.json`, `resolved-advisories.json`, `mypy-resolved.log`.
- `run_windows_consumers.py`, `probe_consumer_config_di.py`;
  `consumers/results.json`, `consumers/config-di-results.json`, log/JUnit từng repo.
- `artifacts/`, `build-artifacts.log`, `wheel-install.log`, `wheel-cli.log`.
- Bản cuối: `artifacts-completion/`, `artifact-completion-check.json`,
  `wheel-completion/results.json`, `wheel-completion.log`,
  `full-completion.log`, `full-completion.xml`, `full-completion-resolved.log`,
  `full-completion-resolved.xml`, `yaml-redaction-controls.json`,
  `consumer-config-equivalence.json`, `wheel-*-advisories.json`.

Framework (venv đã cài đủ extra/dev):

```powershell
python -m pytest tests_temp -q -rs -p no:cacheprovider --deselect=tests_temp/link/test_cleanup.py::TestAlive::test_this_process_is_alive
python -m pytest tests_temp/link/test_cleanup.py::TestAlive::test_this_process_is_alive -q -p no:cacheprovider
python -m mypy xime
python -m ruff check xime --no-cache
python -m pip check
python .claude/scripts/check_dep_advisories.py
```

Consumer: đặt cwd đúng backend, PYTHONPATH gồm framework candidate và backend,
PYTHONDONTWRITEBYTECODE=1; dùng `python -m pytest test -q -rs -p no:cacheprovider
--basetemp <temp-riêng> --junitxml <output-riêng>`. Basetemp cần có parent tồn tại.
Các fixture DB đã đọc dùng SQLite in-memory; không thay chúng bằng DB dev.

## 6. Cổng Linux và giới hạn còn lại

Dừng tại đây theo chỉ thị chủ dự án, không cài Linux/WSL hoặc chạy VPS:

1. Python 3.12/Linux/uvloop và tổ hợp minimum còn lại; full suite trên filesystem
   POSIX thật, gồm quyền file, /dev/shm, Unix sockets, orphan cleanup.
2. Certbot/ACME, symlink lineage, quyền service account, hook reload và VPS thật.
3. Broker MQTT, MinIO/S3 test thật khi có tài nguyên phù hợp; không tự bật dịch
   vụ của phiên khác để xóa các skip.
4. Startup/hook và nghiệp vụ consumer với chứng thư/DB thật, CORS/OAuth/luồng
   người dùng đã xác thực. Không suy kết quả đồ thị/SQLite thành các bằng chứng này.

Sáu phát hiện framework đã sửa theo bằng chứng Windows; các cổng trên là phần
nghiệm thu môi trường còn mở trước phát hành, không phải lỗi đã được chứng minh mới.
