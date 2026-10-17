# Kiểm chứng TLS web và cấu hình môi trường

> **Trạng thái:** đã kiểm chứng bổ sung ngày 2026-10-15; hai vấn đề P2 được xác nhận,
> nhận định thứ ba được đính chính, không coi khác fingerprint là lỗi chức năng.
> **Thuộc bản:** source commit `2ad5274`; metadata package vẫn là `0.8.3`.
> **Thay:** kết luận chỉ đọc mã của lượt rà ban đầu trong `backlog-sua-loi.md`.
> **Bị thay bởi:** chưa có; chưa sửa mã thực thi hoặc cấu hình consumer.

Các thay đổi so với nhận định ban đầu:

| Phát hiện | Kết luận sau kiểm chứng | Việc còn lại |
|---|---|---|
| Checker bỏ sót TLS trong overlay | Xác nhận, hạ từ “cao” xuống P2; cần lỗi cấu hình và không có TLS hợp lệ để kế thừa | Vá checker đối với các khối framework trong cấu hình môi trường |
| Cipher mặc định Uvicorn 0.47.0 | Xác nhận P2 cho client TLS 1.2 không có cipher chung; TLS 1.3 và một số client TLS 1.2 vẫn hoạt động | Nâng sàn dependency hoặc chọn cipher server đã kiểm chứng |
| Worker trả fingerprint khác nhau | Rút lại việc coi đó là lỗi chức năng; chứng thư khác nhau có thể cùng hợp lệ, PEM khác định dạng cũng đổi hash | Làm rõ tài liệu API; không ép fingerprint bằng nhau như quy tắc mặc định |

## 1. Phạm vi và bằng chứng

- Windows, Python 3.14.8, OpenSSL 3.5.9, asyncio; framework được import từ checkout này.
- Uvicorn cài sẵn là 0.47.0. Bản 0.48.0 được tải và giải nén vào thư mục thử riêng;
  chỉ các tiến trình đối chứng dùng bản đó. Sau đo, môi trường cài sẵn vẫn là 0.47.0.
- Mọi cert/key dùng trong phép đo đều tự sinh từ CA thử, listener chỉ bind loopback.
  Client kiểm tra CA, hostname và thời hạn; không dùng `verify=False` hoặc `CERT_NONE`.
- Chạy cả loader, checker, topology, DI/lifecycle của Application và WebAdapter thật
  trong các ca cấu hình. Cụm hai worker dùng supervisor và ProcessLink thật.
- Không khởi động/dừng service Base hay consumer, không sửa YAML nguồn, DB hoặc dependency
  của môi trường thật. Chỉ cập nhật tài liệu sau khi có kết quả.

Thư mục bằng chứng: `D:/temp/xime/framework-tls-audit-20261015-2ad5274/`.

| Tệp | Vai trò |
|---|---|
| `audit.py`, `audit_cluster/` | Harness và ứng dụng tối thiểu để chạy lại |
| `config-0.47.0.json` | Chín ca cấu hình và kết quả HTTP/HTTPS thực |
| `cipher-0.47.0.json`, `cipher-0.48.0.json` | Ma trận cipher, protocol, loại khóa, startup/reload và đối chứng âm |
| `cluster-0.47.0.json`, `cluster_work/cluster.log` | Bảy kịch bản trên cụm hai worker, HTTP management và kết quả client |
| `consumer-config-inventory.json` | Chỉ các cờ/cấu trúc TLS của 12 consumer; không sao chép credential |
| `focused.xml`, `tls048.xml` | Kết quả test có sẵn: 132 ca ở 0.47.0 và 42 ca TLS ở 0.48.0 |

Harness ban đầu tạo CA/leaf thiếu extension Authority Key Identifier nên client OpenSSL
strict từ chối cả ca đối chứng hợp lệ. Đã bổ sung extension chuẩn vào bộ cert thử
`certs_v2`, giữ nguyên việc xác thực client, rồi chạy lại toàn bộ các phép đo cuối cùng.
Lỗi fixture ban đầu không được tính là lỗi framework.

