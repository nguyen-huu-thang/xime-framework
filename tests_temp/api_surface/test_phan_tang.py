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
Chỗ chung của chúng là `core/shared/_mp.py` - module chỉ phụ thuộc thư viện chuẩn.
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
            f"lập. Thứ cả hai cần thì đặt ở core/shared/_mp.py (chỉ phụ thuộc thư viện "
            f"chuẩn), đừng để một bên kéo theo bên kia."
        )

    def test_phep_do_biet_keu(self) -> None:
        """Đối chứng: một phép quét không đọc được gì thì con số 0 vô nghĩa."""
        assert _import_cua("link"), "không đọc được import nào của core/link"
        assert any(m.startswith("xime.core.") for m in _import_cua("bootstrap")), (
            "core/bootstrap phải có import nội bộ xime.core.* - nó là tầng điều phối"
        )

    def test_goi_shared_khong_phu_thuoc_gi_cua_xime(self) -> None:
        """`core/shared/` là chỗ chung, nên nó không được kéo theo ai cả.

        ⚠ Soi **cả gói**, không riêng `_mp.py`: từ 2026-09-01 đây là một gói chứ
        không còn là một tệp lẻ, và một tệp thứ hai đặt vào đó ngày mai cũng phải
        chịu đúng ràng buộc này. Soi một tệp thì phép canh chỉ đúng cho tới lần
        thêm tệp kế tiếp - mà lần đó không ai nhớ để sửa test.
        """
        vi_pham: dict[str, list[str]] = {}
        for tep in sorted((_CORE / "shared").glob("*.py")):
            nguon = tep.read_text(encoding="utf-8")
            ngoai = [
                n.module for n in ast.walk(ast.parse(nguon))
                if isinstance(n, ast.ImportFrom)
                and n.module
                and n.module.startswith("xime")
                and not n.module.startswith("xime.core.shared")
            ]
            if ngoai:
                vi_pham[tep.name] = ngoai

        assert not vi_pham, (
            f"core/shared/ import {vi_pham}. Đây là nơi ba hệ thống con gặp nhau, "
            f"nên nó phải là điểm thấp nhất - chỉ thư viện chuẩn."
        )

    def test_goi_shared_co_that_va_khong_rong(self) -> None:
        """Đối chứng cho test trên: rỗng thì nó xanh vì không có gì để soi.

        Đúng [luật 03] ở tầng đầu ra của chốt kiểm - *"sạch"* và *"không có dữ
        liệu để kết luận"* là hai chuyện khác nhau.
        """
        tep = sorted(p.name for p in (_CORE / "shared").glob("*.py"))
        assert "_mp.py" in tep and "__init__.py" in tep, (
            f"core/shared/ chứa {tep} - phép canh ở trên không soi được gì."
        )
