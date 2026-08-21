# Bản đồ tài liệu cũ (dạng phẳng) - đã thay bằng `../README.md`

> **Trạng thái: BỊ THAY THẾ 2026-08-21.**
>
> Đây là mục *"Tài liệu thiết kế chi tiết"* của `.claude/CLAUDE.md` trước khi thư mục
> `docs/` được sắp xếp lại. Nó **tóm tắt lại nội dung của chính các file thiết kế** -
> tức một tầng bản sao phải bảo trì song song với bản gốc, và đó là lý do nó bị thay.
>
> Thay bằng [`../README.md`](../README.md): một dòng cho mỗi file, không tóm tắt lại.
>
> Giữ lại vì trong đây có vài câu diễn đạt không có ở file gốc. Cần thì moi ra, đừng
> đọc nó như hiện trạng - mọi đường dẫn trong này đã được sửa sang tên mới, nhưng nội
> dung thì đứng yên từ 2026-08-20.


- **Lộ trình phiên bản (0.3 -> 0.9, tra "việc X làm bản nào"):** `docs/lo-trinh-phien-ban.md`
- **Kế hoạch 0.8 (thiết kế ban đầu chốt 2026-06-27: Multi-process Runtime + Bus + config):** `docs/da-phu-dinh/ke-hoach-0.8-ban-dau.md`
- **Cache liên tiến trình - BỐI CẢNH (2026-08-16). ⚠ Phần thiết kế đã tách sang hai file riêng, xem hai mục ngay dưới:** `docs/thiet-ke/09-kho-lien-tien-trinh-boi-canh.md`
  - Chốt: **tách bus khỏi kho** · cache chia **HAI nhóm theo việc có nguồn bền vững hay không**
    (nhóm 1 tự viết shared memory hai-bản-đổi-con-trỏ, nhóm 2 **LMDB**, mỗi bảng một file) ·
    **đa tiến trình TRƯỚC, đa luồng để sau**
  - ⚠ Lý do hoãn đa luồng là **số đo, không phải sở thích**: `grpcio` chưa có wheel free-threaded
    và gRPC là xương sống của Xime, nên bật bản không GIL là **GIL tự bật lại** -> N luồng chậm
    hơn một luồng. `lmdb` cũng chưa có. Tín hiệu duy nhất đáng theo dõi để xét lại
  - ✅ **Bảng "chưa quyết" ở mục 3 ĐÃ ĐÓNG HẾT 2026-08-19** - xem `docs/thiet-ke/13-kho-store-lmdb.md`.
    ⚠ Ba câu **tan chứ không được trả lời** (câu 2 `AtomicStore` · câu 7 ba kết cục · câu 8 mở
    kho ở đâu): chúng giả định một hình dạng thiết kế mà buổi 08-19 không chọn. Đọc bảng đó
    như **lịch sử lập luận**, đừng đọc như việc còn phải làm. Và **3 chỗ bổ sung/lật một phần
    `docs/da-phu-dinh/ke-hoach-0.8-ban-dau.md`** (DI scope hai tầng -> bốn tầng, primitive asyncio không qua được ranh
    giới loop, kết nối DB nhân theo M×N); chỗ thứ tư (*kiểu queue*) **đã tan** vì bus bỏ hẳn
    queue chung
  - ⭐ **`link_id` của bus giải luôn mục 7.2** (số hiệu đời kho / fencing token) trong phạm vi
    một máy. ⚠ ~~Nhưng **7.1 `TrustKeyL2Cache` thì không**~~ - **dòng này HẾT ĐÚNG 2026-08-19**: khoá Trust có nguồn bền vững nên nó thuộc **nhóm 1**, `RefData` giải, và chủ dự án chốt **mỗi máy một kho riêng, mỗi máy tự gọi Trust một lần**
