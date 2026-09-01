"""Tên `CHANGELOG` công bố là tên phải import được - CHANGELOG cũng là tài liệu.

⛔ Nhóm này ra đời từ một lỗi thật do phiên `Base Platform/data` báo về ngày
2026-09-01. `CHANGELOG.md` của `0.7.2` công bố:

    - **`JwtAuthenticator`** - phần verify tách khỏi `JwtAuthMiddleware` ...

nhưng `xime/starters/jwt/__init__.py` không có dòng nào cho nó, nên câu lệnh duy
nhất lấy được nó là `from xime.starters.jwt._authenticator import ...` - tức bảo
người ta thò tay vào ruột mình. Repo ngoài chọn không làm vậy và **chép lại 12
dòng logic đọc `kid`**, đúng thứ lớp đó sinh ra để không có.

⭐ Chỗ mù có tính cấu trúc, và đó mới là lý do có file này: `check_doc_imports.py`
canh *"tên nào tài liệu nhắc thì phải import được"* nhưng nó chỉ soi `docs/`.
`CHANGELOG.md` **cũng nằm trong danh sách trắng sdist** (`pyproject.toml`), tức
nó tới tay mọi người cài từ PyPI y như `docs/`, mà **không guard nào che**.

⚠ Hai hướng khác đã đo rồi loại, ghi lại để không ai dựng lại:

* **Trỏ `check_doc_imports.py` vào `CHANGELOG.md`.** Vô dụng: CHANGELOG có
  **0** câu lệnh `from xime... import`, nó công bố tên bằng **văn xuôi**. Một
  phép dò không nhìn gì thì số 0 của nó không có nghĩa (luật 03 mục 4b).
* **Canh mọi import riêng tư liên-package trong chính `xime/`.** Đo ra **37**
  chỗ, phần lớn là dây nối nội bộ hợp lệ (registry, `AdapterSlot`). *Một phép dò
  kêu oan là một phép dò sẽ bị tắt.*

⚠ Đừng nhầm với `.claude/scripts/find_reexport_gap.py`: script đó soi chiều
NGƯỢC LẠI - tên **có** trong `__init__.py` mà thiếu ở `__all__` (lỗi `mypy
--strict`). File này soi tên **không có trong `__init__.py`** một dòng nào. Hai
hình dạng hỏng khác nhau, không cái nào thay được cái nào. Và script kia nằm ở
`.claude/`, vốn **bị gitignore**, nên nó không đi theo repo - đó cũng là lý do
chốt canh này là một test trong `tests_temp/` chứ không phải một script nữa.

Cái còn lại là phép lọc trong file này, và nó **chính xác**: trong 15 tên in đậm
của CHANGELOG, nó bỏ qua 3 cái không phải class/def (khoá cấu hình, tên trường)
và 2 cái vốn định nghĩa ở module công khai, còn lại 10 tên kiểm được.
"""

from __future__ import annotations

import ast
import functools
import importlib
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CHANGELOG = ROOT / "CHANGELOG.md"
PKG_ROOT = ROOT / "xime"

# `- **`Name`**` ở đầu một bullet: khuôn CHANGELOG dùng để công bố một tên mới.
BULLET = re.compile(r"^\s*-\s+\*\*`([A-Za-z_]\w*)`\*\*", re.MULTILINE)

# ⛔ Tên CHANGELOG có nhắc, định nghĩa ở module riêng tư, và **cố ý giữ riêng tư**.
#
# Chủ dự án chốt 2026-09-01: **viết adapter KHÔNG phải điểm mở rộng công khai** -
# *"người ngoài không được viết adapter, chỉ tôi/chúng tôi được viết"*. Sáu adapter
# đi kèm framework là sáu cái có; thêm cái mới là việc của framework. Tài liệu ở
# `docs/` đã sửa theo (bỏ mục *"Viết adapter của riêng bạn"* và ví dụ
# `ResourceSampler`).
#
# ⚠ Đây KHÔNG phải danh sách bỏ qua cho tiện. Mỗi tên ở đây là một quyết định đã
# ghi lý do, và test dưới cùng **bắt danh sách co lại** nếu ai export một trong
# chúng - vì lúc đó chính sách đã đổi, và tài liệu phải đổi theo chứ không phải
# lặng lẽ mọc thêm một tên công khai.
CO_Y_RIENG_TU = {
    # xime.core.bootstrap._slot - `AdapterSlot` cùng `SlotAware`, `EndpointSpec`
    # là hợp đồng nội bộ giữa framework và sáu adapter của nó. Framework chưa bao
    # giờ đòi cái type này (`_supervisor.py` dùng `getattr(adapter, "assign_slot")`,
    # tức duck typing), và **ba trong sáu** adapter dựng sẵn khai thẳng
    # `slot: object` - chúng ở trong nhà, import tự do, mà vẫn không dùng tới.
    "AdapterSlot",
    # xime.starters.scheduler._adapter - CHANGELOG nhắc nó trong một bullet mô tả
    # đợt TÁI CẤU TRÚC nội bộ (*"scheduler thành adapter hạng đơn nhất"*), không
    # phải công bố một tên để gọi. Không ai import nó ngoài `application.py` và
    # hai test. ⭐ Đây là giới hạn đã biết của phép lọc dưới đây: nó không phân
    # biệt được *"CHANGELOG công bố một API"* với *"CHANGELOG kể một thay đổi bên
    # trong"* - cả hai đều là tên in đậm.
    "SchedulerAdapter",
}


