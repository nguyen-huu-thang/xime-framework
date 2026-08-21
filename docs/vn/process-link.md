# Bus liên tiến trình (ProcessLink)

[English](../en/process-link.md) | **Tiếng Việt**

[← RefData](refdata.md) · **ProcessLink** · [Đa tiến trình →](multi-process.md)

---

Khi một ứng dụng chạy nhiều tiến trình, có những việc không giải được bằng dữ
liệu dùng chung. Ví dụ điển hình: người dùng bấm *"dừng băng tải BT-02"* trên
web, request rơi vào tiến trình `main`, nhưng dây Modbus tới BT-02 nằm ở tiến
trình `line-2`. Đó là một **lệnh**, không phải một mẩu dữ liệu - ghi nó vào
database không làm băng tải dừng.

`ProcessLink` chở những thứ đó: **tín hiệu, lệnh và câu hỏi** giữa các tiến
trình của cùng một ứng dụng, trên cùng một máy.

---

## ⚠ Nó KHÔNG phải `EventBus`

Đây là chỗ dễ nhầm nhất, và nhầm thì **không có triệu chứng**: tin không bao giờ
ra khỏi tiến trình, không lỗi, không log.

| | `EventBus` (`xime.core.event`) | **`ProcessLink`** |
|---|---|---|
| Phạm vi | trong **MỘT** tiến trình | **GIỮA** các tiến trình |
| Chở gì | object Python, không serialize | **bytes** |
| Chở loại gì | **event** - đã xảy ra rồi, ai quan tâm thì nghe | **lệnh và câu hỏi** - có đích, có thể chờ trả lời |
| Phản hồi | không có | **có** (`ask`) |
| Handler chạy | song song (`create_task`) | **tuần tự theo kênh** |
| Đăng ký | `subscribe(Type, handler)` | `@on_announce` / `@on_request` |

Tên cố ý không chung gốc từ: `link.ask(...)` và `event_bus.publish(...)` không
thể gõ nhầm thành nhau.

> **Ranh giới thực dụng: thứ 4 KB không đủ chứa thì đó là DỮ LIỆU, không phải
> tín hiệu.** Dữ liệu đi qua [Store](store.md) hoặc database; bus chở tín hiệu.

---

## Khai kênh và handler

```python
# config/link.py
from xime.core.link import ChannelSpec, configure_link

from app.link.fieldbus import FieldbusHandler

configure_link(
    channels={
        "fieldbus": ChannelSpec(rows=256, payload_bytes=512),
        "cauhinh":  ChannelSpec(rows=64,  payload_bytes=4096),
    },
    handlers=[FieldbusHandler],
)
```

```python
# app/link/fieldbus.py
from xime.core.link import on_announce, on_request


class FieldbusHandler:
    def __init__(self, modbus: ModbusClient, cfg: RuntimeConfig) -> None:
        self._modbus = modbus
        self._mine = cfg.get("...")          # khoá đến từ CẤU HÌNH

    @on_request("fieldbus")
    async def control(self, key: str, payload: bytes) -> bytes | None:
        if key not in self._mine:
            return None                      # chưa hề chạm vào payload
        await self._modbus.write(..., device=key)
        return b"ok"

    @on_announce("cauhinh")
    async def config_changed(self, key: str, payload: bytes) -> None:
        ...
```

Bốn chi tiết cố ý:

| | |
|---|---|
| **`handlers=` nhận CLASS** | Framework lấy instance từ DI nên handler được inject bình thường. Cùng khuôn `configure_jwt(key_provider=...)` |
| **Khai kênh và khai handler tách nhau** | Một handler phục vụ nhiều kênh được, và một kênh có thể chỉ để **gửi** |
| **`channels` giống nhau ở mọi tiến trình** | Vùng nhớ là chung. Tự đúng nhờ `config/` được import y hệt ở mọi tiến trình, nhưng framework vẫn kiểm lại lúc attach |
| **Kích thước khai bằng Python, không phải YAML** | Chọn số dòng và cỡ payload đòi biết *handler chạy bao lâu* và *tin to cỡ nào* - hai thứ người vận hành không biết |

---

## Ba phép gửi

Phân theo **người gửi cần biết gì**, không phải theo bao nhiêu người nhận.

```python
await link.announce("cauhinh", payload=b"khoa vua xoay")        # phát cho mọi người
await link.send("fieldbus", key="BT-01", payload=b"stop")       # có đích, không chờ
result = await link.ask("fieldbus", key="BT-01", payload=b"stop", timeout=2.0)
```

### Bốn kết cục của `ask`

