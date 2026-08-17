# Đa tiến trình: mô hình `main.py`, cấu hình, và adapter phải đổi gì

> **Trạng thái 2026-08-16 (buổi chiều): PHẦN LỚN ĐÃ CHỐT.** Nguyên văn khi chốt:
> *"mấy cái bạn gợi ý cứ chốt vậy đi, nào tôi thấy không ổn thì tôi đổi sau, giờ
> tôi thấy ổn."*
>
> ⚠ **Ba mục ở phần 9 còn để lại**, chủ dự án xem tiếp hôm sau.
>
> File này là **biên bản một buổi trao đổi thiết kế**, viết buổi sáng lúc chưa chốt
> gì rồi cập nhật buổi chiều. Chỗ nào ghi **CHỐT** là quyết định; chỗ nào ghi
> **chưa** thì đúng là chưa. Phần "đã bác bỏ" (mục 8) là phần giá trị nhất: chúng
> bị bác kèm lý do cụ thể, đừng bàn lại.
>
> Cặp với [`cache-lien-tien-trinh-2026-08-16.md`](cache-lien-tien-trinh-2026-08-16.md)
> (cùng buổi, nửa đầu: cache và LMDB). File này là nửa sau: **mô hình chạy**.
>
> ⚠ Cả hai file cộng lại làm **phần lớn [`ke-hoach-0.8.md`](ke-hoach-0.8.md) không
> còn cần tới** - xem mục 7.

---

## 0. Đọc gì trong hai phút

| | |
|---|---|
| **`main.py` chốt** | `import config` · `add_config(config)` · `use(...)` ở **mức module**; `if __name__` chỉ còn `share_load().run()` - xem mục 5 |
| **Nguyên lý trung tâm** | **Không id nào trong code.** `main.py` khai *có cửa nào*, cấu hình khai *tiến trình nào mở cửa nào ở cổng nào* |
| **Mô hình chạy** | Tiến trình gốc **giữ socket nhưng không phục vụ** (bind, không bao giờ `accept`, không dựng DI, không chết); con là `python -m app.main` chạy lại với `XIME_PROCESS_ID`, sinh bằng `multiprocessing` |
| **Chia tải** | web + unix socket: **cha giữ socket** (cả hai hệ điều hành) · gRPC: **`SO_REUSEPORT`**, Windows không hỗ trợ → **báo lỗi lúc khởi động** |
| **Bốn hạng adapter** | nhân bản (web, grpc) · **phân mảnh** (modbus, opcua, **mqtt** - mỗi tiến trình một cụm thiết bị / một tập topic) · đơn nhất · - |
| **MQTT** | **Giữ là CLIENT, KHÔNG làm broker.** Chia tải bằng **chia topic** (giữ thứ tự), không dùng shared subscription. Ba việc còn nợ ở 5.7.4 |
| **Fieldbus** | Tách **LOẠI** (code biết) khỏi **THỰC THỂ** (cấu hình biết). Web **không gọi thẳng** adapter fieldbus - đọc qua DB/vùng nhớ chung, ghi qua **bus** |
| **Nguyên tắc chủ dự án nêu (2)** | ⭐ *"Cứ thay đổi code framework thoải mái, **để code phục vụ thiết kế**"* → đổi API dứt khoát, không giữ hai đường |
| **Vì sao chạy lại `main.py`** | **Một đường khởi động duy nhất.** Hai đường là hai bản trôi lệch nhau, và loại lệch đó không có triệu chứng |
| **Tương thích** | Không gọi `share_load()` thì chạy y hệt hôm nay. **31 app không phải sửa một chữ** |
| **Nguyên tắc chủ dự án nêu** | ⭐ **Adapter phải đổi theo thiết kế, thiết kế không đổi theo adapter** |

---

## 1. Nguyên lý đã hình thành trong buổi bàn

Mười điều, xếp theo thứ tự phụ thuộc. **Đã chốt chiều 2026-08-16.**

| # | Nguyên lý | Ghi chú |
|---|---|---|
| 1 | **`main.py` mô tả ỨNG DỤNG, không mô tả một tiến trình** | ⚠ **Đổi so với bản sáng.** Sáng chốt *"một `Application()` = một tiến trình"*, chiều bỏ: một `Application()` cộng `share_load()` là đủ, số tiến trình do cấu hình quyết |
| 2 | **KHÔNG id tiến trình nào xuất hiện trong code** | Thay cho *"chỉ truyền id tiến trình vào"* của bản sáng. `process_id` chỉ sống trong YAML và trong biến môi trường do framework đặt |
| 3 | **`server_id` là điểm phục vụ BÊN TRONG một tiến trình** | Một tiến trình chạy nhiều server (web, grpc, mqtt...). `server_id` **không** định danh tiến trình. Không viết đối số thì nó là `default` |
| 4 | **Cổng thuộc về CẶP `(process_id, server_id)`** | Không thuộc riêng cái nào. Đây là lý do trước nay phải truyền cổng vào constructor |
| 5 | **Code khai NĂNG LỰC, cấu hình khai LỰA CHỌN** | `main.py` khai app này *có thể* làm gì; cấu hình khai tiến trình này *đang* làm gì |
| 6 | **Tiến trình primary có đủ mọi thứ** | Thêm khối cấu hình = thêm tiến trình chia tải. Việc đơn nhất luôn ở primary. ⚠ Chiều đổi một chỗ: **primary là CON THỨ NHẤT**, không phải tiến trình gốc - xem 5.5 |
| 7 | **Framework định hướng, không bắt buộc** | Team không tách vai vận hành thì code sao cũng được. Ngoại lệ ở mục 2.3 |
| 8 | **Mặc định nghiêng về an toàn: danh sách TRẮNG** | Khai cái gì được **nhân bản**, không khai cái gì là **đơn nhất**. Quên khai thì thừa một chút, không sai |
| 9 | ⭐ **Adapter đổi theo thiết kế, không ngược lại** | Chủ dự án nêu cuối buổi sáng, sau khi phiên lấy chữ ký adapter hiện có làm điểm tựa và suýt ghi một giới hạn không tồn tại vào tài liệu |
| 10 | ⭐ **MỘT đường khởi động duy nhất** | Chốt chiều. Tiến trình con chạy lại chính `main.py`, không có entry point riêng của framework. Lý do ở 5.6 |

### 1.1. Vì sao nguyên lý 6 mạnh hơn vẻ ngoài

Nó giải một loạt việc đang treo **bằng cách làm chúng không tồn tại**, chứ không phải bằng cơ chế:

| Việc treo trước đó | Mô hình "primary có đủ" |
|---|---|
| Tương thích với 31 app | **Miễn phí.** Một khối = hành vi hôm nay |
| Job đơn nhất khai `run_on` ở đâu | **Không cần khai.** Nó ở primary, mà primary luôn tồn tại |
| "Không tiến trình nào nhận job đơn nhất" | **Không xảy ra được** |
| Thứ tự khởi động, migration, tiêu thụ vé bootstrap cert | **Tự đúng** nếu primary làm xong phần một-lần rồi mới sinh tiến trình con. **Quan hệ cha con TỰ NÓ là thứ tự** - không cần khoá, không cần chờ, không cần bus |
| Người vận hành phải học khái niệm "vai" | **Không có khái niệm nào.** Thêm khối = thêm tiến trình |

Việc thứ tư đáng nhấn: trước đó nó bị xếp vào nhóm khó nhất (phải phối hợp giữa các tiến trình), nay tan biến.

---

## 2. Nguyên lý DI - phần giá trị nhất của buổi

### 2.1. Phát biểu của chủ dự án

> *"Code trong 1 dự án nó lấy từ 1 nguồn cho nhiều tiến trình rồi, nếu mà khác code
> thì tách luôn repo đi đỡ rối. Nếu chung rồi thì DI chỉ cần loại trừ theo cách
> sau: lấy cái tổng khai báo trừ đi cái chỉ duy nhất 1 (ví dụ cái hẹn giờ), mà cái
> duy nhất 1 kia phải làm sao cho luồng DI không bị gãy, không được đứng giữa dòng
> DI, chỉ đầu và cuối, mà thường là đầu để gọi cái gì đó. Còn lại thì mỗi tiến
> trình xây DI theo khung hết. Nên chỉ 1 file cấu hình DI cho lập trình viên."*

### 2.2. Phát biểu chặt, và một đính chính

> **Một class chỉ loại trừ được khi KHÔNG class nào còn lại phụ thuộc vào nó.**

Tức nó phải ở **đầu dòng**: nó gọi người khác, không ai gọi nó. Job hẹn giờ đúng
như vậy - nó inject repository và client, nhưng không service nào inject nó vì
`SchedulerRunner` gọi qua registry chứ không qua constructor.

⚠ **Đính chính: "cuối" thì KHÔNG loại được.** Node cuối là node không phụ thuộc ai,
nhưng **có người phụ thuộc vào nó** - bỏ đi là chính những người đó gãy. Luật gọn
lại còn một vế: **chỉ loại trừ được node đầu dòng.**

### 2.3. Đề xuất: biến ràng buộc đó thành phép kiểm tự động

Ràng buộc trên hiện là thứ lập trình viên phải **nhớ**. Nhưng framework đã dựng
dependency graph rồi, nên nó **kiểm được**:

> Khai một class thuộc nhóm đơn nhất, mà class đó có người inject → **lỗi khởi
> động**, kèm tên kẻ inject.

Không có phép kiểm này thì ngày ai đó vô tình inject `CertRotationJob` vào một
service, tiến trình phụ sẽ **thiếu dependency** và nổ với thông báo khó hiểu, hoặc
tệ hơn là vẫn dựng được rồi chạy sai.

⭐ Đây là **ngoại lệ duy nhất** của nguyên lý 7 (định hướng, không bắt buộc): chỗ
này framework nên **bắt buộc**, vì nó là chuyện đúng sai chứ không phải phong cách,
và lập trình viên không có cách nào tự phát hiện.

### 2.4. Giới hạn: nguyên lý loại trừ không phủ hết

Loại trừ áp được cho **thứ tự nó làm việc** (job, listener, poller). **Không** áp
được cho **thứ cung cấp dịch vụ cho người khác**.

Ca thật: `MqttPublisher`. Tiến trình `api` không chạy MQTT adapter, nhưng một use
case nghiệp vụ vẫn inject nó để gửi tin. Nó **có người phụ thuộc** nên không loại
được, nên vẫn bị dựng ở `api`.

> **Nguyên lý phụ phải kèm theo: singleton dùng chung KHÔNG được mở tài nguyên
> trong `post_construct`.** Mở kết nối phải lười, lần dùng đầu tiên mới mở.

Không có luật này thì `api` mở một kết nối MQTT nó không bao giờ dùng, và tương tự
với pool Redis, kênh gRPC. Lãng phí im lặng, không ai thấy cho tới khi đếm kết nối
trên broker.

### 2.5. Danh sách loại trừ khai ở đâu: hai nửa, hai vai

| Khai gì | Ai khai | Ở đâu |
|---|---|---|
| Class này thuộc **nhóm đơn nhất** | **lập trình viên** | `dependency.py` |
| Nhóm đơn nhất chạy ở **tiến trình id nào** | **người vận hành** | cấu hình |

Tách vậy thì lập trình viên không cần biết tên tiến trình, người vận hành không cần
biết tên class, và **framework kiểm chéo được**. Dồn về một phía là mất phép kiểm.

⭐ Và phép kiểm đó rẻ bất ngờ: vì cấu hình khai tập trung, **mọi tiến trình đọc
được toàn bộ bức tranh**, nên mỗi tiến trình tự kiểm tính nhất quán toàn cục **mà
không cần nói chuyện với tiến trình nào**. Không bus, không khoá, không LMDB.

### 2.6. Ba đường giải cho "DI khác nhau theo tiến trình" (chưa chọn)

Nền: framework có nguyên tắc hai tầng - quyết định kiến trúc viết bằng **Python**,
thứ đổi theo môi trường viết bằng **YAML**. DI nằm hẳn ở vế Python. Nên "cấu hình
làm hết" đụng vào ranh giới này.

| | Cách | Đánh đổi |
|---|---|---|
| a | Mọi tiến trình dùng **chung một** `BindingConfig`; cấu hình chỉ chọn adapter và job | Đơn giản nhất. Nhưng tiến trình nào cũng dựng đủ singleton - xem 2.4 |
| b | `config/dependency.py` **đọc id** rồi tự khai khác nhau | Giữ DI ở Python, vẫn khác theo tiến trình. Nhưng `dependency.py` có nhánh `if` theo id |
| c | Mỗi tiến trình một **config package riêng**, chọn bằng `config_module` | Sạch nhất về DI. Nhưng id không còn là thứ duy nhất truyền vào - trái nguyên lý 2 |

Phiên nghiêng về **b**, và nó cần một điều kiện: **id phải có mặt TRƯỚC khi
`dependency.py` chạy.** Hiện `Application.start()` mới đi tìm binding, nên thứ tự
này phải sắp lại.

### 2.7. ⭐ CHỐT chiều 2026-08-16: **DI dựng ĐỦ ở mọi tiến trình, cái nào không được chạy thì tắt bằng cờ**

