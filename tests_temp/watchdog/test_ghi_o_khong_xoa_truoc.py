"""Canh bản vá lỗi *"ô nhịp đang chạy bỗng quay về 0"* (2026-09-01).

## Lỗi được canh ở đây

`struct.pack_into` **xoá vùng đích về 0 trước khi ghi** - nó phải làm vậy để
byte đệm luôn bằng 0. Trong một tiến trình thì GIL che mất cửa sổ ấy; giữa hai
tiến trình thì không có gì che.

Mà số 0 hầu như luôn là một giá trị mang nghĩa riêng, và nghĩa đó thường là
*"chưa có gì"*: `_watchdog.NEVER = 0.0` nghĩa là *"con này chưa bao giờ vỗ
nhịp"*, `_refdata.NEVER_PUBLISHED = 0` nghĩa là *"bảng này chưa ai publish"*.
Đọc trúng cửa sổ đó thì cha **giết một tiến trình đang khoẻ**, hoặc một request
hợp lệ nhận **401** vì bảng khoá JWT bỗng trông như rỗng.

Đo được 2026-09-01, hai tiến trình, 34,6 triệu lượt đọc: `pack_into` cho
1.658.361 lượt thấy toàn số 0 (4,79%), `ghi_o` cho **0**.

## Vì sao mỗi test đi thành cặp

Một test chỉ khẳng định *"`ghi_o` không xoá"* sẽ xanh cả khi `ghi_o` bị sửa
thành một hàm rỗng. Nên mỗi phép kiểm ở đây có **positive control**: cùng phép
đo chạy trên `pack_into` và **phải thấy hành vi xấu**. Ngày CPython bỏ bước
memset thì đối chứng đó đỏ, và đó là tín hiệu đúng - không phải để đi sửa test
cho xanh, mà để biết tiền đề của bản vá đã đổi.
"""
from __future__ import annotations

import struct
import time

import pytest

from xime.core.bootstrap._watchdog import Heartbeats
from xime.core.shared import MP_CONTEXT, ghi_o

_MAU = struct.Struct("<dQ")
_DAU = 8
_NEN = b"\xff"


class TestGhiOKhongXoaVungTruocKhiGhi:
    def test_ghi_o_chi_dung_dung_so_byte_cua_no(self) -> None:
        vung = memoryview(bytearray(_NEN * 64))
        ghi_o(vung, _DAU, _MAU, 1.5, 7)

        assert _MAU.unpack_from(vung, _DAU) == (1.5, 7)
        assert bytes(vung[:_DAU]) == _NEN * _DAU, "ghi lan sang truoc vung"
        cuoi = _DAU + _MAU.size
        assert bytes(vung[cuoi:]) == _NEN * (64 - cuoi), "ghi lan sang sau vung"

    def test_DOI_CHUNG_pack_into_THI_CO_xoa(self) -> None:
        """Positive control. Đỏ ở đây nghĩa là tiền đề của bản vá đã đổi.

        ⚠ Phải dùng `"BQ"` **không có `<`** - tức căn lề theo máy, `1 + 7 đệm +
        8 = 16` byte. Mọi format có `<` đều khít, không có byte đệm nào, nên
        chúng **không lộ ra được** bước memset. Bản đầu của test này viết `<BQ`
        và đỏ oan; cái sai nằm ở phép đo, không ở thứ được đo.
        """
        mau_co_dem = struct.Struct("BQ")
        assert mau_co_dem.size == 16, "nen nay khong co byte dem - doi chung vo nghia"
        vung = bytearray(_NEN * 32)
        mau_co_dem.pack_into(vung, 0, 1, 2)

        assert vung[1:8] == bytes(7), (
            "pack_into KHONG con xoa vung truoc khi ghi. Neu CPython da bo buoc "
            "memset thi ly do ton tai cua ghi_o mat, va phai xem lai ban va."
        )


