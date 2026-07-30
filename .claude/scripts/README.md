# Script kiểm chứng trước khi phát hành

Ba script này ra đời trong đợt kiểm toán 0.7.0 và mỗi cái đều **đã bắt được lỗi
thật**. Chạy lại trước mỗi lần phát hành - rẻ hơn nhiều so với việc phát hiện ra
sau khi người dùng đã cài.

Không nằm trong gói phát hành (`.claude/` đã bị loại khỏi sdist).

| Script | Trả lời câu hỏi | Đã bắt được |
| --- | --- | --- |
| `check_doc_imports.py` | Mọi dòng `from xime... import X` trong tài liệu có chạy được không? | **16 dòng hỏng**: cả mục JWT của `starters.md` mô tả API không tồn tại; 4 chỗ trỏ `xime.config`/`xime.lifecycle`/`xime.event`/`xime.context` thay vì `xime.core.*` |
| `check_doc_register.py` | Mọi class tài liệu bảo `dependency.register(...)` có dựng được trong DI không? | **2 class chết lúc khởi động** (`ModbusClient`, `OpcuaClient`) - đúng dòng lệnh tài liệu hướng dẫn |
| `find_reexport_gap.py` | `__init__.py` nào import một tên rồi không đưa vào `__all__`? | 9 file làm `mypy --strict` của người dùng báo lỗi ngay ở những import mà tài liệu bảo viết |

```bash
python .claude/scripts/check_doc_imports.py .      # quét toàn repo, hoặc truyền docs/
python .claude/scripts/check_doc_register.py
python .claude/scripts/find_reexport_gap.py xime
```

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
