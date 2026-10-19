# Kế hoạch reload TLS web và cổng management theo primary

> **Ngày:** 2026-10-11.
> **Trạng thái cập nhật 2026-10-19:** implementation ở commit `2ad5274` nằm trong `0.8.4`, đã phát hành PyPI. Nghiệm thu Windows và Linux hoàn tất; VPS/ACME thật chưa kiểm chứng.
> **Yêu cầu gốc:** [yeu-cau-reload-tls-web.md](yeu-cau-reload-tls-web.md).
> **Phạm vi:** Repo framework. Không sửa cấu hình hay code của Data Service, các Python consumer hoặc VPS; không commit/push/phát hành PyPI trong công việc này.

## Trạng thái triển khai

- Đã thêm cấu hình `webserver`, alias tương thích `server`, listener management singleton theo primary, TLS context reload, watcher, hàm Python, HTTP API nội bộ và health public/management theo phạm vi đã chốt.
- Đã tái hiện và vá lỗi worker duy nhất restart bị mất primary; giữ chống domino và không chạy lại `run_once` đã được supervisor xác nhận.
- Regression Windows trước lượt rà lại bên dưới: **2763 passed, 25 skipped, 1 deselected**. Test duy nhất bị loại là `tests_temp/link/test_cleanup.py::TestAlive::test_this_process_is_alive`: trên Python 3.14.8/Windows, `os.kill(current_pid, 0)` làm pytest nhận `KeyboardInterrupt` muộn. Nhóm link còn lại đạt **111 passed, 4 skipped**; test PID này được thử riêng nhưng pytest process vẫn kết thúc bằng interrupt.
- TLS thật chạy trên Windows, Python 3.14.8, Uvicorn 0.47.0, OpenSSL 3.5.9, asyncio. RUFF sạch; mypy còn **49 lỗi**, bằng baseline đã ghi trước triển khai.
- Management listener loopback đã bind và trả health thật trên cả IPv4 (`127.0.0.1`) lẫn IPv6 (`::1`) của máy này.
- TLS mặc định/cipher: không đổi chính sách cipher. TLS 1.2 đã kiểm thành công với cipher tường minh; phát hiện tương thích cipher mặc định Uvicorn 0.47.0 ở mục 3.4 vẫn phải được giữ rõ.
- Linux/uvloop đã được nghiệm thu ở candidate sau này. DNS/ACME/Certbot thật trên VPS vẫn chưa được đo. Không sửa Data Service, consumer hay cấu hình triển khai.

### Rà lại và vá kết quả reload ngày 2026-10-11

- Đã vá `TlsReloadResult.succeeded`: chỉ thành công khi outcome tổng thể hợp lệ, có ít nhất một worker, không thiếu ACK và mọi worker thành công. Listener không tồn tại hoặc gọi trước startup trả `failed` và HTTP 503; không còn HTTP 200 do `all([])`.
- Đã vá giải mã ACK: từ chối status không biết, khung thiếu/thừa byte và dữ liệu không phải ASCII. ACK hỏng không còn bị coi là `reloaded`. Kết quả cụm rỗng cũng trả `failed`, không phải `unchanged`.
- Thêm `tests_temp/web/test_tls_reload_results.py`: 37 ca về kết quả Python/HTTP, listener không có TLS hoặc đã dừng, lỗi nạp cert, ACK thiếu/hỏng, partial và timeout. Trước vá: **15 failed, 22 passed**; sau vá: **37 passed** trên cả hai Python hiện có.
- Regression toàn bộ sau vá mã thực thi: **2801 passed, 25 skipped, 1 deselected**, 260,02 giây, Windows/Python 3.14.8/Uvicorn 0.47.0/OpenSSL 3.5.9/asyncio. Lệnh: `python -m pytest -q -p no:cacheprovider --deselect=tests_temp/link/test_cleanup.py::TestAlive::test_this_process_is_alive`.
- Sau regression, chỉ mở rộng fixture TLS từ RSA sang cả RSA/ECDSA P-256, không đổi mã thực thi. Hai file test TLS chạy lại đạt **42 passed** trên Python 3.14.8/OpenSSL 3.5.9 và Python 3.14.2/OpenSSL 3.0.18 (đều Uvicorn 0.47.0, Windows/asyncio). Xác nhận A -> B -> C, keep-alive cũ, SNI/no-SNI, cặp cert/key sai, thử lại và watcher với cả hai loại khóa.
- Lệnh TLS: `python -m pytest -q -p no:cacheprovider tests_temp/web/test_tls_reload.py tests_temp/web/test_tls_reload_results.py`; chạy thêm cùng lệnh qua `py -3.14` để kiểm Python 3.14.2.
- Ruff sạch trên mã/test của lượt vá; mypy kiểm riêng `_tls_reload.py` với cấu hình mục tiêu Python 3.12 đạt. Đây không phải test runtime Python 3.12; không thay kết luận về nợ mypy toàn repo hoặc giới hạn Linux/uvloop/VPS phía trên.
- **Tại thời điểm ghi kết quả ngày 2026-10-11**, các chỉnh sửa nguồn/test trong mục này chưa commit, phát hành hoặc cập nhật runtime framework trong gói build của consumer. Chúng được commit sau đó thành `2ad5274`; trạng thái phát hành PyPI được cập nhật ở đầu tài liệu.
- Đã chạy thêm 12 repo Python đã chọn cho VPS: 6469 test consumer đạt, 8 assertion frontend theo .env cũ chưa di trú, 8 skipped; 12 tiến trình consumer qua 108 phép kiểm startup/TLS thật. Bản framework trong build vẫn cũ, YAML server chưa bật reload và installer đang tính sai ROOT. Xem [báo cáo consumer và giới hạn](../bao-cao-van-de-tu-repo-ngoai/2026-10-11-kiem-tra-vps-consumers-reload-tls.md).
- Sau báo cáo consumer, chủ dự án xóa framework cũ và yêu cầu copy tối giản. Đã cập nhật `build/base/runtime/xime-framework` bằng 240 file runtime + manifest pip riêng, bỏ CLI/testing/dev/docs/cache. Wheel từ bản lọc tạo/cài được, 12 backend import được, 42 test TLS trực tiếp trên wheel đạt; code runtime/checksum khớp nguồn đã vá. YAML server và installer chưa thay. Không phát hành PyPI hoặc commit.

