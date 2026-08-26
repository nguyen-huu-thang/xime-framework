"""Tên công khai nào của framework không có một chữ nào trong `docs/`.

    python .claude/scripts/check_doc_coverage.py
    python .claude/scripts/check_doc_coverage.py --docs docs/vn

Ba script `check_doc_*` kia kiểm chiều **tài liệu -> code**: thứ tài liệu nói
có thật không, import được không, dựng được không. Script này kiểm **chiều
ngược lại**: thứ code phơi ra có ai viết tài liệu chưa.

Hai chiều không thay nhau. Tài liệu nói về một API không tồn tại thì người đọc
mất thời gian chứng minh framework sai; một API tồn tại mà không tài liệu nào
nhắc tới thì **không ai biết nó có** - và nó chết trong im lặng, không ai báo.

⚠⚠ **Hai kết quả của script này KHÔNG cân nhau, đừng đọc chúng như nhau:**

| Kết quả | Bằng chứng mạnh tới đâu |
|---|---|
| Tên **KHÔNG** xuất hiện | **Mạnh** - chắc chắn chưa ai viết gì về nó |
| Tên **CÓ** xuất hiện | **Yếu** - nó có thể chỉ nằm trong một khối code, không một dòng giải thích |

Nên dùng nó để **tìm lỗ**, đừng dùng nó để kết luận *"đã phủ hết"*. Cùng bài
học với phép quét secret của workspace: một phép dò xây bằng danh sách tên thì
con số 0 của nó chỉ nói về danh sách đó.

⛔ Và nó **cố ý không tự phân loại** tên nào đáng có tài liệu, tên nào không
(`*_registry` nội bộ chẳng hạn). Một bản xấp xỉ sẽ sinh cảnh báo giả, mà *một
phép dò kêu oan là một phép dò sẽ bị tắt*.

Mã thoát - BA kết cục, không phải hai:
    0  SACH        - mọi tên công khai đều xuất hiện ít nhất một lần
    1  CO LO HONG  - có tên không xuất hiện
    2  CHUA KET LUAN DUOC - không tìm thấy thư mục tài liệu, hoặc có file
                     không phân tích cú pháp được. Gộp mã này vào 0 là báo
                     xanh cho một phép kiểm chưa hề chạy (luật 03 mục 4b).
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parents[2]


def _ten_cong_khai(goi: Path) -> dict[str, list[str]]:
    """Gom `__all__` của từng package. Trả {tên module: [tên công khai]}."""
    ra: dict[str, list[str]] = {}
    for f in sorted(goi.rglob("__init__.py")):
        try:
            cay = ast.parse(f.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as e:
            raise RuntimeError(f"khong doc/phan tich duoc {f}: {e}") from e
        for n in ast.walk(cay):
            if isinstance(n, ast.Assign) and any(
                getattr(x, "id", None) == "__all__" for x in n.targets
            ):
                if isinstance(n.value, ast.List | ast.Tuple):
                    ten = [e.value for e in n.value.elts if isinstance(e, ast.Constant)]
                    if ten:
                        ra[str(f.parent.relative_to(goc_goi(goi)))] = ten
    return ra


def goc_goi(goi: Path) -> Path:
    return goi.parent


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--docs", default="docs/en", help="thu muc tai lieu (mac dinh docs/en)")
    p.add_argument("--goi", default="xime", help="goi can quet (mac dinh xime)")
    a = p.parse_args()

    thu_muc_docs, goi = GOC / a.docs, GOC / a.goi
    if not thu_muc_docs.is_dir():
        print(f"CHUA KET LUAN DUOC - khong thay thu muc tai lieu: {thu_muc_docs}")
        return 2
    if not goi.is_dir():
        print(f"CHUA KET LUAN DUOC - khong thay goi: {goi}")
        return 2

    trang = sorted(thu_muc_docs.glob("*.md"))
    if not trang:
        print(f"CHUA KET LUAN DUOC - {thu_muc_docs} khong co trang .md nao")
        return 2
    van_ban = " ".join(t.read_text(encoding="utf-8", errors="replace") for t in trang)

    try:
        theo_mo = _ten_cong_khai(goi)
    except RuntimeError as e:
        print(f"CHUA KET LUAN DUOC - {e}")
        return 2
    if not theo_mo:
        print(f"CHUA KET LUAN DUOC - khong module nao trong {goi} khai __all__")
        return 2

    tong = thieu_tong = 0
    dong: list[tuple[str, int, list[str]]] = []
    for mo, ten in sorted(theo_mo.items()):
        tong += len(ten)
        thieu = [x for x in ten if not re.search(rf"\b{re.escape(x)}\b", van_ban)]
        if thieu:
            thieu_tong += len(thieu)
            dong.append((mo, len(ten), thieu))

    print(f"Quet {tong} ten cong khai cua `{a.goi}` doi chieu {len(trang)} trang `{a.docs}`.\n")
    if not dong:
        print(f"SACH - ca {tong} ten deu xuat hien it nhat mot lan.")
        print("Luu y: 'xuat hien' KHONG bang 'da co tai lieu' - xem docstring.")
        return 0

    rong = max(len(m) for m, _, _ in dong)
    for mo, so, thieu in dong:
        print(f"  {mo:{rong}}  {len(thieu):>3}/{so:<3} thieu: {', '.join(thieu)}")
    print(
        f"\nCO LO HONG - {thieu_tong}/{tong} ten khong xuat hien trong `{a.docs}`."
        "\nLuu y: day la bang chung MANH cho 'chua co tai lieu'; chieu nguoc lai"
        "\n(ten co xuat hien) la bang chung YEU - xem docstring."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
