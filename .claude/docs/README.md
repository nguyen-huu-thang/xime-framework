# Tài liệu nội bộ - Xime Framework

> Sắp xếp lại **2026-08-21**. Trước đó là 46 file phẳng, tên mang ngày tháng, bảy loại
> tài liệu trộn chung một chỗ.

## Đọc gì trước

| Muốn biết | Đọc |
|---|---|
| Framework đang ở bản nào, việc X làm ở bản nào | [`lo-trinh-phien-ban.md`](lo-trinh-phien-ban.md) |
| Framework LÀ GÌ, kiến trúc ra sao | [`thiet-ke/01-tong-quan.md`](thiet-ke/01-tong-quan.md) |
| Sửa mảng X thì dễ phá chỗ nào | [`thiet-ke/01-tong-quan.md`](thiet-ke/01-tong-quan.md) mục 16 |
| Hôm nay đứng ở đâu, còn việc gì | [`../CLAUDE.md`](../CLAUDE.md) |
| Luật code của repo này | [`../rules/`](../rules/) |
| ✅ Đợt đo uvloop 0.8.1 trên Linux (**đã xong**) | [`kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](kiem-toan/0.8.1-ket-qua-do-tren-linux.md); đề bài gốc ở [`ban-giao-cho-phien-linux-0.8.1.md`](nhap/ban-giao-cho-phien-linux-0.8.1.md) |
| ✅ Chạy thử `0.8.2` trên Linux (**đã xong** 2026-08-25) | [`kiem-toan/0.8.2-ket-qua-do-tren-linux.md`](kiem-toan/0.8.2-ket-qua-do-tren-linux.md) - 1 lỗi framework đã vá + 1 lỗi bộ benchmark đã vá |
| **Framework nhanh chậm ra sao, uvloop lãi ở đâu** | [`ghi-chep/benchmark-hieu-nang.md`](ghi-chep/benchmark-hieu-nang.md) |

## Bảy loại tài liệu, và luật của từng loại

| Thư mục | Trả lời câu | Hết hạn không |
|---|---|---|
| [`thiet-ke/`](thiet-ke/) | *framework LÀ GÌ* | **Không.** Sai thì sửa tại chỗ, không viết file mới |
| [`phien-ban/`](phien-ban/) | *bản X định làm gì, làm được gì* | Đóng băng khi phát hành |
| [`kiem-toan/`](kiem-toan/) | *có gì hỏng, đã vá chưa* | Đóng băng khi vá xong |
| [`ghi-chep/`](ghi-chep/) | *ca này hỏng vì sao, học được gì* | **Không.** Giá trị nằm ở bài học |
| [`da-phu-dinh/`](da-phu-dinh/) | *hồi đó định thiết kế thế này* | **Đã hết.** Nội dung nay **SAI** |
| [`nhap/`](nhap/) | *giấy nháp lúc đang làm* | **Đã hết.** Nội dung vẫn **ĐÚNG**, chỉ hết vai |
| [`sap-toi/`](sap-toi/) | *chưa làm* | Chưa tới hạn |

**Luật đặt tên: tên file là CHỦ ĐỀ, không phải sự kiện.** Ngày tháng nằm trong khối trạng
thái ở đầu file, không nằm trong tên. Một file mang ngày trong tên là một file không ai
dám sửa, vì sửa xong thì cái tên nói dối.

**Luật khối đầu file:** mọi file mở đầu bằng một khối `>` khai đúng bốn thứ - *trạng thái ·
thuộc bản nào · thay cái gì · bị thay bởi cái gì*.

---

## `thiet-ke/` - framework LÀ GÌ

Đánh số theo thứ tự đọc. 00-08 là phần có từ 0.7 trở về trước, 09-14 là 0.8.

| | Nội dung |
|---|---|
| [`00-gioi-thieu.md`](thiet-ke/00-gioi-thieu.md) | Mục tiêu, triết lý, Xime khác gì Dependency Injector |
| [`01-tong-quan.md`](thiet-ke/01-tong-quan.md) | **Thiết kế đầy đủ**, 16 mục. Mục 16 là *trạng thái từng mảng và cạm bẫy khi sửa* |
| [`02-cay-thu-muc.md`](thiet-ke/02-cay-thu-muc.md) | Cây thư mục kèm giải thích từng folder |
| [`03-diem-khoi-dong.md`](thiet-ke/03-diem-khoi-dong.md) | `main.py`, cấu trúc tối thiểu của một app |
| [`04-routing-layer.md`](thiet-ke/04-routing-layer.md) | Class-based controller, `_make_handler` |
| [`05-grpc-codefirst.md`](thiet-ke/05-grpc-codefirst.md) | Sinh proto từ code, lock file, sidecar |
| [`06-socket-adapter.md`](thiet-ke/06-socket-adapter.md) | Unix socket RPC, frame protocol, peer auth |
| [`07-tls-web-adapter.md`](thiet-ke/07-tls-web-adapter.md) | HTTPS qua khối `server.ssl`. Mức 2 đã bỏ hẳn, lý do ở mục 4 |
| [`08-grpc-client-mtls.md`](thiet-ke/08-grpc-client-mtls.md) | Client SDK + mTLS động, cert lấy từ Trust lúc chạy |
| [`09-kho-lien-tien-trinh-boi-canh.md`](thiet-ke/09-kho-lien-tien-trinh-boi-canh.md) | ⚠ **Bối cảnh**, không phải thiết kế hiện hành - đọc 12 và 13 trước. Giữ vì **mục 2.7** (phạm vi một máy) và **mục 8** (19 hướng đã bác) vẫn đang được trích như luật |
| [`10-da-tien-trinh.md`](thiet-ke/10-da-tien-trinh.md) | **Lớn nhất.** `main.py`, cấu hình, supervisor, ba hạng adapter, chia tải từng loại |
| [`11-bus-lien-tien-trinh.md`](thiet-ke/11-bus-lien-tien-trinh.md) | `ProcessLink` - bộ nhớ chung, mỗi tiến trình một vùng ghi riêng |
| [`12-kho-refdata.md`](thiet-ke/12-kho-refdata.md) | `RefData` - dữ liệu **có nguồn bền vững**, hai bản đổi con trỏ |
| [`13-kho-store-lmdb.md`](thiet-ke/13-kho-store-lmdb.md) | `Store` trên LMDB - dữ liệu **không có nguồn bền vững** |
| [`14-api-adapter.md`](thiet-ke/14-api-adapter.md) | Đổi API adapter một lượt: định danh, cấu hình, hạng nhân bản, vòng đời |

## `phien-ban/` - từng bản làm gì

| | |
|---|---|
| [`0.3-ke-hoach.md`](phien-ban/0.3-ke-hoach.md) | Hardening, đóng kín mảng gRPC |
| [`0.4-ke-hoach.md`](phien-ban/0.4-ke-hoach.md) | Starter `cache` + `redis`, danh tính peer mTLS |
| [`0.5-ke-hoach.md`](phien-ban/0.5-ke-hoach.md) | Phạm vi: kiểm toán + MQTT + file |
| [`0.5-ke-hoach-thi-cong.md`](phien-ban/0.5-ke-hoach-thi-cong.md) | Bản chi tiết theo thứ tự code |
| [`0.6-ke-hoach.md`](phien-ban/0.6-ke-hoach.md) | Gỡ `dependency-injector`, dynamic interface binding |
| [`0.7-ke-hoach.md`](phien-ban/0.7-ke-hoach.md) | Fieldbus công nghiệp: Modbus TCP + OPC UA |
| [`0.7.1-ket-qua.md`](phien-ban/0.7.1-ket-qua.md) | Server-stream có kiểu, đợt 2 vá bảo mật, gỡ phụ thuộc khái niệm, JWT keyset |
| [`0.7.2-ket-qua.md`](phien-ban/0.7.2-ket-qua.md) | JWT `kid`, sàn dependency, F14/F15/F17, WebSocket |
| [`0.8-ban-giao-thiet-ke.md`](phien-ban/0.8-ban-giao-thiet-ke.md) | Bàn giao cuối buổi thiết kế, bảy cạm bẫy |
| [`0.8-chot-thiet-ke.md`](phien-ban/0.8-chot-thiet-ke.md) | Hai buổi 08-18 và 08-19 chốt những gì, và bác những gì |
| [`0.8-ke-hoach-thi-cong.md`](phien-ban/0.8-ke-hoach-thi-cong.md) | Kế hoạch bảy giai đoạn |
| [`0.8-ket-qua-thi-cong.md`](phien-ban/0.8-ket-qua-thi-cong.md) | Kết quả tám giai đoạn, kèm đối chứng từng bản vá |

## `kiem-toan/` - có gì hỏng

| | |
|---|---|
| [`0.5.md`](kiem-toan/0.5.md) | Đợt đầu, chỉ ghi nhận không vá |
| [`0.6.md`](kiem-toan/0.6.md) | Code mới của 0.6.0-0.6.2. Bài học: kiểm *"có test cho X"* bằng Grep nội dung, không Glob tên file |
| [`0.7-truoc-phat-hanh.md`](kiem-toan/0.7-truoc-phat-hanh.md) | Đợt đầu soi **lớp đóng gói** và **tính đúng đắn của tài liệu** - hai lớp test không chạm tới |
| [`0.7-bao-mat.md`](kiem-toan/0.7-bao-mat.md) | Hỏi *"kẻ tấn công làm được gì"*. 24 phát hiện, 12 PoC, phủ cả 31 app |
| [`0.7-bao-mat-ke-hoach-va.md`](kiem-toan/0.7-bao-mat-ke-hoach-va.md) | Vá cái gì, thứ tự nào, kiểm chứng ra sao |
| [`0.7-bao-mat-cho-quyet.md`](kiem-toan/0.7-bao-mat-cho-quyet.md) | Phần còn chờ chủ dự án quyết |
| [`0.8-truoc-phat-hanh.md`](kiem-toan/0.8-truoc-phat-hanh.md) | Bảy phát hiện, ba chặn phát hành. **Cả ba nằm ở chỗ công cụ đo nói dối** |
| [`0.8.1-ket-qua-do-tren-linux.md`](kiem-toan/0.8.1-ket-qua-do-tren-linux.md) | ⭐ **Đợt uvloop đo trên Linux.** Ba phép đo ĐẠT; phép thứ tư **kết luận rõ, và nó lật một giả định của chính bản 0.8.1** (uvloop làm REST chậm ~10%). Sửa hai test lỗi thời - **ca thứ ba của "lỗi máy phát triển không thể thấy"** |
| [`0.8.2-ket-qua-do-tren-linux.md`](kiem-toan/0.8.2-ket-qua-do-tren-linux.md) | ⭐ **Chuyến chạy thử `0.8.2` trước phát hành.** Bộ test khớp tổng Windows; tìm ra **một lỗi thật chưa ai thấy** - dòng log khởi động khai `0 HTTP route(s)` với **mọi** ứng dụng Xime, vì `include_router()` của fastapi 0.141 không còn trải route ra `app.routes`. **14 test canh đã có đều xanh y nguyên** vì chúng đi đường tắt `add_api_route()`. Kèm một lỗi trong chính bộ benchmark |
| [`backlog-sua-loi.md`](kiem-toan/backlog-sua-loi.md) | ⚠ **Không còn mục nào mở.** Đừng đọc để tìm việc |

## `ghi-chep/` - một ca, một bài học

| | |
|---|---|
| [`go-phu-thuoc-khai-niem.md`](ghi-chep/go-phu-thuoc-khai-niem.md) | Gỡ `PEER_APP_ID`. *Framework không được phụ thuộc khái niệm của một người dùng cụ thể* |
| [`jwt-keyset-va-trung-tinh.md`](ghi-chep/jwt-keyset-va-trung-tinh.md) | Cùng khuôn nhưng **ngược chiều**: `KeyContext` sai vì nó biết **quá ít** về JWT |
| [`phu-thuoc-bac-cau.md`](ghi-chep/phu-thuoc-bac-cau.md) | Ba phụ thuộc dùng mà không khai |
| [`loi-dua-scheduler.md`](ghi-chep/loi-dua-scheduler.md) | `create_task` chưa chạy dòng nào. **Mock không mang ngữ nghĩa của thứ nó thay thế** |
| [`yeu-cau-server-stream.md`](ghi-chep/yeu-cau-server-stream.md) | Yêu cầu từ data-service và user-service, đã làm ở 0.7.1 |
| ⭐ [`dac-tinh-python-va-vi-tri-framework.md`](ghi-chep/dac-tinh-python-va-vi-tri-framework.md) | **Quy luật vượt biên C/Rust** (thư viện Rust chỉ có lãi khi vòng lặp nằm BÊN TRONG nó - Pydantic **793 ns/bản ghi** so với viết tay **230 ns**) · ước lượng so Java/Spring, tỉ lệ phụ thuộc **N** chứ không phụ thuộc cách viết code · **nguyên tắc "không phụ thuộc khái niệm ngoài" đo lại: 0 lần trong mã thực thi** · vị trí giữa framework cùng họ, và **Nameko chết từ 2021** |
| [`lam-viec-voi-nhom.md`](ghi-chep/lam-viec-voi-nhom.md) | Repo này giao tiếp với nhóm chat thế nào |
| [`benchmark-hieu-nang.md`](ghi-chep/benchmark-hieu-nang.md) | ⭐ **Benchmark đầu tiên của framework, bốn tầng.** uvloop lãi ở loop trần nhưng **làm chồng web chậm ~10%** · Xime = **41%** thông lượng của ASGI trần · cụm nhiều tiến trình mở rộng **gần tuyến tính (3.88x với 4)**. Mục 7 là bài học về **cách đo**, phần không lỗi thời theo máy |

## `da-phu-dinh/` - THIẾT KẾ bị lật

⛔ **Không file nào ở đây mô tả hiện trạng.** Đọc để biết *hồi đó định thiết kế thế nào và
vì sao bỏ* - phần lý do mới là phần đáng giữ, nó chặn người sau đề xuất lại một hướng đã bác.

⚠ Ranh giới với [`nhap/`](nhap/): ở đây nội dung **SAI** so với hiện tại. Bên kia nội dung
**vẫn đúng**, chỉ là việc đã xong nên không ai cần nữa. Xếp nhầm chỗ thì người sau hoặc tin
một thứ đã bị lật, hoặc bỏ qua một thứ vẫn dùng được.

| | Bị lật bởi |
|---|---|
| [`ke-hoach-0.8-ban-dau.md`](da-phu-dinh/ke-hoach-0.8-ban-dau.md) | Buổi thiết kế 2026-08-16 lật phần lớn |
| [`multi-server-va-dependency-order.md`](da-phu-dinh/multi-server-va-dependency-order.md) | **Phần 1** bị 0.8 lật (bỏ hẳn đối số cổng trong code). ⚠ **Phần 2** `dependency.order()` thì vẫn đúng và đang chạy |
| [`peer-app-id-tu-san-cert.md`](da-phu-dinh/peer-app-id-tu-san-cert.md) | 0.7.1 gỡ hẳn tính năng |
| [`vuong-mac-scheduler-trong-test.md`](da-phu-dinh/vuong-mac-scheduler-trong-test.md) | Chẩn đoán **sai nguyên nhân**, xem `ghi-chep/loi-dua-scheduler.md` |

## `nhap/` - giấy nháp, việc đã xong

Không sai, chỉ hết vai. Giữ vì đôi khi cần tra *"hồi đó làm theo thứ tự nào"*.

⚠ **File bàn giao giữa hai máy thuộc về đây, không thuộc gốc `docs/`.** Chúng là dữ
liệu **tạm**: đúng trong một chuyến đo rồi hết vai, và kết luận thật của chúng luôn
được chép sang `kiem-toan/`. Để ở gốc thì chúng trông ngang hàng với tài liệu tra cứu.

| | |
|---|---|
| [`tien-do-grpc-codefirst.md`](nhap/tien-do-grpc-codefirst.md) | Checklist thi công gRPC code-first, xong 100%. Cây mã trả lời chính xác hơn và không bao giờ lỗi thời |
| [`tien-do-socket-adapter.md`](nhap/tien-do-socket-adapter.md) | Như trên, cho socket adapter |
| [`ban-do-tai-lieu-cu.md`](nhap/ban-do-tai-lieu-cu.md) | Bản đồ tài liệu phẳng cũ, thay bằng chính file README này |
| [`ban-giao-cho-phien-windows.md`](nhap/ban-giao-cho-phien-windows.md) | **Chiều về của chuyến Linux 0.8.0** (2026-08-21): 80 file, 629/629 khớp. Kết luận đã vào `kiem-toan/0.8-*`; giữ để tra trình tự |
| [`ban-giao-cho-phien-linux-0.8.1.md`](nhap/ban-giao-cho-phien-linux-0.8.1.md) | **Đề bài chuyến uvloop 0.8.1** - đã thi hành xong. ⚠ Mục 3.2 của nó (cách chạy test dưới uvloop) từng **hỏng và xanh giả**, đã vá |
| [`ban-giao-cho-phien-windows-0.8.1.md`](nhap/ban-giao-cho-phien-windows-0.8.1.md) | **Chiều về của chuyến đó**: 25 file mới + 5 sửa, 660/660 khớp. Kết quả đã vào [`kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](kiem-toan/0.8.1-ket-qua-do-tren-linux.md) |

## `sap-toi/` - chưa làm

| | |
|---|---|
| [`wishlist-tinh-nang.md`](sap-toi/wishlist-tinh-nang.md) | Danh sách ý tưởng, **không phải cam kết** |
| [`lo-hong-tai-lieu-nguoi-dung.md`](sap-toi/lo-hong-tai-lieu-nguoi-dung.md) | Sổ theo dõi lỗ hổng `docs/` (tài liệu **người dùng**). Đo được: **146/309 tên công khai không xuất hiện lấy một lần**, `core/exception` thiếu **18/19**, `docs/` **không có mục lục**. 21 mục chia bốn nhóm để chủ dự án chọn |
| [`tang-toc-uvicorn-uvloop.md`](sap-toi/tang-toc-uvicorn-uvloop.md) | ⛔ **NGOẠI LỆ của thư mục này: đã CODE và đã ĐO XONG** (0.8.1, 2026-08-22) - còn nằm ở `sap-toi/` vì dời file là quyết định cấu trúc thuộc chủ dự án. Đọc **mục 5b** cho kết quả bốn phép đo. ⚠ Mục 4.3 và việc số 3 của bảng mục 10 **đã hết đúng** (0.8.0 hợp nhất còn một đường vào `asyncio.run`) |
