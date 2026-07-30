# Kiểm toán trước khi phát hành PyPI (0.7.0)

> Bắt đầu 2026-07-29, **hoàn tất 2026-07-30**. Phạm vi: toàn bộ `xime/`
> (191 file) cộng **lớp đóng gói/phát hành** - lớp mà test không chạm tới.
>
> Bối cảnh: repo phát hành là thư mục RIÊNG `D:\code\xime framework`; chủ dự án
> copy mã từ repo này sang khi bên này ổn.

---

# ✅ TRẠNG THÁI - ĐỌC TRƯỚC KHI LÀM TIẾP

## Kết luận

**Mọi phát hiện đã được vá và kiểm chứng lại.** Không còn mục nào mở.

| Mức | Số phát hiện | Trạng thái |
| --- | --- | --- |
| Cao | 3 | đã xử lý |
| Trung | 8 | đã vá |
| Thấp | 5 | đã vá |

Bằng chứng sau khi vá, chạy lại ngày 2026-07-30:

- **1463 passed, 5 skipped** (trước kiểm toán: 1427) - **+36 test mới**, mỗi test
  canh đúng một lỗi đã tìm ra.
- **1463 passed, 9 skipped** khi chạy lại với **đúng bộ floor dependency** khai
  trong `pyproject.toml` (fastapi 0.110.1 + pydantic 2.12.0 + pyyaml 6.0.1).
- `python -m build` + `twine check`: PASSED cả sdist lẫn wheel.
- sdist **230 file / 354 KB** (trước: 400 file / 620 KB), không lẫn `.claude/`,
  `tests_temp/` hay file nhạy cảm nào.
- Cài **từ sdist** vào venv trắng: `import xime` ra `0.7.0`, CLI chạy, 10 module
  không-cần-extra import sạch, web app không cài `[jwt]` khởi động được.
- `ruff check xime/`: còn **1** cảnh báo (`UP046`, thuần style, cố ý giữ).
- `mypy --strict` trên code người dùng: **sạch** (trước: 3 lỗi).
- **343/343 dòng `from xime... import` trong toàn bộ tài liệu đều chạy được**
  (trước: 16 dòng hỏng).

## Điều đáng nhớ nhất từ đợt này

Ba lỗi mức Cao đều **không phải lỗi thuật toán**, mà là lỗi ở chỗ nối giữa các
phần - và cả ba đều **không thể bị 1427 test bắt được**, vì test luôn đi đường
tắt mà người dùng thật không có:

1. **C1** - test luôn chạy trong môi trường đã cài đủ extra, nên chưa ai từng
   khởi động một web app *thiếu* PyJWT. Lỗi có từ **0.2.0** và nằm trong cả 10
   bản đã lên PyPI.
2. **C2** - test luôn gọi `ModbusClient()` trực tiếp; không ai đi qua
   `dependency.register(...)` như tài liệu bảo.
3. **C12** - mọi test server OPC UA đều khai `default=0.0` trên node float, nên
   chưa ai thử công bố một node `bool`.

**Bài học cho lần sau:** với mỗi tính năng, viết ít nhất một test đi **đúng con
đường tài liệu hướng dẫn**, không phải con đường tiện nhất cho test.

Bài học cũ vẫn đúng: kiểm "có test cho X chưa" bằng **Grep nội dung**, không
Glob tên file.

## Phương pháp đã dùng

- Đọc từng file với thái độ phản biện, và **mỗi khi nghi ngờ thì dựng thí
  nghiệm** thay vì suy luận. Cả ba lỗi Cao đều tìm ra theo cách đó.
- Viết **script kiểm chứng tự động** cho những thứ lặp lại: mọi import trong tài
  liệu có chạy không, mọi class tài liệu bảo `register()` có dựng được không.
  Rẻ, và bắt được ngay lớp lỗi mà mắt người bỏ qua.
- Vá xong lỗi nào thì **thêm test canh lỗi đó**, kèm comment nói rõ vì sao 1427
  test cũ không bắt được.

## Phần mã nguồn đã đọc tới đâu

Ghi trung thực để phiên sau không tưởng nhầm là đã soi hết:

| Phần | Mức độ |
| --- | --- |
| `adapters/modbus`, `adapters/opcua` | **đọc từng dòng** (~4.9k dòng) |
| `core/` | **đọc từng dòng** phần cốt lõi: bootstrap, container, config, lifecycle, event, security, transaction, context, exception |
| `starters/jwt`, `starters/localfs`, `starters/storage` | đọc kỹ phần bảo mật (middleware, path traversal) |
| `adapters/web` | đọc phần middleware + TLS + chỗ nối JWT |
| `adapters/grpc`, `adapters/socket`, `adapters/mqtt` | **chưa đọc từng dòng** - đã audit ở 0.5, lần này soi ngang + probe tự động |
| `starters/` còn lại (sqlalchemy, mail, redis, s3, cache, scheduler) | **chưa đọc từng dòng** |
| `cli/`, `testing/` | **chưa đọc từng dòng** |
| Toàn bộ 191 file | quét anti-pattern tự động (sạch) |

Muốn kỹ hơn nữa thì phần chưa đọc ở trên là việc còn lại - nhưng đó là mã đã qua
kiểm toán 0.5/0.6 và không đổi nhiều, nên rủi ro thấp hơn hẳn phần đã soi.

## Kiểm chứng bằng thực nghiệm, ĐỪNG LÀM LẠI

