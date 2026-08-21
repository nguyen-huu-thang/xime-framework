[English](../en/cli.md) | **Tiếng Việt**

# Công cụ dòng lệnh

```bash
xime init <ten-du-an>        # tạo cây thư mục và file cơ bản
xime config --print          # in mọi khoá cấu hình kèm mặc định
xime check config            # đối chiếu application.yml của bạn
xime check module-level      # bắt lời gọi không tất định ở mức module
xime grpc generate|check|client
```

---

## Cấu hình nằm ở HAI chỗ, và ranh giới không tuỳ tiện

| | Ở đâu | Ai quyết |
|---|---|---|
| **Vận hành** - cổng, chuỗi kết nối, đường dẫn, hạn mức | `resources/application.yml` | người vận hành |
| **Kiến trúc** - binding DI, route, middleware, CORS, trần event bus | `config/*.py` | lập trình viên |

Câu để phân loại: **người vận hành có ĐỦ THÔNG TIN để chọn giá trị này không?**
Không thì nó thuộc `config/*.py`, dù nó là một con số và dù nó nghe như chuyện
vận hành.

---

## `xime config --print`

In ra stdout **toàn bộ** bề mặt cấu hình của framework: mọi khối, mọi khoá, mặc
định của từng khoá, và lời giải thích. Không ghi gì cả.

```bash
xime config --print > resources/application.yml     # bắt đầu một file mới
xime config --print | diff - resources/application.yml   # so với file đang có
```

### ⭐ Luật chia: chú thích thứ mặc định được, ghi thẳng thứ không

```yaml
lmdb:
  path: /dev/shm/don-hang-store   # framework không đoán được -> ghi thẳng
  # map_size: 64MB                # mặc định của framework -> để nguyên chú thích
  # total_max: 1GiB
```

Đọc file là biết ngay: **dòng không chú thích = thứ deployment này thật sự đã
quyết**; dòng chú thích = tài liệu, và nó có cũ đi cũng không cắn ai vì nó trơ.

⚠ **Đừng chép giá trị mặc định ra khỏi chú thích nếu bạn không định đổi nó.**
Giá trị nào nằm trong file thì hành vi của app **đóng băng ở phiên bản nó được
tạo**: một bản Xime sau này sửa mặc định vì lý do bảo mật sẽ không tới được bạn.

### Vì sao `lmdb.path` không có mặc định

Nhiều service Xime dùng chung một máy, và kho **cố ý sống qua lần restart** nên
tên của nó phải ổn định. Một mặc định ổn định vì vậy sẽ là **cùng một thư mục
cho mọi app trên máy** - hai service đè bảng hãm nhịp của nhau, **không dấu hiệu
nào**. Framework từ chối đoán; trình tạo thì đoán được, vì nó biết tên dự án.

⭐ Ranh giới chung: **framework được phép đoán khi đoán sai thì có tiếng động**
(hai app cùng cổng 8080 -> `EADDRINUSE`, chết ngay), **không được phép khi đoán
sai thì im lặng**.

---

## `xime check config`

So `application.yml` của bạn với bề mặt trên. Thứ nó bắt được mà hôm nay không
gì bắt: **khoá gõ sai**.

```text
  server.prot: unknown key   did you mean 'port'?
  lmdb.path: required key is missing

2 problem(s) in /srv/don-hang/resources/application.yml.
Blocks checked: server, lmdb
```

**Ba mã thoát:** `0` sạch · `1` có vấn đề · `2` **chưa kết luận được** (không đọc
được file). Mã `2` tồn tại vì *"không tìm thấy vấn đề"* và *"không đọc được để mà
tìm"* là hai câu trả lời khác nhau.

⚠ **Nó cố ý không soi mọi thứ.** Khối của chính ứng dụng bạn (`trust:`, `app:`)
và khối mà framework chưa mô tả đủ khoá đều được để yên. Một phép dò tố khoá hợp
lệ sẽ bị tắt trong tuần đầu, và lúc đó nó không bắt được gì nữa. Dòng
`Blocks checked:` cho biết nó thật sự đã soi những gì.

### Tên KHỐI gõ sai cũng được gợi ý

```text
  serber: unknown block   did you mean 'server'?
```

