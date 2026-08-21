"""Canh C4: mọi nguyên thủy multiprocessing phải đi qua MỘT ngữ cảnh duy nhất.

⛔ Lỗi này KHÔNG THỂ phát hiện được trên Windows, nên test canh ở đây không phải
"cho chắc" mà là **lớp phòng thủ duy nhất**: trên Windows ngữ cảnh mặc định
chính là ``spawn``, nên vi phạm chạy hoàn hảo và không gì đỏ.

Ca thật (2026-08-21): ``core/link/_link.py`` tạo chuông bằng
``from multiprocessing import Semaphore`` trong khi ``Supervisor`` sinh con bằng
``get_context("spawn")``. Trên Linux, Python ném::

    RuntimeError: A SemLock created in a fork context is being shared with a
    process in a spawn context.

Kết quả: **26 test đỏ** ở vùng đa tiến trình trên Linux, **0 đỏ** trên Windows.

⭐ Gốc của lỗi là HAI CHỖ cùng quyết định một thứ mà không biết nhau. Nên hai
test dưới đây đi thành CẶP và canh hai vế khác nhau:

- vế 1: không ai tạo nguyên thủy bằng ngữ cảnh mặc định
- vế 2: không ai gọi ``get_context`` lần thứ hai

Canh mỗi vế đầu thì ngày mai ai đó thêm ``get_context("forkserver")`` ở
supervisor là lỗi quay lại nguyên vẹn, và vẫn vô hình trên Windows.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_XIME = Path(__file__).resolve().parents[2] / "xime"
_NGUON_SU_THAT = _XIME / "core" / "_mp.py"

# Nguyên thủy của multiprocessing mang khóa hệ điều hành bên trong, tức là thứ
# không qua nổi ranh giới giữa hai ngữ cảnh khác nhau.
_NGUYEN_THUY = frozenset({
    "Semaphore", "BoundedSemaphore", "Lock", "RLock", "Event",
    "Condition", "Barrier", "Queue", "JoinableQueue", "SimpleQueue",
    "Pipe", "Value", "Array", "Pool", "Process", "Manager",
})


def _cac_file_python() -> list[Path]:
    return sorted(p for p in _XIME.rglob("*.py") if "__pycache__" not in p.parts)


def _quet(nguon: str) -> tuple[list[str], list[str]]:
    """Trả (tên nguyên thủy nhập thẳng và bị GỌI, lời gọi get_context)."""
    cay = ast.parse(nguon)
    nhap_thang: set[str] = set()
    for nut in ast.walk(cay):
        if isinstance(nut, ast.ImportFrom) and (nut.module or "").split(".")[0] == "multiprocessing":
            for ten in nut.names:
                if ten.name in _NGUYEN_THUY:
                    nhap_thang.add(ten.asname or ten.name)

    goi_nguyen_thuy: list[str] = []
    goi_get_context: list[str] = []
    for nut in ast.walk(cay):
        if not isinstance(nut, ast.Call):
            continue
        ham = nut.func
        # dạng 1: Semaphore(0)  - tên trần đã nhập thẳng từ multiprocessing
        if isinstance(ham, ast.Name) and ham.id in nhap_thang:
            goi_nguyen_thuy.append(f"{ham.id}() dòng {nut.lineno}")
        # dạng 2: multiprocessing.Semaphore(0)  - qua tên module
        if isinstance(ham, ast.Attribute) and ham.attr in _NGUYEN_THUY:
            goc = ham.value
            if isinstance(goc, ast.Name) and goc.id == "multiprocessing":
                goi_nguyen_thuy.append(f"multiprocessing.{ham.attr}() dòng {nut.lineno}")
        # get_context ở bất kỳ dạng nào
        ten_ham = ham.attr if isinstance(ham, ast.Attribute) else getattr(ham, "id", "")
        if ten_ham == "get_context":
            goi_get_context.append(f"dòng {nut.lineno}")
    return goi_nguyen_thuy, goi_get_context


class TestMotNguonSuThat:
    def test_khong_ai_tao_nguyen_thuy_bang_ngu_canh_mac_dinh(self) -> None:
        pham: list[str] = []
        for f in _cac_file_python():
            nguyen_thuy, _ = _quet(f.read_text(encoding="utf-8"))
            pham += [f"{f.relative_to(_XIME)}: {x}" for x in nguyen_thuy]
        assert not pham, (
            "Nguyên thủy multiprocessing tạo bằng ngữ cảnh MẶC ĐỊNH. Trên Linux "
            "ngữ cảnh mặc định là fork/forkserver, không qua nổi ranh giới sang "
            "tiến trình spawn. Dùng MP_CONTEXT của xime.core._mp:\n  "
            + "\n  ".join(pham)
        )

    def test_chi_MOT_cho_goi_get_context(self) -> None:
        cho: list[str] = []
        for f in _cac_file_python():
            _, get_ctx = _quet(f.read_text(encoding="utf-8"))
            cho += [f"{f.relative_to(_XIME)} {x}" for x in get_ctx]
        assert len(cho) == 1, (
            "Phải có đúng MỘT lời gọi get_context trong toàn bộ xime/, và nó ở "
            f"core/_mp.py. Tìm thấy {len(cho)}:\n  " + "\n  ".join(cho)
        )
        assert "core/_mp.py" in cho[0].replace("\\", "/"), (
            f"Lời gọi get_context duy nhất phải nằm ở core/_mp.py, không phải {cho[0]}"
        )

    def test_MP_CONTEXT_that_su_la_spawn(self) -> None:
        from xime.core._mp import MP_CONTEXT

        assert MP_CONTEXT.get_start_method() == "spawn"


class TestPhepDoBietKeu:
    """Đối chứng dương. Không có nhóm này thì hai test trên xanh cả khi trình
    quét mù, và con số 0 của một phép dò mù trông y hệt con số 0 của một repo
    sạch."""

    @pytest.mark.parametrize("nguon", [
        "from multiprocessing import Semaphore\nx = Semaphore(0)\n",
        "from multiprocessing import Lock\nx = Lock()\n",
        "import multiprocessing\nx = multiprocessing.Event()\n",
        "from multiprocessing import Semaphore as Chuong\nx = Chuong(0)\n",
    ])
    def test_bat_duoc_vi_pham(self, nguon: str) -> None:
        nguyen_thuy, _ = _quet(nguon)
        assert nguyen_thuy, f"trình quét KHÔNG bắt được vi phạm trong:\n{nguon}"

    @pytest.mark.parametrize("nguon", [
        "from xime.core._mp import MP_CONTEXT\nx = MP_CONTEXT.Semaphore(0)\n",
        "import asyncio\nx = asyncio.Semaphore(4)\n",
        "import threading\nx = threading.Lock()\n",
        "from multiprocessing import synchronize\ndef f(s: synchronize.Semaphore): ...\n",
    ])
    def test_khong_keu_oan(self, nguon: str) -> None:
        nguyen_thuy, _ = _quet(nguon)
        assert not nguyen_thuy, f"trình quét kêu OAN với:\n{nguon}\n-> {nguyen_thuy}"

    def test_bat_duoc_get_context_thu_hai(self) -> None:
        _, get_ctx = _quet('import multiprocessing\nc = multiprocessing.get_context("fork")\n')
        assert get_ctx, "trình quét KHÔNG bắt được lời gọi get_context"
