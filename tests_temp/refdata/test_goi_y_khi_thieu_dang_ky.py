"""Gợi ý của lỗi thiếu đăng ký phải chỉ đúng registry mà lớp đó thật sự đến từ.

⚠ Bối cảnh: `dependency.scan()` **không bao giờ** với tới bảng `RefData` hay
handler `ProcessLink` - chúng vào container từ registry riêng
(`configure_refdata` / `configure_link`, xem `orchestrator.py`). Gợi ý mặc định
vì thế không chỉ vô ích với chúng, nó là **một con đường không có đích**: người
đọc làm theo, không có gì đổi, và nguyên nhân thật vẫn nằm im.

Báo về từ phiên giữ `Application Layer/dental` (2026-08-22) khi họ dựng container
bằng tay trong test canh nối dây DI - đúng chỗ người đọc không có orchestrator để
đối chiếu. Framework đo lại thì phạm vi rộng hơn báo cáo: **hai** registry nằm
ngoài `scan()`, không phải một.
"""

from __future__ import annotations

import pytest

from xime.core.container.validator import _hint_for
from xime.core.exception.framework import UnregisteredDependencyException
from xime.core.refdata import RefData


class BangThamChieu(RefData):
    pass


class LopThuong:
    pass


class TestGoiYChiDungCho:
    def test_bang_refdata_duoc_chi_ve_configure_refdata(self) -> None:
        hint = _hint_for(BangThamChieu)

        assert hint is not None
        assert "configure_refdata" in hint
        assert "dependency.scan" not in hint.replace("not dependency.scan()", "")

    def test_lop_thuong_van_dung_goi_y_mac_dinh(self) -> None:
        """Vế đối chứng, và nó quan trọng ngang vế trên.

        Một hàm luôn trả `None` cũng làm vế đầu xanh nếu vế đầu chỉ hỏi *"có
        khác mặc định không"*. Và một hàm luôn trả gợi ý RefData thì phá đúng
        99% ca thật - nơi `scan()` mới là câu trả lời đúng.
        """
        assert _hint_for(LopThuong) is None

        thong_bao = str(UnregisteredDependencyException("A", "LopThuong"))
        assert "dependency.scan()" in thong_bao

    def test_validator_that_su_truyen_goi_y_xuong(self) -> None:
        """Canh CHO NOI, khong chi canh ham.

        `_hint_for` dung ma cho raise khong truyen no xuong thi nguoi dung van
        doc goi y sai - va khong test nao o hai ve tren biet chuyen do. Ve nay
        di qua validator that, khong dung exception truc tiep.
        """
        from xime.core.container.graph import DependencyGraph
        from xime.core.container.validator import GraphValidator

        class DichVu:
            def __init__(self, bang: BangThamChieu) -> None:
                self.bang = bang

        resolved = {DichVu: {"bang": BangThamChieu}}

        with pytest.raises(UnregisteredDependencyException) as loi:
            GraphValidator().validate(
                resolved, DependencyGraph(resolved), {}, [DichVu]
            )

        assert "configure_refdata()" in str(loi.value)
