#!/usr/bin/env python3
"""Sinh README của REPO PHÁT HÀNH từ README của repo phát triển.

Vì sao cần script chứ không sửa tay: hai bản khác nhau ở **hai quy tắc máy móc**,
và sửa tay thì mỗi lần phát hành lại phải dò lại chúng. Bản `0.7.2` đã trôi: nó
còn dấu gạch dài mà repo phát triển đã bỏ từ lâu, và bảng tài liệu của nó thiếu
năm mục mới của 0.8.

Hai quy tắc:

1. **Thêm huy hiệu PyPI.** Chỉ có nghĩa ở trang PyPI, nên bản phát triển không có.
2. **Đổi mọi liên kết TƯƠNG ĐỐI thành URL GitHub tuyệt đối.** PyPI dựng trang độc
   lập, không có kho mã bên cạnh, nên `](LICENSE)` ở đó không trỏ vào đâu cả.

⚠ Quy tắc 2 cố ý viết theo hướng **cái gì KHÔNG đổi** (đã là `http`, là neo `#`,
hay là `mailto:`), chứ không liệt kê cái gì phải đổi. Liệt kê thì mỗi tài liệu mới
thêm vào là một dòng phải nhớ sửa, mà quên thì không có gì kêu.

## Vì sao GIỮ dòng chuyển ngôn ngữ (đổi ý 2026-08-21)

Bản đầu của script **bỏ** dòng `**English** | [Tiếng Việt](README-vn.md)`, vì lúc
đó repo phát hành không mang `README-vn.md` nên liên kết sẽ chết.

Nhưng quy tắc 2 vốn đã đổi nó thành URL GitHub tuyệt đối, tức nó **không chết** -
và đó là cách duy nhất để người vào trang PyPI biết có bản tiếng Việt.

⚠ **PyPI KHÔNG hiển thị được hai README.** Trang mô tả dựng từ đúng một file, cái
khai ở `[project] readme`. Đưa `README-vn.md` vào sdist **không** làm nó hiện ra ở
đâu cả; nó chỉ nằm trong tarball. Một đường dẫn trong README tiếng Anh là cách duy
nhất, và nó rẻ.

Chạy:
    python .claude/scripts/sinh_readme_phat_hanh.py
    python .claude/scripts/sinh_readme_phat_hanh.py --kiem   # chỉ so, không ghi

Mã thoát: 0 khớp/đã ghi · 1 lệch (khi dùng --kiem) · 2 chưa kết luận được.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

GOC = "https://github.com/nguyen-huu-thang/xime-framework/blob/main/"

REPO = Path(__file__).resolve().parents[2]
PHAT_HANH = Path("D:/code/xime framework/upload")
# Chỉ sinh bản tiếng Anh. PyPI dựng trang mô tả từ ĐÚNG MỘT file - cái khai ở
# `[project] readme` - nên `README-vn.md` nằm trong sdist không hiện ra ở đâu cả.
# Đường dẫn tuyệt đối trong dòng chuyển ngôn ngữ là cách duy nhất, và nó đủ.
# Vì vậy `/README-vn.md` cũng đã bị bỏ khỏi danh sách trắng sdist trong pyproject:
# một mục khai mà không bao giờ xảy ra thì tệ hơn là không khai.
CAP = [("README.md", "README.md")]

HUY_HIEU_PYPI = "[![PyPI version](https://img.shields.io/pypi/v/xime.svg)](https://pypi.org/project/xime/)"
NEO_HUY_HIEU = "[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)]"

# Đích không cần đổi: đã tuyệt đối, là neo trong trang, hoặc là mailto.
# Targets that need no rewrite: already absolute, in-page anchor, or mailto.
_GIU_NGUYEN = re.compile(r"^(https?://|#|mailto:)")
_LIEN_KET = re.compile(r"\]\(([^)]+)\)")


def _doi_lien_ket(m: re.Match[str]) -> str:
    dich = m.group(1)
    if _GIU_NGUYEN.match(dich):
        return m.group(0)
    return f"]({GOC}{dich})"


def chuyen(van_ban: str) -> str:
    ra: list[str] = []
    for dong in van_ban.split("\n"):
        if dong.startswith(NEO_HUY_HIEU):
            ra.append(HUY_HIEU_PYPI)
        ra.append(_LIEN_KET.sub(_doi_lien_ket, dong))
    return "\n".join(ra)


def main() -> int:
    if not PHAT_HANH.is_dir():
        print(f"CHUA KET LUAN DUOC: khong thay repo phat hanh {PHAT_HANH}")
        return 2

    kiem = "--kiem" in sys.argv
    lech = False
    for ten_nguon, ten_dich in CAP:
        nguon = REPO / ten_nguon
        if not nguon.is_file():
            print(f"CHUA KET LUAN DUOC: khong thay nguon {nguon}")
            return 2
        ra = chuyen(nguon.read_text(encoding="utf-8"))
        dich = PHAT_HANH / ten_dich
        if kiem:
            cu = dich.read_text(encoding="utf-8") if dich.is_file() else ""
            if cu == ra:
                print(f"KHOP : {ten_dich}")
            else:
                print(f"LECH : {ten_dich}")
                lech = True
        else:
            dich.write_text(ra, encoding="utf-8", newline="\n")
            print(f"DA GHI: {dich}  ({len(ra.splitlines())} dong)")

    return 1 if lech else 0


if __name__ == "__main__":
    raise SystemExit(main())
