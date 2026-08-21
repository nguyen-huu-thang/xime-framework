"""`xime check module-level` - đường đi mà người dùng thật đi.

⚠ Bài học 0.7.0 và cả bốn lỗ hổng của giai đoạn 6 cùng một hình dạng: bộ test
kiểm **thứ được tính ra** mà không đi qua chỗ nó **được dùng**. `scan()` có 60
test rồi, nhưng lệnh CLI mới là thứ tài liệu bảo người ta gõ - nên nó cần đường
đi riêng của mình.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from xime.cli._main import main


def _write(root: Path, relative: str, body: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _run(root: Path, *extra: str) -> int:
    return main(["check", "module-level", "--root", str(root), *extra])


class TestExitCodes:
    """⭐ BA mã thoát, không phải hai - CI đọc đúng con số này."""

    def test_clean_is_zero(self, tmp_path: Path, capsys) -> None:
        _write(tmp_path, "main.py", "import time\n\n\ndef now():\n    return time.time()\n")

        assert _run(tmp_path) == 0
        assert "CLEAN" in capsys.readouterr().out

    def test_a_violation_is_one(self, tmp_path: Path, capsys) -> None:
        _write(tmp_path, "main.py", "from uuid import uuid4\nRUN_ID = uuid4()\n")

        assert _run(tmp_path) == 1
        out = capsys.readouterr().out
        assert "uuid.uuid4()" in out
        assert "main.py:2" in out

    def test_an_unreadable_file_is_two_not_zero(self, tmp_path: Path, capsys) -> None:
        """⚠ Không phải 0.

        *"Không tìm thấy vi phạm"* và *"không đọc được để mà tìm"* là hai câu
        trả lời khác nhau, và gộp chúng lại là bán sự yên tâm cho một vùng chưa
        ai nhìn.
        """
        _write(tmp_path, "main.py", "from app import broken\n")
        _write(tmp_path, "app/__init__.py", "")
        _write(tmp_path, "app/broken.py", "def (:\n")

        assert _run(tmp_path) == 2
        out = capsys.readouterr().out
        assert "INCONCLUSIVE" in out
        assert "not a pass" in out

    def test_no_entry_point_is_two_not_zero(self, tmp_path: Path, capsys) -> None:
        """Chạy nhầm thư mục là cách dễ nhất để nhận một con số xanh vô nghĩa."""
        assert _run(tmp_path) == 2
        out = capsys.readouterr().out
        assert "Cannot Locate An Entry Point" in out
        assert "--main" in out

    def test_a_main_that_does_not_exist_is_two(self, tmp_path: Path, capsys) -> None:
        assert _run(tmp_path, "--main", str(tmp_path / "nope.py")) == 2
        assert "does not exist" in capsys.readouterr().out


class TestWhatItSays:
    def test_the_clean_message_admits_what_it_cannot_see(
        self, tmp_path: Path, capsys
    ) -> None:
        """⚠ Con số 0 của một phép dò theo danh sách tên không chứng minh được
        gì, nên nó phải tự nói ra điều đó - cùng bài học với phép quét secret
        chỉ bắt từ khoá tiếng Anh trên một codebase đặt tên tiếng Việt."""
        _write(tmp_path, "main.py", "")

        _run(tmp_path)

        assert "list of NAMES" in capsys.readouterr().out

    def test_the_violation_message_says_where_the_code_belongs(
        self, tmp_path: Path, capsys
    ) -> None:
        _write(tmp_path, "main.py", "import os\nPID = os.getpid()\n")

        _run(tmp_path)
        out = capsys.readouterr().out

        assert "once per process" in out
        assert "run_once()" in out

    def test_it_reports_how_many_files_it_looked_at(
        self, tmp_path: Path, capsys
    ) -> None:
        """Số file quét được là thứ duy nhất phân biệt *"sạch"* với *"đi lạc
        thư mục"* khi cả hai in ra CLEAN."""
        _write(tmp_path, "main.py", "from app import wiring\n")
        _write(tmp_path, "app/__init__.py", "")
        _write(tmp_path, "app/wiring.py", "")

        _run(tmp_path)

        assert "3 file(s) scanned" in capsys.readouterr().out


class TestEntryDiscovery:
    @pytest.mark.parametrize("where", ["app/main.py", "main.py", "src/main.py"])
    def test_the_three_shapes_the_apps_use(
        self, tmp_path: Path, where: str, capsys
    ) -> None:
        _write(tmp_path, where, "import time\nAT = time.time()\n")

        assert _run(tmp_path) == 1
        capsys.readouterr()

    def test_an_explicit_main_wins(self, tmp_path: Path, capsys) -> None:
        _write(tmp_path, "main.py", "import time\nAT = time.time()\n")
        _write(tmp_path, "other.py", "")

        assert _run(tmp_path, "--main", str(tmp_path / "other.py")) == 0
        capsys.readouterr()