Đây là cùng một lỗi gõ với `server.porrt`, chỉ ở một tầng khác - và cùng một hậu
quả: ứng dụng chạy với **mặc định của framework**, người vận hành tin là đang
chạy với giá trị họ vừa viết, và không một dòng log nào nói khác.

⭐ **Chỉ gợi ý khi tên lạ GẦN GIỐNG một tên đã biết**, im khi nó không giống gì
cả. Đo trên `application.yml` thật của các ứng dụng Xime: `serber`, `sever`,
`grcp`, `procss` đều được bắt, còn `trust`, `app`, `shard`, `legal`,
`organization` **không sinh một cảnh báo giả nào**.

---

## `xime init`

```bash
xime init don-hang
cd don-hang && pip install -e . && python main.py
```

Sinh **ít** có chủ ý: `main.py`, `config/`, một controller mẫu, hai file cấu
hình, `pyproject.toml`, `.gitignore`, `README.md`. Không sinh sẵn
`application/service/`, `infrastructure/repository/` - bố trí kiến trúc là việc
của bạn, và mỗi file trình tạo đẻ ra là một file framework ngầm sở hữu vĩnh viễn.

Hai file cấu hình, hai vai:

| | |
|---|---|
| `application.yml` | file thật, **đầy đủ chú thích**, `.gitignore` chặn (secret) |
| `application.yml.example` | cho git, **không chú thích**, chỉ khoá bắt buộc |

⚠ Bản `.example` chỉ để một bản clone sạch biết phải điền gì - **xoá đi cũng
được**. Mọi lời giải thích sống ở `xime config --print`, thứ không bao giờ cũ;
chú thích trong một file đi theo git là tài liệu già đi trong im lặng.

⛔ Lệnh **từ chối ghi đè** file đã có. Ghi đè một `application.yml` đang chạy là
xoá cấu hình thật của một deployment, và không có đường lui. Cần thì `--force`.

### Vài cái tên bị từ chối, và lý do đáng đọc

```bash
xime init config
#   Detail: 'config' is reserved: the generated project already has a 'config'
#           of its own, and the two would overwrite each other
```

Trình tạo tự đặt hai thư mục `config/` và `resources/`, còn tên dự án thì thành
tên gói Python. Trùng nhau thì hai đường ghi vào **cùng một file**, và cái sau
thắng - dự án ra thiếu đúng `config/__init__.py`, nơi `import dependency` nằm.
Không lỗi nào phát ra lúc tạo; nó nổ lúc chạy, bằng một thông báo không liên
quan gì tới cái tên.

`xime init xime` còn tệ hơn: gói của dự án **che chính framework**.

Bị từ chối: `config`, `resources`, `xime`, `main`, `test`, `tests`, và mọi tên
trùng một module của **thư viện chuẩn Python** (`json`, `socket`, `logging`...).

### Dự án mới nghe ở `127.0.0.1`, không phải `0.0.0.0`

`application.yml` sinh ra mở sẵn khối `server:` với `host: "127.0.0.1"` kèm giải
thích ngay tại chỗ. Mặc định của **framework** vẫn là `0.0.0.0` và không đổi -
`xime config --print` vẫn in đúng như vậy, và các ứng dụng đang chạy không bị
ảnh hưởng vì chúng không chạy lại trình tạo.

Lý do: `0.0.0.0` nghĩa là **mọi giao diện mạng** - ai định tuyến tới máy này đều
gọi được. Đó là câu trả lời đúng trong container và câu trả lời sai trên laptop
hay máy dùng chung. Trình tạo đặt bạn ở phía hẹp; mở rộng là một quyết định có ý
thức, không phải một mặc định bạn không biết mình đã nhận.

---

## `xime check module-level`

Xem [Chạy nhiều tiến trình](multi-process.md) mục *"Code ở mức module chạy
`N+1` lần"*.

---

## Liên quan

- [Cấu hình](configuration.md) - hai tầng config và cách chúng được nạp.
- [Chạy nhiều tiến trình](multi-process.md) - `share_load()`, và phép dò thứ nhất.
- [Store](store.md) - kho liên tiến trình, và vì sao `lmdb.path` phải khai.

---

[← Cấu hình](configuration.md) · **CLI** · [Testing →](testing.md)
