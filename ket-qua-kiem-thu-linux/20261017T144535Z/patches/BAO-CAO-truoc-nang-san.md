# Nghiệm thu Linux 20261017T144535Z

> Hoàn thành phần đo được ngày 2026-10-17. Source Windows sau `78c0fa8` / `e5a5b5c`,
> metadata 0.8.3. Kết luận dưới đây là phép đo Linux, không lấy Windows thay thế.
> Chưa sửa framework/test gốc. Các giới hạn hạ tầng còn mở được ghi riêng.

## 1. Kết luận

Ba lượt full suite đều **2.898 passed / 12 skipped / 0 failed / 0 error**,
thu thập đủ **2.910 ca**, không deselect. Lượt asyncio và uvloop dùng cùng tập
dependency resolver; lượt thứ ba dùng core tương thích thấp cùng các sàn bảo mật.

| Cổng | Kết luận | Bằng chứng |
|---|---|---|
| Source, backup và Git gốc | ĐẠT; payload không đổi; ghi chú ref nội bộ ở mục 7 | `source-final.json`, `logs/manifest-before.log`, `logs/manifest-after.log` |
| Python 3.12, full suite mặc định | ĐẠT | `xml/full-asyncio.xml` |
| Đối chứng loop và full uvloop | ĐẠT, có đối chứng ngược | `logs/loop-*.log`, `xml/full-uvloop.xml` |
| Worker thật, shared listener, HTTP/WS/HTTPS/WSS/Unix credentials | ĐẠT | `xml/runtime-probes-v2.xml`, `xml/unix-peercred-v3.xml`, worker logs |
| POSIX, TLS matrix, mTLS, cluster ACK | ĐẠT các test hiện có | `posix-tls-evidence.json` và ba full-suite XML |
| Symlink lineage, watcher/backoff, management hook | ĐẠT mô phỏng trên Linux | `xml/lineage-watcher-v3.xml`, `logs/lineage-watcher-v3.log` |
| Minimum từng nhóm | 12 nhóm đạt; 2 tổ hợp sàn xung đột metadata | `minimum-results.json`, mục 4 |
| Core tương thích và gRPC tương thích | ĐẠT tổ hợp thay thế đã ghi rõ | `xml/core-compatible.xml`, `xml/grpc-compatible.xml` |
| Lint/type/docs | ĐẠT theo phạm vi checker | `logs/ruff.log`, `logs/mypy.log`, `logs/docs-*.log` |
| Advisory | Không còn mục mới ngoài APScheduler đã chấp nhận có điều kiện | `advisory-resolver-final.json`, mục 5 |
| Artifact và hai runtime wheel JWT | ĐẠT 15 ca mỗi môi trường, audit sạch sau cập nhật pip | `artifact-check.json`, `wheel-jwt-results.json`, `wheel-*-audit-after.json` |
| MQTT thật | ĐẠT 2/2; broker test đã dừng | `xml/mqtt-live.xml`, `logs/mqtt-broker.log` |
| S3/MinIO thật | CHƯA KIỂM; tải binary trả HTTP 410 | `logs/download-minio.log` |
| Certbot/ACME/DNS/VPS thật; consumer/DB/cert/nghiệp vụ live | CHƯA KIỂM | Không có phép đo hạ tầng thật trong lượt này |

Hai phát hiện minimum là sai lệch của **tổ hợp sàn khai báo**, không phải lỗi của
lượt cài resolver mới. Không thay floor/exception/skip trong source để làm xanh.

## 2. Máy và bản nhận

- Debian 13.7, kernel `6.12.111+deb13-amd64`, AMD Ryzen 7 5800H, 16 logical CPU,
  RAM khoảng 13 GiB. Chạy bằng user `thang`, UID 1000; không chạy pytest bằng root.
- Đích ext4: `/home/thang/code/xime/xime framework`.
- Nguồn NTFS: `/media/thang/Data/code/xime/xime framework`.
- Hệ thống có Python 3.13.5. Lượt này dùng **CPython 3.12.15** riêng,
  OpenSSL **3.5.9**, tải qua uv vào `/tmp`; không thay Python hệ thống.
- Workspace/venv/key test: `/tmp/xime-linux-run-20261017T144535Z/`.
  Thư mục này là tmpfs, mất khi reboot; log/XML/harness/artifact đã lưu bền ở cây repo.
- `xime.__file__` trỏ đúng source đích; xem `logs/import-runtime.log`.
- Manifest có **749 dòng**, cộng chính manifest là **750 file payload**.
  SHA-256 manifest: `d665fe89092c0ab4132c7ceabf4525feb5a0d77cf145bd14c0b490b48340a0d1`.
- Resolver thực cài: FastAPI 0.143.3, Starlette 1.8.0, Pydantic 2.14.1,
  Uvicorn 0.54.0, uvloop 0.23.0, pytest 9.1.1, pytest-asyncio 1.4.0,
  PyJWT 2.15.1, cryptography 50.0.2, AnyIO 4.15.1.
  Freeze đầy đủ: `logs/resolver-freeze.log`.
- Máy đo và điều kiện: `logs/{kernel,linux,cpu,ram,space,user,filesystem}.log`.
  Có chạy một số nhóm độc lập đồng thời; không dùng các thời gian này làm benchmark.

## 3. Full suite và runtime thật

| Lượt | Passed | Skip | Fail/error | Deselected | Tổng | Thời gian wrapper |
|---|---:|---:|---:|---:|---:|---:|
| Resolver, loop pytest mặc định | 2898 | 12 | 0 | 0 | 2910 | 239,193 s |
| Resolver, loop pytest uvloop | 2898 | 12 | 0 | 0 | 2910 | 236,068 s |
| Core tương thích + sàn bảo mật | 2898 | 12 | 0 | 0 | 2910 | 272,040 s |

Mỗi lệnh có `logs/<tên>.command.txt`, `.json` (UTC, thời gian, exit), `.exit`, `.log`;
XML ở `xml/`. `test-summary.json` lưu số liệu từng lượt. Không cộng ba lượt thành
số test độc lập. `test_this_process_is_alive` chạy trong full suite, không bị loại
như hạn chế ở Windows.

12 skip mỗi full suite: 5 ca Win32 accept lock; 1 ca orphan guard chỉ Windows;
2 ca MQTT khi broker chưa chạy lúc collection; 4 ca S3 chưa có endpoint. MQTT sau
đó đã được chạy riêng trên broker thật và đạt; không sửa lại con số skip của full.
Không có giảm collection; Windows là 2.884/25/1, còn Linux là 2.898/12/0.

Probe in `asyncio.unix_events._UnixSelectorEventLoop` và `uvloop.Loop` ở hai lượt;
probe cố tình mong uvloop nhưng không nạp plugin ra đúng exit 1. Sản phẩm vẫn dùng
loop factory của nó; nhãn loop pytest không mô tả mọi tiến trình con.

`probeapp` là app/harness bổ sung ngoài source gốc. Worker phản hồi loop và PID
trực tiếp: một app HTTP/WS/Unix và cụm 2 worker shared listener đều chạy uvloop.
Unix RPC trả PID/UID của client từ request context, khớp PID pytest và UID 1000;
socket được dọn sau graceful shutdown. Có HTTPS/WSS với CA/hostname kiểm thật.

TLS hiện có chạy RSA/ECDSA × TLS 1.2/1.3 × default/explicit cipher, SNI/no-SNI,
reload/mTLS CA rotation, lỗi cert/key và health/management/cluster ACK.
Danh sách node ID và trạng thái thực nằm ở `posix-tls-evidence.json`.

Lineage mới dùng symlink tương đối `../../archive/test/...`, đổi từng link qua
`os.replace`. Cố tình để cert B/key A hơn một nhịp watcher: hook trả 503 SSLError,
watcher gặp lỗi rồi tự phục hồi sau backoff khi key B tới; kết nối A được giữ sống
bằng request định kỳ để tránh timeout idle 5 s. Kết nối mới thấy B rồi C; reload
lặp trả unchanged. Key chmod 000 và link gãy trả 503 PermissionError/FileNotFoundError,
context cũ vẫn phục vụ. Timeline/serial/fingerprint nằm trong log, key tổng hợp chỉ ở `/tmp`.

**Lỗi harness đầu và cách khắc phục:** `runtime-probes` có 2 fail/1 pass do gửi
SIGTERM cho app đơn khiến cleanup không chạy, và chỉ bắn 120 request quá nhanh
trước khi worker thứ hai sẵn sàng. Đổi harness sang SIGINT cho app đơn, đợi tối đa
30 s để thấy hai worker; `runtime-probes-v2` đạt 3/3. Bản v3 đo thêm watcher backoff
và PID/UID thật đều đạt. Giữ log/XML cũ, không gán hai fail đó thành lỗi sản phẩm.