- **⭐⭐ Đa tiến trình: `main.py`, cấu hình, mô hình chạy (2026-08-16, PHẦN LỚN ĐÃ CHỐT):**
  `docs/thiet-ke/10-da-tien-trinh.md` - nửa sau cùng buổi với file trên.
  **Đọc mục 5 trước khi động vào `core/bootstrap` hoặc bất kỳ adapter nào**
  - **`main.py` chốt**: `import config` · `add_config(config)` · `use(...)` **ở mức module**;
    `if __name__` chỉ còn `share_load().run()`. **Không id tiến trình nào trong code** - cấu
    hình khai ma trận `process_id × server_id`, ô giao nhau là cổng
  - **Mô hình chạy chốt**: tiến trình gốc **giữ socket nhưng không phục vụ** (`bind`, không bao
    giờ `accept`, không dựng DI, không chết); con là `python -m app.main` **chạy lại** với
    `XIME_PROCESS_ID`, sinh bằng **`multiprocessing`** (truyền được socket **và** vẫn import lại
    main). Lý do chọn chạy lại thay vì entry riêng: **một đường khởi động duy nhất** - hai đường
    là hai bản trôi lệch, và loại lệch đó không có triệu chứng. `primary` nay là **con thứ
    nhất**, nên supervisor **thăng cấp** được con khác khi nó chết
  - **Chia tải theo adapter**: web + unix socket dùng **cha giữ socket** (chạy cả Linux lẫn
    Windows) · gRPC dùng **`SO_REUSEPORT`**, Windows **không có đường nào** → phải báo lỗi lúc
    khởi động, đừng để nổ bằng `WinError 10048` giữa chừng
  - ⭐ **BA hạng adapter, không phải hai**: nhân bản (web, grpc) · **phân mảnh** (modbus, opcua,
    **mqtt** - mỗi tiến trình một cụm thiết bị / một tập topic; nhân bản cho *dư thừa*, phân mảnh
    thì **không**) · **đơn nhất** (scheduler). ⚠ Bản đầu ghi *"bốn hạng"* khi mqtt còn xếp riêng;
    sửa 2026-08-19 vì phần 3 của mảng adapter dựng thẳng trên phân loại này
  - ⛔ **MQTT: giữ là CLIENT, KHÔNG tự viết broker** (5.7.4, chốt sau khi chủ dự án hỏi về nhà
    thông minh / nhà máy / nông nghiệp thông minh). Lý do nặng nhất: **firmware đầu kia không sửa
    được**, nên broker thiếu tính năng = thiết bị không kết nối được và không có đường vá. Dùng
    **Mosquitto** (EPL/EDL), lên **EMQX OSS** khi cần cluster - đổi broker chỉ là đổi một dòng
    `host`. ⭐ Cái đáng đầu tư thay vào đó: **Sparkplug B** · lưu chuỗi thời gian · engine quy
    tắc · **sổ đăng ký + danh tính thiết bị** (Xime đã có sẵn nền: Trust, hồn-xác, `PEER_APP_ID` -
    đây mới là chỗ khác được). Kèm **ba tín hiệu để xét lại**, chưa cái nào xuất hiện
  - **Chia tải MQTT: chia THEO TOPIC, không dùng shared subscription.** ⭐ Lý do quyết định là
    **thứ tự trong một thiết bị**: `$share` phát `bật`→`tắt`→`bật` cho ba tiến trình xử lý song
    song thì trạng thái ghi xuống DB là *cái nào thắng cuộc đua*, không phải cái đến sau. Cùng
    khái niệm partition key của luật 01 - khoá phải là **thiết bị/cụm**, ⛔ đừng chia theo loại đo.
    Ba việc còn nợ: tách `client_id` khỏi `_server_id` · `client_id`+`topics` vào khối `processes`
    (ba tầng, **không** cần bốn tầng như Modbus) · **topic filter phải đến từ cấu hình, không phải
    hằng trong `@subscribe`**. ✅ Backpressure thì **đã có** (semaphore trước `create_task`)
  - ⭐ **Fieldbus (5.7.3), chốt chiều**: tách **LOẠI** (`bang-tai`, code biết) khỏi **THỰC THỂ**
    (`BT-01`, cấu hình biết) - bốn tầng khoá `process → modbus → loại → thực thể`. Kèm luật
    **web KHÔNG gọi thẳng adapter fieldbus** (kernel chia request ngẫu nhiên nên gọi thẳng hỏng
    *một nửa số lần* - kiểu lỗi tệ nhất để gỡ): đọc qua DB/vùng nhớ chung, **ghi qua BUS**. Đây
    là ca dùng cụ thể đầu tiên của bus, và nó **dùng lại kênh cha-con vốn đã cần** cho thăng cấp
    primary nên gần như miễn phí
  - ⭐ **Nguyên tắc chủ dự án nêu (2): *"cứ thay đổi code framework thoải mái, để code phục vụ
    thiết kế"*** → đổi API dứt khoát, không giữ hai đường tương thích
  - ✅ ~~**Câu khó nhất còn lại: `post_construct` ở tiến trình phụ**~~ **ĐÓNG 2026-08-18** bằng
    Protocol **`RunOnce`** - xem khối *"Buổi 2026-08-18"* ngay dưới. Mô tả cũ của vấn đề:
    (mục 2.9). Không cắt được ở
    mức tiến trình (cắt luôn pool DB, key JWT) **và cũng không cắt được ở mức class** vì hook đặt
    trên method - `KeyRefreshJob` vừa nạp key ban đầu (mọi tiến trình cần) vừa chạy vòng lặp
    (chỉ primary). Kèm một cái giá chưa ai nêu: **hoãn là biến fail-fast thành fail-late**
  - ⭐ **`add_config(module)` không phải chuyện thẩm mỹ, nó là ĐIỀU KIỆN CẦN**: auto-discovery
    hiện tại dò bằng `__main__.__spec__.parent`, mà giá trị đó **khác ở tiến trình con** → im
    lặng rơi xuống `BindingConfig()` rỗng, DI trống, không gì báo. Kèm phát hiện
    `_import_config_siblings()` dùng `pkgutil.iter_modules` là **auto-scan, vi phạm chính
    `rules/config-discovery.md`**
  - ⭐ **Nguyên tắc chủ dự án nêu: adapter phải đổi theo thiết kế, thiết kế không đổi theo adapter**.
    Ca cụ thể: `MqttAdapter` gộp `_server_id = client_id`, và cái gộp đó **tạo ra một giới hạn
    KHÔNG có thật** ("MQTT không nhân bản được")
  - ⭐ **Nguyên lý DI**: DI = tổng khai báo trừ phần đơn nhất; **chỉ loại trừ được node ĐẦU DÒNG**
    (không ai phụ thuộc vào nó). Đề nghị biến thành **phép kiểm tự động** vì đồ thị đã có sẵn
  - ⚠ **Hai nguyên tắc rút ra khi chủ dự án bác đề xuất**: *một chốt chặn không được phụ thuộc
    thành phần TUỲ CHỌN* (bác khoá LMDB - nó vắng mặt đúng lúc cần nhất) · *đừng viết bộ cân
    bằng tải* - `SO_REUSEPORT` + nginx **cùng máy** lấy được cùng lợi ích mà không mất LMDB;
    thứ phá LMDB là **nhiều máy và cách ly filesystem**, không phải bản thân reverse proxy
  - Mục 8 liệt kê **19 đề xuất đã bị bác kèm lý do** - đọc trước khi đề xuất lại. Đáng nhớ nhất:
    **LMDB làm đệm ghi cho Postgres** (cái giá thật là *mọi đường đọc về sau phải nhớ hỏi LMDB
    trước*, nghĩa vụ không cưỡng chế được) · **cho MQTT qua bộ cân bằng tải** (sai chiều kết
    nối: app MQTT là client, không mở cổng nào)
  - Còn lại: **3 chỗ chủ dự án xem hôm sau** (tách đăng ký job khỏi chạy scheduler · cổng server
    phụ · luật "code mức module phải nhẹ") + 6 câu cũ ở mục 9.2
  - **Cộng với file cache, phần lớn `docs/da-phu-dinh/ke-hoach-0.8-ban-dau.md` không còn cần: nên VIẾT LẠI chứ không bổ sung**