## 1. Quyết định cấu hình

**Giữ nguyên schema và cách khai `process`/`processes`.** Người dùng không phải thêm management vào các khối đó, không phải đổi host/port nghiệp vụ hoặc đổi `primary`, `count`, `shared`.

Thiết lập web chung chuyển từ `server` sang `webserver`. Management có một địa chỉ chung và chạy tại worker đang giữ vai primary:

```yaml
webserver:
  ssl:
    certfile: /path/to/fullchain.pem
    keyfile: /path/to/privkey.pem
    reload:
      mode: both
      interval_seconds: 300

  management:
    enabled: true
    host: 127.0.0.1
    port: <port_management>

# Phần này giữ nguyên cách khai hiện tại của ứng dụng.
processes:
  main:
    primary: true
    web:
      default:
        host: 0.0.0.0
        port: <port_public>
        shared: true
  worker:
    web:
      default:
        host: 0.0.0.0
        port: <port_public>
        shared: true
```

`<port_management>` và `<port_public>` là chỗ thay bằng số port của ứng dụng, không phải giá trị YAML chạy được. Ví dụ trên minh họa nhiều worker; ứng dụng một tiến trình tiếp tục dùng `process` như hiện tại.

| Cấu hình | Ý nghĩa |
|---|---|
| `webserver.ssl` | TLS mặc định cho các web listener không khai `ssl` riêng |
| `webserver.ssl.reload.mode` | `off` mặc định; `watch`, `api`, `both` chọn các đường kích hoạt |
| `webserver.ssl.reload.interval_seconds` | Mặc định 300 giây (5 phút), phải lớn hơn 0; chỉ dùng cho watcher, không làm chậm API/hàm trực tiếp |
| `webserver.management.enabled` | Mặc định false; bật listener quản trị và health chi tiết |
| `webserver.management.host` | Mặc định `127.0.0.1`; chỉ nhận địa chỉ IP loopback, gồm IPv6 nếu môi trường hỗ trợ |
| `webserver.management.port` | Bắt buộc khi management bật; kiểm kiểu và miền giá trị TCP như topology hiện tại |

- `watch` không cần management. `api`/`both` cần management bật và có địa chỉ hợp lệ; thiếu thì báo lỗi startup.
- Hàm lập trình viên gọi trực tiếp vẫn dùng được với `mode: off` và management tắt, khi listener TLS đang hoạt động.
- Ô `process.web.<id>.ssl` / `processes.<p>.web.<id>.ssl` hiện có giữ nguyên ý nghĩa: khai riêng thì dùng nguyên khối riêng; `ssl: {}` tắt TLS; không khai thì kế thừa khối chung. Không tự thêm cơ chế merge từng trường.
- Dùng `server` cũ làm alias tương thích trong lượt nâng này. Nếu đồng thời khai `server` và `webserver`, báo lỗi rõ để tránh hai nguồn cấu hình. Ví dụ và tài liệu mới dùng `webserver`.
- Chỉ đổi tên khối cấu hình web. Tên môi trường `server` trong `environments.server`, vừa được bổ sung ở công việc khác, giữ nguyên.

## 2. Kiến trúc triển khai

### 2.1. Listener management dùng singleton hiện có

Web adapter tự cung cấp một thành phần management nội bộ với `scaling="singleton"`. Nó dùng FastAPI/Uvicorn của web adapter, không yêu cầu ứng dụng đăng ký gRPC, SocketAdapter, controller quản trị hoặc một loại adapter công khai mới.

Trước khi kiểm topology và sinh worker:

1. Đọc RuntimeConfig hiệu lực đã được loader chọn, gồm lớp môi trường hiện hành.
2. Web adapter phân giải `webserver.management` và tạo mô tả listener quản trị.
3. Đăng ký thành phần singleton nội bộ và bổ sung endpoint quản trị vào bản topology dẫn xuất ở primary ban đầu. Với `process`, bổ sung vào tiến trình duy nhất.
4. Chạy lại đầy đủ các phép kiểm địa chỉ, trùng port, adapter và singleton trên topology dẫn xuất.

Đây là chuẩn hóa trong bộ nhớ, **không ghi thêm management vào YAML và không sửa khối `processes` của ứng dụng**. Định danh nội bộ phải được reserve; nếu trùng listener do ứng dụng khai thì báo lỗi, không ghi đè. Lỗi cấu hình phải trỏ về `webserver.management`, không chỉ ra một đường dẫn tổng hợp không tồn tại trong file.

