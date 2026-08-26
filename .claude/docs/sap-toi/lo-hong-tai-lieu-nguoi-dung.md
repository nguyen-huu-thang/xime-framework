# Lỗ hổng trong `docs/` - sổ theo dõi

> | | |
> |---|---|
> | **Trạng thái** | **CHƯA LÀM.** Danh sách để chủ dự án chọn, không phải kế hoạch đã duyệt |
> | **Đo** | 2026-08-25, phiên Linux |
> | **Đo lại** | `python .claude/scripts/check_doc_coverage.py` (và `--docs docs/vn`) |
> | **Phạm vi** | `docs/` - tài liệu **người dùng**. Không nói về `.claude/docs/` (tài liệu nội bộ) |

## 0. Ba con số

| | |
|---|---|
| Số trang | **23**, `vn` và `en` **khớp hoàn toàn** |
| Tổng dòng | 8.049 |
| **Tên công khai không xuất hiện lấy một lần** | **146/309 ở `docs/en`** · 150/309 ở `docs/vn` |
| Mục lục | **không có** |

⚠ Đọc con số 146 cho đúng: *"không xuất hiện"* là bằng chứng **mạnh** rằng chưa ai viết gì;
chiều ngược lại (*"có xuất hiện"*) là bằng chứng **yếu** - tên có thể chỉ nằm trong một khối
code không lời giải thích. Nên **163 tên còn lại không có nghĩa là đã có tài liệu.**

📌 `vn` thiếu hơn `en` **4 tên**. Hai bên khớp về **số trang** nhưng đã bắt đầu lệch về **nội
dung** - đáng kiểm lại khi động vào bất kỳ trang nào.

---

## Nhóm A - có code, tài liệu không có lấy một chữ

Bằng chứng lấy thẳng từ `check_doc_coverage.py`.

| # | Trang đề xuất | Bằng chứng | Công |
|---|---|---|---|
| **A1** | **`security.md`** (chưa có) | `core/security` **7/13 tên thiếu**: `PEER_CN`, `PEER_SANS`, `authenticate`, `credential_type`, `clear_security`, `current_peer_sans`, `CredentialType`. Danh tính peer qua mTLS là tính năng đầu bảng mà **không trang nào nói** | vừa |
| **A2** | **`errors.md`** (chưa có) | `core/exception` **18/19 tên thiếu** - lỗ đơn lẻ lớn nhất trong cả framework. `XimeException`, `StartupException`, `CircularDependencyException`, `AuthorizationException`... Người dùng không biết bắt gì, không biết tự định nghĩa lỗi ra sao | vừa |
| **A3** | **`lifecycle.md`** (chưa có) | `RunOnce` và `LifecycleManager` **không xuất hiện ở đâu**, mà `RunOnce` là tính năng `0.8` (chạy một lần cho cả cụm). `PostConstruct`/`PreDestroy`/`dependency.order()` bị rải trong 4 trang | nhỏ |
| **A4** | **`events.md`** (chưa có) | `core/event` thiếu `EventBusConfig`, `event_bus_registry`. `EventBus` chỉ được nhắc lướt trong 2 trang, không có trang riêng. `PublishOutcome` - nợ luật 03 vừa trả ở `0.8` - chưa ai giải thích ba giá trị | nhỏ |
| **A5** | Bổ sung TLS web vào `configuration.md` | `ServerTlsConfig`, `WebServerConfig` **thiếu**, dù khối `server.ssl` là đường HTTPS duy nhất | nhỏ |
| **A6** | Bổ sung vào `grpc-codefirst.md` | `configure_grpc_interceptors` **thiếu ở cả hai chỗ** nó được export | nhỏ |
| **A7** | Bổ sung vào `transaction.md` | `ReadOnlyContext` thiếu (`read_only()` thì có) | rất nhỏ |
| **A8** | Bổ sung vào `starters.md` | `SmtpMailService` **1/1 thiếu** - starter mail gần như không có tài liệu; `AsyncEngineProvider`, `DEFAULT_TTL`, `store_registry` cũng thiếu | nhỏ |

⛔ **Không phải mọi tên trong danh sách của script đều đáng có tài liệu.** `*_registry`,
`*Scanner`, `*Builder`, `Resolved*` phần lớn là ruột trong - chúng nằm trong `__all__` vì lý
do `mypy --strict` (xem `find_reexport_gap.py`), không phải vì người dùng cần gọi. Script cố
ý **không tự phân loại**, vì một bản xấp xỉ sẽ sinh cảnh báo giả.

---

## Nhóm B - trang thiếu hẳn, theo nhu cầu người dùng

