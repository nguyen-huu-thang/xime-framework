# Code ở mức module phải nhẹ - luật nội bộ Xime Framework

> Lập **2026-08-19** khi chốt mô hình đa tiến trình của 0.8. Chủ dự án chốt đưa vào `rules/`.
>
> Đây là quy tắc **nội bộ repo này**, không phải luật cắt ngang workspace. Nhưng nó áp cho
> **code ứng dụng viết bằng Xime**, nên phải nói rõ trong tài liệu người dùng nữa.

## 1. Luật

> **Mọi thứ ngoài `if __name__ == "__main__":` chạy `N+1` lần khi app có `N` tiến trình.
> Code ở mức module chỉ được KHAI BÁO, không được LÀM.**

`N+1` chứ không phải `N`: tiến trình cha cũng chạy lại chính `main.py` (mô hình chốt ở
[`da-tien-trinh-main-va-cau-hinh-2026-08-16.md`](../docs/da-tien-trinh-main-va-cau-hinh-2026-08-16.md)
mục 5.5), rồi mới rẽ nhánh ở `share_load()`.

## 2. Vì sao nó thành luật, không phải lời khuyên

**a. Nó không có triệu chứng.** `client = SomeClient(...)` ở mức module thành `N+1` kết
nối, và **không gì báo**. Không lỗi, không log, không test đỏ. Chỉ là bốn kết nối tới
database thay vì một, và ai đó phát hiện sau vài tháng khi pool cạn.

**b. Hôm nay nó đúng, ngày mai nó sai - mà code không đổi.** App chạy một tiến trình thì
mọi thứ ở mức module chạy đúng một lần. Thêm một dòng `count: 3` vào `application.yml` là
cùng đoạn code đó chạy bốn lần. **Thứ đổi nằm ở file cấu hình, không nằm ở file có lỗi.**

**c. Cha gánh nó mà không dùng.** Cha **không dựng DI, không chạy code nghiệp vụ**, nhưng
nó vẫn chạy hết code mức module. Đo 2026-08-19: cây import của một app điển hình
(`Application` + web + grpc + sqlalchemy) là **83 MB RSS, 721 module**. Thêm một kết nối
mở ở mức module là cha giữ một kết nối nó không bao giờ dùng.

## 3. Được làm gì, không được làm gì

| Ở mức module | |
|---|---|
| `import config` | ✅ Được - nó chỉ ghi vào registry |
| `app = Application()` | ✅ Được - object rỗng, chưa mở gì |
| `app.add_config(config)` | ✅ Được |
| `app.use(WebAdapter())` | ✅ Được - dựng object adapter, **chưa** `start()`, chưa chiếm cổng |
| Khai class, hằng số, kiểu dữ liệu | ✅ Được |
| **Mở kết nối** (DB, Redis, MQTT, gRPC channel, HTTP session) | ⛔ Không |
| **Đọc/ghi file**, mở `shared_memory`, mở LMDB | ⛔ Không |
| **Gọi mạng** (lấy cert, lấy khoá, gọi API) | ⛔ Không |
| **Sinh giá trị không tất định** (`uuid4()`, `time.time()`, `random`) | ⛔ Không - xem 3.1 |
| Tính toán nặng, dựng bảng lớn trong bộ nhớ | ⛔ Không |

### 3.1. ⚠ Giá trị không tất định hỏng theo kiểu khác, và tệ hơn

Kết nối mở ở mức module thì **thừa** - tốn tài nguyên, nhưng mọi tiến trình đều đúng.

Một `uuid4()` ở mức module thì **mỗi tiến trình có một giá trị KHÁC NHAU**, trong khi code
đọc nó tin rằng cả cụm dùng chung một giá trị. Đó không phải lãng phí, đó là **sai**.

```python
INSTANCE_ID = uuid4()          # ⛔ bốn tiến trình, bốn id, không ai biết
STARTED_AT  = time.time()      # ⛔ bốn mốc khác nhau
```

⭐ Đây là cùng khuôn với `hash()` ở [kho nhóm 2](../docs/kho-nhom-2-store-2026-08-19.md):
Python ngẫu nhiên hoá `hash()` cho mỗi tiến trình, nên chia file theo `hash(key)` hỏng
**hoàn toàn im lặng**. Cả hai đều là *giá trị trông như hằng số nhưng không phải*.

## 4. Hai phép dò

Luật này không tự giữ được - phải có thứ kêu.

### 4.1. `share_load()` đo thời gian từ lúc import

`share_load()` là điểm đầu tiên framework giành lại quyền điều khiển sau khi code mức
module chạy xong. Nó ghi mốc lúc `xime` được import lần đầu, rồi so:

```text
[CẢNH BÁO] Code ở mức module chạy mất 2,4 giây trước khi tới share_load().
           Thời gian này nhân với số tiến trình. Xem rules/module-level-code.md
```

Bắt được cả ba nhóm nặng nhất (kết nối, đọc file, gọi mạng) mà **không cần biết chúng là
gì** - chỉ cần biết chúng chậm.

⚠ Giới hạn phải khai: một kết nối tới `localhost` có thể mất **vài mili giây**, nằm dưới
mọi ngưỡng hợp lý. Phép dò này bắt cái đắt, không bắt cái sai.

### 4.2. Quét tĩnh hàm không tất định ở mức module

Bù đúng chỗ 4.1 mù. Quét AST của `main.py` và các module nó import ở mức module, tìm lời
gọi `uuid4`, `time.time`, `random.*`, `datetime.now` **ở thân module** (không phải trong
hàm hay class body).

⚠ **Đây là phép dò theo danh sách tên, nên con số 0 của nó không chứng minh được gì** -
đúng bài học đã ghi ở CLAUDE.md workspace về phép quét secret. Nó bắt được bốn cái tên
phổ biến, không bắt được `secrets.token_hex()` hay một hàm tự viết gọi vào chúng.

⭐ Vì vậy **hai phép dò không thay thế nhau**: một cái đo *hậu quả* (chậm) mà không biết
nguyên nhân, một cái tìm *nguyên nhân* theo tên mà không thấy hậu quả. Bỏ cái nào cũng
thủng theo hướng riêng.

## 5. Ranh giới: luật này KHÔNG cấm app có trạng thái toàn cục

Nó cấm **làm việc** ở mức module, không cấm **khai báo**. Một registry rỗng, một dict hằng
số, một class - tất cả đều ổn, vì mỗi tiến trình dựng lại chúng giống hệt nhau.

> Câu để tự kiểm: **nếu dòng này chạy bốn lần thay vì một, có gì hỏng hoặc lãng phí
> không?** Không thì để yên.

## 6. Liên quan

- [`background-tasks.md`](background-tasks.md) - cùng họ: thứ trông vô hại ở một tiến
  trình, hỏng khi có tiến trình thứ hai hoặc khi thời gian vào cuộc.
- [`../docs/da-tien-trinh-main-va-cau-hinh-2026-08-16.md`](../docs/da-tien-trinh-main-va-cau-hinh-2026-08-16.md)
  mục 5.5 (mô hình chạy, vì sao là `N+1`) và 5.5b (số đo 83 MB).
- [Luật 01 của workspace](../../../.claude/rules/01-song-song-hoa-va-shard.md) nghĩa 1 -
  *mọi trạng thái phải ra khỏi bộ nhớ tiến trình*. Luật này là một mảnh cụ thể của nó,
  ở đúng chỗ trạng thái hay lọt vào mà không ai để ý.
