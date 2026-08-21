"""Canh C5: adapter không được đọc một thuộc tính không ai gán.

Ca thật (2026-08-21): `SocketAdapter.assign_slot()` đọc `self._path_override`,
mà **không nơi nào trong repo gán nó**. `assign_slot()` là đường bắt buộc đi
qua khi chạy đa tiến trình, nên mọi ứng dụng dùng `SocketAdapter` với
`share_load()` sập lúc khởi động bằng:

    AttributeError: 'SocketAdapter' object has no attribute '_path_override'

Vì sao không test nào bắt được: test socket **tự bỏ qua trên Windows** (thiếu
`asyncio.start_unix_server`), còn test cụm thật thì dùng web adapter. `mypy` là
thứ duy nhất nhìn thấy - và mypy không nằm trong extra `dev` cho tới cùng đợt
kiểm toán này (T11). Hai chỗ mù chồng lên nhau.

⭐ Test canh theo LOẠI chứ không theo ca: gọi `assign_slot` trên **mọi** adapter
có nó. Vá đúng ca thì lần sau một adapter khác lặp lại y hệt.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_XIME = Path(__file__).resolve().parents[2] / "xime"


def _cac_adapter():
    """(tên lớp, module) của mọi lớp có `assign_slot`."""
    ra = []
    for f in sorted((_XIME / "adapters").rglob("_adapter.py")):
        cay = ast.parse(f.read_text(encoding="utf-8"))
        for nut in cay.body:
            if isinstance(nut, ast.ClassDef) and any(
                isinstance(x, ast.FunctionDef) and x.name == "assign_slot"
                for x in nut.body
            ):
                mod = ".".join(f.relative_to(_XIME.parent).with_suffix("").parts)
                ra.append((nut.name, mod))
    return ra


def _thuoc_tinh_doc_va_gan(lop: ast.ClassDef) -> tuple[set[str], set[str]]:
    doc: set[str] = set()
    gan: set[str] = set()
    for nut in ast.walk(lop):
        if isinstance(nut, ast.Attribute) and isinstance(nut.value, ast.Name) \
                and nut.value.id == "self":
            (gan if isinstance(nut.ctx, ast.Store) else doc).add(nut.attr)
    return doc, gan


class TestKhongDocThuocTinhKhongAiGan:
    def test_moi_adapter(self) -> None:
        pham: list[str] = []
        for f in sorted((_XIME / "adapters").rglob("*.py")):
            if "__pycache__" in f.parts:
                continue
            cay = ast.parse(f.read_text(encoding="utf-8"))
            for nut in cay.body:
                if not isinstance(nut, ast.ClassDef):
                    continue
                doc, gan = _thuoc_tinh_doc_va_gan(nut)
                # thuộc tính khai ở thân lớp cũng tính là đã gán
                gan |= {
                    t.id for x in nut.body
                    if isinstance(x, ast.Assign)
                    for t in x.targets if isinstance(t, ast.Name)
                }
                gan |= {
                    x.target.id for x in nut.body
                    if isinstance(x, ast.AnnAssign) and isinstance(x.target, ast.Name)
                }
                # phương thức và property cũng là thuộc tính
                gan |= {x.name for x in nut.body
                        if isinstance(x, ast.FunctionDef | ast.AsyncFunctionDef)}
                thieu = {a for a in doc - gan if a.startswith("_")}
                pham += [f"{f.relative_to(_XIME)}::{nut.name}.{a}" for a in sorted(thieu)]
        assert not pham, (
            "những thuộc tính này được ĐỌC mà không lớp nào gán chúng - mỗi cái "
            f"là một AttributeError chắc chắn nổ khi đường đó chạy:\n  "
            + "\n  ".join(pham)
        )


class TestAssignSlotChayDuoc:
    """Đối chứng chạy thật, không chỉ soi mã.

    Phép quét AST ở trên không thấy được thuộc tính gán qua `setattr` hay ở lớp
    cha; phép gọi thật thì thấy. Hai lớp đo hai chuyện.
    """

    @pytest.mark.parametrize("ten,mod", _cac_adapter())
    def test_goi_duoc_ma_khong_no_AttributeError(self, ten: str, mod: str) -> None:
        import importlib

        lop = getattr(importlib.import_module(mod), ten)
        try:
            a = lop()
        except Exception as exc:  # noqa: BLE001 - adapter cần tham số bắt buộc
            pytest.skip(f"{ten} không dựng được với 0 tham số: {exc}")

        class _Slot:
            process_id = "main"
            spec = None

        try:
            a.assign_slot(_Slot())
        except AttributeError as exc:
            pytest.fail(
                f"{ten}.assign_slot() ném AttributeError: {exc}. Đây là đường "
                f"BẮT BUỘC đi qua khi chạy đa tiến trình."
            )
        except Exception:
            pass  # StartupException có chủ ý thì được, chỉ AttributeError mới sai
