"""Canh T11: mọi công cụ mà hướng dẫn phát hành gọi tới phải được KHAI.

Đây là lần vá thứ HAI của cùng một lỗi. Lượt rà 2026-08-20 chẩn đoán đúng -
*"hướng dẫn phát hành phụ thuộc vào một chương trình mà không file nào nói là
cần"* - rồi vá đúng MỘT CA (`pip-audit`) thay vì cả một LOẠI. `mypy` và `ruff`
có `[tool.*]` trong `pyproject.toml` mà không nằm trong extra nào, nên mypy
không có trên máy phát triển và phép kiểm kiểu **chưa hề chạy cho 0.8**.

⭐ Test này quét NGƯỢC: đọc `pypi_token.py` và `.claude/scripts/` xem chúng gọi
tới công cụ nào, rồi đối chiếu với `dev`. Vá theo LOẠI, không theo ca.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]

# Tên gói PyPI cung cấp mỗi lệnh. Không suy được từ tên lệnh: `python -m build`
# tới từ gói `build`, còn `pip-audit` là cả tên lệnh lẫn tên gói.
_LENH_TOI_GOI = {
    "pytest": "pytest",
    "mypy": "mypy",
    "ruff": "ruff",
    "twine": "twine",
    "build": "build",
    "pip-audit": "pip-audit",
}


def _khai_trong_dev() -> set[str]:
    data = tomllib.loads((_REPO / "pyproject.toml").read_text(encoding="utf-8"))
    dev = data["project"]["optional-dependencies"]["dev"]
    return {re.split(r"[<>=!\[ ]", d.strip())[0].lower() for d in dev}


def _cong_cu_duoc_goi() -> dict[str, set[str]]:
    """lệnh -> tập file gọi nó. Chỉ nhận lời gọi THẬT, không nhận văn xuôi."""
    ket: dict[str, set[str]] = {}
    nguon = [_REPO / "pypi_token.py", *sorted((_REPO / ".claude" / "scripts").glob("*.py"))]
    # Ba dạng gọi thật, và dạng thứ ba là thứ phép quét đầu tiên bỏ sót:
    #   1. `python -m build` / `python -m twine check ...`   (trong hướng dẫn)
    #   2. `mypy --strict xime/`                              (dòng lệnh trần)
    #   3. `subprocess.run([..., "-m", "pip_audit", ...])`    (gọi từ Python)
    # Dạng 3 dùng tên MODULE (`pip_audit`, gạch dưới) chứ không phải tên lệnh.
    mau = re.compile(
        r"(?:python -m (?P<m>[a-z_-]+))"
        r"|(?:\b(?P<c>pytest|mypy|ruff|twine|pip-audit)\b\s+(?:--|-[a-z]|check|upload|xime/|\.))"
        r"|(?:\"-m\",\s*\n?\s*\"(?P<s>[a-z_]+)\")"
    )
    for f in nguon:
        if not f.is_file():
            continue
        for m in mau.finditer(f.read_text(encoding="utf-8")):
            lenh = m.group("m") or m.group("c") or (m.group("s") or "").replace("_", "-")
            if lenh in _LENH_TOI_GOI:
                ket.setdefault(lenh, set()).add(f.name)
    return ket


class TestCongCuPhatHanhDuocKhai:
    def test_moi_cong_cu_duoc_goi_deu_co_trong_extra_dev(self) -> None:
        goi = _cong_cu_duoc_goi()
        dev = _khai_trong_dev()
        thieu = {
            lenh: sorted(files)
            for lenh, files in goi.items()
            if _LENH_TOI_GOI[lenh] not in dev
        }
        assert not thieu, (
            f"những công cụ này được hướng dẫn phát hành gọi tới nhưng không "
            f"khai ở extra `dev`, nên `pip install -e '.[dev]'` không kéo chúng "
            f"về: {thieu}. Một cổng kiểm không cài được là một cổng không chạy."
        )

    def test_phep_quet_biet_tim_thay(self) -> None:
        """Đối chứng: một phép quét không tìm thấy gì thì con số 0 vô nghĩa."""
        goi = _cong_cu_duoc_goi()
        assert goi, "không tìm thấy lời gọi công cụ nào - phép quét đã hỏng"
        assert "pip-audit" in goi, "phải thấy pip-audit trong check_dep_advisories.py"

    @pytest.mark.parametrize("cong_cu", ["mypy", "ruff"])
    def test_cong_cu_co_cau_hinh_thi_phai_co_trong_dev(self, cong_cu: str) -> None:
        """Chiều thứ hai: có `[tool.X]` trong pyproject thì X phải cài được.

        `[tool.ruff]` và `[tool.mypy]` nằm trong chính file khai phụ thuộc, và
        vẫn không ai khai công cụ. Một cấu hình cho một chương trình không tồn
        tại trên máy là một lời hứa không ai kiểm được.
        """
        noi_dung = (_REPO / "pyproject.toml").read_text(encoding="utf-8")
        if f"[tool.{cong_cu}]" not in noi_dung:
            pytest.skip(f"pyproject không cấu hình {cong_cu}")
        assert cong_cu in _khai_trong_dev(), (
            f"pyproject.toml có [tool.{cong_cu}] nhưng {cong_cu} không nằm trong "
            f"extra `dev`"
        )