```python
match await link.ask("fieldbus", key="BT-01", payload=b"stop"):
    case Done(value):    ...   # handler đã nhận và trả lời
    case NoOwner():      ...   # KHÔNG ai nhận -> lỗi CẤU HÌNH, đừng thử lại
    case NoAnswer():     ...   # có đích nhưng quá hạn -> xem tiến trình kia còn sống không
    case Failed(detail): ...   # có người nhận và người đó HỎNG -> lỗi nghiệp vụ
```

Bốn tình huống khiến người gọi làm **bốn việc khác nhau**, nên chúng phải là bốn
giá trị. Gộp `Failed` vào `NoAnswer` là nói *"không ai trả lời"* về một ca **đã
có người trả lời**, và người vận hành sẽ đi sửa nhầm chỗ.

⚠ **`Done` nghĩa là "handler đã nhận và trả lời", KHÔNG nhất thiết là "việc đã
làm xong".** Handler nhét vào hàng đợi rồi trả `b"da nhan"` thì `Done` mang
nghĩa *đã nhận*. Ngữ nghĩa đó do ứng dụng định nghĩa; framework không hứa hộ.

---

## Định tuyến: kênh + khoá, lọc ở bên nhận

> Người gửi khai *"gửi trên kênh `fieldbus`, dành cho `BT-01`"*.
> Nó **không bao giờ** khai *"gửi tới tiến trình `line-2`"*.

Không có tên tiến trình ở bất cứ đâu, vì có tên tiến trình trong tay thì sớm
muộn sẽ có người viết `if process_id == "main"` trong use case - và từ đó dời
một dây Modbus sang tiến trình khác thành **sửa code** thay vì sửa cấu hình.

**`key` nằm ở header nên bên nhận lọc mà chưa chạm payload.** Ba tiến trình
không liên quan bỏ qua tin **không tốn một lần giải mã nào**.

**Trả `None` chính là cách nói "không phải của tôi"**:

| Handler trả | Framework làm |
|---|---|
| `None` | chỉ hạ bit, **không** ghi người nhận |
| `bytes` | ghi người nhận, và gửi câu trả lời nếu đây là `ask` |

Không ai trả khác `None` cho tới lúc người hỏi hết giờ thì kết cục là `NoOwner`.
Cơ chế bốn kết cục chạy mà không cần thêm khái niệm nào.

---

## Handler chạy TUẦN TỰ theo kênh

```text
mỗi KÊNH  = một vòng xử lý riêng, tin trong kênh chạy tuần tự
các kênh  = độc lập, song song với nhau
```

Đây không phải hạn chế, đây là **lý do tồn tại** của cả cơ chế: một tiến trình
gửi `bật` rồi `tắt` rồi `bật`, mà ba tin đó chạy song song, thì trạng thái cuối
là *cái nào thắng cuộc đua* chứ không phải cái đến sau cùng.

Hai hệ quả phải chấp nhận:

- **Một handler chậm chặn kênh của nó.** Đó là cái giá của thứ tự, và nó đúng:
  lệnh sau không nên chạy trước khi lệnh trước xong.
- **Muốn song song thì tách KÊNH, không phải tách task.** Kênh là đơn vị thứ tự.

> ⚠ **Handler phải nhanh.** Việc lâu thì nhét vào hàng đợi của ứng dụng rồi trả
> về ngay. Handler còn đang chạy lúc người hỏi hết giờ sẽ khiến người hỏi nhận
> `NoOwner` (*"sửa cấu hình"*) trong khi sự thật là *"tiến trình kia đang bận"* -
> framework cố ý không vá chuyện đó bằng cơ chế, vì mọi cách vá đều làm hỏng
> `NoOwner`, kết cục quan trọng nhất trong bốn cái.

---

## Mất tin: at-most-once, và bảng đầy thì đè

Bus **không** đảm bảo giao tuyệt đối, và đó là lựa chọn có ý thức:

| | Chết giữa chừng thì | |
|---|---|---|
| Hạ bit **trước**, rồi làm | tin **mất** | ✅ đã chọn: **at-most-once** |
| Làm xong **rồi** mới hạ | khởi động lại **làm lại lần nữa** | at-least-once |

Ứng dụng nào cần chắc thì **tự thêm một hàng đợi bền vững**: handler chỉ nhét
vào hàng đợi rồi trả về ngay, phần bền vững là việc của ứng dụng.

Khi vùng ghi đầy, người gửi **vòng về đầu và đè lên dòng cũ nhất**, bất kể còn
ai chưa đọc - nhưng trước khi đè, nó **đếm cho những người chưa kịp đọc**
(`missed` trong `stats()`).