@functools.lru_cache(maxsize=1)
def _defined_in() -> dict[str, str]:
    """Ánh xạ mọi class/def mức trên cùng trong `xime/` -> module định nghĩa nó."""
    found: dict[str, str] = {}
    for path in sorted(PKG_ROOT.rglob("*.py")):
        module = ".".join(path.relative_to(ROOT).with_suffix("").parts)
        if module.endswith(".__init__"):
            module = module[: -len(".__init__")]
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - cây mã phải parse được
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                found.setdefault(node.name, module)
    return found


def _announced() -> set[str]:
    return set(BULLET.findall(CHANGELOG.read_text(encoding="utf-8")))


def _is_private(module: str) -> bool:
    return any(part.startswith("_") for part in module.split("."))


def khong_export_duoc(names: set[str], defined: dict[str, str]) -> dict[str, str]:
    """Tên nào định nghĩa ở module RIÊNG TƯ mà package của nó không export.

    Tách khỏi phần đọc CHANGELOG để đối chứng nạp được ngữ liệu giả - một chốt
    kiểm không tự chứng minh được là mình biết kêu thì con số 0 của nó vô nghĩa.
    """
    thieu: dict[str, str] = {}
    for name in sorted(names):
        module = defined.get(name)
        if module is None:
            continue  # không phải class/def: khoá cấu hình, tên trường, đường dẫn
        if not _is_private(module):
            continue  # định nghĩa thẳng ở module công khai
        package = module.rsplit(".", 1)[0]
        if not hasattr(importlib.import_module(package), name):
            thieu[name] = f"{module}  ->  không export từ {package}"
    return thieu


# --------------------------------------------------------------------------
# Đối chứng: phép dò có biết kêu không, và có kêu oan không
# --------------------------------------------------------------------------

def test_phep_do_biet_keu_khi_mot_ten_khong_export_duoc() -> None:
    """ĐỐI CHỨNG DƯƠNG - nạp một tên riêng tư có thật mà package không xuất."""
    # `SchedulerRunner` sống ở xime.starters.scheduler._runner và cố ý không được
    # export (nó kéo apscheduler ở mức module). Dùng nó làm mẫu dương vì nó là
    # một chỗ hụt THẬT, không phải một cái tên bịa.
    thieu = khong_export_duoc({"SchedulerRunner"}, _defined_in())
    assert "SchedulerRunner" in thieu, (
        "phép dò không nhận ra một tên định nghĩa ở module riêng tư mà package "
        "không export - nó đang không nhìn gì, nên số 0 của nó vô nghĩa"
    )


def test_phep_do_khong_keu_oan_voi_ten_da_export() -> None:
    """ĐỐI CHỨNG NGƯỢC - tên đã export thì phải im."""
    assert khong_export_duoc({"JwtAuthenticator", "JwtKeyProvider"}, _defined_in()) == {}


def test_phep_do_bo_qua_thu_khong_phai_class_hay_def() -> None:
    """Khoá cấu hình và tên trường trong CHANGELOG không phải tên import được."""
    assert khong_export_duoc({"close_on_token_expiry", "khong_ton_tai_o_dau_ca"}, _defined_in()) == {}


# --------------------------------------------------------------------------
# Chốt canh thật
# --------------------------------------------------------------------------

def test_ngu_lieu_khong_rong() -> None:
    """Ba kết cục, không phải hai: rỗng là CHƯA KẾT LUẬN ĐƯỢC, không phải SẠCH.

    Ngày khuôn bullet của CHANGELOG đổi, `BULLET` sẽ khớp 0 dòng và mọi test
    dưới đây xanh trong khi không kiểm gì cả - đúng lỗi `ShardValueGuard` của
    `identity` đã vấp (luật 03 mục 4b).
    """
    assert CHANGELOG.is_file(), "không thấy CHANGELOG.md - chưa kết luận được"
    assert len(_announced()) >= 10, (
        "CHANGELOG khớp quá ít tên in đậm - nhiều khả năng khuôn bullet đã đổi "
        "và phép dò này đang soi một ngữ liệu rỗng"
    )


def test_moi_ten_changelog_cong_bo_deu_import_duoc() -> None:
    thieu = khong_export_duoc(_announced() - CO_Y_RIENG_TU, _defined_in())
    assert not thieu, (
        "CHANGELOG công bố tên này nhưng package của nó không export - người đọc "
        "chỉ lấy được nó qua một module có tên bắt đầu bằng dấu gạch dưới:\n  "
        + "\n  ".join(f"{k}: {v}" for k, v in thieu.items())
        + "\n\nExport nó từ `__init__.py` của package, hoặc nếu cố ý giữ riêng tư "
        "thì thêm vào CO_Y_RIENG_TU kèm lý do."
    )


@pytest.mark.parametrize("name", sorted(CO_Y_RIENG_TU))
def test_ten_co_y_rieng_tu_van_dang_rieng_tu(name: str) -> None:
    """Ai export một tên trong danh sách này thì chính sách đã đổi, không phải
    danh sách sai.

    Không có test này thì danh sách chỉ phình ra, không bao giờ co lại - và một
    quyết định được khai ra rồi quên là quyết định vĩnh viễn mà không ai từng
    xem lại.
    """
    assert khong_export_duoc({name}, _defined_in()), (
        f"{name!r} nay đã export được. Nếu đó là cố ý thì chính sách 2026-09-01 "
        "đã đổi: gỡ nó khỏi CO_Y_RIENG_TU, và sửa cả docs/ - vì tài liệu hiện "
        "đang nói adapter KHÔNG phải điểm mở rộng công khai."
    )
