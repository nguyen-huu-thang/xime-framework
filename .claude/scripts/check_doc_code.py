"""Mọi khối ```python trong tài liệu phải phân tích cú pháp được.

Bổ sung cho `check_doc_imports.py`, và chúng **không thay nhau**: cái kia hỏi
*"tên này có tồn tại không"*, cái này hỏi *"đoạn code này có còn là Python
không"*. Một đợt sửa hàng loạt trên tài liệu (đổi dấu, đổi thụt lề, thay tên)
làm hỏng vế thứ hai mà vế thứ nhất vẫn xanh.

Nó ra đời ở đợt rà trước 0.8.0, lúc thay 287 dấu gạch dài bằng dấu trừ trên 29
file - trong đó 34 dấu nằm **bên trong khối code**. Phép quét đầu tiên tôi dùng
để tự trấn an lại so nhầm cặp dòng (312 dòng cũ ghép với 644 dòng mới), tức nó
đo một thứ không phải thứ cần đo. Đây là phép đo đúng: đưa thẳng cho `ast`.

Chạy: python .claude/scripts/check_doc_code.py [docs]
"""

from __future__ import annotations

import ast
import pathlib
import sys
import textwrap

DOC_ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")

failures: list[str] = []
checked = 0

for path in sorted(DOC_ROOT.rglob("*.md")):
    lines = path.read_text(encoding="utf-8").splitlines()
    fence: str | None = None
    buffer: list[str] = []
    opened_at = 0
    for lineno, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            if fence is None:
                fence = stripped[3:].strip().lower()
                buffer = []
                opened_at = lineno
            else:
                if fence in ("python", "py"):
                    checked += 1
                    try:
                        ast.parse(textwrap.dedent("\n".join(buffer)))
                    except SyntaxError as exc:
                        failures.append(f"{path}:{opened_at}  {exc}")
                fence = None
            continue
        if fence is not None:
            buffer.append(line)
    if fence is not None:
        failures.append(f"{path}:{opened_at}  khối code không được đóng")

print(f"checked {checked} python block(s) in {DOC_ROOT}")
if failures:
    print(f"\n{len(failures)} khối không phân tích được:\n")
    for failure in failures:
        print(f"  {failure}")
    raise SystemExit(1)
print("ALL OK")
