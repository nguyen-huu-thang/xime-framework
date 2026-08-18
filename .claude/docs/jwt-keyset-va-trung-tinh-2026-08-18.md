# JWT: khóa xoay theo `kid`, và trả nợ trung tính - 2026-08-18

> Nằm trong **0.7.1** (chưa commit). Không phá app nào đang chạy.
> Test sau bản này: **1553 passed, 11 skipped** (trước: 1516).

## 0. Đọc gì trước

Việc này bắt đầu từ một câu hỏi của chủ dự án: *"framework có jwt ký, verify. sao
tôi thấy nó hơi có vẻ phụ thuộc bên ngoài hay sao ấy nhỉ."*

Câu trả lời sau khi đo: **không có một chữ nào của Xime trong starter JWT.**
`grep -rniE "trust|identity-service|shard|org_id|app_id" xime/starters/jwt/` ra rỗng.

Nhưng linh cảm không sai, chỉ **ngược chiều**:

> **Starter JWT không quá Xime. Nó quá NGÂY THƠ.** Và chính vì ngây thơ nên Xime
> phải đắp một lớp lên trên - **Trust nằm ở lớp đắp đó, không nằm trong framework.**

Cùng khuôn với `xime-app://` (gỡ ngày 2026-08-17), nhưng lộn ngược:

| | `PEER_APP_ID` | `KeyContext` |
|---|---|---|
| Sai ở đâu | framework **biết quá nhiều** về Xime | framework **biết quá ít** về JWT |
| Hậu quả | người ngoài dùng không được | **người trong nhà** dùng không được |
| Bằng chứng | 4/5 repo tự viết lại | **21/21 repo tự viết lại** |

Cả hai lộ ra bằng cùng một phép đo: **đếm xem bao nhiêu người dùng thứ ta cấp,
bao nhiêu người tự viết.**

## 1. Bất đối xứng gốc

```
grep -rn "kid" xime/starters/jwt/
  _signer.py:77   headers["kid"] = key_context.key_id      <- KÝ
  (khong con dong nao khac)                                <- VERIFY: khong co gi
```

Framework **tự sinh ra thứ nó không đọc được**. `JwtMiddlewareConfig.key_context`
là **đúng một** `KeyContext`, cấp lúc config, vĩnh viễn.

Hệ quả: xoay khóa thì mọi app phải restart, mà restart cũng không cứu được token
cũ. Nên 21 app tự viết. Đo trên `saas-foundation/template` (nguồn của 20 app kia):

| File | Dòng |
|---|---|
| `TrustKeyProvider.py` | 150 |
| `TrustJwtAuthMiddleware.py` | 105 |
| `config/jwt.py` | 99 |
| `JwtKeySet.py` | 59 |
| | **413** |

⚠ Và 19/21 trong số đó **fail-open**: không lấy được khóa thì `config/jwt.py`
**không gọi `configure_middleware`**, app lên mà không có xác thực nào, tự báo là
khỏe trong khi mọi endpoint mở. `saas-foundation/template` nằm trong nhóm chưa vá,
nên **mọi app clone từ nay đều thừa hưởng**.

⭐ Nhưng đó không phải 19 lần cẩu thả. Đó là **ô duy nhất còn trống trên bàn cờ**:
framework bắt chọn giữa *"có sẵn chuỗi PEM lúc khởi động"* và *"không có middleware
nào"*, mà khóa thì nằm ở Trust, lấy qua mạng.

## 2. ⭐ Cái khe cũ trung tính về TỪ VỰNG, sai về HÌNH DẠNG và VỊ TRÍ

`JwtTokenVerifier` là điểm mở rộng **có tài liệu từ 0.2**, docstring nêu đích danh
*"fetching public keys from a JWKS endpoint"*. Nó không dùng được, vì ba lý do
khác nhau:

| Trục | |
|---|---|
| Từ vựng | ✅ trung tính, không có gì của Xime |
| Hình dạng | ⛔ ép mọi implementation đi qua `KeyContext` - **đúng cái kiểu đang là vấn đề**; và **đồng bộ**, trong khi cả bốn ca dùng docstring nêu tên (HSM, cloud KMS, JWKS, authorization server) đều là lời gọi mạng |
| Vị trí | ⛔ đặt ở **verify**, mà thứ khác nhau giữa các triển khai là **tìm khóa** |

> **Cái khe cho thay thứ không ai muốn thay, và không cho thay thứ ai cũng cần thay.**

Đó là lời giải thích rõ nhất cho con số 21/21: muốn đổi cách **tìm khóa**, người ta
buộc phải viết lại **cả phần verify** - phần nhạy cảm bảo mật nhất, phần họ không
hề muốn đụng.

⚠ Và nó **chưa bao giờ được đi thử**: `grep JwtTokenVerifier tests_temp/` chỉ ra
`PyJwtTokenVerifier()` dựng trực tiếp, **không test nào bind một implementation
khác rồi kiểm middleware có dùng nó**. Nên chuyện middleware đóng cứng
`PyJwtTokenVerifier()` (dòng 55) sống nhiều tháng mà không có gì báo.

