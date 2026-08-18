# Script kiểm chứng trước khi phát hành

Bốn script này mỗi cái đều **đã bắt được lỗi thật**. Ba cái đầu ra đời trong đợt
kiểm toán 0.7.0; cái thứ tư ra đời từ **F3** của kiểm toán bảo mật 0.7. Chạy lại
trước mỗi lần phát hành - rẻ hơn nhiều so với việc phát hiện ra sau khi người
dùng đã cài.

Không nằm trong gói phát hành (`.claude/` đã bị loại khỏi sdist).

| Script | Trả lời câu hỏi | Đã bắt được |
| --- | --- | --- |
| `check_doc_imports.py` | Mọi dòng `from xime... import X` trong tài liệu có chạy được không? | **16 dòng hỏng**: cả mục JWT của `starters.md` mô tả API không tồn tại; 4 chỗ trỏ `xime.config`/`xime.lifecycle`/`xime.event`/`xime.context` thay vì `xime.core.*` |
| `check_doc_register.py` | Mọi class tài liệu bảo `dependency.register(...)` có dựng được trong DI không? | **2 class chết lúc khởi động** (`ModbusClient`, `OpcuaClient`) - đúng dòng lệnh tài liệu hướng dẫn |
| `find_reexport_gap.py` | `__init__.py` nào import một tên rồi không đưa vào `__all__`? | 9 file làm `mypy --strict` của người dùng báo lỗi ngay ở những import mà tài liệu bảo viết |
| **`check_dep_advisories.py`** | **Bộ SÀN ta khai trong `pyproject.toml` có advisory nào không?** | **26 CVE** ở tổ hợp sàn mà chú thích ngay trên nó khai là "đã cài thử". Rồi ở lần chạy đầu sau khi vá, nó bắt tiếp **5 gói nữa** mà F3 không liệt kê (`aiosmtplib`, `msgpack`, `protobuf`, `cryptography`, `pytest`) - và bắt luôn một mốc tôi vừa đặt sai trong cùng buổi (`cryptography 49` trong khi advisory đã đi tới `50`) |

```bash
python .claude/scripts/check_doc_imports.py .      # quét toàn repo, hoặc truyền docs/
python .claude/scripts/check_doc_register.py
python .claude/scripts/find_reexport_gap.py xime

# cần pip-audit; nên cài ở venv riêng để không đụng môi trường chung 31 app
python .claude/scripts/check_dep_advisories.py --pip-audit path/to/venv/Scripts/python.exe
```

## ⭐ Vì sao script thứ tư soi SÀN chứ không soi môi trường đang chạy

Chạy `pip-audit` trần trên máy dev gần như luôn ra kết quả đẹp, vì máy dev bao
giờ cũng có bản mới. Nhưng sàn là **lời hứa ta ký với người cài từ PyPI**: trong
một môi trường đã ghim sẵn bản cũ, resolver giải ra đúng bộ sàn ta khai và không
có gì phản đối.

> **Máy dev sạch không bảo đảm người cài từ PyPI cũng sạch.**

Script đọc sàn thẳng từ `pyproject.toml` (không giữ bản sao thứ hai sẽ trôi
lệch), pin thành `==`, rồi soi. Nó có một danh sách **CHẤP NHẬN kèm lý do** cho
advisory không có bản vá - hiện đúng một mục (`apscheduler`, xem chú thích trong
`pyproject.toml`). Advisory nào chưa xử thì script **thoát mã 1**.

⚠ Hai chi tiết trong script là hai lần đã vấp, đừng gỡ: cờ `--disable-pip` (thiếu
nó thì pip-audit dựng venv tạm rồi xoá, và bước xoá nổ `PermissionError
[WinError 32]` trên Windows, có lần nuốt luôn kết quả đã in) và việc **đọc sàn
từ file** thay vì chép tay.

## ⭐ Phép thử kèm theo, KHÔNG script hoá được: cài ở đúng sàn rồi chạy hết test

Script trên chỉ trả lời *"sàn có an toàn không"*. Nó **không** trả lời *"sàn có
chạy được không"* - và ngày 2026-08-18 câu thứ hai mới là câu ra nhiều lỗi nhất:

| Tìm ra | Loại |
| --- | --- |
| `aiomqtt>=2.0` + `paho-mqtt>=2.1` **mâu thuẫn nhau** - `pip install xime[mqtt]` ở đúng sàn là bất khả thi | hai sàn cùng một extra chống nhau |
| `pytest>=9.0.3` + `pytest-asyncio>=0.23` nổ `INTERNALERROR` lúc thu thập test, dù **metadata khai là tương thích** (0.23 ghi `pytest>=7.0.0`, không nắp trên) | metadata là lời khai, không phải bằng chứng |
| `sqlalchemy>=2.0` **chưa bao giờ đúng** - lệch 38 bản patch. Hai bức tường: import chết trên Python 3.13+, và starter truyền `pool_size` cho `NullPool` | sàn sai từ ngày viết |

Cách chạy (venv riêng, xong thì xoá thư mục):

```bash
python -m venv .venv-floor
.venv-floor/Scripts/python -m pip install -e ".[dev]" -c constraints-floor.txt
.venv-floor/Scripts/python -m pytest -q
```

Sinh `constraints-floor.txt` từ chính `pyproject.toml` bằng hàm
`_floors_from_pyproject` của script thứ tư - **đừng gõ tay**. Bốn sàn phải bỏ ra
khỏi danh sách pin vì không cài nổi trên Python 3.14 (`pydantic`, `grpcio`,
`grpcio-tools`, `asyncpg`); chúng được ghi chú tại chỗ trong `pyproject.toml`.

> **Một sàn là `>=`, nên pip mặc định cài bản MỚI NHẤT. Sàn sai vì vậy vô hình -
> cho tới ngày có người ghim xuống, và khi đó nó thành vấn đề của họ.**

`check_doc_imports.py` và `check_doc_register.py` in `ALL OK` / `0 fail` khi sạch.

`find_reexport_gap.py` thì **không bao giờ về 0**, và như vậy là đúng. Tính tới
2026-07-30 nó còn báo 11 tên, tất cả đều là **bộ máy nội bộ** dùng trong thân
module chứ không phải API công khai, nên cố ý không nằm trong `__all__`:

- `xime/core/container/__init__.py` (8 tên): `PackageScanner`,
  `DependencyRegistry`, `TypeHintResolver`, `GraphValidator`... đều do
  `XimeContainer` ở ngay dưới dùng. Đường import công khai của chúng là module
  cụ thể (`xime.core.container.switcher`), không phải package.
- `xime/__init__.py` (2 tên): `PackageNotFoundError` và `_dist_version` chỉ dùng
  để đọc version từ metadata.
- `xime/adapters/web/openapi/__init__.py` (1 tên): `registry` mà
  `configure_openapi()` ghi vào.

Cách dùng đúng: chạy script, rồi hỏi từng tên nó báo là **API mà tài liệu bảo
người dùng import** hay không. Nếu có, thêm dấu re-export `X as X` (PEP 484).

## Vì sao đáng giữ

Điểm chung của ba lớp lỗi trên: **test không thể bắt được**, vì test luôn đi
đường tắt mà người dùng thật không có - test import trực tiếp từ module con, gọi
thẳng constructor, và không chạy `mypy` với tư cách người dùng bên ngoài. Kiểm
bằng script là cách rẻ nhất để đóng khoảng trống đó.