## 2. Phát hiện 1: checker bỏ sót khóa framework trong overlay — xác nhận, P2

`xime check config` chỉ kiểm cấu trúc `environments`, không dùng cấu hình đã chọn để kiểm
tiếp những khối framework bên trong. Schema của hai khóa `local/server` không có cây con,
nên `_walk()` không đi sâu. Runtime cho phép không khai TLS để hỗ trợ HTTP như hợp đồng
hiện hành; khóa gõ sai có thể trông giống không khai TLS.

Vị trí mã: `xime/cli/_config_check.py:144`, `xime/cli/_config_spec.py:364`,
`xime/core/config/loader.py:134`, `xime/adapters/web/_adapter.py:411` và
`xime/adapters/web/_server_config.py:134`.

Ma trận dùng topology tường minh với cổng tạm trên `127.0.0.1`:

| Cấu hình | Checker | Khởi động và kết nối thật |
|---|---|---|
| TLS đúng ở root hoặc trong overlay | `clean` | HTTPS 200; HTTP thuần không nhận phản hồi HTTP hợp lệ |
| Gõ `websever` ở root | `findings` | Runtime vẫn cho HTTP; checker phát hiện được lỗi gõ sai |
| Gõ `websever` trong nhánh server | `clean` | HTTP 200, HTTPS bị từ chối |
| Gõ `ss1` thay `ssl` ở root | `findings` | Runtime dùng HTTP |
| Gõ `ss1` thay `ssl` trong nhánh server | `clean` | HTTP 200, HTTPS bị từ chối |
| Gõ sai riêng `certfile`, còn `keyfile` đúng, ở root/overlay | `findings` / `clean` | Cả hai đều bị StartupException chặn; không mở listener |
| Nhánh server gõ sai nhưng phần chung đã có TLS đúng | `clean` | Vẫn HTTPS nhờ kế thừa TLS chung |

**Điều kiện gây mất HTTPS:** TLS dự định chỉ nằm trong khối gõ sai của nhánh đang chọn,
không có cấu hình TLS hợp lệ khác để kế thừa. Khóa sai phải làm mất cả khối TLS hoặc cả
cặp cert/key; không phải mọi lỗi trường TLS đều chuyển thành HTTP.

**Ảnh hưởng:** lỗi cấu hình có thể vượt qua kiểm tra trước triển khai. Client dùng URL HTTPS
sẽ gặp lỗi kết nối; không có cơ chế tự chuyển một request HTTPS sang HTTP trong framework.
Nguy cơ lộ dữ liệu chỉ phát sinh nếu client thực sự gửi dữ liệu qua HTTP tới listener đó.
Cần có lỗi YAML do người vận hành/công cụ triển khai; chưa có đường khai thác từ request
từ xa khi cấu hình đúng. Vì vậy hạ mức đánh giá ban đầu từ “cao” xuống **P2/trung bình**,
với hậu quả có thể lớn tùy cách triển khai.

**Hướng xử lý:** kiểm tra các khối framework trong cấu hình hiệu lực và nhánh môi trường
cần triển khai, giữ nguyên các khối riêng của app. Không biến việc thiếu TLS thành lỗi
startup chung cho mọi ứng dụng, vì HTTP đang là chế độ được hỗ trợ.

## 3. Phát hiện 2: mặc định cipher của Uvicorn 0.47.0 — xác nhận, P2

Framework bỏ qua `ssl_ciphers` khi YAML không khai cipher. Với Uvicorn 0.47.0, giá trị
mặc định là `TLSv1`. Trên môi trường đo, tập cipher legacy của server và client Python
mặc định có **0 cipher chung**; các cipher TLS 1.3 được tách khỏi phép so này.

Mỗi ô dưới được đo bằng HTTPS thật trước và sau reload A -> B, với cả RSA 2048 và ECDSA P-256:

| Uvicorn / cipher server | Client TLS 1.2 mặc định | Client TLS 1.3 mặc định |
|---|---|---|
| 0.47.0 / mặc định `TLSv1` | Bị reset | HTTPS 200, chứng thư đúng phiên bản |
| 0.47.0 / khai `ECDHE+AESGCM` | HTTPS 200 | HTTPS 200 |
| 0.48.0 / mặc định OpenSSL | HTTPS 200 | HTTPS 200 |
| 0.48.0 / khai `ECDHE+AESGCM` | HTTPS 200 | HTTPS 200 |

Đối chứng chẩn đoán: nếu client TLS 1.2 được cấu hình riêng để chấp nhận cipher
`ECDHE-RSA-AES256-SHA` hoặc `ECDHE-ECDSA-AES256-SHA`, Uvicorn 0.47.0 mặc định vẫn bắt tay
và trả 200. Đây không phải lỗi của mọi client TLS 1.2. Không đề nghị hạ chính sách cipher
của client như một cách khắc phục triển khai.

Client dùng CA không được tin cậy và hostname sai đều bị từ chối trong các đối chứng âm.
Uvicorn 0.48.0 được kiểm thêm với hai file test TLS hiện có: **42 passed**.

[Release notes 0.48.0](https://github.com/Kludex/uvicorn/blob/0.48.0/docs/release-notes.md)
và [source Config 0.48.0](https://github.com/Kludex/uvicorn/blob/0.48.0/uvicorn/config.py)
xác nhận mặc định mới là `None`, dùng cipher mặc định của OpenSSL.

**Ảnh hưởng:** lỗi khả dụng/tương thích cho client TLS 1.2 có danh sách cipher không giao
với mặc định cũ; không làm mất mã hóa hoặc tự hạ kết nối xuống HTTP. TLS 1.3 đã đo hoạt động.
Lỗi xuất hiện ngay startup và vẫn giữ nguyên sau reload, nên không quy nguyên nhân cho
thuật toán chuyển SSLContext. Mặc định cipher được kế thừa từ Uvicorn; code chuyển tiếp
cipher khi không khai đã tồn tại trước commit TLS reload.

**Hướng xử lý:** nâng sàn dependency web lên ít nhất 0.48.0 để loại phiên bản sàn có mặc
định này, hoặc khai cipher server đã kiểm chứng. Việc thay dependency/cấu hình chưa thực hiện.

## 4. Phát hiện 3: khác fingerprint — rút lại việc coi đó là lỗi chức năng

Đúng là `reload_tls()` không yêu cầu mọi worker trả cùng `certificate_fingerprint`.
Nhưng giá trị này là SHA-256 **của nội dung file PEM/fullchain**, không phải fingerprint
DER của riêng chứng thư leaf (`_tls_reload.py:45, 91`). Nó không trực tiếp biểu diễn
“chứng thư hợp lệ cho hostname mà client đang gọi”.

Đã chạy ứng dụng hai worker chia cùng một socket; mỗi kịch bản có 24 kết nối TLS mới,
đều bật xác thực CA/hostname:

| Kịch bản | Management | Kết quả client |
|---|---|---|
| Hai chứng thư khác nhau, cùng CA và cùng hostname hợp lệ | 200 / `unchanged`, 2 fingerprint | 24/24 đạt; xác nhận cả hai PID và hai chứng thư DER |
| Đổi cả hai sang cùng chứng thư mới | 200 / `reloaded`, 1 fingerprint | 24/24 đạt trên hai PID |
| Cùng chứng thư DER, một file PEM thêm hai dòng trắng | 200 / `reloaded`, 2 fingerprint | 24/24 đạt; chỉ có 1 fingerprint DER |
| Một worker có cert/key không khớp | 503 / `partial` | 24/24 vẫn đạt; worker lỗi giữ context cũ |
| Một worker nạp chứng thư sai hostname | 200 / `reloaded` | 14 đạt, 10 bị client từ chối do hostname mismatch |
| Cả hai cùng nạp một chứng thư đã hết hạn | 200 / `reloaded`, 1 fingerprint | 24/24 bị client từ chối vì hết hạn |
| Khôi phục chứng thư hợp lệ | 200 / `reloaded` | 24/24 đạt trên hai PID |

Kết quả cho thấy khác fingerprint có thể hoàn toàn hợp lệ; cùng fingerprint vẫn có thể
là chứng thư không dùng được. Buộc bằng nhau sẽ từ chối cả ca PEM chỉ khác định dạng và
không giải quyết được chứng thư hết hạn. Vì vậy **rút lại khuyến nghị mặc định đánh dấu
partial/failed chỉ vì fingerprint khác nhau**.

HTTP 200 hiện xác nhận mọi worker đích nạp được cặp cert/key hoặc đã dùng đúng nội dung
file hiện tại. Nó không cam kết kiểm định danh tính/thời hạn chứng thư thay client. Server
không được cấu hình hostname kỳ vọng để thực hiện phép kiểm đó. Client xác thực TLS vẫn
từ chối sai hostname/hết hạn; các phép đo không cho thấy đường bỏ qua xác thực TLS.

Nên làm rõ ý nghĩa HTTP 200 và fingerprint file trong tài liệu API. Nếu một triển khai
cần xác nhận đồng bộ một phiên bản cert cụ thể, bổ sung phép kiểm triển khai phù hợp với
mục tiêu đó; chưa có căn cứ buộc chính sách này lên mọi người dùng framework.

## 5. Phạm vi consumer và giới hạn kết luận

Đã đọc trong RAM YAML nguồn hiện tại của 12 backend: Data, Notification, CRM, Giao việc,
Kho, Nhân sự/chấm công, Sổ thu chi, Admin, Dental, Nhà trọ, Nhà hàng và Shop hoa.

- 12/12 dùng `environments.local/server`; nhánh server có khối TLS được nhận dạng đúng,
  có cả giá trị certfile/keyfile. Không thấy lỗi gõ sai mô tả ở phát hiện 1 trong những
  khối TLS đã khảo sát. Không kiểm tra tính tồn tại/hợp lệ của file Certbot trên VPS.
- 12/12 nhánh server có listener HTTPS kế thừa TLS chung và không đặt cipher tường minh.
  Nhánh server của Notification còn có một listener HTTP tường minh; không tính listener
  nội bộ này là lỗi TLS.
- 12/12 có reload mode hiệu lực `off`. Tính năng reload không tự bật chỉ vì framework có code.
- Manifest runtime trong gói build cũng cho phép `uvicorn>=0.47.0`; đây là giới hạn dependency,
  không phải bằng chứng phiên bản thực tế đã cài trên VPS.

**Không kết luận 12 dịch vụ đã triển khai đang lỗi.** Chưa đọc phiên bản Uvicorn/OpenSSL,
cấu hình hiệu lực hoặc handshake của tiến trình VPS. Linux/uvloop, quyền và symlink Certbot,
gia hạn ACME thật, luồng nghiệp vụ và dữ liệu người dùng nằm ngoài lượt kiểm chứng này.

## 6. Chạy lại và kiểm tra kết thúc

Harness có ba nhóm phép đo; chạy từ checkout framework bằng bốn lệnh sau:

```powershell
python -B D:/temp/xime/framework-tls-audit-20261015-2ad5274/audit.py config
python -B D:/temp/xime/framework-tls-audit-20261015-2ad5274/audit.py cipher
python -B D:/temp/xime/framework-tls-audit-20261015-2ad5274/audit.py cipher --uvicorn048
python -B D:/temp/xime/framework-tls-audit-20261015-2ad5274/audit.py cluster
```

`--uvicorn048` dùng wheel đã giải nén ở `uvicorn048/` trong cùng thư mục bằng chứng.

Bộ test source đã chạy: config overlay, CLI check/spec, TLS reload/results, management
topology và `TestTlsReloadCoordination`: **132 passed**, 2 cảnh báo deprecation.
Hai file TLS chạy lại riêng với Uvicorn 0.48.0: **42 passed**, 3 cảnh báo
deprecation/assert-rewrite; không có failure. Không chạy lại toàn suite framework.

Supervisor thử nghiệm kết thúc code 0. Đo lại PID supervisor/hai worker và hai cổng thử:
**0 tiến trình, 0 listener còn lại**. Môi trường cài sẵn vẫn import Uvicorn 0.47.0.