> Cùng bài học 0.7.0: *viết ít nhất một test đi đúng con đường tài liệu hướng dẫn,
> không phải con đường tiện nhất cho test.*

## 3. Quyết định của chủ dự án

Tôi đề xuất hai hình dạng. Chủ dự án chọn hình dạng thứ nhất:

| | Provider **giữ** cache (chọn) | Framework giữ cache (`fetch()`) |
|---|---|---|
| Hợp đồng | `keys(kid)` - **một method, đồng bộ** | `async fetch()` + framework lo TTL/hãm nhịp/single-flight |
| Ai lo làm tươi | **app** | framework |
| Nợ nghĩa 1 sinh thêm | **không** | mốc thời gian + `Lock` trong RAM tiến trình |

Nguyên văn: *"tôi nghĩ logic này nên để ở app. tôi chọn bỏ refresh(), để người lập
trình app chủ động."*

**Hai cái lợi:**

**a. Framework không sinh thêm một dòng nợ nghĩa 1 nào.** Bản có `refresh()` phải
giữ mốc + `Lock` trong RAM - đúng nhóm *"lời gọi sau phụ thuộc lời gọi trước"* mà
[luật 01](../../../.claude/rules/01-song-song-hoa-va-shard.md) bắt phải ra khỏi bộ
nhớ. Bỏ `refresh()` là **xóa món nợ trước khi nó sinh ra**.

**b. ⭐ 21 app xóa đúng phần đáng xóa, giữ đúng phần đang chạy tốt** - xem mục 6.

**Cái giá, khai rõ:** `kid` lạ thì **401 ngay**, framework không đi hỏi ai. Xoay
khóa mà cache app còn cũ thì hỏng cho tới khi app tự làm tươi. Đó nay là **trách
nhiệm khai báo của app**.

### Đa tiến trình: câu hỏi đúng không phải "ai gọi"

Chủ dự án hỏi liệu để framework gọi thì có đỡ phần *"chỉ một tiến trình được gọi"*
không. Phân tích ra một chỗ phải chỉnh trong tiền đề:

| | Ai làm tươi | Kết quả nằm đâu | |
|---|---|---|---|
| A | **mọi** tiến trình | RAM riêng từng tiến trình | ✅ đúng, đổi lấy N lần gọi mạng |
| B | **một** tiến trình | **kho dùng chung** | ✅ đúng, cần 0.8 |
| C | **một** tiến trình | RAM riêng từng tiến trình | ⛔ **HỎNG** |

> **Dời lời gọi mà không dời chỗ chứa thì không dời được gì.** Bài toán đa tiến
> trình nằm ở **chỗ chứa**.

⭐ Và luật 01 đã trả lời sẵn cho ca này, ở cột **"Không phải nợ"**:

> *"Cache có **nguồn bền vững** (danh bạ app, **khóa ký từ Trust**) - mất thì nạp
> lại được"*

**Khóa ký từ Trust được gọi tên thẳng trong luật.** Nên hình dạng A hợp lệ, không
phải giải pháp tạm. Ngày 0.8 có kho liên tiến trình thì app đổi sang B **mà không
phải đụng hợp đồng** - `keys(kid)` không hứa gì về chỗ chứa.

## 4. Đã làm gì

### Thêm

- **`JwtKeyProvider`** (`_provider.py`) - `keys(kid) -> Sequence[KeyContext]`, đăng
  ký bằng `configure_jwt(config, key_provider=YourClass)`. Cùng khuôn
  `configure_grpc_tls(provider=...)`: truyền CLASS, framework lấy từ DI.
  ⭐ Nhận `kid` là **chuỗi của RFC 7515**, không phải kiểu nào của framework - người
  cắm vào không phải học gì mới.
- **Verify theo `kid`** trong middleware: `get_unverified_header` (không cần khóa)
  → hỏi provider → thử lần lượt ứng viên.
- **Ba knob PyJWT vốn có mà config giấu**: `algorithms` (danh sách trắng - **trần**
  chứ không phải phép chọn), `leeway`, `require`.
- **`sign(..., headers=)`** - trước đây `kid` là header **duy nhất** app đặt được,
  trong khi payload mở toang.

### Sửa

- ⛔ **`configure_jwt()` không có nguồn khóa nay NỔ lúc khởi động.** Đúng một trong
  `key_context` / `key_provider`; không có cái nào, hoặc cả hai, đều
  `StartupException`. **Không phá ai** vì `key_context` vốn bắt buộc nên trạng thái
  "không có gì" trước nay không tồn tại được.
- **Middleware nhận `verifier` từ ngoài** thay vì tự dựng `PyJwtTokenVerifier()`.
  Khai tường minh qua `configure_jwt(config, verifier=...)` chứ **không** nhặt từ
  `dependency.bind()` - middleware do adapter dựng, bind không tới được, mà một
  phép thay thế trông như chạy trong khi không đổi gì thì tệ hơn là không có.
- **`key_id=""`** không còn đóng dấu `kid: ""`. `is not None` cho chuỗi rỗng lọt.

