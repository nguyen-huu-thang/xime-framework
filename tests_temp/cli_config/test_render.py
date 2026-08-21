"""`xime config --print`: cái gì đi ra dạng chú thích, cái gì ghi thẳng.

⭐ **Luật chia, và mọi test ở đây đo đúng nó:**

> **Chú thích những gì framework mặc định ĐƯỢC. Ghi thẳng chỉ những gì nó
> KHÔNG mặc định được.**

⚠ Vế thứ hai đắt hơn nó trông, và repo này có bằng chứng cả hai chiều: 0.7.1
đổi bốn hành vi và tới được **cả 31 app** vì chúng là mặc định của framework;
còn lỗ fail-open JWT thì **19 app vẫn thủng** vì nó nằm trong `config/jwt.py`
của họ. Giá trị nào chép ra file là đóng băng ở phiên bản hôm nay.
"""

from __future__ import annotations

import pytest
import yaml

from xime.cli._config_render import render, render_example
from xime.cli._config_spec import BY_NAME, Block, Key


def _lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


class TestTheSplitRule:
    def test_a_required_key_is_written_out(self) -> None:
        text = render("demo", blocks=(BY_NAME["lmdb"],))
        assert any(line.startswith("  path:") for line in _lines(text))

    def test_a_defaulted_key_stays_commented(self) -> None:
        """Vế thứ hai của cặp, và là vế giữ được đường nâng cấp."""
        text = render("demo", blocks=(BY_NAME["lmdb"],))
        assert any(line.strip().startswith("# map_size:") for line in _lines(text))
        assert not any(line.startswith("  map_size:") for line in _lines(text))

    def test_a_block_with_no_required_key_is_commented_whole(self) -> None:
        text = render("demo", blocks=(BY_NAME["logging"],))
        assert "\nlogging:" not in text
        assert "# logging:" in text

    def test_a_block_with_a_required_key_is_opened(self) -> None:
        text = render("demo", blocks=(BY_NAME["lmdb"],))
        assert "\nlmdb:" in text

    def test_the_project_name_reaches_the_placeholder(self) -> None:
        assert "/dev/shm/demo-store" in render("demo", blocks=(BY_NAME["lmdb"],))

    def test_without_a_project_it_says_so_rather_than_inventing_one(self) -> None:
        assert "<your-service>" in render(blocks=(BY_NAME["lmdb"],))


class TestTheOutputIsValidYaml:
    """⚠ Một file cấu hình sinh ra mà không parse được là thứ tệ nhất: nó trông
    đúng, và app chết ở dòng đầu tiên đọc nó."""

    def test_the_whole_thing_parses(self) -> None:
        assert isinstance(yaml.safe_load(render("demo")), dict)

    def test_the_uncommented_keys_survive_the_round_trip(self) -> None:
        loaded = yaml.safe_load(render("demo"))
        assert loaded["lmdb"]["path"] == "/dev/shm/demo-store"

    def test_nothing_defaulted_leaks_into_the_parsed_document(self) -> None:
        """Cặp với test trên: khoá có mặc định phải KHÔNG xuất hiện sau khi
        parse, vì mặc định thuộc về framework chứ không thuộc về file."""
        loaded = yaml.safe_load(render("demo"))
        assert "map_size" not in loaded["lmdb"]
        assert "logging" not in loaded

    def test_a_quoted_permission_stays_a_string(self) -> None:
        """YAML đọc `0600` không nháy thành số 600 hệ mười - quyền vô nghĩa."""
        text = render("demo", blocks=(BY_NAME["socket"],))
        assert '# permission: "0600"' in text


class TestWhatTheFileTellsTheReader:
    def test_the_header_explains_the_two_kinds_of_line(self) -> None:
        text = render("demo")
        assert "uncommented line" in text
        assert "commented line" in text

    def test_a_block_needing_an_extra_says_which(self) -> None:
        assert "pip install 'xime[lmdb]'" in render("demo", blocks=(BY_NAME["lmdb"],))

    def test_an_incomplete_block_admits_it(self) -> None:
        """⭐ Con số 0 của một danh sách chưa đủ không chứng minh được gì, nên
        nó phải tự nói ra."""
        assert "not the complete list" in render("demo", blocks=(BY_NAME["mqtt"],))

    def test_a_complete_block_does_not_carry_that_warning(self) -> None:
        assert "not the complete list" not in render("demo", blocks=(BY_NAME["lmdb"],))

    def test_a_block_that_cannot_be_read_says_so_instead_of_looking_empty(self) -> None:
        broken = Block(name="x", doc="d", model="khong.co:Thing")
        assert "could not be read" in render("demo", blocks=(broken,))


class TestTheExampleForGit:
    """Bản `.example`: **chỉ khoá bắt buộc, không chú thích**.

    Chủ dự án chốt 2026-08-20 rằng file đó *"không có giá trị, người dùng xoá
    cũng được"*. Chú thích trong một file đi theo git là tài liệu già đi trong
    im lặng, và người đọc không có cách nào biết nó nói về phiên bản nào.
    """

    def test_it_carries_the_required_keys(self) -> None:
        text = render_example("demo")
        assert "lmdb:" in text
        assert "path: /dev/shm/demo-store" in text

    def test_it_carries_nothing_that_has_a_default(self) -> None:
        text = render_example("demo")
        assert "map_size" not in text
        assert "logging" not in text

    def test_it_does_not_copy_the_explanations(self) -> None:
        """Vế đối chứng của bản đầy đủ: cùng dữ liệu, hai vai khác hẳn nhau."""
        text = render_example("demo")
        assert "There is NO default" not in text
        assert len(_lines(text)) < len(_lines(render("demo"))) / 5

    def test_it_points_at_the_command_that_never_goes_stale(self) -> None:
        assert "xime config --print" in render_example("demo")

    def test_it_parses(self) -> None:
        assert isinstance(yaml.safe_load(render_example("demo")), dict)


class TestValueFormatting:
    @pytest.mark.parametrize(
        ("default", "shown"),
        [(True, "true"), (False, "false"), (None, "null"), (600, "600"), ((), "[]")],
    )
    def test_python_values_come_out_as_yaml(self, default: object, shown: str) -> None:
        block = Block(name="b", doc="d", keys=(Key("k", default=default),))
        assert f"# k: {shown}" in render(blocks=(block,))
