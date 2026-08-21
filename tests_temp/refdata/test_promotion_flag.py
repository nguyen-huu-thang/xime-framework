"""Canh C3: cờ primary có đúng MỘT nguồn sự thật.

Ca thật (kiểm toán 0.8): `Application._is_primary` được cập nhật lúc thăng cấp,
còn `RefDataArena._primary` **không có setter nào tồn tại** - mà `publish()` hỏi
đúng cái cờ không được cập nhật. Hậu quả: primary MỚI không bao giờ cập nhật
được khoá JWT nữa, trong khi cha log "took the primary role" và `/healthz` trả
`primary: true`. Triệu chứng nói ngược sự thật.

⭐ Test đi thành CẶP, và cặp ở đây là bắt buộc chứ không phải cho đủ: chỉ canh
vế "thăng cấp thì publish được" thì cách sửa sai *"cho publish luôn"* cũng qua,
mà cách sửa đó biến một con **đã từ chối vai** thành người ghi thứ hai.
"""

from __future__ import annotations

from xime.core.refdata import RefData, specs_of
from xime.core.refdata._arena import RefDataArena


class _Counter(RefData[dict], name="co-primary", max_bytes=8192):
    def encode(self, value: dict) -> bytes:
        return repr(value).encode("utf-8")

    def decode(self, raw: memoryview) -> dict:
        return eval(bytes(raw).decode("utf-8"))  # noqa: S307 - test cuc bo


SPECS_FOR_TEST = specs_of((_Counter,))


class _GiaLapApp:
    """Đứng thay `Application`: chỉ giữ đúng cái cờ mà `_accept_promotion` đổi."""

    def __init__(self) -> None:
        self.is_primary = False


class TestCoPrimaryChiCoMotNguon:
    def test_thang_cap_thi_arena_theo_kip(self) -> None:
        app = _GiaLapApp()
        arena = RefDataArena.create(SPECS_FOR_TEST, index=0, primary=lambda: app.is_primary)
        try:
            assert arena.primary is False
            app.is_primary = True  # _accept_promotion
            assert arena.primary is True, (
                "arena vẫn nói không phải primary sau khi thăng cấp - cờ đang có "
                "hai bản sao, và publish() sẽ bị chặn ở tiến trình vừa nhận vai"
            )
        finally:
            arena.close()

    def test_tu_choi_vai_thi_arena_cung_quay_lai(self) -> None:
        app = _GiaLapApp()
        arena = RefDataArena.create(SPECS_FOR_TEST, index=0, primary=lambda: app.is_primary)
        try:
            app.is_primary = True
            assert arena.primary is True
            app.is_primary = False  # nhánh từ chối vai của _accept_promotion
            assert arena.primary is False, (
                "arena vẫn nói là primary sau khi tiến trình TỪ CHỐI vai - "
                "cụm sẽ có hai người ghi"
            )
        finally:
            arena.close()

    def test_bool_tinh_van_chay(self) -> None:
        """Đối chứng: bản vá không được phá cách gọi cũ."""
        arena = RefDataArena.create(SPECS_FOR_TEST, index=0, primary=True)
        try:
            assert arena.primary is True
        finally:
            arena.close()
        arena = RefDataArena.create(SPECS_FOR_TEST, index=0, primary=False)
        try:
            assert arena.primary is False
        finally:
            arena.close()

    def test_application_truyen_HAM_chu_khong_truyen_gia_tri(self) -> None:
        """Canh chỗ NỐI, không chỉ canh cơ chế.

        `sweep_orphans` là ca thật ở repo này: hàm đúng, có test, nằm trong
        `__all__`, và **không đường khởi động nào gọi**. Cơ chế đúng mà nối sai
        thì không gì đỏ.

        Soi bằng AST chứ không tìm chuỗi: `primary=self._is_primary` cũng xuất
        hiện ở `HealthReport(...)`, nơi một giá trị chụp tại chỗ là ĐÚNG. Tìm
        chuỗi sẽ tố oan đúng dòng không có lỗi.
        """
        import ast
        from pathlib import Path

        nguon = (Path(__file__).resolve().parents[2]
                 / "xime" / "core" / "bootstrap" / "application.py").read_text(encoding="utf-8")
        goi_arena = []
        for nut in ast.walk(ast.parse(nguon)):
            if not isinstance(nut, ast.Call) or not isinstance(nut.func, ast.Attribute):
                continue
            goc = nut.func.value
            if not (isinstance(goc, ast.Name) and goc.id == "RefDataArena"):
                continue
            if nut.func.attr not in ("create", "attach"):
                continue
            kw = {k.arg: k.value for k in nut.keywords}
            goi_arena.append((nut.func.attr, nut.lineno, kw.get("primary")))

        assert goi_arena, "không tìm thấy lời gọi RefDataArena.create/attach nào"
        xau = [(ten, dong) for ten, dong, val in goi_arena
               if not isinstance(val, ast.Lambda)]
        assert not xau, (
            "RefDataArena được dựng với GIÁ TRỊ primary thay vì một HÀM: "
            f"{xau}. Vai primary đổi lúc chạy (thăng cấp / từ chối vai), nên "
            "một giá trị chụp lúc dựng arena sẽ đứng yên qua cả hai lần đổi."
        )