| Việc | Kết quả |
| --- | --- |
| Tải 20 file của 10 bản đã phát hành trên PyPI, quét NỘI DUNG | **Tất cả SẠCH** - không token, không khoá. `-----BEGIN` ở `grpc/tls/_provider.py` là docstring, báo động giả |
| Cơ chế loại trừ của hatchling | Theo `.gitignore`; mẫu trong `include` là kiểu .gitignore nên tên trần khớp **mọi độ sâu** (`"docs"` từng kéo cả `.claude/docs/`) |
| Path traversal của `localfs` | **Chắc chắn**: `../`, tuyệt đối, `C:\`, UNC, `a/b/../../../c` đều bị từ chối; mọi key hợp lệ nằm trong root |
| `bool` truthiness của `ua.Variant` | Luôn `True` kể cả `Variant(0)`/`Variant(False)` -> `data_value.Value.Value if data_value.Value else None` an toàn |
| `asyncua` có tự đọc application URI từ cert không | **Không** - `set_security()` không đụng tới `application_uri` |
| Floor deps thật cài được | pyyaml 6.0 FAIL / 6.0.1 ok; pydantic 2.0-2.11 FAIL / 2.12.0 ok; fastapi 0.110.0 hỏng TestClient / 0.110.1 ok |

## Môi trường đã dựng sẵn (ở `D:\temp\xime\framework`)

    venv_clean\     venv trắng cài wheel 0.7.0 + mypy
    venv_floor2\    venv cài ĐÚNG bộ floor deps - để chứng minh lại
    venv_sdist\     venv cài từ sdist - kiểm gói phát hành thật
    pypi_audit\     20 file của 10 bản đã tải từ PyPI
    dist_check\     sdist + wheel build mới nhất

## Việc đã làm nhưng KHÔNG thuộc kiểm toán

- **`pypi_token.py`** (gốc repo, đã trong `.gitignore`): két sắt token PyPI
  (scrypt + AES-GCM) kèm hướng dẫn phát hành 8 bước. Xem bằng
  `python pypi_token.py --guide`.
- Sửa `.claude/CLAUDE.md`: bỏ thông tin sai "chưa push PyPI".

## Mức độ

**Cao** (gãy chức năng, bảo mật, rò rỉ) · **Trung** (fail-fast thiếu, trải nghiệm
lỗi kém, tuyên bố sai sự thật) · **Thấp** (nhất quán, code thừa, doc lệch).

---

# NHÓM A - Đóng gói & phát hành

Đã build thật (`python -m build`), soi nội dung wheel + sdist, cài vào **venv
sạch** và chạy thử. `twine check` PASSED cho cả hai gói.

## CAO

### A1 - `token.txt` ở repo phát hành sẽ lọt vào sdist ở lần build tới

> **TRẠNG THÁI: ĐÃ XỬ LÝ 2026-07-29 (nguồn rủi ro đã gỡ bỏ).**
>
> Chủ dự án **đã xoá `token.txt`** khỏi `D:\code\xime framework` sau khi cất
> token vào két `pypi_token.py`. Xác minh lại cùng ngày: file không còn,
> `git status` sạch, `find` không thấy file nhạy cảm nào khác trong repo đó.
> Rủi ro "lần build tới nuốt token vào sdist" **không còn**.
>
> **Chưa lộ ra ngoài, đã kiểm chứng bằng bằng chứng cứng:** tải về **toàn bộ 20
> file** của **10 bản đã phát hành trên PyPI** (0.1.0 - 0.6.3) và quét NỘI DUNG
> từng file bên trong, không chỉ tên file. Tìm `pypi-`, `AKIA`, `-----BEGIN`,
> `PRIVATE KEY`, và 40 byte đầu của chính token. **Không một gói nào chứa token
> hay khoá.** Chuỗi `-----BEGIN` bắt được ở `grpc/tls/_provider.py` là **báo động
> giả** - chỉ là docstring mô tả định dạng PEM.
>
> Timestamp khớp lời chủ dự án: `token.txt` ghi lúc 07:34:48, hai gói build lúc
> 06:58:22 / 06:58:26 - token được copy vào **sau** khi build xong.

**Việc phòng ngừa còn để ngỏ (không gấp, chủ dự án quyết):** `.gitignore` của
repo phát hành **vẫn chưa** che `token.txt` / `*.token` / `.pypirc`. Hiện không
có file nào để che nên vô hại, nhưng nếu sau này lại copy credential vào đó thì
cơ chế cũ tái diễn: **hatchling quyết định nội dung sdist theo `.gitignore`**,
file nào không bị che thì vào gói. Ba dòng phòng ngừa:

```gitignore
# Credential phát hành - KHÔNG BAO GIỜ commit, không bao giờ đóng gói
token.txt
*.token
.pypirc
```

Hai lớp bảo vệ đã có sẵn dù không thêm dòng trên: token nay nằm trong két đã mã
hóa (không còn lý do để có file plaintext), và `pypi_token.py --upload` quét gói
tìm credential rồi mới gửi.

- **File:** `D:\code\xime framework\token.txt` (201 byte, sửa lần cuối 2026-07-29
  07:34) và `D:\code\xime framework\.gitignore`.
- **Hiện tượng:** thư mục phát hành chứa `token.txt` - gần như chắc chắn là **PyPI
  API token**. Nó **chưa** bị commit (`git ls-files` không thấy, `git log --all`
  trống) nhưng cũng **không** có trong `.gitignore`, nên `git status` đang hiện
  `?? token.txt`.
- **Vì sao nguy hiểm:** hatchling quyết định nội dung sdist **theo `.gitignore`**.
  Đã kiểm chứng ở repo này: `__pycache__/` có trong `.gitignore` -> không vào
  sdist; `.claude/` không có trong `.gitignore` -> **có** trong sdist. Suy ra ở
  repo phát hành, lần `python -m build` tiếp theo sẽ **đóng gói `token.txt` vào
  `xime-0.7.0.tar.gz`**, và `twine upload` sẽ đẩy nó lên PyPI - nơi ai cũng tải
  được. Token PyPI lộ = người khác đẩy được bản giả mạo dưới tên `xime`.
- **Chưa xảy ra:** sdist `xime-0.6.3.tar.gz` hiện có trong `dist/` **sạch** (170
  file, chỉ `xime/` + metadata, không có file nhạy cảm) vì nó được build lúc
  06:58, trước khi `token.txt` được ghi lúc 07:34.
- **Cách vá (làm ở repo phát hành, trước lần build 0.7.0):**
  1. Thêm vào `.gitignore` của repo phát hành:

     ```gitignore
     # Credential phát hành - KHÔNG BAO GIỜ commit, không bao giờ đóng gói
     token.txt
     *.token
     .pypirc
     ```

  2. Sau khi build, **kiểm lại** trước khi upload:

     ```bash
     python -c "import tarfile; print([n for n in tarfile.open('dist/xime-0.7.0.tar.gz').getnames() if 'token' in n.lower()])"
     ```

  3. Cân nhắc **thu hồi và cấp lại token** nếu không chắc nó từng nằm trong một
     gói đã upload. Kiểm nhanh: tải lại sdist các bản đã phát hành từ PyPI và
     soi nội dung.
- **Đề xuất mạnh hơn:** đừng để token trong thư mục dự án. Dùng biến môi trường
  `TWINE_PASSWORD`, hoặc `~/.pypirc` ngoài repo, hoặc Trusted Publishing của
  PyPI (không cần token dài hạn).

---

## TRUNG

### A2 - sdist đóng gói cả `.claude/` và `tests_temp/`

> **TRẠNG THÁI: ĐÃ VÁ 2026-07-30.** Khai `[tool.hatch.build.targets.sdist]`
> whitelist **neo vào gốc** (`"/xime"`, `"/docs"`, ...). Kết quả đo lại:
> 400 -> 230 file, 620 -> 354 KB, không rò rỉ.
>
> **Cạm bẫy đã vấp khi vá:** mẫu trong `include` theo kiểu .gitignore, nên tên
> trần khớp ở MỌI độ sâu - lần vá đầu ghi `"docs"` và nó kéo luôn
> `.claude/docs/` (27 file) vào gói. Dấu `/` đầu là bắt buộc.

- **File:** `pyproject.toml` (thiếu khai báo `[tool.hatch.build.targets.sdist]`).
- **Hiện tượng:** `xime-0.7.0.tar.gz` có **400 file**, trong đó chỉ 190 là mã
  nguồn. Phần thừa: `tests_temp/` (130 file), `.claude/` (39 file, gồm
  `settings.local.json`, `.mcp.json`, và **toàn bộ tài liệu chiến lược nội bộ**:
  kế hoạch 0.8 chưa làm, các báo cáo kiểm toán, backlog, wishlist).
- **Đã kiểm:** `.claude/settings.local.json` và `.mcp.json` **không chứa
  credential** - chỉ có allowlist quyền và đường dẫn máy cá nhân
  (`d:\code\xime\xime framework`). Nên đây là **Trung**, không phải Cao.
- **Vì sao vẫn nên vá:** (a) công bố kế hoạch nội bộ chưa chốt ra công chúng;
  (b) lộ đường dẫn máy cá nhân; (c) sdist phình gấp ~3 lần (620KB so với 186KB
  của 0.6.3 ở repo phát hành).
- **Ghi chú thực tế:** repo phát hành hiện **không có** `.claude/` hay
  `tests_temp/` nên sdist bên đó đang sạch. Nhưng cách vá đúng là khai tường
  minh trong `pyproject.toml` để không phụ thuộc vào việc copy tay có sót hay
  không.
- **Cách vá:**

  ```toml
  [tool.hatch.build.targets.sdist]
  include = ["xime", "README.md", "LICENSE", "CHANGELOG.md", "pyproject.toml"]
  ```

  (Hoặc `exclude = [".claude", "tests_temp", "docs"]` nếu muốn giữ `docs/`.)
  **Quyết định cần chủ dự án chốt:** có muốn giữ `tests_temp/` và `docs/` trong
  sdist không - nhiều dự án giữ test để người dùng chạy lại được, nhưng tên
  `tests_temp` thì khó gọi là chuyên nghiệp.

### A3 - Ba module ném `ModuleNotFoundError` thô khi thiếu extra

> **TRẠNG THÁI: ĐÃ VÁ 2026-07-30**, nhưng theo cách khác đề xuất ban đầu.
>
> `grpc` và `sqlalchemy`: bọc import, ném **`ImportError`** (không phải
> `RuntimeError` như bản ghi cũ đề xuất) với thông điệp nêu tên extra. Lý do đổi:
> chính framework dựa vào `except ImportError` quanh package grpc để hiểu "chưa
> cài extra, bỏ qua" (`core/bootstrap/application.py`, `orchestrator.py`) - ném
> `RuntimeError` sẽ biến những chỗ bỏ qua êm ái đó thành lỗi sập lúc khởi động
> cho **mọi** app không cài extra. Ngoài ra ở thời điểm IMPORT thì `ImportError`
> mới là kiểu đúng.
>
> `jwt`: không bọc, mà **nạp PyJWT lười** - vì chỉ bọc thôi thì không sửa được
> C1 (xem NHÓM C). Import package giờ sạch, dùng thật mới nổ.

- **File:** `xime/adapters/grpc/__init__.py`,
  `xime/starters/sqlalchemy/__init__.py`, `xime/starters/jwt/__init__.py`.
- **Hiện tượng:** cài `pip install xime` (không extra) rồi import, kết quả:

  | Module | Kết quả |
  | --- | --- |
  | `xime.adapters.web` / `socket` / `mqtt` / `modbus` / `opcua` | import OK |
  | `xime.starters.cache` / `redis` / `storage` / `localfs` / `s3` / `scheduler` / `mail` | import OK |
  | **`xime.adapters.grpc`** | `ModuleNotFoundError: No module named 'grpc'` |
  | **`xime.starters.sqlalchemy`** | `ModuleNotFoundError: No module named 'sqlalchemy'` |
  | **`xime.starters.jwt`** | `ModuleNotFoundError: No module named 'jwt'` |

- **Đối chiếu:** mqtt/modbus/opcua làm đúng - import package OK, và khi thực sự
  dùng thì nổ với thông điệp dẫn đường:

  ```text
  RuntimeError: ModbusAdapter requires pymodbus. Run: pip install 'xime[modbus]'
  ```

- **Vì sao đáng vá, đặc biệt với `jwt`:** thông điệp `No module named 'jwt'` dẫn
  người dùng đi sai đường **rất tệ** - trên PyPI có một package tên `jwt` (khác
  hoàn toàn `PyJWT`, gần như bỏ hoang). Người dùng đọc lỗi rồi
  `pip install jwt` sẽ cài nhầm thư viện và hỏng theo cách khó lần ra. Framework
  đã tuyên bố nguyên tắc "import lười, extra riêng" - ba chỗ này vi phạm chính
  nguyên tắc của mình.
- **Cách vá:** bọc import trong `__init__.py` của ba module, ném `RuntimeError`
  với thông điệp cùng khuôn `Run: pip install 'xime[...]'`.

### A4 - Dependency floor khai trong `pyproject.toml` chưa từng được kiểm chứng, và tổ hợp tối thiểu KHÔNG cài được

> **TRẠNG THÁI: ĐÃ VÁ 2026-07-30.** Floor mới:
> `fastapi>=0.110.1`, `pydantic>=2.5`, `pyyaml>=6.0.1` - mỗi con số đều **cài
> thử** rồi mới ghi, kèm comment giải thích trong `pyproject.toml`.
>
> Phát hiện ngoài dự kiến khi dò: **fastapi 0.110.0 ghim starlette 0.36.3**, mà
> `TestClient` của bản đó gọi `httpx.Client(app=...)` - httpx 0.28 đã xoá tham số
> này. Nghĩa là mọi test mà **ứng dụng** tự viết cho route của mình sẽ chết
> `TypeError`. 0.110.1 là bản đầu tiên không dính.
>
> Đã chạy **full suite với đúng bộ floor**: 1454 passed, 9 skipped (venv_floor2).
> Chính lần chạy đó lòi ra C16 (thiếu `python-multipart`).

- **File:** `pyproject.toml`, khối `dependencies`.
- **Hiện khai:** `fastapi>=0.110.0`, `pydantic>=2.0`, `pyyaml>=6.0`.
- **Thử thật trên Python 3.14:**

  ```text
  pip install "fastapi==0.110.0" "pydantic==2.0" "pyyaml==6.0"
    -> pyyaml==6.0 KHÔNG BUILD ĐƯỢC ('build_ext' object has no attribute 'cython_sources')
    -> fastapi==0.110.0 và pydantic==2.0 XUNG ĐỘT (ResolutionImpossible)
  ```

- **Nghĩa là:** bộ ba floor đang khai là một tổ hợp **không tồn tại**. Người dùng
  bình thường không vấp (pip lấy bản mới nhất), nhưng ai dùng constraint file
  hoặc môi trường đã pin sẵn bản cũ sẽ vấp, và metadata đang **nói sai sự thật**
  về mức tối thiểu thực sự hỗ trợ.
- **Cách vá:** nâng floor lên mức đã kiểm chứng chạy được trên Python 3.12-3.14,
  rồi **chạy full suite với đúng bộ floor đó** để chứng minh. Việc này cần làm
  cho cả extras (`sqlalchemy>=2.0`, `pyjwt>=2.8`... cũng chưa ai thử).
- **Ghi chú:** `apscheduler>=4.0.0a6` đã có comment giải thích rõ vì sao phải ghi
  floor alpha - đó là kiểu chú thích mà các floor còn lại đang thiếu.

---

## Đã kiểm và ĐẠT (không cần làm gì)

| Hạng mục | Kết quả |
| --- | --- |
| `python -m build` | sdist + wheel build sạch, không cảnh báo |
| `twine check dist/*` | PASSED cả hai |
| Nội dung **wheel** | 195 file: 190 `.py` + `py.typed` + METADATA/WHEEL/RECORD/entry_points/LICENSE. Không có `__pycache__`, không file rác |
| `py.typed` | có trong wheel, cài ra đúng chỗ -> type checker của người dùng đọc được |
| LICENSE | đóng gói đúng vào `dist-info/licenses/` (PEP 639) |
| Cài wheel vào venv sạch | OK, chỉ kéo về đúng 3 dep lõi (fastapi, pydantic, pyyaml) + phụ thuộc bắc cầu |
| `import xime` | OK, `xime.__version__ == "0.7.0"` khớp `pyproject.toml` |
| CLI `xime` | entry point hoạt động: `xime` và `xime grpc` in đúng usage |
| Thông điệp thiếu extra (mqtt/modbus/opcua) | Đúng khuôn, có dẫn đường `pip install 'xime[...]'` |

---

# NHÓM B - Mã nguồn

> Tiến độ: đã quét anti-pattern toàn cục (189 file) + đọc `core/container/`.
> Phần đọc từng file của `adapters/` và `starters/` **chưa xong** - xem mục "Còn
> phải làm" ở cuối.

## TRUNG

### B1 - `__all__` bị dùng cho DI scanning làm hỏng type-checking của người dùng

> **TRẠNG THÁI: ĐÃ VÁ 2026-07-30** bằng redundant alias PEP 484 ở 9 file
> `__init__.py`. Cơ chế DI **không đổi một chút nào** (scanner vẫn chỉ đọc
> `__all__`), `mypy --strict` trên code người dùng nay sạch.
>
> Cách tìm đủ tập file cần sửa: script AST liệt kê mọi tên được import trong một
> `__init__.py` nhưng vắng trong `__all__`. Grep tay sẽ sót, vì `__all__` có hai
> dạng (`__all__ = [...]` và `__all__: list[str] = []`).

- **File:** `xime/starters/jwt/__init__.py`, `xime/starters/cache/__init__.py`,
  `xime/starters/sqlalchemy/__init__.py`, `xime/starters/s3/__init__.py` và mọi
  `__init__.py` khác khai `__all__` rút gọn.
- **Bối cảnh:** theo `rules/coding.md`, framework dùng `__all__` để **điều khiển
  DI scanner** ("Có `__all__` → chỉ scan các class được export"). Nên `__all__`
  của các starter cố ý chỉ liệt kê class DI-managed, còn config object và
  Protocol thì import vào nhưng **không** đưa vào `__all__` - dù chúng là public
  API mà tài liệu bảo người dùng import.
- **Hậu quả (đã kiểm chứng):** gói ship `py.typed` và khai classifier
  `Typing :: Typed`, tức cam kết hỗ trợ type checking. Người dùng viết code
  bình thường rồi bật `mypy --strict`:

  ```python
  from xime.starters.jwt import configure_jwt, KeyContext
  from xime.starters.cache import CacheService
  ```

  ```text
  error: Module "xime.starters.jwt" does not explicitly export attribute "configure_jwt"
  error: Module "xime.starters.jwt" does not explicitly export attribute "KeyContext"
  error: Module "xime.starters.cache" does not explicitly export attribute "CacheService"
  ```

  Ba lỗi, đúng ở những import mà chính tài liệu của framework hướng dẫn.
- **Cách vá (rẻ, KHÔNG đụng cơ chế DI):** dùng **redundant alias**, cách chuẩn
  PEP 484 để đánh dấu re-export tường minh mà không cần thêm vào `__all__`:

  ```python
  from ._config import JwtMiddlewareConfig as JwtMiddlewareConfig
  from ._config import configure_jwt as configure_jwt
  from ._key_context import KeyContext as KeyContext
  ```

  DI scanner vẫn đọc `__all__` y như cũ nên hành vi đăng ký không đổi một chút
  nào; mypy/pyright thì hết báo lỗi. Cần rà mọi `__init__.py` có `__all__` rút
  gọn (31 cảnh báo `F401` của ruff chỉ đúng chỗ này).
- **Hướng dài hạn (không làm ở 0.7):** tách hai vai trò - cho DI scanner đọc một
  khóa riêng (vd `__xime_scan__`) và trả `__all__` về đúng nghĩa Python. Đây là
  thay đổi API của framework, để 0.8/0.9 quyết.

---

## THẤP

### B2 - Teardown nuốt lỗi không log

> **TRẠNG THÁI: ĐÃ VÁ 2026-07-30** - thêm `logger.debug(..., exc_info=True)` ở cả
> hai chỗ nuốt lỗi trong `SocketAdapter.stop()` (đóng server và xoá file socket).

- **File:** `xime/adapters/socket/_adapter.py:135`
  (`await self._server.wait_closed()` bọc `except Exception: pass`).
- **Hiện tượng:** lỗi lúc đóng server bị nuốt hoàn toàn, không một dòng log.
- **Đối chiếu:** `application.py:171-177` log `logger.exception(...)` khi adapter
  teardown lỗi, và modbus/opcua (0.7) dùng `logger.debug(..., exc_info=True)`.
  Chỗ này là ngoại lệ duy nhất còn lại.
- **Cách vá:** thêm `logger.debug("...", exc_info=True)`.

### B3 - Import thừa và style lỗi thời

> **TRẠNG THÁI: ĐÃ VÁ 2026-07-30** - `ruff --fix` xử lý 96 mục; `xime/` nay còn
> đúng **1** cảnh báo (`UP046`, thuần style, cố ý giữ vì đổi sang cú pháp
> generic PEP 695 là đổi hình dạng API công khai).
>
> **Còn để ngỏ có chủ đích:** `tests_temp/` chưa lint bao giờ (176 cảnh báo).
> Không gấp - từ bản này `tests_temp/` **không còn nằm trong sdist**.

- **Số liệu ruff trên `xime/`** (112 cảnh báo, không có cảnh báo nào là lỗi
  logic - không `F821`, không `B008`, không mutable default):

  | Rule | Số | Loại |
  | --- | --- | --- |
  | `UP037` quoted-annotation | 48 | style (thừa dấu nháy vì đã có `from __future__ import annotations`) |
  | `F401` unused-import | 31 | phần lớn là re-export ở `__init__.py` -> **thuộc B1**; vài chỗ thừa thật (`dataclasses.field`, `typing.Any` trong `grpc/codefirst/_config.py`, `grpc/interceptors/_config.py`) |
  | `UP035` deprecated-import | 17 | `typing.Callable` -> `collections.abc.Callable` |
  | `I001` unsorted-imports | 14 | style |
  | `UP017`, `UP046` | 2 | style |

- **Ghi chú:** `ruff` **không** nằm trong extra `dev` của `pyproject.toml` dù
  `[tool.ruff]` đã được cấu hình sẵn - nên chưa ai từng chạy nó trên code cũ.
  Code 0.7 (modbus/opcua) đã sạch ruff hoàn toàn.

---

## Đã kiểm và ĐẠT

| Trục soi | Kết quả trên toàn bộ 189 file |
| --- | --- |
| `except:` trần | **không có chỗ nào** |
| `except ...: pass` | 5 chỗ, **cả 5 đều chính đáng** (teardown socket ×3, `_unlink_quiet` bắt đúng `FileNotFoundError`/`IsADirectoryError`, `except CancelledError: pass` trong reap loop) |
| `TODO`/`FIXME`/`XXX`/`HACK` còn sót | **không có** |
| `print(` trong code production | **không có** (chỉ trong `cli/`) |
| `time.sleep` trong code async | **không có** |
| Mutable default argument | **không có** |
| `asyncio.create_task` mất reference | **không có** - cả 3 chỗ nền (`grpc/client/_channel.py`, `core/event/bus.py`, và các adapter) đều giữ strong-ref bằng `set` + `add_done_callback(discard)`, có comment giải thích đúng lý do (asyncio chỉ giữ weak-ref) |
| `core/container/registry.py` | double-checked locking đúng, warm path không chạm lock, sentinel `_MISSING` phân biệt "chưa cache" với "cache giá trị None", `_building` chống đệ quy, `finally` dọn đúng |

---

# NHÓM C - Phát hiện của phiên 2026-07-30 (đọc mã nguồn)

Toàn bộ nhóm này **đã vá**. Điểm chung: không có mục nào là lỗi thuật toán - tất
cả nằm ở **chỗ nối** giữa các phần, và không một cái nào bị 1427 test bắt được.

## CAO

### C1 - Mọi web app không cài extra `[jwt]` sập lúc khởi động

- **File:** `xime/adapters/web/_adapter.py::_add_jwt_middleware` +
  `xime/starters/jwt/{__init__,_signer,_verifier}.py`.
- **Cơ chế:** hàm đó chạy ở **mọi** lần `build_app`, và dòng đầu tiên là
  `from xime.starters.jwt._config import jwt_registry` - chỉ để xem
  `configure_jwt()` có được gọi hay không. Nhưng import một submodule thì Python
  chạy `__init__.py` của package trước, mà file đó `from ._signer import ...`,
  và `_signer.py` có `import jwt` ở mức module. Cái `try/except ImportError` ở
  dưới chỉ bọc `_middleware`, không bọc dòng đầu.
- **Tái hiện (venv trắng, chỉ cài `pip install xime`):**

  ```text
  >>> WebAdapter._add_jwt_middleware(FastAPI())
  ModuleNotFoundError: No module named 'jwt'
  ```

- **Tuổi của lỗi:** có từ **0.2.0**. Kiểm bằng cách mở `xime/starters/jwt/__init__.py`
  trong wheel của 0.2.0 / 0.4.0 / 0.5.0 / 0.6.3 tải từ PyPI - cả bốn đều import
  `_signer`/`_verifier` ở mức module.
- **Vì sao test không bắt:** test luôn chạy trong môi trường đã cài đủ extra.
- **Cách vá:** `starters/jwt/_pyjwt.py` - hàm `pyjwt()` nạp lười, ném
  `RuntimeError` có nêu rõ `pip install 'xime[jwt]'` **và** cảnh báo rằng trên
  PyPI có một package tên đúng là `jwt` khác hẳn PyJWT. `_signer`/`_verifier`
  gọi hàm đó. `_add_jwt_middleware` **dò PyJWT ngay lúc khởi động** khi
  `jwt_registry` có config - nếu không, lỗi sẽ trôi tới request đầu tiên mang
  token, tệ hơn hẳn.

### C2 - `dependency.register(ModbusClient)` / `(OpcuaClient)` chết lúc khởi động

- **File:** `xime/adapters/modbus/_client.py`, `xime/adapters/opcua/_client.py`.
- **Cơ chế:** `def __init__(self, device: str = DEFAULT_DEVICE)`. Type hint chính
  là **tín hiệu opt-in cho DI** (`rules/coding.md`), nên container đi tìm binding
  cho `str`:

  ```text
  UnregisteredDependencyException
    Class     : ModbusClient
    Dependency: str
  ```

- **Đúng dòng tài liệu hướng dẫn:** `docs/vn/modbus.md:84`, `docs/vn/opcua.md:68`.
- **Vì sao test không bắt:** mọi test gọi `ModbusClient()` trực tiếp, không đi
  qua container.
- **Cách vá:** bỏ annotation ở đúng tham số đó - đây chính là cơ chế opt-out mà
  `rules/coding.md` mô tả ("không có hint = developer không muốn framework quản
  lý dep đó"), không phải chiêu lách. Có comment cấm thêm `: str` lại.
- **Sửa gốc rễ (chủ dự án chốt 2026-07-30):** container nay coi **tham số có giá
  trị mặc định là tham số KHÔNG bắt buộc** - không ai cấp được kiểu của nó thì bỏ
  tham số ra khỏi kế hoạch dựng và để Python dùng default. Tương đương
  `@Autowired(required=false)` của Spring. Hiện thực:
  `XimeContainer._drop_unsatisfiable_optional_deps()`, áp cho cả tham số
  constructor và tham số của factory method trong `dependency.configure(...)`.
  **Nhờ vậy annotation `device: str` đã được trả lại** - không cần cách vòng nữa.
  - Hoá ra **không** phải đổi hợp đồng `ClassDeps` như lo ban đầu: `registry`
    vốn đã bỏ qua dep không nằm trong plan, nên chỉ cần tỉa `resolved` trước khi
    dựng graph là đủ. 9 dòng logic.
  - **Fail-fast vẫn nguyên ở chỗ quan trọng:** tham số KHÔNG có default mà thiếu
    implementation vẫn nổ. **Đánh đổi đã chấp nhận:** tham số `Protocol` có
    default mà thiếu binding giờ nhận default thay vì nổ - chọn quy tắc thống
    nhất để gói được trong một câu người đọc nhớ nổi.
  - Test canh: `tests_temp/DI/test_08_optional_dependencies.py` (9 test, gồm cả
    các ca phải TIẾP TỤC nổ).
- **Test canh:** `tests_temp/{modbus,opcua}/test_di.py`.

### C12 - Server OPC UA không công bố được node không phải `float`

- **File:** `xime/adapters/opcua/_server.py::_create_nodes` + `_model.py`.
- **Cơ chế:** biến OPC UA lấy kiểu dữ liệu **từ giá trị lúc tạo** và về sau
  không nhận giá trị khác kiểu. Node không khai `default=` được tạo bằng `0.0`
  (Double), nên `write_value(True)` bị server từ chối `BadTypeMismatch` - và lỗi
  đó bị nuốt trong `except` của `refresh_once`, để node đứng im ở `0.0` **mãi
  mãi**, không một dấu hiệu nào cho người gọi.
- **Tái hiện (server asyncua thật):** model 4 node `bool`/`str`/`int`/`float`
  không khai `default=` -> đọc từ client ra `0.0` cho **cả bốn**.
- **Vì sao test không bắt:** cả hai node trong model test (`Boiler`) đều là
  `float` **và** đều khai `default=0.0`.
- **Cách vá:** `@node_model` đọc `typing.get_type_hints(cls)` và ghi vào
  `OpcuaNode.declared_type`; server suy giá trị khởi tạo theo thứ tự
  `default=` -> annotation -> **StartupException nêu tên node**. Không đoán:
  đoán sai chính là cái đã tạo ra lỗi này.
- **Test canh:** `tests_temp/opcua/test_server.py::TestNodeDataTypes` (3 test).

## TRUNG

### C3 - Tài liệu nêu API không tồn tại (16 dòng import không chạy được)

- Toàn bộ mục JWT của `docs/{vn,en}/starters.md` mô tả một API **khác hẳn** thực
  tế: `JwtConfig`, `JwtSigner`, `JwtVerifier`, `configure_jwt_middleware` -
  không cái nào tồn tại. Thực tế là `JwtMiddlewareConfig`, `JwtTokenSigner`,
  `JwtTokenVerifier`, `configure_jwt`, và chữ ký hàm cũng khác (`sign(payload,
  key_context)` chứ không phải `sign(payload)`).
- Bốn chỗ khác trỏ `xime.config` / `xime.lifecycle` / `xime.event` /
  `xime.context` thay vì `xime.core.*`. Riêng `from xime.context import
  current_user, request_id` thì **cả hai tên đều không tồn tại** - API thật là
  `request_context.get("...")` và `identity.get()`.
- **Cách tìm:** script `check_doc_imports.py` - regex mọi dòng
  `from xime... import X` trong `**/*.md` rồi `importlib` + `hasattr` từng tên.
  Đây là loại kiểm tra nên **giữ lại và chạy mỗi lần trước khi phát hành**.
- **Đã vá:** viết lại mục JWT theo API thật, sửa 4 đường dẫn module, viết lại
  mục Request Context. Nay **343/343 dòng import trong toàn repo đều chạy**.

### C10 - OPC UA thiếu `application_uri`, khiến Sign/SignAndEncrypt vô dụng với cert thật

- **Cơ chế:** ở hai mức bảo mật đó, server đối chiếu URI client khai lúc mở
  session với **URI trong SubjectAltName của cert client**; lệch nhau thì từ chối
  bằng `BadCertificateUriInvalid` - thông báo không hề nhắc tới URI.
- **Đã kiểm:** `asyncua` để mặc định `urn:example.org:FreeOpcUa:opcua-asyncio` và
  **không** tự đọc URI từ cert (đọc source `Client.set_security`). Nghĩa là cert
  tự sinh gần như chắc chắn bị từ chối.
- **Đã vá:** thêm `application_uri` cho cả `OpcuaConfig` và `OpcuaServerConfig`,
  nối vào `client.application_uri` / `Server.set_application_uri()`, + tài liệu
  hai thứ tiếng (có mục riêng "chỗ hay vấp nhất khi bật bảo mật").
- **Ghi chú thẳng thắn:** test bảo mật OPC UA hiện chỉ kiểm việc **dựng chuỗi
  policy**, **chưa từng bắt tay Sign/SignAndEncrypt thật**. Tuyên bố "đủ ba mức"
  dựa trên unit test ánh xạ, không phải handshake. Muốn chắc thì cần sinh cert +
  chạy server/client thật - việc còn lại.

### C13 - Một node OPC UA ghi hỏng làm hỏng cả model

- `refresh_once()` bọc **cả vòng lặp node** trong một `try`, nên node lỗi đầu
  tiên làm mọi node sau nó đứng im ở giá trị khởi tạo. Chính điều này làm C12
  nặng thêm: `level=1.5` hợp lệ cũng không được đẩy.
- **Đã vá:** mỗi node một `try`, log nêu đúng tên node và NodeId có lỗi.

### C14 - `Application.use()` chỉ chặn trùng được ba trong sáu adapter

- Chốt chặn đọc `getattr(adapter, "_server_id", None)`, mà `MqttAdapter` đặt tên
  định danh là `_client_id`, `ModbusAdapter` là `_device`, `OpcuaAdapter` là
  `_server`; hai server adapter không có định danh nào.
- **Đo thật:** WebAdapter x2 -> rejected; Modbus/Opcua/Mqtt/ModbusServer x2 ->
  **ACCEPTED**.
- **Hệ quả:** hai vòng poll đập vào cùng một PLC, hai client thay nhau trên một
  `ModbusConnection` dùng chung; với MQTT thì broker chỉ cho **một** phiên trên
  mỗi client id nên hai adapter đánh nhau trong vòng lặp reconnect; hai server
  adapter thì tranh cổng.
- **Đã vá:** cả sáu adapter khai `_server_id`. Chọn cách này thay vì đổi `use()`
  để tránh nhét tên thuộc tính nội bộ của từng adapter vào core.
- **Test canh:** `tests_temp/multi_server/test_multi_server.py::TestDuplicateDetectionCoversEveryAdapter`.

### C16 - Upload file cần `python-multipart` mà không extra nào khai

- Tìm ra **nhờ** lần chạy full suite ở venv floor: 15 ERROR
  `Form data requires "python-multipart" to be installed`.
- `xime[web]` khai `uvicorn[standard]` nhưng không khai `fastapi[standard]`, mà
  `python-multipart` chỉ nằm trong extra `standard` của FastAPI. Máy dev có sẵn
  gói này do thứ khác kéo về, nên không ai thấy.
- Người dùng `pip install xime[web]` rồi dùng `save_upload` (có tài liệu ở
  `docs/*/file-storage.md`) sẽ chết lúc chạy.
- **Đã vá:** thêm `python-multipart>=0.0.7` vào extra `web`.

### C4 - `count` bị bỏ qua im lặng trên field Modbus kiểu số

- `Holding(0, type="uint16", count=5)` -> `word_count` vẫn 1. Người viết mong 5
  giá trị, nhận 1, không lỗi lúc khai báo cũng không lỗi lúc đọc.
- **Đã vá:** `ValueError` ngay lúc định nghĩa class - `count` chỉ có nghĩa với
  vùng bit và `type="string"`.

### C15 - Scheme `Bearer` phân biệt hoa thường

- RFC 7235 quy định tên scheme **không** phân biệt hoa thường. Client gửi
  `bearer <token>` nhận 401 kèm "Missing authorization token" - nói header không
  có trong khi nó nằm ngay đó.
- **Đã vá** + 3 test tham số hoá (`bearer` / `BEARER` / `BeArEr`).

## THẤP

### C5 - Modicon 6 chữ số không hỗ trợ, thông điệp lỗi không chỉ đường

`modicon=400001` chỉ báo "ngoài dải 40001-49999". Đã sửa thông điệp để nêu rõ
dạng 6 chữ số không được nhận và chỉ sang cách dùng địa chỉ 0-based.
**Việc còn lại (wishlist, không phải lỗi):** hỗ trợ hẳn dạng 6 chữ số - dải
400001-465536 không giao với dải 5 chữ số nên phân biệt được, và thiết bị có hơn
9999 thanh ghi là chuyện thường.

### C8 - Docstring `ModbusConfig` sai về fallback

Nói "mọi field trừ host/port/unit rơi về khối chung", nhưng `pick()` có fallback
cho cả `port` và `unit`. Đã sửa docstring theo code.

### C17 - `CLAUDE.md` nói cấu hình runtime là "YAML + env vars"

Thực tế env var **chỉ chọn file profile** (`XIME_ENV`/`APP_ENV`); không có nội
suy `${VAR}` và không có override kiểu `XIME_SERVER__PORT`. Tài liệu người dùng
(`docs/*/configuration.md`) mô tả đúng; chỉ dòng trong `CLAUDE.md` là quá lời.

---

# Ghi nhận, KHÔNG vá (cân nhắc cho 0.8)

Những mục dưới đây là **quan sát có cơ sở**, không phải lỗi cần vá gấp. Ghi lại
để phiên sau không phải phát hiện lại.

1. **Modbus mất kết nối giữa chừng** dựa vào auto-reconnect của pymodbus; vòng
   `_run_forever` chỉ bắt lỗi ở lần connect đầu, nên đọc lỗi sẽ log mãi mà không
   dựng lại kết nối từ phía Xime.
2. **`@node_model(namespace=...)` và ns index trong NodeId là hai thứ rời nhau.**
   Namespace được `register_namespace()` nhưng NodeId lấy nguyên văn, nên hai thứ
   có thể lệch mà không ai báo. **Đã ghi rõ trong `docs/{vn,en}/opcua.md`** thay vì
   đổi hành vi - đổi thì phá NodeId của mọi model đang chạy.
3. **`LifecycleManager`**: instance mà `post_construct()` ném lỗi giữa chừng sẽ
   **không** được gọi `pre_destroy()`. **CHỦ DỰ ÁN ĐÃ CHỐT (2026-07-30): giữ
   nguyên.** Lý do: gọi `pre_destroy` trên object khởi tạo dở sẽ ném lỗi thứ hai
   (AttributeError vì field chưa tồn tại) và che mất lỗi gốc. Bù lại, quy tắc
   "mở được đến đâu, tự dọn đến đó" đã thành hợp đồng chính thức: ghi trong
   docstring `PostConstruct` (hooks.py) và mục Lifecycle của
   `docs/{vn,en}/core-concepts.md`, kèm mẫu try/except và mẫu `AsyncExitStack` +
   `pop_all()` cho nhiều tài nguyên. Nhân tiện phát hiện mục Lifecycle của
   core-concepts.md mô tả API bịa (`PostConstruct.register(cls, "on_start")` -
   không tồn tại; API thật là đặt đúng tên method) - đã viết lại.
4. **`public_paths` của JWT khớp đường dẫn chính xác**, không prefix. Hệ quả nhỏ:
   bật JWT thì `/docs` và `/openapi.json` của Swagger bị bảo vệ nếu không khai.
   **Đã ghi rõ trong `docs/{vn,en}/starters.md`** - khớp chính xác an toàn hơn khớp
   tiền tố, nên giữ hành vi và nói rõ ra.
