# Bắt đầu ở đây: kiểm thử tiếp trên Linux

> **Trạng thái:** ĐÃ NHẬN KẾT QUẢ Linux ngày 2026-10-17; xem đánh giá ở dưới.
> **Thuộc bản:** source sau `78c0fa8` và `e5a5b5c`; metadata vẫn `0.8.3`.
> **Thay cái gì:** đầu vào cho phần Linux còn thiếu của Bước 7.
> **Bị thay bởi:** đánh giá tiếp nhận và báo cáo Linux đã lưu trong repo.

**Kết quả hiện tại:** [đánh giá và thay đổi đã nhập](.claude/docs/kiem-toan/nghiem-thu-linux-framework.md).
Linux có bốn full suite, mỗi lượt **2.898 passed / 12 skipped / 0 failed**;
đã nhập ba sàn Pydantic/gRPC. Còn mở SIGTERM app đơn, S3/MinIO thật,
Certbot/ACME/VPS và consumer/nghiệp vụ live. Bằng chứng gốc:
[BAO-CAO.md](ket-qua-kiem-thu-linux/20261017T144535Z/BAO-CAO.md).

Phần dưới là hướng dẫn chuyến đã hoàn thành; không dùng manifest incoming để
khẳng định source hiện tại chưa đổi sau khi đã nhập bản vá và cập nhật tài liệu.

**Phiên Linux đọc toàn bộ [hướng dẫn bàn giao](.claude/docs/nhap/ban-giao-kiem-thu-linux.md),
rồi làm lần lượt.** File đó đủ ngữ cảnh cho phiên chưa đọc cuộc trò chuyện này.

Nguồn trên Windows là **`D:\code\xime\xime framework`**. Trên Linux hãy tìm đúng
điểm mount của ổ D; không mặc định đó là `/mnt/d` vì đây là máy dùng hai hệ điều hành.

Chủ dự án đã yêu cầu chép source mới sang **thư mục test Linux đang có source cũ**,
ghi đè source cũ, **loại trừ `.git` ở mọi cấp**. Phải sao lưu cây cũ trước khi đồng bộ,
giữ nguyên Git phía Linux và chạy test trên filesystem Linux hỗ trợ quyền POSIX.
Hướng dẫn có bước xem trước `rsync --delete`, kiểm đường dẫn và đối chiếu bản chép.

- Bảng kiểm source của chuyến này: [KIEM-THU-LINUX.sha256](KIEM-THU-LINUX.sha256).
  Dùng `sha256sum --check`; không tạo lại bảng kiểm ở máy nhận để làm nó xanh.
- Phạm vi: Python 3.12, asyncio/uvloop thật, POSIX, TLS/reload/symlink,
  dependency minimum và resolver, wheel sạch; MQTT/MinIO và hạ tầng ngoài khi có.
- Kế hoạch đã duyệt: [kế hoạch vá kiểm toán](.claude/docs/sap-toi/ke-hoach-va-loi-kiem-toan-framework.md).
- Bằng chứng Windows: [đối chiếu nghiệm thu](.claude/docs/kiem-toan/doi-chieu-nghiem-thu-ke-hoach.md).
- Mẫu báo cáo: [mau-bao-cao-kiem-thu-linux.md](.claude/docs/nhap/mau-bao-cao-kiem-thu-linux.md).

Kết quả mới ghi vào **`ket-qua-kiem-thu-linux/<ma-luot>/BAO-CAO.md`** trong thư mục
test Linux, cùng log và XML. Kết thúc, phiên Linux ghi đường dẫn đầy đủ để chủ dự án
tự đóng gói thư mục đó thành ZIP rồi chuyển sang ổ D. Không tự chép ngược source
lên ổ D, không commit/push/tag/phát hành. Nếu phát hiện lỗi source thì ghi tái hiện
và đề xuất sửa; việc sửa source cần chủ dự án duyệt theo `AGENTS.md`.