## 4. Minimum từng nhóm và hai phát hiện

Mỗi nhóm dùng venv mới; chỉ ghim floor trực tiếp của nhóm đang đo. Các nhóm khác
và test tools do resolver chọn để chạy fixture đầy đủ; đây không phải mọi floor
cùng lúc. Constraints, install/pip-check/freeze/import/test log lưu riêng; venv
minimum đã bỏ sau khi lưu bằng chứng, không đụng môi trường hệ thống.

| Nhóm | Pin chính | Test đạt / skip | Kết luận |
|---|---|---:|---|
| core | FastAPI 0.133.0, Starlette 1.3.1, AnyIO 4.14.2, Pydantic 2.5, YAML 6.0.1 | không cài được | Xung đột |
| web | Uvicorn 0.48.0, multipart 0.0.31 | 323 / 5 | Đạt |
| sqlalchemy | 2.0.38 | 43 / 0 | Đạt, SQLite |
| jwt | PyJWT 2.15.0, crypto 50.0.0 | 179 / 0 | Đạt |
| scheduler | 4.0.0a6 | 64 / 0 | Đạt theo wiring mặc định |
| socket | msgpack 1.2.1 | 19 / 0 | Đạt |
| grpc | grpcio/tools 1.60, protobuf 6.33.5 | không cài được | Xung đột |
| redis | 5.0 | 19 / 0 | Đạt unit; không đo Redis service thật |
| lmdb | 1.7.5 | 160 / 0 | Đạt |
| s3 | aioboto3 12 | 55 / 4 | Đạt unit; chưa S3 integration |
| mqtt | aiomqtt 2.1.0, paho 2.1 | 60 / 2 | Đạt unit; live riêng dùng resolver |
| mail | 5.1.2 | 18 / 0 | Đạt |
| modbus | 3.14 | 161 / 0 | Đạt các test hiện có |
| opcua | 2.0 | 76 / 0 | Đạt các test hiện có |

**F-LINUX-1 — core floor không tương thích.** `min-core-install.log` chứng minh
FastAPI 0.133.0 yêu cầu Pydantic >=2.7.0, mâu thuẫn pin sàn 2.5. Tổ hợp thử nghiệm
chỉ nâng Pydantic lên **2.7.0**, giữ core floor và thêm PyJWT 2.15.0/crypto 50.0.0/
Uvicorn 0.48.0 đã cài, pip check đạt và full suite 2.898/12/0. Xem
`core-compatible-constraints.txt`, `logs/core-compatible-*`, `xml/core-compatible.xml`.
Đề xuất chủ dự án rà nâng floor Pydantic; chưa sửa pyproject.

**F-LINUX-2 — gRPC floors không thể cùng cài.** grpcio-tools 1.60.0 đòi
protobuf >=4.21.6,<5.0.dev0, trái với floor protobuf 6.33.5 của XIME. Đây là bẫy
đã được tài liệu bàn giao dự báo, nay có bằng chứng trên Python 3.12.
Cho uv chọn nghiệm với `--resolution lowest-direct`, giữ protobuf 6.33.5 và
lower bounds grpcio/tools >=1.60: nghiệm thực thu là **grpcio/tools 1.72.1**,
pip check đạt, **286/286 test gRPC đạt**. Freeze có cả phiên bản test tools thấp hơn;
không coi đây là chứng minh mọi tổ hợp đều chạy được. Đề xuất rà lại floors gRPC;
chưa sửa metadata. Log và XML: `grpc-compatible-*`.

## 5. Chất lượng, advisory và artifact

- Ruff sạch; mypy 0 lỗi trên 250 file. Có note sẵn của mypy về thân hàm untyped,
  không phải lỗi mới. Không thêm ignore/cast vào sản phẩm.
- Docs import: 410 tên/49 file, 0 problem; 438 Python block kiểm cú pháp đạt.
- Register checker xem 5 class: 3 ca kiểm đạt, **A/B thiếu import nên bỏ qua**;
  không nói cả 5 đã thực thi. EN/VN mỗi bên 0/317 tên thiếu; sự xuất hiện của tên
  không tự chứng minh ví dụ nghiệp vụ đã chạy.