Bootstrap core chỉ điều phối mô tả adapter/endpoint chung; phần đọc cấu hình, dựng HTTP và TLS thuộc web adapter. Tích hợp qua hợp đồng nội bộ tổng quát, không đưa xử lý HTTP/TLS hoặc khái niệm Data/Trust vào core.

`prepare_worker()` đã giữ singleton trong mọi worker và dùng ô cấu hình của primary ban đầu cho worker phụ. `_start_adapters()` chỉ start singleton tại primary; `_accept_promotion()` gọi `_start_standby_adapters()` khi đổi vai. Management tận dụng đúng đường này.

- Primary hiện hành tự bind management; endpoint quản trị nội bộ có `shared: false`.
- Worker phụ có thành phần quản trị ở standby, chưa bind.
- Primary chết: socket của nó được giải phóng; worker được thăng cấp bind lại cùng host/port. Có khoảng gián đoạn ngắn của cổng quản trị, không restart các listener nghiệp vụ đang chạy.
- Worker cũ được dựng lại với `SharedHandle.primary=false` thì không bind management.
- Management chạy HTTP loopback với TLS tắt tường minh, không kế thừa cert public.
- Listener chỉ có route quản trị; không tự đưa controller nghiệp vụ, Swagger hoặc middleware xác thực nghiệp vụ vào đó.
- Xác thực/phân quyền management được chủ dự án để sang phiên bản sau. Bản này vẫn phải giữ đúng phạm vi bind loopback.

### 2.2. Bộ TLS riêng cho từng listener trong từng worker

Dùng API công khai `ssl_context_factory` của Uvicorn >=0.47.0 để dựng context ban đầu và gắn cơ chế chọn context cho handshake mới.

- Mỗi listener có bộ quản lý TLS thuộc đúng instance Application, không có con trỏ runtime toàn cục có thể trỏ nhầm ứng dụng.
- Dựng candidate SSLContext từ cert/key tại đường dẫn cấu hình, giữ nguyên các thiết lập TLS hiện có, gồm password, cipher, CA và chế độ client certificate nếu được khai.
- Candidate nạp thành công và bộ file ổn định thì mới chuyển tham chiếu context đang có hiệu lực.
- Callback chọn context không đọc file, gọi mạng hoặc dựng context. Context được chọn phải giữ nhất quán trong suốt handshake, kể cả TLS 1.3 HelloRetryRequest.
- Đường có SNI và không có SNI đều phải lấy đúng phiên bản đang có hiệu lực.
- Không nạp đè cert/key vào context đang phục vụ. Candidate lỗi bị bỏ, context cũ tiếp tục dùng.
- Kết nối cũ giữ context của nó và tiếp tục HTTPS/WebSocket/stream bình thường. Không bootstrap lại DI, scheduler, gRPC hoặc ứng dụng.
- Dùng trực tiếp file cấu hình, kể cả symlink của Certbot; không copy cert/key sang kho của framework và không làm ACME.
- File cấu hình là nguồn cert/key. Cache phục vụ TLS gồm SSLContext và dấu nhận diện phiên bản đã áp dụng, giữ trong RAM riêng của từng worker/listener; không lưu cert/private key, dấu đã áp dụng hoặc khóa chống reload trùng vào LMDB/RefData.
- Worker mới hoặc vừa restart luôn đọc file và dựng context khi startup, không dựa vào dấu đã nạp của worker khác hay lần chạy trước. Một dấu dùng chung “đã nạp B” không chứng minh mọi worker đều có context B.
- So cả chứng chỉ/fullchain và key: chứng chỉ có thể đổi dù private key giữ nguyên. Không cần lấy private key ngược ra từ SSLContext; dấu nhận diện được ghi cùng lần nạp thành công.

### 2.3. Một đường reload và chống trùng

API công khai đã thống nhất:

```python
from xime.adapters.web import reload_tls

result = await reload_tls(app, server_id="default")
```

Hàm chờ kết quả cuối cùng của các worker đang phục vụ listener được chọn, không chỉ trả lời đã gửi thông báo. Một tiến trình dùng cùng hành vi, với một đích xử lý.

Watcher, API HTTP và hàm trực tiếp dùng chung bộ nạp cục bộ:

1. Giữ khóa theo worker/listener, bao trọn bước đọc, kiểm tra, dựng candidate và chuyển context.
2. Đọc lại vị trí symlink và dấu nhận diện nội dung cert/key; kiểm tra bộ file trước/sau khi nạp. Nếu file đang đổi hoặc cặp chưa hợp lệ, giữ bản cũ và thử lại.
3. So với dấu nhận diện **đã áp dụng thành công**, không chỉ so mtime hoặc lần quan sát gần nhất.
4. Trùng phiên bản đang dùng thì trả `unchanged`; khác thì nạp candidate.
5. Chỉ cập nhật dấu nhận diện sau khi chuyển context thành công. Một lần nạp hỏng không được chặn lần thử sau.

Hai yêu cầu cùng phát hiện B chỉ làm mỗi worker/listener áp dụng B một lần. A -> B -> C vẫn phải nạp cả B và C; không dùng một khoảng debounce để bỏ mất phiên bản mới thật. Dấu nhận diện liên quan key chỉ dùng nội bộ; log/HTTP chỉ công bố fingerprint chứng chỉ công khai.