- **⭐⭐ Bus liên tiến trình `ProcessLink` (2026-08-18, THIẾT KẾ ĐÓNG):**
  `docs/thiet-ke/11-bus-lien-tien-trinh.md` - thay hẳn phần Bus của `docs/da-phu-dinh/ke-hoach-0.8-ban-dau.md`, và **lật
  cả bản phác 5.7.4b** của file đa tiến trình. Chưa có một dòng code nào.
  - ⚠ **KHÁC HẲN `EventBus` trong `core/event/`**, không dùng chung một dòng nào. Tên cố ý không
    chung gốc từ (`link.ask` vs `event_bus.publish`) vì gọi nhầm thì **không có triệu chứng**:
    tin không bao giờ ra khỏi tiến trình, không lỗi, không log
  - **Cơ chế**: bộ nhớ chung (`shared_memory`), **mỗi tiến trình một vùng ghi riêng** nên không
    tranh chấp ghi và **giữ được thứ tự**; `mp.Semaphore` làm **chuông**, bitmap "ai chưa đọc"
    làm **sự thật**. ⭐ **Cha KHÔNG nằm trên đường đi** - hết nút cổ chai, hết điểm chết
  - **Định tuyến**: kênh + khoá, **lọc ở bên nhận**, `key` ở header nên lọc mà **chưa chạm
    payload**. Không có tên tiến trình ở bất cứ đâu - cùng lý do đã chặn `current_process_id()`
  - **Bốn kết cục** của `ask` (luật 03): `Done` · `NoOwner` (lỗi **cấu hình**) · `NoAnswer` ·
    `Failed`. ⚠ `Done` nghĩa là *handler đã nhận và trả lời*, **không** nhất thiết là *việc đã
    làm xong* - ngữ nghĩa đó do app định nghĩa
  - **at-most-once**: hạ bit **trước** khi làm. Muốn chắc thì **app tự thêm hàng đợi động**
  - **Đầy thì vòng lại và đè**, kèm bắt buộc **đếm `missed`** của người chưa đọc. Nhờ vậy một
    tiến trình treo **tự chịu**, không nghẽn ai
  - ⭐ Đo được: **bộ nhớ chung 17,4 µs · socketpair 16,8 µs, gần như BẰNG NHAU** (thời gian bị
    chi phối bởi *đánh thức*, không phải copy) · `mp.Lock` 0,85 µs · **"kiểm tra chỗ trống rồi
    mới đặt" thật sự đua: 4/2000 slot bị cấp hai lần**
  - **Bus dựng TRƯỚC DI**, nên nó **KHÔNG dính** câu treo `post_construct` ở tiến trình phụ.
    Cha dùng chính bus làm **kênh điều khiển** qua kênh nội bộ `__xime__` (framework luôn tạo),
    nên **ràng buộc (b) của thăng cấp primary hết cần pipe riêng** và **F10 đi cùng đường**
  - ⚠ Thiết kế cho **`N = 1` luồng mỗi tiến trình**. `N > 1` không đòi đổi cấu trúc chia sẻ,
    chỉ thêm một tầng phân phối bên trong tiến trình (và tầng đó **không được dùng
    `asyncio.Queue`**)
  - Mục 11 liệt kê **19 hướng đã loại kèm lý do** - đọc trước khi đề xuất lại
  - ⭐⭐ **Mục 12 - nó đỡ được gì cho phần khác của 0.8**: đóng hẳn **2** câu của tài liệu kho
    (mở kho ở đâu · nút cổ chai queue chung) · cho khuôn sẵn cho **4** câu chưa quyết (trong đó
    **`link_id` giải bài toán fencing token** gần như miễn phí) · mở lối cho **3** câu treo
    (⭐ **`post_construct` phải PHÁT BIỂU LẠI** - luật 2.7 vốn đã cấm nó chạm mạng và
    `create_task`, nên vấn đề nhỏ hơn nhiều; **scheduler cùng lời giải**; **pipe cha-con**).
    ⛔ Kèm **2 chỗ KHÔNG chuyển được**: *"đầy là triệu chứng"* chỉ đúng cho bus chứ không đúng
    cho kho · và **bus khai kích thước ở `.py` trong khi kho đề xuất `application.yml`** - phải
    soi một lần có chủ ý