| # | Trang | Vì sao | Công |
|---|---|---|---|
| **B1** | **`docs/README.md`** (mục lục) | 23 trang, **không có cửa vào**. Người mới mở `docs/` ra thấy danh sách file xếp theo abc. **Rẻ nhất cả danh sách, lợi ngay** | rất nhỏ |
| **B2** | **`deployment.md`** | systemd, profile cấu hình, TLS, health, log, chọn số tiến trình, quyền file - đang rải rác trong `store.md`, `socket-adapter.md`, `multi-process.md`, `cli.md`. Không ai ghép được thành một quy trình | vừa |
| **B3** | **`observability.md`** | Quét `xime/`: **đúng 1 file** nhắc tracing/metrics. `Prometheus` **không có trong `docs/`**. Đây là rào cản đưa vào production **lớn nhất** với người ngoài, lớn hơn cả hiệu năng | vừa |
| **B4** | **`from-fastapi.md`** | Đường vào tự nhiên nhất cho người dùng mới: họ đã có app FastAPI, câu hỏi là *"chuyển sang thì đụng gì"* | vừa |
| **B5** | **`performance.md`** | Bộ benchmark đã có. Công bố số thật + phát hiện *uvloop làm REST chậm ~7%* là thứ hiếm ai dám viết. Số lấy sẵn từ [`ghi-chep/benchmark-hieu-nang.md`](../ghi-chep/benchmark-hieu-nang.md), chỉ cần lọc phần công khai được | nhỏ |
| **B6** | **Ví dụ đầu-cuối đa giao thức** | Một service **vừa đọc Modbus vừa phục vụ REST** trong một file. Đây là khác biệt **duy nhất không ai có** (xem [`ghi-chep/dac-tinh-python-va-vi-tri-framework.md`](../ghi-chep/dac-tinh-python-va-vi-tri-framework.md) mục 4), mà hiện không trang nào cho thấy nó trông thế nào - `modbus.md` và `routing.md` là hai trang rời | vừa |

---

## Nhóm C - sửa cái đang có

| # | Việc | Bằng chứng | Công |
|---|---|---|---|
| **C1** | Tách `starters.md` | **711 dòng ôm 7 starter** (sqlalchemy, jwt, scheduler, cache/redis, storage, mail, lmdb). Đã thành bãi rác, và mục A8 cho thấy phần mail gần như trống | vừa |
| **C2** | Thử `getting-started.md` với người ngoài | Vừa viết lại ở `0.8.2` vì bản cũ **không chạy được** (`ModuleNotFoundError`). Giờ là lúc hợp lý để đưa cho một người không biết Xime và **ngồi im xem họ vấp ở đâu** | nhỏ |
| **C3** | `contributing.md` | 127 dòng, mỏng nhất trong 23 trang | nhỏ |
| **C4** | Đồng bộ lại `vn` với `en` | Lệch **4 tên** (150 so với 146). Số trang khớp nhưng nội dung đã bắt đầu trôi | nhỏ |

---

## Nhóm D - định vị và lòng tin

| # | Trang | Vì sao | Công |
|---|---|---|---|
| **D1** | **"Khi nào ĐỪNG dùng Xime"** | Với framework một-người-làm thì đây là thứ xây lòng tin nhanh nhất. Ai đọc thấy tác giả tự nói *"API REST thuần thì dùng FastAPI đi"* sẽ tin phần còn lại. `README.md` dòng 52 đã có mầm của câu này | nhỏ |
| **D2** | So sánh với FastAPI / Litestar / Django | Người ta **sẽ** hỏi. Tư liệu đã có sẵn ở [`ghi-chep/dac-tinh-python-va-vi-tri-framework.md`](../ghi-chep/dac-tinh-python-va-vi-tri-framework.md) mục 4 | vừa |
| **D3** | **Chính sách phiên bản** | `0.8.x` **vẫn đổi API**, `0.9` sang Beta nơi API coi như chốt. Người ngoài **không có cách nào biết**, mà nó quyết định họ có dám dùng không | rất nhỏ |

---

## Thứ tự đề xuất, nếu chỉ chọn ba

| | Mục | Lý do |
|---|---|---|
| **1** | **B1** mục lục | Rẻ nhất cả danh sách, và làm 23 trang đang có **dùng được hơn ngay lập tức**. Đang có tài liệu tốt mà không có cửa vào |
| **2** | **A2 + A1** (`errors.md`, `security.md`) | Hai lỗ **đo được**: 25/32 tên không có một chữ. Và đây là hai thứ người ta **buộc phải** biết mới đưa vào production |
| **3** | **B6** ví dụ đa giao thức | Chỗ duy nhất không ai cạnh tranh, mà hiện đang **vô hình** trong tài liệu |

**Rẻ mà nên làm kèm:** **D3** (vài chục dòng) và **B5** (số có sẵn).

## ⚠ Chi phí: mọi trang mới tốn gấp đôi

`vn` và `en` đang khớp về số trang - kỷ luật tốt, nhưng nghĩa là mỗi trang phải viết hai lần.
Chọn nhiều mục thì nên **viết `vn` trước cho cả loạt rồi dịch một lượt**, thay vì làm xong
từng trang hai thứ tiếng.

Và mỗi lần thêm trang, chạy lại ba script kiểm tài liệu đã có - chúng canh chiều ngược lại
với script mới:

```bash
python .claude/scripts/check_doc_imports.py    # tai lieu noi ten co that khong
python .claude/scripts/check_doc_code.py       # khoi ```python co phan tich duoc khong
python .claude/scripts/check_doc_register.py   # class tai lieu bao dang ky co dung duoc khong
python .claude/scripts/check_doc_coverage.py   # API nao KHONG co tai lieu   <- moi
```