Ví dụ watcher và API cùng báo khi A đã đổi thành B:

| Thứ tự | Kết quả |
|---|---|
| Watcher lấy khóa trước | So với A, dựng và áp dụng B; chỉ sau thành công mới ghi dấu B |
| API tới lúc watcher đang nạp | Chờ cùng khóa, không nạp song song |
| API lấy được khóa | Đọc lại bộ file; B trùng dấu đã áp dụng thì trả `unchanged`, không dựng lại context |
| B nạp lỗi hoặc file đã đổi tiếp thành C | Dấu thành công vẫn là A khi B lỗi; yêu cầu sau có thể thử B hoặc nạp C theo nội dung hiện tại |

Khóa chỉ bảo đảm chạy lần lượt; bước so phiên bản **bên trong khóa** mới ngăn hai lần reload liên tiếp cùng nội dung. Ở nhiều worker, mỗi worker vẫn phải áp dụng B một lần vì giữ context riêng; không dùng cờ thành công của primary để bỏ qua worker khác.

### 2.4. Watcher và yêu cầu liên tiến trình

- `watch`/`both` tạo task nhẹ trong mỗi worker đang phục vụ TLS, thuộc vòng đời web listener. Không dùng scheduler singleton cho watcher.
- Poll theo `interval_seconds`, mặc định 300 giây. Đây là chu kỳ kiểm tra file, không phải chu kỳ dựng lại context hoặc TTL của cache RAM. Theo lại symlink mỗi lượt; không chặn event loop khi đọc file hoặc dựng context.
- API management, Certbot deploy hook và hàm trực tiếp kích hoạt reload ngay, không đợi đến lượt poll. Certbot chỉ thông báo cho framework khi deploy hook đã được tích hợp; framework không tự nhận thông báo ACME.
- Watcher là đường tự phát hiện độc lập; với `both`, nó còn dự phòng khi hook bị mất hoặc gọi thất bại. Với `watch` không có hook, file đổi vẫn được phát hiện theo chu kỳ đã cấu hình.
- Startup luôn nạp cert ngay, không chờ 300 giây. Dev/test có thể đặt 1–5 giây để đo watcher nhanh, giữ đúng cùng đường code.
- Khi watcher đã phát hiện bộ file mới nhưng chưa nạp được, dùng retry sớm với backoff và giới hạn, chẳng hạn 5/10/30 giây, giữ context cũ. Không bắt mọi lần thử lại đợi trọn 300 giây. Sau một đợt retry chưa thành công thì ghi lỗi và quay về chu kỳ thường, tránh vòng lặp/log liên tục.
- Retry không giữ HTTP/hàm gọi mở vô hạn: yêu cầu phải trả kết quả hoặc timeout theo giới hạn của nó. Khi chỉ chọn `api`, không tự bật watcher định kỳ; bên gọi vẫn có thể gửi lại yêu cầu sau lỗi.
- Listener đang stop/isolated không được bật lại vì watcher hay thông báo reload; task phải được dừng và bộ TLS được bỏ đăng ký khi listener dừng.
- Yêu cầu từ hàm hoặc management dùng ProcessLink nội bộ của framework. Ứng dụng không phải gọi `configure_link()` hoặc đăng ký thêm adapter.
- Thông điệp chỉ mang lệnh, đích và correlation; không vận chuyển PEM/private key. Mỗi worker tự đọc đường dẫn hiệu lực của listener của nó.
- Bootstrap vận chuyển/điều phối lệnh adapter tổng quát; handler TLS ở web adapter. Không dùng event bus trong một tiến trình để giả làm broadcast cả cụm.
- Worker tiếp nhận xếp công việc reload vào task, không giữ pump điều khiển trong lúc nạp file.
- Xác định các worker đang thực sự phục vụ listener, có ACK riêng theo worker và lần chạy của worker. Kết quả một worker hoặc ACK của lần chạy cũ không được đại diện cho cả nhóm.
- Có timeout và retry giới hạn; ACK thiếu, worker thay thế giữa chừng hoặc bus mất thông báo phải hiện `timeout`/`partial`, không báo thành công toàn bộ. Không restart worker để xử lý các trường hợp này.
- Broadcast không tự chạy tại bên gửi thì phải xử lý đích cục bộ riêng. Không dùng một `ask()` trả lời đầu tiên làm bằng chứng đủ mọi worker.
- Mỗi worker/listener giữ kết quả và phiên bản riêng. Không ép các listener có cert riêng phải dùng cùng fingerprint.

Lý do chọn 300 giây: với deploy hook sau gia hạn thành công, yêu cầu bên ngoài là đường cập nhật nhanh; watcher dự phòng có thể chấp nhận độ trễ vài phút trong trường hợp gia hạn thông thường. Certbot gia hạn trước hạn, nhưng không được hardcode giả định “cert cũ luôn còn 30 ngày”. Thời gian còn lại thực tế phụ thuộc chứng chỉ, lịch gia hạn và `notAfter`; framework vẫn là bộ đọc/nạp file tổng quát, không quản lý lịch gia hạn của CA. [Tài liệu Certbot](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates).

### 2.5. HTTP quản trị và health

```http
POST /tls/reload
Content-Type: application/json

{"server_id": "default"}
```

Endpoint chờ cùng hàm `reload_tls()`. Body không nhận đường dẫn cert/key hoặc private key. Chỉ mở cho các listener chọn `api`/`both`; hàm trực tiếp vẫn dùng được cho listener chọn chế độ khác.

