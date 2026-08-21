"""Bề mặt đồng bộ của bus - dành cho tiến trình gốc, thứ **không có event loop**.

Cha `waitpid`, đọc bộ nhớ, ngủ. Nó vẫn phải nói được với con (*"bạn là primary
từ giờ"*) và nghe con báo lại, mà ghi vào bus vốn **đã là một thao tác đồng bộ**:
`announce()` không `await` một dòng nào, nó chỉ bọc `_publish` cho cân với `ask()`.
"""

from __future__ import annotations

import pytest

from xime.core.link import ChannelSpec, LinkError, ProcessLink

SPECS = {"ctl": ChannelSpec(rows=8, payload_bytes=64)}


@pytest.fixture
def pair():
    """Hai ô: 0 là "con", 1 là "cha" - cha giữ ô cuối, như trong thật."""
    parent = ProcessLink.create(SPECS, 2, index=1)
    child = ProcessLink.attach(parent.link_id, SPECS, 2, 0, parent.bells)
    try:
        yield child, parent
    finally:
        child.close()
        parent.close()


class TestTheCreatorPicksItsOwnSlot:
    def test_it_defaults_to_zero(self) -> None:
        link = ProcessLink.create(SPECS, 2)
        try:
            assert link.index == 0
        finally:
            link.close()

    def test_but_the_supervisor_takes_the_last_one(self) -> None:
        """⚠ Để cha ở ô 0 thì cha và con thứ nhất dùng chung một vùng ghi và một
        cái chuông - cha đọc tin của con, con không bao giờ thấy lệnh của cha,
        và **cả hai đều im lặng**."""
        link = ProcessLink.create(SPECS, 3, index=2)
        try:
            assert link.index == 2
        finally:
            link.close()

    def test_a_slot_outside_the_cluster_is_refused(self) -> None:
        with pytest.raises(LinkError, match="outside"):
            ProcessLink.create(SPECS, 2, index=5)


class TestSyncSendAndDrain:
    def test_the_parent_speaks_and_the_child_hears(self, pair) -> None:
        child, parent = pair
        parent.announce_sync("ctl", b"\x00\x01", key="promote")
        got = child.drain_sync("ctl")
        assert [(m.key, m.payload) for m in got] == [("promote", b"\x00\x01")]
        assert got[0].sender == parent.index

    def test_the_child_speaks_and_the_parent_hears(self, pair) -> None:
        child, parent = pair
        child.announce_sync("ctl", b"\x00\x00", key="ready")
        assert [m.key for m in parent.drain_sync("ctl")] == ["ready"]

    def test_reading_twice_does_not_repeat(self, pair) -> None:
        """Đọc là hạ bit. Không hạ thì cha xử lý cùng một tin ở mọi vòng giám
        sát, tức một lần thăng cấp thành một vòng thăng cấp vô hạn."""
        child, parent = pair
        parent.announce_sync("ctl", b"\x00\x00", key="promote")
        assert len(child.drain_sync("ctl")) == 1
        assert child.drain_sync("ctl") == []

    def test_nothing_pending_is_an_empty_list_not_an_error(self, pair) -> None:
        child, _ = pair
        assert child.drain_sync("ctl") == []

    def test_order_is_preserved(self, pair) -> None:
        child, parent = pair
        for i in range(5):
            parent.announce_sync("ctl", bytes([i]), key="promote")
        assert [m.payload[0] for m in child.drain_sync("ctl")] == [0, 1, 2, 3, 4]

    def test_a_sender_never_reads_its_own_message(self, pair) -> None:
        # Cha phát lệnh thăng cấp rồi tự đọc lại nó ở vòng sau là cha tự trả lời
        # chính mình - và với `PROMOTE_FAILED` thì đó là một vòng lặp.
        _, parent = pair
        parent.announce_sync("ctl", b"\x00\x00", key="promote")
        assert parent.drain_sync("ctl") == []

    def test_an_oversized_payload_still_explodes(self, pair) -> None:
        """Bề mặt đồng bộ **không** nới lỏng phép kiểm nào - trả về một kết cục
        thay vì nổ là mời người ta `except` rồi bỏ qua."""
        _, parent = pair
        with pytest.raises(LinkError, match="exceeds"):
            parent.announce_sync("ctl", b"x" * 999, key="promote")
