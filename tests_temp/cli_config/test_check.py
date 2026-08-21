"""`xime check config`: bắt khoá gõ sai, và KHÔNG kêu oan.

Thứ nó bắt được mà hôm nay không gì bắt: viết `publik` thay vì `public` thì là
một server im lặng không có route nào - không lỗi, không log, không test đỏ.

⭐ Nhưng vế thứ hai quan trọng ngang vế thứ nhất. Chạy thử trên **30 file cấu
hình thật** của workspace ngày 2026-08-20: **29 file sạch**, và file duy nhất
kêu là một app **Java Spring Boot** (`server.ssl.key-store`), không phải cấu
hình Xime. Con số đó là nhờ công tắc `complete` - một phép dò tố khoá hợp lệ sẽ
bị tắt trong tuần đầu, và lúc đó nó không bắt được gì nữa.
"""

from __future__ import annotations

from pathlib import Path

from xime.cli._config_check import check


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "application.yml"
    path.write_text(body, encoding="utf-8")
    return path


class TestThreeOutcomes:
    def test_clean(self, tmp_path: Path) -> None:
        result = check(_write(tmp_path, "server:\n  port: 8080\n"))
        assert result.verdict == "clean"
        assert result.findings == ()

    def test_findings(self, tmp_path: Path) -> None:
        result = check(_write(tmp_path, "server:\n  prot: 8080\n"))
        assert result.verdict == "findings"

    def test_a_file_that_does_not_exist_is_inconclusive_not_clean(
        self, tmp_path: Path
    ) -> None:
        """⚠ *"Không tìm thấy vấn đề"* và *"không đọc được để mà tìm"* là hai
        câu trả lời khác nhau. Gộp lại là để một lần chạy trong CI báo xanh trên
        một phép kiểm chưa hề chạy."""
        result = check(tmp_path / "khong-co.yml")
        assert result.verdict == "inconclusive"
        assert result.unreadable is not None

    def test_a_file_that_does_not_parse_is_inconclusive(self, tmp_path: Path) -> None:
        result = check(_write(tmp_path, "server:\n  port: [unclosed\n"))
        assert result.verdict == "inconclusive"

    def test_a_file_that_is_not_a_mapping_is_inconclusive(self, tmp_path: Path) -> None:
        result = check(_write(tmp_path, "- mot\n- danh sach\n"))
        assert result.verdict == "inconclusive"

    def test_an_empty_file_is_clean(self, tmp_path: Path) -> None:
        """Vế đối chứng: rỗng là hợp lệ - mọi khoá đều có mặc định trừ vài khoá
        của starter mà app này không dùng."""
        assert check(_write(tmp_path, "")).verdict == "clean"


class TestCatchingTypos:
    def test_an_unknown_key_is_reported(self, tmp_path: Path) -> None:
        result = check(_write(tmp_path, "server:\n  prot: 8080\n"))
        assert [f.where for f in result.findings] == ["server.prot"]

    def test_it_suggests_the_near_miss(self, tmp_path: Path) -> None:
        result = check(_write(tmp_path, "server:\n  prot: 8080\n"))
        assert "port" in result.findings[0].hint

    def test_it_stays_quiet_when_there_is_no_near_miss(self, tmp_path: Path) -> None:
        """Vế thứ hai: gợi ý bừa còn tệ hơn không gợi ý - nó gửi người đọc đi
        sửa một khoá không liên quan."""
        result = check(_write(tmp_path, "server:\n  zzzzzz: 1\n"))
        assert result.findings[0].hint == ""

    def test_it_goes_into_nested_blocks(self, tmp_path: Path) -> None:
        result = check(_write(tmp_path, "server:\n  ssl:\n    certfil: /a.pem\n"))
        assert [f.where for f in result.findings] == ["server.ssl.certfil"]

    def test_a_correct_nested_key_is_left_alone(self, tmp_path: Path) -> None:
        result = check(_write(tmp_path, "server:\n  ssl:\n    certfile: /a.pem\n"))
        assert result.findings == ()


class TestNotCryingWolf:
    def test_a_block_the_framework_does_not_know_is_ignored(self, tmp_path: Path) -> None:
        """⭐ Ứng dụng có khối riêng của nó (`trust:`, `app:`, ...). Tố chúng là
        biến phép dò thành tiếng ồn ngay ngày đầu."""
        result = check(_write(tmp_path, "trust:\n  bat-ky-gi: 1\n"))
        assert result.findings == ()
        assert "trust" in result.blocks_seen
        assert "trust" not in result.blocks_checked

    def test_an_incomplete_block_is_not_policed(self, tmp_path: Path) -> None:
        """`grpc` còn mang cả cấu hình client SDK, do module khác đọc - nên bản
        mô tả của nó chưa đủ và nó không được phép tố ai.

        📌 Ca thật: lượt chạy đầu tiên trên `data-service` tố `grpc.clients` và
        `grpc.internal` là khoá lạ. Cả hai đều hợp lệ.
        """
        result = check(_write(tmp_path, "grpc:\n  clients:\n    trust: {}\n"))
        assert result.findings == ()
        assert "grpc" not in result.blocks_checked

    def test_a_complete_block_IS_policed(self, tmp_path: Path) -> None:
        """Vế đối chứng của test trên: cách "sửa" bằng việc không bao giờ tố ai
        cũng qua được nó."""
        result = check(_write(tmp_path, "lmdb:\n  path: /x\n  mapsize: 1MB\n"))
        assert [f.where for f in result.findings] == ["lmdb.mapsize"]

    def test_it_reports_which_blocks_it_actually_looked_at(self, tmp_path: Path) -> None:
        """Con số duy nhất phân biệt *"sạch"* với *"không soi gì cả"*."""
        result = check(_write(tmp_path, "server:\n  port: 1\ntrust:\n  x: 1\n"))
        assert result.blocks_checked == ("server",)


class TestRequiredKeys:
    def test_a_missing_required_key_is_reported(self, tmp_path: Path) -> None:
        result = check(_write(tmp_path, "lmdb:\n  map_size: 1MB\n"))
        assert any("required" in f.problem for f in result.findings)

    def test_it_is_not_reported_when_present(self, tmp_path: Path) -> None:
        result = check(_write(tmp_path, "lmdb:\n  path: /x\n"))
        assert result.findings == ()

    def test_a_block_left_out_entirely_is_not_a_finding(self, tmp_path: Path) -> None:
        """⚠ Vắng cả khối `lmdb:` nghĩa là app không dùng kho - không phải quên
        điền. Báo lỗi ở đây là bắt mọi app khai một starter nó không dùng."""
        assert check(_write(tmp_path, "server:\n  port: 1\n")).findings == ()
