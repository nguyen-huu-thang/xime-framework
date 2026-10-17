# Nghiệm thu Linux và tiếp nhận kết quả về Windows

> **Trạng thái:** đã tiếp nhận ZIP và kiểm chứng bằng chứng ngày 2026-10-17;
> nhập bản nâng sàn đã duyệt. Còn mở SIGTERM app đơn và các cổng hạ tầng nêu dưới.
> **Thuộc bản:** sau `78c0fa8` / `e5a5b5c`; metadata vẫn 0.8.3, chưa phát hành.
> **Thay cái gì:** cập nhật các cổng Linux còn thiếu của Bước 7; đính chính việc
> coi thay SIGTERM bằng SIGINT trong harness là đã nghiệm thu shutdown.
> **Bị thay bởi:** chưa có; báo cáo thô Linux được giữ nguyên để đối chiếu.

## 1. Nguồn và tính toàn vẹn

Chủ dự án yêu cầu giải nén, đánh giá, nhập thay đổi phù hợp và commit Windows.
ZIP: `D:\temp\xime framework.zip`, SHA-256:

```text
60d388265d657e35a56b6122934332ff0a9ce90ff1bfa1b9b00022b27b8d6e6c
```

Đã giải nén riêng tại `D:\temp\xime-framework-linux-return-20261017\xime framework`,
không giải nén đè repo. ZIP có 2.802 entry, không path traversal/case collision
hoặc symlink entry. Các cache ngoài payload không được nhập.

- Bảng incoming Windows có 749 file, giữ nguyên hash
  `d665fe89092c0ab4132c7ceabf4525feb5a0d77cf145bd14c0b490b48340a0d1`.
- So từng file incoming: Windows vẫn khớp đầu vào; Linux chỉ khác `pyproject.toml`.
- Manifest sau nâng sàn: **749/749 khớp** cây source trả về.
- Manifest kết quả: **735/735 file khớp**; cả manifest được lưu cùng kết quả.
- Bản `pyproject.before.toml` khớp byte Windows; `pyproject.after.toml` khớp byte
  source Linux. Bản mới có SHA-256
  `e50faccb2c190ee3ae221e61b8c3ff584dcd10fdbd7f738a144daa1347213ed2`.
- Wheel Linux sau vá: 251 file `xime/` khớp byte source, METADATA có đúng sàn mới.

Bằng chứng thô được nhập nguyên byte vào
[`ket-qua-kiem-thu-linux/20261017T144535Z`](../../../ket-qua-kiem-thu-linux/20261017T144535Z/).
Đọc [báo cáo Linux](../../../ket-qua-kiem-thu-linux/20261017T144535Z/BAO-CAO.md),
mục 8–9 để phân biệt trước/sau nâng sàn và checkpoint Git Linux. Không nhập `.git`
Linux, không cherry-pick checkpoint so với HEAD tháng 9. Hai file pycache không
nằm trong bảng kết quả bị bỏ lại. `.gitattributes` giữ byte gốc của bằng chứng để
Git không đổi LF/CRLF rồi làm hỏng checksum. Kiểm whitespace thông thường vẫn áp
dụng cho source/tài liệu; output thô trong vùng checksum giữ cả khoảng trắng/CRLF
ban đầu thay vì sửa log rồi làm lệch bằng chứng.

`KIEM-THU-LINUX.sha256` là **đầu vào lịch sử**, không sinh lại để che thay đổi.
Sau tiếp nhận, pyproject, tài liệu và thuộc tính Git Windows đã đổi có chủ đích;
không dùng bảng incoming để khẳng định toàn cây Windows hiện tại còn nguyên.
Receipt: [`TIEP-NHAN-WINDOWS.json`](../../../ket-qua-kiem-thu-linux/TIEP-NHAN-WINDOWS.json).

## 2. Kết quả thực đo đủ cơ sở chấp nhận

Linux: Debian 13.7/kernel 6.12.111, ext4, user UID 1000; CPython 3.12.15,
OpenSSL 3.5.9; uvloop 0.23.0, pytest 9.1.1, pytest-asyncio 1.4.0.
Đây là thông tin của lần chạy, không phải yêu cầu hệ thống mới.

Windows đã đọc trực tiếp XML, đếm từng testcase/failure/error/skip và đối chiếu
log/exit/command JSON, không chỉ chép số ở báo cáo:

| Full suite Linux | Passed | Skipped | Failed/error | Collected | Thời gian XML |
|---|---:|---:|---:|---:|---:|
| Resolver, loop pytest mặc định | 2.898 | 12 | 0 | 2.910 | 237,872 s |
| Resolver, loop pytest uvloop | 2.898 | 12 | 0 | 2.910 | 234,759 s |
| Core tương thích + sàn bảo mật, trước sửa metadata | 2.898 | 12 | 0 | 2.910 | 270,551 s |
| Sau sửa, ghim đồng thời core và gRPC mới | 2.898 | 12 | 0 | 2.910 | 287,078 s |