## 5. Bốn phép đo đáng giữ

| Đo gì | Kết quả |
|---|---|
| `headers={"alg": "HS512"}` với `algorithm="HS256"` | header ra **`HS512`** - PyJWT ghi rõ *"Prefer headers values if present to function parameters"*. Mở header mà không chặn `alg` là `KeyContext.algorithm` **âm thầm hết đúng** |
| Token **không có `exp`** | `jwt.decode` trả `{'sub': 'a'}` - qua bình thường. `verify_exp` chỉ kiểm **khi claim tồn tại**, và `require` mặc định rỗng |
| `kid` không phải chuỗi | **PyJWT 2.8 (đúng sàn khai báo) và 2.13 đều từ chối.** Tôi đã báo đây là lỗ DoS - **sai**, nó không tồn tại trong dải hỗ trợ |
| `get_unverified_header` | đọc `kid` **không cần khóa** - đây là cơ chế cho phép tra khóa trước khi verify |

⭐ Phép đo thứ ba dẫn tới một quyết định đáng ghi: chốt chặn `isinstance` **vẫn
giữ**, nhưng lý do đổi hẳn. Không phải *"PyJWT sẽ cho lọt"* mà là:

> `JwtKeyProvider.keys()` khai kiểu `str | None`. Đó là **lời hứa với người viết
> ứng dụng**, và lời hứa nên do chính chỗ hứa giữ, chứ không nhờ một thư viện bên
> thứ ba tình cờ đang đồng ý.

Nhánh đó **không tới được qua request thật**, nên nó có test trực tiếp
(`test_read_kid_refuses_a_non_string_even_if_one_gets_through`, monkeypatch) - *một
chốt chặn không ai chạm tới và không ai kiểm thì không phân biệt được với một chốt
chặn hỏng.*

## 6. Việc của 21 app - và vì sao migration nhỏ hơn tưởng

⚠ **Bản vá framework KHÔNG tự đóng lỗ A1 ở 19 app.** Lỗ đó nằm trong `config/jwt.py`
của chính họ, framework không với tới. Cái nó làm là **xóa lý do tồn tại của lỗ**:
nay có ô thứ ba, và ô đó là ô đúng.

| File của app | |
|---|---|
| `TrustKeyProvider.py` (150) | ✅ **giữ nguyên**, chỉ thêm method `keys(kid)` |
| `JwtKeySet.py` (59) | ✅ **giữ nguyên**, thành ruột của provider |
| `TrustJwtAuthMiddleware.py` (105) | ⛔ **xóa** |
| `config/jwt.py` (99) | rút còn ~25 |

⭐ **Xóa ~180 dòng, và 105 dòng bị xóa đúng là mã verify chép tay** - phần nhạy cảm
bảo mật, phần duy nhất thật sự nên nằm ở một chỗ. Phần giữ lại là mã đặc thù Xime,
đã chạy thật nhiều tháng.

⚠ Một chỗ họ phải quyết khi chuyển: `JwtKeySet.resolve(kid)` hiện làm *"theo kid nếu
có, ngược lại **thử tất cả**"*. Framework nay **không suy diễn** khi `kid` vắng - nó
gọi `keys(None)` và tin câu trả lời. Provider trả gì cho `None` là chính sách của
app, và **"thử tất cả" nên được xem lại**, vì nó biến `kid` từ phép định tuyến thành
thứ trang trí.

## 7. Còn nợ

| | |
|---|---|
| **F1 - xác thực WebSocket** | `scope["type"] != "http"` cho qua tất cả, **không một dòng log**. Phải xong trước app `xime chat` |
| **JWT cho gRPC** | `adapters/grpc/interceptors/` không có gì liên quan JWT |
| 19 app migrate | Vá `saas-foundation/template` **trước** - nó là nguồn sinh sôi |

Hai mục đầu là **bề mặt mới**, không phải sửa chữa - đó là ranh giới đã dùng để cắt
phạm vi đợt này.

⚠ **Không làm được, đã rút khỏi phạm vi:** cảnh báo *"ký mà không có `kid`"*.
`sign()` nhận khóa **theo từng lời gọi** nên lúc khởi động framework chưa biết gì,
còn cảnh báo mỗi lần gọi thì thành rác log. Chuyển thành tài liệu trong docstring.

## 8. Liên quan

- [`go-phu-thuoc-khai-niem-2026-08-17.md`](go-phu-thuoc-khai-niem-2026-08-17.md) -
  cùng khuôn, ngược chiều
- [`ke-hoach-va-bao-mat-2026-08-01.md`](ke-hoach-va-bao-mat-2026-08-01.md) mục A1
- [Luật 01](../../../.claude/rules/01-song-song-hoa-va-shard.md) nghĩa 1 - *"khóa ký
  từ Trust"* nằm ở cột **không phải nợ**
- [Luật 03](../../../.claude/rules/03-mot-gia-tri-mot-nghia.md) - ba lý do từ chối là
  ba thông điệp riêng, vì việc operator phải làm khác nhau
