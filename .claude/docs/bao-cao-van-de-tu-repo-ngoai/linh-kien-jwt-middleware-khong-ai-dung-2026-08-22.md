# `configure_jwt` không repo nào dùng, và hai chỗ chặn 2 repo di trú về

> Người báo: phiên giữ `Application Layer/linh-kien-dien-tu`, 2026-08-22.
> Framework đo trên máy: `0.8.1`, cài editable.
>
> ⚠ **Đây KHÔNG phải báo lỗi.** Không có gì hỏng, không repo nào đang sập. Đây là
> một **câu hỏi về tính trung tính**: hai chỗ thiếu dưới đây có phải nhu cầu chung
> của framework, hay chỉ là nhu cầu của một nhóm nhỏ app? Tôi cố ý đưa **cả lập
> luận chống lại việc thêm**, ở mục 5 - phần đó đáng đọc trước phần đề xuất.
>
> Tôi không tự nhận là mình quyết được. Repo tôi đã đi đường vòng và đang chạy tốt.

## 1. Con số đáng chú ý nhất lại không phải hai tính năng kia

Đo bằng lệnh trên toàn workspace ngày 2026-08-22:

| Phép đếm | Kết quả |
|---|---|
| Repo Python có `app/config/jwt.py` | **21** |
| Repo **gọi thật** `configure_jwt(` | **0** |
| File middleware JWT **tự viết** trong workspace | **22** (21 repo + `saas-foundation/template`) |
| Trong đó dài **đúng 105 dòng** | **19** |

Nghĩa là: middleware JWT của framework hiện **không ai dùng**, và thay vào đó
workspace đang nuôi **19 bản sao y hệt** của một file verify token viết tay, cộng
2 bản đã tự mở rộng.

⭐ **Nhưng đừng đọc con số 0 đó thành "framework làm sai".** Tôi đã tra lý do, và
nó là chuyện lịch sử chứ không phải chuyện chất lượng: docstring của chính file
105 dòng đó ghi

> *"Framework `configure_jwt` chỉ verify 1 key_context."*

Câu đó **đúng lúc viết**, và **sai từ `0.7.2`** khi `key_provider` + tra khoá theo
`kid` ra đời. Không ai quay lại đọc. Nên `0/21` là **dấu vết của một hạn chế đã
được vá**, không phải một lá phiếu chống.

📌 Hệ quả thực dụng, và đây là lý do tôi viết báo cáo này thay vì im lặng: **phần
lớn trong 21 repo đó hôm nay đã di trú về `configure_jwt` được rồi.** Chỉ có 2
repo là còn bị chặn, bởi đúng hai chỗ ở mục 2 và 3.

## 2. Chỗ thiếu A: `public_paths` khớp chính xác, không khớp được nhánh

`xime/starters/jwt/_config.py:22-25` khai rõ và có chủ đích:

```text
public_paths : Request paths that bypass JWT authentication entirely.
               Matched EXACTLY (only a trailing slash is ignored), not by
               prefix: listing "/docs" does not open "/docs/anything".
```

Đường công khai có **tham số trong path** vì thế không khai nổi.

⭐ **Điểm mạnh nhất của mục này không phải repo tôi, mà là chính ví dụ trong
docstring của framework: `/docs`.** FastAPI phục vụ `/docs`, `/docs/oauth2-redirect`
và `/openapi.json` - tức framework **tự va vào giới hạn này bằng route của chính
nó**, và câu docstring đó là lời thú nhận sẵn có.

**Hai repo đã tự vá, và động cơ của họ KHÔNG liên quan gì tới nhau:**

| Repo | Đường cần mở | Vì sao không liệt kê chính xác được |
|---|---|---|
| `Application Layer/linh-kien-dien-tu` | `/api/v1/parts/*`, `/api/v1/catalog/*` | Sàn linh kiện, khách **vãng lai** duyệt catalog theo `/parts/{part_id}` |
| `Service ngang/nhan-su-cham-cong` | `/api/v1/devices/*` | **Máy chấm công** đẩy dữ liệu vào `/devices/{id}/events`, xác thực bằng **khoá thiết bị** vì cái máy không đăng nhập được |

Hai lý do khác hẳn nhau: một bên là người dùng ẩn danh, một bên là thiết bị dùng
cơ chế xác thực khác. Chúng gặp nhau ở đúng một chỗ: **REST có tham số đường dẫn**.

### ⚠ Nếu nhận mục này: đừng hiện thực bằng `startswith` trần