- **⭐⭐ Kho nhóm 1 - `RefData` (2026-08-18, THIẾT KẾ XONG):**
  `docs/thiet-ke/12-kho-refdata.md` - phần kho **không dùng LMDB**, tách khỏi tài liệu
  cache theo yêu cầu chủ dự án. Chưa có dòng code nào.
  - **Ranh giới hai nhóm**: dữ liệu **có nguồn bền vững** hay không. Nhóm 1 = khoá JWT, danh bạ
    app, cấu hình đã phân giải - đọc nhiều, ghi hiếm, **thay trọn gói**, mất thì nạp lại được
  - ⭐ **Ba lý do khiến tự viết ở đây RẺ chỉ đúng với nhóm 1** (không cần cấp phát · không có
    khoá nào · người ghi chết giữa chừng vô hại) - **cả ba đều MẤT khi sang bus**. Dùng lại vật
    liệu thì được, dùng lại sự dễ dàng thì không
  - **API**: `RefData[T]` **subclass** đúng khuôn `CrudRepository` (lớp nền abstract, subclass
    khai `name` mới vào DI, có generic nên `mypy` hiểu), `configure_refdata([Class, ...])`
    truyền **class** như `configure_link`, và `read()`/`read_or_fail()` đúng cặp
    `find()`/`find_or_fail()`
  - `read()` trả **object thật, không copy** - **số đời làm chìa khoá cache L1**, đường thường
    lệ chỉ là **một phép so số nguyên**. ⚠ Object đó **dùng chung, không được sửa**
  - **`None` = CHƯA SẴN SÀNG**, tách hẳn khỏi *tập rỗng*. Không cần thêm bit cờ - `so_doi` đã
    đủ. ⛔ **`read()` KHÔNG tự chờ** (chờ trong `read()` là treo request); chờ là lời gọi riêng
    ở tầng khởi động, **có timeout**
  - **Chỉ primary `publish()`**, người khác gọi thì **nổ** - hai người ghi là hỏng **im lặng**
  - ⭐ **Chia đoạn khi dữ liệu lớn** (chủ dự án chốt): chỉ THÊM không thu · người đọc tự attach
    đoạn lạ · **`decode` phải đọc theo dòng** (`unpacker.feed`), nối đoạn trước là một lần copy
    toàn bộ. **Khai hình dạng ngay từ v1, nhưng v1 chỉ dùng một đoạn**
  - ⚠ **Vượt trần nguy hơn ở bus**: primary không publish được thì **cả cụm dùng bản cũ mãi
    mãi**, và **không request nào lỗi** cho tới khi token ký bằng khoá mới xuất hiện. Ba lớp:
    cảnh báo 80% · nổ nhưng giữ bản cũ · đánh dấu `loi_thoi` trong `stats()`
  - ⭐ **Nó cắt bớt một mảng của cái vướng ở luật 2.7**: primary gọi Trust rồi publish, tiến
    trình phụ chỉ read nên **không chạm mạng lần nào**
  - ✅ **Mục 10: 8/8 câu ĐÃ CHỐT 2026-08-19.** Đáng nhớ: **mỗi RefData một vùng nhớ
    RIÊNG** (*"các bảng nên không liên quan gì đến nhau, kể cả bộ nhớ"*) · trần seqlock
    **100 vòng rồi NÉM** (không trần thì một lỗi lạ thành request treo vô hạn, không
    log, không triệu chứng) · và câu 1 (*cha có đợi primary publish*) **đã có đáp án từ
    08-18** - cơ chế chờ qua bus, nên cha **sinh con đồng thời, không đợi**