Đây là **đường a**, và nó thay hẳn phương án "loại trừ node đầu dòng" của buổi sáng.
Nguyên văn chủ dự án: *"với DI thì dựng đủ, cái nào không được phép chạy thì có cờ
tắt đi."*

Ba lợi ích, cái thứ ba mới là lý do thật:

| | |
|---|---|
| DI **đồng nhất tuyệt đối** ở mọi tiến trình | Không còn tổ hợp nào để lệch |
| Không cần phép kiểm "class đơn nhất có ai inject không" (2.3) | Không ai bị loại khỏi đồ thị thì không có gì gãy |
| ⭐ **Điều kiện để thăng cấp primary tức thì** | Con đã dựng sẵn mọi thứ, thăng cấp chỉ là bật cờ. Phương án loại trừ thì con **không có** `CertRotationJob` trong container, thăng cấp phải dựng lại DI |

⚠ **Giá phải trả biến một khuyến nghị thành luật cứng.** Nguyên lý phụ ở 2.4 trước
đây chỉ áp cho *singleton dùng chung*; nay áp cho **mọi** singleton:

> **`post_construct` không được mở kết nối, không `create_task`, không chạm mạng.**
> Mở phải lười, lần dùng đầu tiên mới mở.

Không có luật đó thì bốn tiến trình mở bốn kết nối MQTT, bốn pool Redis, bốn kênh
gRPC mà ba phần tư không bao giờ dùng.

### 2.8. Thăng cấp primary thay vì dựng lại - ĐANG BÀN, bốn ràng buộc

Chủ dự án đề xuất: primary chết thì mẹ **thăng cấp một con đang chạy** lên làm
primary ngay, rồi mới sinh thêm con bù - *"gần như không có độ trễ khởi động"*.

Hướng đúng, và 2.7 làm nó khả thi. Bốn chỗ phải xử lý:

| # | Ràng buộc | Vì sao |
|---|---|---|
| a | ⭐ **Tín hiệu thăng cấp phải là "đã exit theo kernel", KHÔNG phải "không trả lời health check"** | Primary treo tạm (GC dài, đĩa chậm, swap) → thăng cấp con B → A tỉnh lại vẫn tin mình là primary → **hai primary cùng chạy scheduler**, đúng hạng *chạy hai lần thì SAI* của luật 01. Mô hình cha-con miễn nhiễm **nếu** chỉ tin `waitpid` - đó là sự thật của kernel, không phải suy đoán qua mạng. Con treo thì **giết trước, xác nhận exit, rồi mới thăng cấp** |
| b | **Cần kênh cha → con lúc chạy** | Biến môi trường đặt một lần lúc sinh, không đổi được sau. Đường tự nhiên nhất là **pipe có sẵn trong quan hệ cha-con** - không cần LMDB (đã chốt không dựa vào), không file, không cổng. Kênh đó dùng lại cho health check, lệnh drain, báo cấu hình đổi |
| c | **Chống domino** | Primary chết **vì chính job của nó** (cert hỏng làm `CertRotationJob` crash) → thăng cấp B → B chạy job đó → B chết → hết cả đàn trong vài giây. Cần: quá `N` lần thăng cấp trong `T` giây thì **dừng thăng cấp, chạy tiếp không có primary, kêu to**. Mất job nền còn hơn mất khả năng phục vụ |
| d | **Việc dở dang** | Job đơn nhất phải **đọc trạng thái từ nguồn bền vững, không từ RAM**. Phần lớn job hiện tại đã vậy (con trỏ đồng bộ ở DB), nhưng đó là **thuộc tính phải giữ**, không phải điều hiển nhiên |

⚠ **"Cái sau dùng luôn dữ liệu cái cũ" - được với dữ liệu, KHÔNG được với kết nối:**

| | Con thăng cấp dùng lại được? |
|---|---|
| **Dữ liệu** (key đã nạp, danh bạ app, cấu hình đã phân giải) | **Được** - qua vùng nhớ chung nhóm 1 |
| **Tiến độ** (con trỏ đồng bộ, mốc xoay cert) | **Được**, nhưng vì nó vốn ở DB chứ không phải RAM |
| **Kết nối** (socket, pool DB, kênh gRPC, phiên MQTT) | **Không bao giờ.** Tiến trình chết thì kernel đóng hết |

Nên con thăng cấp vẫn phải **tự mở kết nối của nó**. Cái tiết kiệm được là *dựng DI,
import module, nạp dữ liệu*; cái vẫn phải trả là *mở kết nối*, vài trăm mili giây.
Nhanh hơn dựng tiến trình mới rất nhiều, nhưng **không "gần như bằng không"** - ghi
đúng con số để sau này không ai ngạc nhiên.

### 2.9. ⛔ `post_construct` cho tiến trình phụ - **TẠM GÁC**, chưa có lời giải

Chủ dự án đề xuất: tiến trình phụ **không chạy `post_construct`**, được thăng cấp mới
chạy. Rồi tự thấy khó và gác lại: *"chỗ này tôi thấy khá khó đấy, tí bàn kỹ cái này,
giờ tạm thời bỏ qua."*

Ghi lại **đúng vấn đề** để lần sau không phải dựng lại:

**a. Bản rộng cắt luôn thứ tiến trình phụ cần để sống.** `post_construct` đang gánh
hai loại việc rất khác nhau:

| Loại | Ví dụ | Tiến trình phụ có cần |
|---|---|---|
| **Chuẩn bị để phục vụ được** | mở pool DB, mở pool Redis, nạp key JWT từ Trust, mở kênh gRPC client | **Bắt buộc.** Không có thì không xử lý nổi một request |
| **Làm một việc của hệ thống** | khởi động vòng lặp job, tiến con trỏ đồng bộ, xoay cert | Không |

Tắt hết thì tiến trình phụ dựng DI xong mà không có kết nối DB, không có key verify
token, mọi request rơi vào lỗi. **Phép cắt không thể ở mức tiến trình.**

**b. ⭐ Và nó cũng không cắt được ở mức CLASS - chủ dự án chỉ ra chỗ này:**

> *"Cái này hình như nó đặt ở hàm chứ không phải class đúng không? Nếu class thì còn
> cái nào chạy cái nào không. Hàm thì chạy từ trên xuống dưới, vậy phải có cái gì bọc
> nó lại trong hàm để thông báo rằng cái này chạy một lần, có điều kiện."*

