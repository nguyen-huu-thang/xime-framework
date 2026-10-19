# Đợt 4: native gRPC logging và hướng dẫn Linux

**Đã nhận kết quả Linux/Python 3.13.5 và tiếp nhận ba bản vá; Windows/Python
3.12 và 3.14 đều đạt full suite trên runtime sau sửa pointer legacy.**
Đọc [đánh giá tiếp nhận và giới hạn](NGHIEM-THU-LOGGING.md).
Phần kết quả Windows và hướng dẫn Linux bên dưới là mốc trước chuyến Linux;
không dùng chúng thay cho báo cáo source cuối. Chưa triển khai VPS hoặc PyPI.

Chủ dự án đã duyệt thay đổi thiết kế sau lần G4a cũ: không khôi phục stderr khi
grpcio còn được nạp. Pipe/reader giữ đến lúc process OS thoát; app stop/start chỉ
gỡ listener, drain và đóng/mở lại logging Python. Lịch sử restore không đạt vẫn
được giữ trong mục cuối; nó không còn là tiêu chí dừng của thiết kế mới.

## Dùng trong mã nguồn hiện tại

Đọc [hướng dẫn đầy đủ](docs/vn/grpc-handshake-logging.md). Hai công tắc độc lập:

```yaml
grpc:
  handshake_logging:
    enabled: true
    level: WARNING
    rate_limit_per_second: 20
    queue_capacity: 1024
    max_record_bytes: 65536
logging:
  console: {enabled: true, level: INFO}
  file:
    enabled: true
    level: DEBUG
    path: runtime/logs/application.jsonl
```

`prepare_grpc_handshake_logging()` phải chạy trước import grpc/config. Đã thêm
lời gọi sớm ở main của CRM, Giao việc, Kho, Nhân sự, Sổ thu chi, Data và Notification.
Mẫu cấu hình vẫn **tắt**, YAML đang chạy không bị sửa. Main mới cần đi cùng
framework source mới; chưa có API này trong wheel PyPI đã phát hành trước đợt sửa. Data có đoạn mẫu riêng
`resources/grpc-handshake.yml.example`. Bốn app dọc chỉ là client gRPC nên không
cài bộ thu inbound ở main của chúng.

Đổi native cần restart process; không có bật/tắt nóng. Ghi file có công tắc riêng.
Sự kiện `grpc_tls_handshake_failed` đi qua Python logging và sink file G3, có
PID/service/listener, IP/port nguồn/đích và cause whitelist. Địa chỉ là peer TCP
server nhìn thấy; không tự khôi phục IP trước NAT/proxy. Không suy SNI thành IP.

## Kiểm chứng Windows

- Python 3.14.8, grpcio 1.81.0: Native pipe giữ qua hai lần start/stop Application;
  2 listener, 20 ca lỗi có đúng IP/port; RPC hợp lệ vẫn tới interceptor. Đã đo
  thêm grpcio 1.75.1 từ wheel giải nén cô lập: 20/20 sự kiện và 4 RPC hợp lệ,
  không cài đè Python chung.
- HTTP→TLS, thiếu client cert, TLS cũ, ngắt sớm, timeout; đa kết nối đồng thời,
  IPv6 thật, IPv4-mapped normalization, rate limit/queue đầy, custom console,
  cấu hình muộn/sai và marker drain chia từng byte đều có test.
- Cụm hai worker thật: đổi primary, respawn, file writer chung; PID/IP/port đúng
  worker, supervisor không nhận vơ. Kiểm cả tracer do Xime thêm và tracer đã có
  của người vận hành. Root/custom console và cảnh báo Xime đi về stderr gốc.
- Full snapshot: **2933 passed, 25 skipped, 1 deselected**, 320,13 giây;
  ca `_alive(current_pid)` tách riêng theo giới hạn Windows đã biết. Assertion
  riêng 1 passed; subprocess exit 0 trong wrapper bảo vệ SIGINT, nhưng console
  host vẫn báo interrupt. Không sửa source/test guard này để làm xanh.
- Sau snapshot có bổ sung guard console, fatal diagnostics, normalization và
  parser metadata; đã chạy bộ test mục tiêu trên source cuối. Bộ native source cuối **30 passed**. Xem mục 7.5 kế hoạch; không cộng
  các lượt thành ca độc lập.
