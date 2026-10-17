# Bằng chứng nghiệm thu Linux và tiếp nhận Windows

> **Trạng thái:** đã nhận và kiểm checksum ngày 2026-10-17; các cổng còn mở nằm trong đánh giá.
> **Thuộc bản:** sau 78c0fa8, metadata 0.8.3, chưa phát hành các bản vá.
> **Thay cái gì:** lưu bền kết quả chuyến Linux và kiểm lại khi nhập dependency floors.
> **Bị thay bởi:** chưa có.

Đọc [đánh giá Windows](../.claude/docs/kiem-toan/nghiem-thu-linux-framework.md)
trước khi kết luận từ [báo cáo gốc Linux](20261017T144535Z/BAO-CAO.md).
Mục SIGTERM của báo cáo gốc chưa đủ cơ sở coi là lỗi harness đã giải quyết.

- `20261017T144535Z/`: 735 file có checksum và `SHA256-KET-QUA.txt` gốc;
  giữ log lỗi/đối chứng, XML, harness, patch và hai đời artifact trước/sau nâng sàn.
- `TIEP-NHAN-WINDOWS.json`: danh tính ZIP, manifest và bản pyproject đã nhập.
- `windows-tiep-nhan/`: log/XML kiểm lại, metadata artifact, script chẩn đoán
  và checksum; venv/cache/artifact Windows đầy đủ nằm ở D:\temp, ngoài repo.

Kiểm bằng chứng Linux từ thư mục `20261017T144535Z` bằng
`sha256sum --check SHA256-KET-QUA.txt`. Manifest incoming ở gốc repo ghi source
**trước sửa**, không phải hash cây hiện tại sau nhập bản vá/cập nhật tài liệu.

Harness là ảnh chụp phép đo, có đường dẫn/mã lượt cũ; đọc và chép sang vùng temp
mới trước khi chạy lại, không ghi đè log/bằng chứng đang lưu. Đây không phải bộ
test mặc định mới của framework. `.gitattributes` giữ byte dữ liệu nguyên bản.