`/api/v1/parts/*` mà khớp luôn `/api/v1/partsecret` là một **lớp lỗ hổng**, không
phải lỗi nhỏ - và nó hỏng theo chiều an toàn sang kém an toàn nên không ai thấy.

Hai repo trên đều đã tránh được, bằng cách chuẩn hoá tiền tố cho **kết thúc bằng
`/`** rồi xử lý riêng đường gốc. Tôi chạy thử bản của repo mình:

```text
public_paths = ['/api/v1/parts/*']

  /api/v1/parts          -> True     (đường gốc, cố ý mở)
  /api/v1/parts/         -> True
  /api/v1/parts/abc      -> True
  /api/v1/partsecret     -> False    <- chỗ dễ sai nhất
  /api/v1/parts-admin    -> False
  /api/v1/partsX/y       -> False
```

Mã tham khảo, nếu hữu ích: `linh-kien-dien-tu/backend/app/api/rest/TrustJwtAuthMiddleware.py`
(`_split_public` / `_is_public`) và test canh `test/unit/test_duong_cong_khai.py`.
Bản của `nhan-su-cham-cong` gọn hơn và cũng đúng.

## 3. Chỗ thiếu B: công khai và ẩn danh đang bị coi là một

`xime/starters/jwt/_middleware.py:49` mô tả luồng:

```text
1. Path in public_paths?  -> skip, forward request as-is
```

Nên một đường công khai thì **không bao giờ** được nhìn tới token, kể cả khi
client có gửi.

⭐ **Đây là hình dạng luật 03 ở tầng cấu hình**, và tôi nghĩ đó là cách đóng khung
đúng hơn là gọi nó "thiếu tính năng": **một danh sách `public_paths` đang chở hai
ý định khác nhau.**

| Ý định | Nghĩa |
|---|---|
| *"Đường này **không cần** danh tính"* | ai cũng vào được |
| *"Đường này **không được** nhận diện"* | có token cũng vờ như không |

App muốn ý thứ nhất thì **lặng lẽ nhận luôn ý thứ hai**, và không có cách nào khai
khác đi.

**Hậu quả cụ thể ở repo tôi:** nhân viên sàn đang đăng nhập, mở trang linh kiện
công khai, bị coi là khách vãng lai, nên **không thấy bản `DRAFT` mình vừa soạn**.
Use case lọc trạng thái theo danh tính, mà danh tính thì đã bị vứt ở middleware.

⚠ Xin nói rõ vì đây là chỗ dễ hiểu nhầm thành "nới lỏng bảo mật": nhận diện trên
đường công khai **chỉ làm quyền chặt hơn**. Đường không công khai vẫn đòi token
hợp lệ y như cũ; đường công khai thì vốn đã cho người lạ vào rồi, biết thêm người
gửi là ai chỉ có thể **thu hẹp** thứ họ thấy. Token hỏng hoặc hết hạn thì đi tiếp
như khách vãng lai chứ **không** 401 - một cookie cũ không được phép giết trang
công khai.

## 4. Hai chỗ đó có chung một gốc, nhưng KHÔNG phải một tính năng

Tôi nghĩ đây là phần cần cân nhắc kỹ nhất khi đánh giá tính trung tính.

**Chúng là hai trục độc lập.** Một cái là *đường khớp thế nào*, cái kia là *khớp
rồi thì làm gì*. Nhận cái này không kéo theo cái kia, và có thể nhận A mà bác B.

**Nhưng chúng rơi ra từ đúng một giả định**, và giả định đó nằm ngay trong ví dụ
mặc định của docstring (`_config.py:76`):

```python
public_paths=["/auth/login", "/auth/refresh", "/health"],
```

Ba đường **kỹ thuật, cố định**. Đó là hình dạng của một app **quản lý nội bộ**:
mọi thứ sau đăng nhập, trừ vài cửa hạ tầng. App **mặt tiền công khai** thì mặc
định ngược lại - phần lớn mở, chọn lọc nhận diện.

Nói cách khác: middleware hiện tại phục vụ rất tốt hạng app mà workspace này có
nhiều nhất (19/21 repo), và hụt ở hạng app mà workspace này **mới bắt đầu có**.

## 5. ⚖ Lập luận CHỐNG lại việc thêm - đọc phần này trước phần đề xuất

Tôi cố ý viết phần này vì tôi là bên có lợi nếu framework nhận, nên lập luận của
tôi ở trên không đáng được tin một mình.