- **⭐⭐ Kho nhóm 2 - `Store` trên LMDB (2026-08-19, THIẾT KẾ XONG):**
  `docs/thiet-ke/13-kho-store-lmdb.md` - phần kho **dùng LMDB**, cho dữ liệu **không có
  nguồn bền vững** (hãm nhịp, thử thách passkey, chống lặp). Chưa có dòng code nào.
  - ⛔⭐ **Phạm vi: MỘT máy, luôn luôn** (chủ dự án chốt, mục 2.7 tài liệu cache).
    *"nhiều máy tôi đã chia shard"* - đừng nêu phương án nhiều máy nữa, kể cả dưới dạng
    đường lui
  - **Ba lớp nền**: `Store` (bytes) · `CounterStore` (int, có `incr`) · `Store[T]` (kiểu
    riêng của app). ⭐ Tách theo kiểu **không phải chuyện thẩm mỹ**: `incr` chỉ có nghĩa
    với số, đặt nó lên một `Store` chung là hợp đồng hứa thứ nó không giữ được
  - ⭐ **Cấu hình đi bằng THAM SỐ CLASS (PEP 487)**, không phải thuộc tính trong thân:
    `class HamNhip(CounterStore, name="...", ttl=900, parts=4)`. Chủ dự án nêu chỗ vướng
    *"cấu hình với dữ liệu đang nằm 1 chỗ"*; kwargs tách triệt để, không thể va tên, và
    `mypy` kiểm được. **Áp cùng quy ước cho `RefData`**
  - **Vào DI bằng `scan`**, không cần `configure_*` - khác `RefData`/`ProcessLink` vì
    mở một file LMDB không cần cấp phát chung. ⚠ Hệ quả: **câu 8 của tài liệu cache TAN**
  - **Chia file theo `crc32(key) % parts`**, `parts` do lập trình viên chọn, mặc định 1.
    ⛔ Chia theo **tiến trình ghi** (đề xuất ban đầu) cho zero xung đột nhưng **phá hẳn
    `set_if_absent`** - mỗi tiến trình thành người-chiếm-đầu-tiên trong vũ trụ riêng.
    ⛔ **`crc32` chứ không phải `hash()`** - `hash()` ngẫu nhiên lại mỗi tiến trình, đo
    được, và hỏng hoàn toàn im lặng
  - **Lỗi kho báo bằng NGOẠI LỆ**, không phải kết cục trong kiểu trả về: với `incr` /
    `set_if_absent` thì ngoại lệ là **fail-closed tự nhiên**, còn quên một nhánh của kiểu
    trả về là **fail-open im lặng**. ⭐ Ranh giới với bus: *kết quả bình thường thì kiểu
    trả về; sự cố hạ tầng thì ngoại lệ*. Đây là cách **câu 7 tan**
  - ⭐ Số đo: **đọc từ page cache 0,22 µs · gather đắt gấp 27 · thread pool đắt gấp 439**.
    Đọc LMDB không phải I/O nên **không song song hoá được, và không cần**
  - ✅ **Mục 7: còn treo HẾT.** `incr` **gia hạn TTL mỗi lần GHI**, đọc không đụng tới -
    đề nghị ban đầu của phiên (*giữ hạn lần đầu*) đã bị bác, và bác đúng: cạm bẫy "khoá
    vô hạn" mà nó lo **không xảy ra** vì app thoát sớm trước khi `incr`. Thứ còn lại
    **không phải câu hỏi thiết kế** mà là hai phép đo phải làm khi có VPS Linux