Kết quả cần có request ID, thời điểm và từng worker/listener: `reloaded`, `unchanged`, `failed`, `timeout` hoặc `inactive`. Phản hồi chỉ công bố thông tin chứng chỉ công khai. Thành công toàn bộ dùng HTTP 200; đích không tồn tại/không có TLS, lỗi nạp hoặc thiếu ACK phải có mã HTTP lỗi và kết quả rõ. Mã lỗi cụ thể được định nghĩa cùng DTO trong bước 5, không dùng lỗi nghiệp vụ của Xime Platform.

- Public `/healthz`, `/readyz` vẫn chỉ có khi ứng dụng bật health; trả trạng thái tối giản và giữ ý nghĩa/mã 200 hoặc 503.
- Management bật thì tự có hai route health chi tiết.
- `app.health()` tiếp tục là báo cáo của **một tiến trình**, không đổi thành báo cáo toàn cụm. Health chi tiết ghi rõ scope/process và thời điểm; không quảng cáo một phản hồi của primary là sức khỏe tất cả worker.
- Việc giảm trường trong health public là thay đổi hợp đồng phản hồi: ghi rõ trong tài liệu nâng cấp và chỉnh test/monitor minh họa đang đọc `primary` hoặc `adapters` qua cổng public.

## 3. Bằng chứng hiện tại và vấn đề cần sửa trước

### 3.1. Đã hoàn thành việc nâng Uvicorn

- `pyproject.toml`: sàn web extra đã là `uvicorn[standard]>=0.47.0`.
- Môi trường Python 3.14 đang dùng đã nâng Uvicorn 0.41.0 -> 0.47.0, làm mới metadata của Xime editable.
- `ssl_context_factory` được gọi thử thành công; `pip check` sạch.
- Cùng bộ web/processes/bootstrap/watchdog/ws: **496 passed, 4 skipped, 18 warnings** trước và sau nâng. Đây là kiểm chứng nâng dependency, không phải chứng minh reload đã triển khai.
- Môi trường đo: Windows, Python 3.14.8, Uvicorn 0.47.0, OpenSSL 3.5.9.

### 3.2. Các phép thử thiết kế đã đo

- TLS qua MemoryBIO: nạp đè cert B/key A lên context đang dùng A báo mismatch; handshake sau lỗi thất bại. Dựng candidate rồi chuyển context hoạt động A -> B -> C, với TLS 1.2/1.3, có/không SNI; kết nối cũ vẫn truyền dữ liệu.
- HTTP thật với hai instance ứng dụng mô phỏng worker trong cùng tiến trình: management hạng singleton chuyển A -> B trên cùng port; instance A được dựng lại với vai phụ không bind cổng. Đây chưa phải failover management giữa hai process thật.
- Các phép thử trên chỉ dùng cert tự ký/port thử nghiệm và đã dừng, không restart Data hay gọi Trust production.

### 3.3. Lỗi `processes` chỉ có một worker

Đã tái hiện bằng app thử nghiệm của framework và **process thật**: trước khi chết `primary=true`, scheduler serving; sau khi worker duy nhất được dựng lại, `primary=false`, scheduler standby, HTTP vẫn trả lời.

Nguồn: `_respawn()` bỏ primary cũ rồi gọi `_promote_someone()` khi không còn worker sống; `_primary_id` giữ None. `_spawn()` vì vậy trao `SharedHandle.primary=false` cho worker thay thế. READY hiện chỉ ghi nhận/log, không cấp lại vai.

Phải sửa ca này trước khi dựa vào management singleton. Đồng thời giữ:

- Chính sách chống domino/thăng cấp lỗi hiện có; không dùng fallback cấp vai để bỏ qua giới hạn đó.
- `run_once()` chỉ chạy lại khi cụm chưa xác nhận hoàn tất. Worker thay thế primary không được chạy lại hook đã hoàn thành chỉ vì nó nhận vai lúc startup; cần truyền trạng thái này trong handle/đường startup nội bộ nếu hiện chưa có.
- Khi promotion lỗi, dọn phần management đã start trong lần nhận vai chưa thành công; không để một worker đã từ chối primary tiếp tục giữ cổng. Kiểm tra cả scheduler đã khởi động dở để tránh hai worker cùng chạy job.

### 3.4. TLS thật trên máy local, không cần IP public

Ngày 2026-10-11 đã tạo CA thử nghiệm và cert A/B/C có key riêng, SAN gồm `localhost`, `127.0.0.1`, `::1`. Với cert A, Uvicorn và tham số TLS của framework phục vụ HTTPS qua loopback: **4 kết nối trả 200**, gồm TLS 1.2/1.3 và tên được kiểm chứng là `localhost`/`127.0.0.1`. Client tin riêng CA thử nghiệm, giữ `CERT_REQUIRED` và kiểm tên miền; đối chứng CA không được tin cậy và hostname sai đều bị từ chối. Listener đã dừng, cert/key tạm đã được dọn; không cài CA vào Windows.

Đây là handshake và HTTP **thật**, không phải mock. Không cần IP public, DNS công cộng hay chứng chỉ production để kiểm chứng TLS của framework. Cert B/C đã được tạo và kiểm tra nạp cert/key; phép đo HTTPS mới này chỉ dùng A, chưa chứng minh reload A -> B -> C trên listener. IPv6 chưa được đo dù SAN đã chứa `::1`.