| Chống | Nội dung |
|---|---|
| **B mới có đúng 1 khách** | Chỉ repo tôi cần. Một framework nhận tính năng theo một khách là cách nó phình ra |
| **Khớp chính xác là lựa chọn CÓ CHỦ ĐÍCH** | Docstring không im lặng về nó, nó **lập luận** cho nó. Lật một quyết định đã được viết ra thì cần nhiều hơn 2 khách |
| **Đây là danh sách miễn trừ BẢO MẬT** | Nới cách khớp trên một allowlist là nới đúng chỗ đắt nhất khi sai. Framework nên bảo thủ ở đây hơn mọi chỗ khác |
| **App đã có đường tự lo** | `configure_middleware` cho phép app tự viết, và 21 repo đã làm vậy nhiều tháng mà không ai kêu. Có thể đây đúng là việc của app |
| **Con số 0/21 có thể bị đọc quá tay** | Nó là dấu vết của việc chép file cũ, **không** phải bằng chứng ai đó thử framework rồi bỏ. Đừng lấy nó làm lý do gấp |

**Phản biện lại phần chống, ngắn:** mục A thì tôi cho là qua được, vì bằng chứng
mạnh nhất không đến từ app nào cả mà từ **route `/docs` của chính framework**, cộng
hai khách độc lập với hai động cơ không liên quan. Mục B thì tôi **không** cho là
đã đủ chín - tôi đề nghị xem nó như một **câu hỏi thiết kế** (`public_paths` có nên
tách làm hai danh sách không) chứ không phải một yêu cầu tính năng, và để lại tới
khi có khách thứ hai. Workspace sắp có thêm app mặt tiền (`dental` có website
công khai, app thứ tư kiểu Shopify có storefront, `portal`, `marketplace`), nhưng
**"sắp có" không phải một phép đo**, và tôi không muốn báo cáo này dựa vào nó.

## 6. Nếu framework quyết KHÔNG nhận

Hoàn toàn ổn với repo tôi - tôi đã đi đường vòng và nó đang chạy. Nhưng nếu bác
thì có một việc nhỏ đáng làm, rẻ hơn nhiều so với việc thêm tính năng:

> **Sửa một câu trong tài liệu.** Nhiều repo trong workspace đang mang chú thích
> *"framework `configure_jwt` chỉ verify 1 key nên không dùng"* - câu đã sai từ
> `0.7.2`. Một dòng trong `docs/vn/` nói rõ *"từ 0.7.2 `configure_jwt` nhận
> `key_provider` và tra khoá theo `kid`"*, cộng một câu nói thẳng rằng
> `public_paths` khớp chính xác **và cố ý như vậy**, sẽ giúp 19 repo kia biết họ
> di trú về được, và giúp repo thứ 20 không viết lại bản sao thứ 23.

## 7. Phạm vi tôi đo được tới đâu

- **Đo bằng lệnh, chạy thật:** phép đếm ở mục 1 (`21` repo có `config/jwt.py`, `0`
  gọi `configure_jwt(`, `22` file middleware tự viết, `19` file dài đúng 105 dòng)
  quét trên `Application Layer/`, `Service ngang/`, `Base Platform/` của workspace
  `D:\code\xime`. Bảng ca biên tiền tố ở mục 2 là **chạy thật** trên middleware
  của repo tôi, không phải đọc code.
- **Chỉ ĐỌC CODE, chưa chạy:** hai trích dẫn hành vi của framework
  (`_config.py:22-25` khớp chính xác, `_middleware.py:49` skip đường công khai).
  Tôi **chưa** viết một app thử dùng `configure_jwt` thật để xác nhận hai hành vi
  đó lúc chạy. Nếu framework định dựa vào báo cáo này để sửa, **hãy tự đo lại hai
  điểm đó trước** - tôi có thể đã đọc sót một đường lui nào đó.
- **Chưa đo:** tôi **không** kiểm 19 repo kia xem chúng có thật sự di trú về
  `configure_jwt` được không. Tôi suy điều đó từ chỗ chúng dùng chung một file
  105 dòng không sửa gì, chứ chưa thử di trú một repo nào. Con số *"phần lớn 21
  repo di trú được"* ở mục 1 vì vậy là **suy luận, không phải phép đo**.
- **Chưa đo:** tôi không rà các starter khác xem có chỗ nào cùng hình dạng *"một
  danh sách chở hai ý định"* như mục 3 không. Không biết đây là chuyện riêng của
  `jwt` hay một khuôn rộng hơn.
- **Nền tảng:** Windows 11, Python 3.14, `xime 0.8.1` editable. Không có gì trong
  báo cáo này phụ thuộc nền tảng, nhưng tôi chưa đối chứng trên Linux.