- Advisory floors: exit 0; raw 2 dòng APScheduler cùng ID `PYSEC-2026-282`, đã chấp
  nhận theo `MemoryDataStore/LocalEventBroker`. Không mở rộng kết luận sang external
  datastore/serializer. Raw resolver đầu exit 1 có APScheduler và pip 25.0.1 từ venv.
- Sau full suite, chỉ nâng **pip lên 26.2.1** trong venv tạm. Resolver audit cuối
  còn 2 dòng cùng advisory APScheduler, raw exit vẫn 1, không che bằng ignore.
  Freeze cuối/pip check lưu riêng. Không nâng thư viện runtime để làm audit xanh.
- Hai runtime wheel chỉ chứa wheel `[jwt]` cùng dependency và pip, audit bằng công
  cụ ở venv dev ngoài runtime. Cả resolver và JWT-floor đạt 15/15 ca và YAML redaction.
  Audit đầu cũng thấy pip cũ; sau cập nhật riêng pip, cả hai **audit exit 0**,
  smoke 15 ca chạy lại vẫn đạt. Không cài pip-audit/dev vào hai runtime này.
- Wheel có 256 entry, **251 file xime khớp byte source**; sdist kiểm mọi file nguồn
  khớp, không có `.claude`, tests_temp, AGENTS/CLAUDE, credential, cache hay báo cáo.
  Requires-Python >=3.12 và Requires-Dist được lưu trong `artifact-check.json`.
  Build/twine đạt; artifact SHA-256 cũng nằm trong JSON này.
- Version vẫn 0.8.3; wheel dựng từ candidate vừa nhận, không dùng gói PyPI thay thế.

## 6. Integration và giới hạn còn lại

Mosquitto **2.0.21** tải từ gói Debian, giải nén riêng trong workspace tạm cùng
thư viện cần thiết, không cài service hệ thống. Broker bind `127.0.0.1:58983`,
anonymous chỉ trong phạm vi test, persistence tắt. Hai test pub/sub và MQTT v5 RPC
thật đạt 2/2. Broker đã SIGTERM và exit 0; package hash/log/startup/teardown được giữ.
`mosquitto -h` trả exit 3 theo CLI nhưng in version đúng; đây là probe thông tin,
không phải lỗi broker hay kết quả test.

Không có Docker/Podman/MinIO sẵn. Đã thử binary từ endpoint MinIO chính thức;
HTTP 410, curl exit 22. Bốn S3 integration vẫn **CHƯA KIỂM**; cần một S3-compatible
test service riêng và bucket test để nghiệm thu tiếp. Không dùng bucket/service thật.

Không chạy Certbot/ACME/DNS/VPS thật. Harness lineage/hook không chứng minh các
thành phần này. Không sao chép/chạy 12 consumer hay khởi động DB/cert/nghiệp vụ live;
bằng chứng consumer Windows không được coi là Linux live pass.

## 7. Source sau đo, Git và bàn giao

`manifest-after` đạt; đối chiếu toàn payload với ổ D: **750/750 file khớp byte**,
không file source thừa/thiếu/đổi. Chỉ thêm báo cáo và harness dưới thư mục kết quả.

Git không bị chép từ D. HEAD, index và mọi file điều khiển Git gốc ngoài ref nội bộ
vẫn khớp snapshot trước chép; không add/commit/push/tag bằng lệnh của lượt test.
Kiểm đầu tiên đòi toàn `.git` byte-identical không đạt vì xuất hiện/xoay vòng
`refs/codex/turn-diffs` và loose objects. Kiểm lại tách đúng phạm vi xác nhận không
có thay đổi HEAD/index/refs thông thường. Giữ `source-final-first.json` và
`source-final.json`, không xóa ref/object nội bộ để làm số đo xanh.

Các app/broker/worker test đã dừng; không còn tiến trình dùng workspace test;
shared memory `xime-*` của lượt này đã được cleanup, không xóa shm của ứng dụng khác.
Venv/interpreter/key tạm còn ở `/tmp` để có thể tái hiện trước reboot, không đưa vào ZIP.

Chủ dự án tự ZIP cây Linux và chuyển về D. Xem `NOI-DUNG-GUI-VE.txt`; cần source
đã đo cộng báo cáo/log/XML/harness/freeze/JSON và artifact nếu muốn. Loại `.git`,
venv/cache, token, cấu hình riêng, private key và **`chuan-bi-2026-10-17/`** (backup).
Không tự chép ngược source lên ổ D. Hai đề xuất sửa minimum chờ chủ dự án duyệt.
