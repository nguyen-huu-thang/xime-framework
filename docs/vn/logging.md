# Log terminal và ghi file có xoay vòng

Xime dùng Python `logging`, không cần thư viện ngoài. Khai trong `application.yml`
hiệu lực và khởi động lại ứng dụng để áp dụng cấu hình.

```yaml
logging:
  enabled: true
  level: INFO
  service_name: example
  console:
    enabled: true
    level: INFO
  file:
    enabled: false  # đổi true khi muốn tạo writer ghi file
    level: DEBUG
    path: runtime/logs/application.jsonl
    format: json
    max_bytes: 10485760
    backup_count: 5
    queue_capacity: 4096
    max_record_bytes: 65536
    shutdown_timeout: 5
```

Khi bật file, DEBUG chỉ vào file; INFO trở lên vào cả hai. Mỗi nơi kế thừa
`logging.level` nếu không khai mức riêng. `logging.format/datefmt` cũ tiếp tục
quyết định formatter console mặc định. Logger con tự đặt level hoặc
`propagate=False` vẫn theo hành vi Python; Xime không lấy lại được record đã bị
logger con lọc trước khi tới root.

`logging.enabled: false` nhường cấu hình cho ứng dụng; khai cùng
`file.enabled: true` là mâu thuẫn và bị chặn. File mặc định tắt: không tạo thư mục,
file, khóa, queue hoặc thread writer. Có thể tắt console và chỉ bật file. Tắt cả
hai thì NullHandler ngăn Python in lỗi qua lastResort.

## Sở hữu file và giới hạn lưu trữ

Đường dẫn tính từ thư mục chạy Python. Mỗi ứng dụng chỉ có một
RotatingFileHandler ghi append. Với cụm, supervisor cấp queue bằng spawn context
của Xime và giữ writer qua lần thăng primary/respawn. Tiến trình đơn dùng queue
có trần trong process và QueueListener. I/O file không chạy trong task request.

File phụ `<path>.lock` giữ khóa OS. Instance Xime độc lập thứ hai cùng đường dẫn
chuẩn hóa sẽ bị chặn lúc startup. Mỗi service dùng path riêng; không xóa file
khóa khi writer đang chạy. Khóa được trả khi dừng/thoát, file phụ có thể còn lại.

Khởi động lại ghi tiếp lịch sử. Xoay giữ file đang ghi và `.1` đến
`.backup_count`; chỉ tác động đúng family đã cấu hình. Trần size có sai số do
UTF-8/newline và một record lớn: có thể vượt max_bytes tối đa một record đã giới
hạn cộng newline. Không xoay theo tuổi file; không chạy thêm logrotate cùng sở hữu
family này. backup_count từ 1–100; queue từ 1–100000; record từ 1024–1048576 byte;
timeout lớn hơn 0 và tối đa 30 giây; max_bytes phải dương. JSON mỗi dòng là một
object hợp lệ; text cũng escape newline nằm bên trong record.

## Context, che bí mật và xử lý lỗi

File có timestamp ISO-8601 UTC, service, PID/process, logger, level, message và
exception khi có. service_name trung lập với hệ định danh; bỏ trống thì lấy
package của main hoặc `application` nếu chạy script trực tiếp. Request/correlation
ID lấy từ request_context hoặc record tại producer trước khi qua queue. `extra`
khác được làm sạch vào `fields`. Job nền không phải tạo request ID giả.

Che tên field nhạy cảm, chuỗi gán credential phổ biến, Bearer/Basic, chuỗi giống
JWT, mật khẩu URL và PEM private key trong file. Giới hạn chiều sâu/số phần tử
extra; record quá lớn bỏ extra và rút message/exception, có `truncated: true`.
Không thể tự nhận diện mọi bí mật nằm trong văn xuôi. Console vẫn dùng formatter
và chính sách che hiện có. Tránh ghi bí mật ngay tại nơi gọi logger.

Queue không chờ khi đầy: bỏ record, tăng bộ đếm của producer và cảnh báo trực
tiếp stderr, tối đa một lần mỗi 5 giây. Lỗi ghi/xoay runtime cũng dùng đường dự
phòng này, không in payload lỗi. Path/lock không mở được thì fail-fast, không in
giá trị path cấu hình. Đường dự phòng không gọi ngược logging; debug nội bộ của
multiprocessing cũng không đưa vào file queue để tránh đệ quy/deadlock.

Dừng ứng dụng gỡ producer rồi drain có hạn: tối đa một shutdown_timeout cho
listener và thêm một khoảng cho feeder multiprocessing. Nếu I/O treo, thread giữ
khóa tới khi thật sự thoát. Queue không bền vững: quá tải, timeout hoặc kill có
thể mất phần đuôi. Kill đúng lúc worker đang ghi queue còn có thể làm hỏng IPC —
giới hạn của Python. `Application.run()` quản lý tín hiệu của toàn worker:
SIGINT/SIGTERM yêu cầu dừng và dọn mọi adapter, `PreDestroy`, rồi logger. Không
chỉ chờ riêng web server tắt. Tín hiệu lặp không hủy cleanup lần hai; supervisor
vẫn có deadline và kill dự phòng. `start()`/`stop()` khi nhúng không chiếm signal
handler của chương trình chủ. POSIX được kiểm riêng; `terminate()` của Windows
là kill cưỡng bức, không có cùng bảo đảm cleanup.

## Ứng dụng tự cấu hình console

File tắt thì root có handler sẵn vẫn được giữ nguyên. Nếu bật file khi app đang
sở hữu root, Xime báo cách bàn giao thay vì âm thầm đổi quyền sở hữu:

```python
import logging
from xime import Application

console = logging.StreamHandler()
console.setFormatter(MyJsonFormatter())
app = Application().use_logging_console(console)
# đăng ký adapter rồi app.run() / app.run_configured()
```

Có thể bàn giao handler đã gắn vào root. Xime giữ formatter/filter, áp level/công
tắc YAML và trả level/vị trí handler ban đầu lúc stop. Không khai tường minh mức
console/root trong YAML thì console riêng giữ mức hiệu lực cũ. Root có handler
khác sẽ báo lỗi sở hữu rõ ràng. Không gọi dictConfig lần nữa sau bootstrap.

File này nhận Python LogRecord. Log TLS handshake native của gRPC C-core dùng [bộ thu opt-in riêng](grpc-handshake-logging.md);
bật file chưa tự tạo sự kiện IP nguồn của những lần bắt tay thất bại.

Tham chiếu: [Python logging cookbook](https://docs.python.org/3.14/howto/logging-cookbook.html#logging-to-a-single-file-from-multiple-processes),
[QueueHandler/QueueListener](https://docs.python.org/3.14/library/logging.handlers.html#queuehandler),
[giới hạn queue multiprocessing](https://docs.python.org/3.14/library/multiprocessing.html#pipes-and-queues).
