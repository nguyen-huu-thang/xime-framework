# Kế hoạch sửa lịch Trust, dữ liệu mẫu và logging Xime

> **Trạng thái:** G1–G4 đã triển khai; đã tiếp nhận Linux và kiểm lại Windows ngày 2026-10-19. Hai full Windows/Python 3.12 và 3.14 đều 2965 passed/33 skipped/1 deselected; Linux/Python 3.13.5 có bốn full 2975/12 trước bổ sung pointer Windows. Kết quả hiện tại ở 7.6 và `NGHIEM-THU-LOGGING.md`; 7.4–7.5 giữ lịch sử. Nợ consumer giữ riêng; chưa commit/phát hành/VPS.
> **Thuộc bản:** framework phát triển tại `c76b6cd`, metadata vẫn 0.8.3;
> chưa chọn phiên bản phát hành cho đợt sửa này.
> **Thay cái gì:** kế hoạch đầu tiên cho các phát hiện từ log VPS và khảo sát source
> trong phiên này; không thay kế hoạch kiểm toán framework ngày 17/10.
> **Bị thay bởi:** chưa có.

## 1. Phạm vi đã chốt và cách sử dụng kế hoạch

Chủ dự án yêu cầu lập kế hoạch trước, duyệt rồi mới code. Kế hoạch chia thành **4 đợt**,
làm theo thứ tự **Trust → dữ liệu mẫu → logging file → log gRPC kèm IP**.
Chủ dự án đã duyệt lần lượt Đợt 1–4; G1–G3 đã xong ở phạm vi mã nguồn và kiểm chứng Windows. G4a cũ không đạt restore; chủ dự án sau đó duyệt tiếp thiết kế pipe sống suốt đời process. Đã triển khai/kiểm Windows theo 7.5, giữ cổng Linux riêng.
Mỗi đợt sau vẫn có điểm dừng, báo cáo và diff riêng; không tự chuyển tiếp khi chưa được duyệt.

**Chỉ sửa trong các repo mã nguồn gốc dưới `D:\code\xime`.** Không thay đổi
`D:\code\xime-prod\build`, không tạo/copy gói triển khai sang thư mục khác,
không cài lại môi trường VPS, không sửa file hay khởi động lại dịch vụ trên VPS.
Phần đóng gói và triển khai do chủ dự án làm thủ công sau này.

Trong giai đoạn lập kế hoạch không sửa source, YAML ứng dụng, dependency, DB hay
service đang chạy. Sau khi được duyệt, G1/G2 chỉ sửa mã nguồn, test, file cấu hình mẫu
và công cụ kiểm tra chỉ đọc. Test dùng DB cô lập; không ghi DB ứng dụng thật. Các đợt
kế tiếp tiếp tục giới hạn như trên.

`share-live-test-key` **được loại khỏi phạm vi theo yêu cầu chủ dự án**.
Không dọn khóa, không thay chính sách tin cậy của Trust/Identity trong đợt này.

### 1.1. Bốn đầu ra cuối cùng

1. Các service đồng bộ khóa đúng nhịp thiết kế; bỏ lượt thành công bị lặp khi lên.
2. Kho/Sổ thu chi nạp mẫu được trên baseline mặc định hợp lệ, giữ dữ liệu thật an toàn.
3. Xime hỗ trợ logging file trực tiếp, opt-in, mức chi tiết độc lập với terminal,
   có xoay file và hoạt động đúng khi nhiều process.
4. Xime thu được sự kiện **gRPC server bắt tay TLS thất bại** kèm địa chỉ nguồn,
   đưa thành Python `LogRecord` và đi qua hệ logging ở đầu ra 3; có công tắc riêng.

### 1.2. Repo được phép sửa sau khi duyệt

| Repo nguồn | Phần việc dự kiến | HEAD khảo sát ngày 18/10 |
|---|---|---|
| `xime framework` | Logging, bộ thu native gRPC, API/checker/docs/test liên quan | `c76b6cd` |
| `Application Layer/dental` | Trust, cấu hình opt-in logging, test | `2585a35` |
| `Application Layer/nha-hang` | Trust, cấu hình opt-in logging, test | `45bc69b` |
| `Application Layer/nha-tro` | Trust, cấu hình opt-in logging, test | `ceae065` |
| `Application Layer/shop-hoa-qua-tang` | Trust, thống nhất khóa cấu hình, logging, test | `3d28750` |
| `Service ngang/crm` | Tránh Trust sync trùng startup, logging, test | `e641a74` |
| `Service ngang/giao-viec` | Tránh Trust sync trùng startup, logging, test | `f4e9247` |
| `Service ngang/kho` | Trust, dữ liệu mẫu, logging, test | `4a9452b` |
| `Service ngang/nhan-su-cham-cong` | Tránh Trust sync trùng startup, logging, test | `abab8bb` |
| `Service ngang/so-thu-chi` | Trust, dữ liệu mẫu, logging, test | `a54eb69` |
| `Base Platform/data` | Tránh Trust sync trùng startup, logging, test | `fb673d4` |
| `Base Platform/notification` | Tránh Trust sync trùng startup, phối hợp logger JSON riêng | `9786604` |

Đường dẫn Python của 4 app dọc và 5 service ngang nằm dưới `backend/`;
Data/Notification có `app/` và `resources/` ngay trong repo.
Các worktree trên sạch lúc khảo sát; kiểm lại trước từng đợt, không dùng bảng này
để ghi đè công việc xuất hiện sau đó. Template SaaS là tài liệu tham chiếu,
không tự mở rộng sửa sang các bản clone khác. Không sửa Java, frontend,
contract liên service, Trust hoặc Identity để thực hiện bốn đầu ra này.

## 2. Căn cứ và giới hạn bằng chứng

- Đã đọc **11 log**, 8.872 dòng, khoảng 8 giờ chạy. Có **397 lượt đồng bộ khóa
  thành công** được log; 381 lượt thuộc 4 app dọc. Đây không phải phép đếm toàn bộ
  RPC mà Trust nhận, và các dòng `Job ... completed successfully` không phải đều gọi Trust.
- Nha khoa 96 lượt; Nhà hàng/Nhà trọ/Shop hoa mỗi app 95. Nhịp là 300 giây.
  Năm service ngang mỗi repo 2 lượt ở startup, nhịp khai báo 432.000 giây.
  Data/Notification mỗi service 3 lượt, nhịp khai báo 6 giờ.
- Cả 11 service đều có lượt sync trong startup, rồi lượt scheduler gần như ngay lập tức.
- Kho nạp mẫu lỗi tại `uq_warehouse_org_code`, mã `KHO-CHINH`;
  Sổ thu chi lỗi tại `uq_cash_book_org_name`, tên `Tiền mặt`.
- Logging Xime hiện chỉ có mặc định console. Notification tự cài `StreamHandler`
  và JSON formatter. Chưa có `FileHandler`/rotation opt-in trong Xime.
- Probe cô lập **Windows/Python 3.14, grpcio 1.81.0** cho thấy
  `GRPC_TRACE=handshaker` có cả `endpoint_peer_address`, `endpoint_local_address`
  và lỗi TLS trong dòng handshaker; HTTP vào cổng TLS và thiếu client cert đều
  không đi tới RPC interceptor. Chưa đo bộ thu tích hợp Xime hoặc Linux.

### 2.1. Tài liệu phải đối chiếu khi thi công

- [Ghi nhận đổi 300 giây sang 5 ngày](../../../../Application%20Layer/saas-foundation/.claude/docs/loc-activate-at-tren-duong-verify-2026-08-25.md)
  — đường dẫn workspace chính xác: `Application Layer/saas-foundation/.claude/docs/loc-activate-at-tren-duong-verify-2026-08-25.md`, dòng 29–30.
- `Base Platform/Trust/.claude/docs/key-rotation.md`: timeline, preload và khóa còn hạn.
- `Base Platform/data/.claude/docs/jwt-dung-co-che-framework-2026-09-01.md`:
  provider chỉ đọc RAM, primary nạp DB trước rồi đồng bộ Trust; Data giữ nhịp 6 giờ.
- `Service ngang/.claude/docs/27-du-lieu-mau-toan-erp-2026-09-09.md`:
  trạng thái `CHUA → DANG_MAU → THAT`, phân biệt lazy-init với dữ liệu người nhập.
