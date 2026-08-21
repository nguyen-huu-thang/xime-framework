"""Phép dò thứ HAI: quét tĩnh tìm lời gọi không tất định ở mức module.

Mọi nhóm ở đây đi **thành cặp** - *phải kêu* và *phải im*. Vế thứ hai không phải
để cho đủ: một phép dò kêu oan sẽ bị tắt, và lúc đó nó không còn bắt được gì
nữa. `uuid5` và `random.seed` là hai ca cụ thể: cùng module với thứ bị theo dõi,
nhưng **tất định**, nên kêu chúng là kêu sai.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from xime.cli._module_level import find_entry, is_watched, scan


def _write(root: Path, relative: str, body: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _names(root: Path, entry: str = "main.py") -> list[str]:
    result = scan(root / entry, root)
    return [f.name for f in result.findings]


# ---------------------------------------------------------------------------
# Danh sách tên
# ---------------------------------------------------------------------------


class TestTheWatchList:
    @pytest.mark.parametrize(
        "name",
        [
            "uuid.uuid4",
            "uuid.uuid1",
            "time.time",
            "time.monotonic",
            "os.urandom",
            "os.getpid",
            "datetime.datetime.now",
            "datetime.date.today",
            "random.random",
            "random.choice",
            "secrets.token_hex",
        ],
    )
    def test_these_are_watched(self, name: str) -> None:
        assert is_watched(name) is True

    @pytest.mark.parametrize(
        "name",
        [
            # ⭐ Tất định theo (namespace, name) - gọi ở mức module là hợp lệ.
            "uuid.uuid3",
            "uuid.uuid5",
            # ⭐ Ngược chiều: nó LÀM CHO mọi thứ sau đó tất định.
            "random.seed",
            # Không dính dáng.
            "os.path.join",
            "time.sleep",
            "json.dumps",
            "random",
            "secrets",
        ],
    )
    def test_these_are_not(self, name: str) -> None:
        assert is_watched(name) is False


# ---------------------------------------------------------------------------
# Phân giải tên qua các dạng import
# ---------------------------------------------------------------------------


class TestNameResolution:
    def test_a_plain_module_import(self, tmp_path: Path) -> None:
        _write(tmp_path, "main.py", "import uuid\nID = uuid.uuid4()\n")
        assert _names(tmp_path) == ["uuid.uuid4"]

    def test_a_from_import(self, tmp_path: Path) -> None:
        _write(tmp_path, "main.py", "from uuid import uuid4\nID = uuid4()\n")
        assert _names(tmp_path) == ["uuid.uuid4"]

    def test_an_aliased_from_import(self, tmp_path: Path) -> None:
        """Đổi tên là cách rẻ nhất để đi lọt một phép dò khớp chuỗi."""
        _write(tmp_path, "main.py", "from uuid import uuid4 as gen\nID = gen()\n")
        assert _names(tmp_path) == ["uuid.uuid4"]

    def test_an_aliased_module_import(self, tmp_path: Path) -> None:
        _write(tmp_path, "main.py", "import time as t\nAT = t.time()\n")
        assert _names(tmp_path) == ["time.time"]

    def test_datetime_reached_through_the_package(self, tmp_path: Path) -> None:
        _write(tmp_path, "main.py", "import datetime\nAT = datetime.datetime.now()\n")
        assert _names(tmp_path) == ["datetime.datetime.now"]

    def test_datetime_reached_through_the_class(self, tmp_path: Path) -> None:
        _write(tmp_path, "main.py", "from datetime import datetime\nAT = datetime.now()\n")
        assert _names(tmp_path) == ["datetime.datetime.now"]

    def test_a_name_that_was_never_imported_is_not_guessed(self, tmp_path: Path) -> None:
        """Vế thứ hai. `uuid4()` của người khác không phải `uuid.uuid4` - đoán
        theo tên trần là cách sinh ra cảnh báo giả."""
        _write(tmp_path, "main.py", "from mylib import uuid4\nID = uuid4()\n")
        assert _names(tmp_path) == []

    def test_a_local_object_that_shadows_a_stdlib_name_is_not_guessed(
        self, tmp_path: Path
    ) -> None:
        """⚠ Không có import nào thì **không được đoán**.

        `time` ở đây là một object của app, và `time.time()` của nó có thể trả về
        một hằng số cấu hình. Suy tên từ hình dạng chuỗi là cách phép dò bắt
        đầu kêu oan - và một phép dò kêu oan là một phép dò sẽ bị tắt.
        """
        _write(
            tmp_path,
            "main.py",
            "class Clock:\n    def time(self):\n        return 0\n\n\n"
            "time = Clock()\nAT = time.time()\n",
        )
        assert _names(tmp_path) == []


# ---------------------------------------------------------------------------
# Cái gì thật sự chạy lúc import - CẶP
# ---------------------------------------------------------------------------


class TestWhatRunsAtImport:
    def test_the_module_body(self, tmp_path: Path) -> None:
        _write(tmp_path, "main.py", "import time\nAT = time.time()\n")
        assert _names(tmp_path) == ["time.time"]

    def test_a_function_body_does_not(self, tmp_path: Path) -> None:
        """Vế thứ hai, và là vế quan trọng nhất: đây là chỗ code ĐÚNG nằm."""
        _write(
            tmp_path,
            "main.py",
            "import time\n\n\ndef now():\n    return time.time()\n",
        )
        assert _names(tmp_path) == []

    def test_a_class_body_does(self, tmp_path: Path) -> None:
        """⚠ Rộng hơn câu chữ của luật, và cố ý.

        Thân class chạy lúc import y như thân module, nên
        `class C: ID = uuid4()` hỏng đúng kiểu đó: một giá trị cho cả class,
        khác nhau ở mỗi tiến trình.
        """
        _write(
            tmp_path,
            "main.py",
            "from uuid import uuid4\n\n\nclass Node:\n    ID = uuid4()\n",
        )
        assert _names(tmp_path) == ["uuid.uuid4"]

    def test_but_a_method_body_does_not(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            "main.py",
            "from uuid import uuid4\n\n\nclass Node:\n"
            "    def fresh(self):\n        return uuid4()\n",
        )
        assert _names(tmp_path) == []

    def test_a_decorator_does(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            "main.py",
            "import time\nfrom lib import stamp\n\n\n"
            "@stamp(at=time.time())\ndef handler():\n    pass\n",
        )
        assert _names(tmp_path) == ["time.time"]

    def test_a_default_argument_does(self, tmp_path: Path) -> None:
        """Ca kinh điển: giá trị mặc định được tính MỘT lần, lúc định nghĩa."""
        _write(
            tmp_path,
            "main.py",
            "import time\n\n\ndef handler(at=time.time()):\n    return at\n",
        )
        assert _names(tmp_path) == ["time.time"]

    def test_a_keyword_only_default_does(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            "main.py",
            "import time\n\n\ndef handler(*, at=time.time()):\n    return at\n",
        )
        assert _names(tmp_path) == ["time.time"]

    def test_a_try_block_at_module_level_does(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            "main.py",
            "import time\n\ntry:\n    AT = time.time()\nexcept OSError:\n    AT = 0\n",
        )
        assert _names(tmp_path) == ["time.time"]

    def test_an_except_handler_at_module_level_does(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            "main.py",
            "import time\n\ntry:\n    AT = 0\nexcept OSError:\n    AT = time.time()\n",
        )
        assert _names(tmp_path) == ["time.time"]

    def test_a_for_loop_at_module_level_does(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            "main.py",
            "import random\n\nIDS = []\nfor _ in range(3):\n"
            "    IDS.append(random.random())\n",
        )
        assert _names(tmp_path) == ["random.random"]

    def test_the_main_guard_does_not(self, tmp_path: Path) -> None:
        """⭐ Khối duy nhất KHÔNG chạy ở tiến trình con.

        `multiprocessing` với `spawn` import lại `main.py` dưới tên
        `__mp_main__`, nên khối này chạy đúng một lần, ở cha - nó không nhân
        lên, nên nó ngoài phạm vi luật.
        """
        _write(
            tmp_path,
            "main.py",
            'import time\n\nif __name__ == "__main__":\n    AT = time.time()\n',
        )
        assert _names(tmp_path) == []

    def test_a_lookalike_guard_still_counts(self, tmp_path: Path) -> None:
        """Vế thứ hai: chỉ đúng khối đó mới được miễn, không phải mọi `if`."""
        _write(
            tmp_path,
            "main.py",
            'import time\n\nif __name__ == "__mp_main__":\n    AT = time.time()\n',
        )
        assert _names(tmp_path) == ["time.time"]


# ---------------------------------------------------------------------------
# Đi theo import
# ---------------------------------------------------------------------------


class TestFollowingImports:
    def test_it_follows_first_party_modules(self, tmp_path: Path) -> None:
        _write(tmp_path, "main.py", "from app.config import dependency\n")
        _write(tmp_path, "app/__init__.py", "")
        _write(tmp_path, "app/config/__init__.py", "")
        _write(
            tmp_path,
            "app/config/dependency.py",
            "from uuid import uuid4\nRUN_ID = uuid4()\n",
        )

        result = scan(tmp_path / "main.py", tmp_path)

        assert [f.name for f in result.findings] == ["uuid.uuid4"]
        assert len(result.scanned) == 4

    def test_it_scans_the_parent_packages_too(self, tmp_path: Path) -> None:
        """⚠ Lỗ hổng do chính test trên tìm ra.

        `from app.config import dependency` **chạy `app/__init__.py`** trước,
        vì Python import package cha trước module con. Chỉ đi theo cái tên được
        viết ra thì `app/__init__.py` không bao giờ bị quét - mà đó lại là chỗ
        người ta hay để "vài dòng khởi tạo cho gọn".
        """
        _write(tmp_path, "main.py", "from app.config import dependency\n")
        _write(tmp_path, "app/__init__.py", "import os\nBOOT_PID = os.getpid()\n")
        _write(tmp_path, "app/config/__init__.py", "")
        _write(tmp_path, "app/config/dependency.py", "")

        result = scan(tmp_path / "main.py", tmp_path)

        assert [f.name for f in result.findings] == ["os.getpid"]

    def test_it_follows_relative_imports(self, tmp_path: Path) -> None:
        _write(tmp_path, "main.py", "from app import wiring\n")
        _write(tmp_path, "app/__init__.py", "")
        _write(tmp_path, "app/wiring.py", "from . import boot\n")
        _write(tmp_path, "app/boot.py", "import os\nPID = os.getpid()\n")

        assert [f.name for f in _scan_names(tmp_path)] == ["os.getpid"]

    def test_it_does_not_follow_third_party_packages(self, tmp_path: Path) -> None:
        """Vế thứ hai. `xime`, `fastapi`, `sqlalchemy` đều gọi `time.time()` ở
        đâu đó - quét chúng là biến phép dò thành một bức tường cảnh báo về mã
        người dùng không sửa được."""
        _write(tmp_path, "main.py", "import xime\nimport json\n")

        result = scan(tmp_path / "main.py", tmp_path)

        assert result.scanned == (tmp_path / "main.py",)

    def test_an_import_inside_the_main_guard_is_not_followed(
        self, tmp_path: Path
    ) -> None:
        _write(
            tmp_path,
            "main.py",
            'if __name__ == "__main__":\n    from app import boot\n',
        )
        _write(tmp_path, "app/__init__.py", "")
        _write(tmp_path, "app/boot.py", "import time\nAT = time.time()\n")

        result = scan(tmp_path / "main.py", tmp_path)

        assert result.findings == ()

    def test_an_import_inside_a_module_level_try_IS_followed(
        self, tmp_path: Path
    ) -> None:
        """⭐ Vế thứ hai của cặp, và là vế lộ ra một lỗ hổng thật.

        `try: import x except ImportError:` là khuôn phổ biến cho phụ thuộc tuỳ
        chọn, và `x` **vẫn chạy lúc import**. Chỉ nhìn tầng ngoài cùng thì cả
        một nhánh cây import biến mất khỏi phạm vi quét - mà kết quả vẫn in ra
        `CLEAN`.
        """
        _write(
            tmp_path,
            "main.py",
            "try:\n    from app import boot\nexcept ImportError:\n    boot = None\n",
        )
        _write(tmp_path, "app/__init__.py", "")
        _write(tmp_path, "app/boot.py", "import time\nAT = time.time()\n")

        assert [f.name for f in _scan_names(tmp_path)] == ["time.time"]

    def test_an_import_inside_a_function_is_not_followed(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            "main.py",
            "def wire():\n    from app import boot\n\n    return boot\n",
        )
        _write(tmp_path, "app/__init__.py", "")
        _write(tmp_path, "app/boot.py", "import time\nAT = time.time()\n")

        assert scan(tmp_path / "main.py", tmp_path).findings == ()

    def test_a_module_reached_by_two_paths_is_scanned_once(
        self, tmp_path: Path
    ) -> None:
        """⚠ Đây là thứ chốt chặn vòng lặp thật sự giữ, chứ không phải "treo".

        `a` và `b` cùng import `c`, và cả hai xếp `c` vào hàng đợi **trước khi**
        `c` được lấy ra. Không kiểm lại lúc lấy ra thì `c` bị quét hai lần, một
        vi phạm được đếm hai lần, và người đọc đi tìm một lỗi thứ hai không tồn
        tại.
        """
        _write(tmp_path, "main.py", "from app import a, b\n")
        _write(tmp_path, "app/__init__.py", "")
        _write(tmp_path, "app/a.py", "from app import c\n")
        _write(tmp_path, "app/b.py", "from app import c\n")
        _write(tmp_path, "app/c.py", "import time\nAT = time.time()\n")

        result = scan(tmp_path / "main.py", tmp_path)

        assert [f.name for f in result.findings] == ["time.time"]
        assert len(result.scanned) == len(set(result.scanned))

    def test_a_cycle_does_not_hang(self, tmp_path: Path) -> None:
        _write(tmp_path, "main.py", "from app import a\n")
        _write(tmp_path, "app/__init__.py", "")
        _write(tmp_path, "app/a.py", "from app import b\n")
        _write(tmp_path, "app/b.py", "import time\nfrom app import a\nAT = time.time()\n")

        result = scan(tmp_path / "main.py", tmp_path)

        assert [f.name for f in result.findings] == ["time.time"]

    def test_every_finding_carries_a_place_to_go_look(self, tmp_path: Path) -> None:
        _write(tmp_path, "main.py", "import time\n\n\nAT = time.time()\n")

        finding = scan(tmp_path / "main.py", tmp_path).findings[0]

        assert finding.line == 4
        assert finding.path == (tmp_path / "main.py").resolve()
        assert "time.time()" in finding.source


def _scan_names(root: Path):
    return scan(root / "main.py", root).findings


# ---------------------------------------------------------------------------
# BA kết cục
# ---------------------------------------------------------------------------


class TestThreeOutcomes:
    """⚠ Ba, không phải hai.

    Gộp *"không đọc được"* vào *"sạch"* là để người đọc tin vào một phép kiểm
    chưa hề chạy - cùng lỗi `ShardValueGuard` của `identity` đã vấp, và cùng
    khuôn với việc đếm **TREO** riêng ở giàn đối chứng.
    """

    def test_clean(self, tmp_path: Path) -> None:
        _write(tmp_path, "main.py", "import time\n\n\ndef now():\n    return time.time()\n")
        assert scan(tmp_path / "main.py", tmp_path).verdict == "clean"

    def test_violations(self, tmp_path: Path) -> None:
        _write(tmp_path, "main.py", "import time\nAT = time.time()\n")
        assert scan(tmp_path / "main.py", tmp_path).verdict == "violations"

    def test_a_file_that_does_not_parse_is_inconclusive_not_clean(
        self, tmp_path: Path
    ) -> None:
        _write(tmp_path, "main.py", "from app import broken\n")
        _write(tmp_path, "app/__init__.py", "")
        _write(tmp_path, "app/broken.py", "def (:\n")

        result = scan(tmp_path / "main.py", tmp_path)

        assert result.findings == ()
        assert result.verdict == "inconclusive"
        assert len(result.unreadable) == 1

    def test_an_entry_that_does_not_parse_is_inconclusive(self, tmp_path: Path) -> None:
        _write(tmp_path, "main.py", "def (:\n")
        assert scan(tmp_path / "main.py", tmp_path).verdict == "inconclusive"

    def test_a_missing_entry_is_inconclusive(self, tmp_path: Path) -> None:
        result = scan(tmp_path / "nope.py", tmp_path)
        assert result.scanned == ()
        assert result.verdict == "inconclusive"


# ---------------------------------------------------------------------------
# Tìm điểm vào
# ---------------------------------------------------------------------------


class TestFindEntry:
    def test_it_prefers_the_shape_the_apps_use(self, tmp_path: Path) -> None:
        _write(tmp_path, "main.py", "")
        _write(tmp_path, "app/main.py", "")

        assert find_entry(tmp_path) == tmp_path / "app/main.py"

    def test_it_falls_back_to_the_root(self, tmp_path: Path) -> None:
        _write(tmp_path, "main.py", "")
        assert find_entry(tmp_path) == tmp_path / "main.py"

    def test_it_says_nothing_rather_than_guessing(self, tmp_path: Path) -> None:
        assert find_entry(tmp_path) is None
