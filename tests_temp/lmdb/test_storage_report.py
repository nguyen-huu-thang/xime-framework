"""Kho nằm trên RAM hay trên đĩa, và chuyện gì xảy ra khi `total_max` là lời hứa giả.

Hai thứ ở đây, và chúng khác trục nhau:

| | |
|---|---|
| **Dòng log** | tách *"mất khi reboot"* khỏi *"sống qua reboot"* - luật 03 |
| **Chốt kiểm** | `total_max` mà hệ tệp không giữ nổi thì **nổ lúc khởi động**, vì trên tmpfs nó vỡ bằng **OOM kill**, không bằng chậm đi |

Test đi **thành cặp** ở mọi chỗ: một phép kiểm chỉ chặn thì cách sửa sai *"luôn
luôn chặn"* cũng qua được.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from xime.core.config.runtime import RuntimeConfig
from xime.core.exception.framework import StartupException
from xime.starters.lmdb import LmdbEnvironment
from xime.starters.lmdb._storage import (
    RAM_FILESYSTEMS,
    StorageReport,
    human_size,
    inspect_storage,
    nearest_existing,
)


def _runtime(path: str, **sizes: str) -> RuntimeConfig:
    block = {"path": path, "map_size": "1MB", "total_max": "32MB"}
    block.update(sizes)
    return RuntimeConfig.from_dict({"lmdb": block})


# ---------------------------------------------------------------------------
# Đo hệ tệp
# ---------------------------------------------------------------------------


class TestNearestExisting:
    """`lmdb.path` thường CHƯA được tạo lúc ta muốn đo."""

    def test_an_existing_directory_is_its_own_anchor(self, tmp_path: Path) -> None:
        assert nearest_existing(tmp_path) == tmp_path.resolve()

    def test_a_directory_that_does_not_exist_yet_walks_up(self, tmp_path: Path) -> None:
        """Hệ tệp đã quyết định rồi - nó là hệ tệp của thư mục cha. Đo ở đó cho
        cùng câu trả lời mà **không phải tạo gì**."""
        assert nearest_existing(tmp_path / "chua" / "co" / "gi") == tmp_path.resolve()

    def test_a_file_is_not_mistaken_for_a_directory(self, tmp_path: Path) -> None:
        target = tmp_path / "mot-file"
        target.write_text("x", encoding="utf-8")
        assert nearest_existing(target) == tmp_path.resolve()


class TestInspectStorage:
    def test_it_reports_free_space(self, tmp_path: Path) -> None:
        report = inspect_storage(tmp_path)
        assert report.free_bytes is not None
        assert report.free_bytes > 0

    def test_it_measures_the_nearest_existing_directory(self, tmp_path: Path) -> None:
        report = inspect_storage(tmp_path / "chua-co")
        assert report.measured_at == str(tmp_path.resolve())

    def test_ram_backed_has_THREE_values_not_two(self) -> None:
        """⭐ `None` là một kết cục riêng, không phải `False`.

        Trên Windows không có `/proc/mounts` nên framework **không biết**, và
        trả `False` ở đó là nói dối: một ổ đĩa RAM trông y hệt ổ thật với mọi
        API Python. Gộp *"không biết"* vào *"bền vững"* là hứa tính bền cho một
        thứ có thể bay hơi.
        """
        assert {True, False, None} >= {
            StorageReport("x", 1, "tmpfs", True).ram_backed,
            StorageReport("x", 1, "ext4", False).ram_backed,
            StorageReport("x", 1, None, None).ram_backed,
        }

    def test_tmpfs_and_ramfs_are_the_ram_filesystems(self) -> None:
        assert "tmpfs" in RAM_FILESYSTEMS
        assert "ramfs" in RAM_FILESYSTEMS
        assert "ext4" not in RAM_FILESYSTEMS

    def test_an_unreadable_mount_table_gives_UNKNOWN_not_durable(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """⚠ Đây là ca Windows, và là ca dễ trả lời sai nhất.

        Không đọc được `/proc/mounts` thì `fstype` là `None`, và một phép kiểm
        `fstype in RAM_FILESYSTEMS` sẽ ra `False` - tức framework **hứa tính bền
        cho một thứ nó chưa hề đo**. Trên Windows một ổ đĩa RAM trông y hệt ổ
        thật với mọi API Python.

        📌 Lỗ hổng này lộ ra bằng đối chứng: nhóm test kia dựng `StorageReport`
        bằng tay nên nó không bao giờ đi qua chỗ `ram_backed` được TÍNH.
        """
        monkeypatch.setattr("xime.starters.lmdb._storage._MOUNTS", str(tmp_path / "khong-co"))

        assert inspect_storage(tmp_path).ram_backed is None

    def test_a_readable_mount_table_still_answers(self, tmp_path: Path, monkeypatch) -> None:
        """Vế thứ hai của cặp: cách sửa sai *"luôn trả None"* cũng qua được test
        trên, và nó làm dòng log vô dụng ở đúng chỗ nó có ích nhất."""
        mounts = tmp_path / "mounts"
        # ⚠ `/proc/mounts` thoát khoảng trắng thành `\040`, và đường dẫn tạm của
        # test này có khoảng trắng - viết raw thì `split()` cắt nhầm điểm gắn kết.
        point = str(tmp_path.resolve()).replace(" ", "\\040")
        mounts.write_text(f"tmpfs {point} tmpfs rw 0 0\n", encoding="utf-8")
        monkeypatch.setattr("xime.starters.lmdb._storage._MOUNTS", str(mounts))

        assert inspect_storage(tmp_path).ram_backed is True


class TestTheLabel:
    """Nhãn phải nói ra HỆ QUẢ, không chỉ tên hệ tệp.

    *"tmpfs"* không nói gì với người vận hành; *"mất khi reboot"* thì có.
    """

    def test_ram_says_the_data_is_lost_on_reboot(self) -> None:
        assert "lost on reboot" in StorageReport("x", 1, "tmpfs", True).label

    def test_durable_says_it_survives(self) -> None:
        assert "survive" in StorageReport("x", 1, "ext4", False).label

    def test_unknown_says_unknown_and_claims_nothing(self) -> None:
        label = StorageReport("x", 1, None, None).label
        assert "unknown" in label
        assert "lost on reboot" not in label
        assert "survive" not in label


class TestHumanSize:
    @pytest.mark.parametrize(
        ("size", "shown"),
        [(512, "512B"), (1024, "1.0KiB"), (1024**2, "1.0MiB"), (1024**3, "1.0GiB")],
    )
    def test_it_reads_like_the_yaml_the_operator_wrote(self, size: int, shown: str) -> None:
        assert human_size(size) == shown


# ---------------------------------------------------------------------------
# Chốt kiểm - CẶP
# ---------------------------------------------------------------------------


class TestTheBudgetGuard:
    def test_a_budget_the_filesystem_cannot_honour_stops_startup(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """⚠ NỔ, không phải cảnh báo.

        `total_max` là lời hứa *"kho được phép lớn tới đó"*. Hệ tệp không giữ
        nổi thì lời hứa là giả, và trên tmpfs nó vỡ bằng **OOM kill cả tiến
        trình** - VPS thường không có swap. Chặn ở đây tốn một dòng YAML.
        """
        monkeypatch.setattr(
            "xime.starters.lmdb._env.inspect_storage",
            lambda _p: StorageReport(str(tmp_path), 8 * 1024 * 1024, "tmpfs", True),
        )

        with pytest.raises(StartupException, match="Store Budget Exceeds The Filesystem"):
            LmdbEnvironment(_runtime(str(tmp_path / "s"), total_max="32MB"))

    def test_a_budget_that_fits_starts_normally(self, tmp_path: Path, monkeypatch) -> None:
        """Vế thứ hai của cặp, và là vế bảo vệ 31 ứng dụng: cách "sửa" bằng
        việc luôn luôn nổ cũng qua được test trên."""
        monkeypatch.setattr(
            "xime.starters.lmdb._env.inspect_storage",
            lambda _p: StorageReport(str(tmp_path), 1024**3, "tmpfs", True),
        )

        env = LmdbEnvironment(_runtime(str(tmp_path / "s"), total_max="32MB"))
        assert env.config.total_max == 32 * 1024 * 1024

    def test_exactly_fitting_is_allowed(self, tmp_path: Path, monkeypatch) -> None:
        """Ranh giới: `<=` chứ không phải `<`. Hứa đúng bằng chỗ đang có là một
        lời hứa giữ được."""
        monkeypatch.setattr(
            "xime.starters.lmdb._env.inspect_storage",
            lambda _p: StorageReport(str(tmp_path), 32 * 1024 * 1024, "tmpfs", True),
        )

        assert LmdbEnvironment(_runtime(str(tmp_path / "s"), total_max="32MB"))

    def test_an_unmeasurable_filesystem_does_not_block_startup(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """⭐ *"Không đo được"* KHÔNG được đối xử như *"không đủ chỗ"*.

        Chặn khởi động vì một phép đo im lặng là biến một chỗ mù thành một lần
        chết - đúng loại phép dò kêu oan rồi bị tắt.
        """
        monkeypatch.setattr(
            "xime.starters.lmdb._env.inspect_storage",
            lambda _p: StorageReport(str(tmp_path), None, None, None),
        )

        assert LmdbEnvironment(_runtime(str(tmp_path / "s"), total_max="99GB"))

    def test_the_message_names_both_ways_out(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "xime.starters.lmdb._env.inspect_storage",
            lambda _p: StorageReport(str(tmp_path), 1024, "tmpfs", True),
        )

        with pytest.raises(StartupException) as exc:
            LmdbEnvironment(_runtime(str(tmp_path / "s"), total_max="32MB"))

        message = str(exc.value)
        assert "lmdb.total_max" in message
        assert "RuntimeDirectorySize" in message
        assert "--shm-size" in message

    def test_the_message_warns_about_an_out_of_memory_kill_only_on_ram(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Vế đối chứng: trên đĩa hết chỗ là hết chỗ, không phải bị giết vì hết
        bộ nhớ. Nói sai cách hỏng là gửi người vận hành đi tìm nhầm hướng.

        ⚠ Đo cả CÂU chứ không đo ba chữ cái: bản đầu của test này khớp `"OOM"`
        và **đỏ vì chính tên nó** nằm trong `tmp_path` in ra ở thông báo.
        """
        warning = "OOM kill of the whole process"

        monkeypatch.setattr(
            "xime.starters.lmdb._env.inspect_storage",
            lambda _p: StorageReport(str(tmp_path), 1024, "tmpfs", True),
        )
        with pytest.raises(StartupException) as on_ram:
            LmdbEnvironment(_runtime(str(tmp_path / "s"), total_max="32MB"))
        assert warning in str(on_ram.value)

        monkeypatch.setattr(
            "xime.starters.lmdb._env.inspect_storage",
            lambda _p: StorageReport(str(tmp_path), 1024, "ext4", False),
        )
        with pytest.raises(StartupException) as on_disk:
            LmdbEnvironment(_runtime(str(tmp_path / "s"), total_max="32MB"))
        assert warning not in str(on_disk.value)


