"""Canh các bản vá T5, T6, T7 của kiểm toán 0.8."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from xime.core.config.runtime import RuntimeConfig
from xime.core.refdata import RefData, RefDataArena, specs_of
from xime.core.refdata._layout import FLAG_STALE, FLAGS_OFFSET
from xime.starters.lmdb import CounterStore, LmdbEnvironment


class _Bang(RefData[bytes], name="t5-stale", max_bytes=64):
    def encode(self, value: bytes) -> bytes:
        return value

    def decode(self, raw: memoryview) -> bytes:
        return bytes(raw)


_SPECS = specs_of((_Bang,))


# ---------------------------------------------------------------------------
# T5 - cờ `stale` phải nhìn thấy được từ MỌI tiến trình
# ---------------------------------------------------------------------------


class TestCoStaleNamTrongVungNhoChung:
    """Trước bản vá, cờ này là thuộc tính instance của primary.

    Nghĩa là câu *"dữ liệu cụm đang phục vụ có cũ không"* chỉ trả lời được từ
    chính tiến trình đã hỏng, và một primary MỚI được thăng cấp bắt đầu với
    `stale=False` trong khi dữ liệu vẫn cũ.
    """

    def test_tien_trinh_khac_thay_duoc_stale(self) -> None:
        cha = RefDataArena.create(_SPECS, index=0, primary=True)
        con = RefDataArena.attach(cha.run_id, _SPECS, index=1, primary=False)
        try:
            b_cha, b_con = _Bang(cha), _Bang(con)
            asyncio.run(b_cha.publish(b"vua-du"))
            assert b_con.stats().stale is False

            with pytest.raises(Exception):
                asyncio.run(b_cha.publish(b"x" * 500))  # không vừa trần

            assert b_cha.stats().stale is True
            assert b_con.stats().stale is True, (
                "tiến trình KHÔNG phải primary vẫn báo dữ liệu bình thường "
                "trong khi cả cụm đang phục vụ bản cũ - cờ đang nằm trong RAM "
                "của riêng primary"
            )
        finally:
            con.close()
            cha.close()

    def test_publish_thanh_cong_thi_co_tat_lai(self) -> None:
        """Đối chứng: cờ phải hạ được, không phải một chiều."""
        cha = RefDataArena.create(_SPECS, index=0, primary=True)
        con = RefDataArena.attach(cha.run_id, _SPECS, index=1, primary=False)
        try:
            b_cha, b_con = _Bang(cha), _Bang(con)
            with pytest.raises(Exception):
                asyncio.run(b_cha.publish(b"x" * 500))
            assert b_con.stats().stale is True
            asyncio.run(b_cha.publish(b"nho-lai"))
            assert b_con.stats().stale is False
        finally:
            con.close()
            cha.close()

    def test_co_nam_dung_o_hai_byte_dem_cu(self) -> None:
        """Khoá vị trí, vì đổi nó về sau là đổi khuôn vùng nhớ."""
        assert FLAGS_OFFSET == 6
        assert FLAG_STALE == 0x0001


# ---------------------------------------------------------------------------
# T6 - đổi `parts` không được xoá tại chỗ khi N tiến trình cùng khởi động
# ---------------------------------------------------------------------------


class TestDoiPartsKhongXoaTaiCho:
    def test_dung_os_rename_chu_khong_rmtree_tai_cho(self) -> None:
        """Canh CƠ CHẾ, vì đua thật không tái hiện được đáng tin trong test.

        `ignore_errors=True` nuốt mọi va chạm, nên một lần đua hỏng **không để
        lại dấu vết nào** - không exception, không log. Không có gì để đo sau
        khi nó xảy ra, nên phải khoá cách làm.
        """
        nguon = (Path(__file__).resolve().parents[2] / "xime" / "starters"
                 / "lmdb" / "_env.py").read_text(encoding="utf-8")
        i = nguon.index("def _check_parts")
        than = nguon[i : nguon.index("\n    def ", i + 10)]
        assert "os.rename(table_dir" in than, (
            "_check_parts xoá thư mục bảng tại chỗ. Đổi `parts` là sự kiện lúc "
            "triển khai, tức đúng lúc N tiến trình cùng chạy đoạn này."
        )
        assert than.index("os.rename(table_dir") < than.index("shutil.rmtree"), (
            "phải đổi tên TRƯỚC rồi mới xoá - đó là chỗ tính nguyên tử nằm"
        )

    def test_doi_parts_van_lam_dung_viec_cua_no(self, tmp_path: Path) -> None:
        """Đối chứng: bản vá không được làm hỏng chức năng gốc."""

        class _A(CounterStore, name="t6", ttl=900, parts=2):
            pass

        class _B(CounterStore, name="t6", ttl=900, parts=4):
            pass

        rt = RuntimeConfig.from_dict({"lmdb": {"path": str(tmp_path), "map_size": "8MB"}})
        asyncio.run(_A(LmdbEnvironment(rt)).incr("k"))
        assert (tmp_path / "t6" / ".parts").read_text(encoding="utf-8") == "2"
        asyncio.run(_B(LmdbEnvironment(rt)).incr("k"))
        assert (tmp_path / "t6" / ".parts").read_text(encoding="utf-8") == "4"
        con_lai = [p.name for p in tmp_path.iterdir() if p.name.startswith("t6.cu-")]
        assert not con_lai, f"thư mục cũ chưa được dọn: {con_lai}"


# ---------------------------------------------------------------------------
# T7 - hãm luỹ tiến khi con chết liên tục
# ---------------------------------------------------------------------------


class TestHamKhiConChetLienTuc:
    def test_cho_lau_dan_va_co_TRAN(self, monkeypatch) -> None:
        from xime.core.bootstrap import _supervisor as sup

        cho: list[float] = []
        monkeypatch.setattr(sup.time, "sleep", cho.append)

        node = sup.Supervisor.__new__(sup.Supervisor)
        node._children = {}
        node._spawned_at = {}
        node._killed_by_me = {}
        node._respawns = {}
        node._stopping = False
        node._primary_id = None
        monkeypatch.setattr(node, "_spawn", lambda pid: None)

        class _Xac:
            exitcode = 1

            def join(self, timeout=None) -> None: ...

        for _ in range(14):
            node._children["api"] = _Xac()
            node._spawned_at["api"] = time.monotonic()  # chết ngay, không sống nổi
            node._respawn("api")

        assert cho[:5] == [1.0, 2.0, 4.0, 8.0, 16.0], f"phải gấp đôi dần: {cho[:5]}"
        assert max(cho) == sup._RESPAWN_DELAY_MAX, (
            f"phải có trần {sup._RESPAWN_DELAY_MAX}s, đo được {max(cho)}s"
        )
        assert len(cho) == 14, "supervisor phải LUÔN thử lại, không được bỏ cuộc"

    def test_song_du_lau_thi_ham_ve_KHONG(self, monkeypatch) -> None:
        """Vế thứ hai của cặp.

        Chỉ canh *"hãm tăng dần"* thì cách hiện thực sai *"không bao giờ reset"*
        cũng qua - và cách đó biến một cụm khoẻ, sau vài lần restart tình cờ
        trong nhiều tháng, thành một cụm chờ 30 giây mỗi lần restart.
        """
        from xime.core.bootstrap import _supervisor as sup

        cho: list[float] = []
        monkeypatch.setattr(sup.time, "sleep", cho.append)
        node = sup.Supervisor.__new__(sup.Supervisor)
        node._children, node._spawned_at, node._respawns = {}, {}, {}
        node._killed_by_me = {}
        node._stopping, node._primary_id = False, None
        monkeypatch.setattr(node, "_spawn", lambda pid: None)

        class _Xac:
            exitcode = 1

            def join(self, timeout=None) -> None: ...

        for _ in range(3):
            node._children["api"] = _Xac()
            node._spawned_at["api"] = time.monotonic()
            node._respawn("api")
        assert cho[-1] == 4.0

        node._children["api"] = _Xac()
        # đã sống qua ngưỡng: lần chết này không cùng chuỗi với ba lần trên
        node._spawned_at["api"] = time.monotonic() - sup._RESPAWN_RESET_AFTER - 1
        node._respawn("api")
        assert cho[-1] == 1.0, (
            f"con sống được hơn {sup._RESPAWN_RESET_AFTER}s rồi mới chết mà bộ "
            f"hãm không reset: chờ {cho[-1]}s"
        )