⭐ Nhờ vậy **một tiến trình treo tự chịu hậu quả**, không nghẽn ai. Nếu chọn
*"chờ mọi người đọc xong mới xoá"* thì nó giữ chỗ mãi và cả nhà tắc.

> ⚠ Trên một bus chở tín hiệu, **bảng đầy là TRIỆU CHỨNG, không phải vấn đề kích
> thước**: tin ở đây thưa, nên đầy gần như chắc chắn nghĩa là có một tiến trình
> đã treo. Tìm nó trước khi nâng `ChannelSpec.rows`.

---

## Quan sát

```python
stats = link.stats()
for channel in stats.channels:
    print(channel.name, channel.rows_used, "/", channel.rows_total)
    print("  cũ nhất:", channel.oldest_unread_age_ms, "ms")
    for reader in channel.readers:
        print(f"  tiến trình {reader.process_index}: "
              f"chưa đọc {reader.unread}, đã lỡ {reader.missed}")
```

⭐ **`stats()` trả về số liệu của CẢ CỤM**, không chỉ tiến trình gọi - bitmap nằm
trong bộ nhớ chung nên ai cũng đọc được số của mọi người. Một endpoint sức khoẻ
ở tiến trình web trả lời được tình trạng của cả đàn, kể cả tiến trình không mở
cổng nào.

⚠ Ba điều phải nhớ:

- **Nó là ảnh chụp GẦN ĐÚNG**, không giữ khoá. Đừng dùng làm chốt chặn logic -
  `if stats.rows_used == 0:` sẽ sai đúng một lần trong một nghìn lần.
- **`missed` tích luỹ, không reset.** Muốn biết *"năm phút qua mất bao nhiêu"*
  thì tự lấy hiệu hai lần đọc.
- **`dump(channel)` là công cụ GỠ LỖI**, tách riêng có lý do: nó chở toàn bộ
  payload ra ngoài, đừng gọi nó mỗi mười giây trong một endpoint sức khoẻ.

Framework cũng **tự kêu**, không đợi ai hỏi: đè lên dòng chưa đọc, handler chạy
quá năm giây, bảng đầy quá 80% - đều có `WARNING` **có hãm nhịp**.

---

## Xử lý lỗi

| Ca | Framework làm |
|---|---|
| Handler của `@on_request` ném lỗi | bắt, gửi cờ lỗi -> người hỏi nhận **`Failed`** |
| Handler của `@on_announce` ném lỗi | **log rồi đi tiếp** - không có ai chờ |
| Handler treo | **không huỷ**, chỉ log cảnh báo |
| Payload vượt trần | **nổ ngay lúc gửi** |

`Failed.detail` mang tên lớp lỗi cộng thông điệp, cắt cứng 200 byte. **Không chở
traceback**: người hỏi ở tiến trình khác không debug được bằng traceback của
tiến trình kia - họ không có ngữ cảnh, không có biến. Traceback đầy đủ được log
**tại tiến trình bị lỗi**, nơi có đủ mọi thứ.

Payload vượt trần **nổ** chứ không trả về một kết cục, vì đó là **bug của người
viết ứng dụng**, không phải trạng thái lúc chạy - trả về một kết cục là mời
người ta `except` rồi bỏ qua.

Handler treo **không bị huỷ**: một handler đang ghi giữa chừng xuống Modbus mà
bị huỷ ngang sẽ để lại thiết bị ở trạng thái không ai thiết kế cho.

---

## Giới hạn phải biết

| | |
|---|---|
| **Một máy** | Bộ nhớ chung không bắc qua hai máy. Nhiều máy đã giải bằng chia shard |
| **Một luồng mỗi tiến trình** | Đơn vị của bus là **tiến trình**. `N > 1` luồng không đòi đổi cấu trúc chia sẻ, chỉ thêm một tầng phân phối bên trong tiến trình |
| **Không đảm bảo giao** | Xem mục trên. Tin chỉ mất khi tiến trình đích chết - mà nó chết thì cũng đang giữ kết nối tới thiết bị, nên không đường phần mềm nào cứu được lệnh đó. Fail-safe nằm ở watchdog của thiết bị |
| **Payload là bytes thô** | Framework không giải mã, không có sổ đăng ký kiểu. ⛔ Và **đừng dùng `pickle`**: payload đến từ tiến trình khác, `pickle` là thực thi mã tuỳ ý |

---

## Liên quan

- [Store](store.md) - kho liên tiến trình, cho **dữ liệu**; bus cho **tín hiệu**
- [Starters](starters.md) - `EventBus` nằm ở core, xem mục so sánh đầu trang

---

[← RefData](refdata.md) · **ProcessLink** · [Đa tiến trình →](multi-process.md)
