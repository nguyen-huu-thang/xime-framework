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
| Kế hoạch vá kiểm toán | [`sap-toi/ke-hoach-va-loi-kiem-toan-framework.md`](sap-toi/ke-hoach-va-loi-kiem-toan-framework.md): Bước 0–6 đã commit e5a5b5c; Windows/Linux đã kiểm theo phạm vi, còn SIGTERM và hạ tầng thật |
| **Kết quả Linux Bước 7 đã nhận (2026-10-17)** | [`kiem-toan/nghiem-thu-linux-framework.md`](kiem-toan/nghiem-thu-linux-framework.md): bốn full suite 2.898/12/0, nhập ba sàn; còn SIGTERM/S3/Certbot/live. Con trỏ gốc: [`../../KIEM-THU-LINUX.md`](../../KIEM-THU-LINUX.md) |
| Luật code của repo này | [`../rules/`](../rules/) |
| ✅ Đợt đo uvloop 0.8.1 trên Linux (**đã xong**) | [`kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](kiem-toan/0.8.1-ket-qua-do-tren-linux.md); đề bài gốc ở [`ban-giao-cho-phien-linux-0.8.1.md`](nhap/ban-giao-cho-phien-linux-0.8.1.md) |
| ✅ Chạy thử `0.8.2` trên Linux (**đã xong** 2026-08-25) | [`kiem-toan/0.8.2-ket-qua-do-tren-linux.md`](kiem-toan/0.8.2-ket-qua-do-tren-linux.md) - 1 lỗi framework đã vá + 1 lỗi bộ benchmark đã vá |
| ⭐⭐ Khoá `accept()` + cửa sổ memset `pack_into` trên Linux (**đã xong** 2026-09-01) | [`kiem-toan/ket-qua-do-tren-linux-2026-09-01.md`](kiem-toan/ket-qua-do-tren-linux-2026-09-01.md) - khoá accept vô hại & lỗi gốc không tái hiện (đúng dự đoán); nhưng **cửa sổ memset CÓ dính trên Linux** (0,0088%-0,0267%, hẹp hơn Windows ~30-100 lần chứ không phải bằng 0) |
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
| [`07-tls-web-adapter.md`](thiet-ke/07-tls-web-adapter.md) | Tài liệu lịch sử của TLS 0.6.3, không phải hợp đồng hiện tại. Cấu hình/reload hiện hành: `webserver.ssl` và mục cấu hình người dùng |
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
| [`tls-web-va-cau-hinh-moi-truong.md`](kiem-toan/tls-web-va-cau-hinh-moi-truong.md) | Kiểm chứng 2026-10-15: hai vấn đề P2 được xác nhận; nhận định fingerprint được đính chính bằng cụm hai worker thật; 132 test ở Uvicorn 0.47.0 và 42 test TLS ở 0.48.0 |
| [`kiem-toan-framework-va-dependency.md`](kiem-toan/kiem-toan-framework-va-dependency.md) | Kiểm toán 2026-10-17 và nghiệm thu F1–F6, 16 advisory, mypy/API; Bước 0–6 đã commit e5a5b5c; kết quả theo nhóm giữ riêng |
| [`nghiem-thu-windows-framework.md`](kiem-toan/nghiem-thu-windows-framework.md) | Bước 7: hai bộ dependency full 2.881 passed mỗi bộ; 12 consumer 6.557 passed/8 skip; 24 nhánh config, 12 đồ thị DI, wheel/sdist/cài wheel trắng đạt; Linux chưa kiểm |
| [`doi-chieu-nghiem-thu-ke-hoach.md`](kiem-toan/doi-chieu-nghiem-thu-ke-hoach.md) | Đối chiếu từng nhóm yêu cầu với source/test/log; hậu kiểm F4/F7, hai bộ full cuối 2.884 passed; các cổng Linux/tài nguyên thật vẫn ghi chưa kiểm |
| [`jwt-extra-thieu-crypto.md`](kiem-toan/jwt-extra-thieu-crypto.md) | F7 phát hiện bằng wheel sạch: bổ sung crypto runtime cho extra jwt; wheel cũ 12/15 ca lỗi, wheel mới 15/15 đạt ở mỗi bộ sàn/resolver, không bị dev che khuất |
| [`phan-loai-api-cong-khai.md`](kiem-toan/phan-loai-api-cong-khai.md) | 152 lượt export thiếu ở EN/VN: 94 API/kiểu, 54 hạ tầng, 4 alias; từng mục có vai trò/lý do; coverage thô sau bổ sung 0/317 thiếu mỗi ngôn ngữ |
| [`backlog-sua-loi.md`](kiem-toan/backlog-sua-loi.md) | F1–F6 đã vá/commit, mypy 0 lỗi và API đã phân loại; Windows/consumer đã kiểm, cổng Linux còn mở |

## `ghi-chep/` - một ca, một bài học

| | |
|---|---|
| [`go-phu-thuoc-khai-niem.md`](ghi-chep/go-phu-thuoc-khai-niem.md) | Gỡ `PEER_APP_ID`. *Framework không được phụ thuộc khái niệm của một người dùng cụ thể* |
| [`jwt-keyset-va-trung-tinh.md`](ghi-chep/jwt-keyset-va-trung-tinh.md) | Cùng khuôn nhưng **ngược chiều**: `KeyContext` sai vì nó biết **quá ít** về JWT |
| [`phu-thuoc-bac-cau.md`](ghi-chep/phu-thuoc-bac-cau.md) | Ba phụ thuộc dùng mà không khai |
| [`loi-dua-scheduler.md`](ghi-chep/loi-dua-scheduler.md) | `create_task` chưa chạy dòng nào. **Mock không mang ngữ nghĩa của thứ nó thay thế** |
| ⭐⭐ [`windows-shared-listener-accept-treo.md`](ghi-chep/windows-shared-listener-accept-treo.md) | **Đã tìm ra nguyên nhân gốc, tái hiện được NGOÀI Xime và NGOÀI uvicorn** (CPython thuần, 108 module). Windows giữ tiến trình thua cuộc đua lại **bên trong `accept()`**, mà `accept()` chạy trong callback event loop nên cả loop đứng. ⭐ **Thời gian kẹt bám theo timeout của CLIENT** (5s -> 5,4s · 20s -> 20,3s · 40s -> 40,5s), kết nối mới **không** cứu được nó, nên *"im 10 giây"* chỉ là lúc watchdog hết kiên nhẫn chứ không phải mức nghiêm trọng thật. Cờ non-blocking đặt đúng và **có** hiệu lực → **không có mẹo vá ở tầng Python**. `uvicorn --workers >= 2` trên Windows cũng dính (đo 1/2/3/4 worker) và **không thể tự phát hiện** vì `always_pong` chạy trên thread daemon. ⭐⭐ **Mục 5b, phép so ngôn ngữ: Node `cluster` cùng máy cùng mô hình, hơn 3.600 request, 0 lần treo** - vì libuv dùng IOCP/`AcceptEx`. Mà **Python KHÔNG dùng được IOCP với socket kế thừa** (`WinError 87` ở `CreateIoCompletionPort`), nên nó bị dồn vào đúng một đường và đường đó có lỗi. ⭐ **Mục 5c là thang MƯỜI BẬC** thu hẹp từng thành phần: **không phải lỗi riêng của asyncio** (Python thuần không asyncio cũng treo), asyncio chỉ làm tần suất tăng 10 lần (22 so với 2); bốn giả thuyết đã bị bác bằng đo. ✅ **Accept mutex kiểu nginx chữa được**: 7 lần treo -> **0**, chia tải vẫn đều 388/401/443. Bộ tái hiện mười bản: [`scripts/windows-accept/`](../scripts/windows-accept/README.md). ⭐ Mục 11 ghi **ba lỗi phương pháp** đã mắc, trong đó nặng nhất: **bản đối chứng in "0 lần treo" ba lần liên tiếp trong khi nó đang hỏng và trả lỗi cho 90% request** - luật rút ra là *kiểm đối chứng phục vụ được đã, rồi mới đọc số của nó* |
| ⭐⭐ [`loi-nhip-tim-o-quay-ve-khong-2026-08-31.md`](ghi-chep/loi-nhip-tim-o-quay-ve-khong-2026-08-31.md) | ✅ **ĐÃ TÌM RA NGUYÊN NHÂN VÀ VÁ 2026-09-01** (dòng cũ ghi *"chưa tìm ra, ba nghi phạm còn sống"* đã lỗi thời - cả ba đều bị loại). Lỗi **thứ hai** của đợt 30-31/8, độc lập với lỗi `accept()` ở dòng trên; hai lỗi **dồn vào nhau** nên triệu chứng chồng lấp, và chính chủ dự án là người tách chúng ra. ⭐⭐ **Thủ phạm: `struct.pack_into` XOÁ VÙNG ĐÍCH VỀ 0 TRƯỚC KHI GHI** (nó phải làm vậy để byte đệm luôn bằng 0). Giữa hai tiến trình cửa sổ đó nhìn thấy được, mà `NEVER = 0.0` nghĩa là *"chưa bao giờ vỗ nhịp"* - nên cha đọc trúng nó thì **giết một tiến trình đang hoàn toàn khoẻ mạnh**. Đo 34,6 triệu lượt đọc giữa hai tiến trình: `pack_into` cho **1.658.361 lượt thấy toàn số 0 (4,79%)**, gán slice cho **0**. ⭐⭐ **Lỗ hổng KHÔNG chỉ ở watchdog**, và chỗ nặng nhất không phải chỗ phát hiện ra nó: `refdata.write_generation` cũng vậy, mà ở đó `NEVER_PUBLISHED = 0` nên `read()` trả `None` = *"bảng chưa ai publish"* - với bảng `jwt-keys` đó là **một request hợp lệ nhận 401**, im lặng; `refdata.write_segments` thì **ném `RefDataTornError`**, đúng *"exception msgpack ngẫu nhiên vài tháng một lần"* mà `_refdata.py` đã lo trong chú thích của chính nó. Vá bằng **một chỗ quyết định** `core/_mp.py::ghi_o` (đúng bài học C4/C6), **giữ nguyên** `pack_into` ở ba hàm dựng vùng nhớ vì lúc đó chưa ai attach. ⭐ **Vì sao sống lâu: GIL che mất cửa sổ** - cùng phép đo giữa hai *thread* cho **0/10,5 triệu**; đây là ca thứ tư của khuôn *"lỗi mà phép đo hiện tại không thể thấy"* sau C4, C5 và `test_linux_never_switches`, chỉ khác trục (ranh giới **tiến trình** thay vì hệ điều hành). ⭐ Bài học mang đi được: **số 0 không phải giá trị trung tính trong một bố cục nhị phân** - chọn nó làm sentinel là chọn đúng giá trị mà mọi phép ghi dở dang, mọi vùng mới cấp phát và mọi lần memset đều đi qua. ⭐ Cách tìm ra: một **bảng tương quan ba dòng** (56 giết/6 ca · **1 giết/1 ca** · 0/0) loại nghi phạm số một trong hai phút sau khi đọc mã ba lượt không ra - dòng giữa chứng minh `reset()` chưa hề chạy. Kèm hai khuôn đo đáng giữ: ép **214 lần giết trong 12 phút** trên app thật (ra 0 ca, loại giả thuyết *"vòng sinh-giết"*) và **16 cụm tối giản song song** (tái hiện 4 ca trong 10 phút, loại sạch mọi tầng phía trên trong một lần) |
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
| ⭐⭐ [`ban-giao-cho-phien-linux-accept-treo.md`](nhap/ban-giao-cho-phien-linux-accept-treo.md) | ✅ **ĐÃ THI HÀNH 2026-09-01** - kết quả ở [`kiem-toan/ket-qua-do-tren-linux-2026-09-01.md`](kiem-toan/ket-qua-do-tren-linux-2026-09-01.md). Đề bài cho chuyến Linux, có BA phần. ⭐ **Mục 0a (2026-09-01) là chỗ đọc đầu tiên**: đường đi của tệp cả hai chiều - chép từ ổ dùng chung vào ext4 (⛔ **đừng chạy pytest thẳng trên NTFS mount**: nó không giữ bit quyền POSIX, nên 9 test `lmdb`/`storage` đỏ **vì chỗ đặt tệp** chứ không vì mã, và trông y hệt một hồi quy thật), đối chiếu bằng bảng kê khai `chuyen-may/ke-khai.py` với **ba kết cục** (`KHỚP` · `LỆCH` · `CHƯA KẾT LUẬN ĐƯỢC` - mã 2 tồn tại để một bản chép thiếu không đọc thành "khớp"), ghi kết quả vào đâu, và đóng gói `.zip` chiều về (⛔ **chỉ gửi kết quả, đừng gửi cả repo** - bên kia đã có mã). ⭐⭐ **Mục 0c: phần C là phần ƯU TIÊN CAO NHẤT**, vì nó là phần duy nhất có thể tìm ra một lỗi **đang cắn production**: cửa sổ memset của `pack_into` **không** phải chuyện riêng của Windows (`s_pack_into` là mã C chung của CPython), mà trên Linux thì `RefData` chạy thật, nên lỗ *"một request hợp lệ nhận 401"* nhiều khả năng đang có ở đó. Kèm **C2 là đối chứng ngược**: gỡ bản vá phải ra ít nhất 2 đỏ; **không** đỏ nghĩa là Linux KHÔNG dính, và đó là một phát hiện lớn phải báo về ngay. **Mục 0b: phần B** chứng minh khoá accept vô hại trên Linux - không phải thủ tục, vì repo này đã bị cắn **ba lần** bởi lỗi máy Windows không thể thấy (C4, C5, `test_linux_never_switches`). **Phần A** (lỗi accept gốc) đã đoán trước kết quả, bỏ được nếu hết giờ. ⚠ Chuyển bằng `cp -r`, **không** `git clone` - `.claude/` bị gitignore nên clone bỏ lại cả bộ script lẫn chính tệp này |

## `sap-toi/` - chưa làm

| | |
|---|---|
| [`wishlist-tinh-nang.md`](sap-toi/wishlist-tinh-nang.md) | Danh sách ý tưởng, **không phải cam kết** |
| [`yeu-cau-reload-tls-web.md`](sap-toi/yeu-cau-reload-tls-web.md) | Yêu cầu chủ dự án 2026-10-11: reload cert HTTPS từ file mà không restart toàn bộ ứng dụng; nghiên cứu cả tự theo dõi file và nhận thông báo từ chương trình khác; cách hiện thực để phiên framework quyết định |
| [`ke-hoach-reload-tls-web-va-management.md`](sap-toi/ke-hoach-reload-tls-web-va-management.md) | Kế hoạch + nghiệm thu Windows cho commit `2ad5274`: reload TLS, listener quản lý loopback và cấu hình môi trường một file. PyPI vẫn ở 0.8.3; Linux/VPS chưa đo. Hậu kiểm: [TLS/config](kiem-toan/tls-web-va-cau-hinh-moi-truong.md) |
| [`ke-hoach-va-loi-kiem-toan-framework.md`](sap-toi/ke-hoach-va-loi-kiem-toan-framework.md) | Chỉ thị làm liền đã thi hành: Bước 0–6 commit e5a5b5c; Bước 7 Windows đã kiểm; dừng ở cổng Linux, không nâng số/phát hành |
| [`lo-hong-tai-lieu-nguoi-dung.md`](sap-toi/lo-hong-tai-lieu-nguoi-dung.md) | Sổ thiếu tài liệu người dùng: đã có mục lục và API reference song ngữ, coverage 0/317 thiếu; giữ snapshot cũ và các đề xuất trang/chủ đề ngoài phạm vi Bước 6 |
| [`tang-toc-uvicorn-uvloop.md`](sap-toi/tang-toc-uvicorn-uvloop.md) | ⛔ **NGOẠI LỆ của thư mục này: đã CODE và đã ĐO XONG** (0.8.1, 2026-08-22) - còn nằm ở `sap-toi/` vì dời file là quyết định cấu trúc thuộc chủ dự án. Đọc **mục 5b** cho kết quả bốn phép đo. ⚠ Mục 4.3 và việc số 3 của bảng mục 10 **đã hết đúng** (0.8.0 hợp nhất còn một đường vào `asyncio.run`) |
| ⭐ [`bao-cao-loi-windows-accept-ra-ngoai.md`](sap-toi/bao-cao-loi-windows-accept-ra-ngoai.md) | **Bốn bên nên báo lỗi `accept()` Windows, xếp theo thứ tự nên làm**: nội bộ workspace (gửi được ngay) · uvicorn (đủ hồ sơ, thiếu xác nhận máy thứ hai) · CPython (cần tra issue cũ + bản tái hiện tối giản hơn) · Microsoft (chưa đủ, cần bản C phục vụ bằng thread). Có sẵn tiêu đề, dàn bài và bảng đo cho từng bên. ⛔ Mục 5 liệt kê **năm câu KHÔNG được viết** - đó là năm kết luận đã bị lật trong lúc điều tra, đừng chở lại ra ngoài |
| [`bao-ve-ma-nguon-va-runtime-python.md`](sap-toi/bao-ve-ma-nguon-va-runtime-python.md) | Con trỏ local sang tài liệu private ở `D:\code\xime\thiết kế private\bao-ve-ma-nguon-va-runtime-python.md`; không chép nội dung private vào repo/framework public |
