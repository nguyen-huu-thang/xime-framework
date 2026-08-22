# Lộ trình phiên bản Xime Framework

> Chỉ mục tổng các mốc phiên bản đã chốt, để tra nhanh "việc X làm ở bản nào".
> Chi tiết từng mục nằm ở các doc được trỏ tới. Cập nhật **2026-08-22**.
> ⭐ **0.8.1 ĐÃ PHÁT HÀNH 2026-08-22** - PyPI có **15 bản**, `0.1.0` -> `0.8.1`;
> tag `v0.8.1` có ở **cả hai** repo, SHA256 khớp từng bit. (0.8.0 lên ngày 2026-08-21.) ⛔ Dòng cũ ghi *"0.8.0 chưa phát hành,
> PyPI dừng ở 0.7.2"* là **SAI, đừng tin lại** - đó là **lần thứ năm** cùng một
> khuôn ở repo này (*"chưa push PyPI"* · *"0.7.0 chưa commit"* · *"0.7.1 đã phát
> hành"* · *"pyproject = 0.7.2"* · *"0.8.0 chưa phát hành"*). Mỗi lần đều đúng lúc
> viết rồi bị bỏ quên. **Kiểm bằng lệnh, không bằng trí nhớ:**
>
> ```bash
> python -c "import urllib.request,json; print(sorted(json.load(urllib.request.urlopen('https://pypi.org/pypi/xime/json'))['releases']))"
> grep '^version' pyproject.toml && git tag -l | sort -V | tail -3
> ```
>
> Vì `xime` cài **editable** nên mọi thay đổi ở repo phát triển có hiệu lực ngay
> với cả 31 app, kể cả phần chưa phát hành.

| Bản | Chủ đề | Trạng thái |
| --- | --- | --- |
| 0.3 | Hardening + hoàn tất gRPC | Đã phát hành (2026-06-20) |
| 0.4 | Cross-cutting + starters | Đã phát hành (2026-06-20) |
| 0.5 | Kiểm toán toàn diện + Messaging/IoT (MQTT) + File | Đã phát hành (2026-06-22) |
| 0.6 | Thay `dependency-injector` + dynamic interface binding | Đã phát hành (2026-06-23) |
| 0.6.1 | Web adapter: middleware lấy DI/config qua marker + `configure_cors`; SQLAlchemy starter: `CrudRepository` | Đã phát hành (2026-06-29) |
| 0.6.2 | Starter `mail` (SMTP) + hardening sau kiểm toán toàn diện | Đã phát hành (2026-06-30) |
| 0.6.3 | Gỡ chặn app chạy thật: ~~`PEER_APP_ID`~~ + **TLS/HTTPS cho web adapter** + **khối chỉ đọc `read_only()`**; kèm `get_bool` ép kiểu cờ + metadata gói | Đã phát hành (2026-07-29). ⛔ **`PEER_APP_ID` đã bị GỠ ở 0.7.1** vì mang khái niệm của nền tảng vào framework - thay bằng `PEER_SANS`, xem [`ghi-chep/go-phu-thuoc-khai-niem.md`](ghi-chep/go-phu-thuoc-khai-niem.md) |
| 0.7.0 | Fieldbus công nghiệp (Modbus TCP + OPC UA) | **Đã phát hành PyPI** (2026-08-01) - 1463 test. Kiểm toán trước khi đẩy: `kiem-toan/0.7-truoc-phat-hanh.md` |
| 0.7.1 | Server-stream có kiểu (`@stream`) + đợt 2 vá bảo mật (F2/F4/F5/F6/F7/F8/F11/F12/F13/F16) + lỗi đua khi tắt scheduler + ⛔ **GỠ PHỤ THUỘC KHÁI NIỆM (BREAKING)** + khai 3 phụ thuộc bắc cầu | **Đã phát hành PyPI** (commit `975e10c` / `a3fcad8`) - **1516 passed / 11 skipped**. Xem `phien-ban/0.7.1-ket-qua.md`, [`ghi-chep/go-phu-thuoc-khai-niem.md`](ghi-chep/go-phu-thuoc-khai-niem.md), [`ghi-chep/phu-thuoc-bac-cau.md`](ghi-chep/phu-thuoc-bac-cau.md) |
| 0.7.2 | ⭐ **JWT: khoá xoay theo `kid`** (`JwtKeyProvider`) + ba knob PyJWT từng bị giấu (`algorithms`/`leeway`/`require`) + `sign(headers=)` + ⛔ **`configure_jwt()` thiếu nguồn khoá NỔ lúc khởi động** | ✅ **ĐÃ PHÁT HÀNH** - PyPI có `0.7.2`, commit `3cfc3f3 v0.7.2`. Cuối bản: **1624 passed / 11 skipped** (F1+F3+F14+F15+F17 vào cùng ngày). ⚠ **Thiếu tag `v0.7.2`** và **repo phát hành `upload` chưa theo kịp** (còn ở `a3fcad8 v0.7.1`). Xem [`ghi-chep/jwt-keyset-va-trung-tinh.md`](ghi-chep/jwt-keyset-va-trung-tinh.md) |
| 0.7.x | **Vá, không chạm API**: ~~A1 keyset JWT~~ · ~~F3 nâng sàn deps~~ · ~~F14~~ · ~~F15~~ · ~~F17~~ · ~~F1 WebSocket~~ | ✅ **A1 xong 2026-08-18 phía framework** ([`ghi-chep/jwt-keyset-va-trung-tinh.md`](ghi-chep/jwt-keyset-va-trung-tinh.md)) - ⚠ **19 app vẫn fail-open**, framework chỉ xoá lý do tồn tại của lỗ. ✅✅ **F1 + F3 + F14 + F15 + F17 xong cùng ngày 2026-08-18 - HẾT MỤC 0.7.x.** ⚠ F1 thêm API công khai (`@ws`) và đổi hành vi mặc định, tức **vượt luật "0.7.x không chạm API"** - chủ dự án chốt ngoại lệ có ý thức vì chưa app nào dùng WebSocket. Bảng đầy đủ ở [`../CLAUDE.md`](../CLAUDE.md). ⚠ **F10 đã chuyển sang 0.8** · ⛔ **F9 đã bị XOÁ** (không còn chuỗi nào để neo sau khi gỡ phụ thuộc khái niệm) |
| 0.8 | **Đa tiến trình + đổi API adapter một lượt** | ⚠ **Thiết kế đổi hẳn 2026-08-16** - bản 2026-06-27 (Bus Manager, DI scope `global`) phần lớn không còn dùng. ✅ **Phần bus đóng nốt 2026-08-18** ([`thiet-ke/11-bus-lien-tien-trinh.md`](thiet-ke/11-bus-lien-tien-trinh.md), tên chốt `ProcessLink`). ✅ **THI CÔNG XONG 2026-08-20** - bảy giai đoạn kế hoạch cộng một **giai đoạn 8 phát sinh** (trình tạo cấu hình: `xime init` · `xime config --print` · `xime check config`). **2376 passed, 14 skipped**; bốn app thật xanh (388 · 295 · 192 · 53). ✅ **ĐÃ PHÁT HÀNH PyPI 2026-08-21** (bản thứ 14), sau **sáu đợt kiểm toán, vá 28 mục**; SHA256 gói trên PyPI khớp từng bit với gói dựng ở máy này. Bảng tiến độ + các chỗ thi công đụng vào thiết kế: [`../CLAUDE.md`](../CLAUDE.md); chi tiết từng giai đoạn: `CHANGELOG.md` |
| 0.8.1 | **uvloop trên Linux** - bật vòng lặp sự kiện nhanh cho web/socket/MQTT | ✅ **ĐÃ PHÁT HÀNH 2026-08-22** (bản thứ 15, SHA256 khớp từng bit). Đo trên Linux đầy đủ; ⛔ phép đo lãi **lật giả định** - uvloop làm REST chậm ~10%, lãi nằm ở kết nối đã mở. Vẫn giữ. Xem [`kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](kiem-toan/0.8.1-ket-qua-do-tren-linux.md) |
| 0.8.2 | **Fieldbus chia tải + MQTT chia tải + `drain()` lúc tắt** | **Chốt 2026-08-22, chưa code.** Đổi khoá cấu hình nên **phải nằm trong dòng 0.8.x** |
| 0.9 | Beta - config nốt + bug fix + phản hồi người dùng | Mở |

---

## Mức độ chín (PyPI `Development Status`) theo phiên bản

> Quyết định của chủ dự án 2026-06-23. `Development Status` là classifier trong
> `pyproject.toml`, phản ánh độ ổn định API chứ không buộc cứng theo số version.

| Bản | Classifier | Lý do |
| --- | --- | --- |
| 0.6 -> 0.7 (hiện tại) | `3 - Alpha` | Đang dùng |
| 0.7 | `3 - Alpha` | **Vẫn còn thêm tính năng lớn** (Fieldbus). API chưa đông cứng. |
| 0.8 | `3 - Alpha` | **Vẫn còn thêm tính năng lớn** (Multi-process Runtime). API chưa đông cứng. |
| 0.9 | `4 - Beta` | Chỉ sửa nhỏ + chờ feedback; API coi như đã chốt, hardening trước 1.0. |
| 1.0 trở đi | `5 - Production/Stable` | Bản ổn định. |

Quá trình tiến tới 1.0: 0.8 thêm tính năng Runtime + chỉnh config một phần, 0.9 dọn
nốt config + chờ feedback, 1.0 stable.

> ### ⭐⭐ 0.8 là bản ALPHA CUỐI CÙNG - và đó là một ràng buộc, không phải một ghi chú
>
> Bảng trên nói 0.9 đổi sang `4 - Beta`, nơi *"API coi như đã chốt"*. Nên **0.8 là lần
> cuối được đổi API thoải mái.**
>
> Hệ quả trực tiếp cho việc đang làm (rút ra 2026-08-19):
>
> | | |
> |---|---|
> | **Mảng "đổi API adapter một lượt" phải làm ĐỦ ở 0.8** | Sót một chỗ là sót vĩnh viễn, hoặc phải phá tương thích ở Beta |
> | ⚠ ~~**`0.8.1` chỉ được HIỆN THỰC, không được đổi API**~~ | ⛔ **CHỦ DỰ ÁN NỚI 2026-08-19**: *"0.8 đang có nhiều phiên bản con nữa mà, vẫn nhiều cơ hội để đổi"*. Nguyên tắc *"0.7.x không đổi API"* **KHÔNG suy sang 0.8.x** - phiên tự suy ra và suy sai. ⭐ Lý do nới hợp lý: 0.7.x là dòng **đã phát hành, 31 app đang chạy trên nó**; 0.8.x là dòng **đang xây**, chưa ai ngoài dự án dùng. Hai hoàn cảnh khác nhau nên không dùng chung một luật |
>
> ⭐ Vẫn nên chốt tên cho **nhóm adapter kết nối RA** ngay ở 0.8 - không phải vì cấm đổi,
> mà vì **đổi một cái tên sau khi ba adapter đã dùng nó thì phải sửa cả ba**, và vì hình
> dạng cấu hình của chúng đã chốt rồi thì để trống một cái tên là tự tạo việc cho mình.

**Việc cần làm khi phát hành các bản tương ứng** (chỉ sửa `pyproject.toml`):

- **0.7:** ✅ đã giữ `Development Status :: 3 - Alpha` khi phát hành. (Phần vá
  metadata từng xếp vào đây - classifier `Typing :: Typed` + license PEP 639 -
  đã làm ở 0.6.3.)
- **0.8:** giữ `Development Status :: 3 - Alpha`. ⭐ **Đây là bản Alpha cuối** - xem khối trên.
- **0.8.x:** giữ Alpha, và **không đổi API công khai một dòng nào**.
- **0.9:** đổi `3 - Alpha` -> `4 - Beta`.
- **1.0:** đổi `4 - Beta` -> `5 - Production/Stable`.

---

## 0.3 - Hardening & hoàn tất gRPC

Chi tiết đầy đủ: `phien-ban/0.3-ke-hoach.md`.

- Nhóm 1 vá bug: warn `def` vs `async def` (#9), interceptor abort hai lần (#2),
  default `str(exc)` lộ nội bộ (#1a), `asyncio.Lock` cert rotate (#7), bỏ
  hardcode `server_id="default"` (#8).
- Nhóm 2: retry policy YAML cho gRPC client.
- Nhóm 4: bump `0.3.0` + cập nhật docs + CHANGELOG.

## 0.4 - Cross-cutting + starters

Chi tiết kế hoạch: `phien-ban/0.4-ke-hoach.md`. Nguồn ý tưởng: `sap-toi/wishlist-tinh-nang.md`
(mục "Security / Cross-cutting" và "Starters").

- Trích xuất danh tính peer mTLS (CN client cert) -> `request_context`, key
  trung tính + helper `current_caller()`. (đề xuất notification mục 1)
- `cache/` starter (Protocol `CacheService`) + `redis/` starter (client +
  impl của CacheService).
- Cân nhắc thêm (chưa chốt cứng): gRPC reflection + health checking; error
  catalog visibility-aware (#1b).

## 0.5 - Kiểm toán toàn diện + Messaging/IoT + File

> **ĐÃ PHÁT HÀNH 2026-06-22.** Cả ba nhóm hoàn tất: audit toàn diện (báo cáo
> `kiem-toan/0.5.md`, mọi phát hiện đã xử lý), adapter MQTT (pub/sub + RPC over
> MQTT v5), storage starter (local + s3/MinIO) + streaming web. Test: 1051 passed,
> 4 skipped. Chi tiết thực thi: `phien-ban/0.5-ke-hoach-thi-cong.md`.

Chi tiết đầy đủ: `phien-ban/0.5-ke-hoach.md`. Kế hoạch THỰC THI chi tiết (thứ tự code,
file nào, pattern nào) + các quyết định đã chốt 2026-06-22:
`phien-ban/0.5-ke-hoach-thi-cong.md`.

> **Đổi phạm vi 2026-06-21:** bản gốc (chốt 2026-06-19) là bản KHÔNG thêm tính
> năng, chỉ kiểm toán. Chủ dự án quyết định gộp thêm hai mảng feature: **adapter
> MQTT (messaging/IoT)** và **làm việc với file (storage starter + streaming web)**.
> Audit vẫn là trục chính, làm trước; feature làm sau trên nền đã sạch.

- **Nhóm A - Kiểm toán toàn diện** (trục chính): đọc kỹ TỪNG FILE core/adapters/
  starters, ghi `docs/kiem-toan/0.5.md`, phân loại theo mức nghiêm trọng rồi mới
  vá. Gồm fix issue context-bleeding khi test ASGI in-process (dental-clinic #001):
  chuyển `RequestContextMiddleware` từ `BaseHTTPMiddleware` sang pure ASGI middleware.
- **Nhóm B - Adapter MQTT**: pub/sub message-driven (`@subscribe`) và RPC over
  MQTT v5 (`@rpc`), `MqttPublisher`, auto-reconnect, định tuyến bằng Subscription
  Identifier, extra `xime[mqtt]` (aiomqtt import lười).
- **Nhóm C - File**: storage starter (Protocol `StorageService`, backend local
  và s3/MinIO) theo pattern cache/redis, kèm streaming upload/download lớn ở web
  adapter (Range, multipart, chunked).

Phạm vi kiểm toán (đọc thật kỹ, không lướt):

- **Toàn bộ `xime/core/`** - DI container (scan, resolver, graph, registry),
  lifecycle, config hai tầng, context (`ContextVar`), event bus, security,
  transaction, exception hierarchy, metadata. Đây là nền, soi trước.
- **Toàn bộ `xime/adapters/`** - web, grpc (codefirst + client + tls +
  interceptors), socket. Soi từng file.
- **Toàn bộ `xime/starters/`** - sqlalchemy, jwt, scheduler (+ cache/redis nếu
  0.4 đã thêm).

Các trục cần soi xuyên suốt:

1. **Mâu thuẫn logic giữa các phần** - vd thứ tự interceptor (RequestContext ->
   Error -> custom), vòng đời context được set/clear nhất quán giữa web/grpc/
   socket, error mapping có đồng nhất ba transport không.
2. **Nhất quán cross-cutting** - các key trong `request_context` (request_id,
   peer_*, caller...), việc `clear_security()` luôn chạy ở teardown mọi adapter,
   quy ước mã lỗi/exception giống nhau giữa REST/gRPC/socket.
3. **An toàn async / race condition** - đã có tiền lệ #7 (channel rotation).
   Soi mọi chỗ chia sẻ state mutable giữa coroutine: registry, tls registry,
   client channels, event bus tasks.
4. **Rò rỉ tài nguyên** - channel (retired pool), AsyncSession, socket, scheduler
   job, gRPC server. PreDestroy có đóng đủ và đúng thứ tự không.
5. **Fail-fast lúc startup** - mọi sai cấu hình (thiếu binding, thiếu type hint,
   circular, thiếu provider TLS, controller lệch server_id) có nổ rõ ràng lúc
   startup không, hay âm thầm hỏng lúc runtime.
6. **Edge case marshal/serialize** - bytes/decimal/uuid/date/optional/repeated/
   map/nested/enum. Đã từng có bug ở đây (#3, #marshal bytes) -> soi kỹ lại.
7. **Khoảng trống test** - `tests_temp/` (tên cho thấy có thể là thư mục tạm,
   cân nhắc chuẩn hóa thành `tests/`). Tìm nhánh code chưa có test, nhất là
   đường lỗi và teardown.
8. **Dọn backlog tồn đọng** - đối chiếu `kiem-toan/backlog-sua-loi.md`, các mục `[ ]` còn
   mở ở `thiet-ke/08-grpc-client-mtls.md` (dọn dẹp data-service phía service), TODO
   rải trong code.

Cách làm đề xuất khi tới 0.5: đi theo từng package, mỗi file ghi phát hiện vào
một báo cáo kiểm toán (`docs/kiem-toan/0.5.md`), phân loại theo mức nghiêm trọng,
rồi mới vá. KHÔNG vừa đọc vừa sửa lung tung để tránh bỏ sót.

## 0.6 - Thay `dependency-injector` + dynamic interface binding

Kế hoạch chi tiết: `phien-ban/0.6-ke-hoach.md`. **Cả hai việc ĐÃ CODE XONG 2026-06-23**;
full suite **1084 passed / 4 skipped**.

- **Việc 1** - thay `dependency-injector` bằng registry singleton tự viết:
  `registry.py` viết lại bằng dict + `RLock` double-checked, API không đổi, đã gỡ
  thư viện khỏi `pyproject.toml`; benchmark build ~8x / warm get() ~2x nhanh hơn
  backend cũ.
- **Việc 2** - dynamic interface binding: **mở rộng chính `bind`** - value có thể
  là tuple nhiều impl (phần tử đầu = mặc định); bật/tắt bằng cờ runtime
  `xime.di.dynamic-binding` (mặc định tắt = hành vi cũ); khi bật, đổi động **toàn
  cục** qua `Switcher` (`use`/`reset`) với **proxy trong suốt** (`DynamicProxy`)
  nên consumer giữ nguyên code. KHÔNG thêm `bind_many`/`Switchable`. Chuẩn hóa
  binding làm trong `_prepare_dynamic_binding()` (không sửa resolver); `Switcher`
  luôn đăng ký (disabled khi tắt cờ); cờ tắt không auto-register impl. Chi tiết +
  ghi chú thực thi: `phien-ban/0.6-ke-hoach.md` mục 2.5/2.7.

Đã phát hành: version `pyproject.toml` + CHANGELOG đồng bộ 0.6.0 (commit `v 0.6.0`).

## 0.6.1 - Web adapter: middleware lấy DI/config qua marker + `configure_cors`

Bản vá nhỏ (phát hành 2026-06-29), tương thích ngược hoàn toàn. Xuất phát từ thực
tế hai app (`shop`, `dental-clinic` ở `D:\code\Monolithic`) phải subclass
`WebAdapter` chỉ để gắn JWT middleware cần service từ DI và CORS đọc từ config.

- **Marker `Inject` / `FromConfig`** (`adapters/web/_markers.py`): dùng làm giá trị
  option khi gọi `configure_middleware(...)`, framework phân giải lúc `build_app`
  (sau khi DI container dựng xong). `Inject(SomeType)` -> singleton DI;
  `FromConfig("a.b", default)` -> `RuntimeConfig` theo dot-notation. Giá trị không
  phải marker giữ nguyên.
- **`configure_cors(...)`** (`adapters/web/_cors.py`): helper CORS hạng nhất theo
  pattern `configure_*`; tham số để trống tự đọc `cors.<tên>` từ `application.yml`,
  thiếu thì về mặc định Starlette.
- **`CrudRepository[T]`** (`starters/sqlalchemy/repository.py`): base repository
  generic cho sẵn CRUD chung (`find/find_or_fail/find_all/exists/count/save/
  save_all/delete`) + exception `EntityNotFoundError` - giảm boilerplate
  `BaseRepository` mỗi app tự viết (xuất phát từ issue-003 của `shop`). `model` là
  abstract property -> lớp nền là abstract, DI scanner bỏ qua; chỉ subclass set
  `model` mới vào DI nên không sinh singleton thừa.
- Full suite **1101 passed / 4 skipped**. Không có doc kế hoạch riêng; chi tiết
  trong CHANGELOG mục `[0.6.1]`, `rules/config-discovery.md` và `docs/.../starters.md`.

## 0.6.2 - Starter `mail` (SMTP) + hardening sau kiểm toán

Phát hành 2026-06-30. Thêm starter `mail` theo đúng khuôn starter sẵn có
(Protocol `MailService` + backend `SmtpMailService` qua aiosmtplib, extra
`xime[mail]`), kèm hardening từ **kiểm toán toàn diện** (`kiem-toan/0.6.md`:
không có lỗi CAO). Full suite **1125 passed / 4 skipped**. Chi tiết: CHANGELOG
mục `[0.6.2]`.

## 0.6.3 - Gỡ chặn app chạy thật: `PEER_APP_ID` + TLS web adapter + `read_only()`

Phát hành 2026-07-29. Tương thích ngược hoàn toàn. Full suite **1223 passed /
5 skipped**. Chi tiết: CHANGELOG mục `[0.6.3]`.

Hai việc đầu xuất phát từ khảo sát "4 mắt xích còn đứt" khi đưa 6 app lên chạy
thật (`D:\code\xime\.claude\docs\khao-sat-ha-tang-cho-app-chay-that.md`); việc
thứ ba đến từ phản hồi khi viết app.

- **`PEER_APP_ID` - định danh APPLICATION từ SAN client cert.** Cert của tiến
  trình thuộc một app mang SAN URI `xime-app://<Base62 33 ký tự>`; framework đọc
  ra, cắt scheme, lưu cạnh `PEER_CN` trong `request_context`, phơi qua
  `current_app_id()`. `PEER_CN` = tiến trình gọi, `PEER_APP_ID` = app sở hữu tiến
  trình đó. SAN là property **nhiều giá trị** nên duyệt hết entry; fail-soft
  tuyệt đối; framework không giải mã, không kiểm quyền. Bối cảnh + kiểm chứng:
  `da-phu-dinh/peer-app-id-tu-san-cert.md`.
- **TLS/HTTPS cho web adapter** (mục A1 của khảo sát). Khối `server.ssl` trong
  `application.yml` -> `ServerTlsConfig`; để trống = HTTP thuần như cũ.
  `cert_reqs` dùng chữ (`none`/`optional`/`required`) thay vì số `ssl.CERT_*`.
  Validate fail-fast trong `_tls_kwargs()` vì lỗi gốc của uvicorn khi cert khai
  nửa vời là không debug được (`AssertionError` rỗng message). Multi-server:
  `WebAdapter(..., ssl=...)`, để trống thì **kế thừa** `server.ssl` để server phụ
  không âm thầm chạy HTTP. **Mức 2 (cert in-memory) đã BỎ HẲN** - nó không tránh
  được việc key chạm đĩa nên không giải quyết được vấn đề nó sinh ra để giải
  quyết; thay bằng ghi chú "mức 1.5" (nạp đè `load_cert_chain` lên context đang
  phục vụ, đã kiểm chứng bằng handshake thật) cho lúc cần gia hạn không restart.
  Chi tiết + quyết định: `thiet-ke/07-tls-web-adapter.md`.
- **Khối chỉ đọc `read_only()`** - trước đó mọi truy cập DB, kể cả một câu
  `SELECT`, đều phải bọc `async with self.transaction():`, nên service chỉ đọc vẫn
  phải nhận `TransactionManager` và khối transaction xuất hiện dày tới mức không
  còn cho biết chỗ nào thật sự có ghi. Nay có `ReadOnlyManager` -
  manager **riêng, cùng cấp** với `TransactionManager` (chốt như vậy để sau này
  trỏ đường đọc sang read replica chỉ bằng một dòng `bind`). Không bao giờ commit;
  lồng nhau thì mượn session đang chạy; `expunge_all()` trước `rollback()` để
  entity còn dùng được sau khối. Framework **không chặn** việc sửa entity đọc
  ngoài transaction - cố ý, bù bằng quy tắc tài liệu. Chi tiết:
  `rules/transaction.md`, `docs/{vn,en}/transaction.md`.
- **`RuntimeConfig.get_bool()`** - vá B1: cờ `xime.di.dynamic-binding` từng đọc
  bằng `bool()` trần nên `"false"` dạng chuỗi bật nhầm tính năng. Nay ép kiểu
  bằng chính bộ parse boolean của Pydantic, giá trị lạ -> `StartupException`.
- **Metadata gói**: classifier `Typing :: Typed` + license PEP 639 (dời từ 0.7).
  Thêm `cryptography` vào extra `dev` (test TLS cần sinh cert tự ký).
- **Docstring `DynamicProxy`** - ghi caveat B2 về thứ tự `post_construct` khi bật
  dynamic binding (không đổi code).

## 0.7 - Fieldbus công nghiệp (Modbus TCP + OPC UA)

Chi tiết đầy đủ + thiết kế đã chốt: `phien-ban/0.7-ke-hoach.md`. Dời từ 0.5 (quyết 2026-06-21).
**Thiết kế chốt 2026-06-23** (chủ dự án trả lời hết câu hỏi mở); **bốn điểm chờ
quyết cuối cùng chốt 2026-07-29** - không còn gì chặn việc bắt tay code.

- **Chốt 2026-07-29:** pool connection Modbus **key theo TÊN LOGIC** của thiết bị
  (`modbus.devices.<tên>`, đúng khuôn `client_id` của MQTT); `read(device)` **gom
  nhiều range** thay vì một block lớn (block lớn quét trúng địa chỉ thiết bị không
  có -> ILLEGAL DATA ADDRESS, hỏng cả lần đọc); slave **tách datastore theo
  `unit_id`**; phát hành **trọn gói `0.7.0`** cả Modbus lẫn OPC UA. Kèm **bước 0**
  bắt buộc: cài `pymodbus` (nay đã 3.14) + `asyncua` và xác minh API thật trước
  khi viết codec.

- Xime đóng vai client/master chủ động đọc PLC/thiết bị nhà máy - mô hình
  polling/subscribe, khác cả RPC lẫn pub/sub của MQTT.
- **Đã chốt:** không edge gateway (giao tiếp trực tiếp) -> CẦN làm; Modbus làm CẢ
  client lẫn server; CẢ polling + on-demand; OPC UA hỗ trợ TẤT CẢ mức security;
  làm CẢ Modbus và OPC UA trong 0.7.
- **Trục chính = Device Model khai báo** (`@device`/`@node_model` + field
  descriptor `Holding/Coil/Input/Node`, framework lo decode/encode thanh ghi -
  tương đương DTO/contract của fieldbus, đây là chỗ "framework làm nhiều việc").
- Luồng device-driven dùng decorator riêng `@poll`/`@on_change`/`@serve`/
  `@on_write` trong adapter (tái dùng hạ tầng concurrency của MQTT), KHÔNG dựa
  scheduler. Hai adapter độc lập, import lười, extra `xime[modbus]`/`xime[opcua]`.

## 0.8 - Đa tiến trình + đổi API adapter một lượt

> ⚠⚠ **THIẾT KẾ ĐỔI HẲN NGÀY 2026-08-16.** Mục này trước đây mô tả bản thiết kế
> 2026-06-27 (Bus Manager, shared queue, DI scope `global`/`worker`, mặc định TẮT).
> **Phần lớn bản đó không còn cần** - đọc hai tài liệu mới, đừng đọc
> [`da-phu-dinh/ke-hoach-0.8-ban-dau.md`](da-phu-dinh/ke-hoach-0.8-ban-dau.md) như hiện trạng:
>
> - [`thiet-ke/10-da-tien-trinh.md`](thiet-ke/10-da-tien-trinh.md)
>   - mô hình chạy, `main.py`, cấu hình, adapter
> - [`thiet-ke/09-kho-lien-tien-trinh-boi-canh.md`](thiet-ke/09-kho-lien-tien-trinh-boi-canh.md) -
>   kho liên tiến trình (LMDB + shared memory), lý do hoãn đa luồng
> - **[`thiet-ke/11-bus-lien-tien-trinh.md`](thiet-ke/11-bus-lien-tien-trinh.md)** -
>   **bus (`ProcessLink`), thiết kế đóng 2026-08-18**
>
> `da-phu-dinh/ke-hoach-0.8-ban-dau.md` **nên được viết lại chứ không bổ sung**.

Trạng thái: **CODE XONG 2026-08-20**, rà trước phát hành 2026-08-20, và **kiểm
toán toàn diện bốn đợt + vá xong 2026-08-21**. **ĐÃ PHÁT HÀNH 2026-08-21** (bản thứ 14).

> ⛔ Dòng cũ ghi *"chưa code"* đã lỗi thời hai lần: nó đã code xong, rồi đã được
> kiểm toán và vá xong.

### ✅ Nợ luật 03 của `EventBus.publish()` ĐÃ TRẢ ở bản này

Nợ khai từ 0.7.2 (*bên gọi không phân biệt được event **bị bỏ** với event **đã
xếp lịch** - cả hai trả `None`*) và cố ý hoãn tới 0.8 vì đóng nó là **đổi chữ ký
công khai**. `publish()` nay trả `PublishOutcome` với **ba** giá trị:
`SCHEDULED` / `NO_HANDLERS` / `DROPPED`.

⭐ Đây là **chuyến cuối**: 0.8 là bản Alpha cuối, và 0.9 trở đi API coi như đã
chốt. Nợ được xếp lên đúng chuyến đó, và nó đã lên.

⚠ **Không phá ai**: 31 ứng dụng bỏ qua giá trị trả về chạy y nguyên.

### Kiểm toán 2026-08-21: hai lỗi mà máy phát triển không thể thấy

| | |
|---|---|
| **C4** | Ngữ cảnh `multiprocessing` lệch nhau → **toàn bộ đa tiến trình chết trên Linux**. 26 test đỏ ở đó, 0 đỏ trên Windows, cùng một mã nguồn |
| **C5** | `SocketAdapter.assign_slot()` ném `AttributeError` - `mypy` là thứ duy nhất tìm ra, và mypy không nằm trong extra `dev` cho tới chính đợt đó |

⭐⭐ **Bài học cho mọi bản sau: Windows là máy phát triển, Linux là máy chạy
thật, và có những lớp lỗi mà máy phát triển KHÔNG THỂ nhìn thấy về mặt cấu
trúc.** Không phải test yếu - điều kiện gây lỗi không tồn tại ở đó. Từ 0.9, một
lượt chạy bộ test trên Linux nên là điều kiện phát hành, không phải một việc làm
thêm khi có thời gian.

Báo cáo đầy đủ: [`kiem-toan/0.8-kiem-toan-toan-dien.md`](kiem-toan/0.8-kiem-toan-toan-dien.md).

**Nguyên tắc chia bản (chốt 2026-08-16):**

> **0.7.x không đổi API công khai một dòng nào; mọi thay đổi API gom vào 0.8.**
> Chủ dự án chốt *"đổi dứt khoát, không giữ hai đường"* - mà đổi dứt khoát rải rác
> qua nhiều bản patch là thứ tệ nhất cho 31 app dùng chung một cây mã editable.

| Nhóm | Gồm |
|---|---|
| **Mô hình chạy** | Supervisor **giữ socket nhưng không phục vụ** · `share_load()` · con là `python -m app.main` chạy lại với `XIME_PROCESS_ID`, sinh bằng `multiprocessing` · thăng cấp primary · kênh cha-con |
| **Cấu hình** | Khối `processes` ba/bốn tầng · `add_config(module)` thay `config_module` · `count: N` · `shared: true` |
| **Đổi API adapter một lượt** | Tên định danh thống nhất · tách `client_id` khỏi `server_id` · cổng đến từ cấu hình chứ không từ constructor · hạng nhân bản là dữ liệu · **vòng đời + tín hiệu ready (F10, chuyển từ đợt 3 của kế hoạch bảo mật)** |
| **Fieldbus** | Tách **loại** khỏi **thực thể** · `@poll` chạy per-instance · log khi bỏ qua adapter · lỗi rõ khi gọi thiết bị không thuộc tiến trình mình |
| **MQTT** | Ba việc ở 5.7.4 của tài liệu đa tiến trình - đều **chỉ có nghĩa khi có nhiều tiến trình** |
| **Kho liên tiến trình** | **Nhóm 1 `RefData`: ✅ THIẾT KẾ XONG 2026-08-18** ([`thiet-ke/12-kho-refdata.md`](thiet-ke/12-kho-refdata.md)) - shared memory hai-bản-đổi-con-trỏ, `read()` trả object, chỉ primary ghi, chia đoạn khi lớn. **Nhóm 2 `Store` trên LMDB: ✅ THIẾT KẾ XONG 2026-08-19** ([`thiet-ke/13-kho-store-lmdb.md`](thiet-ke/13-kho-store-lmdb.md)) - ba lớp nền, cấu hình bằng tham số class, chia file theo `crc32(key) % parts`, lỗi báo bằng ngoại lệ |
| **Bus** (`ProcessLink`) | ✅ **THIẾT KẾ ĐÓNG 2026-08-18** - [`thiet-ke/11-bus-lien-tien-trinh.md`](thiet-ke/11-bus-lien-tien-trinh.md). Bộ nhớ chung, **mỗi tiến trình một vùng ghi riêng**, semaphore làm chuông và bitmap làm sự thật, **cha KHÔNG nằm trên đường đi**. Bốn kết cục cho `ask`, at-most-once, đầy thì vòng lại đè. Ca dùng đầu tiên: **lệnh điều khiển fieldbus** |
| ✅ ~~**Còn treo, chặn phần thăng cấp**~~ | **ĐÓNG 2026-08-18**: thêm Protocol **`RunOnce`** (`run_once()`), cạnh `post_construct`/`pre_destroy`. Bài toán là **hai trục bốn ô**; ba ô đã có nhà, ô *một lần cho cả cụm* nay có nhà. ⚠ Còn lại là thi công: **`SchedulerRunner` chưa phải Adapter** |

**Ba thứ của bản 2026-06-27 KHÔNG còn dùng:** Bus Manager + shared queue + transport
abstraction (**bus nay đi qua bộ nhớ chung, cha không chuyển tiếp tin nào**) ·
DI scope `global`/`worker` (nay **DI dựng đủ ở mọi tiến
trình, cái nào không được chạy thì tắt bằng cờ**) · "Worker 0 chết thì crash toàn
chương trình" (nay supervisor **thăng cấp** một con đang chạy).

**Đường cắt nếu 0.8 quá dài:** ba nhóm đầu là hạ tầng nền, đủ cho một app web/gRPC
chạy nhiều tiến trình. Ba nhóm fieldbus/MQTT/bus phục vụ hướng IoT-nhà máy, mà **hôm
nay chưa app nào dùng Modbus/OPC UA/MQTT thật** nên chúng không chặn ai.

## 0.8.1 - uvloop trên Linux

Trạng thái: **ĐÃ PHÁT HÀNH 2026-08-22.** Code xong, **bốn phép đo Linux đã chạy**,
commit `d5b5806` + tag `v0.8.1` ở repo phát triển và `4ac504f` + `v0.8.1` ở repo phát
hành, gói lên PyPI lúc 07:32 UTC với **SHA256 khớp từng bit** gói dựng ở máy này.

| Nghiệm thu | |
|---|---|
| Bộ test **Linux** | **2552 / 6 / 0** - và **cũng 2552/6/0 khi chạy dưới uvloop thật** |
| Bộ test **Windows** | **2534 / 24 / 0** (2510 cũ + **16** uvloop + **8** cảnh báo `@ws`) |
| **Tổng, cả hai bên** | **2558**. ⚠ Nghiệm thu bằng **tổng**, đừng bằng `passed` - nó khác nhau theo nền tảng |
| `mypy xime/` | **41 lỗi = đúng mốc 0.8.0**, bản vá không thêm cái nào |
| `ruff check xime/` · `.claude/scripts/benchmark/` | sạch |
| Chạy thật một tiến trình | Windows `ProactorEventLoop` · **Linux `uvloop.Loop`** |

⛔⭐ **Phép đo lãi thật lật một giả định của chính bản này: uvloop KHÔNG tăng tốc REST
của Xime, nó làm chậm ~10%.** Ranh giới thật không phải giao thức mà là **loại việc**:
xử lý một request kiểu HTTP thì lỗ 8-9% (REST 0.91x, **bắt tay WebSocket 0.93x**),
truyền trên kết nối đã mở thì lãi 11-38% (**tin nhắn WebSocket 1.11x**, loop trần
1.38x). **Vẫn giữ uvloop** - lý do ở
[`kiem-toan/0.8.1-ket-qua-do-tren-linux.md`](kiem-toan/0.8.1-ket-qua-do-tren-linux.md)
và [`ghi-chep/benchmark-hieu-nang.md`](ghi-chep/benchmark-hieu-nang.md) mục 6.

⭐ **Chuyến đo đẻ thêm một thứ ngoài đề bài: framework nay CÓ bộ benchmark**
(`.claude/scripts/benchmark/`, năm tầng). Trước đây không có cái nào.

⭐⭐ **Và nó tìm ra ca thứ BA của "lỗi máy phát triển không thể thấy"**:
`test_linux_never_switches` khoá `worker_loop_factory(...) is None` trên Linux, **xanh
trên Windows kể cả sau khi bản vá làm nó sai**, vì ở đây `uvloop_factory()` luôn trả
`None` nên monkeypatch `sys.platform` không đổi được kết quả. **Phép đo đó đo nền tảng
thật, không đo nền tảng được monkeypatch.**

✅ **Việc 7 (cảnh báo khi có route `@ws` mà thiếu thư viện WebSocket) cũng đã làm
2026-08-22** theo yêu cầu chủ dự án - `xime/adapters/web/ws/_availability.py`, 8 test,
3 đối chứng. ⚠ Nó **không phải chuyện cài thư viện**: máy này đủ (`websockets 16.0`,
`httptools` đang chạy); đây là cảnh báo cho **người dùng framework** cài `uvicorn` trần.

⚠⚠ **Không phép đo nào ở trên chạm vào uvloop** - trên Windows `uvloop_factory()` luôn
trả `None`. Chúng chỉ chứng minh **đường dây nối đúng**, không chứng minh uvloop chạy
được. Xem mục 12 của tài liệu thiết kế.

Thiết kế đầy đủ, tới mức code được:
**[`sap-toi/tang-toc-uvicorn-uvloop.md`](sap-toi/tang-toc-uvicorn-uvloop.md)**.
Không cần thêm vòng thiết kế nào.

### Vấn đề

`pip install xime[web]` kéo `uvicorn[standard]`, nên **uvloop đã nằm sẵn trên đĩa ở
mọi cài đặt Linux** - và nó **chưa bao giờ chạy**. Xime gọi `uvicorn.Server.serve()`,
còn `loop_factory` chỉ được đọc trong `Server.run()`, nhánh xime không đi qua.
`httptools` và `websockets` thì lại chạy thật vì chúng được chọn trong
`config.load()` nằm bên trong `_serve()`.

⭐ Ba cơ chế trông **giống hệt nhau từ ngoài** (cùng khuôn `auto.py`, cùng cách dò),
nhưng một cái nằm ở nhánh ta không đi qua. Nhìn `pip list` thấy đủ bốn gói rồi kết
luận *"đã bật tăng tốc"* là sai, và **không có gì báo**.

### Việc phải làm

| # | Việc |
|---|---|
| 1 | `xime/core/bootstrap/_loop.py` + `uvloop_factory()` - trả `None` khi không import được |
| 2 | Ghép vào `worker_loop_factory` (`_supervisor.py`). ⛔ **Giữ nguyên nhánh Windows selector** |
| ~~3~~ | ~~Sửa `asyncio.run` ở nhánh không `share_load`~~ - xem đính chính dưới |
| 4 | Log **loop đang chạy thật** trong `_run_async()`. **Bắt buộc** |
| 5 | Test canh |
| ~~6~~ | ~~**Bốn phép đo trên Linux**~~ ✅ xong 2026-08-22, ba ĐẠT + một lật giả định |
| ~~7~~ | ~~WARNING khi app có route `@ws` mà thiếu thư viện WebSocket~~ ✅ xong |
| ~~8~~ | ~~`CHANGELOG.md` + con trỏ~~ ✅ xong |
| ~~9~~ | ~~**Tài liệu người dùng**~~ ✅ xong 2026-08-22: trang mới `docs/{vn,en}/event-loop.md` (loop nào đang chạy · Xime chọn thế nào · số đo lãi/lỗ · vì sao không có công tắc) + mục *"cần cài gì"* của `websocket.md` - trang đó trước nay **không nói một chữ nào** về thư viện WebSocket, trong khi bản này vừa thêm cảnh báo về đúng chuyện đó |

**Toàn bộ tám việc đã đóng.** Còn lại là commit/tag/PyPI của chủ dự án.

### ⛔ Đính chính: việc số 3 KHÔNG còn tồn tại

Tài liệu viết 2026-08-20, giữa lúc 0.8.0 đang thi công, nên nó mô tả **hai** đường vào
`asyncio.run` và cảnh báo *"sửa một chỗ quên chỗ kia là dạng lỗi tệ nhất ở đây"*.

Code 0.8.0 sau kiểm toán **đã hợp nhất còn một đường vào duy nhất**: cả ba nhánh của
`run()` (đơn tiến trình · supervisor · worker) đều rơi vào `Application._run_worker()`,
nơi có đúng một lời gọi `asyncio.run(..., loop_factory=worker_loop_factory(sockets))`.

> Rủi ro *"vá một nửa"* nay **không tồn tại về mặt cấu trúc**, chứ không phải được
> tránh nhờ cẩn thận. Sửa `worker_loop_factory` là phủ hết mọi đường vào.

⚠ Chỗ phải cẩn thận khi sửa hàm đó: điều kiện hiện tại
`if sys.platform != "win32" or not sockets: return None` **gộp hai chuyện khác nhau
vào một dòng**. Phải tách thành ba nhánh thật (Windows có socket kế thừa -> selector ·
Linux/macOS -> uvloop · còn lại -> `None`).

### ⚠ Linux ở đây là để CHẠY THỬ LẦN ĐẦU, không phải để nghiệm thu

uvloop **không có wheel Windows và sẽ không bao giờ có**. Nên trên máy dev,
`uvloop_factory()` **luôn trả `None`**, tức **nhánh mới viết ra không chạy một lần
nào**. Bộ test ở Windows chỉ chứng minh được **không hồi quy**.

Nặng hơn bài học C4/C5 của 0.8 một bậc: ở đó *điều kiện gây lỗi* không tồn tại trên
Windows; ở đây **chính tính năng** không tồn tại. Cái giá đó không xoá được, chỉ bù
được bằng **bốn phép đo** ở mục 5 của tài liệu (bắt tay TLS thật · `SO_PEERCRED` của
socket adapter · `share_load()` với socket kế thừa · **lãi thật**), không bù bằng
niềm tin.

📌 ✅ **Đã đi đúng như dự kiến**: chuyến 2026-08-22 chạy trên chính máy Linux của chủ
dự án (Debian 13, Python 3.13.5), không cần VPS. ⏳ Hai phép đo `Store`/LMDB **vẫn còn
chờ** - chúng không chặn gì.

### Thứ cố ý KHÔNG làm

| | |
|---|---|
| **Công tắc bật/tắt uvloop** | Có thì dùng, không có thì thôi. Muốn tắt thì `pip uninstall uvloop`. Một công tắc chưa ai cần là một nhánh code chưa ai chạy |
| **Khai `uvloop` thành phụ thuộc riêng** | `uvicorn[standard]` đã khai kèm marker nền tảng. Khai lại là dựng sàn thứ hai phải bảo trì |
| **Bắt buộc phải có uvloop trên Linux** | Đây là **tối ưu**, không phải sửa lỗi. Thiếu nó thì app chạy đúng như hôm nay, chỉ chậm hơn |
| **Mong uvloop giúp gRPC** | `grpcio` chạy trên core C riêng, không dùng transport asyncio. Phần hưởng lợi là **web, socket, MQTT** |

📌 Lý do hoãn số 3 của tài liệu dựa vào luật *"0.8.1 chỉ được hiện thực, không đổi
API"*. **Luật đó đã bị chủ dự án nới 2026-08-19**, nhưng kết luận không đổi: bản vá
này vốn không có bề mặt API nào để mà vướng.

## 0.8.2 - fieldbus chia tải + MQTT chia tải + `drain()` lúc tắt

Trạng thái: **CHỐT 2026-08-22, chưa code.** Chủ dự án: *"mấy cái fieldbus + MQTT +
drain() tôi cũng chưa cần bây giờ."*

| Việc | Đã có gì ở 0.8.0 | Còn thiếu |
|---|---|---|
| **Fieldbus chia tải** (Modbus/OPC UA) | Chữ ký **đã khai xong**: `devices_of()`/`servers_of()`, `@poll`/`@on_change` đã bỏ `device=` | Cấu hình bốn tầng `process -> modbus -> loại -> thực thể` · handler chạy **một lần mỗi thực thể** · log khi bỏ qua adapter · lỗi rõ khi gọi thiết bị không thuộc tiến trình mình · chiều ghi đi qua `ProcessLink` |
| **MQTT chia tải** | Metadata **đã có**: `unique_per_process=("client_id",)` + `disjoint_per_process=("topics",)`, và supervisor **đã kiểm chéo** hai ô | Việc 3 của mục 5.7.4: **topic filter đến từ cấu hình**, `@subscribe` chỉ còn là bảng định tuyến · cảnh báo route không tiến trình nào nghe |
| **`drain()` lúc tắt** | `EventBus.drain()` đã có | Framework **không bao giờ tự gọi**, nên handler đang chạy bị cắt ngang. Sửa tử tế thì chạm vòng đời adapter |

### Vì sao tách khỏi 0.8.1

**Tách rủi ro** - đúng lập luận mà chính tài liệu uvloop đã dùng để tự hoãn khỏi
0.8.0: gộp lại thì ngày có sự cố trên Linux không biết thủ phạm là uvloop hay
fieldbus; tách ra thì mỗi lần đổi có **đúng một nguyên nhân**.

Cộng hai điều kiện thật:

- **uvloop có lãi ngay cho 31 app đang chạy**; ba mảng này thì **chưa app nào dùng
  Modbus/OPC UA/MQTT thật**, nên chúng không chặn ai.
- Chuyến Linux của chúng **nặng hơn hẳn**: cả ba đều là mảng **đa tiến trình**, đúng
  vùng mà C4 đã chứng minh máy Windows không nhìn thấy lỗi về mặt cấu trúc (26 test
  đỏ trên Linux, **0 đỏ trên Windows**, cùng một mã nguồn).

### ⚠ Hạn chót có thật: phải nằm trong dòng 0.8.x

Cả ba đổi khoá cấu hình, tức **đổi API công khai**. 0.8 là bản Alpha cuối; **0.9 sang
Beta nơi API coi như đã chốt**. 0.8.2 vẫn là 0.8.x nên thoả - nhưng đừng để trôi tiếp.

### Ba thứ hoãn có ý thức, KHÔNG thuộc 0.8.2

Chủ dự án xác nhận lại 2026-08-22: *"mấy thứ bạn gợi ý hoãn tôi cũng thực sự muốn
hoãn."*

| | Vì sao hoãn được |
|---|---|
| **Cha không có mồm** (mục 2.8c) | Chưa chốt hình dạng, còn bốn phương án đang cân |
| **Supervisor trông tiến trình ngoài** (câu F) | Chủ dự án 2026-08-19: *"giờ tôi chưa biết dùng nó để làm gì, chưa có nhu cầu"* |
| **Tắt êm** | Chưa bàn thiết kế; nó là lý do trường *"mức bận"* bị cắt khỏi watchdog |

⭐ Cả ba **không phải API**, nên thêm vào 0.8.3 hay 1.1 đều được - khác hẳn ba việc của
0.8.2 vốn có hạn chót thật.

## 0.9 - Beta: config nốt + bug fix + phản hồi người dùng

Trạng thái: **Mở**.

- Phần config cải thiện còn lại từ 0.8 (nếu có).
- Bug fix từ phản hồi người dùng sau 0.8.
- Đổi classifier sang `4 - Beta` khi phát hành.
- KHÔNG thêm tính năng lớn mới.

## Chưa gắn mốc (wishlist thuần)

Xem `sap-toi/wishlist-tinh-nang.md`: bidi streaming, `@proto_field`, sinh SDK từ
ContractModel, SDK đa ngôn ngữ, socket Transport -> TCP/Named Pipe, idempotency
helper, gRPC reflection/health (nếu 0.4 không lấy).