Phép thử đầu dùng cipher mặc định `TLSv1` của Uvicorn 0.47.0 bị reset khi ép TLS 1.2. Đối chiếu trên môi trường Windows/Python 3.14.8/OpenSSL 3.5.9 cho thấy không có cipher chung với client Python mặc định ở TLS <=1.2. Phép thử đạt ở trên đã cấu hình `ECDHE+AESGCM`; TLS 1.3 cũng đạt. Không suy rộng kết quả cipher này sang mọi client hoặc OS.

Do đó bước 3 phải kiểm riêng cipher mặc định và cipher được ứng dụng khai tường minh. Chưa đổi cipher mặc định trong code; nếu cần thay chính sách mặc định khi triển khai thì ghi rõ lý do, tác động tương thích và bằng chứng. Linux vẫn cần kiểm event loop, quyền file và symlink riêng. DNS public/ACME/Certbot thật trên VPS thuộc kiểm chứng tích hợp triển khai, không phải điều kiện để bắt đầu test TLS local.

## 4. Các bước triển khai

### Bước 0 - Bảo toàn worktree và lập mốc kiểm tra ✅

- Đọc diff đang có trước khi sửa; các file CLI/config/bootstrap và docs configuration đang chứa công việc khác. Không ghi đè, hoàn tác hoặc gom chúng vào thay đổi TLS.
- Lập mốc test trên cây hiện tại. Mốc 496/4 ở mục 3 chỉ phủ bộ được ghi, không đại diện toàn suite.
- Ghi hồ sơ lỗi primary một worker trước khi vá, gồm bản tái hiện, phạm vi và bằng chứng; liên kết với mục 3.3.

### Bước 1 - Sửa và kiểm chứng vòng đời primary ✅

Phạm vi dự kiến: `core/bootstrap/{_supervisor.py,_shared.py,application.py}` và test processes/watchdog.

- Khôi phục primary cho worker thay thế khi không còn ứng viên sống, qua chính sách phục hồi/chống domino có kiểm soát.
- Truyền đúng vai runtime và nhu cầu chạy `run_once` vào worker mới; worker cũ trở lại không giành primary khi đã có primary khác.
- Kiểm chứng dọn các thành phần mới start khi promotion thất bại, xử lý standby/retry đúng vòng đời tài nguyên.
- Đối chứng: bản trước phải tái hiện mất primary; bản sửa phải khôi phục job/management, vẫn không chạy job ở hai worker và không chạy lại `run_once` đã xong.
- Bằng chứng đã có: regression subprocess một worker chết rồi restart; management được dựng lại trên cùng cổng ở primary mới; promotion rollback giải phóng listener đã start; test chống domino hiện có vẫn nằm trong bộ kiểm tra.

**Điều kiện qua bước:** một worker và nhiều worker đều có bằng chứng process thật về phục hồi vai; chống domino và các listener nghiệp vụ còn đúng.

### Bước 2 - Cấu hình chung và management singleton ✅

Phạm vi dự kiến: web `_server_config.py`, thành phần management mới; tích hợp bootstrap/slot/topology, CLI `_config_spec.py`, `_config_check.py` và các test liên quan.

- Thêm model `webserver.ssl.reload` và `webserver.management`, alias `server` có kiểm xung đột.
- Tạo/chuẩn hóa management trước các phép kiểm topology; lỗi trùng địa chỉ phải được phát hiện trước khi spawn.
- Tự đăng ký thành phần singleton qua cơ chế nội bộ tổng quát; giữ core không phụ thuộc HTTP/TLS.
- Giữ nguyên schema `process`/`processes`, xử lý `count`, `shared`, quyền sở hữu cổng và TLS riêng hiện có.
- Kiểm thử startup/stop, chuyển primary và bind thất bại; management tắt không mở thêm cổng.

**Điều kiện qua bước:** cùng YAML `process`/`processes` cũ chạy được; bật management bằng khối chung thì đúng một primary phục vụ đúng địa chỉ.

Đã thêm model/CLI cho `webserver`, kiểm host loopback và port, chặn khai đồng thời alias `server`, tự thêm endpoint nội bộ sau khi parse topology, và kiểm trùng địa chỉ trước khi sinh worker. Cấu hình topology ứng dụng giữ nguyên.

### Bước 3 - Bộ TLS, API Python và nạp an toàn ✅

Phạm vi dự kiến: web `_adapter.py`, `_server_config.py`, các module TLS/reload mới và export trong `web/__init__.py`.

- Tích hợp `ssl_context_factory`; tạo bộ TLS có vòng đời theo Application/listener.
- Dựng candidate và chuyển context, xử lý symlink/file lệch, giữ policy TLS và context cũ khi lỗi.
- Implement bộ nạp cục bộ, khóa và dấu nhận diện trong RAM theo Application/worker/listener; không thêm phụ thuộc LMDB. So cả cert/fullchain và key; chuẩn bị hàm công khai và kết quả theo mục 2.3.
- Tạo fixture CA thử nghiệm + cert A/B/C/key riêng, client tin riêng CA và luôn kiểm chứng tên miền. Có đối chứng client từ chối CA không được tin cậy và hostname sai; không dùng `verify=False` hoặc `CERT_NONE` để làm test thành công.
- Kiểm riêng TLS 1.2/1.3 với cipher mặc định và cipher khai tường minh. Giải quyết/ghi rõ phát hiện ở mục 3.4; không dùng cấu hình cipher của fixture để che lỗi tương thích của mặc định.
- Chạy handshake thật để xác nhận cert mới, cùng kết nối dài đang dùng cert cũ.

