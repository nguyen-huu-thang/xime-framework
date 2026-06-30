# Kiểm toán mã nguồn 0.6.2 (đọc + vá)

> Tạo 2026-07-01. Phạm vi: toàn bộ code mới / thay đổi trong **0.6.0 - 0.6.2**
> (registry tự viết, dynamic binding, middleware markers + CORS, CrudRepository,
> starter mail). Code cũ từ 0.5 trở về đã kiểm toán đầy đủ trong `kiem-toan-0.5.md`.
>
> **TRẠNG THÁI: ĐÃ XỬ LÝ TOÀN BỘ (2026-07-01).** Full suite sau vá:
> **1125 passed, 4 skipped** (tăng 7 test so với 1118; 4 skip là tích hợp
> MQTT/S3 cần broker/MinIO, không đổi).

## Tóm tắt nhanh

Chất lượng mã các mảng mới cao và nhất quán — **không có lỗi CAO** (không gãy
chức năng, không rò rỉ tài nguyên, không race). Mọi phát hiện ở mức Thấp
(nhất quán / hardening nhỏ). Một bài học quan trọng về quy trình audit (xem dưới).

**Cập nhật quan trọng so với bản nháp đầu:** ba phát hiện "Trung" M1a/M1b/M1c
("ba tính năng mới thiếu test") đều là **BÁO ĐỘNG GIẢ** — cả ba tính năng đã có
test đầy đủ từ trước:
- Markers `Inject`/`FromConfig` + `configure_cors`: `tests_temp/routing/test_web_middleware_di.py`
- `CrudRepository`: `tests_temp/sqlalchemy/test_crud_repository.py`

Nguyên nhân sai: lúc audit dùng `Glob` theo **tên file dự đoán**
(`test_markers*.py`, `test_cors*.py`, `test_*crud*.py` trong `web/`) thay vì
**search nội dung** — các file test thật nằm ở vị trí/tên khác convention dự đoán
(`routing/test_web_middleware_di.py`). **Bài học:** kiểm tra "có test cho X
không" phải bằng `Grep` nội dung (tên symbol đang test), không bằng `Glob` tên file.

## Mức độ

**Cao** (gãy chức năng, bảo mật, rò rỉ) · **Trung** (fail-fast thiếu, edge case)
· **Thấp** (code thừa, nhất quán, doc lệch) · **Info** (khoảng trống test).

---

## CAO

*Không phát hiện.*

---

## TRUNG

### M2 - Fallback version lỗi thời ở HAI nơi (mở rộng khi vá)

> **TRẠNG THÁI: ĐÃ XỬ LÝ (2026-07-01).**