- Framework: `xime/core/config/runtime.py`, `core/bootstrap/application.py`,
  `starters/scheduler/_runner.py`, `adapters/grpc/_adapter.py`, `tls/_credentials.py`.
- gRPC chính thức:
  [trace flags](https://github.com/grpc/grpc/blob/v1.81.0/doc/trace_flags.md),
  [environment variables](https://github.com/grpc/grpc/blob/v1.81.0/doc/environment_variables.md),
  [Python AsyncIO API](https://grpc.github.io/grpc/python/grpc_asyncio.html).

Đường dẫn trong các mục dưới tính từ repo nguồn tương ứng. Tài liệu lịch sử không
thay việc kiểm lại source, dependency và lifecycle trước khi sửa.

## 3. Thứ tự và điểm dừng

| Đợt | Làm gì | Điều kiện bàn giao | Điểm dừng |
|---|---|---|---|
| **1** | Lịch Trust và bỏ sync startup trùng | Đúng nhịp, một sync startup thành công, failover vẫn lấy được khóa | **G1:** báo cáo 11 consumer, dừng chờ chủ dự án |
| **2** | Nạp dữ liệu mẫu Kho/Sổ thu chi | Qua PostgreSQL cô lập: baseline mặc định, dữ liệu thật, rollback, cạnh tranh | **G2:** báo cáo hai repo và kết luận nhu cầu DB, dừng |
| **3** | Logging file chuẩn trong Xime | Công tắc, hai mức log độc lập, rotation và nhiều process được kiểm | **G3:** bàn giao API/config tương thích và kết quả consumer, dừng |
| **4** | Thu lỗi handshake gRPC kèm IP | Qua cổng khả thi G4a; sự kiện vào Python logging/file, off không cài collector | **G4:** bàn giao tính năng, giới hạn Windows/Linux và hướng dẫn kiểm tiếp |

Mỗi điểm dừng phải ghi: file/repo đã đổi, kiểm chứng nào đã chạy, kết quả,
phần chưa đo và việc đợt sau sẽ làm. Nếu chủ dự án chưa bảo tiếp tục, dừng tại đó.
Nếu chủ dự án cho phép làm nhiều đợt liên tục ở một chỉ thị sau, vẫn giữ báo cáo
và kiểm chứng từng cổng; chỉ bỏ việc chờ giữa đợt theo đúng chỉ thị mới.

## 4. Đợt 1 — lịch đồng bộ khóa Trust

### 4.1. Kết quả và cấu hình đích

| Nhóm | Chu kỳ đồng bộ Trust thành công | Việc đổi |
|---|---:|---|
| Nha khoa, Nhà hàng, Nhà trọ, Shop hoa | **432.000 giây = 5 ngày** | Bỏ mặc định/YAML 300 giây còn sót |
| CRM, Giao việc, Kho, Nhân sự, Sổ thu chi | **5 ngày** | Giữ chu kỳ, bỏ lượt startup trùng |
| Data, Notification | **6 giờ** | Giữ chu kỳ riêng đã có tài liệu, bỏ lượt startup trùng |

Giữ quyền override hợp lệ của ứng dụng. Không sửa `key_policies`, tuổi thọ khóa,
preload của Trust hoặc lịch kiểm chứng chỉ mTLS. Nếu kiểm chứng phát hiện chính sách
preload hiện hành không đủ cho nhịp thiết kế, dừng báo bằng chứng trước khi đổi chính sách.

### 4.2. Các bước sửa nguồn

1. Đọc baseline của từng repo; lập bảng nguồn quyết định chu kỳ: default Python,
   `resources/application.yml.example`, YAML local có thật và nhánh môi trường liên quan.
   Không in credential; file local đang ignore/skip-worktree không được ép stage cả file.
2. Sửa default và ví dụ của 4 app dọc về 5 ngày. Đồng bộ khóa cấu hình chuẩn
   **`trust.key_refresh_seconds`** ở Shop hoa; scheduler hiện đọc sai
   `auth.jwt.refresh_seconds`. Hỗ trợ alias cũ có cảnh báo trong giai đoạn tương thích:
   chỉ alias → dùng alias; cả hai cùng giá trị → dùng chuẩn; khác giá trị → fail-fast
   nêu tên khóa, không âm thầm chọn. Ví dụ mới chỉ khai khóa chuẩn.
3. Giữ startup **cert sẵn sàng → khóa DB vào RAM → Trust → upsert/đọc lại DB → RAM**.
   Giữ scheduler singleton; không đổi mặc định chạy ngay của mọi `IntervalJob`.
4. Mỗi refresher giữ một kết quả startup trong instance: `false` khi vừa dựng; chỉ
   thành `true` khi Trust fetch, cache DB và publish RefData hoàn tất. Fallback chỉ đọc
   DB không đặt cờ. `SchedulerRunner.post_construct()` dựng Job trong `SchedulerAdapter.start()`,
   sau `run_once()` (đã xác nhận trong framework source); Job chụp cờ lúc dựng và bỏ
   đúng lượt đầu nếu startup thành công. Worker được promotion có instance mới/cờ trống
   nên vẫn sync ngay. Cờ không quyết định primary; singleton scheduler vẫn là writer.
5. Startup Trust lỗi hoặc trả rỗng không được đánh dấu là sync thành công để bỏ
   lượt thử của job. Giữ fallback DB còn hạn/fail-closed. Không tự chuyển request-time
   provider thành nơi gọi mạng. Nếu cần thêm chính sách retry mới, ghi rõ và trình
   trước; không lấy lý do chống trùng để bỏ luôn cơ hội hồi phục hiện có.
6. Áp cùng semantics cho Data/Notification và 5 service ngang; không ép Notification
   đổi toàn bộ mô hình cache của nó chỉ vì chữ ký lớp khác với các app còn lại.
7. Data còn `KeyCleanupJob` mỗi 24 giờ: nó xóa khóa hết hạn rồi đọc/publish DB.
   Nếu startup sync thành công đã dọn hết hạn, lần cleanup tức thời tạo thêm DB
   read/publish thừa. Cho cleanup chụp cùng cờ startup và bỏ đúng lượt đầu khi cờ
   thành công; startup lỗi thì để cleanup/fallback ban đầu chạy bình thường. Giữ chu kỳ
   cleanup 24 giờ. Kiểm chứng khóa hết hạn bị loại khỏi RefData ngay khi nạp và DB
   được dọn không muộn hơn chu kỳ kế. Notification không có KeyCleanupJob tương ứng.
8. Cập nhật docstring cũ như “template/Identity đều 5 phút” và “IntervalJob lần đầu
   chạy sau một nhịp”. Lưu riêng số lần job chạy và số lần thật sự gọi Trust.

**File chính:** `app/config/scheduler.py`, `app/integration/trust/startup/TrustStartupOrchestrator.py`,
`app/integration/trust/JwtKeyRefresher.py`, job JWT tương ứng; ở Data/Notification
là `app/integration/trust/key/VerificationKeySynchronizer.py` và `scheduler/KeyRefreshJob.py`.
Shop hoa dùng job dưới `app/application/job/`. Giữ nguyên API/hành vi mặc định của
framework scheduler; sửa việc trùng ngay trong orchestration/job của consumer.

### 4.3. Nghiệm thu G1

- Test cấu hình cả 11 consumer: 4 app dọc 5 ngày, 5 ngang 5 ngày, 2 Base 6 giờ;
  kiểm override và tất cả trường hợp alias của Shop hoa.
- Dùng thời gian giả/interval rút ngắn trong test: startup thành công chỉ một lượt
  Trust; job đầu không thêm DB/network/publish thừa; đến hạn mới gọi tiếp.
- Startup lỗi, DB có/không có khóa; Trust hồi phục; khóa preload chưa activate;
  Trust tạm thiếu một `kid` còn hạn; khóa hết hạn không tiếp tục verify.
- Data: startup thành công bỏ đúng lượt đầu của KeyRefresh và KeyCleanup; cleanup tiếp
  theo vẫn chạy trong chu kỳ 24 giờ. Startup lỗi thì không skip các fallback đầu.
- Cập nhật các bản kê Luật 01 về state/job trong process ở đúng repo phát sinh
  marker. Phân loại đây là cờ tối ưu một lượt, không là cache/nguồn nghiệp vụ;
  không bỏ, nới hoặc sửa test guard để làm test xanh.
- Cụm tối thiểu hai worker, đổi primary: chỉ một writer, job ở primary mới vẫn chạy;
  không lặp `run_once` của cả cụm và không mất job sau promotion.
- Provider request-time vẫn không DB/network. Không chờ thật 5 ngày để nghiệm thu.

**Điểm dừng G1:** báo cáo per-repo; giữ riêng các giới hạn live/OS. Chưa sửa demo
hoặc logging và chưa copy/cài bất kỳ gói triển khai nào.

### 4.4. Kết quả triển khai G1 (2026-10-18)

**Đợt 1 đã hoàn tất ở mã nguồn và test cô lập; dừng tại G1 để chủ dự án xem xét.**

| Repo | Test Trust/scheduler | Guard Luật 01 |
|---|---:|---:|
| Base Platform/data | 20 passed | 19 passed |
| Base Platform/notification | 4 passed | 4 passed |
| Application Layer/dental | 25 passed | 25 passed |
| Application Layer/nha-hang | 22 passed | 21 passed |
| Application Layer/nha-tro | 6 passed | 6 passed |
| Application Layer/shop-hoa-qua-tang | 43 passed | 7 passed |
| Service ngang/crm | 28 passed | 21 passed, 1 skipped |
| Service ngang/giao-viec | 28 passed | 22 passed, 1 skipped |
| Service ngang/kho | 28 passed | 18 passed, 1 skipped |
| Service ngang/nhan-su-cham-cong | 28 passed | 26 passed, 1 skipped |
| Service ngang/so-thu-chi | 28 passed | 22 passed, 1 skipped |

Ruff và `git diff --check` đều qua trên các tệp đã sửa. Shop hoa có test đủ các
trường hợp khóa cấu hình: mặc định, khóa chuẩn, alias cũ có cảnh báo, hai khóa cùng
giá trị có cảnh báo, và hai khóa xung đột thì fail-fast. Các test cũng kiểm tra chỉ
bỏ đúng lượt job đầu sau startup thành công; startup lỗi và lượt tiếp theo vẫn chạy.

**Giới hạn chưa kiểm chứng trong G1:** chưa chạy full suite của 11 ứng dụng, chưa
khởi chạy cụm hai worker để đổi primary trực tiếp, chưa thử trên Linux/VPS. Test job
xác nhận tiến trình mới/trạng thái startup chưa thành công vẫn chạy lượt đầu, nhưng
không thay cho thử nghiệm promotion thật. Không ghi DB ứng dụng. Chỉ sửa các file
`application.yml.example`; `resources/application.yml` bị ignore và cấu hình đang
chạy vẫn cần chủ dự án cập nhật thủ công khi triển khai sau này. Không sửa, copy hay
build bất kỳ gói VPS nào.

Đã chạy `git add -A` riêng trong framework và 11 repo consumer; mọi thay đổi đang
staged, chưa commit. Đợt 2 chưa bắt đầu.

## 5. Đợt 2 — sửa nạp dữ liệu mẫu Kho và Sổ thu chi

### 5.1. Nguyên tắc xử lý

- Giữ máy trạng thái `CHUA → DANG_MAU → THAT`; `THAT` không quay về `CHUA`.
- Giữ unique constraint của kho, quỹ, khoản mục. Chưa có căn cứ cần đổi schema.
- Không xóa bản ghi đang trùng chỉ vì tên giống mẫu. Kiểm tra sự tồn tại của dữ liệu
  thật, chỉnh sửa của người dùng và các tham chiếu trước khi coi nó là baseline.
- Giữ `org_id`/shard đã chốt; không gọi `place_new()` để đổi shard một org đã tồn tại.
- Một transaction cho kiểm tra, chuẩn hóa baseline hợp lệ, sinh mẫu và ghi trạng thái.

### 5.2. Các bước sửa nguồn

1. Lập danh sách bảng/quan hệ hiện hành của hai module, gồm các phần thêm sau doc 27.
   Rà `_BANG_LOI`, `_BANG_NGHIEP_VU`, FK và các đường khởi tạo mặc định; không suy
   “không có giao dịch” thành “mọi quỹ/danh mục đều do hệ thống tạo”.
2. Bổ sung bước phân loại **rỗng thật / chỉ baseline hệ thống chưa sử dụng /
   có dữ liệu hoặc tùy chỉnh người dùng**. Chỉ hai trạng thái đầu đủ điều kiện nạp.
   Khi không đủ bằng chứng bản ghi là baseline, trả 409 rõ lý do, không tự xóa.
3. Kho: reuse `KHO-CHINH` hợp lệ, giữ ID/shard và tạo các bản ghi mẫu còn thiếu;
   không INSERT ID mới với cùng code. Kho tự tạo thêm/đã tùy chỉnh phải được xét
   vào điều kiện chặn, không bị bỏ qua như `_BANG_LOI` hiện nay.
4. Sổ thu chi: xử lý đồng thời quỹ `Tiền mặt` và bộ khoản mục lazy-init, gồm
   các tên trùng như `Thu khác`, `Lương nhân viên`, `Điện nước`. Với baseline
   được chứng minh chưa dùng, chuẩn hóa có kiểm soát trong transaction trước khi
   dựng mẫu; không sửa số dư đầu của một quỹ đã dùng. Nếu cần thay quỹ mặc định
   chưa dùng để tạo đúng số dư mẫu 20 triệu, chỉ tác động đúng baseline đã xác minh,
   kiểm hết FK và giữ shard. Không gọi thao tác “xóa toàn bộ dữ liệu nghiệp vụ”
   chỉ để né constraint. Bổ sung kiểm tổng số dư/quan hệ sau nạp.
5. Khóa thao tác nạp/xóa theo `(module, org_id)` bằng cơ chế PostgreSQL không cần
   migration, ví dụ advisory transaction lock có khóa ổn định. Các đường lazy-init
   có thể đua phải dùng cùng ranh giới khóa; chỉ khóa hai request nạp là chưa đủ.
   Rà thêm ghi nghiệp vụ đồng thời để không có cửa chèn dữ liệu thật giữa kiểm tra
   và chuẩn hóa. Nếu cần đổi hợp đồng ghi/migration ngoài phạm vi, dừng trình phương án.
6. Bắt đúng các conflict dự kiến và đổi sang `PublicError`/409. Không catch-all
   biến mọi lỗi DB thành 409. Lỗi hệ thống vẫn rollback và được log với dữ liệu đã che.
7. Chuẩn bị một lệnh/script **chỉ đọc** trong `backend/tools/` để xem trạng thái
   `demo_data`, số bản ghi/baseline và các tham chiếu theo org. Không tự chạy nó
   trên VPS; không kèm câu DELETE/UPDATE mặc định.

**File chính:** `app/application/usecase/demo/DemoDataUseCase.py`, `blueprint_kho.py`
hoặc `blueprint_sothuchi.py`, `app/infrastructure/persistence/repository/SqlAlchemyDemoRepository.py`,
repository kho/quỹ/khoản mục và các cổng domain liên quan. Đối chiếu
`OrgSetupService`, `KhoService`, `_trung_lap.py`, error handler và test hiện có.

### 5.3. Nghiệm thu G2

Dùng PostgreSQL/schema thử riêng, không dùng DB ứng dụng và không coi fake repository
không có unique constraint là nghiệm thu đủ:

- Org mới; org đã mở module và có đúng baseline; org có quỹ/kho/danh mục tự tạo;
  org có giao dịch/phiếu/biến động/số dư thực; bản ghi mặc định đã tùy chỉnh.
- Nạp hợp lệ được đủ bộ mẫu, FK/shard/số dư đúng, không còn unique violation.
- Nạp lại hoặc trạng thái `THAT` trả 409. Nạp/xóa sai trạng thái không ghi gì.
- Hai request nạp đồng thời; nạp đua lazy-init; nạp đua ghi nghiệp vụ: không tạo
  hai bộ mẫu, không ghi đè hoặc xóa dữ liệu thật. Org khác giữ nguyên.
- Cố ý gây lỗi sau bước chuẩn hóa: toàn bộ transaction rollback, kể cả baseline
  và `demo_data`; không để dữ liệu mẫu dở dang.
- Vòng nạp → thêm dữ liệu trong chế độ mẫu → xóa: kiểm đầy đủ bảng hiện hành,
  đúng phạm vi org, trạng thái sang `THAT`.

**Điểm dừng G2:** báo cáo hai repo, kết quả DB thử và kết luận migration. Nếu phát
hiện bắt buộc thêm cột để phân biệt provenance hoặc cần sửa dữ liệu thật, trình
phương án riêng; không tự đưa migration hay bản vá SQL production vào đợt này.

### 5.4. Kết quả triển khai G2 (2026-10-18)

**Đợt 2 hoàn tất ở mã nguồn, test PostgreSQL cô lập và kiểm tra toàn bộ backend; dừng tại G2.**

| Repo | Full `pytest -q` | PostgreSQL cô lập |
|---|---:|---:|
| Service ngang/kho | 238 passed, 5 skipped | 4 passed |
| Service ngang/so-thu-chi | 246 passed, 8 skipped | 7 passed |

Ruff và `git diff --check` đều qua ở hai repo. PostgreSQL 18 dùng cluster và database
`xime_test_*` riêng trên loopback; các fixture tạo rồi xóa schema sau mỗi test. Các ca
đã kiểm: baseline mở sẵn, giữ ID/shard mặc định, dữ liệu tùy chỉnh/chỉnh sửa trả 409
và không bị ghi/xóa, hai lượt nạp đồng thời chỉ tạo một blueprint, ghi nghiệp vụ đang
giữ khóa khiến nạp chờ rồi từ chối, purge và tạo lại dữ liệu thật vẫn giữ shard. Sổ thu
chi còn kiểm mã PT/PC kế tiếp sau dữ liệu mẫu để không trùng số phiếu.

Không thêm migration/schema. Kho tái sử dụng `KHO-CHINH` và giữ `org_kho_setting` khi
xóa mẫu. Sổ thu chi dùng lại quỹ/khoản mục mặc định, tạo mã phiếu qua bộ đếm bền vững,
và dùng shard đã lưu khi khởi tạo lại sau purge. Mọi baseline có dấu hiệu tùy chỉnh,
quỹ/kho/danh mục do người dùng tạo, nghiệp vụ cũ hoặc bộ đếm đã dùng đều chặn nạp bằng
`PublicError`/409; không bắt lỗi DB tổng quát rồi đổi thành 409.

Đã chuẩn bị `backend/tools/kiem-tra-du-lieu-mau.py` ở cả hai repo. Script chỉ đọc,
dùng database URL của cấu hình đang chọn, đặt transaction PostgreSQL read-only và in
số lượng/baseline theo một `org_id`; `--help` đã kiểm tra. **Không chạy script này lên
DB VPS và không kết nối/đọc DB ứng dụng thật trong phiên này.** Chủ dự án cần tự chạy
hai script trên VPS khi chuẩn bị triển khai để xác nhận dữ liệu thực; kế hoạch không
đưa thay đổi dữ liệu hay migration production vào đợt này.

Đã chạy `git add -A` cho source/test trong hai repo và tài liệu framework; chưa commit.
Đợt 3 chưa bắt đầu.

## 6. Đợt 3 — logging file của Xime, chưa thu native gRPC

### 6.1. Hợp đồng cấu hình đã triển khai trong G3

Các khóa dưới đây đã có trong mã nguồn phát triển; cấu hình mẫu consumer vẫn tắt file.

```yaml
logging:
  enabled: true
  level: INFO                 # khóa cũ: mức mặc định khi console/file không khai riêng
  service_name: dental         # tùy chọn, trung lập với Trust; không khai thì dùng main package
  console:
    enabled: true
    level: INFO
  file:
    enabled: false             # opt-in; tắt thì không tạo file/queue/writer
    level: DEBUG
    path: runtime/logs/application.jsonl
    format: json              # json hoặc text; không đổi console formatter hiện có
    max_bytes: 10485760        # đề xuất 10 MiB mỗi file
    backup_count: 5            # giữ 5 bản xoay, ngoài file đang ghi
    queue_capacity: 4096       # trần chung cho cả ứng dụng
    max_record_bytes: 65536    # JSON/text đã chuẩn hóa, chưa tính newline
    shutdown_timeout: 5        # hạn chờ mỗi listener/feeder lúc dừng
```

Khóa cũ `logging.enabled/level/format/datefmt` tiếp tục dùng được. Không khai khối
mới thì hành vi console cũ giữ nguyên. `logging.enabled: false` vẫn có nghĩa Xime
nhường việc cấu hình cho ứng dụng; không hiểu nó thành `logging.disable()` toàn process.
Khai `enabled: false` nhưng yêu cầu Xime tự mở file phải báo mâu thuẫn rõ ràng.
App tự cấu hình logger có đường phối hợp tường minh, không bị âm thầm thay formatter.

### 6.2. Thiết kế triển khai

1. Bổ sung model console/file và kiểm tra cấu hình; cập nhật config spec/checker để
   bắt typo ở cả nhánh môi trường. Không thêm thư viện logging ngoài; dùng Python
   `logging`, `logging.handlers` và formatter/context filter của Xime.
2. Tách formatter/filter và lifecycle manager vào module chuyên trách của core.
   `Application._configure_logging()` chỉ điều phối, không nhét toàn bộ xử lý file
   vào một hàm. Console và file có handler level riêng; root level phải cho phép
   nhận mức thấp nhất cần dùng, để console INFO không làm mất DEBUG của file.
3. **Một writer giữ file và rotation cho mỗi ứng dụng.** App đơn dùng QueueListener
   trong process; cụm nhiều process dùng queue do supervisor sở hữu và một writer
   phía supervisor. Worker gửi bản ghi đã chuẩn hóa qua QueueHandler/IPC, không
   mở nhiều RotatingFileHandler vào cùng path. Không thêm service ngoài.
4. Queue có trần, không để I/O file chặn event loop. Khi quá tải, đếm bản ghi bị
   bỏ và có cảnh báo giới hạn tần suất qua đường console dự phòng; không hứa log
   không mất khi queue đầy hoặc tiến trình bị kill cưỡng bức.
5. Chỉ truyền config/queue phù hợp multiprocessing, không pickle handler/file descriptor
   đang mở tùy tiện. Kiểm start method và thời điểm tạo thread để tránh kế thừa
   lock khi fork; worker spawn/restart không cài lặp handler.
6. Supervisor giữ writer qua lần đổi primary; worker mới nối lại đúng queue.
   Stop dừng producer rồi flush có timeout hữu hạn, đóng writer và tài nguyên.
   App đơn, startup lỗi và shutdown sớm cũng phải dọn được. Các hạn chế SIGTERM
   app đơn còn trong backlog cũ phải ghi riêng, không tự coi là đã sửa nhờ logging.
7. Ghi append khi bật lại, xoay theo size, giữ số bản đã khai. Chặn hai instance
   độc lập cùng sở hữu một file bằng khóa OS hoặc báo cấu hình rõ ràng.
   Chỉ thao tác file thuộc family đã cấu hình, không quét/xóa thư mục log tùy ý.
8. File JSON có thời gian ISO-8601 UTC có offset, service, PID/process label,
   logger, level, message, request/correlation ID khi có và exception đã chuẩn hóa.
   Lấy context tại producer trước khi đưa qua queue. Không buộc job nền có request ID giả.
9. Che field nhạy cảm và các mẫu credential thông dụng; có fixture token/URL mật khẩu/
   PEM để kiểm. Không cam kết tự nhận biết mọi bí mật đã bị app nối tùy ý vào chuỗi.
   Hạn chế kích thước từng record, bảo vệ lỗi formatter, Unicode và dòng JSON.
10. File bật mà path không tạo/ghi được: startup fail-fast với thông báo đã che.
    Lỗi ghi phát sinh khi chạy (hết đĩa/quyền thay đổi) phải hiện ra qua kênh dự phòng
    có hạn tần suất; không làm request nghiệp vụ treo hoặc tạo vòng log đệ quy.
11. Notification: phối hợp `app/config/logging.py` để giữ JSON/context console,
    có handler level rõ ràng và đăng ký file qua cơ chế Xime. Không có hai chủ sở hữu
    root logging. Các consumer còn lại chỉ cần cấu hình mẫu, mặc định file vẫn tắt.

**File chính:** `xime/core/config/runtime.py`, `xime/core/config/__init__.py`,
`xime/core/bootstrap/application.py`, module logging core mới, điểm truyền tài nguyên
ở `_cluster.py`/`_supervisor.py`/`_shared.py` theo thực tế; `xime/cli/_config_spec.py`,
checker, docs EN/VN và API reference. Consumer chỉ sửa trong danh sách mục 1.2.

### 6.3. Nghiệm thu G3

- File off: không tạo thư mục/file/queue/writer; console và custom logger cũ hoạt động.
- File on + console INFO/file DEBUG: DEBUG chỉ có trong file, ERROR có ở cả hai;
  console off + file on; restart append; cấu hình cũ và config môi trường còn tương thích.
- Rotation với ngưỡng nhỏ trong test: đủ dòng, đúng số backup, Unicode/traceback JSON
  hợp lệ; giới hạn dung lượng có giới hạn sai số một record được ghi rõ.
- Cụm nhiều worker ghi record đánh số, kiểm không trộn dòng/ghi trùng trong tải bình thường;
  đổi primary, respawn worker và shutdown vẫn dọn được. Kiểm riêng case queue đầy.
- Đường dẫn Unicode/Windows, lỗi quyền/disk bằng fault injection, root do app sở hữu,
  API/CLI/import và sample config của 11 consumer.
- Kiểm redaction, context không lẫn request, không mở listener/app Base thật để test logging.

**Điểm dừng G3:** bàn giao cấu hình/API, test single/multi-process và các giới hạn OS.
Chưa coi có file log là đã có IP của kết nối TLS lỗi.

### 6.4. Kết quả triển khai G3 (2026-10-18)

**G3 đã triển khai và nghiệm thu Windows theo kết quả bên dưới; dừng tại G3.**
Chưa làm bộ thu native gRPC của G4.

- Core có `ConsoleLoggingConfig`, `FileLoggingConfig`, module `core/logging` riêng;
  console/file độc lập, file off không cấp tài nguyên. Cấu hình cũ và root do app
  sở hữu vẫn được tôn trọng; bật file với root riêng cần bàn giao tường minh bằng
  `Application.use_logging_console(handler)`, không có hai chủ sở hữu root.
- Writer append/size rotation có khóa OS sidecar. Một QueueListener ở app đơn;
  ở cụm, supervisor giữ writer và spawn-context queue, truyền endpoint qua
  SharedHandle. Worker không mở file, promotion/respawn dùng lại queue.
- Queue có trần, producer không chờ khi đầy, đếm lượt bỏ và báo stderr tối đa
  một lần mỗi 5 giây. Warnings không đi ngược logging hoặc in payload lỗi.
  Shutdown chờ hữu hạn cho listener/feeder; startup lỗi trả file/khóa.
- File JSON/text có UTC, service, process/PID, logger, level, context và exception;
  chụp request/correlation ID tại producer, che field/credential phổ biến trước IPC,
  giới hạn byte/độ sâu/số phần tử. Không hứa nhận diện mọi secret nối vào chuỗi.
- CLI suy model con và kiểm typo/value ở cấu hình đã merge, kể cả nhánh không
  được chọn. Hướng dẫn/cấu hình/API reference EN/VN và CHANGELOG đã cập nhật.
- Notification bàn giao handler JSON/context có sẵn cho Xime; handler level rõ
  ràng. Khi không khai mức YAML, console riêng giữ mức hiệu lực cũ (LOG_LEVEL);
  khi khai YAML, Xime áp mức riêng, không để file DEBUG làm console in DEBUG.
- 11 consumer có ví dụ opt-in, đều `file.enabled: false`; đã kiểm schema/checker
  **21 nhánh**. Data chưa có application.yml.example nên thêm riêng
  `resources/logging.yml.example` là đoạn cấu hình để ghép thủ công. Không tạo
  application.yml đầy đủ từ file cấu hình thật có secret.

**Kiểm chứng tính năng:** 237 passed ở bộ logging/bootstrap logging/CLI config/docs
trên venv kiểm thử với Uvicorn 0.48.0. Có Windows/Unicode, append, rotation/retention,
traceback JSON, context task song song, redaction, malformed record, queue đầy,
fault injection lỗi ghi và I/O treo, khóa giữa hai tiến trình độc lập,
start/stop/start và cleanup khi startup lỗi. Cụm hai worker không có listener mạng
cho logging ghi đủ **400 record đánh số**, đổi primary và respawn, không thiếu/trùng
trong các batch đã nghiệm thu; file được mở lại sau supervisor stop.

**Hồi quy framework:** **2908 passed, 25 skipped**, 312,95 giây, không deselect;
Uvicorn 0.48.0 trong venv kiểm thử, source Xime trỏ đúng repo hiện tại.
Mypy Windows và `--platform linux`: 0 lỗi / 254 file; Ruff và diff check đạt.
Phân tích tĩnh Linux không thay cho runtime Linux. Lượt đầu bằng Python chung dùng
Uvicorn **0.47.0**, thấp hơn sàn 0.48.0 hiện khai báo, có 4 ca TLS 1.2 đỏ
(2900 passed, 25 skipped). Chuyển sang venv kiểm thử sẵn có, không cài/sửa package:
15/15 test_tls_reload qua ở 0.48.0; full chạy lại trên môi trường phù hợp này đạt
2908/25 như trên. Không đổi source TLS để xử lý sai lệch môi trường.

**Full backend 11 consumer** (cùng venv kiểm thử, source framework hiện tại):

| Consumer | Passed | Skipped | Failed |
|---|---:|---:|---:|
| Dental | 1577 | 0 | 1 |
| Nhà hàng | 489 | 0 | 0 |
| Nhà trọ | 432 | 0 | 0 |
| Shop hoa | 1082 | 2 | 1 |
| CRM | 211 | 1 | 0 |
| Giao việc | 175 | 1 | 0 |
| Kho | 238 | 5 | 0 |
| Nhân sự | 688 | 1 | 0 |
| Sổ thu chi | 246 | 8 | 0 |
| Data | 695 | 0 | 0 |
| Notification | 462 | 0 | 0 |
| **Tổng** | **6295** | **18** | **2** |

Hai failed đều là `test_khong_khai_lai_thu_framework_da_giu` ở Dental/Shop hoa:
app đã khai cryptography>=42.0 trong HEAD, còn metadata Xime kéo >=50.0.0 qua
extra JWT. Đã xác nhận pyproject/test guard của app và pyproject framework không
có diff với HEAD; G3 không sửa/cài dependency. Test chỉ đọc các nguồn này, không
chạy logging. Đây là baseline dependency trùng khai, được báo riêng; giữ nguyên
phạm vi G3, không nới guard hoặc tự sửa dependency để làm suite xanh.

Bằng chứng JUnit ở `%TEMP%/xime-framework-g3-20261018/`: framework.xml và 11 file
consumer theo tên repo. Các ca PostgreSQL opt-in của G2 vẫn skip trong lượt này;
không thay kết quả test DB cô lập đã ghi ở G2 bằng kết quả skip.

**Giới hạn:** chưa chạy Linux/VPS, không build/copy triển khai, không sửa YAML đang
chạy hoặc DB thật. Queue không bền vững; overload/timeout/kill có thể mất log đuôi,
kill đúng lúc ghi có thể làm hỏng multiprocessing queue. Lỗi SIGTERM app đơn trong
backlog cũ chưa sửa. File có thể vượt trần size tối đa một record giới hạn cộng
newline. Redaction của file không thay formatter console riêng. Log file chưa có
IP handshake native gRPC — đó là G4. Không nâng version/commit/push/PyPI.

Đã `git add -A` trong framework và 11 consumer. Hai artifact PostgreSQL tạm còn
từ G2 ở Kho (`backend/.pytest-codex-phase2-pg/` và file log cùng tiền tố) được loại
khỏi staging; không thử xóa lại. Mã nguồn và tài liệu kế hoạch đã stage; chưa commit.

## 7. Đợt 4 — sự kiện gRPC handshake thất bại kèm IP

Đây là một module của logging Xime ở Đợt 3, với bộ thu native riêng. Không làm
RPC interceptor giả bắt lỗi TLS, không dùng certificate fetcher để suy ra IP.

### 7.1. Cổng khả thi G4a ban đầu — lịch sử trước quyết định 7.5

> Chủ dự án đã duyệt đổi điều kiện vòng đời: không restore khi grpcio còn được nạp;
> pipe/thread tồn tại đến lúc process OS thoát. Các tiêu chí restore dưới đây được
> giữ để đọc kết quả cũ; thiết kế/kết quả hiện hành ở 7.5.

1. Đưa probe của phiên này thành harness/test nguồn, lưu kết quả tái chạy được.
   So mặc định với `GRPC_TRACE=handshaker`, gồm HTTP→TLS, thiếu cert, SNI sai,
   TLS không tương thích, peer ngắt giữa handshake và timeout.
2. Kiểm grpcio đang dùng và phiên bản sàn tương thích Python được test. Kiểm thời
   điểm tracer đọc môi trường: trước/sau import grpc, trước/sau lần gRPC init đầu.
   Chốt điểm hook lifecycle đủ sớm; không hứa bật nóng một tracer chỉ đọc một lần.
3. Xác minh trên Windows cơ chế thu native có thể: lấy địa chỉ từ **chính dòng lỗi**,
   chuyển thành `LogRecord`, bảo toàn stderr khác và không cần sửa/cài lại grpcio binary.
   Chuẩn bị phép đo POSIX/Linux trong source; Windows không thay phép đo đó.
4. Ưu tiên hook logging native được hỗ trợ nếu phiên bản thực có. Nếu phải thu FD 2,
   phải có bản sao descriptor gốc cho đường passthrough, consumer thread có trần,
   xử lý dữ liệu từng phần và khôi phục descriptor đúng lifecycle. Không hook riêng
   `sys.stderr` rồi cho rằng đã bắt được C-core.
5. Nếu không đạt bảo toàn stderr/không đệ quy/không gán nhầm IP, **dừng Đợt 4 tại
   G4a và trình kết quả cùng phương án khác**. Không thay bằng tracing thô rồi báo
   đã hoàn thành log Python có cấu trúc; không tự thêm proxy/service/dependency native.

### 7.2. Cấu hình và sự kiện — đã triển khai theo thiết kế 7.5

```yaml
grpc:
  handshake_logging:
    enabled: false             # opt-in; tắt thì không cài collector/tracer của Xime
    level: WARNING
    rate_limit_per_second: 20  # trần đề xuất, có thống kê sự kiện bị giới hạn
```

- Cấu hình là **process/application-level**, áp dụng từ lần khởi động. Bộ thu phân
  biệt listener/server ID theo địa chỉ local đã đăng ký với adapter.
- `logging.file.enabled` điều khiển đầu ra file; `grpc.handshake_logging.enabled`
  điều khiển việc tạo sự kiện native đã chuẩn hóa. Bật một cái không tự bật cái kia.
  Native off vẫn để gRPC phát các lỗi mặc định của thư viện theo cấu hình riêng của nó.
- Event tối thiểu: `event=grpc_tls_handshake_failed`, timestamp, service, PID,
  `server_id`, remote IP/port, local IP/port, mã nguyên nhân, mức log và phiên bản grpcio.
  Đây là kết nối chưa xác thực: không gắn identity đã tin cậy hoặc request ID giả.
- SNI chỉ là tên đích client gửi; không dùng nó làm IP nguồn. Không dùng “IP vừa thấy
  gần nhất” hoặc chỉ thread ID để ghép lỗi khi nhiều kết nối đồng thời.
- Phân biệt gRPC server inbound với client outbound. Chuẩn hóa IPv4/IPv6, thiếu trường
  thì ghi thiếu/không hỗ trợ rõ ràng; không bịa địa chỉ và không bỏ lỗi âm thầm.
- Dùng whitelist field/cause, không đưa raw buffer, JWT, metadata xác thực, PEM hay
  con trỏ native vào file chuẩn. Tránh ghi lặp cùng failure từ nhiều dòng trace.
- Console handler của Python và cảnh báo collector phải dùng đường không bị collector
  thu lại. Dòng không thuộc phần Xime quản lý phải được passthrough, không nuốt.
- Nếu môi trường đã khai tracer trước, bảo toàn phần do người vận hành sở hữu;
  không tự bật `all`, `tcp` hoặc `GRPC_VERBOSITY=DEBUG`. Giới hạn parser buffer/queue
  và phát thống kê giới hạn tần suất. Thay đổi quyền native ngoài khả năng tương thích
  phải fail rõ khi opt-in, không làm app mặc định bị ảnh hưởng.

**File chính:** model gRPC trong `adapters/grpc/_config.py`, điểm đăng ký listener
ở `_adapter.py`, bộ thu/parser native mới dùng backend logging core ở Đợt 3,
điểm bootstrap sớm đã được chứng minh; config checker/docs và ví dụ consumer.
Nếu cần một lời gọi bootstrap tường minh trước import gRPC, phải ghi rõ API và
đổi đúng `app/main.py` của consumer cần dùng, không âm thầm monkey-patch toàn Python.

### 7.3. Nghiệm thu G4

- Off: không collector thread/pipe, không tự thay tracer/descriptor, logging hiện có đúng.
- On: các ca G4a có sự kiện vào **Python logging và file handler**, không chỉ thấy
  một dòng C-core được shell chuyển vào file. IP/port khớp socket client đo được.
- Client TLS/RPC hợp lệ vẫn chạy; stream/gRPC mTLS, cert rotation và HTTP adapters
  không hỏng. TLS lỗi không đi tới interceptor được chứng minh bằng đối chứng RPC hợp lệ.
- Nhiều client đồng thời, nhiều listener, worker/promotion, IPv4/IPv6, đổi phiên bản
  log prefix; không gán nhầm IP giữa hai kết nối. Parser kiểm fixture đã khử dữ liệu nhạy cảm.
- Rate limit, record bị cắt, native line không nhận dạng, queue đầy, writer lỗi,
  shutdown/khôi phục stderr và startup thất bại không treo process.
- Ma trận đủ 4 tổ hợp file on/off × native on/off, console mức riêng hoạt động.
- Đo lượng log/chi phí với tải loopback cố định, cùng baseline và cùng điều kiện;
  báo số đo, không tự ghi một phần trăm hiệu năng chưa đo.
- Phần chỉ chạy được trên Linux để harness + lệnh đọc trong repo và đánh dấu
  **chưa nghiệm thu Linux** nếu phiên này chỉ có Windows. Không copy sang Linux/VPS.

**Điểm dừng G4:** báo cáo phần đã chứng minh, phiên bản hỗ trợ, API/config cuối,
giới hạn native/OS và cách chủ dự án kiểm tiếp khi tự triển khai về sau.

### 7.4. Kết quả G4a trên Windows (2026-10-18): KHÔNG ĐẠT

**Dừng theo điều 7.1.5. G4 chưa hoàn tất; không tích hợp collector vào runtime.**
Không thêm model/config handshake_logging, không đổi main/config consumer, không
vá/cài đè grpcio, không thêm proxy hoặc service ngoài. Logging file G3 giữ nguyên.

Con trỏ dễ đọc: [KIEM-THU-GRPC-HANDSHAKE.md](../../../KIEM-THU-GRPC-HANDSHAKE.md).
Harness nguồn: `tests_temp/grpc_handshake/probe.py`, `matrix.py`, `test_probe.py`.
Đây là probe/analyzer offline trong subprocess test, chưa phải API logging sản phẩm.

Đã đo 9 biến thể × 2 wheel Windows/Python 3.14.8/OpenSSL 3.5.9: grpcio 1.81.0
đang có và 1.75.1 giải nén trong thư mục thử riêng. Shared Python vẫn 1.81.0;
pyproject/dependency, source runtime Xime và app không đổi trong G4a. Sàn khai
1.72.1 không có wheel cp314 Windows, để kiểm trên Linux/Python 3.12; không nhận
lượt 1.75.1 là kiểm exact-floor.

| Bất biến / quan sát | 1.81.0 | 1.75.1 |
|---|---|---|
| HTTP→TLS, thiếu client cert, TLS cũ, peer ngắt, timeout: source/destination khớp socket trong cùng record | 5/5 | 5/5 |
| RPC mTLS hợp lệ trả ok; đúng một interceptor | Đạt | Đạt |
| Các kết nối lỗi đi trước RPC | Đạt | Đạt |
| Stderr marker Python/os.write passthrough trong capture | Đạt | Đạt |
| Native gRPC mới sau khi restore FD2/standard handle | **Mất** | **Mất** |
| Đối chứng không cài capture, cùng native lỗi mới | Có log | Có log |
| Tracer trước init đầu tiên, kể cả sau import | Có trace | Có trace |
| Tracer bật sau init đầu tiên | Không có handshaker trace | Không có handshaker trace |
| Capture bắt đầu sau import/init | Không thu được native cần dùng | Không thu được native cần dùng |
| Verdict | **not_ready: native_stderr_restore** | **not_ready: native_stderr_restore** |

Đã thử FD2 đơn và FD2 + Windows SetStdHandle: capture sớm lấy địa chỉ được nhưng
vẫn mất native log sau restore. Hai marker Python/os.write đều qua, nên chỉ kiểm
marker là bằng chứng thiếu. Kiểm thêm server mới/SNI sai sau restore phát hiện lỗi;
đối chứng cùng kết nối có log. Không khẳng định nguyên nhân CRT/binary bên trong
khi chưa có bằng chứng trực tiếp về cơ chế đó. Chưa tìm thấy hook Python native
log sink được hỗ trợ trong bề mặt module/Cython hai phiên bản đã khảo sát.

Prefix 1.75.1 khác 1.81.0; timeout Windows có newline bên trong native record.
Analyzer đã xử lý hai dạng prefix, multiline, IPv6 fixture và không mượn peer của
record trước, không gán client-outbound thành server-inbound. SNI sai được kiểm
riêng: dòng SNI không có địa chỉ và client có thể tự từ chối hostname; không biến
SNI hoặc lỗi client thành IP của server inbound.

Raw trace capture sớm: 31.734 byte (1.81.0) / 31.838 byte (1.75.1) cho fixture;
chưa làm benchmark collector sản phẩm vì gate thất bại. Artifact ở
`%TEMP%/xime-framework-g4-20261018/matrix181-final` và `matrix175-final`, có
`report.json`, stderr đối chứng/capture và raw trace. Raw log có pointer native
fixture nên giữ trong artifact tạm, không stage vào Git.

Kiểm `python -m pytest -q tests_temp/grpc_handshake tests_temp/cli_docs
 tests_temp/api_surface`: **68 passed** (5 thuộc harness mới). Ruff/diff check đạt.
Test pass chứng minh probe/guard biết phát hiện bất biến không đạt; không chứng
minh G4 đã đạt. Không chạy lại full framework/11 consumer: không sửa runtime,
config hay dependency, kết quả G3 vẫn được giữ riêng ở 6.4.

Đã chuẩn bị hướng dẫn chạy cùng harness trên Linux trong file con trỏ gốc.
Chưa chạy Linux/WSL/VPS. Nếu Linux candidate_ready thì vẫn còn toàn bộ phần tích
hợp Python LogRecord/file, công tắc, rate limit/bounded queue, multi-listener/
worker, IPv6 thật và đo tải của G4. Không dùng raw tracing thay đầu ra đã yêu cầu.
Đã `git add -A` phần source test và tài liệu trong framework; chưa commit.

### 7.5. Thiết kế process-lifetime đã được duyệt và triển khai (2026-10-18)

**Chủ dự án đã duyệt đề xuất tiếp tục: giữ grpcio chính thức, thu native stderr
suốt đời process; đổi native bằng restart process, không bật/tắt nóng.**
Đã triển khai mã nguồn và kiểm chứng Windows; runtime Linux/POSIX vẫn chưa đo.
Không mặc định kết quả Windows là nghiệm thu Linux, không build/copy/deploy.

**Thay điều kiện G4a:** không restore FD2/Windows handle khi grpcio còn tồn tại.
App stop/start chỉ gỡ listener, drain có hạn, đóng/mở log file. Pipe/2 daemon
thread và stderr gốc tồn tại đến lúc process OS thoát; marker drain đảm bảo xử lý
phần stderr đã ghi, không để marker lộ ra ngoài. Atexit drain rồi tắt phát sự kiện
Python, vẫn giữ passthrough cho native destructor muộn; OS thu hồi tài nguyên.

**API/source:** `xime.observability.prepare_grpc_handshake_logging()` trước mọi
import grpc/config ở từng process; native off không pipe/thread/tracer/grpc import.
Có model GrpcHandshakeLoggingConfig, counter GrpcHandshakeLoggingStats và API
snapshot grpc_handshake_logging_stats(). Core bootstrap phối hợp logging G3;
GrpcAdapter đăng ký chính listener TLS đang bind; Event dùng PID process thật,
không mượn peer/thread ID, không phát outbound thành inbound.

Parser chỉ đọc frame handshaker đầy đủ; lấy địa chỉ trong metadata tail, không lấy
field giả trong chuỗi reason. Có IPv4/IPv6/mapped, giới hạn record/queue/rate,
whitelist field/cause và summary khi mất/không parse được. Cause thiếu chính xác
được ghi chung thay vì suy đoán. Console Python/cảnh báo Xime bypass pipe; handler
stderr do app sở hữu cần bàn giao tường minh. Giữ operator tracer; trace do Xime
thêm được làm gọn. Native warning/error/fatal và stderr khác vẫn passthrough.

Đã thêm bootstrap/mẫu opt-in **tắt** vào 5 service ngang + Data/Notification.
Data dùng `resources/grpc-handshake.yml.example`; không sửa YAML đang chạy.
Bốn app dọc không mở gRPC server nên không thêm inbound collector ở main.
Không sửa Trust/Identity, frontend, DB/schema, TLS/mTLS policy, cipher hay version.
Test IPv6 thật phát hiện bind host `::1:port` thiếu ngoặc; đã chuẩn hóa thành
`[::1]:port` trong GrpcAdapter, giữ hành vi IPv4/host có ngoặc.

**Nghiệm thu Windows:**

- Native 1.81.0: 4 tổ hợp file/native, 2 Application epochs, 2 listener;
  20 lỗi HTTP/TLS thiếu cert/TLS cũ/ngắt/timeout khớp socket, RPC mTLS vẫn chạy.
  48 kết nối lỗi đồng thời đúng listener/port; IPv6 thật và mapped normalization.
- Native 1.75.1 từ wheel cô lập: 20/20 lỗi thành LogRecord/file, 4 RPC hợp lệ;
  không thay grpcio trong Python chung. Chưa đo exact-floor 1.72.1 trên Windows
  vì không có wheel cp314; Linux/Python 3.12 có hướng dẫn kiểm riêng.
- Cụm hai worker, primary chết, promotion/respawn: đúng PID worker trong file,
  không nhận vơ PID supervisor; kiểm cả operator tracing đã bật sẵn.
- Queue đầy/rate limit có counter/summary, CPP/native record malformed/truncated,
  marker split từng byte, stderr không newline, warning/error/fatal, custom console,
  late/invalid bootstrap, immutable native config và startup fail được kiểm.
- Full regression snapshot: **2933 passed, 25 skipped, 1 deselected**, 320,13 giây,
  venv sẵn có Uvicorn 0.48.0; `_alive` gây Ctrl-C trên Windows đúng lịch sử, tách
  riêng: assertion 1 passed và child exit 0 trong wrapper bảo vệ SIGINT, console
  host vẫn báo interrupt. Không sửa test/implementation `_alive` trong đợt này.
- Sau snapshot đã thêm guard console/fatal/mapped/status metadata và chạy lại bộ
  native cuối: **30 passed**. Bộ liên quan gRPC/logging/API/docs trước đó 286 passed;
  không cộng các lượt chạy thành ca độc lập. Chạy config/native mục tiêu cũng đạt.
- 7 consumer có sửa main: **2715 passed, 16 skipped** (Data 695; Notification 462;
  CRM 211/1 skip; Giao việc 175/1; Kho 238/5; Nhân sự 688/1; Sổ thu chi 246/8).
  Không chạy lại full 4 app dọc ở G4; hai guard dependency baseline vẫn ghi ở 6.4.
- Mypy Windows/Linux: 0 lỗi/260 file; Ruff và diff check đạt. Mypy Linux là kiểm tĩnh.

**Đo chi phí tái chạy được:** `tests_temp/grpc_handshake/benchmark.py`, 5 lượt mỗi
chế độ, file bật cả hai; 80 HTTP→TLS lỗi + 4 RPC mTLS hợp lệ, 2 listener và 2 vòng
đời app mỗi lượt. Kết quả checkpoint cuối ở `benchmark-final-source/benchmark.json`:
median workload **53,6 ms → 85,8 ms**, CPU process gồm drain/log **125,0 ms →
156,25 ms** khi bật native. Đây là loopback lỗi dày, không suy thành chi phí trên
mọi RPC hoặc bảo đảm hiệu năng VPS. Rate limit không loại chi phí tạo C-core trace.

Artifact ở `%TEMP%/xime-framework-g4-lifetime-20261018/`, có full/native JUnit,
1.75.1 report, benchmark. Hướng dẫn dùng: `docs/{vn,en}/grpc-handshake-logging.md`;
con trỏ Linux hiện hành: `KIEM-THU-GRPC-HANDSHAKE.md`. `matrix.py` cũ chỉ đo restore,
không dùng verdict cũ làm kết luận về lifetime collector. File on/off độc lập với
native on/off; mọi mẫu consumer còn tắt, chủ dự án áp dụng thủ công sau này.

**Giới hạn còn mở:** Linux/POSIX/py3.12 exact floor, VPS thực; kill/abort/timeout có
thể mất đuôi log, stderr gốc nghẽn giữ backpressure. SNI không phải IP/identity;
địa chỉ là TCP peer nhìn thấy ở server, không tự suy IP trước NAT/proxy.
Không cải thiện nợ SIGTERM app đơn hay hai khai báo dependency baseline ngoài G4.
Source/test/docs được `git add -A`, chưa commit; không có build, deploy hoặc PyPI.

### 7.6. Tiếp nhận Linux và nghiệm thu Windows (2026-10-19)

Chủ dự án đã chuyển gói ZIP Linux vào `D:\temp`, yêu cầu xem xét, chạy test lại,
tiếp nhận source/docs và đánh giá phát hành. Kế hoạch bổ sung ở phiên Linux đã
được chủ dự án duyệt riêng, bao gồm vá lifecycle và S3 ngoài collector ban đầu.
Không suy quyền duyệt kiểm thử thành quyền upload PyPI.

Đã kiểm 793 file theo final manifest và mốc incoming của 13 file sửa; nhập đúng
22 file = 13 sửa + 9 thêm, không xóa. Ba nhóm runtime: signal ownership toàn
worker/cleanup, parser gRPC 1.72.1 legacy, S3 giữ StreamingBody wrapper thay vì
response thô. Pyproject/version/floor giữ nguyên; không sửa consumer hoặc DB thật.

Linux/Python 3.13.5: bốn full resolver/1.72.1 × asyncio/uvloop, mỗi lượt
2975 passed/12 skipped/0 failed; soak 30 phút, 20 Application lifecycle,
3600/3600 event khớp kết nối và JSONL, FD/thread ổn định. MinIO/MQTT/Redis/
PostgreSQL riêng và wheel sạch có bằng chứng, nợ consumer được tách riêng.

Windows/Python 3.12 exact grpcio/tools 1.72.1 tìm thêm pointer legacy không có
`0x`: trước sửa 0/20 event, unparsed=92. Đã nhận hex 8/16 ký tự, giữ kiểm
metadata/IP/listener, thêm guard reason giả/pointer sai/framing; đối chứng
8 failed/8 passed trước sửa. Sửa assertion console của test cụm để nhận đúng
định dạng Windows, không bỏ kiểm event/PID/promotion/respawn. Thêm hai ca
CTRL_BREAK thật, có/không WebAdapter, kiểm PreDestroy một lần và drain file.

Hai full Windows trên runtime sau sửa: Python 3.14.8 resolver và Python 3.12.10
core exact floors + grpcio/tools 1.72.1 đều **2965 passed/33 skipped/1 deselected**.
Một deselect là `_alive(current_pid)` theo hạn chế Windows đã biết; Linux đã
chạy full ca đó. Native sàn ghi đúng 20/20 event lên đĩa, bốn RPC mTLS hợp lệ,
không counter lỗi/mất log. Mypy 0 lỗi/261 file, Ruff/pip check/docs đạt.

Wheel/sdist dựng lại trong thư mục tạm, runtime bytes khớp, không lẫn nội bộ;
venv wheel trắng không dev/pytest, CLI/JWT RSA/native thực đạt. Metadata 0.8.3
chỉ để test; không upload đè bản đã phát hành. Báo cáo, SHA và giới hạn đầy đủ:
[`../../../NGHIEM-THU-LOGGING.md`](../../../NGHIEM-THU-LOGGING.md).

Linux full thuộc snapshot trước bổ sung pointer Windows; chưa chạy lại Linux
sau bổ sung này hoặc Linux/Python 3.12. Audit còn một ID APScheduler được chấp
nhận có điều kiện, không gọi zero advisory. Cần thử VPS vài ngày theo yêu cầu
chủ dự án, chốt version và dựng artifact cuối trước PyPI. Chưa commit/push/upload.

## 8. Kiểm chứng và tài liệu xuyên suốt

- Trước sửa: ghi HEAD, dependency và dirty paths của đúng repo. Framework đang
  editable có thể ảnh hưởng consumer khi nạp lại code; không tự restart app đang chạy.
- Mỗi lỗi có test đối chứng: đỏ trên hành vi cũ vì đúng lỗi, xanh sau sửa, và có ca
  hợp lệ bên cạnh. Dùng test PostgreSQL thật cho constraint/transaction và process thật
  cho file logging/handshake, không chỉ mock lại implementation.
- Chạy test liên quan sau từng nhóm. Chạy full framework và full hai repo demo
  tại checkpoint thay đổi tương ứng; với consumer khác chạy suite Trust/config/DI
  phù hợp. Chỉ mở rộng chạy lại khi có thay đổi hoặc lỗi mới cần giải thích.
- Mỗi repo Python chạy `python -m pytest ...` từ đúng root/backend; Ruff phạm vi sửa,
  framework mypy và kiểm docs/API/config nếu đổi bề mặt công khai. Không cài nâng
  dependency vào Python chung đang dùng; probe sàn phiên bản dùng môi trường riêng.
- Báo cáo không cộng nhiều lần chạy cùng testcase thành số ca độc lập. Phân biệt
  đọc source, mock/fault injection, DB thử, process thật và phép đo production.
- Lưu tài liệu triển khai tính năng trong framework docs EN/VN, đồng bộ ví dụ dùng
  thật. Báo cáo từng đợt nằm trong repo nguồn; log probe có thể lưu vùng artifact
  test đã ignore trong repo, chỉ đưa kết luận/fixture đã lọc vào Git.

## 9. Quy tắc Git, DB và bàn giao

1. Ghi kế hoạch/tài liệu là quyền hiện tại; **source chỉ bắt đầu sau chủ dự án duyệt**.
2. Giữ yêu cầu trước của chủ dự án: `git add -A` sau mỗi nhóm trong đúng repo được
   giao. Trước khi stage kiểm lại dirty paths; không gom phần của phiên khác,
   không force-add YAML credential, key/cert, cache hay kết quả chứa dữ liệu nhạy cảm.
   Nếu có dirty không thuộc phạm vi, stage theo path và báo ngoại lệ rõ ràng.
3. Commit giữ theo repo, sau khi có chỉ thị commit cho đợt mới; không tự diễn giải
   quyền commit đợt kiểm toán cũ thành quyền commit/push đợt này. Không tag/phát hành PyPI.
4. Không có migration được mặc định cho phép trong kế hoạch này. DB thử cô lập dùng
   để chứng minh behavior; DB ứng dụng thật và DB VPS giữ nguyên. Nếu phát hiện cần
   sửa schema/dữ liệu thật, dừng tại cổng tương ứng và trình phương án cụ thể.
5. Không chạm thư mục build hay artifact ngoài repo nguồn; không đóng gói/copy sang
   thư mục khác và không triển khai VPS. Chỉ ghi yêu cầu cài cấu hình/kiểm tiếp vào docs.

### Mẫu báo cáo tại mỗi điểm dừng

```text
Đợt / cổng:
Repo và HEAD ban đầu:
File/behavior đã sửa:
Lệnh kiểm chứng + kết quả:
Phần chỉ đọc / phần đã chạy thật:
Giới hạn hoặc việc chưa nghiệm thu:
DB schema/data có thay đổi không:
Git index / commit (nếu được yêu cầu):
Trạng thái: DỪNG CHỜ CHỦ DỰ ÁN.
Đợt tiếp theo và điều kiện để bắt đầu:
```

Không coi “đã viết code”, “đã có file log” hay “đã bật tracer” là hoàn tất khi
tiêu chí tương ứng chưa được kiểm. Các mục kết quả G1–G3 ở trên ghi rõ bằng chứng
và giới hạn đã đo; G4a cũ theo 7.4 được thay thiết kế đã duyệt ở 7.5; phần
tiếp nhận Linux, kiểm lại Windows và điều kiện phát hành hiện hành ở 7.6.
