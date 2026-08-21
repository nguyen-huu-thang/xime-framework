"""Canh T8, T9, T13 của kiểm toán 0.8 - nhóm CLI."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from xime.cli._config_check import check
from xime.cli._config_render import render
from xime.cli._init import build_plan, validate_name


# ---------------------------------------------------------------------------
# T8 - tên dự án không được sinh ra một dự án không chạy được
# ---------------------------------------------------------------------------


class TestTenDuAnBiCam:
    @pytest.mark.parametrize("ten", ["config", "resources", "xime", "main", "test", "tests"])
    def test_ten_dung_ham_voi_thu_muc_trinh_tao_bi_tu_choi(self, ten: str) -> None:
        assert validate_name(ten) is not None, (
            f"`xime init {ten}` sinh ra một dự án có hai khoá trùng nhau trong "
            f"cùng một dict literal: cái sau đè cái trước, ra 11 file thay vì "
            f"12, và file mất là config/__init__.py - nơi `import dependency` "
            f"nằm. Không lỗi nào phát ra lúc tạo."
        )

    @pytest.mark.parametrize("ten", ["json", "socket", "logging", "asyncio"])
    def test_ten_che_thu_vien_chuan_bi_tu_choi(self, ten: str) -> None:
        assert ten in sys.stdlib_module_names  # đối chứng cho chính phép kiểm
        assert validate_name(ten) is not None

    @pytest.mark.parametrize("ten", ["don-hang", "nha-tro", "shop2", "a"])
    def test_ten_binh_thuong_van_duoc_chap_nhan(self, ten: str) -> None:
        """Đối chứng âm: danh sách cấm không được nuốt tên hợp lệ."""
        assert validate_name(ten) is None

    def test_du_an_hop_le_sinh_ra_du_12_file(self, tmp_path: Path) -> None:
        plan = build_plan(tmp_path, "don-hang", "0.1.0")
        assert len(plan.files) == 12
        assert "config/__init__.py" in plan.files
        assert "import dependency" in plan.files["config/__init__.py"] or \
               "dependency" in plan.files["config/__init__.py"]

    def test_khoa_trung_thi_NO_chu_khong_de_im_lang(self, monkeypatch, tmp_path: Path) -> None:
        """Lớp thứ hai: `validate_name` chặn mọi cách trùng ĐÃ BIẾT.

        Lớp này bắt cách trùng chưa ai nghĩ tới - và đó chính là ca cần một
        thông báo lỗi thay vì một file bị mất im lặng.
        """
        from xime.cli import _init

        monkeypatch.setattr(_init, "module_name", lambda p: "config")
        with pytest.raises(ValueError, match="duplicate"):
            build_plan(tmp_path, "don-hang", "0.1.0")


# ---------------------------------------------------------------------------
# T9 - `check config` phải gợi ý khi TÊN KHỐI gõ sai
# ---------------------------------------------------------------------------


def _kiem(doc: dict, tmp_path: Path) -> list[str]:
    f = tmp_path / "application.yml"
    f.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return [f"{x.where}: {x.problem}" for x in check(f).findings]


class TestGoSaiTenKhoi:
    @pytest.mark.parametrize("go_sai,y_dinh", [
        ("serber", "server"), ("sever", "server"),
        ("grcp", "grpc"), ("procss", "process"),
    ])
    def test_bat_duoc_va_goi_y_dung(self, go_sai, y_dinh, tmp_path: Path) -> None:
        f = tmp_path / "application.yml"
        f.write_text(yaml.safe_dump({go_sai: {}}), encoding="utf-8")
        kq = check(f)
        assert kq.findings, f"{go_sai!r} đi lọt - ứng dụng sẽ chạy với mặc định"
        assert y_dinh in kq.findings[0].hint

    @pytest.mark.parametrize("cua_app", [
        "trust", "app", "shard", "dental", "organization", "payment", "notification",
    ])
    def test_khoi_cua_ung_dung_thi_IM(self, cua_app: str, tmp_path: Path) -> None:
        """⭐ Vế đối chứng, và là vế quyết định bản vá có dùng được không.

        Tố mọi tên lạ thì công cụ kêu oan ngay ngày đầu ở mọi ứng dụng Xime, và
        một phép dò kêu oan là một phép dò bị tắt.
        """
        assert not _kiem({cua_app: {"x": 1}}, tmp_path), (
            f"{cua_app!r} là khối của chính ứng dụng, framework không được tố nó"
        )

    def test_khoi_process_nay_la_HOP_LE(self, tmp_path: Path) -> None:
        """T10: `process:` từng không có trong bản mô tả, nên nó bị coi là lạ."""
        assert not _kiem({"process": {"web": {"port": 8080}}}, tmp_path)


# ---------------------------------------------------------------------------
# T13 - dự án mới không nghe trên mọi giao diện mạng mà không nói gì
# ---------------------------------------------------------------------------


class TestDuAnMoiNgheODauDuoc:
    def test_xime_init_ghi_host_127_va_giai_thich(self) -> None:
        noi_dung = render("don-hang", for_init=True)
        assert '\n  host: "127.0.0.1"' in noi_dung, (
            "dự án `xime init` sinh ra nghe trên 0.0.0.0 ngay lần chạy đầu"
        )
        i = noi_dung.index('host: "127.0.0.1"')
        truoc = noi_dung[max(0, i - 500) : i]
        assert "0.0.0.0" in truoc and "EVERY network" in truoc, (
            "phải nói ra 0.0.0.0 nghĩa là gì, ngay tại chỗ - file sinh ra có ba "
            "dòng chú thích cẩn thận về TLS rồi in host mà không một chữ nào"
        )

    def test_config_print_van_in_mac_dinh_THAT_cua_framework(self) -> None:
        """Đối chứng: bản vá không được làm `xime config --print` nói dối.

        31 ứng dụng hiện có KHÔNG chạy lại trình tạo, nên mặc định của framework
        phải giữ nguyên và phải được in ra đúng như nó là.
        """
        noi_dung = render("don-hang")
        assert '# host: "0.0.0.0"' in noi_dung
        assert 'host: "127.0.0.1"' not in noi_dung