- **File:** [xime/adapters/grpc/client/_codegen.py](xime/adapters/grpc/client/_codegen.py),
  [xime/__init__.py:29](xime/__init__.py#L29)
- **Hiện tượng:** `_codegen._framework_xime_version()` trả `"0.5.0"` khi chạy từ
  source (chưa cài) → SDK sinh ra khai báo floor `xime>="0.5.0"` thay vì 0.6.2.
  Đã ghi nhận ở audit 0.5 (note I3) nhưng chưa sửa qua 2 lần bump.
  **Phát hiện mới khi vá:** `xime/__init__.py` cũng có fallback `__version__ =
  "0.6.1"` (lệch pyproject 0.6.2) — quên cập nhật ở bản 0.6.2.
- **Vá:** gộp về MỘT nguồn version:
  - `xime/__init__.py` fallback `"0.6.1"` → `"0.6.2"`.
  - `_codegen._framework_xime_version()` nay ủy quyền `from xime import
    __version__` (xóa logic `_dist_version`/`PackageNotFoundError` trùng lặp), nên
    chỉ còn MỘT literal fallback duy nhất cần đồng bộ với pyproject mỗi lần bump.
- **Lưu ý phát hành:** trước khi push lên PyPI cần đảm bảo literal trùng pyproject.

### ~~M1a/M1b/M1c - Ba tính năng mới thiếu test~~ → BÁO ĐỘNG GIẢ

> **TRẠNG THÁI: BÁO ĐỘNG GIẢ (đã có test đầy đủ từ trước).** Xem "Tóm tắt nhanh".
> Trong lúc xác minh đã **bổ sung 6 ca giá trị** chưa được cover vào file test gốc
> `tests_temp/routing/test_web_middleware_di.py`:
> - markers: `FromConfig` không default → None; `RuntimeConfig` chỉ fetch một lần
>   dù nhiều `FromConfig`.
> - cors: tách biệt theo `server_id`; thiếu YAML → mặc định Starlette đầy đủ;
>   giá trị tường minh thắng YAML; **thứ tự CORS nằm ngoài JwtAuth** (chính là I1).

---

## THẤP (đã vá)

### L1 - `_NO_DEFAULT` sentinel thừa trong `_markers.py`

> **TRẠNG THÁI: ĐÃ XỬ LÝ (2026-07-01).**

- **File:** [xime/adapters/web/_markers.py](xime/adapters/web/_markers.py)
- **Vá:** xóa `_NO_DEFAULT` (dead code), ghi rõ trong docstring `FromConfig`:
  thiếu key → trả `default` (None nếu không truyền), không có chế độ "bắt buộc".

### L2 - Error message `resolve_options` bằng tiếng Việt (cả framework dùng tiếng Anh)

> **TRẠNG THÁI: ĐÃ XỬ LÝ (2026-07-01).** Đổi sang tiếng Anh cho nhất quán với mọi
> error message khác trong framework (framework public lên PyPI → message tiếng
> Anh chuẩn mực). Cập nhật assertion test gốc match `"is not registered"`.

- **File:** [xime/adapters/web/_markers.py:88-94](xime/adapters/web/_markers.py#L88-L94)

### L3 - `DynamicProxy` tạo thừa object khi `setdefault` tìm thấy key có sẵn

> **TRẠNG THÁI: ĐÃ XỬ LÝ (2026-07-01).**

- **File:** [xime/core/container/__init__.py](xime/core/container/__init__.py)
- **Vá:** thay `setdefault(interface, DynamicProxy(...))` bằng `if interface not
  in self._instances: self._instances[interface] = DynamicProxy(...)` — ngữ nghĩa
  giữ nguyên (không đè override), không tạo proxy thừa rồi vứt.

### L4 - `EmailMessage.to`/`cc` nhận list có thể bị mutate ngoài

> **TRẠNG THÁI: ĐÃ XỬ LÝ (2026-07-01).**

- **File:** [xime/starters/mail/_message.py](xime/starters/mail/_message.py)
- **Vá:** `__post_init__` snapshot `to`/`cc` sang `tuple` qua
  `object.__setattr__` (frozen dataclass) → message thật sự bất biến, mutate list
  gốc của caller không ảnh hưởng. Cập nhật test `test_minimal_ok` (giờ so tuple)
  + thêm `test_recipients_snapshot_to_tuple`.

### L5 - `username`/`password` dùng falsy check thay `is not None`

> **TRẠNG THÁI: ĐÃ XỬ LÝ (2026-07-01).**

- **File:** [xime/starters/mail/_smtp.py:134-150](xime/starters/mail/_smtp.py#L134-L150)
- **Vá:** đổi `if self._username:` → `if self._username is not None:` (và
  password) — chuỗi rỗng cấu hình tường minh vẫn được truyền tới SMTP server;
  chỉ giá trị thật sự vắng (null/thiếu key) mới bỏ qua xác thực.

---

## INFO

### I1 - Thứ tự CORS vs JWT → ĐÃ THÊM TEST

Trước đây chỉ kiểm chứng bằng đọc code. Nay có test
`test_cors_sits_outside_jwt_in_stack` (trong `test_web_middleware_di.py`) khẳng
định CORS outermost hơn JwtAuth trong stack → preflight OPTIONS chạy trước xác thực.

### I2 - Mail: chưa có test tích hợp SMTP thật

`tests_temp/mail/test_mail.py` monkeypatch `aiosmtplib.send`. Chưa có test
guard-skipped với SMTP server thật (tương tự MQTT/S3). Ghi nhận để CI sau thêm
`mailhog`/`MailCatcher`. Rủi ro thấp — logic build MIME + chọn TLS đã test kỹ.

### I3 - `_descriptors.py:38-42` nuốt mọi Exception khi `pool.Add`

Tồn từ audit 0.5, chưa sửa. `except Exception: continue` bỏ qua FileDescriptor
hỏng. Rủi ro thấp (dữ liệu generated). Để lại cho bản sau nếu cần.

---

## Điểm tốt cần giữ (không phải lỗi)

- **Registry tự viết thread-safe:** `RLock` + double-checked locking, đường nóng
  (cache hit) không chạm lock. Benchmark ~8x build, ~2x get() so backend cũ.
- **DynamicProxy lifecycle safety:** `_RESERVED` block đúng `post_construct`/
  `pre_destroy`, `isinstance(proxy, PostConstruct/PreDestroy)` trả False, hook
  impl chạy đúng một lần (test `test_07` phủ kỹ).
- **Switcher atomic + GIL:** gán `_current[interface]` là dict mutation đơn,
  atomic dưới GIL, không cần lock — design được ghi chú rõ.
- **Validator hỗ trợ tuple binding:** `_check_bindings` validate mọi impl trong
  tuple khi cờ bật.
- **Mail starter sạch:** lỗi cấu hình (`no sender`) raise trước vòng try, không
  bị đóng gói nhầm thành `MailSendError` transport.
- **`CrudRepository` abstract đúng:** `@property @abstractmethod model` khiến class
  nền abstract, `PackageScanner._is_eligible` bỏ qua đúng — đã có test khẳng định.

---

## Bài học quy trình (cho phiên audit sau)

1. **"Có test cho X không" → dùng `Grep` nội dung, KHÔNG `Glob` tên file.** Test
   thật của một tính năng có thể nằm ở thư mục/tên không theo convention dự đoán
   (vd test markers + cors nằm trong `routing/test_web_middleware_di.py`, không
   phải `web/test_markers.py`). Search theo tên symbol/khái niệm đang test.
2. **Khi `Glob` báo "100 of N files", N-100 file còn lại có thể chứa đúng thứ
   đang tìm** — thu hẹp pattern hoặc đổi sang Grep.
