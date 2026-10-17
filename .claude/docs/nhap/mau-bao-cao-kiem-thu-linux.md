# Báo cáo nghiệm thu Linux — [điền mã lượt]

> **Trạng thái:** MẪU CHƯA ĐO — phiên Linux phải thay bằng kết luận thực tế.
> **Thuộc bản:** source Windows sau `78c0fa8`; metadata 0.8.3, xác nhận bằng manifest.
> **Thay cái gì:** trả lời các cổng Linux còn thiếu ở Bước 7.
> **Bị thay bởi:** chưa có.

## 1. Kết luận và giới hạn

[Đã đo gì, lỗi nào, điều kiện phát hành nào còn mở. Không dùng Windows pass thay Linux pass.]

| Cổng | ĐẠT / LỖI SẢN PHẨM / LỖI MÔI TRƯỜNG-HARNESS / CHƯA KIỂM | Bằng chứng tương đối |
|---|---|---|
| Nhận đúng source, giữ nguyên `.git`, backup cây cũ | | |
| Python 3.12 + full suite loop pytest mặc định | | |
| Đối chứng loop mặc định/uvloop trong pytest | | |
| Full suite uvloop thật | | |
| Application/worker dùng uvloop, HTTP/HTTPS/WSS/Unix socket | | |
| Quyền POSIX, /dev/shm, socket inheritance, cleanup | | |
| TLS ma trận và nhiều worker/primary/ACK | | |
| Lineage symlink/watcher/hook mô phỏng | | |
| Certbot/ACME/DNS/VPS thật | | |
| Minimum từng extra + resolver mới | | |
| Lint/types/docs/advisory | | |
| Wheel/sdist và hai runtime JWT trắng | | |
| MQTT/MinIO riêng | | |
| Consumer/DB/cert/nghiệp vụ live | | |

## 2. Máy và bản nhận

- Ngày giờ bắt đầu/kết thúc UTC, người dùng thường/root:
- Linux/kernel/CPU/RAM, filesystem thật của source và output:
- Python/OpenSSL/uvloop/pytest/pytest-asyncio:
- Nguồn mount ổ D; đích test Linux; vùng backup ngoài cây:
- SHA-256 của `KIEM-THU-LINUX.sha256`, số file đã kiểm, log kiểm nguồn/bản chép:
- Cách bảo toàn mọi `.git`; không lấy HEAD Git Linux cũ làm danh tính candidate:
- Import `xime.__file__`, dependency freeze; tên/package version không đủ xác nhận source:

## 3. Nhật ký kiểm thử

| Phép chạy | Lệnh/log/XML | Exit | Collected | Passed | Failed | Error | Skip | Deselect | Giây |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Full asyncio | | | | | | | | | |
| Full uvloop | | | | | | | | | |
| Tập sàn riêng nếu chạy full | | | | | | | | | |

Liệt kê **từng lý do skip** và collection khác mốc Windows 2.910. Nếu bỏ test vì
hạ tầng, nêu số ca/tên và lý do; không biến skip/deselect thành passed.

## 4. Loop thật, POSIX và TLS

- Hai log `LOOP_THUC`, đối chứng thành công/thất bại, cách chọn loop của harness:
- Loop thực trong từng worker; request/HTTPS/WSS/Unix credentials/shutdown:
- Test quyền chạy bằng user thường, `/dev/shm`, Unix socket và cleanup:
- RSA/ECDSA × TLS 1.2/1.3 × default/explicit, A→B→C, SNI/no-SNI, mTLS:
- Nhiều worker, primary, ACK/partial/timeout, public/management health:
- Timeline symlink đổi từng link, mismatch tạm, context cũ, watcher hồi phục/hook:
- Phần Certbot/ACME/DNS/VPS thật chưa đo và điều kiện cần:

## 5. Dependency, chất lượng và artifact

| Nhóm minimum | Pin yêu cầu | Version thực | Install/pip check/import/test | Kết luận/log |
|---|---|---|---|---|
| core | | | | |
| web | | | | |
| sqlalchemy | | | | |
| jwt | | | | |
| scheduler | | | | |
| socket | | | | |
| grpc | | | | |
| redis | | | | |
| lmdb | | | | |
| s3 | | | | |
| mqtt | | | | |
| mail | | | | |
| modbus | | | | |
| opcua | | | | |

- Resolver mới: freeze, pip check, phiên bản các thư viện đã thay so Windows:
- Sàn không tương thích và tổ hợp thấp nhất cài được: ghi hai kết quả riêng:
- Ruff/mypy/docs: exit và output thực; checker skip ví dụ nào:
- Advisory: ngày dữ liệu, raw exit/JSON, ngoại lệ APScheduler, mục mới/mạng lỗi:
- Artifact: SHA-256, nội dung/METADATA, đối chiếu source, kết quả twine:
- Hai runtime chỉ wheel `[jwt]`: version/path/pip check/15 ca + YAML redaction:
- MQTT/MinIO: phiên bản, cổng test/bucket/topic, số ca thực chạy, teardown:
- Consumer nào có/không có, phạm vi test và cổng live chưa kiểm:

## 6. Phát hiện và bàn giao

Mỗi lỗi ghi: mức ảnh hưởng, source/environment/harness, lệnh tái hiện, expected /
actual, log/trace, đề xuất. Chỉ sửa source nếu owner duyệt; giữ dấu vết thay đổi.

- Hash source sau test và dry-run kiểm file thêm/mất/đổi:
- Source có sửa không; nếu có: quyền duyệt, file, diff với incoming, cách tái hiện:
- Tiến trình/tài nguyên do lượt này tạo đã dọn; ngoại lệ cần giữ:
- Đường dẫn cây test để owner ZIP; đường dẫn tương đối báo cáo trong ZIP:
- Manifest các kết quả gửi về; mục loại trừ `.git`/venv/cache/token/private key:
- Việc còn thiếu, lý do và điều kiện để nghiệm thu tiếp:
