# Đặc tính Python, so với Java, và Xime đứng ở đâu giữa các framework cùng họ

> | | |
> |---|---|
> | **Trạng thái** | **ĐANG DÙNG** - đo 2026-08-25 trên máy Linux của chủ dự án |
> | **Loại** | Ghi chép: *học được gì*, không phải *có gì hỏng* |
> | **Đo lại được** | `python .claude/scripts/do_bien_c_python.py` (mục 1) · `.claude/scripts/benchmark/` (mục 2) |
> | **Bị thay bởi** | Chưa. Số thì lỗi thời theo máy; **ba quy luật** ở mục 1, 3, 4 thì không |
>
> ⚠ **Luật đọc file này:** mỗi con số đều dán nhãn **ĐO** hay **ƯỚC LƯỢNG**. Máy này không
> có JVM (`java: không tìm thấy lệnh`, không `mvn`, không `~/.m2`), nên **mọi con số Java
> trong file là ước lượng**, không phải phép đo. Đừng trích chúng như đã đo.

## 0. Ba câu trả lời, đọc cái này là đủ

| Câu hỏi | Trả lời |
|---|---|
| *"Code Python ngắn nên bên trong đã là C, chắc nhanh?"* | **Sai theo hướng ngược lại.** Dạng "ngắn" (`model_validate`, `json.dumps`) **chậm hơn** dạng viết tay 1,5-3,4x. Quy luật thật ở mục 1 |
| *"Spring Boot nhanh hơn Xime bao nhiêu?"* | **Tuỳ N**, không tuỳ cách viết code: chạm vài bản ghi thì **4-5x**, chạm hàng nghìn bản ghi thì **10-80x** (ước lượng) |
| *"Framework có bị nhét khái niệm riêng của Xime Platform vào không?"* | **Không, ở tầng code: 0 lần.** Đo ở mục 3 |

## 1. ⭐ Quy luật vượt biên Python ↔ C/Rust

### Số đo

Ba cặp, mỗi cặp **hai vế cho ra kết quả bằng nhau** (có `assert` canh trong script), 1000 bản ghi:

| Việc | dạng "ngắn" (C/Rust) | dạng viết dài (bytecode) | |
|---|---|---|---|
| Kiểm hợp lệ + dựng object | Pydantic **793 ns** | viết tay **230 ns** | **C chậm hơn 3,4x** |
| Tuần tự hoá JSON (cùng thoát ký tự) | `json.dumps` **372 ns** | ghép f-string **245 ns** | C chậm hơn 1,5x |
| Tổng hợp một cột | `sum(map(itemgetter))` **16 ns** | `sum(genexpr)` **23 ns** | **C nhanh hơn 1,4x** |

*(dao động vài phần trăm giữa các lượt; chạy lại bằng script ở khối trạng thái)*

### Quy luật

> **Thư viện C/Rust chỉ có lãi khi VÒNG LẶP NẰM BÊN TRONG nó.** Gọi nó một lần mỗi phần tử
> thì chi phí qua biên cộng chi phí dựng object Python **ăn hết** phần tiết kiệm được - và
> ăn nhiều hơn.

Ba dòng trên chỉ khác nhau ở đúng chỗ đó:

| | Vượt biên | Kết quả |
|---|---|---|
| `sum(map(itemgetter(...), rows))` | **một lần** cho 1000 bản ghi | thắng |
| `json.dumps(rows)` | một lần, **nhưng vẫn phải sinh chuỗi Python** | hoà tới thua nhẹ |
| `[Model.model_validate(d) for d in rows]` | **1000 lần**, mỗi lần dựng một object Python | **thua đậm** |

⚠ **Đây KHÔNG phải "Pydantic chậm".** 793 ns mua cho bạn ép kiểu, model lồng nhau, thông
báo lỗi dùng được. Bản viết tay 230 ns không có gì trong số đó. Bài học đúng là: **dạng
tiện luôn có giá, và giá đó tính trên MỖI bản ghi.**

### ⭐⭐ Bản đo đầu tiên SAI, và cái sai đó là bài học chính

Lượt đo đầu cho ra `model_validate` chậm hơn bản tay **10 lần** và `json.dumps` chậm hơn
ghép chuỗi tay. Con số trông hợp lý, kết luận thì vô hiệu: **hai vế làm hai lượng việc khác
nhau** - vế "C" còn thoát ký tự và còn dựng object, vế "tay" thì không.

> Cùng khuôn với luật của `scripts/benchmark/`: *một phép đo phải tự khai nó đo được cái
> gì*. Ở đây nó khai bằng cách **so hai hàm cho ra kết quả bằng nhau**, và `assert` nằm
> ngay trong script để không ai sửa mất tính chất đó.

Đây là **lần thứ ba trong một ngày** cùng một họ lỗi xuất hiện: cửa sổ đo CPU cố định ·
danh sách pid lấy quá sớm · và cặp so sánh lệch việc. Cả ba đều cho ra **con số trông đúng**.

### Hệ quả dùng được ngay

> **Đừng lặp trên hàng nghìn bản ghi trong Python.** Đẩy lọc, tổng, nhóm xuống SQL rồi chỉ
> nhận về vài chục dòng để định dạng.

## 2. So với Java / Spring Boot - ước lượng, chưa đo

### Nền: một request tiêu bao nhiêu, trước khi chạm code nghiệp vụ

**ĐO** trên máy này, tách từ ba dòng cùng một lượt benchmark:

| Lớp | µs/request | Lớp đó tự tốn |
|---|---|---|
| ASGI trần | 100,3 | 100,3 |
| + FastAPI | 157,6 | +57,3 |
| + Xime WebAdapter | **237,5** | +79,9 |

**ƯỚC LƯỢNG** cho một `@RestController` tầm thường: **40-65 µs**.

### DI không tốn gì mỗi request - ở cả hai bên