Không deselect `_alive(current_pid)`; không giảm collection. Các XML có hash và
timestamp khác nhau, bốn lần chạy cùng bộ ca không được cộng thành số test độc lập.
12 skip mỗi lượt: 6 ca Windows-only, 2 MQTT chưa có broker lúc collection,
4 S3 chưa có endpoint. MQTT được kiểm riêng sau đó, không sửa số skip của full.

Các bằng chứng bổ sung:

- Đối chứng loop in `_UnixSelectorEventLoop` / `uvloop.Loop`; cố ý mong uvloop mà
  không nạp plugin cho exit 1. Worker thật phản hồi loop và PID; hai worker dùng
  chung listener đều được quan sát. HTTP, WS, HTTPS, WSS và Unix RPC chạy thật.
- POSIX: quyền LMDB/local storage, chmod key 000 bằng user thường, `/dev/shm`,
  Unix socket/peer PID/UID và socket inheritance có ca thực thi.
- TLS RSA/ECDSA × TLS 1.2/1.3 × default/explicit, reload/mTLS/ACK/management đã chạy
  trong full suite. Probe lineage dùng symlink tương đối, đổi cert trước key,
  nhận 503 lúc mismatch/quyền/link gãy, giữ context cũ rồi watcher tự hồi phục.
  `runtime-probes-v2` 3/3, `unix-peercred-v3` 1/1, `lineage-watcher-v3` 1/1.
- Mosquitto 2.0.21 riêng trên loopback: **2/2** test MQTT v5 pub/sub/RPC đạt,
  broker đã dừng. Không phải bằng chứng MQTT floor kết hợp broker live: lượt live
  dùng resolver; floor aiomqtt được kiểm unit riêng.
- 12 nhóm minimum ban đầu cài/chạy được; core và gRPC xung đột đã được sửa ở mục 3.
  S3/Redis minimum unit pass không chứng minh đã kết nối S3/Redis service thật.
- Wheel `[jwt]` trắng: 15/15 ca ở mỗi tập resolver/JWT-floor, YAML redaction đạt;
  audit hai runtime sạch sau khi nâng riêng pip trong venv. Không gọi audit trước
  nâng pip là sạch. Resolver đầy đủ vẫn còn hai dòng cùng ID APScheduler.

## 3. Thay đổi đã nhập

Chỉ chép `pyproject.toml` từ payload Linux, kiểm cấu trúc TOML để chắc không đổi
requirement ngoài ba dòng dưới. Toàn bộ 251 file Python/type marker dưới `xime/`
và các test framework giữ nguyên.

| Requirement | Trước | Sau | Căn cứ |
|---|---|---|---|
| Pydantic | >=2.5 | >=2.7.0 | FastAPI floor 0.133.0 cần >=2.7.0 |
| grpcio | >=1.60 | >=1.72.1 | Cặp runtime/compiler thấp đã đo cùng protobuf 6.33.5 |
| grpcio-tools | >=1.60 | >=1.72.1 | 1.60 đòi protobuf <5, trái floor Xime >=6.33.5 |

Giữ `protobuf>=6.33.5`, các sàn bảo mật khác và version 0.8.3. Comment cũ nói sàn
chưa đo được đã được thay bằng phạm vi phép đo Linux/Python 3.12. Không tuyên bố
wheel exact-floor cũ chạy Python 3.14/Windows; resolver được chọn bản mới hỗ trợ
interpreter đó. Bản Linux đã được owner duyệt và full suite xác nhận tổ hợp mới.

Tài liệu/changelog/backlog được cập nhật theo kết quả này. Bằng chứng thô giữ cả
lỗi harness và đối chứng đỏ. Artifact trước sửa ở `artifacts/`; artifact đã sửa
ở `artifacts-floor-fix/`, cùng tên 0.8.3 nhưng hash khác; không đánh đồng chúng.

## 4. Điểm không chấp nhận kết luận “đã sạch”: SIGTERM

**F-LINUX-3 — P2 cần điều tra lifecycle/shutdown của app đơn.**
`xml/runtime-probes.xml` và `logs/runtime-probes.log` ghi app HTTP/WS/Unix để lại
`default.sock` sau SIGTERM. Bản harness sau dùng SIGINT cho app đơn và đạt. Việc
đổi tín hiệu chỉ chứng minh đường SIGINT; chưa loại được lỗi teardown SIGTERM.
Kết luận “lỗi harness” cho ca này trong báo cáo Linux chưa đủ cơ sở. Lỗi không
thấy worker thứ hai khi bắn 120 request quá sớm có đối chứng chờ readiness và
được phân loại riêng; không gộp hai failure làm một.