- **Kế hoạch triển khai 0.5 (đã phát hành 2026-06-22 - feature trước, audit sau):** `docs/phien-ban/0.5-ke-hoach-thi-cong.md`
- **Báo cáo kiểm toán 0.5 (mọi phát hiện H1/M1-M7/L1-L11/I1-I2 đã xử lý):** `docs/kiem-toan/0.5.md`
- **Kế hoạch 0.6 (ĐÃ PHÁT HÀNH 2026-06-23: Việc 1 thay `dependency-injector` + Việc 2 dynamic interface binding; version + CHANGELOG đã đồng bộ 0.6.0):** `docs/phien-ban/0.6-ke-hoach.md`
- **Kế hoạch 0.3 (hardening):** `docs/phien-ban/0.3-ke-hoach.md`
- **Thiết kế tổng thể:** `docs/thiet-ke/01-tong-quan.md`
- **Giới thiệu & triết lý:** `docs/thiet-ke/00-gioi-thieu.md`
- **Cây thư mục dự án:** `docs/thiet-ke/02-cay-thu-muc.md`
- **Entry point ứng dụng (`main.py`):** `docs/thiet-ke/03-diem-khoi-dong.md`
- **Routing layer (class-based controllers, `_make_handler`):** `docs/thiet-ke/04-routing-layer.md`
- **Kế hoạch gRPC Client SDK + mTLS động (chốt 2026-06-12):** `docs/thiet-ke/08-grpc-client-mtls.md`
- **Kế hoạch 0.7 (CODE XONG 2026-07-30, chưa commit: Modbus + OPC UA; có bảng tiến độ, 4 quyết định đã chốt, 4 chỗ API pymodbus lệch so với thiết kế):** `docs/phien-ban/0.7-ke-hoach.md`
- **⭐ Kết quả 0.7.1 (2026-08-03): server-stream có kiểu + đợt 2 vá bảo mật:** `docs/phien-ban/0.7.1-ket-qua.md`
- **Yêu cầu gốc của phiên data-service/user-service (đã làm xong):** `docs/ghi-chep/yeu-cau-server-stream.md`
- **Kiểm toán bảo mật 0.7 + kế hoạch vá (đợt 2 xong, đợt 0/1/3/4/5 chưa):** `docs/kiem-toan/0.7-bao-mat.md`, `docs/kiem-toan/0.7-bao-mat-ke-hoach-va.md`, `docs/kiem-toan/0.7-bao-mat-cho-quyet.md`
- **`PEER_APP_ID` - định danh app từ SAN cert (ĐÃ LÀM 0.6.3):** `docs/da-phu-dinh/peer-app-id-tu-san-cert.md`
- **TLS/HTTPS cho web adapter (ĐÃ LÀM 0.6.3, mức 2 đã bỏ):** `docs/thiet-ke/07-tls-web-adapter.md`
- **Backlog lỗi cần sửa (event bus tests, pb2 collision):** `docs/kiem-toan/backlog-sua-loi.md`
- **Wishlist tính năng tương lai (bidi, transport TCP, retry...):** `docs/sap-toi/wishlist-tinh-nang.md`

