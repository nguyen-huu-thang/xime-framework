"""Con không được sống lâu hơn cha - `_orphan.py`.

`_supervisor.py` khai con mồ côi là kết cục tệ nhất, nhưng lớp phòng thủ ở đó
chỉ **bắt tín hiệu**, nên nó che được cái chết lịch sự của cha chứ không che
được `SIGKILL` / `Stop-Process -Force` / cha sập. Bộ test này canh phần lấp.

⚠ Test ở đây **không** sinh tiến trình thật: chúng lái `OrphanGuard` bằng một
cha giả. Phép đo đầu-cuối (giết cha thật bằng `-Force`, xem con thoát và cổng
được trả) đã chạy tay trên Windows 11 ngày 2026-08-23, ghi trong CHANGELOG.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import threading

import pytest

from xime.core.bootstrap import _orphan
from xime.core.bootstrap._orphan import OrphanGuard


class _ChaGia:
    """Cha giả: `join()` chặn tới khi test cho phép nó chết."""

    def __init__(self, pid: int = 4242) -> None:
        self.pid = pid
        self._da_chet = threading.Event()

    def join(self, timeout: float | None = None) -> None:
        self._da_chet.wait(timeout)

    def chet(self) -> None:
        self._da_chet.set()


class TestKhongCoChaThiKhongCanh:
    """Chạy tay một tiến trình, chạy trong test, chạy dưới trình giám sát khác."""

    @pytest.mark.asyncio
    async def test_khong_co_cha_thi_start_khong_lam_gi(self, monkeypatch) -> None:
        monkeypatch.setattr(_orphan.multiprocessing, "parent_process", lambda: None)
        guard = OrphanGuard()
        guard.start()
        assert guard._thread is None

    @pytest.mark.asyncio
    async def test_goi_start_hai_lan_chi_co_MOT_thread(self, monkeypatch) -> None:
        cha = _ChaGia()
        monkeypatch.setattr(_orphan.multiprocessing, "parent_process", lambda: cha)
        guard = OrphanGuard()
        try:
            guard.start()
            dau = guard._thread
            guard.start()
            assert guard._thread is dau
        finally:
            guard.stop()
            cha.chet()

    def test_khong_co_loop_thi_khong_canh(self, monkeypatch) -> None:
        """Không loop nghĩa là chưa phục vụ ai, và không có gì để huỷ êm."""
        cha = _ChaGia()
        monkeypatch.setattr(_orphan.multiprocessing, "parent_process", lambda: cha)
        guard = OrphanGuard()
        guard.start()
        assert guard._thread is None


class TestChaChetThiConDi:
    @pytest.mark.asyncio
    async def test_cha_chet_thi_gui_tin_hieu_dung_bang_lan_tat_binh_thuong(
        self, monkeypatch, caplog
    ) -> None:
        cha = _ChaGia(pid=777)
        monkeypatch.setattr(_orphan.multiprocessing, "parent_process", lambda: cha)
        da_gui: list[int] = []
        # ⚠ Bắt CẢ HAI đường, rồi mới khẳng định đường nào phải chạy. Chỉ vá
        # một đường là dựng lại đúng cái bẫy đã cắn ba lần ở repo này: một phép
        # đo xanh vì nó không bao giờ chạy nhánh của nền tảng kia.
        monkeypatch.setattr(signal, "raise_signal", da_gui.append)
        monkeypatch.setattr(
            _orphan.os, "kill", lambda _pid, sig: da_gui.append(sig)
        )
        cat: list[int] = []
        monkeypatch.setattr(_orphan.os, "_exit", cat.append)

        guard = OrphanGuard(grace=30.0)
        with caplog.at_level(logging.CRITICAL, logger="xime.bootstrap"):
            guard.start()
            cha.chet()
            for _ in range(200):
                if da_gui:
                    break
                await asyncio.sleep(0.01)

        assert da_gui == [signal.SIGTERM], (
            "phải đi bằng ĐÚNG tín hiệu mà cha dùng lúc tắt êm - một đường tắt "
            "thứ hai là chỗ hành vi hai bên trôi ra khỏi nhau"
        )
        assert "777" in caplog.text
        assert cat == [], "chưa hết hạn thì không được cắt"

    @pytest.mark.asyncio
    async def test_gui_tin_hieu_hong_thi_HUY_task_lam_duong_lui(
        self, monkeypatch
    ) -> None:
        cha = _ChaGia()
        monkeypatch.setattr(_orphan.multiprocessing, "parent_process", lambda: cha)

        def _hong(*_args):
            raise OSError("khong gui duoc")

        monkeypatch.setattr(signal, "raise_signal", _hong)
        monkeypatch.setattr(_orphan.os, "kill", _hong)
        monkeypatch.setattr(_orphan.os, "_exit", lambda code: None)

        guard = OrphanGuard(grace=30.0)
        guard.start()
        cha.chet()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.sleep(3.0)

    @pytest.mark.asyncio
    async def test_da_stop_roi_thi_cha_chet_la_chuyen_BINH_THUONG(
        self, monkeypatch, caplog
    ) -> None:
        """Tắt êm: con dừng trước, cha biến mất sau. Không có gì để báo."""
        cha = _ChaGia()
        monkeypatch.setattr(_orphan.multiprocessing, "parent_process", lambda: cha)
        da_gui: list[int] = []
        monkeypatch.setattr(signal, "raise_signal", da_gui.append)
        monkeypatch.setattr(
            _orphan.os, "kill", lambda _pid, sig: da_gui.append(sig)
        )

        guard = OrphanGuard(grace=30.0)
        with caplog.at_level(logging.CRITICAL, logger="xime.bootstrap"):
            guard.start()
            guard.stop()
            cha.chet()
            await asyncio.sleep(0.3)

        assert da_gui == []
        assert "orphan" not in caplog.text


class TestHanChotCat:
    @pytest.mark.asyncio
    async def test_qua_han_thi_cat_bang_ma_thoat_KHAC_khong(
        self, monkeypatch, caplog
    ) -> None:
        """Tắt êm treo thì vẫn phải trả cổng - đó là toàn bộ việc còn lại."""
        cat: list[int] = []
        monkeypatch.setattr(_orphan.os, "_exit", cat.append)
        with caplog.at_level(logging.CRITICAL, logger="xime.bootstrap"):
            OrphanGuard(grace=0.01)._cut()
        assert cat == [_orphan.EXIT_CODE]
        assert _orphan.EXIT_CODE != 0, "mã 0 sẽ bị đọc thành một lần tắt bình thường"
        assert "hard way" in caplog.text


class TestChoNoiChuKhongChiLaHam:
    """Canh việc guard ĐƯỢC CẮM, không chỉ việc nó chạy đúng khi gọi tay.

    Cùng lỗ hổng đã trả giá hai lần trong tuần này (uvloop 0.8.1, dòng log xác
    thực): test gọi thẳng hàm thì gỡ lời gọi ra khỏi vòng đời cũng không đỏ.
    """

    @pytest.mark.asyncio
    async def test_cluster_listen_co_cam_guard(self, monkeypatch) -> None:
        from xime.core.bootstrap._cluster import ClusterMember

        cha = _ChaGia()
        monkeypatch.setattr(_orphan.multiprocessing, "parent_process", lambda: cha)
        member = ClusterMember(None, share_load=False)
        try:
            await member.listen({}, _khong_lam_gi)
            assert member._orphan is not None, (
                "listen() phải cắm OrphanGuard - và phải cắm TRƯỚC lối ra sớm "
                "`if self._link is None`, kẻo ứng dụng không khai kênh bus nào "
                "thì mất hẳn phép canh"
            )
            assert member._orphan._thread is not None
        finally:
            if member._orphan is not None:
                member._orphan.stop()
            cha.chet()

    @pytest.mark.asyncio
    async def test_quiesce_thoi_canh(self, monkeypatch) -> None:
        from xime.core.bootstrap._cluster import ClusterMember

        cha = _ChaGia()
        monkeypatch.setattr(_orphan.multiprocessing, "parent_process", lambda: cha)
        member = ClusterMember(None, share_load=False)
        await member.listen({}, _khong_lam_gi)
        guard = member._orphan
        assert guard is not None
        await member.quiesce()
        assert member._orphan is None
        assert guard._stopping.is_set()
        cha.chet()


async def _khong_lam_gi(_flag: bool) -> None:
    return None


class TestMaThoatNoiDuocAiGiet:
    """`_foreign_death` - luật 03 ở tầng log của supervisor."""

    def test_ma_duong_la_tu_thoat(self) -> None:
        from xime.core.bootstrap._supervisor import _foreign_death

        assert "on its own" in _foreign_death(1)
        assert "on its own" in _foreign_death(0)

    @pytest.mark.skipif(sys.platform != "win32", reason="chỉ đúng trên Windows")
    def test_windows_am_15_KHONG_phai_tin_hieu_tu_ben_ngoai(self) -> None:
        """Chỗ đã làm một phiên mất nửa buổi.

        CPython đổi `TERMINATE = 0x10000` thành `-SIGTERM`, mà `0x10000` chỉ do
        chính `multiprocessing` ghi. `taskkill /F` ghi 1, `Stop-Process -Force`
        ghi `0xFFFFFFFF`. Nên `-15` ở đây là bằng chứng của một CỤM CŨ chưa tắt.
        """
        from xime.core.bootstrap._supervisor import _foreign_death

        loi = _foreign_death(-15)
        assert "another multiprocessing parent" in loi
        assert "leftover supervisor" in loi

    def test_chua_chet_thi_noi_ro_la_chua_ket_luan_duoc(self) -> None:
        from xime.core.bootstrap._supervisor import _foreign_death

        assert "?" in _foreign_death(None)


class TestSupervisorKhaiAiGiet:
    """Log lúc con chết phải nói AI giết, không chỉ nói MÃ THOÁT.

    Một mã thoát mang hai nghĩa bắt người đọc log đoán, và hai nghĩa đó dẫn
    tới hai việc ngược nhau: *"watchdog của tôi vừa giết nó vì nó treo"* là
    chuyện nội bộ đã xử lý xong, còn *"ai đó bên ngoài giết nó"* là một tiến
    trình khác đang can thiệp - thường là một cụm cũ chưa tắt hẳn.
    """

    def _node(self, monkeypatch):
        from xime.core.bootstrap import _supervisor as sup

        monkeypatch.setattr(sup.time, "sleep", lambda _s: None)
        node = sup.Supervisor.__new__(sup.Supervisor)
        node._children, node._spawned_at, node._respawns = {}, {}, {}
        node._killed_by_me = {}
        node._stopping, node._primary_id = False, None
        monkeypatch.setattr(node, "_spawn", lambda pid: None)
        return node

    class _Xac:
        exitcode = -15

        def join(self, timeout=None) -> None: ...

    def test_watchdog_cua_chinh_minh_giet_thi_KHAI_RA(
        self, monkeypatch, caplog
    ) -> None:
        node = self._node(monkeypatch)
        node._children["api"] = self._Xac()
        node._killed_by_me["api"] = "my watchdog killed it: event loop blocked"
        with caplog.at_level(logging.WARNING, logger="xime.bootstrap"):
            node._respawn("api")
        assert "my watchdog killed it" in caplog.text
        assert "NOT me" not in caplog.text

    def test_khong_phai_minh_giet_thi_noi_ro_KHONG_PHAI_MINH(
        self, monkeypatch, caplog
    ) -> None:
        node = self._node(monkeypatch)
        node._children["api"] = self._Xac()
        with caplog.at_level(logging.WARNING, logger="xime.bootstrap"):
            node._respawn("api")
        assert "NOT me" in caplog.text

    def test_loi_khai_khong_song_sang_lan_chet_SAU(self, monkeypatch) -> None:
        """Con mới sinh thì xoá lời khai của con cũ cùng tên.

        Không xoá thì lần chết sau bị gán lý do của lần trước - một dòng log
        đúng cú pháp và sai sự thật, loại khó phát hiện nhất.
        """
        node = self._node(monkeypatch)
        node._children["api"] = self._Xac()
        node._killed_by_me["api"] = "my watchdog killed it: event loop blocked"
        node._respawn("api")
        assert "api" not in node._killed_by_me