Cả Spring lẫn Xime dựng đồ thị **một lần lúc khởi động** (`rules/coding.md`: *"chỉ có MỘT
scope: singleton, dựng eager"*). **ĐO**: `DI: get()` = **12,5 triệu op/s ≈ 80 ns**, tức
**0,03%** của một request. Thêm tầng, thêm binding, không đổi gì.

### Tỉ lệ phụ thuộc N, không phụ thuộc cách viết code

| | Java | Python | tỉ lệ |
|---|---|---|---|
| 5 tầng chuyển tiếp thuần | ~0 (JIT nội tuyến) | ~0,3-1 µs | **không đáng kể ở cả hai** |
| Dựng + kiểm một bản ghi | ~10-30 ns *(ước lượng)* | **230 ns** (tay) / **793 ns** (Pydantic) | **10-30x** / **30-80x** |

| Kịch bản | tỉ lệ ước lượng |
|---|---|
| Request chạm **vài** bản ghi | **4-5x** - hạ tầng 237 µs áp đảo, nghiệp vụ chìm nghỉm |
| Request chạm **hàng nghìn** bản ghi | **10-80x** - nghiệp vụ áp đảo ngược lại |
| Request **chờ I/O** (DB, HTTP, hàng đợi) | **~1x** - cả hai đứng chờ như nhau |

⭐ Chỗ phản trực giác đáng nhớ: **với Xime, hạ tầng đắt tới mức code nghiệp vụ gần như miễn
phí so với nó; với Spring thì ngược lại.** Nên thêm tầng và thêm logic làm **Spring xấu đi
nhanh hơn** về mặt tương đối - chỉ không đủ để lật kết quả.

Dòng cuối bảng trên là lý do phân công ngôn ngữ của workspace (Java cho *transaction-heavy*,
Python cho *IO-bound*) là một quyết định đúng chứ không phải một thoả hiệp.

### Chi phí lắp ghép - **ĐO**

| | |
|---|---|
| `Trust/pom.xml` | **336 dòng**, khai **26** dependency |
| Jar thực sự trong fat jar | **136** |
| Xime | **4** phụ thuộc bắt buộc (`fastapi`, `starlette`, `pydantic`, `pyyaml`) + 15 extra tự chọn |

## 3. ⭐ Nguyên tắc "không phụ thuộc khái niệm ngoài" có giữ được không

`ghi-chep/go-phu-thuoc-khai-niem.md` ghi nguyên văn lời chủ dự án ngày 2026-08-17:

> *"Framework làm ra để nhiều người khác dùng nữa, và không liên quan gì tới các dự án kia
> của tôi, nên framework không được phụ thuộc gì khái niệm ngoài cả."*

**Đo lại tám ngày sau**, quét `xime/` tìm `Trust`, `shard_id`, `org_id`, `tenant`,
`identity_id`, `ksuid`:

```text
26 lần khớp - TẤT CẢ nằm trong docstring hoặc ví dụ
             ("e.g. clients/trust", "trust: host: trust.internal")
 0 lần trong mã thực thi
```

`shard_id` và `org_id` - hai thứ thấm vào 19 codebase app - **không xuất hiện lấy một lần**.
Nguyên tắc giữ được.

### ⚠ Nhưng có một dạng "làm cho chính mình" tinh vi hơn, và dạng đó thì CÓ

Nó không nằm ở **khái niệm**, mà ở **hình dạng triển khai**.

Bốn thứ lớn nhất của `0.8` - `share_load()`, `RefData`, `ProcessLink`, `Store` LMDB - đều
**chỉ có nghĩa trong phạm vi một máy**. Chúng giải đúng ràng buộc của chủ dự án: *nhiều tiến
trình trên hai VPS nhỏ, RAM là nút thắt, không muốn dựng Redis*.

Người triển khai trên Kubernetes với N pod thì **cả bốn vô dụng** - pod không chia sẻ bộ
nhớ, họ vẫn phải dùng Redis. Mà đó là hình dạng triển khai phổ biến nhất hiện nay.

> Nguyên tắc hiện hành cấm **rò khái niệm**. Nó không nói gì về **rò ràng buộc hạ tầng**, và
> thứ hai khó thấy hơn nhiều vì nó trông y hệt một tính năng kỹ thuật trung lập.

📌 Ghi ra đây làm câu hỏi mở, **không đề xuất đổi gì**: `RefData`/`ProcessLink` là lựa chọn
có ý thức và đúng với người dùng đầu tiên của framework. Chỉ cần biết rằng phần đắt nhất của
`0.8` phục vụ một nhóm hẹp hơn phần còn lại.

## 4. Vị trí giữa các framework Python cùng họ

**ĐO** - tra PyPI ngày 2026-08-25:

| Framework | DI có sẵn | Giao thức phục vụ | Bản mới nhất | Phát hành | Số bản |
|---|---|---|---|---|---|
| **Xime** | ✅ tự viết, eager | **HTTP · WS · gRPC · socket · MQTT · Modbus · OPC UA** | `0.8.1` | 2026-08-22 | **15** |
| Litestar | ✅ phân tầng | HTTP · WS | `2.24.0` | 2026-06-11 | 65 |
| Ellar | ✅ kiểu NestJS | HTTP · WS | `0.9.5` | **2026-01-01** | 62 |
| BlackSheep | ✅ | HTTP · WS | `2.6.3` | 2026-06-04 | 108 |
| FastStream | ✅ | **Kafka · RabbitMQ · NATS · Redis** (không có HTTP server) | `0.7.4` | 2026-08-07 | 123 |
| **Nameko** | ✅ | HTTP · RPC/AMQP · timer · event | `2.14.1` | ⛔ **2021-12-05** | 110 |
| FastAPI | ⚠ chỉ theo request | HTTP · WS | `0.141.1` | 2026-07-29 | 317 |
| Django | ❌ | HTTP · WS | `6.1` | 2026-08-05 | 441 |
| `dependency-injector` | ✅ chỉ làm DI | - | `4.49.1` | 2026-06-18 | **262** |

### ⭐⭐ Nameko chết từ 2021, và đó là dữ kiện quý nhất trong bảng

Nameko làm **đúng thứ Xime đang làm**: một service, nhiều cửa vào, chung một cơ chế tiêm phụ
thuộc. Nó có người dùng thật. Rồi tắt.

Nó cắt hai chiều, và cả hai đều đáng nhớ:

| | |
|---|---|
| **Xấu** | Hốc này đã có người vào và **không sống nổi** |
| **Tốt** | Lý do chết khá rõ và Xime **không dính**: Nameko đồng bộ (`eventlet`, sinh trước kỷ nguyên `async`), **buộc chặt vào RabbitMQ**, ra đời trước khi gRPC phổ biến |

> **Bài học, và nó nối thẳng với mục 3:** hốc "một service nhiều giao thức" có thật nhưng
> mong manh. Nameko chết không phải vì ý tưởng sai, mà vì **lệ thuộc vào một lựa chọn hạ
> tầng cụ thể**. Đừng để `RefData`/`ProcessLink` (chỉ chạy một máy) thành `eventlet` của Xime.

### Đối thủ trực diện nhất là FastStream, không phải Litestar

FastStream bán đúng câu chuyện *"nhiều giao thức, một DI"* - chỉ khác là giao thức của nó là
**message broker** chứ không phải **thiết bị**. Ranh giới rất sạch:

| | FastStream | Xime |
|---|---|---|
| Nói chuyện với **hệ thống khác** | Kafka, RabbitMQ, NATS, Redis | MQTT, gRPC |
| Nói chuyện với **thiết bị** | ❌ | **Modbus TCP, OPC UA** |
| Phục vụ **người** | ❌ phải ghép FastAPI | ✅ có sẵn |

**Không framework Python nào trong bảng nói chuyện được với thiết bị công nghiệp.** Đó không
phải "Xime hơn ở điểm này" - đó là một ô trống không ai đứng.

### Bản đồ gọn

```text
API HTTP thuần            -> FastAPI (don gian) hoac Litestar (nhanh, day du)
DI thuan                  -> dependency-injector / wireup / svcs
Message broker            -> FastStream
Full-stack + ORM + admin  -> Django
THIET BI + NGUOI + SERVICE, cung mot DI  -> khong ai
                                            ^ cho nay
```

⚠ Hai rào cản có thật ở phía Python, ghi để đừng ngạc nhiên về sau:

1. **Cộng đồng Python có phản xạ chống framework nặng.** Ellar - nỗ lực làm "NestJS cho
   Python", tức gần nhất với "Spring cho Python" - sau **62 bản vẫn chưa tới 1.0** và im
   lặng từ tháng 1.
2. **15 bản so với 65/108/123 của nhóm cùng lứa.** Với người ngoài, con số đó đọc là *"tác
   giả nghỉ thì tôi ôm gì"* - và không cãi được bằng chất lượng code.

## 5. Ba con số về chính Xime, và một lỗ hổng

**ĐO** ngày 2026-08-25:

| | |
|---|---|
| Tên công khai trong `__all__` | **309** |
| Phụ thuộc bắt buộc | **4** |
| Khái niệm nền tảng Xime trong mã thực thi | **0** |
| **File trong `xime/` nhắc tới tracing/metrics** | **1** |

Dòng cuối là **rào cản đưa vào production lớn nhất với người ngoài, lớn hơn cả hiệu năng**.
Spring Boot có Actuator + Micrometer sẵn; Xime có `configure_health()` và nó **mặc định
TẮT**. `Prometheus` không xuất hiện trong `docs/`.

Với chủ dự án thì không sao - tự viết cái cần. Với người thứ hai thì không ai chạy một
service mà không biết p99 của nó là bao nhiêu.

## 6. Liên quan

- [`benchmark-hieu-nang.md`](benchmark-hieu-nang.md) - số đo năm tầng, uvloop lãi ở đâu, và
  bài học về **cách** đo (mục 7, bảy mục a-g).
- [`go-phu-thuoc-khai-niem.md`](go-phu-thuoc-khai-niem.md) - nguyên tắc mà mục 3 đo lại.
- [`../kiem-toan/0.8.2-ket-qua-do-tren-linux.md`](../kiem-toan/0.8.2-ket-qua-do-tren-linux.md)
  - chuyến đo cùng ngày, nơi hai lỗi cửa sổ đo lộ ra.
- [`../sap-toi/lo-hong-tai-lieu-nguoi-dung.md`](../sap-toi/lo-hong-tai-lieu-nguoi-dung.md) -
  lỗ hổng `docs/` đo được, gồm cả chỗ quan trắc ở mục 5.
- `.claude/scripts/do_bien_c_python.py` - chạy lại mục 1.
