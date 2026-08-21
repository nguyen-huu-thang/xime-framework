"""Canh ranh giới giữa các hệ thống con của `core/`.

Ca thật (2026-08-21, do chính lượt rà cuối của đợt vá bắt được): một bản vá đặt
hàm dùng chung `view_of` vào `core/link/_cleanup.py`, và thế là `core/refdata`
phải import một module **riêng tư** của `core/link` - một cạnh phụ thuộc chưa
từng tồn tại giữa hai hệ thống con cố ý độc lập, dựng lên chỉ để dùng một hàm ba
dòng. `ruff` không thấy, `mypy` không thấy, 2500 test không thấy: mọi thứ chạy
đúng, chỉ có kiến trúc là xấu đi.

⭐ Ranh giới ở đây **không phải quy ước cho đẹp**. `core/link` (bus) và
`core/refdata` (kho tham chiếu) giải hai bài toán khác nhau và có thể dùng riêng;
buộc một cái kéo theo cái kia là buộc người đọc mã phải hiểu cả hai để hiểu một.
Chỗ chung của chúng là `core/_mp.py` - module chỉ phụ thuộc thư viện chuẩn.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_CORE = Path(__file__).resolve().parents[2] / "xime" / "core"

# Cặp nào KHÔNG được import cặp nào. `bootstrap` cố ý vắng mặt: nó là tầng điều
# phối, việc của nó là biết cả hai.
_CAM = [("link", "refdata"), ("refdata", "link")]


def _import_cua(goi: str) -> set[str]:
    ra: set[str] = set()
    for f in (_CORE / goi).rglob("*.py"):
        if "__pycache__" in f.parts:
            continue
        for nut in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(nut, ast.ImportFrom) and nut.module:
                ra.add(nut.module)
            elif isinstance(nut, ast.Import):
                ra |= {a.name for a in nut.names}
    return ra


class TestHaiHeThongConDocLap:
    @pytest.mark.parametrize("a,b", _CAM)
    def test_khong_import_lan_nhau(self, a: str, b: str) -> None:
        pham = sorted(m for m in _import_cua(a) if m.startswith(f"xime.core.{b}"))
        assert not pham, (
            f"core/{a} import từ core/{b}: {pham}. Hai hệ thống con này cố ý độc "
            f"lập. Thứ cả hai cần thì đặt ở core/_mp.py (chỉ phụ thuộc thư viện "
            f"chuẩn), đừng để một bên kéo theo bên kia."
        )

    def test_phep_do_biet_keu(self) -> None:
        """Đối chứng: một phép quét không đọc được gì thì con số 0 vô nghĩa."""
        assert _import_cua("link"), "không đọc được import nào của core/link"
        assert any(m.startswith("xime.core.") for m in _import_cua("bootstrap")), (
            "core/bootstrap phải có import nội bộ xime.core.* - nó là tầng điều phối"
        )

    def test_mp_khong_phu_thuoc_gi_cua_xime(self) -> None:
        """`core/_mp.py` là chỗ chung, nên nó không được kéo theo ai cả."""
        nguon = (_CORE / "_mp.py").read_text(encoding="utf-8")
        pham = [
            n.module for n in ast.walk(ast.parse(nguon))
            if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("xime")
        ]
        assert not pham, (
            f"core/_mp.py import {pham}. Nó là nơi ba hệ thống con gặp nhau, nên "
            f"nó phải là điểm thấp nhất - chỉ thư viện chuẩn."
        )
