"""Dọn vùng nhớ mồ côi của những lần chạy trước.

⚠ Chỉ Linux mới có chuyện này: trên Windows vùng nhớ biến mất khi handle cuối
đóng, còn trên Linux nó là một file thật trong `/dev/shm` - mà `/dev/shm` là
RAM, nên rác ở đó là RAM không ai đòi lại.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from xime.core.link._cleanup import _alive, _owner_pid, sweep_orphans

_LINUX_ONLY = pytest.mark.skipif(
    sys.platform == "win32", reason="/dev/shm chỉ có trên Linux"
)


class TestOwnerPid:
    def test_it_reads_the_pid_out_of_the_block_name(self):
        """pid nằm trong tên chính là thứ trả lời được "còn ai giữ cái này không"."""
        assert _owner_pid("xime-link-4242-a3f9c1-fieldbus") == 4242

    def test_a_channel_name_with_dashes_does_not_confuse_it(self):
        assert _owner_pid("xime-link-7-abc-nha-kinh-A") == 7

    @pytest.mark.parametrize("name", ["xime-link-abc-x-y", "xime-link--x", "xime-link-"])
    def test_a_name_it_cannot_read_yields_nothing(self, name):
        """Không đọc được pid thì KHÔNG xoá - thà để rác còn hơn xoá nhầm."""
        assert _owner_pid(name) is None


class TestAlive:
    def test_this_process_is_alive(self):
        assert _alive(os.getpid())

    def test_a_pid_that_cannot_exist_is_not_alive(self):
        """Vế đối chứng: phép dò phải phân biệt được, không chỉ luôn trả True."""
        assert not _alive(_unused_pid())


class TestSweep:
    def test_it_is_a_no_op_where_there_is_no_shm(self):
        """Trên Windows nó trả 0 ngay, không nổ - dọn dẹp không được kén môi trường."""
        assert sweep_orphans() >= 0

    @_LINUX_ONLY
    def test_it_removes_a_block_whose_owner_is_gone(self):
        orphan = Path("/dev/shm") / f"xime-link-{_unused_pid()}-testrun-fieldbus"
        orphan.write_bytes(b"rac")
        try:
            sweep_orphans()
            assert not orphan.exists()
        finally:
            orphan.unlink(missing_ok=True)

    @_LINUX_ONLY
    def test_it_leaves_a_block_whose_owner_is_still_running(self):
        """Vế đối chứng, và là vế quan trọng hơn.

        Chỉ test "xoá được" thì một hiện thực xoá sạch mọi thứ cũng qua - và nó
        sẽ giật vùng nhớ khỏi tay một ứng dụng Xime khác đang chạy trên cùng máy.
        """
        live = Path("/dev/shm") / f"xime-link-{os.getpid()}-testrun-fieldbus"
        live.write_bytes(b"cua toi")
        try:
            sweep_orphans()
            assert live.exists()
        finally:
            live.unlink(missing_ok=True)

    @_LINUX_ONLY
    def test_it_never_touches_a_name_that_is_not_ours(self):
        other = Path("/dev/shm") / "someone-elses-block"
        other.write_bytes(b"khong phai cua xime")
        try:
            sweep_orphans()
            assert other.exists()
        finally:
            other.unlink(missing_ok=True)


def _unused_pid() -> int:
    """Một pid gần như chắc chắn không tồn tại, tìm bằng cách hỏi thật."""
    for candidate in range(999_000, 999_100):
        if not _alive(candidate):
            return candidate
    pytest.skip("không tìm được pid trống để đối chứng")