**Điều kiện qua bước:** A -> B -> C và candidate hỏng đều đạt trên listener thật; số bootstrap/hook/worker không tăng vì reload.

Đã kiểm trên Uvicorn thật: A -> B -> C, cặp sai bị từ chối và thử lại được, handshake mới nhận cert mới, kết nối TLS cũ tiếp tục hoạt động, có/không SNI. Hai yêu cầu đồng thời cùng B cho một kết quả `reloaded` và một `unchanged` tại mỗi worker.

### Bước 4 - Watcher và reload đủ mọi worker ✅

Phạm vi dự kiến: vòng đời web TLS; `_control.py`, `_cluster.py` và lớp điều phối adapter nội bộ cần thiết.

- Watcher theo từng listener/worker, không phụ thuộc scheduler.
- Mặc định poll 300 giây; startup và lệnh gọi trực tiếp xử lý ngay. Thêm retry sớm có backoff/giới hạn cho bộ file mới chưa hợp lệ và dừng retry khi listener stop/isolated.
- Hoàn thiện `reload_tls(app, server_id=...)` với điều phối các đích đang phục vụ, xử lý đích cục bộ và ACK theo từng worker.
- Chống trùng khi watcher/hàm/API cùng yêu cầu; thể hiện timeout/partial và retry, không đưa key vào bus.
- Đo từng worker, gồm worker vừa restart và primary không trực tiếp phục vụ listener đích.

**Điều kiện qua bước:** đổi file không gửi thông báo vẫn cập nhật; lệnh gọi hàm cập nhật đủ đích; cùng một phiên bản chỉ áp dụng một lần tại mỗi worker/listener.

Đã có watcher kiểm file cục bộ và retry 5/10/30 giây sau lỗi; API/hàm dùng lệnh `ProcessLink` opaque có correlation và ACK theo worker. Test cụm thật nhận ACK đủ hai worker và xác nhận cùng phiên bản chỉ nạp một lần/worker.

### Bước 5 - HTTP reload và health đúng phạm vi ✅

Phạm vi dự kiến: thành phần management, `_health.py`, `_registry.py`, DTO/kết quả và test web/watchdog.

- Thêm endpoint POST dùng đúng hàm chung, chờ kết quả cuối cùng; kiểm đích/mode, không nhận cert/key từ request.
- Health public tối giản; management chi tiết có scope rõ. Giữ `app.health()` và semantics alive/ready.
- Management không có controller nghiệp vụ, API reload public, Swagger hoặc phụ thuộc xác thực nghiệp vụ.
- Đưa ví dụ Certbot deploy hook dùng HTTP loopback; lỗi reload phản ánh qua exit code của hook, không dùng `systemctl restart`.

**Điều kiện qua bước:** gọi từ chương trình bên ngoài có kết quả cuối cùng; management chỉ nghe loopback; route và thông tin public đúng thiết kế.

Đã tạo `/tls/reload` chỉ cho `api`/`both`, không nhận đường dẫn cert/key; public health trả trạng thái tối giản, health trên management loopback trả báo cáo cục bộ chi tiết. Đã thêm ví dụ deploy hook và docs VN/EN.

### Bước 6 - Kiểm chứng tổng hợp và bàn giao ⏳

- Dùng CA thử nghiệm và loopback để đo handshake/HTTPS thật trên máy local, gồm xoay A -> B -> C, kết nối dài và nhiều worker; không cần IP public hoặc xin cert production.
- Chạy các ca ở mục 5 trên Windows và Linux, với asyncio và uvloop ở những nhánh được hỗ trợ; ghi Python/Uvicorn/OpenSSL/OS/event loop đã dùng.
- Ghi riêng kết quả tích hợp DNS public/ACME/Certbot trên VPS khi phiên triển khai thực hiện; kết quả local không đại diện cho đường truy cập Internet hay môi trường Linux.
- Chạy kiểm tra phù hợp và full regression trước bàn giao; linter/type check so với baseline hiện tại, không quy lỗi cũ thành lỗi mới.
- Cập nhật docs VN/EN về cấu hình, multi-process, API, health, alias/migration và ví dụ ứng dụng; ghi rõ thay đổi phản hồi health public.
- Cập nhật tài liệu yêu cầu gốc và kế hoạch bằng liên kết tới kết quả thực; ghi rõ phần chưa đo, không đánh dấu đạt bằng suy luận.
- Bàn giao file thay đổi, lệnh test chạy lại, ví dụ YAML/hàm/hook và giới hạn. Phiên VPS/Python consumer chỉ tích hợp sau khi nhận giao diện cuối cùng.

**Điều kiện hoàn thành:** các yêu cầu runtime đạt bằng handshake/request thật, các regression được giải thích, cấu hình nghiệp vụ cũ không phải viết lại. Chưa phát hành nếu còn thiếu kiểm chứng Linux bắt buộc.

Đã kiểm chứng trên Windows: CA thử nghiệm và HTTPS thật A -> B -> C; cặp mismatch giữ context cũ; kết nối keep-alive cũ tiếp tục; handshake có/không SNI; watcher tự phát hiện; management API qua hai worker thật có ACK từng worker và dedupe; primary restart khôi phục management; rollback promotion giải phóng cổng đã start.