Đúng: hook đặt trên **method**, nên một method chứa cả việc chung lẫn việc đơn nhất
thì cắt ở mức class không chạm tới được. Đề xuất của phiên (*"`post_construct` của
class thuộc nhóm đơn nhất mới hoãn"*) chỉ giải được khi hai loại việc **đã nằm ở hai
class khác nhau** - mà hiện tại chúng không.

Ca thật: `KeyRefreshJob` **nạp key ban đầu** (mọi tiến trình cần, để verify token) và
**chạy vòng lặp làm tươi 6 giờ** (chỉ primary). Hai việc, một chỗ, vì trước nay chỉ
có một tiến trình.

**c. Cái giá chưa ai nêu: fail-fast biến thành fail-late.** Hôm nay cert hỏng thì nổ
lúc khởi động, người vận hành thấy ngay. Hoãn tới lúc thăng cấp thì lỗi đó **nằm im
cho tới lúc primary chết** - tức 3 giờ sáng, tức đúng lúc tệ nhất, và bây giờ có hai
sự cố chồng nhau thay vì một. Ba cách xử lý: chấp nhận · **tiến trình phụ vẫn KIỂM
điều kiện lúc khởi động, chỉ không CHẠY việc** (giữ được fail-fast, nhưng đòi lập
trình viên tách *kiểm* khỏi *làm*) · chống domino ở supervisor (**cần dù chọn cách
nào**).

**d. Chi tiết dễ quên: `pre_destroy`.** `post_construct` không chạy thì `pre_destroy`
**cũng không được chạy**. Framework phải nhớ instance nào đã init. Sổ ghi đó đã có
phần nào: repo chốt 2026-07-30 rằng `LifecycleManager` không gọi `pre_destroy` cho
instance mà `post_construct` ném lỗi - nay chỉ mở rộng cùng sổ sang ca *"chưa chạy vì
là tiến trình phụ"*.

---

## 3. Phát hiện về code hiện tại (đo được, đừng đo lại)

### 3.1. Sáu adapter, và chúng đã nhất quán một nửa

| Adapter | Đối số đầu | Đối số còn lại |
|---|---|---|
| `WebAdapter` | `server_id="default"` | host, port, ssl |
| `GrpcAdapter` | `server_id="default"` | host, port |
| `SocketAdapter` | `server_id="default"` | path |
| `MqttAdapter` | `client_id="default"` | path |
| `ModbusAdapter` | `device=DEFAULT_DEVICE` | controllers |
| `OpcuaAdapter` | `server=DEFAULT_SERVER` | controllers |

Tất cả đều đặt `self._server_id` để `Application.use()` chống trùng. Nhưng **bốn
tên cho cùng một vai trò** là bốn người viết ở bốn thời điểm, không phải một thiết
kế - xem mục 4.

### 3.2. ⭐ `MqttAdapter` gộp hai nghĩa, và cái gộp đó tạo ra một giới hạn KHÔNG có thật

```python
self._server_id = client_id     # adapters/mqtt/_adapter.py
```

`client_id` của MQTT **không phải** định danh nội bộ - nó là giá trị thật gửi lên
broker, và broker chỉ cho **một phiên trên mỗi giá trị đó** (docstring của adapter
ghi rõ: hai adapter cùng id sẽ *"đánh nhau trong vòng lặp reconnect"*).

Gộp hai nghĩa dẫn thẳng tới kết luận *"MQTT không nhân bản được"*. **Kết luận đó
sai về bản chất**: MQTT không nhân bản được **vì hai bản đang buộc phải dùng chung
một `client_id`**, không phải vì giao thức cấm. Tách ra thì hai tiến trình cùng
phục vụ vai `devices` với hai `client_id` khác nhau, và với shared subscription của
MQTT 5 thì chúng chia tải được thật.

> **Đây là ca cụ thể cho nguyên lý 9.** Phiên đã suýt ghi vào tài liệu một bảng
> "adapter nào nhân bản được" dựng trên chính chỗ gộp này, tức để một lựa chọn hiện
> thực định hình một kết luận thiết kế.

⚠ Modbus và OPC UA thì **khác**: `device` và `server` trỏ tới **thiết bị vật lý ở
đầu kia**, hai tiến trình cùng poll một PLC là nhân đôi tải lên thiết bị thật. Giới
hạn đó là **thật**, không phải do hiện thực.

### 3.3. `_import_config_siblings()` là nguyên nhân scheduler bật ở mọi tiến trình

`Application._discover_binding()` tìm `dependency` rồi gọi `_import_config_siblings()`
([application.py:336-364](../../xime/core/bootstrap/application.py)), hàm này dùng
`pkgutil.iter_modules()` để **import mọi module anh em trong package `config/`**. Nên
`app/config/scheduler.py` luôn được nạp, `configure_scheduler()` luôn chạy.

⚠ **Cơ chế này vi phạm chính luật của repo.**
[`rules/config-discovery.md`](../rules/config-discovery.md) mở đầu bằng: *"Framework
**không tự quét** file config. Developer chủ động import một hàm/object từ framework
và gọi nó."* `_import_config_siblings()` là auto-scan đúng nghĩa đen, chỉ nằm ở tầng
khác nên không ai để ý.

Kéo theo: mọi `configure_*` đều là **side effect ở mức module**, chạy lúc import,
**không nhận được tham số**.

### 3.4. ⭐ Cơ chế dò config hiện tại SẼ HỎNG khi có tiến trình con

Đây là phát hiện buổi chiều, và nó biến `add_config()` từ "cho đẹp" thành **điều
kiện cần**.

```python
Application(binding=..., resources_dir="resources", config_module=...)
```

Thứ tự ưu tiên (docstring): `binding=` → `config_module=` → auto-discovery →
`BindingConfig()` **rỗng**. Nhánh auto-discovery dò package bằng
`__main__.__spec__.parent` ([application.py:299-301](../../xime/core/bootstrap/application.py)).

**`__main__` của tiến trình con khác `__main__` của tiến trình cha** - dù sinh con
bằng cách nào. Nên `__spec__.parent` trả giá trị khác, framework đi tìm
`config.dependency` sai chỗ, rồi **im lặng rơi xuống `BindingConfig()` rỗng ở dòng
284**. Tiến trình con khởi động được, DI rỗng, không route nào, **không gì báo**.

> Đúng [luật 03](../../../.claude/rules/03-mot-gia-tri-mot-nghia.md) dấu hiệu 3:
> *"không tìm thấy vì chưa nạp"* trả về giống hệt *"không có config"*.

Vá bằng `add_config(config)` (mục 5): truyền **module object**, framework có
`config.__name__` trong tay, xác định, không dò.

### 3.5. Khuôn fail-fast đã có, chép được

`Application._validate_grpc_codefirst_targets()`: controller code-first trỏ vào
`server_id` mà không `GrpcAdapter` nào phục vụ → `StartupException` kèm danh sách
kẻ mồ côi và danh sách id đang được phục vụ. Đây là đúng khuôn cần cho bốn phép
kiểm ở mục 6.

### 3.6. Bốn job của data-service, ví dụ tự khớp

| Job | Nhịp | Hạng theo luật 01 | Kết quả đi đâu |
|---|---|---|---|
| `CertRotationJob` | 1 giờ | **chạy hai lần thì SAI** | DB |
| `KeyRefreshJob` | 6 giờ | thừa | DB **và cache L1 trong tiến trình** |
| `KeyCleanupJob` | 24 giờ | thừa | DB |
| `ApplicationSubjectSyncJob` | 5 phút | **SAI** (tiến con trỏ đồng bộ) | DB |

Hai job hạng SAI được giải **miễn phí** bởi nguyên lý 6. Còn `KeyRefreshJob` cập
nhật **cache L1 trong bộ nhớ tiến trình**, nên với nhiều tiến trình thì cache L1 của
các tiến trình phụ **không ai làm mới** - đúng ca dùng của vùng nhớ chung nhóm 1
(xem file cache). ⚠ Phần vá đó nằm ở **repo data-service**, không phải framework.

---

## 4. Adapter phải đổi gì (theo nguyên lý 9)

Năm điều, rút từ nguyên lý chứ không từ chữ ký hiện có.

| # | Phải đổi | Vì sao |
|---|---|---|
| 1 | **Một khái niệm, một tên.** Mọi adapter nhận cùng một định danh, cùng tên, cùng vị trí | Bốn tên hiện tại là di sản, không phải thiết kế |
| 2 | **Tách định danh khỏi tham số nghiệp vụ** | Xem 3.2. `client_id` MQTT, `device` Modbus là dữ liệu nghiệp vụ, không phải id nội bộ |
| 3 | **Adapter KHÔNG tự đi tìm cấu hình nữa** | Hiện web đọc `server.port`, grpc đọc `grpc.port`, mqtt đọc `mqtt.*`: sáu adapter, sáu quy ước khoá. Cổng nay thuộc cặp `(process, server)` nên chỉ **một chỗ** biết cách ánh xạ. Framework **đẩy** khối cấu hình đã phân giải vào adapter |
| 4 | **Hạng nhân bản phải là DỮ LIỆU, không phải chú thích** | Lý do chống trùng đang nằm trong docstring; framework đọc được nhưng không dùng được. Và theo mục 2 thì hạng là **điều kiện** (*"nhân bản được nếu mỗi bản có X riêng"*), không phải nhãn cứng |
| 5 | **Vòng đời phải có tín hiệu "đã sẵn sàng"** | `Adapter` hiện chỉ có `start()`/`stop()`. Ba việc cùng hỏi câu này: primary phải làm xong phần một-lần trước khi sinh con · cô lập lỗi cần phân biệt hỏng trước/sau khi phục vụ · health check. **Trùng với F10 của kế hoạch vá bảo mật** - làm một lần được cả hai |

⚠ **Cái giá:** bốn trong năm mục **đổi API công khai của gói đã có 11 bản trên
PyPI**. Trong nhà thì 31 codebase sửa được; với người ngoài thì đây là thay đổi phá
tương thích. Phiên đề nghị **đổi dứt khoát, không giữ hai đường** - giữ hai đường
chính là cách thiết kế mới bị kéo về hình dạng cũ. Nhưng đó là quyết định chưa chốt.

---

## 5. `main.py` và cấu hình - ĐÃ CHỐT chiều 2026-08-16

### 5.0. `add_config(module)` thay cho `config_module="chuỗi"`

Chủ dự án đề xuất: thư mục `config/` có `__init__.py` khai hết, `main.py` import nó
rồi đưa thẳng vào `Application`, thay vì nhét một chuỗi vào đối số khởi tạo.

Ba cái được, xếp theo trọng lượng:

| Được | |
|---|---|
| ⭐ **Tiến trình con dựng được DI** | Xem 3.4 - cơ chế dò hiện tại hỏng ở tiến trình con. Đây không phải cải tiến, đây là **điều kiện cần** |
| **Về đúng luật của repo** | `pkgutil.iter_modules()` biến mất; thứ tự nạp là thứ tự lập trình viên viết trong `__init__.py`, đọc là thấy. Hết auto-scan (xem 3.3) |
| **Sai thì nổ ngay** | Gõ sai tên module → lỗi ở dòng `import`, không phải im lặng rơi xuống `BindingConfig()` rỗng. IDE và `mypy` cũng nhìn thấy |

⚠ Tên dùng **snake_case** (`add_config`), không `addConfig` - repo đang là `use`,
`run`, `configure_*`, và đây là API công khai của gói đã phát hành.

### 5.1. `app/main.py` - bản chốt

```python
import config

from xime import Application
from xime.adapters.grpc import GrpcAdapter
from xime.adapters.web import WebAdapter

app = Application()
app.add_config(config)
app.use(WebAdapter()).use(GrpcAdapter("internal")).use(GrpcAdapter("external"))

if __name__ == "__main__":
    app.share_load().run()
```

| Dòng | Trả lời câu | Chạy ở |
|---|---|---|
| `import config` | Cấu hình khung nằm ở đâu | cha **và** mọi con |
| `add_config(config)` | Chỉ thẳng, không để framework dò | cha và mọi con |
| `use(...)` | Ứng dụng này có những cửa nào | cha và mọi con |
| `share_load().run()` | Chạy nó ra sao | chỉ khi là entry point |

⭐ **Ba dòng giữa nằm ở MỨC MODULE, không nằm trong `if __name__`.** Đây là điều
kiện để tiến trình con dựng lại được ứng dụng (xem 5.6). Đặt chúng trong
`if __name__` thì con import xong sẽ có một `app` không adapter nào, DI rỗng.

⚠ Cú pháp: **không xuống dòng ở dấu chấm đầu dòng** nếu không có ngoặc bao ngoài -
Python báo lỗi cú pháp. Nhiều adapter thì bọc `(...)`.

### 5.2. `app/config/__init__.py`

```python
from config.dependency import dependency

from config import grpc, scheduler, web  # noqa: F401  - chạy configure_* lúc import

__all__ = ["dependency"]
```

Được nhiều hơn vẻ ngoài: cơ chế cũ nạp theo **thứ tự alphabet của `pkgutil`**, không
ai chọn và không ai thấy. Ở đây thứ tự là thứ viết ra. Thêm file config mới mà quên
thêm dòng import thì nó không chạy - và **cái quên đó nhìn thấy được trong file
này**, khác hẳn một file nằm im trong thư mục.

### 5.3. `resources/application.yml`

```yaml
processes:
  main:
    primary: true
    web:
      default:  { host: 0.0.0.0,   port: 8086, shared: true }
    grpc:
      internal: { host: 127.0.0.1, port: 9095 }        # chỉ trong máy
      external: { host: 0.0.0.0,   port: 9096 }        # ra ngoài, có mTLS
    socket:
      rpc:      { path: /run/xime/data-main.sock }

  api-2:
    web:
      default:  { host: 0.0.0.0,   port: 8086, shared: true }
    grpc:
      internal: { host: 127.0.0.1, port: 9098 }
      external: { host: 0.0.0.0,   port: 9099 }
    socket:
      rpc:      { path: /run/xime/data-api-2.sock }
```

Ba tầng khoá: **id tiến trình** → **loại adapter** → **`server_id`**. Khoá `default`
ứng với `WebAdapter()` không đối số.

**Khoá của một khối điểm phục vụ** (bổ sung chiều 2026-08-16 - bản trước **thiếu
`host`**, chủ dự án phát hiện):

| Khoá | Adapter nào | Ghi chú |
|---|---|---|
| `host` | web, grpc | Để trống thì lấy mặc định hiện hành của adapter. Ca thật cần nó: `internal` bind `127.0.0.1`, `external` bind `0.0.0.0` |
| `port` | web, grpc | |
| `path` | socket | Thay cho `host`/`port` |
| `shared` | web · grpc (chỉ Linux) · socket | **Khai tường minh**, vì *"bind thành công"* mang hai nghĩa - xem 5.9 |
| `ssl` | web | Hiện đang truyền trong code (`WebAdapter(ssl=...)`), đây là chỗ nó nên về |

⚠ **Mọi tiến trình phải có cùng tập adapter** (chủ dự án chốt): code bên trong phụ
thuộc lẫn nhau, tách ra cái có cái không thì khó lắp, DI mỗi tiến trình một khác, và
số cách hỏng nhân theo tổ hợp. Ma trận **đầy** dễ kiểm hơn ma trận thưa - phép kiểm
rút gọn thành *"mọi hàng có cùng tập cột"*. Web quá tải mà MQTT nhàn thì vẫn **thêm
đồng loạt**.

⚠ **Nhưng luật đó áp cho CỬA VÀO, và ba adapter không nhân bản được bằng cách nhân
đôi kết nối** - xem 5.7. Modbus/OPC UA còn có một ngoại lệ nữa ở 5.7.3.

### 5.3b. Viết gọn N tiến trình giống nhau

Bốn tiến trình giống hệt thì không viết bốn khối:

```yaml
processes:
  main:
    primary: true
    web:  { default:  { port: 8086, shared: true } }
    grpc: { internal: { port: 9095, shared: true } }

  workers:
    count: 3          # chỉ hợp lệ khi MỌI cổng trong khối là shared
    web:  { default:  { port: 8086, shared: true } }
    grpc: { internal: { port: 9095, shared: true } }
```

Hai ràng buộc:

- **`count` mà có cổng không `shared` là lỗi khởi động.** Không tự sinh dải cổng -
  tự sinh là lấn sang việc của [`đăng kí mạng.md`](../../../đăng%20kí%20mạng.md), và
  người vận hành sẽ có bốn cổng không ai đăng ký.
- **Id sinh ra phải xác định** (`workers-1`, `workers-2`, `workers-3`), vì nó là
  nhãn trong mọi dòng log và trong `/healthz`.

### 5.4. App một tiến trình: không đổi một chữ

```python
app = Application()
app.add_config(config)

if __name__ == "__main__":
    app.use(WebAdapter()).use(GrpcAdapter()).run()
```

Không gọi `share_load()` → `run()` chạy nhánh đơn tiến trình, đọc `server.port` /
`grpc.port` như cũ, **không cần khối `processes:`**. Đây là thứ giữ cho 31 codebase
hiện tại không phải di cư.

### 5.5. ⭐ Mô hình chạy: supervisor **giữ socket nhưng không phục vụ** + con chạy lại `main.py`

> ⚠ **Sửa cách phát biểu, chiều 2026-08-16.** Bản đầu ghi *"supervisor thuần, không
> mở cổng nào"*. Sau khi chốt web chung cổng theo kiểu uvicorn thì cha **phải**
> `bind()` và `listen()`. Phát biểu đúng:
>
> > Cha **giữ socket nhưng không phục vụ**: nó `bind()` + `listen()`, **không bao
> > giờ `accept()`**, không dựng DI, không chạy code nghiệp vụ.
>
> Cha vẫn nhẹ, vẫn dựng lại được con, chỉ khác là nó nắm một tài nguyên. Lợi ích phụ
> đáng kể: **cổng bị chiếm thì cha nổ ngay lúc khởi động**, thay vì bốn con lần lượt
> nổ và người vận hành đọc bốn stack trace giống nhau.

**Hai câu hỏi tách rời được, và chúng có hai câu trả lời độc lập:**

| Trục | Câu hỏi | Chốt |
|---|---|---|
| 1 | Tiến trình gốc có phục vụ request không | **Không.** Supervisor thuần |
| 2 | Con lấy code ứng dụng bằng cách nào | **Chạy lại `main.py`** + biến môi trường |

Bốn tổ hợp đều dựng được; chốt là ô *(supervisor thuần × chạy lại main)*.

```text
Người vận hành gõ:  python -m app.main        (không đối số, không env)
│
├─ import config                → registry được điền
├─ app = Application()          → object rỗng, chưa mở gì
├─ app.add_config(config)
├─ app.use(...) x3              → ba object adapter, CHƯA start, chưa chiếm cổng
│
└─ if __name__ == "__main__":  app.share_load().run()
   │
   └─ share_load() nhìn XIME_PROCESS_ID → KHÔNG có → "tôi là cha"
      │
      ├─ kiểm application.yml (bốn phép kiểm ở mục 6)
      ├─ bind() + listen() các cổng web và unix socket dùng chung
      ├─ sinh con "main"  : env XIME_PROCESS_ID=main,  kèm socket đã bind
      ├─ sinh con "api-2" : env XIME_PROCESS_ID=api-2, kèm socket đã bind
      └─ vòng lặp giám sát: con chết thì dựng lại, Ctrl+C thì tắt theo thứ tự
         KHÔNG accept() · KHÔNG dựng DI · KHÔNG chạy code nghiệp vụ

Mỗi con chạy lại đúng file đó, tới share_load() thì:
      → CÓ XIME_PROCESS_ID → "tôi là con api-2"
      → đọc khối processes.api-2, gán cổng cho từng adapter theo server_id
      → dựng DI, start adapter, phục vụ, KHÔNG sinh con nào
```

**Vì sao cha không được chết** (bốn lý do, chọn "ở lại" thay vì "kết thúc sau khi
sinh con"):

| | |
|---|---|
| Con chết thì ai dựng lại | Không ai. `systemd` chỉ trông tiến trình nó sinh trực tiếp; con mồ côi thì `init` nhận nuôi nhưng không hồi sinh |
| `Ctrl+C` | Không có cha thì không chỗ nào điều phối thứ tự tắt, bốn tiến trình cùng đứt giữa chừng |
| Tắt êm | Cần một chỗ biết cả đàn: rút một con khỏi LB, đợi nó phục vụ nốt, đóng, rồi tới con sau |
| Thêm bớt tiến trình lúc chạy, `/healthz` tổng | Cần một điểm |

Giá phải trả nhỏ **vì cha không dựng DI**: chỉ đọc YAML, kiểm, sinh, trông. Không
kết nối database, không lấy cert, không `post_construct`.

⭐ **Hệ quả tốt ngoài dự tính: `primary` trở thành CON THỨ NHẤT.** Trước đó primary
là tiến trình gốc, nghĩa là primary chết thì mất luôn supervisor. Nay primary chỉ là
một con bình thường được cấp thêm scheduler, và supervisor dựng lại nó khi nó chết.

**`run()` có ba nhánh, mỗi nhánh do một điều kiện QUAN SÁT ĐƯỢC quyết định:**

| Điều kiện | `run()` làm gì |
|---|---|
| không gọi `share_load()` | chạy đơn tiến trình như hôm nay - **tương thích cho 31 app** |
| có `share_load()`, **không** có env | supervisor |
| có `share_load()`, **có** env | worker |

⚠ Dùng **biến môi trường**, không dùng `sys.argv`: `argv` là chỗ ứng dụng có thể tự
dùng, còn env thừa kế tự nhiên xuống con và không đụng gì. Và người vận hành vẫn gõ
`python -m app.main` trống trơn - **đối số do framework tự đặt khi sinh con**, không
phải thứ ai gõ tay.

⚠ **Framework biết `process_id`, nhưng KHÔNG phơi ra cho code nghiệp vụ.** Có
`current_process_id()` công khai thì sớm muộn sẽ có người viết `if process_id ==
"main"` trong use case, và từ đó N tiến trình chạy N nhánh code khác nhau. Cần phân
biệt thì phân biệt bằng **năng lực được cấp**, không bằng **tên**.

### 5.6. Vì sao chạy lại `main.py` thay vì entry point riêng

Đây là chỗ cân nhắc lâu nhất buổi chiều. Hai đường:

| | **A. Entry riêng của framework** | **B. Chạy lại `main.py` + env** ← CHỐT |
|---|---|---|
| Con chạy gì | `python -m xime._worker` | `python -m app.main` với `XIME_PROCESS_ID=...` |
| Con biết adapter bằng | Cha **serialize công thức** `[("xime.adapters.web", "WebAdapter", {}), ...]`, con import class rồi dựng lại | `use()` chạy tự nhiên |
| Con biết config bằng | Cha gửi `config.__name__` | `import config` chạy tự nhiên |
| Chặn sinh con vô hạn | Con không có `share_load()` | `share_load()` đọc env |
| Ràng buộc mới | Mọi đối số của `use()` **phải serialize được**. Lambda, object đã mở tài nguyên là hỏng | Code ở mức module chạy `N+1` lần nên phải nhẹ |
| Debug tay một con | Khó, phải tự dựng spec | `XIME_PROCESS_ID=api-2 python -m app.main` |
| Số đường khởi động | **Hai** | **Một** |

> **Dòng cuối là lý do chọn B.** Hai đường khởi động là hai chỗ để trôi lệch, và
> loại lệch đó **không có triệu chứng**: ai đó thêm một `configure_middleware()` vào
> `main.py`, cha có, con không, ba tiến trình phục vụ thiếu một middleware xác thực
> và **không gì báo**. Cùng khuôn hỏng ngày 2026-07-31 của workspace (hai bộ test
> canh khoá hai luật khác nhau).

**Nền kỹ thuật, để không ai đề xuất lại "cho con thừa hưởng luôn":** Windows không
có `fork`, nên tiến trình con là một `python.exe` trắng và **buộc phải dựng lại
`app` từ code**. Đó là giới hạn kernel, không phải lựa chọn thư viện.

| Đường sinh con | Con thừa hưởng | `main.py` chạy lại |
|---|---|---|
| `fork` (Linux/macOS) | toàn bộ bộ nhớ cha | không |
| `spawn` (Windows **bắt buộc**) | không gì | **có** |
| `subprocess` + entry riêng | không gì | có (import module chứa `app`) |

⚠ **Khuyến nghị dùng `spawn` cả trên Linux** dù Linux có `fork`: `fork` sau khi đã
mở kết nối DB hoặc đã chạy event loop là nguồn bug rất khó tìm, và **dev trên Windows
chạy khác prod trên Linux đắt hơn nhiều so với cái `fork` tiết kiệm được**.

### 5.7. Mỗi adapter chia tải một kiểu

#### 5.7.1. Cơ chế chia cổng - CHỐT chiều 2026-08-16

| Adapter | Chia bằng | Linux | Windows |
|---|---|---|---|
| **web** (uvicorn) | **cha giữ socket, truyền fd cho con** | ✅ | ✅ `WSADuplicateSocket` qua `socket.share()` / `fromshare()` |
| **socket** (Unix domain) | **cha giữ socket** | ✅ | - |
| **grpc** | **`SO_REUSEPORT`** | ✅ (C-core **mặc định đã bật**) | ⛔ **không có đường nào** |

`grpc.aio` chỉ nhận địa chỉ dạng chuỗi (`add_insecure_port("host:port")`,
[_adapter.py:146-148](../../xime/adapters/grpc/_adapter.py)), **không có API nhận
socket từ ngoài**, nên nó không dùng được đường truyền socket.

⚠ **Windows vẫn chạy đa tiến trình được** - chỉ gRPC phải khai cổng riêng cho từng
tiến trình. Đây là giới hạn của một adapter, không phải của mô hình.

⚠ **Bắt buộc báo lúc khởi động:** trên Windows mà cấu hình khai
`grpc: { internal: { port: 9095, shared: true } }` thì **cha nổ ngay** với thông báo
nói rõ. Không có nó thì tiến trình thứ hai nổ bằng `WinError 10048` giữa lúc chạy,
và người đọc lỗi đó không có đường nào lần ra nguyên nhân thật.

⚠ **Sinh con bằng `multiprocessing`, không phải `subprocess`.** Đây là hệ quả của
việc cha giữ socket: `multiprocessing` vừa truyền được socket qua ranh giới tiến
trình trên cả hai hệ điều hành, **vừa vẫn import lại module main** (dưới tên
`__mp_main__`, nên `if __name__ == "__main__"` không kích hoạt) - tức `use()` vẫn
chạy tự nhiên và vẫn giữ được nguyên lý 10 *một đường khởi động*. `subprocess` thuần
thì phải tự dựng kênh truyền fd.

#### 5.7.2. Unix socket: mặc định **tách path**, cho phép chung

⚠ Đính chính một giả định của bản sáng: unix socket **chia sẻ được** y hệt TCP - một
listening socket `AF_UNIX` được nhiều tiến trình cùng `accept()`. Không có chuyện
*"bắt buộc N tiến trình thì N path"*.

Chủ dự án chốt **mặc định tách** (mỗi tiến trình một path), **cho phép chung** nếu
khai `shared: true`. Đánh đổi:

| | Tách N path | Chung một path |
|---|---|---|
| Client phải biết | **N đường dẫn**, tự cân bằng | **một đường dẫn** |
| Hợp đồng giữa hai phần mềm | N dòng, đổi khi thêm tiến trình | một dòng, không đổi |
| Client **chọn được** tiến trình nào | **Có** | Không |

Dòng cuối là lý do tách vẫn đáng có: với tiến trình **phân mảnh** (mỗi cái giữ một
cụm thiết bị) thì client phải gọi đúng tiến trình giữ cụm đó.

`main.py` không đổi: `app.use(SocketAdapter("rpc"))`. Cấu hình khai path từng tiến
trình (xem 5.3), hoặc cùng path + `shared: true` ở **mọi khối** - lặp giá trị trông
thừa nhưng nó **kiểm chéo được**: khai `shared` mà hai path khác nhau là lỗi bắt
được ngay, còn khai một lần ở cấp trên thì mất phép kiểm đó.

⛔ **Điều kiện trước khi cho phép chung path:** vá dòng `os.remove` ở
[_adapter.py:104](../../xime/adapters/socket/_adapter.py). Nó sinh ra để dọn socket
mồ côi sau crash và đúng với một tiến trình; với nhiều tiến trình cùng path thì
**tiến trình thứ hai xoá socket của tiến trình thứ nhất rồi bind cái mới** - tiến
trình một vẫn sống, vẫn `accept()` trên một inode không còn tên, **không ai gọi tới
được, và không lỗi nào phát ra**. Nó im lặng cướp chỗ chứ không nổ.

#### 5.7.3. Modbus / OPC UA: **phân mảnh**, không phải nhân bản

Chủ dự án nêu mô hình đúng: hai tiến trình, **mỗi cái điều khiển một dải thiết bị
khác nhau**, không tranh chấp. Web thì vẫn có ở cả hai và liên kết ngang qua vùng nhớ
chung + DB.

Đây là **một loại song song khác hẳn**, và khác về bản chất chứ không phải mức độ:

| | Web, gRPC | Modbus, OPC UA |
|---|---|---|
| Kiểu | **Nhân bản** - N bản làm cùng một việc | **Phân mảnh** - mỗi bản làm việc khác |
| Cấu hình | viết tắt được (`count: 3`) | **phải khai chi tiết từng tiến trình** |
| Một bản chết | ba bản còn lại gánh, người dùng không thấy gì | **cụm thiết bị đó mất hẳn** tới khi dựng lại |

> Nhân bản cho **dư thừa**; phân mảnh thì **không**. Đừng tưởng "chạy hai tiến trình
> thì an toàn hơn" - với Modbus thì không.

⭐ **Chi tiết làm hai adapter này khác hẳn: tên thiết bị xuất hiện trong CODE NGHIỆP
VỤ.** Docstring của `modbus/_config.py` ghi `modbus.read(Inverter, device="meter_a")`.
`server_id` của web là chuyện nội bộ framework; `device` của Modbus là **tên một
thiết bị vật lý có thật ngoài kia** mà use case gọi tới. Nên với mô hình phân mảnh,
`device="line-1"` **chỉ chạy được ở tiến trình giữ line-1** - việc phân mảnh lộ ra
trong code nghiệp vụ dù ta có muốn giấu hay không, vì cái thật ngoài kia đúng là
chia như vậy.

#### Quy tắc - CHỐT chiều 2026-08-16

Chủ dự án hợp nhất hai hình dạng phiên đề xuất thành **một quy tắc với hai cách
điền**:

> `main.py` khai **đủ mọi LOẠI thiết bị**. Cấu hình khai **tiến trình nào nối tới
> thực thể nào**. Khối vắng mặt thì adapter đó **không chạy** ở tiến trình đó.

```python
app.use(ModbusAdapter("bang-tai", controllers=[ConveyorController]))
app.use(ModbusAdapter("lo-nung",  controllers=[FurnaceController]))
```

```yaml
# Có 2 băng tải, 2 lò nung: ma trận đầy
main:    { modbus: { bang-tai: { BT-01: {host: 10.0.0.11} },
                     lo-nung:  { LN-01: {host: 10.0.0.21} } } }
line-2:  { modbus: { bang-tai: { BT-02: {host: 10.0.0.12} },
                     lo-nung:  { LN-02: {host: 10.0.0.22} } } }

# Chỉ có 1 lò nung: line-2 không khai, nên nó không chạy phần lò nung
main:    { modbus: { bang-tai: { BT-01: {host: 10.0.0.11} },
                     lo-nung:  { LN-01: {host: 10.0.0.21} } } }
line-2:  { modbus: { bang-tai: { BT-02: {host: 10.0.0.12} } } }
```

⚠ **Hai điều kiện**, cả hai đều chống hỏng im lặng:

1. **Framework phải LOG khi bỏ qua một adapter.** Phép kiểm số 3 ở mục 6 hiện ghi
   *"bỏ qua im lặng"* - với web thì đúng, với Modbus thì im lặng nghĩa là **một dây
   chuyền không ai đọc mà không ai biết**.
2. **Gọi thiết bị không thuộc tiến trình mình phải nổ với thông báo rõ**
   (*"thiết bị `LN-02` không được cấu hình ở tiến trình `main`"*), không timeout,
   không trả `None`.

#### Luật "cùng tập adapter" phải phát biểu BA TẦNG

Quy tắc trên làm tập adapter *thực sự chạy* khác nhau giữa các tiến trình, trong khi
5.3 nói phải giống nhau. Không mâu thuẫn - luật chỉ chưa nói rõ nó áp cho tầng nào:

| Tầng | Giống nhau giữa các tiến trình? |
|---|---|
| **Code khai** (`main.py`) | **Giống tuyệt đối** - một file, không nhánh nào |
| **DI dựng** | **Giống tuyệt đối** - đã chốt ở 2.7 |
| **Adapter thực sự khởi động** | web/grpc: giống · **modbus/opcua: khác theo cấu hình** |

Nới chỉ ở dòng thứ ba, và chỉ cho adapter phân mảnh. Web mà một tiến trình thiếu
khối thì vẫn là lỗi.

#### ⭐ Tách LOẠI khỏi THỰC THỂ - chủ dự án chọn hướng 3

Vấn đề: nếu hai tiến trình cùng dùng tên `bang-tai` thì **một tên gánh hai nghĩa** -
*vai trò trong code* và *máy có thật ngoài kia*. Dữ liệu ghi xuống DB lấy tên đó làm
khoá thì hai tiến trình sinh hai bản ghi trông giống hệt nhau, và báo cáo tổng hợp
không phân biệt được máy nào. Luật 03 ở tầng dữ liệu.

Chủ dự án chọn **thêm một tầng khoá**, tách hẳn hai nghĩa:

| | Ai biết | Ở đâu |
|---|---|---|
| **Loại** (`bang-tai`, `lo-nung`) | **Code** - controller viết cho một loại thiết bị | `main.py` |
| **Thực thể** (`BT-01`, `BT-02`) | **Cấu hình** - nhà máy nào có bao nhiêu máy là chuyện vận hành | `application.yml` |

Bốn tầng khoá: `process_id` → `modbus` → **loại** → **thực thể**.

Code đọc thì **lặp qua thực thể của loại mình giữ**:

```python
for dev in modbus.devices_of("bang-tai"):
    trang_thai = await modbus.read(Conveyor, device=dev)
```

Ba cái được: danh tính thật **có sẵn**, không cần khoá `id` phụ và không có nghĩa vụ
nào phải nhớ · thêm máy chỉ sửa cấu hình, `main.py` đứng yên (đúng nguyên lý 5) · và
nó là hình dạng đúng cho nhà máy, nơi một loại thiết bị luôn có nhiều cái.

⚠ **Hai hệ quả phải khai, vì chúng đụng vào code chứ không chỉ khoá cấu hình:**

1. **Tên thực thể KHÔNG BAO GIỜ là hằng trong code nghiệp vụ.**
   `modbus.read(X, device="BT-01")` viết cứng là buộc code vào một nhà máy cụ thể.
   Tên phải đến từ **vòng lặp** `devices_of(...)` hoặc từ **dữ liệu** (người dùng
   chọn máy nào trên màn hình).
2. **`@poll` / `@on_change` nay chạy một lần cho MỖI thực thể**, nên handler phải
   nhận thêm tham số biết mình đang xử lý máy nào. Đây là **thay đổi thật trong
   adapter**, không phải đổi khoá cấu hình.

**Viết tắt cho ca đơn giản:** nếu giá trị dưới tên loại là dict phẳng có `host` thì
coi như một thực thể trùng tên loại - tức `modbus.devices.meter_a.host` như hôm nay
vẫn chạy nguyên, không ai phải di cư vì một PLC.

⚠ Hướng này **đổi khoá cấu hình `modbus.devices.<name>` hiện hành**, nên nó thuộc
nhóm "đổi API công khai" cùng bốn mục ở phần 4. Chủ dự án chốt: *"nếu cần thì cứ thay
đổi code framework thoải mái, để code phục vụ thiết kế."*

#### ⭐ Đọc/ghi thiết bị nằm ở tiến trình nào - CHỐT

Hệ quả chưa bàn tới lúc đầu, và nó lớn hơn phần cấu hình: cả hai tiến trình đều có
web (chung cổng, **kernel chia request ngẫu nhiên**) và đều dựng DI đủ, nên
`ModbusClient` có mặt ở cả hai. Use case gọi `device="LN-02"` mà rơi vào tiến trình
`main` thì hỏng - và vì chia ngẫu nhiên, nó hỏng **một nửa số lần**, kiểu lỗi tệ nhất
để gỡ.

Luật chủ dự án chốt:

> **Đọc và ghi thiết bị là việc của tiến trình giữ thiết bị đó. Web đọc kết quả từ DB
> hoặc vùng nhớ chung, không gọi thẳng adapter fieldbus.**

Có luật này thì lỗi "gọi thiết bị không thuộc tiến trình mình" từ chuyện xảy ra
thường xuyên thành chuyện chỉ xảy ra khi lập trình viên viết sai - và lúc đó thông
báo rõ (điều kiện 2 ở trên) là đủ.

**Chiều GHI thì không giải bằng DB được** - bấm nút *"dừng băng tải BT-02"* trên web,
request rơi vào `main`, mà BT-02 do `line-2` giữ. Đó là **lệnh**, không phải dữ liệu.

✅ **Chủ dự án chốt: dùng BUS liên tiến trình** (thứ `ke-hoach-0.8.md` thiết kế sẵn mà
từ đầu đến giờ chưa ai chỉ ra được nó chở gì). *"Bàn kỹ sau"*, nhưng ghi lại ba chỗ
bản 0.8 chưa đủ và một chỗ đừng làm - xem 5.7.4b.

OPC UA y hệt, đổi `modbus` thành `opcua`, `host`/`port` thành `endpoint`.

⚠ **Chi tiết từ code Modbus, đáng nhớ khi dựng lại tiến trình:** `@on_change`
**không bắn ở lần đọc đầu**, nó chỉ lấy mốc. Nên tiến trình vừa được dựng lại
**bỏ lỡ thay đổi xảy ra trong lúc nó chết** - giá trị đã đổi rồi, và lần đọc đầu chỉ
ghi nhận giá trị mới làm mốc. Với cảnh báo vượt ngưỡng thì đó là một cảnh báo mất
luôn. Vá bằng cách lấy mốc từ DB thay vì từ lần đọc đầu, nhưng **đó là việc của
app**, không phải framework.

OPC UA y hệt, đổi `modbus.devices` thành `opcua.servers`, `host`/`port` thành
`endpoint`.

#### 5.7.4. MQTT - CHỐT: **giữ nguyên là client, KHÔNG làm broker**

**Hiện trạng đo được:** `MqttAdapter.start()` gọi `aiomqtt.Client(**kwargs)` rồi
connect tới `mqtt.host:mqtt.port` ([_adapter.py:209](../../xime/adapters/mqtt/_adapter.py),
[_config.py:55-56](../../xime/adapters/mqtt/_config.py)). **Client thuần**, `host` bắt
buộc và fail-fast nếu thiếu - tức framework luôn giả định có broker ở ngoài.

⚠ Đính chính một hiểu nhầm về **chiều kết nối**, ghi lại để lần bàn sau khỏi đi lại
đường cũ: với HTTP/gRPC thì người ngoài kết nối **vào** app nên LB đứng trước cổng
đó; với MQTT thì app là **client**, nó kết nối **ra** broker và **không mở cổng
nào**, nên **LB không có gì để cân**.

Lời giải chia tải nằm ở **broker**: shared subscription của MQTT 5
(`$share/<group>/<topic>`) để broker chia lượt, kèm điều kiện `client_id` phải **khác
nhau** - đúng chỗ gộp ở 3.2. Và LMDB chia sẻ **dữ liệu sau khi xử lý**, không chia sẻ
**kết nối**, nên nó không quyết định được ai nhận.

##### Vì sao KHÔNG tự viết broker (chủ dự án hỏi, chốt 2026-08-16)

Bối cảnh: chủ dự án nhắm **nhà thông minh · nhà máy thông minh · nông nghiệp thông
minh**, cần "một máy chủ điều khiển thiết bị", và đặt câu *"tự xây broker hay dùng có
sẵn"*. Chẩn đoán đi kèm **đúng**: thiết bị chạy nổi framework thì dùng gRPC/HTTP
nhanh hơn; MQTT chỉ còn lý do tồn tại với thiết bị quá nhỏ.

Bốn lý do, xếp theo trọng lượng:

| | |
|---|---|
| **Broker là chỗ đã chuẩn hoá, không phải chỗ tạo khác biệt** | Đúng [luật 04](../../../.claude/rules/04-tham-khao-nghiep-vu-truoc-khi-code.md): *chép thứ nhàm chán, giữ nguyên thứ mình cố ý khác*. Không khách nào trả tiền vì broker hay hơn - họ trả cho quy tắc tự động, cảnh báo, biểu đồ, báo cáo |
| ⭐ **Firmware đầu kia KHÔNG sửa được** | Với web/gRPC ta kiểm soát cả hai đầu. Broker thiếu tính năng = **thiết bị không kết nối được và không có đường vá từ phía ta**. Ba lĩnh vực trên đều có thiết bị từ hàng chục hãng, mỗi hãng lệch spec một chút - broker chạy 10 năm đã va vào những chỗ đó rồi |
| **Ca dùng chưa tồn tại** | 31 codebase hiện tại chưa app nào dùng MQTT. [Luật 02](../../../.claude/rules/02-ba-muc-chua-co-va-adapter-rong.md): thứ bị chặn bởi **thị trường** thì được phép chưa code |
| **Đa tiến trình làm nó nặng thêm một bậc** | Broker giữ **trạng thái session** (subscribe, message chưa ack, retained) - hàng đợi có thứ tự, không chia sẻ tự nhiên qua LMDB. Nó chỉ chạy được ở **một** tiến trình, tức thành adapter **đơn nhất**, mọi tiến trình khác publish phải qua bus |

⚠ **Khác hẳn ca LMDB/Redis:** ở đó Redis bị loại vì nó **qua mạng** và phá mô hình đa
tiến trình cùng máy - có lý do kiến trúc. Mosquitto **không phá gì cả**, nó chỉ là
một tiến trình nữa cùng máy, ~3-5MB RAM.

**Một broker dùng được ngoài đời phải có:** MQTT 3.1.1 **và** 5.0 (thiết bị cũ chỉ
nói 3.1.1) · **Last Will and Testament** (cách duy nhất biết thiết bị rớt) · retained
message · session persistence (`clean_session=false`, cho thiết bị chạy pin ngủ rồi
tỉnh) · QoS 1 và 2 (QoS 2 là bắt tay bốn bước có trạng thái) · topic matching,
keepalive, TLS, ACL.

##### Bốn broker mã nguồn mở đáng xét

| | Ngôn ngữ | Giấy phép | Hợp với |
|---|---|---|---|
| **Mosquitto** | C | EPL 2.0 / EDL 1.0 | **Khuyến nghị giai đoạn đầu.** ~3-5MB RAM, chạy trên Raspberry Pi và router |
| **NanoMQ** | C | MIT | Gateway biên, siêu nhẹ. Cùng nhà EMQ nên nâng cấp lên EMQX thuận |
| **EMQX** (bản OSS) | Erlang | Apache 2.0 cho bản OSS | Khi cần **cluster**, hàng trăm nghìn kết nối |
| **VerneMQ** | Erlang | Apache 2.0 | Cùng hạng EMQX |

⚠ **Hai chỗ phải TỰ KIỂM trước khi cam kết** (đừng tin bảng này): **giấy phép bản
hiện hành** - EMQX đã từng đổi mô hình cấp phép cho một số thành phần, phải xem bản
đang dùng chứ không xem bài viết cũ · và **điều kiện phân phối kèm** nếu Xime bán máy
chủ điều khiển như sản phẩm đóng gói.

⭐ **Lợi ích lớn nhất của việc không tự xây: đổi broker gần như miễn phí.** Cả bốn nói
MQTT chuẩn, nên chuyển Mosquitto → EMQX khi hệ lớn lên là đổi **một dòng `host`**,
không sửa dòng code Xime nào. Tự xây là tự khoá vào thứ không đổi được.

##### ⭐ Cái đáng đầu tư thay vào đó

| Nên xây | Vì sao |
|---|---|
| **Sparkplug B** (nếu làm nhà máy) | Chuẩn de-facto IIoT: cấu trúc topic, payload protobuf, birth/death certificate. **Chạy trên bất kỳ broker nào**, và là thứ khách công nghiệp hỏi tới mà phần lớn sản phẩm nội địa chưa có |
| **Lưu chuỗi thời gian + truy vấn** | Nền của mọi biểu đồ, cảnh báo, báo cáo |
| **Engine quy tắc** (nếu X thì Y) | Thứ người dùng cuối thực sự cấu hình và trả tiền |
| ⭐ **Sổ đăng ký thiết bị + cấp danh tính** | **Xime đã có sẵn nền này** - Trust cấp cert, mô hình hồn-xác, `PEER_APP_ID`. Đây mới là chỗ Xime khác được: thiết bị có danh tính thật, không phải username/password dùng chung. Phần lớn giải pháp IoT làm chỗ này rất sơ sài |

##### Ba lĩnh vực khác nhau nhiều hơn vẻ ngoài

- **Nhà máy**: MQTT chỉ ở tầng trên; tầng dưới là Modbus, OPC UA, Profinet - **Xime
  đã có hai cái đầu**. Gần đích nhất, và khách chịu chi nhất.
- **Nông nghiệp**: mạng chập chờn, thiết bị chạy pin, thường qua LoRaWAN/NB-IoT chứ
  không MQTT trực tiếp. Cần gateway dịch, và **logic phải nằm ở thiết bị**.
- **Nhà thông minh**: Home Assistant (Apache 2.0) đã chiếm lĩnh với hàng nghìn tích
  hợp. Vào bằng **dịch vụ lắp đặt cho thị trường Việt Nam**, không bằng viết lại phần
  mềm.

##### Ba tín hiệu để xét lại (chưa cái nào xuất hiện)

1. Có khách **thật**, và mosquitto là thứ **đang** chặn họ - không phải "có thể sẽ".
2. Xime bán **thiết bị đóng gói** mà thêm một tiến trình ngoài là vấn đề vận hành
   thật. ⚠ Kể cả lúc đó, đường đúng vẫn là **nhúng một broker OSS**, không viết lại
   protocol.
3. Cần một tính năng không broker nào có, **và tính năng đó là lý do khách mua**.

##### Vai của MQTT trong Xime - chủ dự án làm rõ

> *"MQTT tôi dùng là dùng cho máy chủ, không phải broker - mà máy chủ xử lý dữ liệu gì
> đó thôi. Ở máy chủ, chia client theo tiến trình máy chủ."*

Tức đúng vai adapter đang có: máy chủ Xime là **client**, nhận dữ liệu thiết bị đẩy
lên qua broker ngoài, xử lý rồi ghi xuống. Không đổi gì về bản chất, chỉ cần chạy được
ở nhiều tiến trình.

##### Nền: MQTT lọc theo topic, không phát mù

Đính chính một hiểu nhầm nhỏ nhưng nó là nền của cả phần chia tải: broker **không**
phát cho tất cả. Nó giữ danh sách ai đăng ký **topic filter** nào rồi chỉ gửi tới
những ai khớp - thiết bị publish `nha-kinh/A/nhiet-do` thì ai subscribe
`nha-kinh/B/#` không nhận gì. Nên MQTT vốn đã có sẵn cơ chế chia việc, chỉ là chia
theo **chủ đề** chứ không theo tải. Ngoại lệ ngược hẳn là **shared subscription**
(`$share/nhom/topic`): broker gửi cho **đúng một** thành viên.

##### Quá tải: ba chỗ khác nhau, ba cách chữa khác nhau

| Nghẽn ở | Triệu chứng | Chữa bằng |
|---|---|---|
| **Broker** | kết nối bị từ chối, độ trễ tăng đều với mọi client | Broker mạnh hơn (EMQX cluster), hoặc nhiều broker chia theo vùng |
| **Client Xime** | message dồn, xử lý trễ dần | **Nhiều tiến trình** |
| **Handler** (ghi DB, gọi API) | CPU thấp mà vẫn chậm | Sửa code, hoặc mở rộng thứ nó gọi tới |

⚠ Ở quy mô Xime nhắm tới, nghẽn ở broker **khó xảy ra**: mosquitto trên phần cứng
khiêm tốn xử lý vài chục nghìn message/giây, còn nhà kính 1000 cảm biến gửi mỗi 5
giây chỉ là 200 msg/s - nhẹ hơn hai bậc. Nghẽn thật gần như luôn ở dòng thứ ba, và
đây là **bài học lặp lại từ ca LMDB/Postgres**: nếu handler ghi DB thì nút thắt là
DB, và thêm tiến trình MQTT chỉ **dời tranh chấp xuống dưới**. Đo trước, chia sau.

✅ **Tin tốt: adapter ĐÃ có backpressure.**
[_adapter.py:220-227](../../xime/adapters/mqtt/_adapter.py) acquire semaphore trước
khi `create_task`, nên khi số handler đang chạy chạm trần thì vòng
`async for message in client.messages` ngừng đọc và TCP đẩy ngược áp lực về broker.
Không tràn bộ nhớ, không mất tin ở QoS 1 - nó **chậm lại chứ không vỡ**.

##### Hai cách chia tải, KHÔNG thay thế nhau

> Với Modbus, chia theo thiết bị là **bắt buộc** (hai tiến trình cùng poll một PLC là
> tranh chấp vật lý). Với MQTT, chia là **lựa chọn** - broker đã lo phân phối.

| | **Chia theo topic** ← chọn cái này | **Shared subscription** |
|---|---|---|
| Cách làm | mỗi tiến trình subscribe filter khác: `nha-kinh/A/#` vs `nha-kinh/B/#` | mọi tiến trình cùng `$share/g/nha-kinh/#` |
| Ai nhận gì | **Xác định** - biết chắc cụm nào do ai xử lý | **Không xác định** - broker chia lượt |
| Tải | Có thể lệch nếu cụm không đều | **Tự cân** |
| Thêm một tiến trình | Sửa cấu hình, chia lại filter | Chỉ cần bật lên |
| Debug | Dễ - lần theo topic ra tiến trình | Khó |
| ⭐ **Thứ tự trong một thiết bị** | **Giữ được** | **MẤT** |

⭐ **Dòng cuối là chỗ quyết định, và nó không hiện ra cho tới khi cắn:** thiết bị gửi
chuỗi `bật` → `tắt` → `bật`; shared subscription có thể phát ba message cho ba tiến
trình, chúng xử lý song song, và trạng thái ghi xuống DB là **cái nào thắng cuộc đua**
chứ không phải cái đến sau cùng. Với dữ liệu cảm biến (chỉ lấy giá trị mới nhất) thì
vô hại; với **sự kiện trạng thái, lệnh, hay đếm** thì sai âm thầm.

##### Nối vào luật 01: đây là phân mảnh theo KHOÁ

Chia theo topic thực chất là phân mảnh theo khoá - cùng khái niệm với `org_id` của
[luật 01](../../../.claude/rules/01-song-song-hoa-va-shard.md) và partition của Kafka.
Câu hỏi đúng không phải *"chia thế nào"* mà là:

> **Khoá phân mảnh là gì, và mọi message của cùng một khoá có luôn về cùng một chỗ
> không?**

Khoá phải là **thiết bị hoặc cụm thiết bị**. ⛔ **Đừng chia theo loại đo**
(`+/nhiet-do` cho tiến trình 1, `+/do-am` cho tiến trình 2) - lúc đó một thiết bị nói
chuyện với hai tiến trình và mất khả năng suy ra trạng thái của nó ở một chỗ.

##### Ba việc PHẢI làm, một việc NÊN làm

| # | Việc | Ghi chú |
|---|---|---|
| **1** | **Tách `client_id` khỏi `_server_id`** (3.2) | **Bắt buộc, làm trước** - không có nó thì không việc nào sau đây chạy được. Sau khi tách: `server_id` = *kết nối tới broker nào* (lập trình viên đặt, như `GrpcAdapter("internal")`); `client_id` = *danh tính phiên với broker*, phải duy nhất toàn hệ (người vận hành đặt). `server_id` có ích thật khi một máy chủ nối hai broker: `MqttAdapter("nha-may")` + `MqttAdapter("cloud")` |
| **2** | **`client_id` và `topics` vào khối `processes`** | **Ba tầng, giống web/grpc - KHÔNG cần bốn tầng như Modbus**, vì ở đây chia theo tiến trình máy chủ chứ không theo thiết bị vật lý |
| **3** | ⭐ **Topic filter phải đến từ CẤU HÌNH, không phải hằng trong `@subscribe`** | Hôm nay `@subscribe("nha-kinh/A/#")` viết cứng. Chia theo tiến trình nghĩa là **cùng một controller chạy ở hai tiến trình với hai filter khác nhau** - không làm được nếu filter nằm trong code |
| nên | **Chọn khoá phân mảnh cho đúng** | Xem mục ngay trên |

```yaml
mqtt:
  host: broker.local          # chung, mọi tiến trình kế thừa
  port: 1883

processes:
  main:
    mqtt:
      nha-may: { client_id: xime-main, topics: ["nha-kinh/A/#"] }
  api-2:
    mqtt:
      nha-may: { client_id: xime-2,    topics: ["nha-kinh/B/#"] }
```

`host` ở cấp trên vì mọi tiến trình nối cùng broker; `client_id` và `topics` theo từng
tiến trình vì đó mới là thứ **phải** khác nhau.

**Cách hiện thực việc 3, nhẹ nhất:** giữ `@subscribe` làm **bảng định tuyến**, cấu
hình `topics` quyết định tiến trình này **thật sự subscribe cái nào**, adapter lấy
giao của hai thứ. Kèm một phép kiểm lúc khởi động, cùng khuôn phép kiểm số 2 ở mục 6:

> Route nào của controller mà **không tiến trình nào** subscribe → **cảnh báo**, kèm
> tên route.

Không có nó thì gõ nhầm `nha-kinh/A/#` thành `nhakinh/A/#` trong YAML là **một handler
không bao giờ chạy, và không gì báo**.

##### Việc KHÔNG cần làm

- **Shared subscription** - chỉ cần khi muốn tải tự cân với xử lý **không trạng thái**
  (nhận ảnh rồi đẩy lên kho, chuyển tiếp sang hệ khác). Chia theo topic đã đủ và cho
  tính xác định, quý hơn ở nhà máy.
- **Broker** - đã chốt ở trên.
- **Sparkplug B** - chỉ khi có khách công nghiệp thật hỏi tới.
- Đụng vào `qos` / `retained` / `will` / backpressure - phần này **đã đủ**.

⚠ **Thứ tự:** việc 1 và 2 đi cùng nhau, nằm gọn trong đợt đổi API ở mục 4 - làm một
thể với web/grpc/socket. Việc 3 độc lập, làm sau cũng được vì nó chỉ cần khi thật sự
bật tiến trình thứ hai có MQTT. **Hôm nay chưa app nào dùng MQTT nên cả ba chưa gấp**;
chúng chỉ thành đường găng vào ngày bắt đầu app nhà kính hoặc nhà máy thật.

#### 5.7.4b. Bus liên tiến trình - chở LỆNH điều khiển (chốt dùng, bàn kỹ sau)

⭐ **Chỗ ăn khớp đáng chú ý: kênh cha-con đã phải có sẵn rồi.** Ràng buộc (b) của
2.8 đòi một kênh cha → con lúc chạy để thăng cấp primary; health check và lệnh drain
cũng cần đúng kênh đó. Nên bus liên tiến trình **dùng lại chính nó**, cha làm trung
tâm chuyển tiếp, **không cần thành phần mới nào**.

Đánh đổi: mọi tin đi qua cha nên cha là nút cổ chai và điểm chết. Với **tín hiệu**
(thưa, nhỏ) thì không sao. Cần thông lượng cao thì đó không còn là tín hiệu mà là
**dữ liệu**, mà dữ liệu đi qua LMDB và vùng nhớ chung - đúng phân vai đã chốt ở
[file cache](cache-lien-tien-trinh-2026-08-16.md). Ranh giới tự nó rõ.

**Ba chỗ thiết kế 0.8 chưa đủ cho ca này:**

| Thiếu | Vì sao cần |
|---|---|
| **Phản hồi** | 0.8 là fire-and-forget. Web bấm *"dừng băng tải"* thì phải biết lệnh đã chạy chưa, không thể hiện màn hình xanh rồi thôi |
| **Phân biệt "không ai nhận" với "đã làm xong"** | Broadcast mà không tiến trình nào giữ thiết bị đó thì từ phía người gửi **trông y hệt** broadcast mà mọi người xử lý. Luật 03, và ở đây nó nghĩa là **băng tải không dừng mà màn hình báo đã dừng** |
| **Địa chỉ, hoặc quy ước lọc** | 0.8 là broadcast-only. Lọc ở bên nhận (*"thiết bị này có phải của tôi không"*) là đủ với vài tiến trình, nhưng phải khai thành **quy ước** chứ không để mỗi controller tự nghĩ |

⛔ **Một chỗ đừng làm: đảm bảo giao tuyệt đối.** Bus trong bộ nhớ chung cùng máy hầu
như chỉ mất tin khi **tiến trình đích chết** - mà tiến trình đích chết thì nó cũng
đang giữ kết nối Modbus, nên **không đường phần mềm nào dừng được băng tải đó**.
Fail-safe của ca này nằm ở **watchdog trên PLC**, không nằm ở framework. Đầu tư vào
*"bus không bao giờ mất tin"* là mua một bảo đảm mà lớp dưới không có.

⚠ Phần lớn `ke-hoach-0.8.md` đã bị lật (mục 7), nên cái cần là **viết lại bus với vai
trò mới** (chở tín hiệu, có phản hồi, đi qua kênh cha-con), không phải lôi bản cũ ra
dùng. `BusMessage` và hàng đợi thì tái dụng được.

#### 5.7.5. Vế thứ hai của luật "cùng tập adapter"

> Mọi tiến trình dựng **cùng một đồ thị DI** và cùng một tập adapter được khai.
> Adapter nào **không nhân bản được** thì framework chỉ khởi động nó ở primary, và
> **nói ra điều đó lúc khởi động**, không im lặng. Adapter **phân mảnh** (5.7.3) là
> ngoại lệ khai tường minh trong cấu hình.

Nó ghép đúng với ngoại lệ scheduler: **primary có đủ, các tiến trình khác có phần
nhân bản được**. Một câu, hai áp dụng.

### 5.8. Quyết định nằm trong hình dạng này

| Quyết định | Vì sao |
|---|---|
| Ba tầng khoá: **id tiến trình** → **loại adapter** → **`server_id`** | Cổng thuộc **cặp**, không thuộc riêng cái nào |
| `primary: true` khai **tường minh**, không dựa thứ tự trong file | Thứ tự YAML mang ý nghĩa là phụ thuộc ngầm: sắp xếp lại cho gọn mắt là đổi hành vi mà không gì báo |
| Không có khối `processes` thì đọc `server.port`/`grpc.port` như cũ | Tương thích ngược; ai chưa cần chia tải không phải học gì |
| Scheduler và job **không xuất hiện trong cấu hình** | Không khai được thì không khai sai được |
| Tên tiến trình do **người vận hành đặt** | Phải khớp cổng đã đăng ký trong sổ mạng, và là nhãn trong mọi dòng log |

### 5.9. Bình luận của chủ dự án về Docker và cân bằng tải

> Nếu chạy trên VPS, máy chủ vật lý (không ảo hoá) thì dùng LMDB nhúng sẵn trong
> framework; nhưng nếu Docker và Kubernetes thì phải dùng Redis, phải tính từ trước
> là dùng cái nào. Riêng tôi thì tôi không thích chạy trên Docker, Kubernetes, vì nó
> không dùng được cái liên kết đa tiến trình framework dựng sẵn. Nếu muốn cân bằng
> tải thì framework có cơ chế tự tăng giảm tiến trình luôn, cổng mạng đã đăng ký
> trước, người vận hành cho giới hạn tối thiểu, tối đa được dùng.

⚠ **Một chỗ cần tách, vì một quyết định lớn đang tựa lên nó: nginx KHÔNG kéo theo
Docker/Kubernetes.** Thứ phá LMDB là **nhiều máy** và **cách ly filesystem**, không
phải bản thân việc có một reverse proxy. nginx chạy như một tiến trình bình thường
trên chính VPS đó, trỏ vào `127.0.0.1:8086`, `127.0.0.1:8088`, và các tiến trình
Xime vẫn mmap chung một file LMDB. Không mất gì.

| Mức | Cần gì | Được gì | Mất gì |
|---|---|---|---|
| **`SO_REUSEPORT`** | Sửa vài chục dòng ở web adapter | Kernel tự chia tải, **không chặng phụ, không tiến trình phụ** | Chỉ Linux. Không TLS termination, không định tuyến theo host |
| **nginx trước N tiến trình, cùng máy** | Một khối `upstream` ~6 dòng | TLS, tên miền, header, static, rate limit | Một tiến trình nữa phải cài và trông |
| **Docker/K8s** | Nhiều | Nhiều máy, tự hồi phục | **LMDB hết dùng chung** |

Ranh giới thật nằm giữa dòng 2 và 3, **không phải giữa 1 và 2**.

⭐ **`SO_REUSEPORT` gần như đã có sẵn ở gRPC**: adapter bind bằng
`add_insecure_port("host:port")` ([_adapter.py:146-148](../../xime/adapters/grpc/_adapter.py)),
mà gRPC C-core **mặc định bật `SO_REUSEPORT` trên Linux**. Nghĩa là hai tiến trình
cùng khai một cổng gRPC sẽ bind thành công cả hai và kernel chia tải - **trên
Windows thì tiến trình thứ hai nổ**.

> ⚠ Hệ quả xấu phải vá: *"bind thành công"* đang mang hai nghĩa - *tôi độc chiếm
> cổng này* và *tôi đang chia cổng với người khác*. Khai nhầm trùng cổng thì Windows
> báo ngay, Linux chạy êm và một nửa request đi vào tiến trình không định gửi tới.
> Bản vá: bắt khai tường minh `{ port: 9096, shared: true }`, phép kiểm khởi động
> **từ chối** cổng trùng khi không có cờ đó.

Web adapter chưa dùng được ngay vì gọi `uvicorn.Server.serve()` không truyền socket,
nhưng uvicorn nhận `serve(sockets=[...])` nên chỉ cần tự tạo socket rồi đưa vào.

**Đề nghị của phiên: đừng viết bộ cân bằng tải.** Một LB layer 7 tử tế phải làm TLS,
HTTP/2, keep-alive upstream, health check, graceful drain, chống slowloris, giới hạn
body. Đó là một sản phẩm riêng, và mọi lỗi trong nó nằm trên **đường đi của mọi
request**. Thứ đáng viết là **process supervisor** (5.5) - nhỏ hơn nhiều, nằm ngoài
đường request, và chính nó mới là thứ thay được K8s.

**Về "API giao tiếp với LB phía trước":** nginx bản mã nguồn mở **không có API động**
(module cấu hình upstream lúc chạy chỉ có ở nginx Plus). Nhưng hướng đẩy là hướng
ngược - nó buộc framework phải biết trước LB là ai và có credential gọi nó. Đổi
chiều thì framework không cần biết gì:

| Endpoint | Trả lời | Ai dùng |
|---|---|---|
| `/healthz` | *Tiến trình này còn sống không* | Supervisor. Chết thì **giết và dựng lại** |
| `/readyz` | *Nhận request mới được không* | LB. Không sẵn sàng thì **rút khỏi đàn, đừng giết** |

Gộp hai cái thành một là hỏng đúng lúc cần nhất - lúc tắt êm, ta muốn nói *"đừng gửi
request mới nhưng tôi vẫn sống và đang phục vụ nốt"*, và một endpoint không nói được
câu đó. Đúng [luật 03](../../../.claude/rules/03-mot-gia-tri-mot-nghia.md).

**Về co giãn trong khoảng `[x, y]`:** chủ dự án chốt **tạm gác, chưa làm**. Ba chỗ
khó ghi lại để lần sau khỏi đo lại: đo CPU thì sai vì app Xime **IO-bound** (chỉ số
đúng là độ trễ event loop hoặc độ dài hàng đợi) · tiến trình mới mất vài giây để
dựng DI và lấy cert nên phản ứng chậm hơn cơn tải · và **`y` bị chặn cứng từ phía
database**: `y × pool_size < max_connections` (Postgres mặc định **100**), 10 tiến
trình × 10 kết nối là hết sạch.

---

## 6. Bốn phép kiểm lúc khởi động

Cả bốn làm được **trong một tiến trình**, không cần phối hợp, vì mọi tiến trình đọc
cùng một file (xem 2.5).

| # | Kiểm | Kết cục |
|---|---|---|
| 1 | Không khối nào `primary: true`, hoặc có hai | **lỗi khởi động** |
| 2 | Tên điểm phục vụ có trong cấu hình mà `main.py` **không khai** | **lỗi** - chắc chắn gõ sai, vì cấu hình không tự sinh ra năng lực |
| 3 | Adapter khai trong `main.py` mà khối này **không có** | **bỏ qua im lặng** - đó là cách lọc, không phải lỗi |
| 4 | Điểm phục vụ **không nhân bản được** xuất hiện ở hai khối | **lỗi**, kèm lý do. Với MQTT sau khi tách `client_id` thì đổi thành: hai khối **trùng `client_id`** mới lỗi |

⭐ Phép kiểm 2 bắt được lỗi mà mô hình cũ không bắt được: gõ `web: publik` thay vì
`public` thì hôm nay là một server im lặng không có controller nào.

---

## 7. Ảnh hưởng tới `ke-hoach-0.8.md`

Cộng với file cache cùng buổi, **phần lớn bản kế hoạch đó không còn cần**:

| Thành phần trong 0.8 | Còn cần |
|---|---|
| Bus Manager · shared queue + mutex · `BusMessage` · transport abstraction · API `broadcast` | **Không** (chủ dự án vẫn muốn **giữ bus** nhưng với vai trò khác: chở **tín hiệu**, không chở dữ liệu - xem file cache mục 6) |
| DI scope `global` | **Không.** "Global" nay nghĩa là *chỉ khai ở tiến trình primary* |
| Worker 0 chết thì global singleton mất | **Không tồn tại** |
| Master spawn/giám sát/restart | Có, nhưng **nhỏ hơn nhiều** - không có trạng thái chung nào phải quản |
| HTTP routing tới worker | **Không.** Mỗi tiến trình một cổng |

> **Đề nghị: `ke-hoach-0.8.md` nên được VIẾT LẠI chứ không bổ sung.**

---

## 8. Đã bác bỏ, kèm lý do (đừng bàn lại)

| Đề xuất | Ai bác | Lý do |
|---|---|---|
| `uvicorn --workers N` | chủ dự án | Chỉ nhân bản ASGI app, **không thấy 5 adapter kia**. Xime không phải web framework thuần |
| `app.role("api")` trong main | phiên tự rút | Thừa: `Application()` đã là một tiến trình, `config_module` đã phân biệt được DI |
| `--id` như một cờ dòng lệnh riêng biệt | phiên tự rút | Nên là **đối số của `Application`**, không phải khái niệm song song |
| **Dùng cổng làm chốt chặn duy nhất id** | **chủ dự án** | *"Không phải lúc nào cũng cấp cổng"* - tiến trình chỉ chạy scheduler + MQTT không bind gì |
| **Khoá trong LMDB để chặn scheduler chạy hai bản** | **chủ dự án** | ⭐ *"Chắc gì trong mọi trường hợp cái LMDB đã chạy"*. Thành nguyên tắc: **một chốt chặn không được phụ thuộc thành phần TUỲ CHỌN** - nó sẽ vắng mặt đúng lúc cần nhất, và buộc phải trả lời một câu không có đáp án hay (LMDB chưa chạy thì cho qua hay chặn?) |
| `for i in list: app = Application(i)` trong main | phiên phản biện, chủ dự án chấp nhận đổi sang `share_load()` | Ba lỗi: **không sinh tiến trình nào** (tạo N object cùng tiến trình, biến bị ghi đè) · **không chạy gì** (`run()` chặn, không gọi N lần được) · ⭐ **nói sai mô hình thực thi** - người đọc tưởng N `Application` sống chung một tiến trình. Gốc: `Application(i)` mang **hai nghĩa** (*"tôi LÀ tiến trình này"* vs *"tôi KHAI RẰNG CÓ tiến trình này"*), đúng luật 03 ở tầng hàm khởi tạo |
| Người vận hành sửa `main.py` | phiên phản biện | `main.py` là **code**: không kiểm tra đầu vào (gõ sai ra traceback), đổi triển khai thành đổi code + commit + review, và ranh giới nhoè. Mà nguyên lý 2 vốn đã khiến họ **không cần** đụng vào |
| Khai danh sách **đơn nhất** (danh sách đen) | phiên đề nghị đảo | Quên khai một thứ → nó chạy ở mọi tiến trình → **nhân đôi → SAI**. Danh sách trắng thì quên khai → ở lại primary → **thừa, không sai** |

### Bổ sung chiều 2026-08-16

| Đề xuất | Ai bác | Lý do |
|---|---|---|
| **LMDB làm đệm ghi cho Postgres** (gom lô rồi commit) | **chủ dự án** | Cái giá thật không phải rủi ro mất dữ liệu (vá được bằng phục hồi lúc khởi động), mà là **mọi đường đọc về sau đều phải nhớ hỏi LMDB trước** - nghĩa vụ không cưỡng chế được, lan khắp code, người viết use case thứ bốn mươi sẽ quên. ⚠ Gặp lại bài toán này thì thứ tự đúng là: **đo** bằng `pg_stat_activity` + `pg_locks` (*"tranh nhau"* mang ba nghĩa khác nhau) → hết kết nối thì **pgbouncer** → ghi nhiều thì **gom lô trong bộ nhớ từng tiến trình + `COPY`**. LMDB chỉ cần khi phải gom **xuyên tiến trình**. Ghi chú thêm: LMDB chỉ cho **một writer mỗi environment**, nên N tiến trình cùng ghi là **dời chỗ tắc**, không xoá nó |
| **Framework tự viết bộ cân bằng tải** | phiên đề nghị gác, chủ dự án đồng ý bàn sau | LB layer 7 tử tế = TLS + HTTP/2 + keep-alive upstream + health check + graceful drain + chống slowloris. Một sản phẩm riêng, và mọi lỗi trong nó nằm trên **đường đi của mọi request** của 31 codebase. `SO_REUSEPORT` + nginx cùng máy lấy được cùng lợi ích mà không mất LMDB - xem 5.9 |
| **Entry point riêng cho tiến trình con** (`python -m xime._worker`) | phiên phản biện, chủ dự án chọn B | **Hai đường khởi động là hai chỗ để trôi lệch**, và loại lệch đó không có triệu chứng. Kèm ràng buộc mới: mọi đối số của `use()` phải serialize được. Bảng so sánh đầy đủ ở 5.6 |
| **Cha kết thúc sau khi sinh con** | phiên phản biện, chủ dự án chọn "ở lại" | Con chết thì **không ai dựng lại**; `Ctrl+C` không có chỗ điều phối thứ tự tắt; tắt êm cần một chỗ biết cả đàn. Xem 5.5 |
| **Cho MQTT đi qua bộ cân bằng tải** | phiên đính chính | **Sai chiều kết nối**: app MQTT là *client*, nó kết nối **ra** broker và **không mở cổng nào**, nên LB không có gì để cân. Lời giải ở **broker**: shared subscription MQTT 5. Xem 5.7 |
| **`--only api-2` làm cờ dòng lệnh** | phiên tự rút | Chạy bằng `python -m app.main` thì người vận hành không truyền đối số. Dùng **biến môi trường** `XIME_PROCESS_ID` do framework tự đặt khi sinh con; `argv` là chỗ ứng dụng có thể tự dùng |
| **Phơi `current_process_id()` cho code nghiệp vụ** | phiên tự chặn trước | Có nó thì sớm muộn có người viết `if process_id == "main"` trong use case, và N tiến trình chạy N nhánh code khác nhau - cùng hình dạng với thứ [luật 01](../../../.claude/rules/01-song-song-hoa-va-shard.md) mục 2 cấm với `org_id`. Phân biệt bằng **năng lực được cấp**, không bằng **tên** |
| ~~*"Supervisor thuần, KHÔNG mở cổng nào"*~~ | phiên tự sửa | Đúng lúc viết, sai sau khi chốt web chung cổng kiểu uvicorn - cha **phải** `bind()`. Phát biểu đúng ở 5.5: **giữ socket nhưng không phục vụ** (không bao giờ `accept()`). Giữ vết gạch vì bản đầu đã kịp vào tài liệu |
| ~~*"Unix socket: N tiến trình bắt buộc N path"*~~ | phiên đính chính | **Giả định sai.** Một listening socket `AF_UNIX` được nhiều tiến trình cùng `accept()` y hệt TCP. Chốt cuối là **mặc định tách, cho phép chung** - xem 5.7.2 |
| **Sinh con bằng `subprocess`** | phiên tự rút sau khi chốt cha giữ socket | `subprocess` không truyền được socket qua ranh giới tiến trình mà không tự dựng kênh. `multiprocessing` làm được cả hai OS **và** vẫn import lại `main.py`, nên giữ được nguyên lý 10 |
| **Tiến trình phụ không chạy `post_construct` nào cả** | phiên phản biện, chủ dự án gác lại | Cắt luôn thứ tiến trình phụ **cần để sống** (pool DB, key JWT). Phép cắt phải ở mức việc, không phải mức tiến trình - nhưng cũng **không cắt được ở mức class** vì hook đặt trên method. Chưa có lời giải, xem 2.9 |

---

## 9. Còn lại

### 9.0. Năm câu buổi sáng ĐÃ ĐÓNG trong buổi chiều

Ghi lại để không ai mở lại tưởng còn treo:

| Câu cũ | Đóng bằng |
|---|---|
| 4. `share_load()` sinh con bằng cách nào, ai giám sát | **Framework**, `spawn`, supervisor thuần không chết - 5.5 |
| 6. Windows có hỗ trợ nhiều tiến trình không | **Có.** Dùng `spawn` cả hai hệ điều hành, một đường chạy giống nhau - 5.6 |
| 7. Chọn đường a/b/c cho DI (mục 2.6) | **Đường a**: mọi tiến trình chung một `BindingConfig`, đúng ý *"chỉ 1 file cấu hình DI cho lập trình viên"* |
| 8. Id có mặt trước khi `dependency.py` chạy bằng cách nào | **Biến môi trường**: nó có sẵn từ lúc tiến trình khởi động, tức **trước mọi lệnh import**. Câu hỏi khó nhất buổi sáng tan biến, không phải được giải |
| 1. `primary` là khoá dành riêng hay tách tầng `servers:` | **Khoá dành riêng**, khai tường minh - 5.3 |

### 9.1. Ba chỗ chủ dự án để lại xem hôm sau

Phiên nêu cuối buổi chiều, chủ dự án: *"3 chỗ cần chốt tiếp thì để hôm sau tôi xem
lại tiếp vậy."*

| # | Câu hỏi | Ghi chú |
|---|---|---|
| A | **Scheduler: tách ĐĂNG KÝ job khỏi CHẠY vòng lặp lịch** | `config/scheduler.py` được import ở mọi tiến trình nên mọi tiến trình đều **khai** job - đúng nguyên lý DI đồng nhất. Nhưng chỉ primary được **chạy**. Hiện `SchedulerRunner` gộp cả hai |
| B | **Cổng của server phụ: `processes:` thắng đối số trong code, hay cấm hẳn đối số** | Hôm nay muốn hai gRPC phải truyền cổng thẳng trong code. Phiên nghiêng về **cấm hẳn, báo lúc khởi động**: hai nguồn cho cùng một giá trị là chỗ để lệch, và *người vận hành sửa YAML mà cổng không đổi* là loại bug tốn cả buổi |
| C | **Luật "code ở mức module phải nhẹ"** | Với `N` tiến trình, mọi thứ ngoài `if __name__` chạy `N+1` lần. `import config` rẻ vì chỉ ghi registry; nhưng `client = SomeClient(...)` ở mức module thành `N+1` kết nối và **không gì báo**. Nên là một dòng trong [`rules/`](../rules/), cạnh luật vòng lặp nền |

### 9.2. Còn mở

| # | Câu hỏi | Ghi chú |
|---|---|---|
| ⭐ | **`post_construct` ở tiến trình phụ** | **Câu khó nhất còn lại.** Chủ dự án gác lại để bàn kỹ. Vấn đề đã được nêu chính xác ở [2.9](#29--post_construct-cho-tiến-trình-phụ---tạm-gác-chưa-có-lời-giải) - đọc đó trước khi bàn tiếp, đừng dựng lại từ đầu |
| A | **Scheduler: tách ĐĂNG KÝ job khỏi CHẠY vòng lặp lịch** | Xem 9.1 |
| B | **Cổng server phụ: `processes:` thắng đối số code, hay cấm hẳn đối số** | Xem 9.1. Chốt web "cha giữ socket" làm câu này gấp hơn: `host`/`port` của web nay do **cha** quyết, con chỉ nhận fd - nên hai nguồn cho cùng một giá trị là chuyện chắc chắn xảy ra |
| C | **Luật "code ở mức module phải nhẹ"** | Xem 9.1 |
| 3 | ⚠ **Dải cổng trong `đăng kí mạng.md` có đủ không** | Base HTTP `8081-8099` = **19 cổng cho 9 service**. Chung cổng (5.7.1) làm câu này nhẹ hẳn: N tiến trình vẫn một dòng sổ. **Việc của workspace, không phải framework** |
| 5 | **Tiến trình primary chết thì cụm ở trạng thái nào** | Nhẹ hơn nhiều sau 2.8: supervisor **thăng cấp** một con đang chạy. Còn lại: trong lúc chưa thăng cấp xong, `/readyz` của phụ có nên báo không |
| D | **Bus liên tiến trình: thiết kế lại theo vai trò mới** | ✅ Chốt **dùng** nó cho lệnh điều khiển fieldbus, chủ dự án: *"bàn kỹ sau"*. Ba chỗ 0.8 chưa đủ + một chỗ đừng làm đã ghi ở 5.7.4b |
| F | **Supervisor trông TIẾN TRÌNH NGOÀI** (phiên đề xuất, chưa chốt) | Sinh ra từ câu hỏi MQTT broker: điều chủ dự án thực sự muốn là *"đừng bắt tôi cài và trông thêm một thứ"*. Supervisor đã sinh và trông tiến trình con rồi, cho nó trông cả `mosquitto` là **gần như miễn phí** - khai `external: { mosquitto: { command: ..., start_before: main } }`, framework không phải biết MQTT là gì. Dùng lại được cho mọi thứ cần sống cùng vòng đời app |
| E | **`@poll` / `@on_change` chạy một lần cho MỖI thực thể** | Hệ quả của hướng 3 (5.7.3): handler phải nhận thêm tham số biết mình đang xử lý máy nào. **Đổi chữ ký công khai của decorator**, gộp vào đợt đổi API ở mục 4 |
| 9 | Tên thống nhất cho đối số định danh của cả sáu adapter | Nay khó hơn: web/grpc/socket dùng **`server_id`** (điểm phục vụ), modbus/opcua dùng **loại thiết bị** - hai khái niệm khác nhau, có thể không nên ép cùng một tên |
| 10 | Đổi dứt khoát hay giữ hai đường (tương thích PyPI) | ✅ Chủ dự án chốt chiều 2026-08-16: *"nếu cần thì cứ thay đổi code framework thoải mái, **để code phục vụ thiết kế**"* → **đổi dứt khoát** |
| 11 | Hình dạng "hạng nhân bản là điều kiện" trông thế nào trên adapter | Liên quan 5.7. Nay có **ba** hạng chứ không hai: nhân bản · phân mảnh · đơn nhất |

**Câu 2 (cổng chung hay riêng) đã ĐÓNG chiều 2026-08-16** - xem 5.7.1: web và unix
socket dùng **cha giữ socket** (cả hai hệ điều hành), gRPC dùng **`SO_REUSEPORT`**
(Windows không hỗ trợ, báo lỗi lúc khởi động).

---

## 9b. Chia việc giữa 0.7.x và 0.8 (chốt 2026-08-16)

Bảng đầy đủ nằm ở [`../CLAUDE.md`](../CLAUDE.md) mục *"Việc đang chờ làm ở repo này"* -
đó là nơi phiên sau tra đầu tiên. Ở đây chỉ ghi **nguyên tắc và ba chỗ đáng chú ý**,
vì lý do quan trọng hơn danh sách.

### Nguyên tắc

> **0.7.x không đổi API công khai một dòng nào; mọi thay đổi API gom vào 0.8.**

Hệ quả trực tiếp của quyết định *"đổi dứt khoát, không giữ hai đường"*: đổi dứt khoát
**rải rác qua nhiều bản patch** là thứ tệ nhất cho 31 app dùng chung một cây mã
editable - mỗi bản là một lần cả 31 app phải sửa theo, mà chúng không có venv riêng.

### Ba chỗ đáng chú ý

**a. F10 chuyển từ 0.7.x sang 0.8.** Kế hoạch bảo mật xếp nó vào đợt 3, tức trước 0.8.
Nhưng chính tài liệu đó viết: *"Phải mở rộng protocol - **đây là đổi API cho mọi
adapter**, gồm cả adapter người dùng tự viết."* Mà đó đúng là mục 4.5 ở đây, và
**supervisor cũng cần chính tín hiệu ready đó** để biết khi nào con sẵn sàng. Làm ở
0.7.x là đổi API adapter **hai lần trong hai bản liên tiếp**.

**b. A1 thì ngược lại - đừng đợi 0.8.** Nó là lỗ hổng thật đang mở ở **19/21
codebase**, và `saas-foundation/template` nằm trong nhóm chưa vá nên **mọi app clone
từ nay đều thừa hưởng**. Quan trọng hơn: **đợt 1 không vá được nếu framework chưa có
keyset** - 21 repo đang tự viết `TrustJwtAuthMiddleware` vì `JwtMiddlewareConfig.key_context`
chỉ nhận đúng một khoá tĩnh. Nó là **nút chặn cho việc của người khác**, không chỉ
việc của framework.

> Giữ tương thích bằng cách **thêm đường keyset opt-in ở 0.7.x, để mặc định
> fail-closed sang 0.8**. Thêm API mới không phá ai; đổi mặc định thì có.

**c. MQTT không cần làm gì trước 0.8.** Cả ba việc ở 5.7.4 **chỉ có nghĩa khi đã có
nhiều tiến trình**. Làm sớm là xây nửa cây cầu: đổi API xong mà không có gì dùng nó,
rồi 0.8 lại đụng vào lần nữa. Và hôm nay chưa app nào dùng MQTT nên không ai đang
chịu thiệt.

### Quan sát: 0.8 đang phình

Tám nhóm việc, chia làm hai cụm rõ rệt:

| Cụm | Gồm | Chặn ai |
|---|---|---|
| **Hạ tầng nền** | mô hình chạy · cấu hình · đổi API adapter · kho liên tiến trình | Đủ để một app web/gRPC bình thường chạy nhiều tiến trình |
| **Hướng IoT-nhà máy** | fieldbus phân mảnh · MQTT chia topic · bus | **Không chặn ai** - hôm nay chưa app nào dùng Modbus/OPC UA/MQTT thật |

Đường cắt tự nhiên nằm giữa hai cụm, nếu muốn có thứ chạy được sớm. **Chưa quyết** -
ghi lại để lúc cần thì không phải phân tích lại.

---

## 10. Liên quan

- [`cache-lien-tien-trinh-2026-08-16.md`](cache-lien-tien-trinh-2026-08-16.md) - nửa
  đầu cùng buổi: nhóm 1 (shared memory), nhóm 2 (LMDB), lý do hoãn đa luồng.
- [`ke-hoach-0.8.md`](ke-hoach-0.8.md) - **nên viết lại**, xem mục 7.
- [`app-entry-point.md`](app-entry-point.md) - khuôn `main.py` hiện hành. Mục 5 ở
  đây là bản mở rộng của nó.
- [`ke-hoach-va-bao-mat-2026-08-01.md`](ke-hoach-va-bao-mat-2026-08-01.md) - **F10
  (cô lập adapter) trùng với mục 4.5**, làm một lần được cả hai.
- [`../rules/config-discovery.md`](../rules/config-discovery.md) - ranh giới hai
  tầng config, nền của mục 2.6.
- Luật 01 của workspace - hai hạng lịch chạy nền, dùng ở 3.6.
- Luật 03 của workspace - áp hai lần ở đây: `MqttAdapter` gộp `_server_id` với
  `client_id` (3.2), và `Application(i)` mang hai nghĩa (mục 8).