class TestKhongConDuongGhiNaoDungPackInto:
    """`pack_into` chỉ còn được phép ở đường **dựng** một vùng nhớ mới.

    Ở đó chưa tiến trình nào attach, nên không có ai để mà đọc dở. Mọi chỗ khác
    phải đi qua `ghi_o`.
    """

    #: Khai tường minh, theo đúng khuôn danh sách ngoại lệ của luật 01: không
    #: cấm, nhưng bắt mỗi lần thêm phải đi qua một quyết định.
    DUOC_PHEP = {
        ("xime/core/bootstrap/_watchdog.py", "create"),
        ("xime/core/link/_layout.py", "write_header"),
        ("xime/core/refdata/_layout.py", "write_header"),
    }

    def test_moi_pack_into_deu_nam_trong_ham_dung_vung_nho(self) -> None:
        import ast
        from pathlib import Path

        goc = Path(__file__).resolve().parents[2]
        thay: set[tuple[str, str]] = set()
        for tep in (goc / "xime").rglob("*.py"):
            cay = ast.parse(tep.read_text(encoding="utf-8"))
            for ham in ast.walk(cay):
                if not isinstance(ham, ast.FunctionDef):
                    continue
                for nut in ast.walk(ham):
                    if (
                        isinstance(nut, ast.Call)
                        and isinstance(nut.func, ast.Attribute)
                        and nut.func.attr == "pack_into"
                    ):
                        ten = tep.relative_to(goc).as_posix()
                        thay.add((ten, ham.name))

        assert thay == self.DUOC_PHEP, (
            f"Danh sach chO dung `pack_into` da doi.\n"
            f"  them: {sorted(thay - self.DUOC_PHEP)}\n"
            f"  mat : {sorted(self.DUOC_PHEP - thay)}\n"
            f"`pack_into` xoa vung ve 0 truoc khi ghi, nen no chi an toan o "
            f"duong DUNG vung nho - luc chua ai attach. Dung `ghi_o` o moi cho "
            f"khac, va neu that su can them mot ngoai le thi khai no vao day "
            f"kem ly do."
        )


def _con_vo_het_toc_luc(run_id: str, giay: float) -> None:
    beats = Heartbeats.attach(run_id, 2)
    han = time.monotonic() + giay
    while time.monotonic() < han:
        beats.pat(0)
    beats.close()


class TestChaKhongBaoGioDocRaChuaVoLanNao:
    """Phép đo đầu-cuối: đúng hình dạng lỗi thật, chỉ nén thời gian lại.

    Con vỗ hết tốc lực, cha đọc hết tốc lực. Với đường ghi cũ, cha kết luận sai
    *"con này chưa bao giờ vỗ nhịp"* khoảng 1% số lượt đọc; với đường ghi mới,
    không lượt nào.
    """

    GIAY = 2.0

    def test_con_dang_vo_thi_cha_KHONG_BAO_GIO_thay_chua_vo_lan_nao(self) -> None:
        run_id = f"canh-ghio-{time.time_ns()}"
        beats = Heartbeats.create(run_id, 2)
        con = MP_CONTEXT.Process(
            target=_con_vo_het_toc_luc, args=(run_id, self.GIAY)
        )
        con.start()
        try:
            # ⚠ CHỜ nhịp đầu tiên, đừng `sleep` một con số đoán trước. Tiến
            # trình `spawn` phải nạp lại Python và cả cây import của pytest -
            # bản đầu của test này ngủ 0,3 giây rồi đếm luôn, và 9% số lượt đọc
            # rơi vào lúc con **chưa attach**. Khi đó `silent_for` trả `None`
            # hoàn toàn đúng, nhưng test lại đọc nó thành lỗi 2 quay lại.
            han_cho = time.monotonic() + 30.0
            while beats.so_nhip(0) == 0:
                if time.monotonic() > han_cho:
                    pytest.fail("con khong vo duoc nhip nao trong 30 giay")
                time.sleep(0.01)

            so_doc = sai = 0
            han = time.monotonic() + self.GIAY - 0.5
            while time.monotonic() < han:
                so_doc += 1
                if beats.silent_for(0) is None:
                    sai += 1
        finally:
            con.join(30)
            beats.close()

        assert so_doc > 1000, f"chi doc duoc {so_doc} lan - phep do khong du manh"
        assert sai == 0, (
            f"{sai}/{so_doc} luot doc ket luan SAI rang con chua bao gio vo "
            f"nhip, trong khi no dang vo lien tuc. Day la loi 2 quay lai: mot "
            f"duong ghi nao do da tro ve `pack_into`."
        )