- 7 consumer có sửa main: **2715 passed, 16 skipped**, không lỗi. Bốn app dọc
  không chạy lại full ở lượt này; kết quả G3 và hai guard dependency baseline
  Dental/Shop hoa được giữ riêng. Không ghi DB thật.
- Mypy Windows/Linux và Ruff được chạy; Linux mypy chỉ là kiểm tĩnh.

Artifact: `%TEMP%/xime-framework-g4-lifetime-20261018/`, gồm `framework-final.xml`,
`native-final.xml`, `grpc175-final.json`/stderr và `benchmark-final-source/benchmark.json`. Không stage raw log,
cert/key fixture hoặc wheel vào Git.

Mẫu đo cố định (5 lượt mỗi chế độ, file bật, 80 HTTP→TLS lỗi + 4 RPC mTLS hợp lệ,
2 listener, 2 vòng đời ứng dụng mỗi lượt; chạy bằng `benchmark.py`):

| Median | Native tắt | Native bật |
|---|---:|---:|
| Thời gian workload | 53,6 ms | 85,8 ms |
| CPU process gồm drain/ghi log | 125,0 ms | 156,25 ms |

Đây là loopback lỗi dày đặc; không suy thành phần trăm chi phí trên mọi RPC.
Trace phát ở handshake mới; rate limit chỉ giảm xử lý/ghi sự kiện chuẩn hóa,
không loại chi phí tạo trace C-core. Tính năng mặc định tắt và queue/buffer có trần.
Stderr gốc bị nghẽn vẫn giữ backpressure; kill/abort/timeout có thể mất phần đuôi.

## Phiên Linux kiểm tiếp đúng bản nguồn này

1. Chép source mới sang thư mục thử trên filesystem Linux, gồm `xime/`,
   `tests_temp/`, `docs/`, `pyproject.toml` và tài liệu này. Giữ `.git`, venv/wheel
   Windows và cache ở ngoài; ghi đè bản source cũ trong thư mục thử đã chọn.
   Không chạy pytest thẳng trên NTFS mount; không chạm service/DB VPS thật.
2. Python >=3.12, venv riêng:

```bash
python3 -m venv .venv-g4b
. .venv-g4b/bin/activate
python -m pip install -e '.[dev]'
python -c 'import sys,grpc,xime; print(sys.version); print(grpc.__version__); print(xime.__file__)'
python -m pytest -q tests_temp/grpc_handshake --junitxml=ket-qua-g4b/native.xml
python tests_temp/grpc_handshake/lifetime_probe.py --native --file --all-faults --rate 10000 --workdir ket-qua-g4b/lifetime > ket-qua-g4b/lifetime.json 2> ket-qua-g4b/lifetime.stderr
python -m pytest -q --junitxml=ket-qua-g4b/framework.xml
python tests_temp/grpc_handshake/benchmark.py --output-dir ket-qua-g4b/benchmark
```

3. Trong venv thứ hai trên Python 3.12, cài đồng thời `grpcio==1.72.1` và
   `grpcio-tools==1.72.1` với source `[dev]`, rồi chạy lại bộ native. Đây là sàn
   hiện khai; không nhận phép đo 1.75.1 trên Windows là exact-floor 1.72.1.
4. Kiểm JSON: mỗi tuple server_id/remote/local khớp `expected`, đúng PID, không
   có identity/request ID giả; `stats` không có drop/parse/flush lỗi ở tải thường.
   Test overload cố ý có drop/rate_limited và summary; không coi đó là hồi quy.
   Kiểm append/rotation/lock POSIX của G3 và stderr thường qua stop/start/exit.
5. Ghi báo cáo: OS/kernel, Python/OpenSSL/grpcio, source đang import, lệnh/exit
   code, full/native/IPv6/cluster, phần skip/chưa đo. Đóng ZIP kết quả cùng báo cáo
   để chủ dự án mang về Windows. Không phát hành/deploy trong lượt kiểm này.

## Lịch sử G4a cũ — phép thử restore

`probe.py`/`matrix.py` giữ nguyên vai trò đo restore theo thiết kế cũ. Windows
1.75.1/1.81.0 thu đúng IP nhưng mất native log sau restore; đối chứng không thu
vẫn có log. `matrix.py` có thể tiếp tục trả `not_ready` cho restore: kết quả đó
không phủ định thiết kế process-lifetime mới và không phải hướng dẫn bật sản phẩm.
