# Log lỗi bắt tay TLS native của gRPC

Tính năng opt-in tạo Python LogRecord cho lỗi TLS inbound xảy ra trước RPC.
Ghi file dùng [hệ logging đợt 3](logging.md), giữ grpcio chính thức, không cần proxy.

Parser nhận cả tiền tố trace `handshake_manager ...: error=` của grpcio 1.72.1
và `CallNextHandshakerLocked: error=` của bản mới. IP/port chỉ lấy từ đuôi metadata
của cùng record, không lấy từ reason hoặc record trước. Trace thành công không
bị tính thành lỗi parse. Pointer legacy có thể có `0x` trên Linux hoặc là hex
8/16 ký tự không có `0x` trên Windows. Sàn dependency vẫn là
grpcio/grpcio-tools 1.72.1.

Dùng đồng bộ mã nguồn framework và main ứng dụng mới. Main đã sửa cần API này;
wheel PyPI đã phát hành trước đợt này chưa có API đó.

```yaml
grpc:
  handshake_logging:
    enabled: false
    level: WARNING
    rate_limit_per_second: 20
    queue_capacity: 1024
    max_record_bytes: 65536
logging:
  console: {enabled: true, level: INFO}
  file:
    enabled: false
    level: DEBUG
    path: runtime/logs/application.jsonl
```

Hai công tắc độc lập: native bật/file tắt vẫn tạo sự kiện Python; file bật/native
tắt vẫn ghi log Python thông thường. Khai native ở `grpc.handshake_logging` cấp
gốc, dùng chung cho các listener trong process; chỉ listener TLS được đăng ký.

## Chuẩn bị trước khi import grpc

Trong main của từng process, đặt trước grpc, adapter và config ứng dụng:

```python
from xime.observability import prepare_grpc_handshake_logging

prepare_grpc_handshake_logging()  # đọc resources/application.yml sau chọn môi trường

from xime import Application  # noqa: E402
from xime.adapters.grpc import GrpcAdapter  # noqa: E402
import app.config as config  # noqa: E402

app = Application().add_config(config).use(GrpcAdapter())
if __name__ == "__main__":
    app.run_configured()
```

Để lời gọi ngoài main guard: worker spawn cũng phải chạy trước khi import grpc.
Nếu dùng `resources_dir` riêng, truyền đúng cùng thư mục cho helper/Application.
Test/embedding có thể truyền `runtime=RuntimeConfig(...)`. Tắt thì không import
grpc, không cấp pipe/thread/tracer. Bật sau khi đã import grpc thì fail rõ; cấu
hình bật nhưng quên gọi helper cũng bị chặn lúc app start.

Đây là ngoại lệ tường minh của quy tắc hạn chế việc ở mức module: phải chuẩn bị
native trước import/initialization. Kết nối và khởi tạo nghiệp vụ vẫn ở lifecycle.

## Vòng đời process và vòng đời ứng dụng

Pipe native và hai daemon thread sống đến khi **tiến trình OS thoát**. App stop/
start gỡ listener, drain có hạn và đóng file logger; giữ pipe native. Không thử
khôi phục stderr khi grpcio vẫn được nạp. Gọi chuẩn bị lại cùng cấu hình không
cấp thêm tài nguyên. Đổi native, kể cả bật/tắt, cần restart process. Hỗ trợ spawn;
không tái dùng collector bị kế thừa qua fork. Công tắc file có thể thay độc lập
qua các lần restart Application.

Supervisor giữ writer file chung. Worker thu native và PID của chính nó; supervisor
không nhận vơ trace của worker. Thăng primary/respawn vẫn dùng cơ chế log của cụm.

Marker drain nội bộ không ra console. Chờ reader và dispatcher tối đa 2 giây mỗi
bước. OS thu hồi FD/pipe khi process thoát; native destructor chạy muộn vẫn còn
đường stderr. Kill, timeout hoặc quá tải có thể mất phần đuôi; không đảm bảo giao
log bền vững.

## Nội dung sự kiện và stderr

Logger `xime.grpc.handshake`, event `grpc_tls_handshake_failed`. File JSON có UTC,
service, PID/process, level cùng `fields.server_id`, remote/local IP/port, cause,
grpcio_version, address_status. Thời gian là lúc quan sát sự kiện. Thiếu địa chỉ
hoặc listener không xác định thì ghi null/trạng thái thiếu; không mượn IP từ record
trước hoặc thread. Không tạo request ID giả hay identity đã xác thực. Chuẩn hóa
IPv4/IPv6; lỗi outbound của client không nhập vào luồng lỗi server.

Chỉ field/cause trong whitelist đi vào Python logging; không đưa raw buffer,
pointer native, credential hay nội dung SNI vào file chuẩn. Nếu native chỉ báo
read failed, giữ cause `handshake_read_failed`, không suy thành timeout chính xác.
SNI là tên đích, không phải IP nguồn.

Xime chỉ thêm tracer handshaker. Giữ các flag người vận hành đã khai; flag phủ
định xung đột bị chặn trước setup. Trace do Xime bật thường được giấu khỏi console;
trace do người vận hành bật vẫn hiện. Stderr khác, lỗi mặc định của thư viện và
continuation không nhận dạng được tiếp tục đi ra đầu gốc. Công tắc console chỉ
điều khiển LogRecord Python, không bao trùm stderr riêng của mọi thư viện native.

Console Python và cảnh báo dự phòng của Xime ghi thẳng về đầu gốc để tránh đệ quy.
Console riêng bàn giao qua `Application.use_logging_console(handler)`; handler
stderr được trỏ tạm về đầu gốc, giữ formatter/filter. Handler stderr chưa bàn giao
sẽ bị chặn khi gắn native logging. Passthrough giữ backpressure của stderr: đầu
nhận bên ngoài bị nghẽn vĩnh viễn vẫn có thể làm native writer chờ. Trần queue/rate áp dụng cho việc xử lý sự kiện đã chuẩn hóa.

## Thống kê và giới hạn

```python
from xime.observability import grpc_handshake_logging_stats

stats = grpc_handshake_logging_stats()
```

Counter cộng dồn theo process: received, emitted, rate_limited, queue_dropped,
truncated, unparsed, unregistered, inactive, logger_filtered, passthrough_errors,
read_errors, flush_timeouts. Emitted là LogRecord đã phát, chưa phải xác nhận ghi
đĩa. Tắt trả counter 0, không tự cài bộ thu. Mất log/lỗi parse có thêm event
`grpc_handshake_logging_summary`, tối đa mỗi 5 giây và khi gỡ app. Buffer/record
native và queue chuẩn hóa đều có trần. Rate limit không tắt chi phí tạo trace
của C-core trên các lần bắt tay mới. Level còn chịu lọc bởi logger/handler của
ứng dụng; Xime không âm thầm tăng level của logging do app sở hữu.

Thiết kế vòng đời process đã được kiểm trên Windows và Linux/Python 3.13.5,
gồm grpcio 1.72.1 và resolver. Windows/Python 3.12 cũng có phép thử sàn 1.72.1
với IP/port đối chiếu kết nối thật và file trên đĩa. Linux/Python 3.12 và VPS
thực vẫn cần bằng chứng riêng; mypy không thay phép đo runtime.