Chưa đạt điều kiện phát hành: chưa chạy Linux/uvloop, chưa kiểm symlink Certbot trên Linux, chưa thử DNS/ACME/deploy hook thực trên VPS. Máy hiện tại không có WSL distribution.

## 5. Ma trận nghiệm thu

| Nhóm | Ca bắt buộc |
|---|---|
| Cấu hình | `process`/`processes` giữ nguyên; lớp môi trường hiện có; alias `server`; khai cả hai khối bị chặn; TLS riêng/`ssl: {}` |
| Management | Tắt không mở port; đúng một primary bind; IP loopback IPv4/IPv6 được hỗ trợ; trùng port/bind lỗi có thông báo đúng nguồn |
| Primary | Hai worker chuyển vai; worker cũ trở lại không bind management; `processes` một worker phục hồi vai; không chạy lại `run_once` đã xong; giữ chống domino |
| Promotion lỗi | Không để management/job vừa start tiếp tục chạy sau khi từ chối vai; các listener nghiệp vụ đang chạy được giữ |
| Watcher | Đổi file/symlink không gửi lệnh; A -> B -> C có thay key; cert đổi nhưng key giữ nguyên; thiếu file/permission/lệch cert-key rồi khôi phục vẫn nạp được |
| Nhịp kiểm tra/retry | Mặc định 300 giây; startup/API/hook/hàm không đợi poll; mất hook vẫn có watcher; retry bộ file mới sớm và có giới hạn; mode `api` không tự bật watcher |
| Chống trùng | Watcher + API + hàm cùng phiên bản, yêu cầu lặp, mtime đổi nhưng nội dung không đổi; mỗi worker/listener chỉ áp dụng một lần |
| Cache theo worker | Không cần LMDB/RefData cho nội dung TLS hoặc dấu đã áp dụng; worker mới luôn dựng context; worker A đã nạp B không làm worker B bỏ qua lần nạp của nó |
| TLS thật | CA thử nghiệm và loopback, client verify chain/hostname; TLS 1.2/1.3, có/không SNI, handshake lặp khi đang reload; client từ chối CA không được tin cậy/hostname sai; không cần IP public |
| Cipher/policy | Đo riêng cipher mặc định và cipher khai tường minh, nhất là TLS 1.2 trên môi trường đã phát hiện thiếu cipher chung; CA/mTLS và policy đã cấu hình tiếp tục được giữ |
| Kết nối dài | HTTP keep-alive, WebSocket, stream vẫn phục vụ; handshake mới thấy cert mới; không tăng bootstrap/run-once hoặc restart worker vì reload |
| Cụm/listener | ACK từng worker; đích không nằm ở primary; cert riêng; listener HTTP; worker restart; timeout/mất thông báo/trùng request không báo thành công giả |
| API/health | Đúng mode; hàm không cần management; endpoint không nhận key/path; health public tối giản, health management chi tiết đúng scope |
| Startup/stop | TLS startup sai vẫn fail fast; HTTP dev vẫn chạy; listener stop/isolated không được tự bật lại; đóng watcher/task/context/port đúng vòng đời |
| Tương thích | CLI config/init/check khớp model mới; bộ test và docs cũ được di trú có lý do; không đổi Trust/gRPC/mTLS hay code consumer |

Các test nhiều worker phải ghi nhận được từng worker thực sự phục vụ, không chỉ xác nhận port còn mở. Test reload đồng thời cần đếm lần chuyển context thực tế cùng handshake xác nhận cert, không chỉ đếm log/request.

## 6. Phạm vi ghi file và trạng thái công việc

- Lượt triển khai chỉ sửa repo framework: core bootstrap, web adapter, CLI config spec/check, docs VN/EN và tests trong `tests_temp/`.
- Sàn dependency vẫn là `uvicorn[standard]>=0.47.0`; môi trường hiện tại đã dùng 0.47.0 trước lượt triển khai.
- Worktree có thay đổi cấu hình môi trường và tài liệu tồn tại trước lượt này; đã giữ nguyên nội dung ngoài phạm vi và không hoàn tác.
- Không sửa Data Service, Python consumer, cấu hình ứng dụng thật hoặc VPS; không restart service, commit, push hay phát hành.
- Regression Windows đã xong theo kết quả trên; còn chờ kiểm chứng Linux/VPS nêu tại bước 6. Không đánh dấu hoàn thành cho các phần chưa đo.

## 7. Nguồn đối chiếu

- [Yêu cầu gốc](yeu-cau-reload-tls-web.md), [thiết kế TLS lịch sử](../thiet-ke/07-tls-web-adapter.md), [đa tiến trình](../thiet-ke/10-da-tien-trinh.md).
- Mã hiện tại: `core/bootstrap/{_supervisor.py,application.py,_shared.py,_cluster.py,_processes.py}`, `adapters/web/{_adapter.py,_server_config.py,_health.py}`, `starters/scheduler/_adapter.py`.
- [Uvicorn 0.47.0 release notes](https://github.com/encode/uvicorn/blob/0.47.0/docs/release-notes.md), [API SSL context factory](https://github.com/encode/uvicorn/blob/0.47.0/docs/settings.md), [Python SSL](https://docs.python.org/3.14/library/ssl.html), [Certbot deploy hooks](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates).
