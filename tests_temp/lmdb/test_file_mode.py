"""Canh C1: kho LMDB không được để lộ cho user khác trên cùng máy.

Nội dung kho: hãm nhịp đăng nhập, thử thách passkey, chống lặp webhook. Và
docstring của chính gói khuyên đặt kho ở `/dev/shm` - thư mục mode `1777` mà
mọi user vào được, không cần quyền quản trị.

⚠ Test này CHỈ CHẠY TRÊN POSIX, nên nó **không** bảo vệ được nhánh Windows.
Đó là hiện thực của một sự thật chứ không phải thiếu sót: `chmod` gần như vô
nghĩa ở đó. Nhưng hệ quả phải nhớ: **CI chạy trên Windows sẽ báo xanh cho một
hồi quy ở đây.**
"""

from __future__ import annotations

import asyncio
import os
import stat
from pathlib import Path

import pytest

from xime.core.config.runtime import RuntimeConfig
from xime.starters.lmdb import CounterStore, LmdbEnvironment

posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits only")


class _HamNhip(CounterStore, name="canh-quyen", ttl=900, parts=1):
    """Bộ đếm hãm nhịp - đúng loại dữ liệu C1 nói tới."""


def _quyen(p: Path) -> int:
    return stat.S_IMODE(p.stat().st_mode)


async def _ghi_mot_khoa(root: Path, **them: object) -> None:
    rt = RuntimeConfig.from_dict({"lmdb": {"path": str(root), "map_size": "8MB", **them}})
    await _HamNhip(LmdbEnvironment(rt)).incr("tai-khoan:1.2.3.4")


class TestQuyenMacDinh:
    @posix_only
    def test_moi_thu_kho_tao_ra_deu_chi_chu_so_huu(self, tmp_path: Path) -> None:
        cu = os.umask(0o022)  # umask rộng nhất thường gặp, để phép đo có nghĩa
        try:
            asyncio.run(_ghi_mot_khoa(tmp_path))
        finally:
            os.umask(cu)

        ho = {str(p.relative_to(tmp_path)): oct(_quyen(p))
              for p in sorted(tmp_path.rglob("*")) if _quyen(p) & 0o077}
        assert not ho, (
            f"những thứ này group/other đọc được: {ho}. Kho giữ hãm nhịp và thử "
            "thách passkey, và đường dẫn tài liệu khuyên dùng là /dev/shm (1777)."
        )

    @posix_only
    def test_dung_ba_loai_tep_va_ca_ba_deu_chat(self, tmp_path: Path) -> None:
        """Canh từng loại một, vì C1 có BA chỗ tạo tệp chứ không phải một.

        Kiểm gộp bằng "không cái nào hở" sẽ vẫn xanh nếu một loại tệp biến mất
        khỏi cây thư mục vì lý do khác.
        """
        cu = os.umask(0o022)
        try:
            asyncio.run(_ghi_mot_khoa(tmp_path))
        finally:
            os.umask(cu)
        bang = tmp_path / "canh-quyen"
        assert _quyen(bang) == 0o700, "thư mục bảng (mkdir của framework)"
        assert _quyen(bang / ".parts") == 0o600, "marker .parts (write của framework)"
        assert _quyen(bang / "0.mdb") == 0o600, "tệp dữ liệu (lmdb.open)"
        assert _quyen(bang / "0.mdb-lock") == 0o600, "tệp khoá (lmdb.open)"


class TestNguoiVanHanhKhaiDuoc:
    @posix_only
    def test_gia_tri_khai_trong_cau_hinh_duoc_ton_trong(self, tmp_path: Path) -> None:
        cu = os.umask(0o022)
        try:
            asyncio.run(_ghi_mot_khoa(tmp_path, file_mode="0640", dir_mode="0750"))
        finally:
            os.umask(cu)
        bang = tmp_path / "canh-quyen"
        assert _quyen(bang) == 0o750
        assert _quyen(bang / "0.mdb") == 0o640


class TestSuaKhoDoBanCuTao:
    @posix_only
    def test_tep_dang_rong_bi_ha_xuong_khi_mo_lai(self, tmp_path: Path) -> None:
        cu = os.umask(0o022)
        try:
            asyncio.run(_ghi_mot_khoa(tmp_path))
            # giả lập kho do bản framework CŨ tạo ra
            for p in tmp_path.rglob("*"):
                os.chmod(p, 0o755 if p.is_dir() else 0o644)
            asyncio.run(_ghi_mot_khoa(tmp_path))
        finally:
            os.umask(cu)
        ho = {str(p.relative_to(tmp_path)): oct(_quyen(p))
              for p in sorted(tmp_path.rglob("*")) if _quyen(p) & 0o077}
        assert not ho, (
            f"kho cũ vẫn hở sau khi mở lại: {ho}. Bản vá chỉ áp cho tệp mới thì "
            "mọi cài đặt đang chạy vẫn hở nguyên sau khi nâng cấp."
        )

    @posix_only
    def test_marker_parts_cung_duoc_sua_o_duong_THOAT_SOM(self, tmp_path: Path) -> None:
        """Đường thoát sớm của `_check_parts` là đường đi qua MỖI LẦN MỞ.

        Đo được 2026-08-21: bản vá đầu chỉ hạ quyền ở nhánh GHI marker, nên mọi
        tệp khác về 0600 còn `.parts` ở lại 0644 mãi mãi. Test này canh đúng
        nhánh đó.
        """
        cu = os.umask(0o022)
        try:
            asyncio.run(_ghi_mot_khoa(tmp_path))
            marker = tmp_path / "canh-quyen" / ".parts"
            os.chmod(marker, 0o644)
            asyncio.run(_ghi_mot_khoa(tmp_path))  # parts KHÔNG đổi -> thoát sớm
        finally:
            os.umask(cu)
        assert _quyen(marker) == 0o600

    @posix_only
    def test_tep_CHAT_hon_thi_khong_bi_noi_ra(self, tmp_path: Path) -> None:
        """Đối chứng âm: phép sửa chỉ đi MỘT chiều."""
        from xime.starters.lmdb._env import _sieu_chat

        t = tmp_path / "chat-hon"
        t.write_bytes(b"x")
        os.chmod(t, 0o400)
        _sieu_chat(t, 0o600)
        assert _quyen(t) == 0o400, "framework không được nới quyền của ai"

    @posix_only
    def test_phep_sua_biet_lam_viec(self, tmp_path: Path) -> None:
        """Đối chứng dương cho chính phép sửa."""
        from xime.starters.lmdb._env import _sieu_chat

        t = tmp_path / "rong"
        t.write_bytes(b"x")
        os.chmod(t, 0o666)
        _sieu_chat(t, 0o600)
        assert _quyen(t) == 0o600