class TestTheStartupLine:
    def test_it_says_where_and_whether_it_is_ram(
        self, tmp_path: Path, monkeypatch, caplog
    ) -> None:
        monkeypatch.setattr(
            "xime.starters.lmdb._env.inspect_storage",
            lambda _p: StorageReport(str(tmp_path), 1024**3, "tmpfs", True),
        )

        with caplog.at_level(logging.INFO, logger="xime.starters.lmdb._env"):
            LmdbEnvironment(_runtime(str(tmp_path / "s")))

        assert "lost on reboot" in caplog.text
        assert "total_max=32.0MiB" in caplog.text

    def test_it_says_the_opposite_for_durable_storage(
        self, tmp_path: Path, monkeypatch, caplog
    ) -> None:
        """Vế thứ hai: một dòng log luôn nói cùng một câu không tách được hai
        nghĩa nào cả."""
        monkeypatch.setattr(
            "xime.starters.lmdb._env.inspect_storage",
            lambda _p: StorageReport(str(tmp_path), 1024**3, "ext4", False),
        )

        with caplog.at_level(logging.INFO, logger="xime.starters.lmdb._env"):
            LmdbEnvironment(_runtime(str(tmp_path / "s")))

        assert "survive a reboot" in caplog.text

    def test_measuring_does_not_create_the_directory(self, tmp_path: Path) -> None:
        """⚠ Đo, không chiếm. Luật 2.7 cấm dựng DI mà chiếm tài nguyên, và một
        thư mục được tạo ra ở mọi tiến trình là đúng thứ nó cấm."""
        target = tmp_path / "chua-co"
        LmdbEnvironment(_runtime(str(target)))
        assert not target.exists()
