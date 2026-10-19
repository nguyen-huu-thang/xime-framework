# Kế hoạch code: Trust, dữ liệu mẫu và logging

**G1–G4 đã triển khai; đã tiếp nhận Linux và kiểm lại Windows ngày 2026-10-19.**
Hai full Windows/Python 3.12 và 3.14 đều 2965 passed/33 skipped/1 deselected;
Linux/Python 3.13.5 có bốn lượt full 2975 passed/12 skipped trước bổ sung
pointer Windows. Xem [nghiệm thu, bản vá và giới hạn](NGHIEM-THU-LOGGING.md).
Source/test đã stage khi bàn giao, chưa commit hoặc phát hành.

Đọc [kế hoạch chi tiết và tiêu chí nghiệm thu](.claude/docs/sap-toi/ke-hoach-trust-du-lieu-mau-va-logging.md).

| Thứ tự | Đợt | Điểm dừng |
|---|---|---|
| 1 | Sửa lịch Trust, khóa cấu hình Shop hoa và sync startup trùng | G1 đã báo cáo, staged |
| 2 | Sửa nạp dữ liệu mẫu Kho/Sổ thu chi, kiểm PostgreSQL cô lập | G2 đã báo cáo, staged |
| 3 | Logging file Xime: công tắc, mức riêng, rotation, nhiều process | G3 đã bàn giao: framework 2908 passed/25 skipped |
| 4 | Thu lỗi gRPC native kèm IP vào logging Xime | Đã kiểm Linux, tiếp nhận ba bản vá; Windows sàn 1.72.1 ghi đúng 20/20 event vào file; full hai Python đạt |

Không sửa/copy thư mục build VPS hoặc triển khai. Wheel/sdist trong vùng tạm
chỉ dùng để nghiệm thu, không phải gói phát hành đã được duyệt.
Không ghi DB ứng dụng thật, không xử lý `share-live-test-key`, không tự commit/push/PyPI.
Consumer G3 Windows: 6295 passed, 18 skipped; hai guard cryptography baseline
giữ riêng. Linux kiểm thêm consumer và phân loại nợ Dental/Shop Hoa, xem nghiệm thu;
không coi mọi consumer hoặc nghiệp vụ live đã xanh.

Chủ dự án đã duyệt tiếp thiết kế pipe sống suốt đời process; lịch sử ở mục 7.5,
tiếp nhận ở mục 7.6. [Kết quả native](KIEM-THU-GRPC-HANDSHAKE.md).
Hướng dẫn logging: [docs/vn/logging.md](docs/vn/logging.md). Chưa triển khai VPS;
điều kiện thử VPS vài ngày trước PyPI vẫn còn.
