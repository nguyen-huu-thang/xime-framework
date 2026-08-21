"""Canh các bản vá của kiểm toán 0.8 ở tầng bus: T2, T3, T4, L1, L4, L5.

Gom một chỗ vì cả sáu đều là *"cơ chế có mặt nhưng không làm việc nó khai"* -
loại lỗi không có triệu chứng và không test nào chạm tới.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from xime.core.link import ChannelSpec, ProcessLink
from xime.core.link._cleanup import _PREFIXES, _owner_pid
from xime.core.link._layout import ChannelLayout

SPECS = {"ctl": ChannelSpec(rows=8, payload_bytes=64)}


# ---------------------------------------------------------------------------
# T2 - cảnh báo "kênh sắp đầy" phải đo VÙNG GHI, không đo hộp thư đến
# ---------------------------------------------------------------------------


class TestCanhBaoDoDungDaiLuong:
    """Cặp: người chỉ GỬI phải kêu, người chỉ NHẬN phải im.

    Bản trước đếm dòng chưa đọc GỬI TỚI MÌNH rồi in câu về *bảng ghi sắp đầy*.
    Sai cả hai chiều, và không một test nào chạm tới hàm đó.
    """

    def test_nguoi_chi_GUI_thi_KEU(self, caplog) -> None:
        link = ProcessLink.create(SPECS, 2, index=0)
        try:
            with caplog.at_level("WARNING", logger="xime.link"):
                for i in range(8):  # lấp trọn vùng ghi của chính mình
                    link.announce_sync("ctl", b"x", key=f"k{i}")
            assert any("full of unread rows" in r.message for r in caplog.records), (
                "vùng ghi đã đầy mà không có cảnh báo nào - phép đo đang nhìn "
                "sang hộp thư đến"
            )
        finally:
            link.close()

    def test_nguoi_chi_NHAN_thi_IM(self, caplog) -> None:
        """⚠ Phải dùng NĂM tiến trình, không phải hai - và đó là một phép đo.

        Ngưỡng cảnh báo là 0.8. Công thức SAI chia cho `total_rows` của cả
        kênh, nên với hai tiến trình thì hộp thư đến tối đa chỉ đạt
        `8 / (8*2) = 0.5` - không bao giờ chạm ngưỡng, và test sẽ XANH kể cả
        khi lỗi còn nguyên. Với năm tiến trình, bốn người kia lấp đầy phần của
        họ cho `32 / (8*5) = 0.8`: công thức sai thì KÊU, công thức đúng thì im
        vì vùng ghi của chính b mới dùng 1/8.

        Không có phép tính đó thì vế này chỉ là một dòng chữ, không phải một
        cái khoá.
        """
        so = 5
        a = ProcessLink.create(SPECS, so, index=0)
        khac = [ProcessLink.attach(a.link_id, SPECS, so, i, a.bells)
                for i in range(1, so)]
        b = khac[0]  # index 1 - người CHỈ NHẬN
        try:
            for link in [a] + khac[1:]:          # bốn người gửi, mỗi người 8 dòng
                for i in range(8):
                    link.announce_sync("ctl", b"x", key=f"k{i}")
            caplog.clear()
            with caplog.at_level("WARNING", logger="xime.link"):
                b.announce_sync("ctl", b"x", key="mot-tin")  # b ghi ĐÚNG MỘT dòng
            assert not any("full of unread rows" in r.message for r in caplog.records), (
                "b bị tố là 'bảng ghi sắp đầy' trong khi nó mới ghi 1/8 dòng - "
                "phép đo đang đếm hộp thư ĐẾN của b"
            )
        finally:
            for link in khac:
                link.close()
            a.close()


# ---------------------------------------------------------------------------
# T3 - sweep_orphans phải ĐƯỢC GỌI, không chỉ tồn tại
# ---------------------------------------------------------------------------


class TestSweepOrphansDuocNoi:
    """Canh CHỖ NỐI.

    Hàm này có 4 test, nằm trong `__all__`, docstring xếp nó là lớp che
    `kill -9` **duy nhất** - và trước bản vá thì **không đường khởi động nào
    gọi nó**. Test hàm đúng mà không test chỗ nối thì mọi thứ xanh.
    """

    def test_run_supervisor_co_goi_sweep_orphans(self) -> None:
        nguon = (Path(__file__).resolve().parents[2] / "xime" / "core"
                 / "bootstrap" / "_supervisor.py").read_text(encoding="utf-8")
        cay = ast.parse(nguon)
        ham = next((n for n in ast.walk(cay)
                    if isinstance(n, ast.FunctionDef) and n.name == "run_supervisor"), None)
        assert ham is not None, "không tìm thấy run_supervisor"
        goi = [n for n in ast.walk(ham)
               if isinstance(n, ast.Call)
               and getattr(n.func, "id", getattr(n.func, "attr", None)) == "sweep_orphans"]
        assert goi, (
            "run_supervisor không gọi sweep_orphans. Vùng nhớ chung của lần "
            "chạy trước bị kill -9 sẽ nằm lại trong /dev/shm mãi mãi."
        )


# ---------------------------------------------------------------------------
# T4 - sweep_orphans phải phủ CẢ BA họ vùng nhớ
# ---------------------------------------------------------------------------


class TestPhuCaBaHo:
    def test_ba_tien_to(self) -> None:
        assert set(_PREFIXES) == {"xime-link-", "xime-ref-", "xime-beat-"}, (
            "chú thích ở refdata/_arena.py khai rằng một lần dọn rác nhìn thấy "
            "cả hai họ; trước bản vá thì chỉ xime-link- được lọc"
        )

    @pytest.mark.parametrize("ten,pid", [
        ("xime-link-4242-abc123-ctl", 4242),
        ("xime-ref-4242-abc123-jwt-keys", 4242),
        ("xime-beat-4242-abc123", 4242),
        ("xime-khac-4242-abc", None),
        ("hoan-toan-khac", None),
    ])
    def test_doc_duoc_pid_cua_ca_ba_ho(self, ten: str, pid: int | None) -> None:
        assert _owner_pid(ten) == pid


# ---------------------------------------------------------------------------
# L1 - read_payload phải ép trần
# ---------------------------------------------------------------------------


class TestPayloadKhongTranRaNgoai:
    def test_do_dai_bi_bop_meo_khong_doc_lan_sang_dong_khac(self) -> None:
        layout = ChannelLayout(rows_per_writer=4, payload_bytes=64, process_count=2)
        buf = memoryview(bytearray(layout.total_bytes))
        layout.write_header(buf)
        layout.write_payload(buf, 0, b"A" * 64)
        layout.write_length(buf, 0, 64)
        assert len(layout.read_payload(buf, 0)) == 64

        # kẻ tấn công (hoặc một lỗi ghi) đặt độ dài lớn hơn dòng
        layout.write_length(buf, 0, layout.payload_bytes * 30)
        doc = layout.read_payload(buf, 0)
        assert len(doc) <= layout.payload_bytes, (
            f"đọc ra {len(doc)} byte từ một dòng chỉ chứa {layout.payload_bytes} - "
            "nội dung vùng ghi của tiến trình khác vừa chảy vào stats() và dump()"
        )


# ---------------------------------------------------------------------------
# L5 - `bump_missed` phải KHAI là không nguyên tử
# ---------------------------------------------------------------------------


class TestKhaiBaoKhongNguyenTu:
    def test_bump_missed_co_docstring_khai_ro(self) -> None:
        assert ChannelLayout.bump_missed.__doc__, (
            "`missed` là chỉ số chẩn đoán chính của bus và nó là đọc-sửa-ghi "
            "không nguyên tử. `next_sequence` ngay dưới có cả đoạn giải thích; "
            "chỗ này thì không, nên người sau phải tự phát hiện."
        )
        assert "nguyên tử" in ChannelLayout.bump_missed.__doc__


# ---------------------------------------------------------------------------
# L2 - `index` sai không được để lại rác trong /dev/shm
# ---------------------------------------------------------------------------


class TestIndexSaiKhongDeLaiRac:
    @pytest.mark.skipif(not os.path.isdir("/dev/shm"), reason="/dev/shm only")
    def test_khong_con_vung_nho_nao_sau_khi_bi_tu_choi(self) -> None:
        """Windows tự dọn khi tiến trình chết, **Linux thì không**.

        Vùng nhớ nằm lại tới lần khởi động máy. Nên phép kiểm phải chạy TRƯỚC
        khi cấp tài nguyên, không phải sau.
        """
        from xime.core.link import LinkError

        truoc = {x for x in os.listdir("/dev/shm") if x.startswith("xime-")}
        with pytest.raises(LinkError, match="outside"):
            ProcessLink.create(SPECS, 2, index=5)
        rac = {x for x in os.listdir("/dev/shm") if x.startswith("xime-")} - truoc
        assert not rac, (
            f"một `index` sai để lại {rac} trong /dev/shm - phép kiểm đang chạy "
            "sau khi đã cấp vùng nhớ"
        )

    def test_index_dung_van_dung_duoc(self) -> None:
        """Đối chứng âm: phép kiểm không được chặn nhầm giá trị hợp lệ."""
        link = ProcessLink.create(SPECS, 3, index=2)
        try:
            assert link.index == 2
        finally:
            link.close()