Đọc source hiện tại phát hiện trình tự đáng lo: `WebAdapter.serve()` đặt cleanup
ngoài `with self._server.capture_signals()`. Uvicorn khôi phục handler rồi phát
lại tín hiệu khi ra khỏi context; ở bản Uvicorn tham chiếu, shutdown nằm trong
context. [Source chính thức Uvicorn](https://github.com/Kludex/uvicorn/blob/main/uvicorn/server.py).
Probe điều khiển thứ tự trên Windows ghi:

```text
enter capture -> main loop finished -> replay signal -> web shutdown
```

Probe chỉ chứng minh thứ tự gọi, **không thay phép đo SIGTERM native Linux**.
Với SIGTERM mặc định có thể thoát trước finally ở ngoài; cần kiểm cả stop adapter,
`PreDestroy`, socket và worker, không chỉ đổi mã thoát hay xóa socket trong harness.
Chưa áp bản vá signal handler khi chưa có phép tái hiện Linux kiểm được các nhánh.

Lượt Linux tiếp theo cần giữ SIGTERM của probe gốc, chạy app đơn có web+Unix và
hook `PreDestroy` ghi marker; đợi ready, gửi một SIGTERM, đo marker/socket/port/
tiến trình còn lại. Ghi riêng một SIGINT đối chứng và cụm nhiều worker SIGTERM.
Nếu sửa, canh cleanup đúng một lần cho mọi adapter trước khi phát lại tín hiệu,
không chỉ di chuyển shutdown web rồi mặc định lifecycle ứng dụng đã hoàn tất.
Giữ nguồn/checksum và log trước/sau, không dùng thao tác xóa của harness làm bằng
chứng sản phẩm tự cleanup. Đây còn là điều kiện trước triển khai systemd.

## 5. Các cổng còn mở

| Cổng | Trạng thái chính xác |
|---|---|
| SIGTERM app đơn | Chưa nghiệm thu; failure gốc và thứ tự gọi cần điều tra tiếp |
| S3/MinIO thật | Chưa kiểm; tải binary MinIO HTTP 410; 4 ca còn skip, unit vẫn đạt |
| Certbot/ACME/DNS/VPS thật | Chưa kiểm; lineage/hook mô phỏng không thay hạ tầng này |
| Consumer/DB/cert/nghiệp vụ live trên Linux | Chưa kiểm; không suy từ 12 suite/config/DI trên Windows |
| APScheduler PYSEC-2026-282 | Ngoại lệ cũ có điều kiện MemoryDataStore/LocalEventBroker; không tuyên bố external serializer an toàn |

Không thêm ngoại lệ advisory, không xóa skip hoặc sửa báo cáo thô để đóng cổng.
Lượt tiếp nhận này không khởi động service Base/consumer hay thay DB/cert thật.

## 6. Kiểm lại trên Windows

CPython 3.14, tập resolver sẵn có: Pydantic 2.14.1, grpcio/grpcio-tools 1.84.0.
251 file runtime không đổi và các thư viện này đã cao hơn sàn mới; không ép cài
wheel cũ chưa hỗ trợ 3.14, không chạy lại full Windows chỉ để lặp bằng chứng.

- gRPC server: **172 passed**; config: **95 passed**, chạy riêng để tránh đụng
  package fixture `sample` khi ghép tùy ý nhiều thư mục.
- Ruff sạch; mypy **0 lỗi/250 file**; pip check đạt. Docs: 410 import/49 file,
  438 Python block đạt. Audit floor mới exit 0, chỉ ngoại lệ APScheduler cũ.
- Build wheel/sdist và twine đạt; kiểm METADATA ba floor, nội dung artifact và
  byte của 251 file runtime. Harness kiểm artifact ban đầu thiếu `.gitignore`
  trong allowlist sdist; đã sửa allowlist đúng một tên và kiểm byte nguồn, không
  thay quy tắc đóng gói sản phẩm để đạt.
- Cài wheel mới `[grpc]` vào venv trắng, import bằng `python -I` ngoài checkout
  và pip check; kết quả cụ thể ở bằng chứng Windows đi kèm.

Bằng chứng Windows được lưu tại
[`windows-tiep-nhan`](../../../ket-qua-kiem-thu-linux/windows-tiep-nhan/).
Các artifact/venv/cache thử Windows ở `D:\temp\xime-framework-windows-validation-20261017`;
không đưa venv/key vào Git. Không push/tag hoặc phát hành trong lượt này.
